import { authenticate } from "./auth";
import { currentAuthority } from "./core";
import type { EventRow } from "./domain";
import { enqueueInvalidation } from "./push";
import { apiError, isAvailableLabel, json, nowIso, readJsonBody, sha256Hex } from "./util";

type ResourceType="PDA"|"USER_PICK"|"PACK_TABLE"|"USER_PACK";
type Operation="UPSERT"|"DELETE";
interface Body{operation:Operation;resource_type:ResourceType;resource_id:string;status_label?:string;metadata?:Record<string,unknown>;idempotency_key:string;}
const NS:Record<ResourceType,string>={PDA:"pda",USER_PICK:"user_pick",PACK_TABLE:"pack_table",USER_PACK:"user_pack"};
const ENTITY:Record<ResourceType,string>={PDA:"MASTER_PDA",USER_PICK:"MASTER_USER_PICK",PACK_TABLE:"MASTER_PACK_TABLE",USER_PACK:"MASTER_USER_PACK"};
function text(v:unknown,max=180):string{return String(v??"").trim().slice(0,max);}
function shiftFrom(label:string,table:string):string{const f=label.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase().trim(),t=table.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toUpperCase().trim();if(f.startsWith("CA 1-"))return "Ca 1";if(f.startsWith("CA 2-"))return "Ca 2";if(f.startsWith("HP-")||t==="HP")return "Ca HC";return "";}
function cleanMeta(raw:Record<string,unknown>|undefined):Record<string,unknown>{const out:Record<string,unknown>={};for(const [k,v] of Object.entries(raw||{})){const key=text(k,80);if(!key||/pass|password|token|secret|cookie|authorization|verifier|private.?key/i.test(key))continue;out[key]=typeof v==="boolean"||typeof v==="number"?v:text(v,300);}return out;}

export async function resourceAdminList(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const [resources,maps,catalogs]=await env.DB.batch([
    env.DB.prepare("SELECT resource_type,resource_id,status_label,available,metadata_json FROM resources ORDER BY resource_type,resource_id"),
    env.DB.prepare("SELECT pack_table,shift,user_pack,label,available FROM resource_pack_map ORDER BY pack_table,shift,user_pack"),
    env.DB.prepare("SELECT namespace,ordinal,value FROM catalog_values WHERE namespace IN ('DANH SÁCH PDA_Tình trạng','DANH SÁCH USER PICK_Tình trạng','DANH SÁCH BÀN PACK_Tình trạng','DANH SÁCH USER PACK_Tình trạng') ORDER BY namespace,ordinal"),
  ]);
  return json({ok:true,resources:resources.results??[],pack_map:maps.results??[],catalogs:catalogs.results??[],can_edit:auth.role==="ADMIN"||auth.role==="SUPERADMIN"});
}

export async function resourceAdminMutate(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);if(auth.role!=="ADMIN"&&auth.role!=="SUPERADMIN")return apiError("ADMIN_REQUIRED","PERMISSION",403);
  const b=await readJsonBody<Body>(request),operation=String(b.operation||"").toUpperCase() as Operation,type=String(b.resource_type||"").toUpperCase() as ResourceType,id=text(b.resource_id),idem=text(b.idempotency_key,220);
  if(!["UPSERT","DELETE"].includes(operation)||!["PDA","USER_PICK","PACK_TABLE","USER_PACK"].includes(type)||!id||!idem)return apiError("RESOURCE_ADMIN_FIELDS_REQUIRED","VALIDATION",400);
  const prior=await env.DB.prepare("SELECT * FROM events WHERE idempotency_key=?1").bind(idem).first<EventRow>();if(prior)return json({ok:true,duplicate:true,event:prior});
  const authority=await currentAuthority(env.DB);if(authority.mode!=="SERVICE_PRIMARY"||authority.scope!=="PRODUCTION")return apiError("SERVICE_NOT_WRITE_AUTHORITY","CONFLICT",409,true);
  const leased=await env.DB.prepare("SELECT 1 x FROM resource_leases WHERE resource_type=?1 AND resource_id=?2 LIMIT 1").bind(type,id).first();if(operation==="DELETE"&&leased)return apiError("RESOURCE_IN_USE","RESOURCE",409,false);
  const before=await env.DB.prepare("SELECT resource_type,resource_id,status_label,available,metadata_json FROM resources WHERE resource_type=?1 AND resource_id=?2").bind(type,id).first<Record<string,unknown>>();
  if(operation==="DELETE"&&!before)return apiError("RESOURCE_NOT_FOUND","VALIDATION",404);
  const at=nowIso(),meta=cleanMeta(b.metadata),status=text(b.status_label).ifBlank?.();
  const statusLabel=text(b.status_label)||text(before?.status_label)||"Hoạt động",available=isAvailableLabel(statusLabel)?1:0,after=operation==="DELETE"?null:{resource_type:type,resource_id:id,status_label:statusLabel,available,metadata_json:JSON.stringify(meta)};
  const seq=authority.authority_seq+1,namespace=NS[type],rev=(await env.DB.prepare("SELECT revision FROM revision_state WHERE namespace=?1").bind(namespace).first<{revision:number}>())?.revision??0,newRev=rev+1;
  const base={event_id:crypto.randomUUID(),event_type:operation==="DELETE"?"MASTER_RESOURCE_DELETE":"MASTER_RESOURCE_UPSERT",entity_type:ENTITY[type],entity_id:id,business_date:"MASTER",authority_epoch:authority.authority_epoch,authority_seq:seq,service_generation:authority.service_generation,base_version:rev,new_version:newRev,actor_id:auth.login_id,actor_role:auth.role,device_id:auth.device_id,occurred_at:at,committed_at:at,payload_json:JSON.stringify({source:"PDA_RESOURCE_ADMIN",operation,before,after,resource_type:type,namespace}),idempotency_key:idem,origin:"PDA_RESOURCE_ADMIN",schema_version:1},event:EventRow={...base,checksum:await sha256Hex(JSON.stringify(base))};
  const stmts:D1PreparedStatement[]=[];
  if(operation==="UPSERT"){
    stmts.push(env.DB.prepare("INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,0,?6) ON CONFLICT(resource_type,resource_id) DO UPDATE SET status_label=excluded.status_label,available=excluded.available,metadata_json=excluded.metadata_json,source_checksum=excluded.source_checksum").bind(type,id,statusLabel,available,JSON.stringify(meta),event.event_id));
    if(type==="USER_PACK"){
      const table=text(meta["Tên bàn pack"]??meta.pack_table),label=text(meta["User pack"]??meta.label),shift=shiftFrom(label,table);
      if(table&&shift)stmts.push(env.DB.prepare("INSERT INTO resource_pack_map(pack_table,shift,user_pack,label,available,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,0,?6) ON CONFLICT(pack_table,shift) DO UPDATE SET user_pack=excluded.user_pack,label=excluded.label,available=excluded.available,source_checksum=excluded.source_checksum").bind(table,shift,id,label,available,event.event_id));
    }
  }else{
    stmts.push(env.DB.prepare("DELETE FROM resources WHERE resource_type=?1 AND resource_id=?2").bind(type,id));
    if(type==="USER_PACK")stmts.push(env.DB.prepare("DELETE FROM resource_pack_map WHERE user_pack=?1").bind(id));
    if(type==="PACK_TABLE")stmts.push(env.DB.prepare("DELETE FROM resource_pack_map WHERE pack_table=?1").bind(id));
  }
  stmts.push(env.DB.prepare("UPDATE revision_state SET revision=?1,updated_at=?2 WHERE namespace=?3 AND revision=?4").bind(newRev,at,namespace,rev));
  stmts.push(env.DB.prepare("UPDATE authority_state SET authority_seq=?1,updated_at=?2 WHERE singleton_id=1 AND authority_epoch=?3 AND authority_seq=?4").bind(seq,at,authority.authority_epoch,authority.authority_seq));
  stmts.push(env.DB.prepare("INSERT INTO events(event_id,event_type,entity_type,entity_id,business_date,authority_epoch,authority_seq,service_generation,base_version,new_version,actor_id,actor_role,device_id,occurred_at,committed_at,payload_json,idempotency_key,origin,schema_version,checksum) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20)").bind(event.event_id,event.event_type,event.entity_type,event.entity_id,event.business_date,event.authority_epoch,event.authority_seq,event.service_generation,event.base_version,event.new_version,event.actor_id,event.actor_role,event.device_id,event.occurred_at,event.committed_at,event.payload_json,event.idempotency_key,event.origin,event.schema_version,event.checksum));
  stmts.push(env.DB.prepare("INSERT INTO sheet_replication_outbox(event_id,status,next_attempt_at) VALUES(?1,'PENDING',?2)").bind(event.event_id,at));
  try{await env.DB.batch(stmts);}catch(e){return apiError("RESOURCE_ADMIN_CONFLICT","TRANSIENT",409,true,String(e).slice(0,160));}
  await enqueueInvalidation(env.DB,namespace,newRev);
  try{const hub=env.REALTIME_HUB.getByName("master:global") as unknown as {invalidate(message:Record<string,unknown>):Promise<number>};await hub.invalidate({type:"MASTER_CHANGED",namespace,revision:newRev,authority_epoch:event.authority_epoch,authority_seq:event.authority_seq});}catch{}
  return json({ok:true,duplicate:false,event,resource:after,deleted:operation==="DELETE",namespace,revision:newRev},201);
}

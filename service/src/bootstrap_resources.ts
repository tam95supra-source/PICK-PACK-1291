import { fold, isAvailableLabel } from "./util";

type StoredRow = { row_index:number; row_checksum:string; row_json:string };
type BootstrapState = Record<string, unknown> & { phase?:string; warnings?:Array<Record<string,unknown>> };
type Candidate = {
  resource_type:string;
  resource_id:string;
  status_label:string;
  available:number;
  metadata_json:string;
  source_row:number;
  source_checksum:string;
  valid_reference:boolean;
};
type PackMapping = {
  pack_table:string;
  shift:string;
  user_pack:string;
  label:string;
  available:number;
  source_row:number;
  source_checksum:string;
};

async function rows(db:D1Database,sheet:string):Promise<StoredRow[]>{
  const got=await db.prepare("SELECT row_index,row_checksum,row_json FROM source_rows WHERE sheet_name=?1 ORDER BY row_index").bind(sheet).all<StoredRow>();
  return got.results??[];
}
function arr(x:StoredRow):string[]{
  const raw=JSON.parse(x.row_json) as unknown[];
  return raw.map(v=>String(v??"").trim());
}
function shiftFrom(label:string,table:string):string{
  const f=fold(label),t=fold(table);
  if(f.startsWith("CA 1-"))return "Ca 1";
  if(f.startsWith("CA 2-"))return "Ca 2";
  if(f.startsWith("HP-")||t==="HP")return "Ca HC";
  return "";
}
async function chunks(db:D1Database,stmts:D1PreparedStatement[],size=50):Promise<void>{
  for(let i=0;i<stmts.length;i+=size)await db.batch(stmts.slice(i,i+size));
}
function resourceStmt(db:D1Database,c:Candidate):D1PreparedStatement{
  return db.prepare("INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7)")
    .bind(c.resource_type,c.resource_id,c.status_label,c.available,c.metadata_json,c.source_row,c.source_checksum);
}

export async function bootstrapResourceProjectionStep(db:D1Database,runId:string):Promise<Record<string,unknown>>{
  const run=await db.prepare("SELECT status,manifest_json FROM bootstrap_runs WHERE run_id=?1").bind(runId).first<{status:string;manifest_json:string}>();
  if(!run)throw new Error("BOOTSTRAP_RUN_NOT_FOUND");
  if(run.status!=="RUNNING")throw new Error(`BOOTSTRAP_RUN_NOT_RUNNING:${run.status}`);
  const state=JSON.parse(run.manifest_json) as BootstrapState;
  if(state.phase!=="RESOURCES")throw new Error(`BOOTSTRAP_RESOURCE_PHASE_INVALID:${String(state.phase)}`);

  const warnings:Array<Record<string,unknown>>=Array.isArray(state.warnings)?state.warnings:[];
  const pdaRows=await rows(db,"DANH SÁCH PDA");
  const pickRows=await rows(db,"DANH SÁCH USER PICK");
  const tableRows=await rows(db,"DANH SÁCH BÀN PACK");
  const packRows=await rows(db,"DANH SÁCH USER PACK");

  const validTables=new Set<string>();
  for(const x of tableRows){const r=arr(x),id=r[0]||"";if(id)validTables.add(id);}

  const selected=new Map<string,Candidate>();
  const put=(c:Candidate)=>{
    if(!c.resource_id)return;
    const key=`${c.resource_type}\u0000${c.resource_id}`,old=selected.get(key);
    if(!old){selected.set(key,c);return;}
    warnings.push({code:"DUPLICATE_RESOURCE_ID",resource_type:c.resource_type,resource_id:c.resource_id,kept_source_row:old.source_row,candidate_source_row:c.source_row});
    if(!old.valid_reference&&c.valid_reference){selected.set(key,c);return;}
    if(old.valid_reference===c.valid_reference&&c.source_row<old.source_row)selected.set(key,c);
  };

  for(const x of pdaRows){const r=arr(x);put({resource_type:"PDA",resource_id:r[0]||"",status_label:r[2]||"",available:isAvailableLabel(r[2]||"")?1:0,metadata_json:JSON.stringify({"Seri PDA":r[0]||"","5 số cuối Seri":r[1]||"","Tình trạng":r[2]||"","Ghi chú":r[3]||""}),source_row:x.row_index,source_checksum:x.row_checksum,valid_reference:true});}
  for(const x of pickRows){const r=arr(x);put({resource_type:"USER_PICK",resource_id:r[1]||"",status_label:r[2]||"",available:isAvailableLabel(r[2]||"")?1:0,metadata_json:JSON.stringify({"Số User":r[0]||"","User Pick":r[1]||"","Tình trạng":r[2]||"","Ghi chú":r[3]||""}),source_row:x.row_index,source_checksum:x.row_checksum,valid_reference:true});}
  for(const x of tableRows){const r=arr(x);put({resource_type:"PACK_TABLE",resource_id:r[0]||"",status_label:r[1]||"",available:isAvailableLabel(r[1]||"")?1:0,metadata_json:JSON.stringify({"Tên bàn pack":r[0]||"","Tình trạng":r[1]||""}),source_row:x.row_index,source_checksum:x.row_checksum,valid_reference:true});}

  const mappings:PackMapping[]=[];
  const mapByShiftUser=new Map<string,PackMapping>();
  for(const x of packRows){
    const r=arr(x),table=r[0]||"",label=r[1]||"",user=r[2]||"",status=r[3]||"",validTable=validTables.has(table),shift=shiftFrom(label,table);
    if(!user)continue;
    put({resource_type:"USER_PACK",resource_id:user,status_label:status,available:isAvailableLabel(status)?1:0,metadata_json:JSON.stringify({"Tên bàn pack":table,"User pack":label,"User Pack":user,"Tình trạng":status}),source_row:x.row_index,source_checksum:x.row_checksum,valid_reference:validTable});
    if(!validTable){warnings.push({code:"PACK_TABLE_REFERENCE_MISSING",pack_table:table,user_pack:user,label,source_row:x.row_index});continue;}
    if(!shift){warnings.push({code:"PACK_SHIFT_UNRECOGNIZED",pack_table:table,user_pack:user,label,source_row:x.row_index});continue;}
    const m:PackMapping={pack_table:table,shift,user_pack:user,label,available:isAvailableLabel(status)?1:0,source_row:x.row_index,source_checksum:x.row_checksum};
    const uniqueKey=`${shift}\u0000${user}`,old=mapByShiftUser.get(uniqueKey);
    if(old){warnings.push({code:"DUPLICATE_PACK_USER_SHIFT",shift,user_pack:user,kept_pack_table:old.pack_table,kept_source_row:old.source_row,candidate_pack_table:table,candidate_source_row:x.row_index});continue;}
    mapByShiftUser.set(uniqueKey,m);mappings.push(m);
  }

  const stmts:D1PreparedStatement[]=[db.prepare("DELETE FROM resource_pack_map"),db.prepare("DELETE FROM resources")];
  for(const c of selected.values())stmts.push(resourceStmt(db,c));
  for(const m of mappings)stmts.push(db.prepare("INSERT INTO resource_pack_map(pack_table,shift,user_pack,label,available,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(m.pack_table,m.shift,m.user_pack,m.label,m.available,m.source_row,m.source_checksum));
  await chunks(db,stmts);

  state.phase="ACCOUNTS";
  state.warnings=warnings;
  await db.prepare("UPDATE bootstrap_runs SET manifest_json=?1 WHERE run_id=?2 AND status='RUNNING'").bind(JSON.stringify(state),runId).run();
  return {ok:true,done:false,run_id:runId,phase:"ACCOUNTS",state,resource_count:selected.size,pack_mapping_count:mappings.length,warnings};
}

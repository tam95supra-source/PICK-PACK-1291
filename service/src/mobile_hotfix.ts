import { authenticate } from "./auth";
import { currentAuthority } from "./core";
import { bangkokToday, ensureCurrentBangkokBusinessDate } from "./business_date";
import { apiError, b64u, b64uDecode, hmacB64u, json, nowIso, readJsonBody } from "./util";

const GAS_API_URL = "https://script.google.com/macros/s/AKfycbzbEoGfbNg6s2HnP-gUpcBJ7mMIkVBtYuQKMndb9seDV2c55lQwSUO1GZ-LtQ2CxMCauA/exec";

type GasTokenPayload = { l?:string; r?:string; v?:string; s?:string; d?:string };
type Employee = { mnv:string; full_name:string; phone:string; main_position:string; supplier:string; department:string; site:string; warehouse:string; start_date:string; note:string };

function parseGasToken(token:string):GasTokenPayload|null{
  try{
    const first=token.split(".")[0]; if(!first)return null;
    return JSON.parse(new TextDecoder().decode(b64uDecode(first))) as GasTokenPayload;
  }catch{return null;}
}

async function validateGasSession(gasToken:string,payload:GasTokenPayload):Promise<Record<string,unknown>|null>{
  const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),4500);
  try{
    const response=await fetch(GAS_API_URL,{
      method:"POST",
      headers:{"content-type":"application/json; charset=utf-8","accept":"application/json"},
      body:JSON.stringify({action:"m2_authority_status",_token:gasToken,_device_id:String(payload.d||""),_app_channel:"BETA",_app_version:"m2-session-exchange-v1"}),
      signal:controller.signal,
    });
    const body=await response.json() as Record<string,unknown>;
    return response.ok&&body.ok===true?body:null;
  }catch{return null;}finally{clearTimeout(timer);}
}

export async function exchangeGasSession(request:Request,env:Env):Promise<Response>{
  const input=await readJsonBody<{gas_token?:string;device_id?:string;device_label?:string}>(request,64_000);
  const gasToken=String(input.gas_token||"").trim(),deviceId=String(input.device_id||"").trim().slice(0,180);
  if(!gasToken||!deviceId)return apiError("SESSION_EXCHANGE_FIELDS_REQUIRED","VALIDATION",400);
  const payload=parseGasToken(gasToken);
  if(!payload?.l||!payload.r||!payload.v||!payload.s||!payload.d)return apiError("GAS_SESSION_INVALID","AUTH",401);
  const discovery=await validateGasSession(gasToken,payload);
  if(!discovery)return apiError("GAS_SESSION_INVALID","AUTH",401);
  if(String(discovery.authority_mode||"")!=="SERVICE_PRIMARY")return apiError("SERVICE_NOT_PRIMARY","CONFLICT",409,true);

  const account=await env.DB.prepare("SELECT login_id,role,display_name,position,email,verifier_hash,status FROM accounts WHERE login_id=?1")
    .bind(String(payload.l)).first<{login_id:string;role:string;display_name:string;position:string;email:string;verifier_hash:string;status:string}>();
  if(!account||account.status!=="ACTIVE"||account.role!==String(payload.r))return apiError("SESSION_EXCHANGE_ACCOUNT_MISMATCH","AUTH",401);

  const current=await env.DB.prepare("SELECT session_id,device_id FROM auth_sessions WHERE login_id=?1").bind(account.login_id).first<{session_id:string;device_id:string}>();
  const reused=Boolean(current?.session_id&&current.device_id===deviceId);
  const sessionId=reused?String(current?.session_id):crypto.randomUUID(),issuedAt=nowIso();
  await env.DB.prepare(`INSERT INTO auth_sessions(login_id,session_id,device_id,issued_at) VALUES(?1,?2,?3,?4)
    ON CONFLICT(login_id) DO UPDATE SET session_id=excluded.session_id,device_id=excluded.device_id,issued_at=excluded.issued_at`)
    .bind(account.login_id,sessionId,deviceId,issuedAt).run();
  const servicePayload={l:account.login_id,r:account.role,v:account.verifier_hash,s:sessionId,d:deviceId};
  const encoded=b64u(new TextEncoder().encode(JSON.stringify(servicePayload)));
  const sig=await hmacB64u(new TextEncoder().encode(env.SERVICE_TOKEN_SECRET),encoded);
  return json({ok:true,token:`${encoded}.${sig}`,account:{login_id:account.login_id,role:account.role,display_name:account.display_name,position:account.position,email:account.email},session:{issued_at:issuedAt,device_label:String(input.device_label||"").slice(0,120),session_id:sessionId,reused},authority:discovery.authority,authority_mode:discovery.authority_mode,service_generation:discovery.service_generation});
}

async function businessDate(db:D1Database):Promise<string>{
  const date=bangkokToday();await ensureCurrentBangkokBusinessDate(db,date);return date;
}

function employeeJson(e:Employee|null){return e?{mnv:e.mnv,full_name:e.full_name,phone:e.phone,main_position:e.main_position,supplier:e.supplier,department:e.department,site:e.site,warehouse:e.warehouse,start_date:e.start_date,note:e.note}:null;}
function visibleWork(v:string){return v==="KHONG"?"KHÔNG":v;}

async function resourceOptions(db:D1Database,date:string,mnv:string):Promise<Record<string,unknown>>{
  const leaseRows=(await db.prepare("SELECT resource_type,resource_id,mnv FROM resource_leases WHERE business_date=?1").bind(date).all<{resource_type:string;resource_id:string;mnv:string}>()).results??[];
  const busy=new Set(leaseRows.map(x=>`${x.resource_type}|${x.resource_id}`));
  const usedRows=(await db.prepare("SELECT resource_type,resource_id,mnv FROM resource_daily_consumption WHERE business_date=?1").bind(date).all<{resource_type:string;resource_id:string;mnv:string}>()).results??[];
  const used=new Set(usedRows.map(x=>`${x.resource_type}|${x.resource_id}`));
  const current=await db.prepare("SELECT pda_serial,user_pick,pack_table,user_pack FROM attendance_sessions WHERE business_date=?1 AND mnv=?2 AND state='ACTIVE'").bind(date,mnv).first<{pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null}>();
  const pdasRaw=(await db.prepare("SELECT resource_id,status_label,metadata_json FROM resources WHERE resource_type='PDA' AND available=1 ORDER BY resource_id").all<{resource_id:string;status_label:string;metadata_json:string}>()).results??[];
  const pdas=pdasRaw.filter(x=>!busy.has(`PDA|${x.resource_id}`)||x.resource_id===current?.pda_serial).map(x=>{let m:Record<string,unknown>={};try{m=JSON.parse(x.metadata_json) as Record<string,unknown>;}catch{}return{serial:x.resource_id,last5:String(m["5 số cuối Seri"]||x.resource_id.slice(-5)),status:x.status_label};});
  const picksRaw=(await db.prepare("SELECT resource_id FROM resources WHERE resource_type='USER_PICK' AND available=1 ORDER BY resource_id").all<{resource_id:string}>()).results??[];
  const user_picks:string[]=[],user_picks_reissue:Array<Record<string,unknown>>=[];
  for(const x of picksRaw){const id=x.resource_id,isCurrent=id===current?.user_pick,isBusy=busy.has(`USER_PICK|${id}`),isUsed=used.has(`USER_PICK|${id}`);if(isCurrent||(!isBusy&&!isUsed))user_picks.push(id);else if(!isBusy&&isUsed)user_picks_reissue.push({id,busy:false,used_today:true,duplicate_user:true,note:"PHÁT LẠI USER"});}
  const packsRaw=(await db.prepare("SELECT pack_table,shift,user_pack FROM resource_pack_map WHERE available=1 ORDER BY pack_table,shift,user_pack").all<{pack_table:string;shift:string;user_pack:string}>()).results??[];
  const pack_tables:Array<Record<string,unknown>>=[],pack_tables_reissue:Array<Record<string,unknown>>=[];
  for(const x of packsRaw){const exactCurrent=x.pack_table===current?.pack_table&&x.user_pack===current?.user_pack;const tableBusy=busy.has(`PACK_TABLE|${x.pack_table}`),userBusy=busy.has(`USER_PACK|${x.user_pack}`),userUsed=used.has(`USER_PACK|${x.user_pack}`);if(exactCurrent||(!tableBusy&&!userBusy&&!userUsed))pack_tables.push({table:x.pack_table,shift:x.shift,user_pack:x.user_pack,duplicate_user:false});else if(!tableBusy&&!userBusy&&userUsed)pack_tables_reissue.push({table:x.pack_table,shift:x.shift,user_pack:x.user_pack,duplicate_user:true,used_today:true,note:"PHÁT LẠI USER"});}
  return{ok:true,business_date:date,pdas,user_picks,user_picks_reissue,pack_tables,pack_tables_reissue,current};
}

async function employeeContext(env:Env,body:Record<string,unknown>):Promise<Response>{
  const mnv=String(body.mnv||"").trim();if(!mnv)return apiError("MNV_REQUIRED","VALIDATION",400);
  const date=await businessDate(env.DB);
  const employee=await env.DB.prepare("SELECT mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note FROM employees WHERE mnv=?1").bind(mnv).first<Employee>();
  if(!employee)return apiError("EMPLOYEE_NOT_FOUND","VALIDATION",404);
  const session=await env.DB.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,pda_enter_status,pda_exit_status,resource_note,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions WHERE business_date=?1 AND mnv=?2").bind(date,mnv).first<Record<string,unknown>>();
  const state=!session?"NOT_ENTERED":String(session.state)==="ACTIVE"?"ACTIVE":"ENDED";
  const sessionOut:Record<string,unknown>|null=session?{...session,work_choice:visibleWork(String(session.work_choice||""))}:null;
  const activeLabor=body.include_labor===true?await env.DB.prepare("SELECT labor_id,mnv,business_date,shift,labor_type,time_marker,state,start_at,end_at,note,deduct_staff,start_event_id,finish_event_id,version FROM labor_sessions WHERE business_date=?1 AND mnv=?2 AND state='OPEN' ORDER BY start_at DESC LIMIT 1").bind(date,mnv).first<Record<string,unknown>>():null;
  const options=body.include_options===true&&state==="NOT_ENTERED"?await resourceOptions(env.DB,date,mnv):null;
  return json({ok:true,source:"SERVICE_D1",business_date:date,employee:employeeJson(employee),state,session:sessionOut,active_labor:activeLabor,options});
}

function eventLabel(type:string):string{return type==="ATTENDANCE_ENTER"?"Vào ca":type==="ATTENDANCE_EXIT"?"Ra ca":type==="RESOURCE_CHANGE"?"Đổi tài nguyên":type==="LABOR_START"?"Bắt đầu công nhật":type==="LABOR_FINISH"?"Hoàn thành công nhật":type;}

async function sharedHistory(env:Env,body:Record<string,unknown>):Promise<Response>{
  const requested=String(body.business_date||"").trim();const date=requested||await businessDate(env.DB),target=String(body.mnv||"").trim();
  const raw=(await env.DB.prepare("SELECT event_id,event_type,actor_id,committed_at,payload_json FROM events WHERE business_date=?1 ORDER BY authority_seq").bind(date).all<{event_id:string;event_type:string;actor_id:string;committed_at:string;payload_json:string}>()).results??[];
  const employeeRows=(await env.DB.prepare("SELECT mnv,full_name FROM employees").all<{mnv:string;full_name:string}>()).results??[];const names=new Map(employeeRows.map(x=>[x.mnv,x.full_name]));
  const timeline=raw.map(e=>{let p:Record<string,unknown>={};try{p=JSON.parse(e.payload_json) as Record<string,unknown>;}catch{}const mnv=String(p.mnv||"");return{scope:"SESSION",session_id:`${date}|${mnv}`,mnv,full_name:names.get(mnv)||"",shift:String(p.shift||""),event_type:e.event_type,label:eventLabel(e.event_type),at:e.committed_at,at_iso:e.committed_at,actor:e.actor_id,detail:String(p.labor_type||p.note||""),event_id:e.event_id};}).filter(x=>x.mnv&&(!target||x.mnv===target));
  if(target)return json({ok:true,source:"SERVICE_D1",history_engine:"M2_CANONICAL_D1",business_date:date,mnv:target,timeline});
  const groups:Record<string,{mnv:string;full_name:string;shift:string;state:string;event_count:number;last_time:string;last_at_iso:string;last_actor:string;last_label:string}>={};
  for(const e of timeline){let g=groups[e.mnv];if(!g)g=groups[e.mnv]={mnv:e.mnv,full_name:e.full_name,shift:e.shift,state:"ACTIVE",event_count:0,last_time:"",last_at_iso:"",last_actor:"",last_label:""};if(e.full_name)g.full_name=e.full_name;if(e.shift)g.shift=e.shift;g.event_count++;if(e.event_type==="ATTENDANCE_EXIT")g.state="ENDED";g.last_time=e.at;g.last_at_iso=e.at_iso;g.last_actor=e.actor;g.last_label=e.label;}
  const items=Object.values(groups).sort((a,b)=>(Date.parse(b.last_at_iso)||0)-(Date.parse(a.last_at_iso)||0));
  return json({ok:true,source:"SERVICE_D1",history_engine:"M2_CANONICAL_D1",business_date:date,total:items.length,active_count:items.filter(x=>x.state==="ACTIVE").length,ended_count:items.filter(x=>x.state==="ENDED").length,items});
}

export async function mobileRead(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const body=await readJsonBody<Record<string,unknown>>(request,256_000),action=String(body.action||"");
  if(action==="employee_context")return employeeContext(env,body);
  if(action==="master_options")return json(await resourceOptions(env.DB,await businessDate(env.DB),String(body.mnv||"")));
  if(action==="history_shared")return sharedHistory(env,body);
  if(action==="runtime_status")return json({ok:true,source:"SERVICE_D1",authority:await currentAuthority(env.DB),service_generation:env.SERVICE_GENERATION});
  return apiError("MOBILE_READ_ACTION_UNSUPPORTED","VALIDATION",400);
}
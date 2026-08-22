import type { EventRow } from "./domain";
import { nowIso, sha256Hex } from "./util";

type GoogleToken={access_token?:string;error?:string};
type SessionRow={session_id:string;mnv:string;business_date:string;shift:string;work_choice:string;full_name:string;supplier:string;department:string;site:string};
type ConsumptionRow={business_date:string;resource_type:string;resource_id:string;mnv:string;first_event_id:string};
type Grid=unknown[][];
type Update={range:string;values:unknown[][]};

const CATALOG_HEADERS=["DANH SÁCH NHÂN SỰ_Vị trí chính","DANH SÁCH NHÂN SỰ_Nhà cung cấp","DANH SÁCH NHÂN SỰ_Bộ phận","DANH SÁCH NHÂN SỰ_Site","DANH SÁCH NHÂN SỰ_Kho","DANH SÁCH PDA_Tình trạng","DANH SÁCH USER PICK_Tình trạng","DANH SÁCH BÀN PACK_Tình trạng","DANH SÁCH USER PACK_Tình trạng","RA - VÀO TRONG CA_Loại thao tác","VÀO - RA TRONG CA_Ca","CÔNG NHẬT_Thông tin công nhật","CÔNG NHẬT_Mốc thời gian","CÔNG NHẬT_Trạng thái"] as const;
const RA_HEADERS=["Ngày","Ca","Mã nhân viên","Họ và tên","Số điện thoại","Nhà cung cấp","Bộ phận","Site","Kho","Vị trí chính","Vị trí trong ca","Seri PDA","User Pick","Bàn Pack","User Pack","Loại thao tác","Ghi chú","Người cập nhật","Thời gian cập nhật","Event ID","App action","App revision"] as const;
const USER_HEADERS=["Ngày","Ca","Mã nhân viên","Họ và tên","Nhà cung cấp","Bộ phận","Site","Vị trí trong ca","User","Người cập nhật","Event ID"] as const;
const HISTORY_HEADERS=["Ngày","Session ID","Mã nhân viên","Họ tên","Ca","Loại sự kiện","Nhãn sự kiện","Thời gian","Người xử lý","Chi tiết","Event ID","Phạm vi","App Revision"] as const;

function text(v:unknown):string{return String(v??"").trim();}
function q(name:string):string{return `'${name.replace(/'/g,"''")}'`;}
function payload(e:EventRow):Record<string,unknown>{try{return JSON.parse(e.payload_json) as Record<string,unknown>;}catch{return{};}}
function obj(v:unknown):Record<string,unknown>{return v&&typeof v==="object"&&!Array.isArray(v)?v as Record<string,unknown>:{};}
function dateVisible(v:string):string{const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(v);return m?`${m[3]}/${m[2]}/${m[1]}`:v;}
function timeVisible(v:string):string{const d=new Date(v);if(Number.isNaN(d.getTime()))return v;return new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Ho_Chi_Minh",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"}).format(d).replace(",","");}
function eventDate(e:EventRow):string{return /^\d{4}-\d{2}-\d{2}$/.test(e.business_date)?dateVisible(e.business_date):timeVisible(e.occurred_at).slice(0,10);}
function uniq(values:string[]):string[]{const out:string[]=[];for(const raw of values){const v=raw.trim();if(v&&!out.includes(v))out.push(v);}return out;}
function addResource(target:string[],p:Record<string,unknown>,key:string){const v=text(p[key]);if(v)target.push(v);}

async function googleToken(env:Env):Promise<string>{
  const body=new URLSearchParams({client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET,refresh_token:env.GOOGLE_OAUTH_REFRESH_TOKEN,grant_type:"refresh_token"});
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});const j=await r.json<GoogleToken>();if(!r.ok||!j.access_token)throw new Error(`GOOGLE_OAUTH:${j.error??r.status}`);return j.access_token;
}
async function getGrid(env:Env,token:string,sheet:string,range:string):Promise<Grid>{const full=`${q(sheet)}!${range}`,r=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(env.GOOGLE_SOURCE_SHEET_ID)}/values/${encodeURIComponent(full)}?majorDimension=ROWS&valueRenderOption=FORMATTED_VALUE`,{headers:{authorization:`Bearer ${token}`}});if(!r.ok)throw new Error(`BETA47_GOOGLE_READ:${sheet}:${r.status}`);return (await r.json<{values?:Grid}>()).values??[];}
async function batchPut(env:Env,token:string,data:Update[]):Promise<void>{if(!data.length)return;const r=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(env.GOOGLE_SOURCE_SHEET_ID)}/values:batchUpdate`,{method:"POST",headers:{authorization:`Bearer ${token}`,"content-type":"application/json"},body:JSON.stringify({valueInputOption:"RAW",data:data.map(x=>({range:x.range,majorDimension:"ROWS",values:x.values}))})});if(!r.ok){const t=await r.text();throw new Error(`BETA47_GOOGLE_WRITE:${r.status}:${t.slice(0,220)}`);}}
async function appendRows(env:Env,token:string,sheet:string,range:string,values:unknown[][],insertMode:"INSERT_ROWS"|"OVERWRITE"="INSERT_ROWS"):Promise<void>{if(!values.length)return;const full=`${q(sheet)}!${range}`,r=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(env.GOOGLE_SOURCE_SHEET_ID)}/values/${encodeURIComponent(full)}:append?valueInputOption=RAW&insertDataOption=${insertMode}`,{method:"POST",headers:{authorization:`Bearer ${token}`,"content-type":"application/json"},body:JSON.stringify({range:full,majorDimension:"ROWS",values})});if(!r.ok){const t=await r.text();throw new Error(`BETA47_GOOGLE_APPEND:${sheet}:${r.status}:${t.slice(0,220)}`);}}
function assertHeader(grid:Grid,expected:readonly string[],name:string){const got=(grid[0]??[]).slice(0,expected.length).map(String);if(JSON.stringify(got)!==JSON.stringify([...expected]))throw new Error(`BETA47_SCHEMA_DRIFT:${name}`);}

/** Beta47: Danh mục is edited directly in Google Sheet and ingested one-way into Service. */
export async function syncCatalogSource(env:Env,token?:string):Promise<{changed:boolean;revision:number;values:number}>{
  const t=token??await googleToken(env),grid=await getGrid(env,t,"Danh mục","A:N");assertHeader(grid,CATALOG_HEADERS,"Danh mục");
  const next:Array<{namespace:string;ordinal:number;value:string;source_checksum:string}>=[];
  for(let c=0;c<CATALOG_HEADERS.length;c++){
    const ns=CATALOG_HEADERS[c]!;let ordinal=0;
    for(let r=1;r<grid.length;r++){const v=text(grid[r]?.[c]);if(!v)continue;ordinal++;next.push({namespace:ns,ordinal,value:v,source_checksum:await sha256Hex(`${ns}\n${ordinal}\n${v}`)});}
  }
  const cur=(await env.DB.prepare("SELECT namespace,ordinal,value FROM catalog_values ORDER BY namespace,ordinal,value").all<{namespace:string;ordinal:number;value:string}>()).results??[];
  const a=JSON.stringify(cur.map(x=>[x.namespace,Number(x.ordinal),x.value])),b=JSON.stringify(next.map(x=>[x.namespace,x.ordinal,x.value]).sort((x,y)=>String(x[0]).localeCompare(String(y[0]))||Number(x[1])-Number(y[1])||String(x[2]).localeCompare(String(y[2]))));
  const rev=(await env.DB.prepare("SELECT revision FROM revision_state WHERE namespace='catalogs'").first<{revision:number}>())?.revision??0;
  if(a===b)return{changed:false,revision:rev,values:next.length};
  const at=nowIso(),stmts:D1PreparedStatement[]=[env.DB.prepare("DELETE FROM catalog_values")];
  for(const x of next)stmts.push(env.DB.prepare("INSERT INTO catalog_values(namespace,ordinal,value,source_checksum) VALUES(?1,?2,?3,?4)").bind(x.namespace,x.ordinal,x.value,x.source_checksum));
  stmts.push(env.DB.prepare("INSERT INTO revision_state(namespace,revision,updated_at) VALUES('catalogs',?1,?2) ON CONFLICT(namespace) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at").bind(rev+1,at));
  await env.DB.batch(stmts);return{changed:true,revision:rev+1,values:next.length};
}

type SessionAgg={session:SessionRow;pdas:string[];picks:string[];tables:string[];packs:string[];events:EventRow[];cons:ConsumptionRow[]};
function eventLabel(type:string):string{const m:Record<string,string>={ATTENDANCE_ENTER:"Vào ca",ATTENDANCE_EXIT:"Ra ca",RESOURCE_CHANGE:"Thay đổi tài nguyên",LABOR_START:"Bắt đầu công nhật",LABOR_FINISH:"Kết thúc công nhật",HISTORY_DELETE:"Xóa lịch sử",MASTER_RESOURCE_UPSERT:"Cập nhật danh sách tài nguyên",MASTER_RESOURCE_DELETE:"Xóa tài nguyên",MASTER_STAFF_UPSERT:"Cập nhật nhân sự",MASTER_STAFF_DELETE:"Xóa nhân sự",ACCOUNT_UPSERT:"Cập nhật tài khoản",ACCOUNT_STATUS:"Đổi trạng thái tài khoản",ACCOUNT_DELETE:"Xóa tài khoản",ACCOUNT_EMAIL:"Đổi email",ACCOUNT_PASSWORD:"Đổi mật khẩu",ACCOUNT_LOGIN:"Đăng nhập",ACCOUNT_LOGOUT:"Đăng xuất",SETTINGS_CHANGE:"Thay đổi cài đặt"};return m[type]??type.replace(/_/g," ");}
function eventDetail(e:EventRow):string{const p=payload(e);if(e.event_type==="HISTORY_DELETE"){const ids=Array.isArray(p.target_event_ids)?p.target_event_ids.map(String):[];return `Xóa ${Number(p.deleted_count??ids.length)} mục lịch sử${ids.length?`: ${ids.join(", ")}`:""}`.slice(0,900);}const direct=text(p.detail)||text(p.note)||text(p.labor_type);if(direct)return direct.slice(0,900);const before=obj(p.before),after=obj(p.after),keys=["work_choice","pda_serial","user_pick","pack_table","user_pack","status_label","operation"],parts:string[]=[];for(const k of keys){const bv=text(before[k]),av=text(after[k]);if(bv||av){if(bv!==av)parts.push(`${k}: ${bv||"—"} → ${av||"—"}`);}else{const v=text(p[k]);if(v)parts.push(`${k}: ${v}`);}}return parts.join(" • ").slice(0,900);}

/** Reconcile RA/USER operational projections and guarantee every canonical Service event has an audit row. */
export async function reconcileBeta47OperationalProjection(env:Env):Promise<{ra_updates:number;user_rows:number;history_rows:number;catalog_changed:boolean}>{
  const token=await googleToken(env),catalog=await syncCatalogSource(env,token);
  const [sessionsR,eventsR,consR]=await env.DB.batch([
    env.DB.prepare(`SELECT s.session_id,s.mnv,s.business_date,s.shift,s.work_choice,e.full_name,e.supplier,e.department,e.site FROM attendance_sessions s JOIN employees e ON e.mnv=s.mnv WHERE s.business_date IN (SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 7) ORDER BY s.business_date DESC,s.mnv`),
    env.DB.prepare(`SELECT * FROM events WHERE (entity_type='ATTENDANCE_SESSION' OR event_type IN ('HISTORY_DELETE','MASTER_RESOURCE_UPSERT','MASTER_RESOURCE_DELETE','MASTER_STAFF_UPSERT','MASTER_STAFF_DELETE','ACCOUNT_UPSERT','ACCOUNT_STATUS','ACCOUNT_DELETE','ACCOUNT_EMAIL','ACCOUNT_PASSWORD','ACCOUNT_LOGIN','ACCOUNT_LOGOUT','SETTINGS_CHANGE')) ORDER BY authority_seq DESC LIMIT 1500`),
    env.DB.prepare(`SELECT business_date,resource_type,resource_id,mnv,first_event_id FROM resource_daily_consumption WHERE business_date IN (SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 7) ORDER BY business_date,mnv,resource_type,resource_id`),
  ]);
  const sessions=(sessionsR?.results??[]) as unknown as SessionRow[],events=(eventsR?.results??[]) as unknown as EventRow[],cons=(consR?.results??[]) as unknown as ConsumptionRow[];
  const bySession=new Map<string,SessionAgg>(),byMnvDate=new Map<string,ConsumptionRow[]>();
  for(const c of cons){const k=`${c.business_date}|${c.mnv}`,a=byMnvDate.get(k)??[];a.push(c);byMnvDate.set(k,a);}
  for(const s of sessions)bySession.set(s.session_id,{session:s,pdas:[],picks:[],tables:[],packs:[],events:[],cons:byMnvDate.get(`${s.business_date}|${s.mnv}`)??[]});
  for(const e of events){const g=bySession.get(e.entity_id);if(!g)continue;g.events.push(e);const p=payload(e),before=obj(p.before),after=obj(p.after);for(const x of [p,before,after]){addResource(g.pdas,x,"pda_serial");addResource(g.picks,x,"user_pick");addResource(g.tables,x,"pack_table");addResource(g.packs,x,"user_pack");}}
  for(const g of bySession.values()){for(const c of g.cons){if(c.resource_type==="USER_PICK")g.picks.push(c.resource_id);if(c.resource_type==="USER_PACK")g.packs.push(c.resource_id);}g.pdas=uniq(g.pdas);g.picks=uniq(g.picks);g.tables=uniq(g.tables);g.packs=uniq(g.packs);}

  const ra=await getGrid(env,token,"RA - VÀO TRONG CA","A:V");assertHeader(ra,RA_HEADERS,"RA - VÀO TRONG CA");const eventToSession=new Map<string,SessionAgg>();for(const g of bySession.values())for(const e of g.events)eventToSession.set(e.event_id,g);const updates:Update[]=[];
  for(let i=1;i<ra.length;i++){const eventId=text(ra[i]?.[19]),g=eventToSession.get(eventId);if(!g)continue;const wanted=[g.pdas.join(", "),g.picks.join(", "),g.tables.join(", "),g.packs.join(", ")],have=(ra[i]??[]).slice(11,15).map(text);if(JSON.stringify(wanted)!==JSON.stringify(have))updates.push({range:`${q("RA - VÀO TRONG CA")}!L${i+1}:O${i+1}`,values:[wanted]});}
  await batchPut(env,token,updates);

  const users=await getGrid(env,token,"THÔNG TIN USER CỦA NLĐ","A:K");assertHeader(users,USER_HEADERS,"THÔNG TIN USER CỦA NLĐ");const existing=new Set<string>();for(let i=1;i<users.length;i++)existing.add([text(users[i]?.[0]),text(users[i]?.[2]),text(users[i]?.[7]).toUpperCase(),text(users[i]?.[8])].join("|"));const userRows:unknown[][]=[];
  for(const g of bySession.values())for(const c of g.cons){const pos=c.resource_type==="USER_PICK"?"PICK":"PACK",key=[dateVisible(g.session.business_date),g.session.mnv,pos,c.resource_id].join("|");if(existing.has(key))continue;const actor=g.events.find(e=>e.event_id===c.first_event_id)?.actor_id??g.events[g.events.length-1]?.actor_id??"SERVICE";userRows.push([dateVisible(g.session.business_date),g.session.shift,g.session.mnv,g.session.full_name,g.session.supplier,g.session.department,g.session.site,pos,c.resource_id,actor,`${g.session.session_id}:${c.resource_type}:${c.resource_id}`]);existing.add(key);}
  await appendRows(env,token,"THÔNG TIN USER CỦA NLĐ","A:K",userRows,"OVERWRITE");

  const history=await getGrid(env,token,"LỊCH SỬ NGHIỆP VỤ","A:M");assertHeader(history,HISTORY_HEADERS,"LỊCH SỬ NGHIỆP VỤ");const historyIds=new Set(history.slice(1).map(r=>text(r?.[10])).filter(Boolean)),employeeByMnv=new Map<string,string>();for(const g of bySession.values())employeeByMnv.set(g.session.mnv,g.session.full_name);const historyRows:unknown[][]=[];
  for(const e of [...events].sort((x,y)=>x.authority_seq-y.authority_seq)){if(historyIds.has(e.event_id))continue;const p=payload(e),session=bySession.get(e.entity_id),mnv=text(p.mnv)||session?.session.mnv||((e.entity_type==="STAFF")?e.entity_id:""),name=text(p.full_name)||employeeByMnv.get(mnv)||"",shift=text(p.shift)||session?.session.shift||"",sessionId=session?.session.session_id||text(p.session_id)||((e.entity_type==="ATTENDANCE_SESSION")?e.entity_id:"");historyRows.push([eventDate(e),sessionId,mnv,name,shift,e.event_type,eventLabel(e.event_type),timeVisible(e.occurred_at),e.actor_id,eventDetail(e),e.event_id,`${e.origin} • ${e.actor_role}`,e.authority_seq]);historyIds.add(e.event_id);}
  await appendRows(env,token,"LỊCH SỬ NGHIỆP VỤ","A:M",historyRows);
  return{ra_updates:updates.length,user_rows:userRows.length,history_rows:historyRows.length,catalog_changed:catalog.changed};
}

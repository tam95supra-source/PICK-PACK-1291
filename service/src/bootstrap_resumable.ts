import { isAvailableLabel, nowIso, parseVisibleDate, sha256Hex, visibleToIsoTimestamp, workChoice, fold } from "./util";

const EXPECTED: Array<{name:string;headers:string[]}> = [
  {name:"Danh mục",headers:["DANH SÁCH NHÂN SỰ_Vị trí chính","DANH SÁCH NHÂN SỰ_Nhà cung cấp","DANH SÁCH NHÂN SỰ_Bộ phận","DANH SÁCH NHÂN SỰ_Site","DANH SÁCH NHÂN SỰ_Kho","DANH SÁCH PDA_Tình trạng","DANH SÁCH USER PICK_Tình trạng","DANH SÁCH BÀN PACK_Tình trạng","DANH SÁCH USER PACK_Tình trạng","RA - VÀO TRONG CA_Loại thao tác","VÀO - RA TRONG CA_Ca","CÔNG NHẬT_Thông tin công nhật","CÔNG NHẬT_Mốc thời gian","CÔNG NHẬT_Trạng thái"]},
  {name:"LỊCH SỬ NGHIỆP VỤ",headers:["Ngày","Session ID","Mã nhân viên","Họ tên","Ca","Loại sự kiện","Nhãn sự kiện","Thời gian","Người xử lý","Chi tiết","Event ID","Phạm vi","App Revision"]},
  {name:"DANH SÁCH PDA",headers:["Seri PDA","5 số cuối Seri","Tình trạng","Ghi chú"]},
  {name:"DANH SÁCH USER PICK",headers:["Số User","User Pick","Tình trạng","Ghi chú"]},
  {name:"DANH SÁCH BÀN PACK",headers:["Tên bàn pack","Tình trạng"]},
  {name:"DANH SÁCH USER PACK",headers:["Tên bàn pack","User pack","User Pack","Tình trạng"]},
  {name:"DANH SÁCH NHÂN SỰ",headers:["Mã nhân viên","Họ và tên","Số điện thoại","Vị trí chính","Nhà cung cấp","Bộ phận","Site","Kho","Ngày bắt đầu làm việc","Ghi chú","Người cập nhật","Thời gian cập nhật"]},
  {name:"RA - VÀO TRONG CA",headers:["Ngày","Ca","Mã nhân viên","Họ và tên","Số điện thoại","Nhà cung cấp","Bộ phận","Site","Kho","Vị trí chính","Vị trí trong ca","Seri PDA","User Pick","Bàn Pack","User Pack","Loại thao tác","Ghi chú","Người cập nhật","Thời gian cập nhật","Event ID","App action","App revision"]},
  {name:"CÔNG NHẬT",headers:["Ngày","Ca","Mã nhân viên","Họ và tên","Số điện thoại","Nhà cung cấp","Bộ phận","Site","Kho","Vị trí chính","Vị trí trong ca","Thông tin công nhật","Thời gian bắt đầu","Thời gian kết thúc","Mốc thời gian","Trạng thái","Ghi chú","Người cập nhật","Thời gian cập nhật","Event ID","Finish Event ID","App revision","Khấu trừ nhân sự"]},
  {name:"Danh sách Admin",headers:["Số User","Password verifier","Tình trạng","Ghi chú","Vị trí","Mail","Logic quyền cơ bản","","Trạng thái tài khoản","Người cập nhật","Thời gian cập nhật"]},
];

const FETCH_ROWS = 200;
const ATTENDANCE_ROWS = 120;
const LABOR_ROWS = 160;
const LEASE_ROWS = 160;

type Phase = "FETCH"|"CATALOG"|"STAFF"|"RESOURCES"|"ACCOUNTS"|"DATES"|"ATTENDANCE"|"LEASES"|"LABOR"|"FINALIZE"|"COMPLETE";
type SheetReport = {name:string;row_count:number;checksum:string};
type State = {
  schema_version:2;
  mode:"RESUMABLE";
  phase:Phase;
  sheet_index:number;
  next_row:number;
  current_sheet_rows:number;
  current_sheet_checksum:string;
  sheet_report:SheetReport[];
  business_dates:string[];
  cursor:number;
};
type StoredRow = {row_index:number;row_checksum:string;row_json:string};
type Table = {headers:string[];rows:string[][];objects:Array<Record<string,string>>;rowChecksums:string[];rowIndexes:number[]};

async function googleToken(env:Env):Promise<string>{
  const body=new URLSearchParams({client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET,refresh_token:env.GOOGLE_OAUTH_REFRESH_TOKEN,grant_type:"refresh_token"});
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});
  const j=await r.json<{access_token?:string;error?:string}>();
  if(!r.ok||!j.access_token)throw new Error(`GOOGLE_OAUTH:${j.error??r.status}`);
  return j.access_token;
}
function auth(t:string):HeadersInit{return{authorization:`Bearer ${t}`};}
function q(name:string):string{return `'${name.replace(/'/g,"''")}'`;}
function obj(headers:string[],row:string[]):Record<string,string>{const out:Record<string,string>={};headers.forEach((h,i)=>{if(h)out[h]=String(row[i]??"").trim();});return out;}
function normRow(row:unknown[],n:number):string[]{return Array.from({length:n},(_,i)=>String(row[i]??"").trim());}
function activeStatus(v:string):string{return isAvailableLabel(v)||["ACTIVE","HOAT DONG","DANG HOAT DONG"].includes(fold(v))?"ACTIVE":"DISABLED";}
function role(v:string):"SUPERADMIN"|"ADMIN"|"USER"{const f=fold(v);return f==="SUPERADMIN"?"SUPERADMIN":f==="ADMIN"?"ADMIN":"USER";}
async function runChunks(db:D1Database,stmts:D1PreparedStatement[],size=50):Promise<void>{for(let i=0;i<stmts.length;i+=size)await db.batch(stmts.slice(i,i+size));}
function initialState():State{return{schema_version:2,mode:"RESUMABLE",phase:"FETCH",sheet_index:0,next_row:1,current_sheet_rows:0,current_sheet_checksum:"",sheet_report:[],business_dates:[],cursor:0};}
function parseState(raw:string):State{const s=JSON.parse(raw) as State;if(s?.schema_version!==2||s.mode!=="RESUMABLE")throw new Error("BOOTSTRAP_STATE_VERSION_INVALID");return s;}
async function saveState(db:D1Database,runId:string,state:State):Promise<void>{await db.prepare("UPDATE bootstrap_runs SET manifest_json=?1 WHERE run_id=?2 AND status='RUNNING'").bind(JSON.stringify(state),runId).run();}
async function ensureShadow(db:D1Database):Promise<void>{const a=await db.prepare("SELECT scope FROM authority_state WHERE singleton_id=1").first<{scope:string}>();if(a?.scope!=="STAGING_SHADOW")throw new Error("BOOTSTRAP_ONLY_ALLOWED_IN_STAGING_SHADOW");}

async function validateWorkbook(env:Env):Promise<void>{
  const t=await googleToken(env),id=env.GOOGLE_SOURCE_SHEET_ID;
  const r=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}?fields=properties.title,sheets.properties.title`,{headers:auth(t)});
  if(!r.ok)throw new Error(`GOOGLE_SOURCE_META:${r.status}`);
  const meta=await r.json<{properties?:{title?:string};sheets?:Array<{properties?:{title?:string}}>}>();
  const title=String(meta.properties?.title??"");if(title!=="DỮ LIỆU THEO NGÀY")throw new Error(`SOURCE_TITLE_MISMATCH:${title}`);
  const actual=(meta.sheets??[]).map(x=>x.properties?.title??"").filter(Boolean),expected=EXPECTED.map(x=>x.name);
  if(JSON.stringify(actual)!==JSON.stringify(expected))throw new Error(`SOURCE_TABS_MISMATCH:${JSON.stringify(actual)}`);
}

async function fetchSheetChunk(db:D1Database,env:Env,runId:string,state:State):Promise<State>{
  const spec=EXPECTED[state.sheet_index];if(!spec){state.phase="CATALOG";state.cursor=0;return state;}
  const start=state.next_row,end=start+FETCH_ROWS-1,t=await googleToken(env),id=env.GOOGLE_SOURCE_SHEET_ID;
  const range=encodeURIComponent(`${q(spec.name)}!A${start}:AZ${end}`);
  const r=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}/values/${range}?majorDimension=ROWS&valueRenderOption=FORMATTED_VALUE`,{headers:auth(t)});
  if(!r.ok)throw new Error(`GOOGLE_SOURCE_VALUES:${spec.name}:${r.status}`);
  const payload=await r.json<{values?:unknown[][]}>(),raw=payload.values??[];
  let dataStart=0;
  if(start===1){
    const header=normRow(raw[0]??[],spec.headers.length);
    if(JSON.stringify(header)!==JSON.stringify(spec.headers))throw new Error(`SOURCE_HEADERS_MISMATCH:${spec.name}:${JSON.stringify(header)}`);
    dataStart=1;
  }
  const stmts:D1PreparedStatement[]=[],checks:string[]=[];let added=0;const dates=new Set(state.business_dates);
  for(let i=dataStart;i<raw.length;i++){
    const row=normRow(raw[i]??[],spec.headers.length);if(!row.some(Boolean))continue;
    const rowIndex=start+i,checksum=await sha256Hex(JSON.stringify(row));checks.push(checksum);added++;
    stmts.push(db.prepare("INSERT OR REPLACE INTO source_rows(sheet_name,row_index,row_checksum,row_json,import_run_id) VALUES(?1,?2,?3,?4,?5)").bind(spec.name,rowIndex,checksum,JSON.stringify(row),runId));
    if(spec.name==="RA - VÀO TRONG CA"||spec.name==="CÔNG NHẬT"){const d=parseVisibleDate(row[0]??"");if(d)dates.add(d);}
  }
  await runChunks(db,stmts);
  state.current_sheet_rows+=added;
  if(checks.length)state.current_sheet_checksum=await sha256Hex([state.current_sheet_checksum,...checks].filter(Boolean).join("\n"));
  state.business_dates=[...dates].sort();
  const done=raw.length<FETCH_ROWS;
  if(done){
    state.sheet_report.push({name:spec.name,row_count:state.current_sheet_rows,checksum:state.current_sheet_checksum||await sha256Hex("")});
    state.sheet_index++;state.next_row=1;state.current_sheet_rows=0;state.current_sheet_checksum="";
    if(state.sheet_index>=EXPECTED.length){state.phase="CATALOG";state.cursor=0;}
  }else state.next_row=start+FETCH_ROWS;
  return state;
}

async function loadTable(db:D1Database,name:string):Promise<Table>{
  const spec=EXPECTED.find(x=>x.name===name);if(!spec)throw new Error(`BOOTSTRAP_SHEET_UNKNOWN:${name}`);
  const got=await db.prepare("SELECT row_index,row_checksum,row_json FROM source_rows WHERE sheet_name=?1 ORDER BY row_index").bind(name).all<StoredRow>();
  const stored=got.results??[],rows=stored.map(x=>normRow(JSON.parse(x.row_json) as unknown[],spec.headers.length));
  return{headers:spec.headers,rows,objects:rows.map(r=>obj(spec.headers,r)),rowChecksums:stored.map(x=>x.row_checksum),rowIndexes:stored.map(x=>x.row_index)};
}

async function projectCatalog(db:D1Database):Promise<void>{
  const t=await loadTable(db,"Danh mục"),stmts:D1PreparedStatement[]=[db.prepare("DELETE FROM catalog_values")];
  t.headers.forEach((h,c)=>{const seen=new Set<string>();for(let r=0;r<t.rows.length;r++){const v=t.rows[r]?.[c]??"";if(!v||seen.has(v))continue;seen.add(v);stmts.push(db.prepare("INSERT INTO catalog_values(namespace,ordinal,value,source_checksum) VALUES(?1,?2,?3,?4)").bind(h,seen.size,v,t.rowChecksums[r]!));}});
  await runChunks(db,stmts);
}
async function projectStaff(db:D1Database):Promise<void>{
  const t=await loadTable(db,"DANH SÁCH NHÂN SỰ"),stmts:D1PreparedStatement[]=[db.prepare("DELETE FROM employees")];
  t.objects.forEach((r,i)=>{const mnv=r["Mã nhân viên"]||"";if(!mnv)return;stmts.push(db.prepare("INSERT INTO employees(mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12)").bind(mnv,r["Họ và tên"]||"",r["Số điện thoại"]||"",r["Vị trí chính"]||"",r["Nhà cung cấp"]||"",r["Bộ phận"]||"",r["Site"]||"",r["Kho"]||"",r["Ngày bắt đầu làm việc"]||"",r["Ghi chú"]||"",t.rowIndexes[i]!,t.rowChecksums[i]!));});
  await runChunks(db,stmts);
}
async function projectResources(db:D1Database):Promise<void>{
  const stmts:D1PreparedStatement[]=[db.prepare("DELETE FROM resources"),db.prepare("DELETE FROM resource_pack_map")];
  const add=async(sheet:string,type:string,idField:string)=>{const t=await loadTable(db,sheet);t.objects.forEach((r,i)=>{const id=r[idField]||"";if(!id)return;stmts.push(db.prepare("INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(type,id,r["Tình trạng"]||"",isAvailableLabel(r["Tình trạng"])?1:0,JSON.stringify(r),t.rowIndexes[i]!,t.rowChecksums[i]!));});return t;};
  await add("DANH SÁCH PDA","PDA","Seri PDA");await add("DANH SÁCH USER PICK","USER_PICK","User Pick");await add("DANH SÁCH BÀN PACK","PACK_TABLE","Tên bàn pack");const packs=await add("DANH SÁCH USER PACK","USER_PACK","User Pack");
  packs.objects.forEach((r,i)=>{const table=r["Tên bàn pack"]||"",user=r["User Pack"]||"",label=r["User pack"]||"";if(!table||!user)return;const f=fold(label),shift=f.startsWith("CA 1-")?"Ca 1":f.startsWith("CA 2-")?"Ca 2":f.startsWith("HP-")||fold(table)==="HP"?"Ca HC":"";if(!shift)return;stmts.push(db.prepare("INSERT OR REPLACE INTO resource_pack_map(pack_table,shift,user_pack,label,available,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(table,shift,user,label,isAvailableLabel(r["Tình trạng"])?1:0,packs.rowIndexes[i]!,packs.rowChecksums[i]!));});
  await runChunks(db,stmts);
}
async function projectAccounts(db:D1Database):Promise<void>{
  const t=await loadTable(db,"Danh sách Admin"),stmts:D1PreparedStatement[]=[db.prepare("DELETE FROM auth_sessions"),db.prepare("DELETE FROM auth_challenges"),db.prepare("DELETE FROM accounts WHERE is_shadow_test=0")];
  for(let i=0;i<t.objects.length;i++){const r=t.objects[i]!,login=r["Số User"]||"",verifier=r["Password verifier"]||"";if(!login||!verifier)continue;const rr=role(r["Vị trí"]||"");stmts.push(db.prepare("INSERT INTO accounts(login_id,verifier,verifier_hash,role,display_name,position,email,status,source_row,source_checksum,is_shadow_test) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,0)").bind(login,verifier,await sha256Hex(verifier),rr,login,rr.toLowerCase(),r["Mail"]||"",activeStatus(r["Trạng thái tài khoản"]||r["Tình trạng"]||""),t.rowIndexes[i]!,t.rowChecksums[i]!));}
  await runChunks(db,stmts);
}
async function projectDates(db:D1Database,state:State):Promise<void>{
  const sorted=[...new Set(state.business_dates)].sort(),stmts:D1PreparedStatement[]=[db.prepare("DELETE FROM business_dates")];
  sorted.forEach((d,i)=>stmts.push(db.prepare("INSERT INTO business_dates(business_date,sequence_no,source) VALUES(?1,?2,'GOOGLE_BOOTSTRAP')").bind(d,i+1)));
  await runChunks(db,stmts);
}

async function projectAttendanceStep(db:D1Database,state:State):Promise<{state:State;done:boolean}>{
  if(state.cursor===0)await db.batch([db.prepare("DELETE FROM resource_leases"),db.prepare("DELETE FROM resource_daily_consumption"),db.prepare("DELETE FROM attendance_sessions")]);
  const got=await db.prepare("SELECT row_index,row_json FROM source_rows WHERE sheet_name='RA - VÀO TRONG CA' AND row_index>?1 ORDER BY row_index LIMIT ?2").bind(state.cursor,ATTENDANCE_ROWS).all<{row_index:number;row_json:string}>(),rows=got.results??[];
  const spec=EXPECTED.find(x=>x.name==="RA - VÀO TRONG CA")!,groups=new Map<string,Array<{row_index:number;o:Record<string,string>}>>();
  for(const x of rows){const r=normRow(JSON.parse(x.row_json) as unknown[],spec.headers.length),o=obj(spec.headers,r),d=parseVisibleDate(o["Ngày"]||""),m=o["Mã nhân viên"]||"";if(!d||!m)continue;const sid=`BOOTSTRAP:${d}:${m}`,g=groups.get(sid)??[];g.push({row_index:x.row_index,o});groups.set(sid,g);}
  const stmts:D1PreparedStatement[]=[];
  for(const [sid,g] of groups){
    const first=g[0]!,last=g[g.length-1]!,o=last.o,d=parseVisibleDate(o["Ngày"]||""),m=o["Mã nhân viên"]||"",action=fold(o["Loại thao tác"]||o["App action"]||""),ended=action.includes("RA")&&!action.includes("VAO"),pda=o["Seri PDA"]||"",pick=o["User Pick"]||"",table=o["Bàn Pack"]||"",pack=o["User Pack"]||"",updated=visibleToIsoTimestamp(o["Thời gian cập nhật"]||"");
    stmts.push(db.prepare(`INSERT INTO attendance_sessions(session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,exit_at,entered_by,exited_by,version,source_last_row,updated_at)
      VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,'GOOGLE_BOOTSTRAP',?13,?14,?15,?16)
      ON CONFLICT(session_id) DO UPDATE SET shift=excluded.shift,work_choice=excluded.work_choice,state=excluded.state,pda_serial=excluded.pda_serial,user_pick=excluded.user_pick,pack_table=excluded.pack_table,user_pack=excluded.user_pack,enter_at=COALESCE(attendance_sessions.enter_at,excluded.enter_at),exit_at=excluded.exit_at,exited_by=excluded.exited_by,version=attendance_sessions.version+excluded.version,source_last_row=excluded.source_last_row,updated_at=excluded.updated_at
      WHERE excluded.source_last_row>attendance_sessions.source_last_row`).bind(sid,m,d,o["Ca"]||"",workChoice(o["Vị trí trong ca"]),ended?"ENDED":"ACTIVE",pda||null,pick||null,table||null,pack||null,visibleToIsoTimestamp(first.o["Thời gian cập nhật"]||""),ended?updated:null,ended?"GOOGLE_BOOTSTRAP":null,g.length,last.row_index,updated));
  }
  await runChunks(db,stmts);
  if(rows.length)state.cursor=rows[rows.length-1]!.row_index;
  return{state,done:rows.length<ATTENDANCE_ROWS};
}
async function projectLeasesStep(db:D1Database,state:State):Promise<{state:State;done:boolean}>{
  const got=await db.prepare("SELECT session_id,mnv,business_date,pda_serial,user_pick,pack_table,user_pack FROM attendance_sessions WHERE state='ACTIVE' ORDER BY session_id LIMIT ?1 OFFSET ?2").bind(LEASE_ROWS,state.cursor).all<{session_id:string;mnv:string;business_date:string;pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null}>(),rows=got.results??[],stmts:D1PreparedStatement[]=[];
  for(const x of rows){for(const [type,id] of [["PDA",x.pda_serial],["USER_PICK",x.user_pick],["PACK_TABLE",x.pack_table],["USER_PACK",x.user_pack]] as Array<[string,string|null]>){if(!id)continue;stmts.push(db.prepare("INSERT OR IGNORE INTO resource_leases(resource_type,resource_id,session_id,mnv,business_date,acquired_event_id,acquired_at) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(type,id,x.session_id,x.mnv,x.business_date,`BOOTSTRAP:${x.business_date}:${x.mnv}:${type}`,nowIso()));}}
  await runChunks(db,stmts);state.cursor+=rows.length;return{state,done:rows.length<LEASE_ROWS};
}
async function projectLaborStep(db:D1Database,state:State):Promise<{state:State;done:boolean}>{
  if(state.cursor===0)await db.prepare("DELETE FROM labor_sessions").run();
  const got=await db.prepare("SELECT row_index,row_json FROM source_rows WHERE sheet_name='CÔNG NHẬT' AND row_index>?1 ORDER BY row_index LIMIT ?2").bind(state.cursor,LABOR_ROWS).all<{row_index:number;row_json:string}>(),rows=got.results??[],spec=EXPECTED.find(x=>x.name==="CÔNG NHẬT")!,stmts:D1PreparedStatement[]=[];
  for(const x of rows){const r=obj(spec.headers,normRow(JSON.parse(x.row_json) as unknown[],spec.headers.length)),d=parseVisibleDate(r["Ngày"]||""),m=r["Mã nhân viên"]||"";if(!d||!m)continue;const startId=r["Event ID"]||`BOOTSTRAP-LABOR:${d}:${m}:${x.row_index}`,finishId=r["Finish Event ID"]||null,status=fold(r["Trạng thái"]||""),stateLabel=(status.includes("HOAN")||status.includes("COMPLET")||Boolean(finishId))?"COMPLETED":"OPEN";stmts.push(db.prepare("INSERT OR REPLACE INTO labor_sessions(labor_id,mnv,business_date,shift,labor_type,time_marker,state,start_at,end_at,note,deduct_staff,start_event_id,finish_event_id,version,source_row,updated_at) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16)").bind(startId,m,d,r["Ca"]||"",r["Thông tin công nhật"]||"",r["Mốc thời gian"]||"",stateLabel,visibleToIsoTimestamp(r["Thời gian bắt đầu"]||r["Thời gian cập nhật"]||""),stateLabel==="COMPLETED"?visibleToIsoTimestamp(r["Thời gian kết thúc"]||r["Thời gian cập nhật"]||""):null,r["Ghi chú"]||"",fold(r["Khấu trừ nhân sự"]||"")==="CO"?1:0,startId,finishId,stateLabel==="COMPLETED"?2:1,x.row_index,visibleToIsoTimestamp(r["Thời gian cập nhật"]||"")));}
  await runChunks(db,stmts);if(rows.length)state.cursor=rows[rows.length-1]!.row_index;return{state,done:rows.length<LABOR_ROWS};
}

async function finalize(db:D1Database,env:Env,runId:string,state:State):Promise<Record<string,unknown>>{
  const counts:Record<string,number>={};for(const table of ["employees","catalog_values","resources","resource_pack_map","accounts","business_dates","attendance_sessions","labor_sessions"]){const c=await db.prepare(`SELECT COUNT(*) n FROM ${table}`).first<{n:number}>();counts[table]=c?.n??0;}
  const dates=[...new Set(state.business_dates)].sort(),completed=nowIso(),report={run_id:runId,source_title:"DỮ LIỆU THEO NGÀY",source_sheet_id:env.GOOGLE_SOURCE_SHEET_ID,sheets:state.sheet_report,projection_counts:counts,business_date_min:dates[0]??null,business_date_max:dates[dates.length-1]??null,business_date_count:dates.length,completed_at:completed,resumable:true};
  state.phase="COMPLETE";await db.prepare("UPDATE bootstrap_runs SET completed_at=?1,status='COMPLETE',manifest_json=?2,report_json=?3 WHERE run_id=?4").bind(completed,JSON.stringify(state),JSON.stringify(report),runId).run();return{ok:true,done:true,...report};
}

export async function bootstrapGoogleStart(db:D1Database,env:Env):Promise<Record<string,unknown>>{
  await ensureShadow(db);await validateWorkbook(env);const at=nowIso(),runId=crypto.randomUUID(),state=initialState();
  await db.batch([
    db.prepare("UPDATE bootstrap_runs SET completed_at=?1,status='FAILED',report_json=?2 WHERE status='RUNNING'").bind(at,JSON.stringify({error:"SUPERSEDED_BY_RESUMABLE_BOOTSTRAP",at})),
    db.prepare("DELETE FROM source_rows"),
    db.prepare("INSERT INTO bootstrap_runs(run_id,source_title,source_sheet_identity,started_at,status,manifest_json) VALUES(?1,'DỮ LIỆU THEO NGÀY',?2,?3,'RUNNING',?4)").bind(runId,env.GOOGLE_SOURCE_SHEET_ID,at,JSON.stringify(state)),
  ]);
  return{ok:true,done:false,run_id:runId,phase:state.phase,state};
}
export async function bootstrapGoogleStatus(db:D1Database,runId?:string):Promise<Record<string,unknown>>{
  const row=runId?await db.prepare("SELECT run_id,status,manifest_json,report_json,started_at,completed_at FROM bootstrap_runs WHERE run_id=?1").bind(runId).first<{run_id:string;status:string;manifest_json:string;report_json:string|null;started_at:string;completed_at:string|null}>():await db.prepare("SELECT run_id,status,manifest_json,report_json,started_at,completed_at FROM bootstrap_runs ORDER BY started_at DESC LIMIT 1").first<{run_id:string;status:string;manifest_json:string;report_json:string|null;started_at:string;completed_at:string|null}>();
  if(!row)throw new Error("BOOTSTRAP_RUN_NOT_FOUND");const state=parseState(row.manifest_json);return{ok:true,done:row.status==="COMPLETE",run_id:row.run_id,status:row.status,phase:state.phase,state,report:row.report_json?JSON.parse(row.report_json):null,started_at:row.started_at,completed_at:row.completed_at};
}
export async function bootstrapGoogleStep(db:D1Database,env:Env,runId:string):Promise<Record<string,unknown>>{
  await ensureShadow(db);const row=await db.prepare("SELECT status,manifest_json,report_json FROM bootstrap_runs WHERE run_id=?1").bind(runId).first<{status:string;manifest_json:string;report_json:string|null}>();if(!row)throw new Error("BOOTSTRAP_RUN_NOT_FOUND");
  if(row.status==="COMPLETE")return{ok:true,done:true,run_id:runId,report:row.report_json?JSON.parse(row.report_json):null};if(row.status!=="RUNNING")throw new Error(`BOOTSTRAP_RUN_NOT_RUNNING:${row.status}`);
  let state=parseState(row.manifest_json);
  try{
    if(state.phase==="FETCH")state=await fetchSheetChunk(db,env,runId,state);
    else if(state.phase==="CATALOG"){await projectCatalog(db);state.phase="STAFF";state.cursor=0;}
    else if(state.phase==="STAFF"){await projectStaff(db);state.phase="RESOURCES";state.cursor=0;}
    else if(state.phase==="RESOURCES"){await projectResources(db);state.phase="ACCOUNTS";state.cursor=0;}
    else if(state.phase==="ACCOUNTS"){await projectAccounts(db);state.phase="DATES";state.cursor=0;}
    else if(state.phase==="DATES"){await projectDates(db,state);state.phase="ATTENDANCE";state.cursor=0;}
    else if(state.phase==="ATTENDANCE"){const x=await projectAttendanceStep(db,state);state=x.state;if(x.done){state.phase="LEASES";state.cursor=0;}}
    else if(state.phase==="LEASES"){const x=await projectLeasesStep(db,state);state=x.state;if(x.done){state.phase="LABOR";state.cursor=0;}}
    else if(state.phase==="LABOR"){const x=await projectLaborStep(db,state);state=x.state;if(x.done){state.phase="FINALIZE";state.cursor=0;}}
    else if(state.phase==="FINALIZE")return await finalize(db,env,runId,state);
    else if(state.phase==="COMPLETE")return bootstrapGoogleStatus(db,runId);
    await saveState(db,runId,state);return{ok:true,done:false,run_id:runId,phase:state.phase,state};
  }catch(e){await db.prepare("UPDATE bootstrap_runs SET report_json=?1 WHERE run_id=?2 AND status='RUNNING'").bind(JSON.stringify({last_error:String(e),at:nowIso(),phase:state.phase}),runId).run().catch(()=>undefined);throw e;}
}

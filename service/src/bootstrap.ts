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

type Table = { headers:string[]; rows:string[][]; objects:Array<Record<string,string>>; rowChecksums:string[] };

async function token(env:Env):Promise<string>{
  const body=new URLSearchParams({client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET,refresh_token:env.GOOGLE_OAUTH_REFRESH_TOKEN,grant_type:"refresh_token"});
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});const j=await r.json<{access_token?:string;error?:string}>();if(!r.ok||!j.access_token)throw new Error(`GOOGLE_OAUTH:${j.error??r.status}`);return j.access_token;
}
function auth(t:string):HeadersInit{return{authorization:`Bearer ${t}`};}
function q(name:string):string{return `'${name.replace(/'/g,"''")}'`}
function obj(headers:string[],row:string[]):Record<string,string>{const o:Record<string,string>={};headers.forEach((h,i)=>{if(h)o[h]=String(row[i]??"").trim();});return o;}
function normRow(row:unknown[],n:number):string[]{return Array.from({length:n},(_,i)=>String(row[i]??"").trim());}
function activeStatus(v:string):string{return isAvailableLabel(v)||["ACTIVE","HOAT DONG","DANG HOAT DONG"].includes(fold(v))?"ACTIVE":"DISABLED";}
function role(v:string):"SUPERADMIN"|"ADMIN"|"USER"{const f=fold(v);return f==="SUPERADMIN"?"SUPERADMIN":f==="ADMIN"?"ADMIN":"USER";}
async function runChunks(db:D1Database,stmts:D1PreparedStatement[],size=50):Promise<void>{for(let i=0;i<stmts.length;i+=size)await db.batch(stmts.slice(i,i+size));}

async function fetchWorkbook(env:Env):Promise<{title:string;tables:Map<string,Table>;sheetReport:Array<{name:string;row_count:number;checksum:string}>}>{
  const t=await token(env),id=env.GOOGLE_SOURCE_SHEET_ID;
  const metaR=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}?fields=properties.title,sheets.properties.title`,{headers:auth(t)});if(!metaR.ok)throw new Error(`GOOGLE_SOURCE_META:${metaR.status}`);
  const meta=await metaR.json<{properties?:{title?:string};sheets?:Array<{properties?:{title?:string}}>}>();
  const title=String(meta.properties?.title??"");if(title!=="DỮ LIỆU THEO NGÀY")throw new Error(`SOURCE_TITLE_MISMATCH:${title}`);
  const actual=(meta.sheets??[]).map(x=>x.properties?.title??"").filter(Boolean);const expected=EXPECTED.map(x=>x.name);if(JSON.stringify(actual)!==JSON.stringify(expected))throw new Error(`SOURCE_TABS_MISMATCH:${JSON.stringify(actual)}`);
  const params=EXPECTED.map(x=>`ranges=${encodeURIComponent(`${q(x.name)}!A:AZ`)}`).join("&");
  const valuesR=await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(id)}/values:batchGet?majorDimension=ROWS&valueRenderOption=FORMATTED_VALUE&${params}`,{headers:auth(t)});if(!valuesR.ok)throw new Error(`GOOGLE_SOURCE_VALUES:${valuesR.status}`);
  const values=await valuesR.json<{valueRanges?:Array<{values?:unknown[][]}>}>();const tables=new Map<string,Table>(),sheetReport:Array<{name:string;row_count:number;checksum:string}>=[];
  for(let i=0;i<EXPECTED.length;i++){
    const spec=EXPECTED[i]!;const raw=values.valueRanges?.[i]?.values??[];const header=normRow(raw[0]??[],spec.headers.length);
    if(JSON.stringify(header)!==JSON.stringify(spec.headers))throw new Error(`SOURCE_HEADERS_MISMATCH:${spec.name}:${JSON.stringify(header)}`);
    const rows=(raw.slice(1)).map(r=>normRow(r,spec.headers.length)).filter(r=>r.some(Boolean));const checks:string[]=[];for(const r of rows)checks.push(await sha256Hex(JSON.stringify(r)));
    const checksum=await sha256Hex(checks.join("\n"));tables.set(spec.name,{headers:header,rows,objects:rows.map(r=>obj(header,r)),rowChecksums:checks});sheetReport.push({name:spec.name,row_count:rows.length,checksum});
  }
  return{title,tables,sheetReport};
}

export async function bootstrapFromGoogle(db:D1Database,env:Env):Promise<Record<string,unknown>>{
  const a=await db.prepare("SELECT scope,mode FROM authority_state WHERE singleton_id=1").first<{scope:string;mode:string}>();
  if(a?.scope!=="STAGING_SHADOW")throw new Error("BOOTSTRAP_ONLY_ALLOWED_IN_STAGING_SHADOW");
  const started=nowIso(),runId=crypto.randomUUID();
  await db.prepare("INSERT INTO bootstrap_runs(run_id,source_title,source_sheet_identity,started_at,status,manifest_json) VALUES(?1,'DỮ LIỆU THEO NGÀY',?2,?3,'RUNNING',?4)").bind(runId,env.GOOGLE_SOURCE_SHEET_ID,started,JSON.stringify({schema_version:1,tabs:EXPECTED.map(x=>x.name)})).run();
  try{
    const wb=await fetchWorkbook(env),tables=wb.tables;
    const sourceStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM source_rows")];
    for(const spec of EXPECTED){const table=tables.get(spec.name)!;table.rows.forEach((r,i)=>sourceStmts.push(db.prepare("INSERT INTO source_rows(sheet_name,row_index,row_checksum,row_json,import_run_id) VALUES(?1,?2,?3,?4,?5)").bind(spec.name,i+2,table.rowChecksums[i]!,JSON.stringify(r),runId)));}
    await runChunks(db,sourceStmts);

    const catalog=tables.get("Danh mục")!;const catStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM catalog_values")];
    catalog.headers.forEach((h,c)=>{const seen=new Set<string>();for(let r=0;r<catalog.rows.length;r++){const v=catalog.rows[r]?.[c]??"";if(!v||seen.has(v))continue;seen.add(v);catStmts.push(db.prepare("INSERT INTO catalog_values(namespace,ordinal,value,source_checksum) VALUES(?1,?2,?3,?4)").bind(h,seen.size,v,catalog.rowChecksums[r]!));}});await runChunks(db,catStmts);

    const staff=tables.get("DANH SÁCH NHÂN SỰ")!;const staffStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM employees")];
    staff.objects.forEach((r,i)=>{const mnv=r["Mã nhân viên"]||"";if(!mnv)return;staffStmts.push(db.prepare("INSERT INTO employees(mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12)").bind(mnv,r["Họ và tên"]||"",r["Số điện thoại"]||"",r["Vị trí chính"]||"",r["Nhà cung cấp"]||"",r["Bộ phận"]||"",r["Site"]||"",r["Kho"]||"",r["Ngày bắt đầu làm việc"]||"",r["Ghi chú"]||"",i+2,staff.rowChecksums[i]!));});await runChunks(db,staffStmts);

    const resStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM resources"),db.prepare("DELETE FROM resource_pack_map")];
    const addResource=(sheet:string,type:string,idField:string)=>{const t=tables.get(sheet)!;t.objects.forEach((r,i)=>{const id=r[idField]||"";if(!id)return;resStmts.push(db.prepare("INSERT INTO resources(resource_type,resource_id,status_label,available,metadata_json,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(type,id,r["Tình trạng"]||"",isAvailableLabel(r["Tình trạng"])?1:0,JSON.stringify(r),i+2,t.rowChecksums[i]!));});};
    addResource("DANH SÁCH PDA","PDA","Seri PDA");addResource("DANH SÁCH USER PICK","USER_PICK","User Pick");addResource("DANH SÁCH BÀN PACK","PACK_TABLE","Tên bàn pack");addResource("DANH SÁCH USER PACK","USER_PACK","User Pack");
    const packs=tables.get("DANH SÁCH USER PACK")!;packs.objects.forEach((r,i)=>{const table=r["Tên bàn pack"]||"",user=r["User Pack"]||"",label=r["User pack"]||"";if(!table||!user)return;const f=fold(label),shift=f.startsWith("CA 1-")?"Ca 1":f.startsWith("CA 2-")?"Ca 2":f.startsWith("HP-")||fold(table)==="HP"?"Ca HC":"";if(!shift)return;resStmts.push(db.prepare("INSERT OR REPLACE INTO resource_pack_map(pack_table,shift,user_pack,label,available,source_row,source_checksum) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(table,shift,user,label,isAvailableLabel(r["Tình trạng"])?1:0,i+2,packs.rowChecksums[i]!));});await runChunks(db,resStmts);

    const admins=tables.get("Danh sách Admin")!;const accountStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM auth_sessions"),db.prepare("DELETE FROM auth_challenges"),db.prepare("DELETE FROM accounts WHERE is_shadow_test=0")];
    for(let i=0;i<admins.objects.length;i++){const r=admins.objects[i]!,login=r["Số User"]||"",verifier=r["Password verifier"]||"";if(!login||!verifier)continue;const rr=role(r["Vị trí"]||"");accountStmts.push(db.prepare("INSERT INTO accounts(login_id,verifier,verifier_hash,role,display_name,position,email,status,source_row,source_checksum,is_shadow_test) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,0)").bind(login,verifier,await sha256Hex(verifier),rr,login,rr.toLowerCase(),r["Mail"]||"",activeStatus(r["Trạng thái tài khoản"]||r["Tình trạng"]||""),i+2,admins.rowChecksums[i]!));}await runChunks(db,accountStmts);

    const ra=tables.get("RA - VÀO TRONG CA")!, labor=tables.get("CÔNG NHẬT")!;const dates=new Set<string>();for(const r of [...ra.objects,...labor.objects]){const d=parseVisibleDate(r["Ngày"]||"");if(d)dates.add(d);}const sorted=[...dates].sort();const dateStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM business_dates")];sorted.forEach((d,i)=>dateStmts.push(db.prepare("INSERT INTO business_dates(business_date,sequence_no,source) VALUES(?1,?2,'GOOGLE_BOOTSTRAP')").bind(d,i+1)));await runChunks(db,dateStmts);

    const attendanceMap=new Map<string,{date:string;mnv:string;rows:Array<{o:Record<string,string>;idx:number}>}>();ra.objects.forEach((o,i)=>{const d=parseVisibleDate(o["Ngày"]||""),m=o["Mã nhân viên"]||"";if(!d||!m)return;const k=`${d}|${m}`,x=attendanceMap.get(k)??{date:d,mnv:m,rows:[]};x.rows.push({o,idx:i});attendanceMap.set(k,x);});
    const attStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM resource_leases"),db.prepare("DELETE FROM resource_daily_consumption"),db.prepare("DELETE FROM attendance_sessions")];
    for(const x of attendanceMap.values()){const last=x.rows[x.rows.length-1]!,first=x.rows[0]!,action=fold(last.o["Loại thao tác"]||last.o["App action"]||""),ended=action.includes("RA")&&!action.includes("VAO"),sid=`BOOTSTRAP:${x.date}:${x.mnv}`;const pda=last.o["Seri PDA"]||"",pick=last.o["User Pick"]||"",table=last.o["Bàn Pack"]||"",pack=last.o["User Pack"]||"";attStmts.push(db.prepare("INSERT INTO attendance_sessions(session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,exit_at,entered_by,exited_by,version,source_last_row,updated_at) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,'GOOGLE_BOOTSTRAP',?13,?14,?15,?16)").bind(sid,x.mnv,x.date,last.o["Ca"]||"",workChoice(last.o["Vị trí trong ca"]),ended?"ENDED":"ACTIVE",pda||null,pick||null,table||null,pack||null,visibleToIsoTimestamp(first.o["Thời gian cập nhật"]||""),ended?visibleToIsoTimestamp(last.o["Thời gian cập nhật"]||""):null,ended?"GOOGLE_BOOTSTRAP":null,x.rows.length,last.idx+2,visibleToIsoTimestamp(last.o["Thời gian cập nhật"]||"")));if(!ended){for(const [type,id] of [["PDA",pda],["USER_PICK",pick],["PACK_TABLE",table],["USER_PACK",pack]])if(id)attStmts.push(db.prepare("INSERT OR IGNORE INTO resource_leases(resource_type,resource_id,session_id,mnv,business_date,acquired_event_id,acquired_at) VALUES(?1,?2,?3,?4,?5,?6,?7)").bind(type,id,sid,x.mnv,x.date,`BOOTSTRAP:${x.date}:${x.mnv}:${type}`,nowIso()));}}
    await runChunks(db,attStmts);

    const laborStmts:D1PreparedStatement[]=[db.prepare("DELETE FROM labor_sessions")];for(let i=0;i<labor.objects.length;i++){const r=labor.objects[i]!,d=parseVisibleDate(r["Ngày"]||""),m=r["Mã nhân viên"]||"";if(!d||!m)continue;const startId=r["Event ID"]||`BOOTSTRAP-LABOR:${d}:${m}:${i+2}`,finishId=r["Finish Event ID"]||null,status=fold(r["Trạng thái"]||""),state=(status.includes("HOAN")||status.includes("COMPLET")||Boolean(finishId))?"COMPLETED":"OPEN";laborStmts.push(db.prepare("INSERT OR REPLACE INTO labor_sessions(labor_id,mnv,business_date,shift,labor_type,time_marker,state,start_at,end_at,note,deduct_staff,start_event_id,finish_event_id,version,source_row,updated_at) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16)").bind(startId,m,d,r["Ca"]||"",r["Thông tin công nhật"]||"",r["Mốc thời gian"]||"",state,visibleToIsoTimestamp(r["Thời gian bắt đầu"]||r["Thời gian cập nhật"]||""),state==="COMPLETED"?visibleToIsoTimestamp(r["Thời gian kết thúc"]||r["Thời gian cập nhật"]||""):null,r["Ghi chú"]||"",fold(r["Khấu trừ nhân sự"]||"")==="CO"?1:0,startId,finishId,state==="COMPLETED"?2:1,i+2,visibleToIsoTimestamp(r["Thời gian cập nhật"]||"")));}await runChunks(db,laborStmts);

    const counts:{[k:string]:number}={};for(const table of ["employees","catalog_values","resources","resource_pack_map","accounts","business_dates","attendance_sessions","labor_sessions"]){const c=await db.prepare(`SELECT COUNT(*) n FROM ${table}`).first<{n:number}>();counts[table]=c?.n??0;}
    const report={run_id:runId,source_title:wb.title,source_sheet_id:env.GOOGLE_SOURCE_SHEET_ID,sheets:wb.sheetReport,projection_counts:counts,business_date_min:sorted[0]??null,business_date_max:sorted[sorted.length-1]??null,business_date_count:sorted.length,completed_at:nowIso()};
    await db.prepare("UPDATE bootstrap_runs SET completed_at=?1,status='COMPLETE',report_json=?2 WHERE run_id=?3").bind(report.completed_at,JSON.stringify(report),runId).run();return{ok:true,...report};
  }catch(e){const at=nowIso();await db.prepare("UPDATE bootstrap_runs SET completed_at=?1,status='FAILED',report_json=?2 WHERE run_id=?3").bind(at,JSON.stringify({error:String(e)}),runId).run();throw e;}
}

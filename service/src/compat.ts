import { CoreError, currentAuthority } from "./core";
import { fold } from "./util";

interface Employee {
  mnv:string; full_name:string; phone:string; main_position:string; supplier:string; department:string; site:string; warehouse:string; start_date:string; note:string;
}
interface SessionRow {
  session_id:string; mnv:string; business_date:string; shift:string; work_choice:string; state:string; pda_serial:string|null; user_pick:string|null; pack_table:string|null; user_pack:string|null; enter_at:string|null; exit_at:string|null; entered_by:string|null; exited_by:string|null; version:number;
}
interface LaborRow { labor_id:string; mnv:string; business_date:string; shift:string; labor_type:string; time_marker:string; state:string; start_at:string|null; end_at:string|null; note:string; deduct_staff:number; start_event_id:string; finish_event_id:string|null; version:number; }
interface CompatEvent { event_id:string; mnv:string; full_name:string; shift:string; event_type:string; label:string; at:string; at_iso:string; actor:string; detail:string; authority_seq:number; }

const REPORT_ROWS=["Trưởng nhóm","Chuyên viên","Tổ trưởng","Điều phối khu pack","Điều phối khu chờ xuất","Kéo hàng","5S","Picker","Packer","Phúc Long"];
const SUPPLIER_ORDER=["IH","NLV","VW","MP","MGL","HGP","HAD"];

function supplierCode(v:string):string{
  const f=fold(v).replace(/[^A-Z0-9]+/g," ");
  for(const c of SUPPLIER_ORDER)if(new RegExp(`(^| )${c}( |$)`).test(f))return c;
  return SUPPLIER_ORDER.includes(f)?f:"";
}
function reportPosition(s:{work_choice:string;employee_snapshot:Employee}):string{
  const e=s.employee_snapshot,p=fold(e.main_position),d=fold(e.department),work=String(s.work_choice||"");
  if(p==="TRUONG NHOM")return"Trưởng nhóm";if(p==="CHUYEN VIEN")return"Chuyên viên";if(p==="TO TRUONG")return"Tổ trưởng";
  if(p.includes("DIEU PHOI")){if(p.includes("PACK")||d.includes("PICK PACK"))return"Điều phối khu pack";if(p.includes("CHO XUAT")||d.includes("GIAO VAN")||d.includes("OUTBOUND"))return"Điều phối khu chờ xuất";return"";}
  if(p==="KEO HANG")return"Kéo hàng";if(p==="5S")return"5S";if(p.includes("PHUC LONG"))return"Phúc Long";if(work==="PICK"||p==="PICK"||p==="PICKER")return"Picker";if(work==="PACK"||p==="PACK"||p==="PACKER")return"Packer";return"";
}
function deductAllowed(mainPosition:string,laborType:string):boolean{const a=fold(mainPosition),b=fold(laborType),fixed=(v:string)=>v.includes("KEO HANG")||v.includes("TO TRUONG");return!fixed(a)&&!fixed(b);}
function tenureDays(startDate:string,businessDate:string):number{
  if(!startDate)return 99999;let iso=startDate;const m=startDate.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);if(m&&m[1]&&m[2]&&m[3])iso=`${m[3]}-${m[2]}-${m[1]}`;
  const a=Date.parse(`${iso}T00:00:00+07:00`),b=Date.parse(`${businessDate}T00:00:00+07:00`);return Number.isFinite(a)&&Number.isFinite(b)?Math.max(0,Math.floor((b-a)/86400000)):99999;
}
function matrix(sessions:Array<{mnv:string;work_choice:string;employee_snapshot:Employee}>,columns:string[]){
  const data:Record<string,Record<string,number>>={};for(const r of REPORT_ROWS){data[r]={};for(const c of columns)data[r]![c]=0;}
  for(const s of sessions){const pos=reportPosition(s),sup=supplierCode(s.employee_snapshot.supplier);if(pos&&sup&&data[pos]&&columns.includes(sup))data[pos]![sup]=(data[pos]![sup]??0)+1;}
  const rows=REPORT_ROWS.map(position=>{const counts:Record<string,number>={};for(const c of columns)counts[c]=data[position]?.[c]??0;return{position,counts,total:columns.reduce((n,c)=>n+(counts[c]??0),0)};});
  const totals:Record<string,number>={};for(const c of columns)totals[c]=rows.reduce((n,r)=>n+(r.counts[c]??0),0);return{columns,rows,totals,total:columns.reduce((n,c)=>n+(totals[c]??0),0)};
}
function tenure(sessions:Array<{mnv:string;work_choice:string;employee_snapshot:Employee}>,columns:string[],work:string,deducted:Set<string>,date:string){
  const data:Record<string,Record<string,number>>={"Nhân sự mới":{},"Nhân sự cũ":{}};for(const label of Object.keys(data))for(const c of columns)data[label]![c]=0;
  for(const s of sessions){if(s.work_choice!==work||deducted.has(s.mnv))continue;const sup=supplierCode(s.employee_snapshot.supplier);if(!sup||!columns.includes(sup))continue;const label=tenureDays(s.employee_snapshot.start_date,date)<=30?"Nhân sự mới":"Nhân sự cũ";data[label]![sup]=(data[label]![sup]??0)+1;}
  const rows=["Nhân sự mới","Nhân sự cũ"].map(label=>{const counts:Record<string,number>={};for(const c of columns)counts[c]=data[label]?.[c]??0;return{label,counts,total:columns.reduce((n,c)=>n+(counts[c]??0),0)};});const totals:Record<string,number>={};for(const c of columns)totals[c]=rows.reduce((n,r)=>n+(r.counts[c]??0),0);return{columns,rows,totals,total:rows.reduce((n,r)=>n+r.total,0)};
}
function support(sessions:Array<{mnv:string;shift:string;employee_snapshot:Employee}>,labor:LaborRow[],allowed:string[],columns:string[]){
  const byMnv=new Map(sessions.map(s=>[s.mnv,s])),deducted=new Set<string>(),rowsByType:Record<string,{label:string;counts:Record<string,number>;total:number}>={},seen=new Set<string>();
  for(const r of labor){if(!allowed.includes(r.shift)||!r.deduct_staff)continue;const s=byMnv.get(r.mnv);if(!s)continue;const type=r.labor_type||"Khác";if(!deductAllowed(s.employee_snapshot.main_position,type))continue;const k=`${type}|${r.mnv}`;if(seen.has(k))continue;seen.add(k);deducted.add(r.mnv);const sup=supplierCode(s.employee_snapshot.supplier);if(!sup||!columns.includes(sup))continue;if(!rowsByType[type]){const counts:Record<string,number>={};for(const c of columns)counts[c]=0;rowsByType[type]={label:type,counts,total:0};}rowsByType[type]!.counts[sup]=(rowsByType[type]!.counts[sup]??0)+1;rowsByType[type]!.total++;}
  const rows=Object.keys(rowsByType).sort().map(k=>rowsByType[k]!);const totals:Record<string,number>={};for(const c of columns)totals[c]=rows.reduce((n,r)=>n+(r.counts[c]??0),0);return{deducted,matrix:{columns,rows,totals,total:rows.reduce((n,r)=>n+r.total,0),unique_staff:deducted.size}};
}
function period(sessions:Array<{mnv:string;shift:string;work_choice:string;employee_snapshot:Employee}>,labor:LaborRow[],allowed:string[],label:string,date:string){
  const items=sessions.filter(s=>allowed.includes(s.shift)),seen=new Set<string>();for(const s of items){const c=supplierCode(s.employee_snapshot.supplier);if(c)seen.add(c);}const columns=SUPPLIER_ORDER.filter(c=>seen.has(c));const sp=support(items,labor,allowed,columns),picker=tenure(items,columns,"PICK",sp.deducted,date),packer=tenure(items,columns,"PACK",sp.deducted,date);
  const one=(x:{rows:Array<{total:number}>})=>{const n=x.rows[0]?.total??0,o=x.rows[1]?.total??0;return{new:n,old:o,total:n+o}};return{label,manpower:matrix(items,columns),picker_tenure:picker,packer_tenure:packer,support:sp.matrix,remaining:{picker:one(picker),packer:one(packer)},session_total:items.length};
}
function history(events:CompatEvent[]){
  const groups:Record<string,{mnv:string;full_name:string;shift:string;state:string;event_count:number;last_time:string;last_at_iso:string;last_actor:string;last_label:string}>={};
  for(const e of events){let g=groups[e.mnv];if(!g)g=groups[e.mnv]={mnv:e.mnv,full_name:e.full_name||"",shift:e.shift||"",state:"ACTIVE",event_count:0,last_time:"",last_at_iso:"",last_actor:"",last_label:""};if(e.full_name)g.full_name=e.full_name;if(e.shift)g.shift=e.shift;g.event_count++;if(e.event_type==="EXIT"||e.event_type==="ATTENDANCE_EXIT")g.state="ENDED";g.last_time=e.at||g.last_time;g.last_at_iso=e.at_iso||g.last_at_iso;g.last_actor=e.actor||g.last_actor;g.last_label=e.label||g.last_label;}
  const items=Object.values(groups).sort((a,b)=>(Date.parse(b.last_at_iso)||0)-(Date.parse(a.last_at_iso)||0));return{total:items.length,active_count:items.filter(x=>x.state==="ACTIVE").length,ended_count:items.filter(x=>x.state==="ENDED").length,items};
}
function labelFor(type:string):string{return type==="ATTENDANCE_ENTER"?"Vào ca":type==="ATTENDANCE_EXIT"?"Ra ca":type==="RESOURCE_CHANGE"?"Đổi tài nguyên":type==="LABOR_START"?"Bắt đầu công nhật":type==="LABOR_FINISH"?"Kết thúc công nhật":type;}

async function revisions(db:D1Database){
  const dates=await db.prepare("SELECT business_date,sequence_no FROM business_dates ORDER BY sequence_no DESC LIMIT 45").all<{business_date:string;sequence_no:number}>();const rows=dates.results??[];const out:Record<string,number>={};
  for(const d of rows){const r=await db.prepare("SELECT COALESCE(MAX(authority_seq),0) n FROM events WHERE business_date=?1").bind(d.business_date).first<{n:number}>();out[d.business_date]=Math.max(1,r?.n??0);}return{rows,out,floor:rows.length?rows[rows.length-1]!.business_date:""};
}

export async function compatSyncStatus(db:D1Database):Promise<Record<string,unknown>>{
  const a=await currentAuthority(db),rev=await revisions(db),rep=await db.prepare("SELECT pending_count FROM replication_status WHERE singleton_id=1").first<{pending_count:number}>();
  const master=await db.prepare("SELECT COALESCE(MAX(source_row),0) n FROM employees").first<{n:number}>();return{ok:true,business_date:rev.rows[0]?.business_date??"",server_seq:a.authority_seq,master_revision:master?.n??0,last_event_at:a.updated_at,projection_pending:rep?.pending_count??0,mode:"APP_SERVICE_D1",sync_engine:"S15_LOCAL_FIRST_45D",retention_floor:rev.floor,server_retention_floor:rev.floor,retention_epoch:a.authority_epoch,day_revisions:rev.out,authority:a,service_generation:a.service_generation};
}

export async function compatDay(db:D1Database,date:string):Promise<Record<string,unknown>>{
  const rev=await revisions(db);if(!date||!(date in rev.out))throw new CoreError("DATE_OUTSIDE_RETENTION","VALIDATION",400);
  const employees=await db.prepare("SELECT mnv,full_name,phone,main_position,supplier,department,site,warehouse,start_date,note FROM employees").all<Employee>();const staff=new Map((employees.results??[]).map(e=>[e.mnv,e]));
  const sessionsRaw=await db.prepare("SELECT session_id,mnv,business_date,shift,work_choice,state,pda_serial,user_pick,pack_table,user_pack,enter_at,exit_at,entered_by,exited_by,version FROM attendance_sessions WHERE business_date=?1 ORDER BY mnv").bind(date).all<SessionRow>();
  const sessions=(sessionsRaw.results??[]).map(s=>({id:s.session_id,business_date:s.business_date,mnv:s.mnv,employee_snapshot:staff.get(s.mnv)??{mnv:s.mnv,full_name:"",phone:"",main_position:"",supplier:"",department:"",site:"",warehouse:"",start_date:"",note:""},shift:s.shift,work_choice:s.work_choice,pda_serial:s.pda_serial,user_pick:s.user_pick,pack_table:s.pack_table,user_pack:s.user_pack,state:s.state,enter_at:s.enter_at,exit_at:s.exit_at,entered_by:s.entered_by,exited_by:s.exited_by,version:s.version}));
  const laborRaw=await db.prepare("SELECT labor_id,mnv,business_date,shift,labor_type,time_marker,state,start_at,end_at,note,deduct_staff,start_event_id,finish_event_id,version FROM labor_sessions WHERE business_date=?1 ORDER BY start_at").bind(date).all<LaborRow>();const labor=laborRaw.results??[];
  const eventRaw=await db.prepare("SELECT event_id,event_type,actor_id,committed_at,authority_seq,payload_json FROM events WHERE business_date=?1 ORDER BY authority_seq").bind(date).all<{event_id:string;event_type:string;actor_id:string;committed_at:string;authority_seq:number;payload_json:string}>();
  const events:CompatEvent[]=(eventRaw.results??[]).map(e=>{let p:Record<string,unknown>={};try{p=JSON.parse(e.payload_json) as Record<string,unknown>;}catch{}const mnv=String(p.mnv??""),emp=staff.get(mnv);const session=sessions.find(x=>x.mnv===mnv);return{event_id:e.event_id,mnv,full_name:emp?.full_name??"",shift:session?.shift??String(p.shift??""),event_type:e.event_type,label:labelFor(e.event_type),at:e.committed_at,at_iso:e.committed_at,actor:e.actor_id,detail:String(p.note??p.labor_type??""),authority_seq:e.authority_seq};});
  const report={ok:true,business_date:date,reports:{ca1_hc:period(sessions,labor,["Ca 1","Ca HC"],"Ca 1 + Ca HC",date),ca2:period(sessions,labor,["Ca 2"],"Ca 2",date),all:period(sessions,labor,["Ca 1","Ca HC","Ca 2"],"Cả ngày",date)}};
  return{business_date:date,day_revision:rev.out[date]??1,snapshot_engine:"S15_LOCAL_FIRST_45D_SERVICE",sessions,labor,events,history:history(events),report};
}

export async function compatBootstrap(db:D1Database,dates?:unknown[]):Promise<Record<string,unknown>>{
  const rev=await revisions(db),wanted=Array.isArray(dates)?dates.map(String).filter(d=>d in rev.out).slice(0,45):rev.rows.map(x=>x.business_date),days=[];for(const d of wanted)days.push(await compatDay(db,d));return{ok:true,sync_engine:"S15_LOCAL_FIRST_45D_SERVICE",retention_floor:rev.floor,retention_epoch:(await currentAuthority(db)).authority_epoch,days};
}

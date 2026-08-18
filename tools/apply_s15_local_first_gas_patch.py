#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "google-apps-script/PICK_PACK_API.gs"
text = path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S15 GAS anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)

if "v0.4.2 S15 LOCAL-FIRST 45D SYNC" in text:
    print("S15 GAS transform already present")
    raise SystemExit(0)

# Authenticated sync routes. UI reads local SQLite; these routes only reconcile revisions/snapshots.
once(
    "    if (action === 'sync_status') return ppJson_(ppSyncStatus_());\n",
    "    if (action === 'sync_day') return ppJson_(ppSyncDayS15_(auth, body));\n    if (action === 'sync_bootstrap') return ppJson_(ppSyncBootstrapS15_(auth, body));\n    if (action === 'sync_status') return ppJson_(ppSyncStatus_());\n",
    "sync routes",
)

append = r'''

// === v0.4.2 S15 LOCAL-FIRST 45D SYNC ===
// Sheet remains authoritative. PDA screens read a 45-day SQLite snapshot and only fetch dates whose
// day revision changed. N and N-1 are the only editable business dates; older retained dates are immutable.
function ppIsoDateFromVisibleS15_(v) {
  if(!v)return '';
  try{return Utilities.formatDate(Utilities.parseDate(String(v),PP.TZ,'dd/MM/yyyy'),PP.TZ,'yyyy-MM-dd');}catch(_){return '';}
}
function ppVisibleDateFromIsoS15_(iso) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(String(iso||'')))return '';
  try{return Utilities.formatDate(Utilities.parseDate(String(iso),PP.TZ,'yyyy-MM-dd'),PP.TZ,'dd/MM/yyyy');}catch(_){return '';}
}
function ppRetentionFloorS15_() {
  const now=Utilities.parseDate(ppBusinessVisible_(),PP.TZ,'dd/MM/yyyy');
  return Utilities.formatDate(new Date(now.getTime()-44*86400000),PP.TZ,'yyyy-MM-dd');
}
function ppPreviousBusinessIsoS15_() {
  const now=Utilities.parseDate(ppBusinessVisible_(),PP.TZ,'dd/MM/yyyy');
  return Utilities.formatDate(new Date(now.getTime()-86400000),PP.TZ,'yyyy-MM-dd');
}
function ppDateRetainedS15_(iso){const v=String(iso||'');return !!v&&v>=ppRetentionFloorS15_()&&v<=ppBusinessIso_();}
function ppDateEditableS15_(iso){const v=String(iso||'');return v===ppBusinessIso_()||v===ppPreviousBusinessIsoS15_();}
function ppDayRevisionPropsS15_(){return PropertiesService.getScriptProperties();}
function ppWriteDayRevisionsS15_(map){ppDayRevisionPropsS15_().setProperty('PP_DAY_REVISIONS_S15',JSON.stringify(map));}
function ppSeedDayRevisionsS15_(){
  const floor=ppRetentionFloorS15_(),today=ppBusinessIso_(),out={};
  [PP.RA,PP.LABOR,PP.HISTORY].forEach(function(name){
    const sh=ppSs_().getSheetByName(name);if(!sh||sh.getLastRow()<2)return;
    const vals=sh.getRange(2,1,sh.getLastRow()-1,1).getDisplayValues();
    vals.forEach(function(r){const iso=ppIsoDateFromVisibleS15_((r||[])[0]);if(iso&&iso>=floor&&iso<=today&&!out[iso])out[iso]=1;});
  });
  ppWriteDayRevisionsS15_(out);return out;
}
function ppDayRevisionsS15_(){
  const raw=ppDayRevisionPropsS15_().getProperty('PP_DAY_REVISIONS_S15');
  if(!raw)return ppSeedDayRevisionsS15_();
  try{const j=JSON.parse(raw)||{},floor=ppRetentionFloorS15_(),today=ppBusinessIso_(),out={};Object.keys(j).forEach(function(d){if(d>=floor&&d<=today)out[d]=Number(j[d]||0);});return out;}catch(_){return ppSeedDayRevisionsS15_();}
}
function ppBumpDayRevisionS15_(iso){
  const date=String(iso||'');if(!ppDateRetainedS15_(date))return 0;
  const map=ppDayRevisionsS15_();map[date]=Number(map[date]||0)+1;ppWriteDayRevisionsS15_(map);return map[date];
}
function ppRetentionEpochS15_(){return Number(ppDayRevisionPropsS15_().getProperty('PP_RETENTION_EPOCH_S15')||'1');}
function ppRetentionSweepS15_(){
  const props=ppDayRevisionPropsS15_(),today=ppBusinessIso_(),floor=ppRetentionFloorS15_();
  if(props.getProperty('PP_RETENTION_SWEEP_DAY_S15')===today)return floor;
  let deleted=0;
  [PP.RA,PP.LABOR,PP.HISTORY].forEach(function(name){
    const sh=ppSs_().getSheetByName(name);if(!sh||sh.getLastRow()<2)return;
    const vals=sh.getRange(2,1,sh.getLastRow()-1,1).getDisplayValues(),rows=[];
    vals.forEach(function(r,i){const iso=ppIsoDateFromVisibleS15_((r||[])[0]);if(iso&&iso<floor)rows.push(i+2);});
    if(!rows.length)return;
    const spans=[];let s=rows[0],e=rows[0];for(let i=1;i<rows.length;i++){if(rows[i]===e+1)e=rows[i];else{spans.push([s,e]);s=rows[i];e=rows[i];}}spans.push([s,e]);
    spans.reverse().forEach(function(x){sh.deleteRows(x[0],x[1]-x[0]+1);deleted+=x[1]-x[0]+1;});
  });
  const map=ppDayRevisionsS15_();let changed=false;Object.keys(map).forEach(function(d){if(d<floor){delete map[d];changed=true;}});if(changed)ppWriteDayRevisionsS15_(map);
  const oldFloor=props.getProperty('PP_RETENTION_FLOOR_S15')||'';
  if(oldFloor!==floor||deleted>0){props.setProperty('PP_RETENTION_EPOCH_S15',String(ppRetentionEpochS15_()+1));ppBumpRevision_(false);}
  props.setProperty('PP_RETENTION_FLOOR_S15',floor);props.setProperty('PP_RETENTION_SWEEP_DAY_S15',today);return floor;
}
function ppObjectRowsForDatesS15_(sheetName,wanted){
  const sh=ppSs_().getSheetByName(sheetName),out={};Object.keys(wanted).forEach(function(d){out[d]=[];});
  if(!sh||sh.getLastRow()<2||sh.getLastColumn()<1)return out;
  const vals=sh.getDataRange().getDisplayValues(),headers=vals[0].map(function(v){return String(v||'').trim();});
  for(let ri=1;ri<vals.length;ri++){
    const row=vals[ri],iso=ppIsoDateFromVisibleS15_(row[0]);if(!iso||!wanted[iso])continue;
    const o={};headers.forEach(function(h,i){if(h)o[h]=String(row[i]==null?'':row[i]).trim();});out[iso].push(o);
  }
  return out;
}
function ppStaffMapS15_(){const out={};ppMasterSnapshotData_().staff.forEach(function(e){out[String(e.mnv||'')]=e;});return out;}
function ppSessionMapFromRowsS15_(dateIso,raRows,staffMap){
  const out={};
  raRows.forEach(function(r){
    const mnv=String(r['Mã nhân viên']||'').trim();if(!mnv)return;
    const action=ppFold_(r['App action']||r['App Action']||r['Loại thao tác']);let ss=out[mnv];
    if(action==='ENTER'||action==='VAO'){
      const snap=ppEmployeeFromRa_(r),master=staffMap[mnv]||{};snap.start_date=master.start_date||'';
      out[mnv]=ss={id:dateIso+'|'+mnv,business_date:dateIso,mnv:mnv,employee_snapshot:snap,shift:String(r['Ca']||''),work_choice:ppWorkCode_(r['Vị trí trong ca']),pda_serial:String(r['Seri PDA']||'')||null,user_pick:String(r['User Pick']||'')||null,pack_table:String(r['Bàn Pack']||'')||null,user_pack:String(r['User Pack']||'')||null,state:'ACTIVE',enter_at:ppIsoFromVisible_(r['Thời gian cập nhật']),exit_at:null,entered_by:String(r['Người cập nhật']||''),exited_by:null};
    }else if((action==='RESOURCE'||action==='DOI TAI NGUYEN'||action==='CAP NHAT')&&ss&&ss.state==='ACTIVE'){
      ss.work_choice=ppWorkCode_(r['Vị trí trong ca']);ss.pda_serial=String(r['Seri PDA']||'')||null;ss.user_pick=String(r['User Pick']||'')||null;ss.pack_table=String(r['Bàn Pack']||'')||null;ss.user_pack=String(r['User Pack']||'')||null;
    }else if((action==='EXIT'||action==='RA')&&ss&&ss.state==='ACTIVE'){
      ss.work_choice=ppWorkCode_(r['Vị trí trong ca']);ss.pda_serial=String(r['Seri PDA']||'')||null;ss.user_pick=String(r['User Pick']||'')||null;ss.pack_table=String(r['Bàn Pack']||'')||null;ss.user_pack=String(r['User Pack']||'')||null;ss.state='ENDED';ss.exit_at=ppIsoFromVisible_(r['Thời gian cập nhật']);ss.exited_by=String(r['Người cập nhật']||'');
    }
  });
  return out;
}
function ppRaEventsFromRowsS15_(dateIso,raRows){
  const out=[];raRows.forEach(function(r){
    const mnv=String(r['Mã nhân viên']||'').trim();if(!mnv)return;const raw=ppFold_(r['App action']||r['App Action']||r['Loại thao tác']);let type='',label='';
    if(raw==='ENTER'||raw==='VAO'){type='ENTER';label='Vào ca';}else if(raw==='EXIT'||raw==='RA'){type='EXIT';label='Ra ca';}else if(raw==='RESOURCE'||raw==='DOI TAI NGUYEN'||raw==='CAP NHAT'){type='RESOURCE';label='Đổi / trả tài nguyên';}else return;
    const work=String(r['Vị trí trong ca']||''),pda=String(r['Seri PDA']||r['Mã PDA']||''),pick=String(r['User Pick']||''),table=String(r['Bàn Pack']||''),pack=String(r['User Pack']||''),at=String(r['Thời gian cập nhật']||'');
    out.push({scope:'SESSION',session_id:dateIso+'|'+mnv,mnv:mnv,full_name:String(r['Họ và tên']||r['Họ tên']||''),shift:String(r['Ca']||''),event_type:type,label:label,at:at,at_iso:ppIsoFromVisible_(at),actor:String(r['Người cập nhật']||''),detail:ppHistoryResourceTextS13_(work,pda,pick,table,pack),event_id:String(r['Event ID']||'')});
  });return out;
}
function ppLaborCompactS15_(dateIso,laborRows){
  return laborRows.map(function(r){return {business_date:dateIso,mnv:String(r['Mã nhân viên']||''),full_name:String(r['Họ và tên']||r['Họ tên']||''),shift:String(r['Ca']||''),labor_type:String(r['Loại công nhật']||r['Thông tin công nhật']||''),start_at:String(r['Thời gian bắt đầu']||''),end_at:String(r['Thời gian kết thúc']||''),time_marker:String(r['Mốc thời gian']||''),status:String(r['Trạng thái']||''),note:String(r['Ghi chú']||''),actor:String(r['Người cập nhật']||''),deduct_staff:ppFold_(r['Khấu trừ nhân sự'])==='CO',event_id:String(r['Event ID']||''),finish_event_id:String(r['Finish Event ID']||'')};}).filter(function(x){return !!x.mnv;});
}
function ppLaborEventsCompactS15_(dateIso,labor){
  const out=[];labor.forEach(function(r){const detail=[r.labor_type,r.time_marker?('Mốc '+r.time_marker):'',r.deduct_staff?'Khấu trừ Có':''].filter(Boolean).join(' • ');if(r.start_at)out.push({scope:'SESSION',session_id:dateIso+'|'+r.mnv,mnv:r.mnv,full_name:r.full_name,shift:r.shift,event_type:'LABOR_START',label:'Bắt đầu công nhật',at:r.start_at,at_iso:ppIsoFromVisible_(r.start_at),actor:r.actor,detail:detail,event_id:r.event_id});if(r.end_at)out.push({scope:'SESSION',session_id:dateIso+'|'+r.mnv,mnv:r.mnv,full_name:r.full_name,shift:r.shift,event_type:'LABOR_FINISH',label:'Hoàn thành công nhật',at:r.end_at,at_iso:ppIsoFromVisible_(r.end_at),actor:r.actor,detail:detail,event_id:r.finish_event_id});});return out;
}
function ppAuditEventsFromRowsS15_(auditRows){
  return auditRows.map(function(r){const at=String(r['Thời gian']||'');return {scope:String(r['Phạm vi']||'SESSION'),session_id:String(r['Session ID']||''),mnv:String(r['Mã nhân viên']||''),full_name:String(r['Họ tên']||''),shift:String(r['Ca']||''),event_type:String(r['Loại sự kiện']||''),label:String(r['Nhãn sự kiện']||''),at:at,at_iso:ppIsoFromVisible_(at),actor:String(r['Người xử lý']||''),detail:String(r['Chi tiết']||''),event_id:String(r['Event ID']||'')};}).filter(function(x){return x.scope==='SESSION'&&x.mnv;});
}
function ppMergeEventsS15_(audit,fallback){
  const seen={},out=[];function key(e){return e.event_id||[e.mnv,e.event_type,e.at].join('|');}
  audit.concat(fallback).forEach(function(e){const k=key(e);if(!seen[k]){seen[k]=true;out.push(e);}});out.sort(function(a,b){return (Date.parse(a.at_iso||'')||0)-(Date.parse(b.at_iso||'')||0);});return out;
}
function ppHistorySummaryS15_(events){
  const groups={};events.forEach(function(e){let g=groups[e.mnv];if(!g)g=groups[e.mnv]={mnv:e.mnv,full_name:e.full_name||'',shift:e.shift||'',state:'ACTIVE',event_count:0,last_time:'',last_at_iso:'',last_actor:'',last_label:''};if(e.full_name)g.full_name=e.full_name;if(e.shift)g.shift=e.shift;g.event_count++;if(e.event_type==='EXIT')g.state='ENDED';g.last_time=e.at||g.last_time;g.last_at_iso=e.at_iso||g.last_at_iso;g.last_actor=e.actor||g.last_actor;g.last_label=e.label||g.last_label;});
  const items=Object.keys(groups).map(function(k){return groups[k];}).sort(function(a,b){return (Date.parse(b.last_at_iso||'')||0)-(Date.parse(a.last_at_iso||'')||0);});return {total:items.length,active_count:items.filter(function(x){return x.state==='ACTIVE';}).length,ended_count:items.filter(function(x){return x.state==='ENDED';}).length,items:items};
}
function ppTenureDaysAtS15_(startDate,dateVisible){if(!startDate)return 99999;try{const s=Utilities.parseDate(String(startDate),PP.TZ,'dd/MM/yyyy'),d=Utilities.parseDate(String(dateVisible),PP.TZ,'dd/MM/yyyy');return Math.max(0,Math.floor((d.getTime()-s.getTime())/86400000));}catch(_){return 99999;}}
function ppReportColumnsS15_(sessions){const seen={};sessions.forEach(function(ss){const e=ss.employee_snapshot||{},c=ppSupplierCode_(e.supplier);if(c)seen[c]=true;});return ppReportSupplierOrder_().filter(function(c){return !!seen[c];});}
function ppReportMatrixS15_(sessions,columns){const rows=ppReportRows_(),matrix={};rows.forEach(function(p){matrix[p]={};columns.forEach(function(c){matrix[p][c]=0;});});sessions.forEach(function(ss){const e=ss.employee_snapshot||{},pos=ppReportPositionS12_(ss,e),sup=ppSupplierCode_(e.supplier);if(pos&&sup&&matrix[pos]&&columns.indexOf(sup)>=0)matrix[pos][sup]++;});const outRows=rows.map(function(p){const counts={};columns.forEach(function(c){counts[c]=matrix[p][c]||0;});return {position:p,counts:counts,total:columns.reduce(function(n,c){return n+(counts[c]||0);},0)};});const totals={};columns.forEach(function(c){totals[c]=outRows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});return {columns:columns,rows:outRows,totals:totals,total:columns.reduce(function(n,c){return n+(totals[c]||0);},0)};}
function ppSupportS15_(sessions,labor,allowed,columns){const byMnv={},deducted={},rowsByType={},seen={};sessions.forEach(function(ss){byMnv[ss.mnv]=ss;});labor.forEach(function(r){if(allowed.indexOf(String(r.shift||''))<0||!r.deduct_staff)return;const mnv=String(r.mnv||''),ss=byMnv[mnv];if(!mnv||!ss)return;const e=ss.employee_snapshot||{},type=String(r.labor_type||'Khác');if(!ppDeductAllowed_(e.main_position||'',type))return;const k=type+'|'+mnv;if(seen[k])return;seen[k]=true;deducted[mnv]=true;const sup=ppSupplierCode_(e.supplier);if(!sup||columns.indexOf(sup)<0)return;if(!rowsByType[type]){rowsByType[type]={label:type,counts:{},total:0};columns.forEach(function(c){rowsByType[type].counts[c]=0;});}rowsByType[type].counts[sup]=(rowsByType[type].counts[sup]||0)+1;rowsByType[type].total++;});const rows=Object.keys(rowsByType).sort().map(function(k){return rowsByType[k];}),totals={};columns.forEach(function(c){totals[c]=rows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});return {deducted:deducted,matrix:{columns:columns,rows:rows,totals:totals,total:rows.reduce(function(n,r){return n+r.total;},0),unique_staff:Object.keys(deducted).length}};}
function ppTenureS15_(sessions,columns,work,deducted,dateVisible){const data={'Nhân sự mới':{},'Nhân sự cũ':{}};columns.forEach(function(c){data['Nhân sự mới'][c]=0;data['Nhân sự cũ'][c]=0;});sessions.forEach(function(ss){if(String(ss.work_choice||'')!==work||deducted[ss.mnv])return;const e=ss.employee_snapshot||{},sup=ppSupplierCode_(e.supplier);if(!sup||columns.indexOf(sup)<0)return;const label=ppTenureDaysAtS15_(e.start_date,dateVisible)<=30?'Nhân sự mới':'Nhân sự cũ';data[label][sup]++;});const rows=['Nhân sự mới','Nhân sự cũ'].map(function(label){const counts={};columns.forEach(function(c){counts[c]=data[label][c]||0;});return {label:label,counts:counts,total:columns.reduce(function(n,c){return n+(counts[c]||0);},0)};});const totals={};columns.forEach(function(c){totals[c]=rows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});return {columns:columns,rows:rows,totals:totals,total:rows.reduce(function(n,r){return n+r.total;},0)};}
function ppReportPeriodS15_(sessions,labor,allowed,label,dateVisible){const items=sessions.filter(function(ss){return allowed.indexOf(ss.shift)>=0;}),columns=ppReportColumnsS15_(items),support=ppSupportS15_(items,labor,allowed,columns),picker=ppTenureS15_(items,columns,'PICK',support.deducted,dateVisible),packer=ppTenureS15_(items,columns,'PACK',support.deducted,dateVisible);return {label:label,manpower:ppReportMatrixS15_(items,columns),picker_tenure:picker,packer_tenure:packer,support:support.matrix,remaining:ppRemainingFromTenureS12_(picker,packer),session_total:items.length};}
function ppReportForDateS15_(dateIso,sessions,labor){const visible=ppVisibleDateFromIsoS15_(dateIso);return {ok:true,business_date:dateIso,reports:{ca1_hc:ppReportPeriodS15_(sessions,labor,['Ca 1','Ca HC'],'Ca 1 + Ca HC',visible),ca2:ppReportPeriodS15_(sessions,labor,['Ca 2'],'Ca 2',visible),all:ppReportPeriodS15_(sessions,labor,['Ca 1','Ca HC','Ca 2'],'Cả ngày',visible)}};}
function ppDaySnapshotFromRowsS15_(dateIso,raRows,laborRows,auditRows,revision,staffMap){const sm=ppSessionMapFromRowsS15_(dateIso,raRows,staffMap),sessions=Object.keys(sm).map(function(k){return sm[k];}),labor=ppLaborCompactS15_(dateIso,laborRows),fallback=ppRaEventsFromRowsS15_(dateIso,raRows).concat(ppLaborEventsCompactS15_(dateIso,labor)),events=ppMergeEventsS15_(ppAuditEventsFromRowsS15_(auditRows),fallback);return {business_date:dateIso,day_revision:Number(revision||0),snapshot_engine:'S15_LOCAL_FIRST_45D',sessions:sessions,labor:labor,events:events,history:ppHistorySummaryS15_(events),report:ppReportForDateS15_(dateIso,sessions,labor)};}
function ppSyncDayS15_(auth,body){const iso=String(body.business_date||'').trim();if(!ppDateRetainedS15_(iso))return {ok:false,error:'DATE_OUTSIDE_RETENTION'};const visible=ppVisibleDateFromIsoS15_(iso),revs=ppDayRevisionsS15_(),staff=ppStaffMapS15_(),ra=ppRowsForDateS12_(PP.RA,visible),labor=ppRowsForDateS12_(PP.LABOR,visible);ppHistoryEnsureS13_();const audit=ppRowsForDateS12_(PP.HISTORY,visible);return {ok:true,sync_engine:'S15_LOCAL_FIRST_45D',day:ppDaySnapshotFromRowsS15_(iso,ra,labor,audit,revs[iso]||0,staff)};}
function ppSyncBootstrapS15_(auth,body){ppRetentionSweepS15_();const revs=ppDayRevisionsS15_(),req=body.dates,wanted={};if(Array.isArray(req)){req.slice(0,45).forEach(function(d){d=String(d||'');if(ppDateRetainedS15_(d)&&revs[d]!=null)wanted[d]=true;});}else Object.keys(revs).forEach(function(d){wanted[d]=true;});const dates=Object.keys(wanted).sort().reverse();ppHistoryEnsureS13_();const ra=ppObjectRowsForDatesS15_(PP.RA,wanted),labor=ppObjectRowsForDatesS15_(PP.LABOR,wanted),audit=ppObjectRowsForDatesS15_(PP.HISTORY,wanted),staff=ppStaffMapS15_(),days=[];dates.forEach(function(d){days.push(ppDaySnapshotFromRowsS15_(d,ra[d]||[],labor[d]||[],audit[d]||[],revs[d]||0,staff));});return {ok:true,sync_engine:'S15_LOCAL_FIRST_45D',retention_floor:ppRetentionFloorS15_(),retention_epoch:ppRetentionEpochS15_(),days:days};}

// Late overrides are authoritative for all existing callers.
function ppBumpRevision_(dateIso) {
  const p=PropertiesService.getScriptProperties();const n=Number(p.getProperty('PP_REVISION')||'1')+1;p.setProperty('PP_REVISION',String(n));
  if(dateIso!==false){try{ppBumpDayRevisionS15_(typeof dateIso==='string'&&dateIso?dateIso:ppBusinessIso_());}catch(err){console.error('S15 day revision '+String(err));}}
  return n;
}
function ppSyncStatus_(){const floor=ppRetentionSweepS15_();return {ok:true,business_date:ppBusinessIso_(),server_seq:ppRevision_(),master_revision:ppMasterRevision_(),last_event_at:ppNowIso_(),projection_pending:0,mode:'APP_GSHEET',sync_engine:'S15_LOCAL_FIRST_45D',retention_floor:floor,retention_epoch:ppRetentionEpochS15_(),day_revisions:ppDayRevisionsS15_()};}
function ppHealth_(){const rows=ppValues_(PP.STAFF);return {ok:true,service:'pick-pack-gsheet-api',mode:'APP_GSHEET',api_version:'0.4.2',sheet_read:rows.length>1,auth_session_model:'SINGLE_ACTIVE_DEVICE_V1',business_date:ppBusinessIso_(),revision:ppRevision_(),master_revision:ppMasterRevision_(),report_engine:'S12_CURRENT_DAY',history_engine:'S13_SHARED_SESSION',sync_engine:'S15_LOCAL_FIRST_45D',retention_days:45,editable_days:2};}
function onEdit(e){
  try{
    if(!e||!e.range)return;const name=e.range.getSheet().getName(),masters=[PP.CATALOG,PP.STAFF,PP.PDA,PP.PICK,PP.TABLE,PP.PACK,PP.ADMIN];
    if(masters.indexOf(name)>=0){ppBumpMasterRevision_();ppBumpRevision_();return;}
    if(name!==PP.RA&&name!==PP.LABOR&&name!==PP.HISTORY)return;
    const row=Math.max(2,e.range.getRow()),visible=e.range.getSheet().getRange(row,1).getDisplayValue(),iso=ppIsoDateFromVisibleS15_(visible);
    if(iso&&!ppDateEditableS15_(iso)){
      if(e.range.getNumRows()===1&&e.range.getNumColumns()===1&&typeof e.oldValue!=='undefined')e.range.setValue(e.oldValue);
      try{e.range.setNote('Chỉ được sửa dữ liệu ngày N và N-1.');}catch(_){}
      return;
    }
    ppBumpRevision_(iso||ppBusinessIso_());
  }catch(err){console.error('onEdit S15 '+String(err));}
}
'''

text += append
path.write_text(text, encoding="utf-8")
print("S15 local-first 45-day GAS sync transform applied")

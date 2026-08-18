#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "google-apps-script/PICK_PACK_API.gs"
text = path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S13 GAS anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)


def insert_before(marker: str, payload: str, label: str) -> None:
    global text
    count = text.count(marker)
    if count != 1:
        raise SystemExit(f"S13 GAS insert {label!r}: expected 1 marker, got {count}")
    text = text.replace(marker, payload + marker, 1)


# Dedicated business-audit sheet. Account/email/password administration is intentionally excluded.
once("  LABOR: 'CÔNG NHẬT',\n", "  LABOR: 'CÔNG NHẬT',\n  HISTORY: 'LỊCH SỬ NGHIỆP VỤ',\n", "history constant")
once(
    "    if (action === 'report_daily') return ppJson_(ppReportDaily_());\n",
    "    if (action === 'report_daily') return ppJson_(ppReportDaily_());\n    if (action === 'history_shared') return ppJson_(ppHistorySharedS13_(auth, body));\n",
    "history route",
)

history_functions = r'''
// === v0.4.2 S13 SHARED BUSINESS HISTORY ===
// Shared operational history only. Never append account/password/email administration here.
function ppHistoryEnsureS13_() {
  const ss=ppSs_(); let sh=ss.getSheetByName(PP.HISTORY);
  if(!sh) sh=ss.insertSheet(PP.HISTORY);
  const headers=['Ngày','Session ID','Mã nhân viên','Họ tên','Ca','Loại sự kiện','Nhãn sự kiện','Thời gian','Người xử lý','Chi tiết','Event ID','Phạm vi','App Revision'];
  const current=sh.getLastColumn() ? sh.getRange(1,1,1,Math.max(sh.getLastColumn(),headers.length)).getDisplayValues()[0] : [];
  let mismatch=sh.getLastRow()<1;
  for(let i=0;i<headers.length&&!mismatch;i++) if(String(current[i]||'').trim()!==headers[i]) mismatch=true;
  if(mismatch) sh.getRange(1,1,1,headers.length).setValues([headers]);
  if(sh.getFrozenRows()<1) sh.setFrozenRows(1);
  return sh;
}
function ppHistorySafeAppendS13_(event) {
  try {
    const sh=ppHistoryEnsureS13_();
    sh.appendRow([
      ppBusinessVisible_(), String(event.session_id||''), String(event.mnv||''), String(event.full_name||''), String(event.shift||''),
      String(event.event_type||''), String(event.label||''), String(event.at||ppNowVisible_()), String(event.actor||''), String(event.detail||''),
      String(event.event_id||''), String(event.scope||'SESSION'), Number(event.revision||ppRevision_())
    ]);
  } catch(err) { console.error('S13 history append '+String(err)); }
}
function ppHistoryResourceTextS13_(work,pda,pick,table,pack) {
  const parts=[]; if(work)parts.push('Vị trí '+work); if(pda)parts.push('PDA '+pda); if(pick)parts.push('User Pick '+pick); if(table)parts.push('Bàn '+table); if(pack)parts.push('User Pack '+pack);
  return parts.join(' • ') || 'Không giữ tài nguyên';
}
function ppHistoryRaFallbackS13_(dateVisible) {
  return ppRowsForDateS12_(PP.RA,dateVisible).map(function(r){
    const mnv=String(r['Mã nhân viên']||'').trim(); if(!mnv)return null;
    const raw=ppFold_(r['App Action']||r['App action']||r['Loại thao tác']);
    let type='',label='';
    if(raw==='ENTER'||raw==='VAO'){type='ENTER';label='Vào ca';}
    else if(raw==='EXIT'||raw==='RA'){type='EXIT';label='Ra ca';}
    else if(raw==='RESOURCE'||raw==='DOI TAI NGUYEN'||raw==='CAP NHAT'){type='RESOURCE';label='Đổi / trả tài nguyên';}
    else return null;
    const work=String(r['Vị trí trong ca']||'').trim(),pda=String(r['Seri PDA']||r['Mã PDA']||'').trim(),pick=String(r['User Pick']||'').trim(),table=String(r['Bàn Pack']||'').trim(),pack=String(r['User Pack']||'').trim();
    const at=String(r['Thời gian cập nhật']||'').trim();
    return {scope:'SESSION',session_id:dateVisible+'|'+mnv,mnv:mnv,full_name:String(r['Họ và tên']||r['Họ tên']||'').trim(),shift:String(r['Ca']||'').trim(),event_type:type,label:label,at:at,at_iso:ppIsoFromVisible_(at),actor:String(r['Người cập nhật']||'').trim(),detail:ppHistoryResourceTextS13_(work,pda,pick,table,pack),event_id:String(r['Event ID']||'').trim()};
  }).filter(Boolean);
}
function ppHistoryLaborFallbackS13_(dateVisible) {
  const out=[];
  ppRowsForDateS12_(PP.LABOR,dateVisible).forEach(function(r){
    const mnv=String(r['Mã nhân viên']||'').trim(); if(!mnv)return;
    const name=String(r['Họ và tên']||r['Họ tên']||'').trim(),shift=String(r['Ca']||'').trim(),type=String(r['Loại công nhật']||r['Thông tin công nhật']||'').trim(),marker=String(r['Mốc thời gian']||'').trim(),deduct=String(r['Khấu trừ nhân sự']||'').trim(),actor=String(r['Người cập nhật']||'').trim();
    const detail=[type,marker?('Mốc '+marker):'',deduct?('Khấu trừ '+deduct):''].filter(Boolean).join(' • ');
    const start=String(r['Thời gian bắt đầu']||'').trim(),startId=String(r['Event ID']||'').trim();
    if(start) out.push({scope:'SESSION',session_id:dateVisible+'|'+mnv,mnv:mnv,full_name:name,shift:shift,event_type:'LABOR_START',label:'Bắt đầu công nhật',at:start,at_iso:ppIsoFromVisible_(start),actor:actor,detail:detail,event_id:startId});
    const end=String(r['Thời gian kết thúc']||'').trim(),finishId=String(r['Finish Event ID']||'').trim();
    if(end) out.push({scope:'SESSION',session_id:dateVisible+'|'+mnv,mnv:mnv,full_name:name,shift:shift,event_type:'LABOR_FINISH',label:'Hoàn thành công nhật',at:end,at_iso:ppIsoFromVisible_(end),actor:actor,detail:detail,event_id:finishId});
  });
  return out;
}
function ppHistoryAuditS13_(dateVisible) {
  ppHistoryEnsureS13_();
  return ppRowsForDateS12_(PP.HISTORY,dateVisible).map(function(r){
    const at=String(r['Thời gian']||'').trim();
    return {scope:String(r['Phạm vi']||'SESSION'),session_id:String(r['Session ID']||''),mnv:String(r['Mã nhân viên']||''),full_name:String(r['Họ tên']||''),shift:String(r['Ca']||''),event_type:String(r['Loại sự kiện']||''),label:String(r['Nhãn sự kiện']||''),at:at,at_iso:ppIsoFromVisible_(at),actor:String(r['Người xử lý']||''),detail:String(r['Chi tiết']||''),event_id:String(r['Event ID']||'')};
  }).filter(function(x){return x.scope==='SESSION'&&x.mnv;});
}
function ppHistoryEventsS13_(dateVisible) {
  const audit=ppHistoryAuditS13_(dateVisible),fallback=ppHistoryRaFallbackS13_(dateVisible).concat(ppHistoryLaborFallbackS13_(dateVisible)),byKey={},out=[];
  function key(e){return e.event_id||[e.mnv,e.event_type,e.at].join('|');}
  audit.forEach(function(e){const k=key(e);if(!byKey[k]){byKey[k]=true;out.push(e);}});
  fallback.forEach(function(e){const k=key(e);if(!byKey[k]){byKey[k]=true;out.push(e);}});
  out.sort(function(a,b){const aa=Date.parse(a.at_iso||'')||0,bb=Date.parse(b.at_iso||'')||0;return aa-bb;});
  return out;
}
function ppHistorySharedS13_(auth,body) {
  const dateVisible=ppBusinessVisible_(),mnv=String(body.mnv||'').trim(),events=ppHistoryEventsS13_(dateVisible);
  if(mnv){
    const timeline=events.filter(function(e){return e.mnv===mnv;});
    const staff=ppLookupStaff_(mnv)||null;
    return {ok:true,source:'SHARED_GSHEET',history_engine:'S13_SHARED_SESSION',business_date:ppBusinessIso_(),mnv:mnv,employee:staff,timeline:timeline};
  }
  const groups={};
  events.forEach(function(e){
    let g=groups[e.mnv]; if(!g)g=groups[e.mnv]={mnv:e.mnv,full_name:e.full_name||'',shift:e.shift||'',state:'ACTIVE',event_count:0,last_time:'',last_at_iso:'',last_actor:'',last_label:''};
    if(e.full_name)g.full_name=e.full_name;if(e.shift)g.shift=e.shift;g.event_count++;
    if(e.event_type==='EXIT')g.state='ENDED';
    g.last_time=e.at||g.last_time;g.last_at_iso=e.at_iso||g.last_at_iso;g.last_actor=e.actor||g.last_actor;g.last_label=e.label||g.last_label;
  });
  const items=Object.keys(groups).map(function(k){return groups[k];}).sort(function(a,b){return (Date.parse(b.last_at_iso||'')||0)-(Date.parse(a.last_at_iso||'')||0);});
  return {ok:true,source:'SHARED_GSHEET',history_engine:'S13_SHARED_SESSION',business_date:ppBusinessIso_(),total:items.length,active_count:items.filter(function(x){return x.state==='ACTIVE';}).length,ended_count:items.filter(function(x){return x.state==='ENDED';}).length,items:items};
}

'''
insert_before("function ppEmployeeContext_(body) {", history_functions, "shared history functions")

# Record only successful session/business mutations. No account/email/password actions are touched.
once(
    "  const res=ppValidateResources_(mnv,choice,body,shift); const rev=ppAppendRa_(staff,shift,choice,res,'VÀO','ENTER',eventId,auth.login_id,'PUBLIC BETA');\n  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};\n",
    "  const res=ppValidateResources_(mnv,choice,body,shift); const rev=ppAppendRa_(staff,shift,choice,res,'VÀO','ENTER',eventId,auth.login_id,'PUBLIC BETA');\n  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:staff.full_name,shift:shift,event_type:'ENTER',label:'Vào ca',at:ppNowVisible_(),actor:auth.login_id,detail:ppHistoryResourceTextS13_(ppWorkLabel_(choice),res.pda,res.userPick,res.packTable,res.userPack),event_id:eventId,revision:rev});\n  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};\n",
    "enter audit",
)
once(
    "  const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const res={pda:s.pda_serial,userPick:s.user_pick,packTable:s.pack_table,userPack:s.user_pack}; const rev=ppAppendRa_(staff,s.shift,s.work_choice,res,'RA','EXIT',eventId,auth.login_id,'PUBLIC BETA');\n  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};\n",
    "  const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const res={pda:s.pda_serial,userPick:s.user_pick,packTable:s.pack_table,userPack:s.user_pack}; const rev=ppAppendRa_(staff,s.shift,s.work_choice,res,'RA','EXIT',eventId,auth.login_id,'PUBLIC BETA');\n  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:staff.full_name,shift:s.shift,event_type:'EXIT',label:'Ra ca',at:ppNowVisible_(),actor:auth.login_id,detail:ppHistoryResourceTextS13_(ppWorkLabel_(s.work_choice),res.pda,res.userPick,res.packTable,res.userPack),event_id:eventId,revision:rev});\n  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};\n",
    "exit audit",
)
once(
    "  const res=ppValidateResources_(mnv,choice,body,s.shift); const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const rev=ppAppendRa_(staff,s.shift,choice,res,'ĐỔI TÀI NGUYÊN','RESOURCE',eventId,auth.login_id,'ĐỔI TÀI NGUYÊN');\n  return {ok:true,result:{event_id:eventId,revision:rev}};\n",
    "  const res=ppValidateResources_(mnv,choice,body,s.shift); const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const before=ppHistoryResourceTextS13_(ppWorkLabel_(s.work_choice),s.pda_serial,s.user_pick,s.pack_table,s.user_pack); const after=ppHistoryResourceTextS13_(ppWorkLabel_(choice),res.pda,res.userPick,res.packTable,res.userPack); const rev=ppAppendRa_(staff,s.shift,choice,res,'ĐỔI TÀI NGUYÊN','RESOURCE',eventId,auth.login_id,'ĐỔI TÀI NGUYÊN');\n  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:staff.full_name,shift:s.shift,event_type:'RESOURCE',label:'Đổi / trả tài nguyên',at:ppNowVisible_(),actor:auth.login_id,detail:before+' → '+after,event_id:eventId,revision:rev});\n  return {ok:true,result:{event_id:eventId,revision:rev}};\n",
    "resource audit",
)

# Patch the S12 override of labor_start (the authoritative late declaration).
start = text.find("function ppLaborStart_(auth,body) {", text.find("// === v0.4.2 S12 CURRENT-DAY CACHE / REPORT OVERRIDES ==="))
end = text.find("function ppReportRows_()", start)
if start < 0 or end < 0:
    raise SystemExit("S13 GAS S12 labor_start block not found")
labor_start = r'''function ppLaborStart_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const mnv=String(body.mnv||'').trim(), eventId=String(body.event_id||'').trim(), type=String(body.labor_type||'').trim(), marker=String(body.time_marker||'Trong ngày').trim(), note=String(body.note||'').trim();
  if(!mnv||!eventId||!type)return {ok:false,error:'LABOR_FIELDS_INVALID'};
  if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const ss=ppSessionMap_(ppBusinessVisible_())[mnv];
  if(!ss||ss.state!=='ACTIVE')return {ok:false,error:'PP_SESSION_NOT_ENTERED'};
  if(ppActiveLabor_(mnv))return {ok:false,error:'PP_LABOR_ALREADY_ACTIVE'};
  const catalog=ppCatalog_(); if(catalog.labor_types.length && catalog.labor_types.indexOf(type)<0)return {ok:false,error:'LABOR_TYPE_INVALID'};
  const e=ppLookupStaff_(mnv)||ss.employee_snapshot;
  const deduct=body.deduct_staff===true && ppDeductAllowed_(e.main_position||'',type);
  ppEnsureOperationalHeaders_();
  const at=ppNowVisible_();
  ppSheet_(PP.LABOR).appendRow([ppBusinessVisible_(),ss.shift,mnv,e.full_name,e.phone,e.supplier,e.department,e.site,e.warehouse,e.main_position,ppWorkLabel_(ss.work_choice),type,at,'',marker,'Đang làm',note,auth.login_id,at,eventId,'',ppRevision_()+1,deduct?'Có':'Không']);
  const rev=ppBumpRevision_();
  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:e.full_name,shift:ss.shift,event_type:'LABOR_START',label:'Bắt đầu công nhật',at:at,actor:auth.login_id,detail:type+' • Mốc '+marker+' • Khấu trừ '+(deduct?'Có':'Không'),event_id:eventId,revision:rev});
  return {ok:true,result:{event_id:eventId,revision:rev,deduct_staff:deduct},projection:'DIRECT_GSHEET'};
}

'''
text = text[:start] + labor_start + text[end:]

# Finish labor: preserve exact finisher actor in shared audit before the row can lose historical actor context.
once(
    "  const oldNote=String(sh.getRange(row,17).getDisplayValue()||''); sh.getRange(row,14).setValue(ppNowVisible_()); sh.getRange(row,16).setValue('Hoàn thành'); sh.getRange(row,17).setValue(note || oldNote); sh.getRange(row,18).setValue(auth.login_id); sh.getRange(row,19).setValue(ppNowVisible_()); sh.getRange(row,21).setValue(eventId); sh.getRange(row,22).setValue(ppRevision_()+1); const rev=ppBumpRevision_();\n  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};\n",
    "  const hist=vals[row-1]||[],histShift=String(hist[1]||''),histName=String(hist[3]||''),histType=String(hist[11]||''),histMarker=String(hist[14]||''),histDeduct=String(hist[22]||''); const oldNote=String(sh.getRange(row,17).getDisplayValue()||''); const at=ppNowVisible_(); sh.getRange(row,14).setValue(at); sh.getRange(row,16).setValue('Hoàn thành'); sh.getRange(row,17).setValue(note || oldNote); sh.getRange(row,18).setValue(auth.login_id); sh.getRange(row,19).setValue(at); sh.getRange(row,21).setValue(eventId); sh.getRange(row,22).setValue(ppRevision_()+1); const rev=ppBumpRevision_();\n  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:histName,shift:histShift,event_type:'LABOR_FINISH',label:'Hoàn thành công nhật',at:at,actor:auth.login_id,detail:histType+' • Mốc '+histMarker+' • Khấu trừ '+histDeduct,event_id:eventId,revision:rev});\n  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};\n",
    "labor finish audit",
)

# Surface live engine marker for deployment/preflight verification.
once(
    "report_engine:'S12_CURRENT_DAY',sheet_read:rows.length>1",
    "report_engine:'S12_CURRENT_DAY',history_engine:'S13_SHARED_SESSION',sheet_read:rows.length>1",
    "history health marker",
)

path.write_text(text, encoding="utf-8")
print("S13 shared business history GAS patch applied")

#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "google-apps-script/PICK_PACK_API.gs"
text = path.read_text(encoding="utf-8")
start_marker = "// === v0.4.2 FINAL CACHE / REPORT OVERRIDES ==="
end_marker = "function ppStaffSearch_(body) {"
if text.count(start_marker) != 1:
    raise SystemExit("S12 GAS start anchor changed")
start = text.index(start_marker)
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("S12 GAS end anchor changed")

replacement = r'''// === v0.4.2 S12 CURRENT-DAY CACHE / REPORT OVERRIDES ===
// Read only matching business-date row spans instead of materializing every historical cell.
function ppRowsForDateS12_(sheetName,dateVisible) {
  const rev=ppRevision_(), cache=CacheService.getScriptCache();
  const key='PP_DAY_S12_'+ppSha256Hex_(sheetName+'|'+dateVisible+'|'+rev).slice(0,40);
  const cached=cache.get(key);
  if(cached){try{return JSON.parse(cached);}catch(_){} }
  const sh=ppSheet_(sheetName), lastRow=sh.getLastRow(), lastCol=sh.getLastColumn();
  if(lastRow<2||lastCol<1)return [];
  const headers=sh.getRange(1,1,1,lastCol).getDisplayValues()[0].map(function(v){return String(v||'').trim();});
  const dateValues=sh.getRange(2,1,lastRow-1,1).getDisplayValues();
  const spans=[];let spanStart=0,spanEnd=0;
  for(let i=0;i<dateValues.length;i++){
    const row=i+2,match=String((dateValues[i]||[])[0]||'').trim()===dateVisible;
    if(match){if(!spanStart){spanStart=row;spanEnd=row;}else if(row===spanEnd+1){spanEnd=row;}else{spans.push([spanStart,spanEnd]);spanStart=row;spanEnd=row;}}
  }
  if(spanStart)spans.push([spanStart,spanEnd]);
  const out=[];
  spans.forEach(function(span){
    const values=sh.getRange(span[0],1,span[1]-span[0]+1,lastCol).getDisplayValues();
    values.forEach(function(r){
      if(!r.some(function(v){return String(v||'').trim()!=='';}))return;
      const o={};headers.forEach(function(h,i){if(h)o[h]=String(r[i]==null?'':r[i]).trim();});out.push(o);
    });
  });
  const raw=JSON.stringify(out);if(raw.length<95000)cache.put(key,raw,90);
  return out;
}

function ppSessionMap_(dateVisible) {
  const rev=ppRevision_(), cache=CacheService.getScriptCache(), key='PP_SESS_S12_'+dateVisible+'_'+rev;
  const cached=cache.get(key);
  if(cached){try{return JSON.parse(cached);}catch(_){} }
  const out={};
  ppRowsForDateS12_(PP.RA,dateVisible).filter(function(r){return r['Mã nhân viên'];}).forEach(function(r){
    const mnv=r['Mã nhân viên'], action=ppFold_(r['App action'] || r['Loại thao tác']); let ss=out[mnv];
    if(action==='ENTER' || action==='VAO') {
      if(!ss) out[mnv]=ss={id:dateVisible+'|'+mnv,business_date:ppBusinessIso_(),mnv:mnv,employee_snapshot:ppEmployeeFromRa_(r),shift:r['Ca']||'',work_choice:ppWorkCode_(r['Vị trí trong ca']),pda_serial:r['Seri PDA']||null,user_pick:r['User Pick']||null,pack_table:r['Bàn Pack']||null,user_pack:r['User Pack']||null,state:'ACTIVE',enter_at:ppIsoFromVisible_(r['Thời gian cập nhật']),exit_at:null,entered_by:r['Người cập nhật']||'',exited_by:null};
    } else if((action==='RESOURCE'||action==='DOI TAI NGUYEN'||action==='CAP NHAT') && ss && ss.state==='ACTIVE') {
      ss.work_choice=ppWorkCode_(r['Vị trí trong ca']);ss.pda_serial=r['Seri PDA']||null;ss.user_pick=r['User Pick']||null;ss.pack_table=r['Bàn Pack']||null;ss.user_pack=r['User Pack']||null;
    } else if((action==='EXIT'||action==='RA') && ss && ss.state==='ACTIVE') {
      ss.work_choice=ppWorkCode_(r['Vị trí trong ca']);ss.pda_serial=r['Seri PDA']||null;ss.user_pick=r['User Pick']||null;ss.pack_table=r['Bàn Pack']||null;ss.user_pack=r['User Pack']||null;ss.state='ENDED';ss.exit_at=ppIsoFromVisible_(r['Thời gian cập nhật']);ss.exited_by=r['Người cập nhật']||'';
    }
  });
  const raw=JSON.stringify(out);if(raw.length<95000)cache.put(key,raw,120);
  return out;
}

function ppDeductAllowed_(mainPosition,laborType){
  const a=ppFold_(mainPosition||''), b=ppFold_(laborType||'');
  const fixed=function(v){return v.indexOf('KEO HANG')>=0 || v.indexOf('TO TRUONG')>=0;};
  return !fixed(a) && !fixed(b);
}

function ppLaborStart_(auth,body) {
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
  ppSheet_(PP.LABOR).appendRow([ppBusinessVisible_(),ss.shift,mnv,e.full_name,e.phone,e.supplier,e.department,e.site,e.warehouse,e.main_position,ppWorkLabel_(ss.work_choice),type,ppNowVisible_(),'',marker,'Đang làm',note,auth.login_id,ppNowVisible_(),eventId,'',ppRevision_()+1,deduct?'Có':'Không']);
  const rev=ppBumpRevision_();
  return {ok:true,result:{event_id:eventId,revision:rev,deduct_staff:deduct},projection:'DIRECT_GSHEET'};
}

function ppReportRows_(){return ['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Kéo hàng','5S','Picker','Packer','Phúc Long'];}
function ppReportSupplierOrder_(){return ['IH','NLV','VW','MP','MGL','HGP','HAD'];}
function ppLaborTypeS12_(r){return String(r['Loại công nhật']||r['Thông tin công nhật']||'').trim();}

function ppReportPositionS12_(ss,e) {
  const p=ppFold_(e.main_position||''), d=ppFold_(e.department||''), work=String(ss.work_choice||'');
  if(p==='TRUONG NHOM')return 'Trưởng nhóm';
  if(p==='CHUYEN VIEN')return 'Chuyên viên';
  if(p==='TO TRUONG')return 'Tổ trưởng';
  if(p.indexOf('DIEU PHOI')>=0){
    if(p.indexOf('PACK')>=0||d.indexOf('PICK PACK')>=0)return 'Điều phối khu pack';
    if(p.indexOf('CHO XUAT')>=0||d.indexOf('GIAO VAN')>=0||d.indexOf('OUTBOUND')>=0)return 'Điều phối khu chờ xuất';
    return '';
  }
  if(p==='KEO HANG')return 'Kéo hàng';
  if(p==='5S')return '5S';
  if(p.indexOf('PHUC LONG')>=0)return 'Phúc Long';
  if(work==='PICK')return 'Picker';
  if(work==='PACK')return 'Packer';
  if(p==='PICK'||p==='PICKER')return 'Picker';
  if(p==='PACK'||p==='PACKER')return 'Packer';
  return '';
}

function ppReportColumnsS12_(sessions) {
  const seen={};
  sessions.forEach(function(ss){const e=ppLookupStaff_(ss.mnv)||ss.employee_snapshot||{},c=ppSupplierCode_(e.supplier);if(c)seen[c]=true;});
  return ppReportSupplierOrder_().filter(function(c){return !!seen[c];});
}

function ppReportMatrixS12_(sessions,columns) {
  const rows=ppReportRows_(), matrix={};
  rows.forEach(function(p){matrix[p]={};columns.forEach(function(c){matrix[p][c]=0;});});
  sessions.forEach(function(ss){
    const e=ppLookupStaff_(ss.mnv)||ss.employee_snapshot||{},pos=ppReportPositionS12_(ss,e),sup=ppSupplierCode_(e.supplier);
    if(pos&&sup&&matrix[pos]&&columns.indexOf(sup)>=0)matrix[pos][sup]++;
  });
  const outRows=rows.map(function(p){const counts={};columns.forEach(function(c){counts[c]=matrix[p][c]||0;});return {position:p,counts:counts,total:columns.reduce(function(n,c){return n+(counts[c]||0);},0)};});
  const totals={};columns.forEach(function(c){totals[c]=outRows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});
  return {columns:columns,rows:outRows,totals:totals,total:columns.reduce(function(n,c){return n+(totals[c]||0);},0)};
}

function ppTenureForWorkS12_(sessions,columns,work,deducted) {
  const data={'Nhân sự mới':{},'Nhân sự cũ':{}};columns.forEach(function(c){data['Nhân sự mới'][c]=0;data['Nhân sự cũ'][c]=0;});
  sessions.forEach(function(ss){
    if(String(ss.work_choice||'')!==work||deducted[ss.mnv])return;
    const e=ppLookupStaff_(ss.mnv)||ss.employee_snapshot||{},sup=ppSupplierCode_(e.supplier);if(!sup||columns.indexOf(sup)<0)return;
    const label=ppTenureDays_(e.start_date)<=30?'Nhân sự mới':'Nhân sự cũ';data[label][sup]++;
  });
  const rows=['Nhân sự mới','Nhân sự cũ'].map(function(label){const counts={};columns.forEach(function(c){counts[c]=data[label][c]||0;});return {label:label,counts:counts,total:columns.reduce(function(n,c){return n+(counts[c]||0);},0)};});
  const totals={};columns.forEach(function(c){totals[c]=rows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});
  return {columns:columns,rows:rows,totals:totals,total:rows.reduce(function(n,r){return n+r.total;},0)};
}

function ppSupportS12_(sessions,laborRows,allowed,columns) {
  const byMnv={},deducted={},rowsByType={},seen={};sessions.forEach(function(ss){byMnv[ss.mnv]=ss;});
  laborRows.forEach(function(r){
    if(allowed.indexOf(String(r['Ca']||''))<0||ppFold_(r['Khấu trừ nhân sự'])!=='CO')return;
    const mnv=String(r['Mã nhân viên']||'').trim(),ss=byMnv[mnv];if(!mnv||!ss)return;
    const e=ppLookupStaff_(mnv)||ss.employee_snapshot||{},type=ppLaborTypeS12_(r)||'Khác';if(!ppDeductAllowed_(e.main_position||'',type))return;
    const dedupe=type+'|'+mnv;if(seen[dedupe])return;seen[dedupe]=true;deducted[mnv]=true;
    const sup=ppSupplierCode_(e.supplier);if(!sup||columns.indexOf(sup)<0)return;
    if(!rowsByType[type]){rowsByType[type]={label:type,counts:{},total:0};columns.forEach(function(c){rowsByType[type].counts[c]=0;});}
    rowsByType[type].counts[sup]=(rowsByType[type].counts[sup]||0)+1;rowsByType[type].total++;
  });
  const rows=Object.keys(rowsByType).sort().map(function(k){return rowsByType[k];}),totals={};columns.forEach(function(c){totals[c]=rows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});
  return {deducted:deducted,matrix:{columns:columns,rows:rows,totals:totals,total:rows.reduce(function(n,r){return n+r.total;},0),unique_staff:Object.keys(deducted).length}};
}

function ppRemainingFromTenureS12_(picker,packer) {
  function one(t){const rows=t.rows||[],n=(rows[0]&&rows[0].total)||0,o=(rows[1]&&rows[1].total)||0;return {new:n,old:o,total:n+o};}
  return {picker:one(picker),packer:one(packer)};
}

function ppReportPeriodV42_(sessions,laborRows,allowed,label){
  const items=sessions.filter(function(ss){return allowed.indexOf(ss.shift)>=0;}),columns=ppReportColumnsS12_(items);
  const supportData=ppSupportS12_(items,laborRows,allowed,columns),deducted=supportData.deducted;
  const picker=ppTenureForWorkS12_(items,columns,'PICK',deducted),packer=ppTenureForWorkS12_(items,columns,'PACK',deducted);
  return {label:label,manpower:ppReportMatrixS12_(items,columns),picker_tenure:picker,packer_tenure:packer,support:supportData.matrix,remaining:ppRemainingFromTenureS12_(picker,packer),session_total:items.length};
}

function ppReportDaily_() {
  const date=ppBusinessVisible_(),rev=ppRevision_(),cache=CacheService.getScriptCache(),key='PP_REPORT_S12_'+date+'_'+rev,cached=cache.get(key);
  if(cached){try{return JSON.parse(cached);}catch(_){} }
  const sm=ppSessionMap_(date),sessions=Object.keys(sm).map(function(k){return sm[k];}),labor=ppRowsForDateS12_(PP.LABOR,date);
  const out={ok:true,business_date:ppBusinessIso_(),reports:{
    ca1_hc:ppReportPeriodV42_(sessions,labor,['Ca 1','Ca HC'],'Ca 1 + Ca HC'),
    ca2:ppReportPeriodV42_(sessions,labor,['Ca 2'],'Ca 2'),
    all:ppReportPeriodV42_(sessions,labor,['Ca 1','Ca HC','Ca 2'],'Cả ngày')
  }};
  const raw=JSON.stringify(out);if(raw.length<95000)cache.put(key,raw,90);return out;
}

'''

path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print("S12 GAS current-day report patch applied")

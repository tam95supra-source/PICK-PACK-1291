from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing marker: {label}")
    return text.replace(old, new, 1)


# FullBeta: isolate foreground polling and master refresh from scan/business requests.
p = "app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt"
s = read(p)
if "private val syncApi = BetaApiClient()" not in s:
    s = replace_once(
        s,
        "    private val api = BetaApiClient()\n",
        "    private val api = BetaApiClient()\n    private val syncApi = BetaApiClient()\n    private val cacheApi = BetaApiClient()\n",
        "full api fields",
    )
s = s.replace("ForegroundSyncCoordinator(this, api, object :", "ForegroundSyncCoordinator(this, syncApi, object :", 1)
s = s.replace(
    "if (status.masterChanged) refreshMasterCache()",
    "if (status.masterChanged || status.masterRevision != MasterDataCache.revision(this@FullBetaActivity)) refreshMasterCache()",
    1,
)
s = s.replace(
    "                refreshMasterCache()\n                LocalLogManager.uploadAutomaticPending",
    "                if (MasterDataCache.revision(this@FullBetaActivity) == 0L) refreshMasterCache()\n                LocalLogManager.uploadAutomaticPending",
    1,
)
s = s.replace('            else->resourceBox.addView(info("Không cấp tài nguyên cho lựa chọn KHÔNG."))', "            else->Unit")
s = s.replace('private fun refreshStatus() { api.call("sync_status")', 'private fun refreshStatus() { syncApi.call("sync_status")')
s = s.replace('private fun refreshMasterCache(){api.call("master_snapshot")', 'private fun refreshMasterCache(){cacheApi.call("master_snapshot")')
write(p, s)


# Operations: isolate queues, reactive deduction rule, remove redundant guide text, period support table.
p = "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
s = read(p)
if "private val syncApi = BetaApiClient()" not in s:
    s = replace_once(
        s,
        "    private val api = BetaApiClient()\n",
        "    private val api = BetaApiClient()\n    private val syncApi = BetaApiClient()\n    private val cacheApi = BetaApiClient()\n",
        "ops api fields",
    )
s = s.replace("ForegroundSyncCoordinator(this, api, object :", "ForegroundSyncCoordinator(this, syncApi, object :", 1)
s = s.replace(
    "if(status.masterChanged) refreshMasterCache()",
    "if(status.masterChanged || status.masterRevision != MasterDataCache.revision(this@OperationsActivity)) refreshMasterCache()",
    1,
)
s = s.replace('            else->box.addView(info("KHÔNG: trả toàn bộ tài nguyên đang giữ."))', "            else->Unit")
s = s.replace('private fun refreshMasterCache(){api.call("master_snapshot")', 'private fun refreshMasterCache(){cacheApi.call("master_snapshot")')

old = 'val fixed=foldLocal(e.optString("main_position")).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=false;isEnabled=!fixed;setTextColor(if(fixed)muted else ink);textSize=11f};body.addView(deduct,matchWrap());body.addView(gap(6));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("deduct_staff",deduct.isChecked&&!fixed).put("note",note.text.toString()))'
new = 'val fixedMain=foldLocal(e.optString("main_position")).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=false;setTextColor(ink);textSize=11f};fun updateDeduct(){val fixedLabor=foldLocal(typeSpinner.selectedItem?.toString().orEmpty()).let{it.contains("KEO HANG")||it.contains("TO TRUONG")};val blocked=fixedMain||fixedLabor;deduct.isEnabled=!blocked;if(blocked)deduct.isChecked=false;deduct.setTextColor(if(blocked)muted else ink)};typeSpinner.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){updateDeduct()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};updateDeduct();body.addView(deduct,matchWrap());body.addView(gap(6));body.addView(note,matchWrap());body.addView(gap(9));val start=primary("BẮT ĐẦU CÔNG NHẬT",green){};start.setOnClickListener{start.isEnabled=false;start.text="ĐANG GHI...";api.call("labor_start",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("labor_type",typeSpinner.selectedItem.toString()).put("time_marker",markerSpinner.selectedItem.toString()).put("deduct_staff",deduct.isChecked&&deduct.isEnabled).put("note",note.text.toString()))'
if old in s:
    s = s.replace(old, new, 1)
elif "fun updateDeduct()" not in s:
    raise SystemExit("missing labor deduction UI marker")

s = s.replace('supportGrid(rootJson.optJSONObject("support"))', 'supportGrid(p.optJSONObject("support"))')
s = s.replace('val h=TableRow(this);h.addView(cell("Thông tin công nhật",true,true));h.addView(cell("Số lượng",true,true));h.addView(cell("Khấu trừ",true,true));table.addView(h)', 'val h=TableRow(this);h.addView(cell("Thông tin công nhật",true,true));h.addView(cell("Số lượng",true,true));table.addView(h)')
s = s.replace('val q=x.optInt("quantity");val d=x.optInt("deduction");tr.addView(cell(if(q==0)"" else q.toString()));tr.addView(cell(if(d==0)"" else d.toString(),d>0));table.addView(tr)', 'val q=x.optInt("quantity");tr.addView(cell(if(q==0)"" else q.toString()));table.addView(tr)')
write(p, s)


# Apps Script v0.4.2: append final overrides. Later declarations are authoritative in V8.
p = "google-apps-script/PICK_PACK_API.gs"
s = read(p)
marker = "// === v0.4.2 FINAL CACHE / REPORT OVERRIDES ==="
if marker not in s:
    s += r'''

// === v0.4.2 FINAL CACHE / REPORT OVERRIDES ===
function ppSessionMap_(dateVisible) {
  const rev=ppRevision_(), cache=CacheService.getScriptCache(), key='PP_SESS_V42_'+dateVisible+'_'+rev;
  const cached=cache.get(key);
  if(cached){try{return JSON.parse(cached);}catch(_){} }
  const out={};
  ppRaRows_().filter(function(r){return r['Ngày']===dateVisible && r['Mã nhân viên'];}).forEach(function(r){
    const mnv=r['Mã nhân viên'], action=ppFold_(r['App action'] || r['Loại thao tác']); let ss=out[mnv];
    if(action==='ENTER' || action==='VAO') {
      if(!ss) out[mnv]=ss={id:dateVisible+'|'+mnv,business_date:ppBusinessIso_(),mnv:mnv,employee_snapshot:ppEmployeeFromRa_(r),shift:r['Ca']||'',work_choice:ppWorkCode_(r['Vị trí trong ca']),pda_serial:r['Seri PDA']||null,user_pick:r['User Pick']||null,pack_table:r['Bàn Pack']||null,user_pack:r['User Pack']||null,state:'ACTIVE',enter_at:ppIsoFromVisible_(r['Thời gian cập nhật']),exit_at:null,entered_by:r['Người cập nhật']||'',exited_by:null};
    } else if((action==='RESOURCE'||action==='DOI TAI NGUYEN'||action==='CAP NHAT') && ss && ss.state==='ACTIVE') {
      ss.work_choice=ppWorkCode_(r['Vị trí trong ca']); ss.pda_serial=r['Seri PDA']||null; ss.user_pick=r['User Pick']||null; ss.pack_table=r['Bàn Pack']||null; ss.user_pack=r['User Pack']||null;
    } else if((action==='EXIT'||action==='RA') && ss && ss.state==='ACTIVE') {
      ss.work_choice=ppWorkCode_(r['Vị trí trong ca']); ss.pda_serial=r['Seri PDA']||null; ss.user_pick=r['User Pick']||null; ss.pack_table=r['Bàn Pack']||null; ss.user_pack=r['User Pack']||null; ss.state='ENDED'; ss.exit_at=ppIsoFromVisible_(r['Thời gian cập nhật']); ss.exited_by=r['Người cập nhật']||'';
    }
  });
  const raw=JSON.stringify(out); if(raw.length<95000)cache.put(key,raw,180);
  return out;
}

function ppLaborRows_() {
  if(PP_REQUEST_LABOR_ROWS_!==null)return PP_REQUEST_LABOR_ROWS_;
  const rev=ppRevision_(), cache=CacheService.getScriptCache(), key='PP_LABOR_V42_'+rev, cached=cache.get(key);
  if(cached){try{PP_REQUEST_LABOR_ROWS_=JSON.parse(cached);return PP_REQUEST_LABOR_ROWS_;}catch(_){} }
  PP_REQUEST_LABOR_ROWS_=ppObjects_(PP.LABOR);
  const raw=JSON.stringify(PP_REQUEST_LABOR_ROWS_); if(raw.length<95000)cache.put(key,raw,180);
  return PP_REQUEST_LABOR_ROWS_;
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

function ppReportPosition_(e) {
  const p=ppFold_(e.main_position||''), d=ppFold_(e.department||'');
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
  if(p==='PICK'||p==='PICKER')return 'Picker';
  if(p==='PACK'||p==='PACKER')return 'Packer';
  if(p.indexOf('PHUC LONG')>=0)return 'Phúc Long';
  return '';
}

function ppReportRows_(){return ['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Kéo hàng','5S','Picker','Packer','Phúc Long'];}

function ppReportMatrix_(sessions,forcedColumns) {
  const suppliers=['IH','NLV','VW','MP','HGP','MGL','HAD'], matrix={}, rows=ppReportRows_();
  rows.forEach(function(p){matrix[p]={};suppliers.forEach(function(c){matrix[p][c]=0;});});
  sessions.forEach(function(ss){const e=ppLookupStaff_(ss.mnv)||ss.employee_snapshot||{}, pos=ppReportPosition_(e), sup=ppSupplierCode_(e.supplier);if(pos&&sup&&matrix[pos])matrix[pos][sup]++;});
  const totals={};suppliers.forEach(function(c){totals[c]=rows.reduce(function(n,p){return n+(matrix[p][c]||0);},0);});
  const cols=forcedColumns||suppliers.filter(function(c){return totals[c]>0;});
  const outRows=rows.map(function(p){const counts={};cols.forEach(function(c){counts[c]=matrix[p][c]||0;});return {position:p,counts:counts,total:cols.reduce(function(n,c){return n+(counts[c]||0);},0)};});
  const outTotals={};cols.forEach(function(c){outTotals[c]=totals[c]||0;});
  return {columns:cols,rows:outRows,totals:outTotals,total:cols.reduce(function(n,c){return n+(outTotals[c]||0);},0)};
}

function ppTenureMatrix_(sessions,columns){
  const labels=['Nhân sự mới','Nhân sự cũ'], data={'Nhân sự mới':{},'Nhân sự cũ':{}};
  columns.forEach(function(c){data['Nhân sự mới'][c]=0;data['Nhân sự cũ'][c]=0;});
  sessions.forEach(function(ss){const e=ppLookupStaff_(ss.mnv)||ss.employee_snapshot||{},sup=ppSupplierCode_(e.supplier);if(!sup||columns.indexOf(sup)<0)return;const label=ppTenureDays_(e.start_date)<=30?'Nhân sự mới':'Nhân sự cũ';data[label][sup]++;});
  const rows=labels.map(function(label){const counts={};columns.forEach(function(c){counts[c]=data[label][c]||0;});return {label:label,counts:counts,total:columns.reduce(function(n,c){return n+(counts[c]||0);},0)};});
  const totals={};columns.forEach(function(c){totals[c]=rows.reduce(function(n,r){return n+(r.counts[c]||0);},0);});
  return {columns:columns,rows:rows,totals:totals,total:columns.reduce(function(n,c){return n+(totals[c]||0);},0)};
}

function ppReportPeriodV42_(sessions,laborRows,allowed,label){
  const items=sessions.filter(function(ss){return allowed.indexOf(ss.shift)>=0;}), byMnv={};
  items.forEach(function(ss){byMnv[ss.mnv]=ss;});
  const support={}, deducted={};
  laborRows.forEach(function(r){
    if(allowed.indexOf(String(r['Ca']||''))<0 || ppFold_(r['Khấu trừ nhân sự'])!=='CO')return;
    const mnv=String(r['Mã nhân viên']||''), ss=byMnv[mnv]; if(!ss)return;
    const e=ppLookupStaff_(mnv)||ss.employee_snapshot||{}, type=String(r['Thông tin công nhật']||'').trim();
    if(!ppDeductAllowed_(e.main_position||'',type))return;
    if(!support[type])support[type]={}; support[type][mnv]=true; deducted[mnv]=true;
  });
  const base=items.filter(function(ss){return !deducted[ss.mnv];});
  const manpower=ppReportMatrix_(base), tenure=ppTenureMatrix_(base,manpower.columns);
  const supportRows=Object.keys(support).sort().map(function(type){return {labor_type:type,quantity:Object.keys(support[type]).length};});
  return {label:label,manpower:manpower,tenure:tenure,support:{rows:supportRows,total:supportRows.reduce(function(n,r){return n+r.quantity;},0)}};
}

function ppReportDaily_() {
  const sm=ppSessionMap_(ppBusinessVisible_()), sessions=Object.keys(sm).map(function(k){return sm[k];}), labor=ppLaborRows_().filter(function(r){return r['Ngày']===ppBusinessVisible_();});
  return {ok:true,business_date:ppBusinessIso_(),reports:{
    ca1_hc:ppReportPeriodV42_(sessions,labor,['Ca 1','Ca HC'],'Ca 1 + Ca HC'),
    ca2:ppReportPeriodV42_(sessions,labor,['Ca 2'],'Ca 2'),
    all:ppReportPeriodV42_(sessions,labor,['Ca 1','Ca HC','Ca 2'],'Cả ngày')
  }};
}

function ppStaffSearch_(body) {
  const q=ppFold_(body.query||''); if(q.length<1)return {ok:true,items:[]};
  const items=ppMasterSnapshotData_().staff.filter(function(r){return ppFold_((r.mnv||'')+' '+(r.full_name||'')+' '+(r.phone||'')+' '+(r.main_position||'')+' '+(r.supplier||'')).indexOf(q)>=0;}).slice(0,100);
  return {ok:true,items:items};
}
'''
write(p, s)

/* Pick Pack 1291 authoritative API
 * Architecture: Android App <-> Google Apps Script <-> Google Sheets.
 * Google Sheets remains the operational source of truth.
 */

const PP = Object.freeze({
  SHEET_ID: '1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78',
  TZ: 'Asia/Bangkok',
  RA: 'RA - VÀO TRONG CA',
  LABOR: 'CÔNG NHẬT',
  STAFF: 'DANH SÁCH NHÂN SỰ',
  PDA: 'DANH SÁCH PDA',
  PICK: 'DANH SÁCH USER PICK',
  TABLE: 'DANH SÁCH BÀN PACK',
  PACK: 'DANH SÁCH USER PACK',
  CATALOG: 'Danh mục',
  ADMIN: 'Danh sách Admin',
  RELEASES: 'https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30',
  LOG_MANUAL_FOLDER_ID: '1jSPHbj3csKiRNyHtTp87Ed10m2VyFxXU',
  LOG_CRASH_FOLDER_ID: '1tfEaiyhOScH0ucJGSfSDXF1Qq4tkCl0n',
  LOG_ANDROID_FOLDER_ID: '1AN_cEcbbdVO0dory_01hkJhQ1dhlO7Vb'
});

function doGet() {
  return ppJson_({ok:true, service:'pick-pack-gsheet-api', mode:'APP_GSHEET', business_date:ppBusinessIso_()});
}

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const action = String(body.action || '').trim();

    if (action === 'health') return ppJson_(ppHealth_());
    if (action === 'login_challenge') return ppJson_(ppLoginChallenge_(body));
    if (action === 'login') return ppJson_(ppLogin_(body));

    const auth = ppAuthenticate_(body);
    if (!auth) return ppJson_({ok:false,error:'UNAUTHORIZED'}, 401);

    if (action === 'logout') return ppJson_({ok:true});
    if (action === 'password_challenge') return ppJson_(ppPasswordChallenge_(auth));
    if (action === 'change_password') return ppJson_(ppChangePassword_(auth, body));
    if (action === 'employee_context') return ppJson_(ppEmployeeContext_(body));
    if (action === 'master_options') return ppJson_(ppMasterOptions_(body));
    if (action === 'master_snapshot') return ppJson_(ppMasterSnapshot_());
    if (action === 'enter') return ppJson_(ppWithLock_(function(){ return ppEnter_(auth, body); }));
    if (action === 'exit') return ppJson_(ppWithLock_(function(){ return ppExit_(auth, body); }));
    if (action === 'resource_change') return ppJson_(ppWithLock_(function(){ return ppResourceChange_(auth, body); }));
    if (action === 'labor_start') return ppJson_(ppWithLock_(function(){ return ppLaborStart_(auth, body); }));
    if (action === 'labor_finish') return ppJson_(ppWithLock_(function(){ return ppLaborFinish_(auth, body); }));
    if (action === 'list_sessions') return ppJson_(ppListSessions_(body));
    if (action === 'list_labor') return ppJson_(ppListLabor_(auth));
    if (action === 'resource_list') return ppJson_(ppResourceList_());
    if (action === 'report_daily') return ppJson_(ppReportDaily_());
    if (action === 'staff_search') return ppJson_(ppStaffSearch_(body));
    if (action === 'diagnostic_log') return ppJson_(ppDiagnosticLog_(auth, body));
    if (action === 'account_list') return ppJson_(ppAccountList_(auth));
    if (action === 'account_upsert') return ppJson_(ppWithLock_(function(){ return ppAccountUpsert_(auth, body); }));
    if (action === 'account_status') return ppJson_(ppWithLock_(function(){ return ppAccountStatus_(auth, body); }));
    if (action === 'sync_status') return ppJson_(ppSyncStatus_());

    return ppJson_({ok:false,error:'UNKNOWN_ACTION'}, 404);
  } catch (err) {
    console.error(String(err && err.stack || err).slice(0, 3000));
    return ppJson_({ok:false,error:ppCleanError_(err)}, 500);
  }
}

function ppJson_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function ppHealth_() {
  const rows = ppValues_(PP.STAFF);
  return {ok:true,service:'pick-pack-gsheet-api',mode:'APP_GSHEET',api_version:'0.4.2',sheet_read:rows.length>1,business_date:ppBusinessIso_(),revision:ppRevision_(),master_revision:ppMasterRevision_()};
}

function ppSs_() { return SpreadsheetApp.openById(PP.SHEET_ID); }
function ppSheet_(name) {
  const s = ppSs_().getSheetByName(name);
  if (!s) throw new Error('SHEET_NOT_FOUND:' + name);
  return s;
}
function ppValues_(name) { return ppSheet_(name).getDataRange().getDisplayValues(); }
function ppObjects_(name) {
  const values = ppValues_(name);
  if (values.length < 2) return [];
  const h = values[0].map(String);
  return values.slice(1).filter(function(r){ return r.some(function(v){return String(v).trim() !== '';}); }).map(function(r){
    const o = {};
    h.forEach(function(k,i){ if (k) o[String(k).trim()] = String(r[i] == null ? '' : r[i]).trim(); });
    return o;
  });
}
function ppFold_(v) {
  return String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().trim();
}
function ppAvailable_(v) {
  const s = ppFold_(v);
  return s === 'KHA DUNG' || s === 'NGUYEN VEN' || s === 'HOAT DONG';
}
function ppBusinessVisible_() { return Utilities.formatDate(new Date(), PP.TZ, 'dd/MM/yyyy'); }
function ppBusinessIso_() { return Utilities.formatDate(new Date(), PP.TZ, 'yyyy-MM-dd'); }
function ppNowVisible_() { return Utilities.formatDate(new Date(), PP.TZ, 'dd/MM/yyyy HH:mm:ss'); }
function ppNowIso_() { return new Date().toISOString(); }
function ppIsoFromVisible_(v) {
  if (!v) return null;
  try { return Utilities.parseDate(String(v), PP.TZ, 'dd/MM/yyyy HH:mm:ss').toISOString(); } catch (_) { return null; }
}
function ppWithLock_(fn) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) throw new Error('BUSY_RETRY');
  try { return fn(); } finally { lock.releaseLock(); }
}
function ppRevision_() { return Number(PropertiesService.getScriptProperties().getProperty('PP_REVISION') || '1'); }
function ppBumpRevision_() {
  const p = PropertiesService.getScriptProperties();
  const n = Number(p.getProperty('PP_REVISION') || '1') + 1;
  p.setProperty('PP_REVISION', String(n));
  return n;
}

function ppMasterRevision_() {
  return Number(PropertiesService.getScriptProperties().getProperty('PP_MASTER_REVISION') || '1');
}
function ppBumpMasterRevision_() {
  const p=PropertiesService.getScriptProperties();
  const n=Number(p.getProperty('PP_MASTER_REVISION') || '1')+1;
  p.setProperty('PP_MASTER_REVISION',String(n));
  return n;
}
function onEdit(e) {
  try {
    if(!e || !e.range) return;
    const name=e.range.getSheet().getName();
    const masters=[PP.CATALOG,PP.STAFF,PP.PDA,PP.PICK,PP.TABLE,PP.PACK,PP.ADMIN];
    if(masters.indexOf(name)>=0){ ppBumpMasterRevision_(); ppBumpRevision_(); }
    else if(name===PP.RA || name===PP.LABOR){ ppBumpRevision_(); }
  } catch(err) { console.error('onEdit '+String(err)); }
}
function ppPackShift_(label,table) {
  const f=ppFold_(label);
  if(f.indexOf('CA 1-')===0) return 'Ca 1';
  if(f.indexOf('CA 2-')===0) return 'Ca 2';
  if(f.indexOf('HP-')===0 || ppFold_(table)==='HP') return 'Ca HC';
  return '';
}
function ppMasterSnapshotData_() {
  const rev=ppMasterRevision_(), cache=CacheService.getScriptCache(), key='PP_MASTER_V4_'+rev;
  const cached=cache.get(key);
  if(cached){ try { return JSON.parse(cached); } catch(_) {} }
  const staff=ppObjects_(PP.STAFF).map(function(r){return {
    mnv:r['Mã nhân viên']||'',full_name:r['Họ và tên']||'',phone:r['Số điện thoại']||'',main_position:r['Vị trí chính']||'',
    supplier:r['Nhà cung cấp']||'',department:r['Bộ phận']||'',site:r['Site']||'',warehouse:r['Kho']||'',start_date:r['Ngày bắt đầu làm việc']||'',note:r['Ghi chú']||''
  };}).filter(function(x){return !!x.mnv;});
  const pdas=ppObjects_(PP.PDA).filter(function(r){return ppAvailable_(r['Tình trạng']);}).map(function(r){return {serial:r['Seri PDA'],last5:r['5 số cuối Seri']||'',status:r['Tình trạng']||''};}).filter(function(x){return !!x.serial;});
  const userPicks=ppObjects_(PP.PICK).filter(function(r){return ppAvailable_(r['Tình trạng']);}).map(function(r){return r['User Pick'];}).filter(Boolean);
  const tables=ppObjects_(PP.TABLE).filter(function(r){return ppAvailable_(r['Tình trạng']);}).map(function(r){return r['Tên bàn pack'];}).filter(Boolean);
  const tableSet=new Set(tables), warnings=[], packs=[], seen={};
  ppObjects_(PP.PACK).filter(function(r){return ppAvailable_(r['Tình trạng']);}).forEach(function(r){
    const table=String(r['Tên bàn pack']||'').trim(), label=String(r['User pack']||'').trim(), userPack=String(r['User Pack']||'').trim();
    if(!table || !userPack) return;
    if(!tableSet.has(table)){ warnings.push('PACK_TABLE_MISSING:'+table+':'+label); return; }
    const shift=ppPackShift_(label,table); if(!shift){ warnings.push('PACK_SHIFT_UNKNOWN:'+table+':'+label); return; }
    const k=shift+'|'+userPack; if(seen[k]){ warnings.push('USER_PACK_DUPLICATE:'+k+':'+seen[k]+':'+table); return; }
    seen[k]=table; packs.push({table:table,label:label,user_pack:userPack,shift:shift});
  });
  const rows=ppObjects_(PP.CATALOG), labor=[], markers=[];
  rows.forEach(function(r){ const a=r['CÔNG NHẬT_Thông tin công nhật'],b=r['CÔNG NHẬT_Mốc thời gian']; if(a&&labor.indexOf(a)<0)labor.push(a);if(b&&markers.indexOf(b)<0)markers.push(b); });
  const out={master_revision:rev,staff:staff,pdas:pdas,user_picks:userPicks,pack_tables:tables,pack_bundles:packs,labor_types:labor,time_markers:markers,config_warnings:warnings};
  const raw=JSON.stringify(out); if(raw.length<95000) cache.put(key,raw,600);
  return out;
}
function ppMasterSnapshot_() { const s=ppMasterSnapshotData_(); return Object.assign({ok:true},s); }
function ppLookupStaff_(mnv) { return ppMasterSnapshotData_().staff.find(function(x){return String(x.mnv)===String(mnv);})||null; }
function ppMasterData_() { const s=ppMasterSnapshotData_(); return {pdas:s.pdas,userPicks:s.user_picks,packs:s.pack_bundles}; }
function ppCatalog_() { const s=ppMasterSnapshotData_(); return {labor_types:s.labor_types,time_markers:s.time_markers}; }

let PP_REQUEST_RA_ROWS_ = null;
let PP_REQUEST_LABOR_ROWS_ = null;
function ppRaRows_() { if(PP_REQUEST_RA_ROWS_!==null)return PP_REQUEST_RA_ROWS_; PP_REQUEST_RA_ROWS_=ppObjects_(PP.RA); return PP_REQUEST_RA_ROWS_; }
function ppSessionMap_(dateVisible) {
  const out = {};
  ppRaRows_().filter(function(r){return r['Ngày']===dateVisible && r['Mã nhân viên'];}).forEach(function(r){
    const mnv=r['Mã nhân viên'], action=ppFold_(r['App action'] || r['Loại thao tác']);
    let s=out[mnv];
    if(action==='ENTER' || action==='VAO') {
      if(!s) {
        s=out[mnv]={id:dateVisible+'|'+mnv,business_date:ppBusinessIso_(),mnv:mnv,employee_snapshot:ppEmployeeFromRa_(r),shift:r['Ca']||'',work_choice:ppWorkCode_(r['Vị trí trong ca']),pda_serial:r['Seri PDA']||null,user_pick:r['User Pick']||null,pack_table:r['Bàn Pack']||null,user_pack:r['User Pack']||null,state:'ACTIVE',enter_at:ppIsoFromVisible_(r['Thời gian cập nhật']),exit_at:null,entered_by:r['Người cập nhật']||'',exited_by:null};
      }
    } else if((action==='RESOURCE' || action==='DOI TAI NGUYEN' || action==='CAP NHAT') && s && s.state==='ACTIVE') {
      s.work_choice=ppWorkCode_(r['Vị trí trong ca']); s.pda_serial=r['Seri PDA']||null; s.user_pick=r['User Pick']||null; s.pack_table=r['Bàn Pack']||null; s.user_pack=r['User Pack']||null;
    } else if((action==='EXIT' || action==='RA') && s && s.state==='ACTIVE') {
      s.work_choice=ppWorkCode_(r['Vị trí trong ca']); s.pda_serial=r['Seri PDA']||null; s.user_pick=r['User Pick']||null; s.pack_table=r['Bàn Pack']||null; s.user_pack=r['User Pack']||null; s.state='ENDED'; s.exit_at=ppIsoFromVisible_(r['Thời gian cập nhật']); s.exited_by=r['Người cập nhật']||'';
    }
  });
  return out;
}
function ppWorkCode_(v) {
  const f=ppFold_(v); return f==='PICK'?'PICK':f==='PACK'?'PACK':'KHÔNG';
}
function ppWorkLabel_(v) { return v==='PICK'?'Pick':v==='PACK'?'Pack':'Không'; }
function ppEmployeeFromRa_(r) {
  return {mnv:r['Mã nhân viên']||'',full_name:r['Họ và tên']||'',phone:r['Số điện thoại']||'',main_position:r['Vị trí chính']||'',supplier:r['Nhà cung cấp']||'',department:r['Bộ phận']||'',site:r['Site']||'',warehouse:r['Kho']||''};
}
function ppEventExists_(eventId) {
  if(!eventId) return false;
  const ra=ppValues_(PP.RA); for(let i=1;i<ra.length;i++){ if(String(ra[i][19]||'')===eventId) return true; }
  const lb=ppValues_(PP.LABOR); for(let i=1;i<lb.length;i++){ if(String(lb[i][19]||'')===eventId || String(lb[i][20]||'')===eventId) return true; }
  return false;
}
function ppConsumption_(dateVisible, excludeMnv) {
  const picks=new Set(), packs=new Set();
  ppRaRows_().filter(function(r){return r['Ngày']===dateVisible && r['Mã nhân viên']!==excludeMnv;}).forEach(function(r){
    if(r['User Pick']) picks.add(r['User Pick']); if(r['User Pack']) packs.add(r['User Pack']);
  });
  return {picks:picks,packs:packs};
}
function ppBusyResources_(excludeMnv) {
  const sessions=ppSessionMap_(ppBusinessVisible_()), busy=new Set();
  Object.keys(sessions).forEach(function(k){ const s=sessions[k]; if(s.state!=='ACTIVE' || s.mnv===excludeMnv) return; if(s.pda_serial)busy.add('PDA|'+s.pda_serial);if(s.user_pick)busy.add('USER_PICK|'+s.user_pick);if(s.pack_table)busy.add('PACK_TABLE|'+s.pack_table);if(s.user_pack)busy.add('USER_PACK|'+s.user_pack); });
  return busy;
}

function ppEmployeeContext_(body) {
  const mnv=String(body.mnv||'').trim(); if(!mnv)return {ok:false,error:'MNV_REQUIRED'};
  const staff=ppLookupStaff_(mnv); if(!staff)return {ok:false,error:'EMPLOYEE_NOT_FOUND'};
  const session=ppSessionMap_(ppBusinessVisible_())[mnv]||null;
  const state=!session?'NOT_ENTERED':session.state==='ACTIVE'?'ACTIVE':'ENDED';
  const options=state==='NOT_ENTERED'?ppMasterOptions_({mnv:mnv}):null;
  return {ok:true,business_date:ppBusinessIso_(),employee:staff,state:state,session:session,active_labor:ppActiveLabor_(mnv),options:options};
}
function ppMasterOptions_(body) {
  const mnv=String(body.mnv||'').trim(), masters=ppMasterData_(), busy=ppBusyResources_(mnv), used=ppConsumption_(ppBusinessVisible_(),mnv), sessions=ppSessionMap_(ppBusinessVisible_());
  const catalog=ppCatalog_();
  return {ok:true,business_date:ppBusinessIso_(),master_revision:ppMasterRevision_(),
    pdas:masters.pdas.filter(function(x){return !busy.has('PDA|'+x.serial);}),
    user_picks:masters.userPicks.filter(function(x){return !busy.has('USER_PICK|'+x) && !used.picks.has(x);}),
    pack_tables:masters.packs.filter(function(x){return !busy.has('PACK_TABLE|'+x.table) && !busy.has('USER_PACK|'+x.user_pack) && !used.packs.has(x.user_pack);}),
    current:sessions[mnv]||null,labor_types:catalog.labor_types,time_markers:catalog.time_markers,config_warnings:ppMasterSnapshotData_().config_warnings};
}

function ppValidateResources_(mnv, choice, body, shift) {
  const masters=ppMasterData_(), busy=ppBusyResources_(mnv), used=ppConsumption_(ppBusinessVisible_(),mnv);
  let pda=null,userPick=null,packTable=null,userPack=null;
  if(choice==='PICK') {
    pda=String(body.pda_serial||'').trim()||null; userPick=String(body.user_pick||'').trim()||null;
    if(!pda || !masters.pdas.some(function(x){return x.serial===pda;})) throw new Error('PDA_INVALID');
    if(!userPick) throw new Error('USER_PICK_REQUIRED');
    if(busy.has('PDA|'+pda)) throw new Error('PP_RESOURCE_CONFLICT:PDA');
    if(masters.userPicks.indexOf(userPick)<0) throw new Error('USER_PICK_INVALID');
    if(busy.has('USER_PICK|'+userPick) || used.picks.has(userPick)) throw new Error('PP_USER_PICK_USED_TODAY');
  } else if(choice==='PACK') {
    packTable=String(body.pack_table||'').trim()||null;
    const bundle=masters.packs.find(function(x){return x.table===packTable && x.shift===shift;});
    if(!bundle) throw new Error('PACK_BUNDLE_INVALID:'+String(shift||''));
    userPack=bundle.user_pack;
    if(busy.has('PACK_TABLE|'+packTable) || busy.has('USER_PACK|'+userPack)) throw new Error('PP_RESOURCE_CONFLICT:PACK');
    if(used.packs.has(userPack)) throw new Error('PP_USER_PACK_USED_TODAY');
  }
  return {pda:pda,userPick:userPick,packTable:packTable,userPack:userPack};
}
function ppAppendRa_(staff, shift, choice, res, actionLabel, appAction, eventId, actor, note) {
  const sh=ppSheet_(PP.RA); ppEnsureOperationalHeaders_();
  sh.appendRow([ppBusinessVisible_(),shift,staff.mnv,staff.full_name,staff.phone,staff.supplier,staff.department,staff.site,staff.warehouse,staff.main_position,ppWorkLabel_(choice),res.pda||'',res.userPick||'',res.packTable||'',res.userPack||'',actionLabel,note||'PUBLIC BETA',actor,ppNowVisible_(),eventId,appAction,ppRevision_()+1]);
  return ppBumpRevision_();
}
function ppEnter_(auth,body) {
  const mnv=String(body.mnv||'').trim(), eventId=String(body.event_id||'').trim(), shift=String(body.shift||'').trim(), choice=String(body.work_choice||'').trim().toUpperCase();
  if(!mnv||!eventId||['Ca 1','Ca 2','Ca HC'].indexOf(shift)<0||['PICK','PACK','KHÔNG'].indexOf(choice)<0)return {ok:false,error:'ENTER_FIELDS_INVALID'};
  if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const staff=ppLookupStaff_(mnv); if(!staff)return {ok:false,error:'EMPLOYEE_NOT_FOUND'};
  const old=ppSessionMap_(ppBusinessVisible_())[mnv]; if(old && old.state==='ACTIVE')return {ok:false,error:'PP_SESSION_ALREADY_ACTIVE'}; if(old && old.state==='ENDED')return {ok:false,error:'PP_SESSION_ALREADY_ENDED'};
  const res=ppValidateResources_(mnv,choice,body,shift); const rev=ppAppendRa_(staff,shift,choice,res,'VÀO','ENTER',eventId,auth.login_id,'PUBLIC BETA');
  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};
}
function ppExit_(auth,body) {
  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(); if(!mnv||!eventId)return {ok:false,error:'EXIT_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const s=ppSessionMap_(ppBusinessVisible_())[mnv]; if(!s)return {ok:false,error:'PP_SESSION_NOT_ENTERED'}; if(s.state!=='ACTIVE')return {ok:false,error:'PP_SESSION_ALREADY_ENDED'};
  const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const res={pda:s.pda_serial,userPick:s.user_pick,packTable:s.pack_table,userPack:s.user_pack}; const rev=ppAppendRa_(staff,s.shift,s.work_choice,res,'RA','EXIT',eventId,auth.login_id,'PUBLIC BETA');
  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};
}
function ppResourceChange_(auth,body) {
  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(),choice=String(body.work_choice||'').trim().toUpperCase(); if(!mnv||!eventId||['PICK','PACK','KHÔNG'].indexOf(choice)<0)return {ok:false,error:'RESOURCE_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const s=ppSessionMap_(ppBusinessVisible_())[mnv]; if(!s||s.state!=='ACTIVE')return {ok:false,error:'PP_SESSION_NOT_ENTERED'};
  const res=ppValidateResources_(mnv,choice,body,s.shift); const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const rev=ppAppendRa_(staff,s.shift,choice,res,'ĐỔI TÀI NGUYÊN','RESOURCE',eventId,auth.login_id,'ĐỔI TÀI NGUYÊN');
  return {ok:true,result:{event_id:eventId,revision:rev}};
}

function ppLaborRows_() { if(PP_REQUEST_LABOR_ROWS_!==null)return PP_REQUEST_LABOR_ROWS_; PP_REQUEST_LABOR_ROWS_=ppObjects_(PP.LABOR); return PP_REQUEST_LABOR_ROWS_; }
function ppLaborState_(r) { return ppFold_(r['Trạng thái'])==='DANG LAM'?'ACTIVE':'COMPLETED'; }
function ppLaborObj_(r) {
  return {mnv:r['Mã nhân viên']||'',business_date:ppBusinessIso_(),labor_type:r['Thông tin công nhật']||'',start_at:ppIsoFromVisible_(r['Thời gian bắt đầu']),end_at:ppIsoFromVisible_(r['Thời gian kết thúc']),time_marker:r['Mốc thời gian']||'',state:ppLaborState_(r),note:r['Ghi chú']||'',deduct_staff:ppFold_(r['Khấu trừ nhân sự'])==='CO',updated_at:ppIsoFromVisible_(r['Thời gian cập nhật'])};
}
function ppActiveLabor_(mnv) {
  const rows=ppLaborRows_().filter(function(r){return r['Ngày']===ppBusinessVisible_() && r['Mã nhân viên']===mnv && ppLaborState_(r)==='ACTIVE';});
  return rows.length?ppLaborObj_(rows[rows.length-1]):null;
}
function ppLaborStart_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(),type=String(body.labor_type||'').trim(),marker=String(body.time_marker||'Trong ngày').trim(),note=String(body.note||'').trim(); let deduct=body.deduct_staff===true||ppFold_(body.deduct_staff)==='CO'; if(!mnv||!eventId||!type)return {ok:false,error:'LABOR_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const s=ppSessionMap_(ppBusinessVisible_())[mnv]; if(!s||s.state!=='ACTIVE')return {ok:false,error:'PP_SESSION_NOT_ENTERED'}; if(ppActiveLabor_(mnv))return {ok:false,error:'PP_LABOR_ALREADY_ACTIVE'};
  const catalog=ppCatalog_(); if(catalog.labor_types.length && catalog.labor_types.indexOf(type)<0)return {ok:false,error:'LABOR_TYPE_INVALID'};
  const e=ppLookupStaff_(mnv)||s.employee_snapshot; const fixed=ppFold_(e.main_position).indexOf('KEO HANG')>=0||ppFold_(e.main_position).indexOf('TO TRUONG')>=0; if(fixed)deduct=false; ppEnsureOperationalHeaders_(); ppSheet_(PP.LABOR).appendRow([ppBusinessVisible_(),s.shift,mnv,e.full_name,e.phone,e.supplier,e.department,e.site,e.warehouse,e.main_position,ppWorkLabel_(s.work_choice),type,ppNowVisible_(),'',marker,'Đang làm',note,auth.login_id,ppNowVisible_(),eventId,'',ppRevision_()+1,deduct?'Có':'Không']); const rev=ppBumpRevision_();
  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};
}
function ppLaborFinish_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(),note=String(body.note||'').trim(); if(!mnv||!eventId)return {ok:false,error:'LABOR_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const sh=ppSheet_(PP.LABOR), vals=sh.getDataRange().getDisplayValues(); let row=-1;
  for(let i=vals.length-1;i>=1;i--){if(vals[i][0]===ppBusinessVisible_() && String(vals[i][2])===mnv && ppFold_(vals[i][15])==='DANG LAM'){row=i+1;break;}}
  if(row<0)return {ok:false,error:'PP_LABOR_NOT_ACTIVE'};
  const oldNote=String(sh.getRange(row,17).getDisplayValue()||''); sh.getRange(row,14).setValue(ppNowVisible_()); sh.getRange(row,16).setValue('Hoàn thành'); sh.getRange(row,17).setValue(note || oldNote); sh.getRange(row,18).setValue(auth.login_id); sh.getRange(row,19).setValue(ppNowVisible_()); sh.getRange(row,21).setValue(eventId); sh.getRange(row,22).setValue(ppRevision_()+1); const rev=ppBumpRevision_();
  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};
}

function ppListSessions_(body) {
  const q=ppFold_(body.query||''), state=String(body.state||'').toUpperCase(), map=ppSessionMap_(ppBusinessVisible_());
  let items=Object.keys(map).map(function(k){return map[k];});
  if(state==='ACTIVE'||state==='ENDED')items=items.filter(function(s){return s.state===state;});
  if(q)items=items.filter(function(s){return ppFold_(s.mnv+' '+(s.employee_snapshot.full_name||'')).indexOf(q)>=0;});
  items.sort(function(a,b){return String(b.enter_at||'').localeCompare(String(a.enter_at||''));});
  return {ok:true,items:items.slice(0,300)};
}
function ppListLabor_(auth) { if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'}; const items=ppLaborRows_().filter(function(r){return r['Ngày']===ppBusinessVisible_();}).map(ppLaborObj_).reverse().slice(0,300); return {ok:true,items:items}; }
function ppResourceList_() {
  const map=ppSessionMap_(ppBusinessVisible_()), items=[];
  Object.keys(map).forEach(function(k){const s=map[k]; if(s.state!=='ACTIVE')return; const add=function(t,key){if(key)items.push({resource_type:t,resource_key:key,mnv:s.mnv,session:s});}; add('PDA',s.pda_serial);add('USER_PICK',s.user_pick);add('PACK_TABLE',s.pack_table);add('USER_PACK',s.user_pack);});
  return {ok:true,items:items};
}
function ppSupplierCode_(v) {
  const f=ppFold_(v);
  if(f==='NGUON LUC VIET')return 'NLV'; if(f==='HOA ANH DAO')return 'HAD'; if(f==='VIET WORK')return 'VW'; if(f==='MAN POWER')return 'MP'; if(f==='MEGA LINK')return 'MGL'; if(f==='HA GIA PHAT')return 'HGP'; if(f==='INHOUSE')return 'IH'; return '';
}
function ppReportPosition_(e) {
  const p=ppFold_(e.main_position),d=ppFold_(e.department);
  if(p==='PICK')return 'Picker'; if(p==='PACK')return 'Packer'; if(p==='TRUONG NHOM')return 'Trưởng nhóm'; if(p==='CHUYEN VIEN')return 'Chuyên viên'; if(p==='TO TRUONG')return 'Tổ trưởng'; if(p==='KEO HANG')return 'Kéo hàng'; if(p==='5S')return '5S'; if(p==='PHUC LONG')return 'Phúc Long';
  if(p.indexOf('DIEU PHOI')>=0){if(d.indexOf('PICK PACK')>=0)return 'Điều phối khu pack';if(d.indexOf('GIAO VAN')>=0||d.indexOf('OUTBOUND')>=0)return 'Điều phối khu chờ xuất';return 'Điều phối';}
  return e.main_position||'Khác';
}
function ppTenureDays_(startDate) {
  if(!startDate)return 99999;
  try{const d=Utilities.parseDate(String(startDate),PP.TZ,'dd/MM/yyyy');const now=Utilities.parseDate(ppBusinessVisible_(),PP.TZ,'dd/MM/yyyy');return Math.floor((now.getTime()-d.getTime())/86400000);}catch(_){return 99999;}
}
function ppReportMatrix_(sessions) {
  const supplierOrder=['IH','NLV','VW','MP','HGP','MGL','HAD'];const positionOrder=['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Điều phối','Kéo hàng','5S','Picker','Packer','Phúc Long'];const rows={},totals={};supplierOrder.forEach(function(c){totals[c]=0;});
  sessions.forEach(function(x){const e=ppLookupStaff_(x.mnv)||x.employee_snapshot||{},c=ppSupplierCode_(e.supplier);if(!c)return;const pos=ppReportPosition_(e);if(!rows[pos]){rows[pos]={position:pos,counts:{},total:0};supplierOrder.forEach(function(k){rows[pos].counts[k]=0;});}rows[pos].counts[c]++;rows[pos].total++;totals[c]++;});
  const active=supplierOrder.filter(function(c){return totals[c]>0;});const list=Object.keys(rows).map(function(k){return rows[k];}).filter(function(r){return r.total>0;});list.sort(function(a,b){const ia=positionOrder.indexOf(a.position),ib=positionOrder.indexOf(b.position);return (ia<0?999:ia)-(ib<0?999:ib)||a.position.localeCompare(b.position);});return {columns:active,rows:list,totals:totals,total:list.reduce(function(n,r){return n+r.total;},0)};
}
function ppTenureMatrix_(sessions) {
  const supplierOrder=['IH','NLV','VW','MP','HGP','MGL','HAD'],totals={};supplierOrder.forEach(function(c){totals[c]=0;});const rows=[{label:'Nhân sự mới ≤ 30 ngày',counts:{},total:0},{label:'Nhân sự cũ > 30 ngày',counts:{},total:0}];rows.forEach(function(r){supplierOrder.forEach(function(c){r.counts[c]=0;});});sessions.forEach(function(x){const e=ppLookupStaff_(x.mnv)||x.employee_snapshot||{},c=ppSupplierCode_(e.supplier);if(!c)return;const ix=ppTenureDays_(e.start_date)<=30?0:1;rows[ix].counts[c]++;rows[ix].total++;totals[c]++;});const active=supplierOrder.filter(function(c){return totals[c]>0;});return {columns:active,rows:rows,totals:totals,total:rows[0].total+rows[1].total};
}
function ppReportPeriod_(sessions,mode) {let items=sessions;if(mode==='ca1_hc')items=sessions.filter(function(x){return x.shift==='Ca 1'||x.shift==='Ca HC';});else if(mode==='ca2')items=sessions.filter(function(x){return x.shift==='Ca 2';});return {manpower:ppReportMatrix_(items),tenure:ppTenureMatrix_(items)};}
function ppReportDaily_() {
  const sm=ppSessionMap_(ppBusinessVisible_()),sessions=Object.keys(sm).map(function(k){return sm[k];});const laborRows=ppLaborRows_().filter(function(r){return r['Ngày']===ppBusinessVisible_();});const supportMap={};laborRows.forEach(function(r){const type=r['Thông tin công nhật']||'Khác';if(!supportMap[type])supportMap[type]={labor_type:type,quantity:0,deduction:0};supportMap[type].quantity++;if(ppFold_(r['Khấu trừ nhân sự'])==='CO')supportMap[type].deduction++;});const support=Object.keys(supportMap).map(function(k){return supportMap[k];}).sort(function(a,b){return b.quantity-a.quantity||a.labor_type.localeCompare(b.labor_type);});return {ok:true,business_date:ppBusinessIso_(),report_version:'0.4.2',reports:{ca1_hc:ppReportPeriod_(sessions,'ca1_hc'),ca2:ppReportPeriod_(sessions,'ca2'),all:ppReportPeriod_(sessions,'all')},support:{rows:support,total:support.reduce(function(n,x){return n+x.quantity;},0),deduction_total:support.reduce(function(n,x){return n+x.deduction;},0)}};
}
function ppStaffSearch_(body) {
  const q=ppFold_(body.query||''); if(q.length<2)return {ok:true,items:[]};
  const items=ppObjects_(PP.STAFF).filter(function(r){return ppFold_((r['Mã nhân viên']||'')+' '+(r['Họ và tên']||'')).indexOf(q)>=0;}).slice(0,60).map(function(r){return {mnv:r['Mã nhân viên'],full_name:r['Họ và tên'],main_position:r['Vị trí chính'],supplier:r['Nhà cung cấp'],department:r['Bộ phận'],site:r['Site'],warehouse:r['Kho']};});
  return {ok:true,items:items};
}

function ppAdminRows_() {
  const sh=ppSheet_(PP.ADMIN), vals=sh.getDataRange().getDisplayValues(), out=[];
  for(let i=1;i<vals.length;i++){
    if(!String(vals[i][0]||'').trim())continue;
    out.push({row:i+1,login_id:String(vals[i][0]||'').trim(),verifier:String(vals[i][1]||'').trim(),role:String(vals[i][2]||'USER').trim().toUpperCase(),display_name:String(vals[i][3]||vals[i][0]||'').trim(),position:String(vals[i][4]||'').trim(),status:String(vals[i][8]||'ACTIVE').trim().toUpperCase()||'ACTIVE'});
  }
  return out;
}
function ppAccount_(login) { return ppAdminRows_().find(function(a){return a.login_id===login;})||null; }
function ppIsAdmin_(a){return a && (a.role==='ADMIN'||a.role==='SUPERADMIN');}
function ppIsSuper_(a){return a && a.role==='SUPERADMIN';}
function ppVerifierParts_(v){const p=String(v||'').split('$'); if(p.length!==4||p[0]!=='pbkdf2_sha256')return null; const n=Number(p[1]); if(!n||n<100000||n>1000000)return null; return {iterations:n,salt:p[2],key:p[3]};}
function ppLoginChallenge_(body) {
  const login=String(body.login_id||'').trim(), account=ppAccount_(login), parts=account?ppVerifierParts_(account.verifier):null, fakeSalt=ppB64u_(ppRandom_(16));
  const id=Utilities.getUuid(), challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:login,purpose:'LOGIN',challenge:challenge}),120);
  return {ok:true,challenge_id:id,challenge:challenge,iterations:parts?parts.iterations:120000,salt:parts?parts.salt:fakeSalt};
}
function ppLogin_(body) {
  const login=String(body.login_id||'').trim(), id=String(body.challenge_id||''), proof=String(body.proof||''), c=ppTakeChallenge_(id,'LOGIN',login), a=ppAccount_(login), p=a?ppVerifierParts_(a.verifier):null;
  if(!c||!a||a.status!=='ACTIVE'||!p||!ppVerifyProof_(p.key,c.challenge,proof))return {ok:false,error:'INVALID_CREDENTIALS'};
  const exp=Date.now()+12*60*60*1000, token=ppMakeToken_(a,exp);
  return {ok:true,token:token,expires_at:new Date(exp).toISOString(),account:{login_id:a.login_id,role:a.role,display_name:a.display_name,position:a.position||''}};
}
function ppPasswordChallenge_(auth) {
  const p=ppVerifierParts_(auth.verifier); if(!p)return {ok:false,error:'ACCOUNT_VERIFIER_INVALID'}; const id=Utilities.getUuid(),challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:auth.login_id,purpose:'PASSWORD',challenge:challenge}),120); return {ok:true,challenge_id:id,challenge:challenge,iterations:p.iterations,salt:p.salt};
}
function ppChangePassword_(auth,body) {
  const id=String(body.challenge_id||''),proof=String(body.proof||''),newVerifier=String(body.new_verifier||''),c=ppTakeChallenge_(id,'PASSWORD',auth.login_id),p=ppVerifierParts_(auth.verifier),np=ppVerifierParts_(newVerifier); if(!c||!p||!ppVerifyProof_(p.key,c.challenge,proof))return {ok:false,error:'CURRENT_PASSWORD_INVALID'}; if(!np)return {ok:false,error:'PASSWORD_POLICY'};
  ppSheet_(PP.ADMIN).getRange(auth.row,2).setValue(newVerifier); ppEnsureAdminHeaders_(); ppSheet_(PP.ADMIN).getRange(auth.row,10).setValue(auth.login_id); ppSheet_(PP.ADMIN).getRange(auth.row,11).setValue(ppNowVisible_()); ppBumpRevision_(); ppBumpMasterRevision_(); return {ok:true};
}
function ppAccountList_(auth) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const items=ppAdminRows_().filter(function(x){return ppIsSuper_(auth)||x.role==='USER';}).map(function(x){return {login_id:x.login_id,role:x.role,display_name:x.display_name,status:x.status,failed_attempts:0,locked_until:null};}); return {ok:true,items:items};
}
function ppAccountUpsert_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const login=String(body.login_id||'').trim(),display=String(body.display_name||login).trim(),role=String(body.role||'USER').toUpperCase(),verifier=String(body.password_verifier||'').trim(),position=String(body.position||'').trim(); if(!login||['USER','ADMIN'].indexOf(role)<0)return {ok:false,error:'ACCOUNT_FIELDS_INVALID'}; if(!ppIsSuper_(auth)&&role!=='USER')return {ok:false,error:'FORBIDDEN'};
  const old=ppAccount_(login); if(old&&(old.role==='SUPERADMIN'||(!ppIsSuper_(auth)&&old.role!=='USER')))return {ok:false,error:'FORBIDDEN'}; if(!old&&!ppVerifierParts_(verifier))return {ok:false,error:'PASSWORD_POLICY'}; if(verifier&&!ppVerifierParts_(verifier))return {ok:false,error:'PASSWORD_POLICY'};
  ppEnsureAdminHeaders_(); const sh=ppSheet_(PP.ADMIN);
  if(old){sh.getRange(old.row,1).setValue(login);if(verifier)sh.getRange(old.row,2).setValue(verifier);sh.getRange(old.row,3).setValue(role.toLowerCase());sh.getRange(old.row,4).setValue(display);if(position)sh.getRange(old.row,5).setValue(position);sh.getRange(old.row,9).setValue('ACTIVE');sh.getRange(old.row,10).setValue(auth.login_id);sh.getRange(old.row,11).setValue(ppNowVisible_());}
  else {sh.appendRow([login,verifier,role.toLowerCase(),display,position,'','','','ACTIVE',auth.login_id,ppNowVisible_()]);}
  ppBumpRevision_(); ppBumpMasterRevision_(); return {ok:true};
}
function ppAccountStatus_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'}; const login=String(body.login_id||'').trim(),status=String(body.status||'').toUpperCase(),t=ppAccount_(login); if(!t||['ACTIVE','DISABLED'].indexOf(status)<0)return {ok:false,error:'ACCOUNT_FIELDS_INVALID'}; if(t.role==='SUPERADMIN'||(!ppIsSuper_(auth)&&t.role!=='USER')||login===auth.login_id)return {ok:false,error:'FORBIDDEN'}; ppEnsureAdminHeaders_(); const sh=ppSheet_(PP.ADMIN);sh.getRange(t.row,9).setValue(status);sh.getRange(t.row,10).setValue(auth.login_id);sh.getRange(t.row,11).setValue(ppNowVisible_());ppBumpRevision_();ppBumpMasterRevision_();return {ok:true};
}

function ppAuthenticate_(body) {
  const token=String(body._token||''); const parts=token.split('.'); if(parts.length!==2)return null;
  const secret=ppTokenSecret_(), expected=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(parts[0]).getBytes(),secret)); if(!ppSafeEq_(expected,parts[1]))return null;
  let payload; try{payload=JSON.parse(Utilities.newBlob(ppB64uDecode_(parts[0])).getDataAsString());}catch(_){return null;} if(!payload||Number(payload.e||0)<Date.now())return null;
  const a=ppAccount_(String(payload.l||'')); if(!a||a.status!=='ACTIVE'||a.role!==payload.r||ppSha256Hex_(a.verifier)!==payload.v)return null; return a;
}
function ppMakeToken_(a,exp) {
  const payload=ppB64u_(Utilities.newBlob(JSON.stringify({l:a.login_id,r:a.role,e:exp,v:ppSha256Hex_(a.verifier)})).getBytes()), sig=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(payload).getBytes(),ppTokenSecret_())); return payload+'.'+sig;
}
function ppTokenSecret_() {const p=PropertiesService.getScriptProperties();let v=p.getProperty('PP_TOKEN_SECRET');if(!v){v=ppB64u_(ppRandom_(32));p.setProperty('PP_TOKEN_SECRET',v);}return ppB64uDecode_(v);}
function ppTakeChallenge_(id,purpose,login) {if(!id)return null;const cache=CacheService.getScriptCache(),key='PP_CHAL_'+id,raw=cache.get(key);cache.remove(key);if(!raw)return null;try{const c=JSON.parse(raw);return c.purpose===purpose&&c.login_id===login?c:null;}catch(_){return null;}}
function ppVerifyProof_(keyB64,challenge,proof) {try{const expected=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(challenge).getBytes(),ppB64uDecode_(keyB64)));return ppSafeEq_(expected,proof);}catch(_){return false;}}
function ppRandom_(n){const out=[];for(let i=0;i<n;i++)out.push(Math.floor(Math.random()*256)-128);return out;}
function ppB64u_(bytes){return Utilities.base64EncodeWebSafe(bytes).replace(/=+$/,'');}
function ppB64uDecode_(s){let v=String(s||'');while(v.length%4)v+='=';return Utilities.base64DecodeWebSafe(v);}
function ppSafeEq_(a,b){a=String(a||'');b=String(b||'');if(a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
function ppSha256Hex_(s){return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,Utilities.newBlob(String(s)).getBytes()).map(function(b){const n=b<0?b+256:b;return ('0'+n.toString(16)).slice(-2);}).join('');}

function ppEnsureOperationalHeaders_() {
  const ra=ppSheet_(PP.RA); if(ra.getRange(1,20).getValue()!=='Event ID')ra.getRange(1,20,1,3).setValues([['Event ID','App action','App revision']]);
  const lb=ppSheet_(PP.LABOR); if(lb.getRange(1,20).getValue()!=='Event ID')lb.getRange(1,20,1,3).setValues([['Event ID','Finish Event ID','App revision']]); if(lb.getRange(1,23).getValue()!=='Khấu trừ nhân sự')lb.getRange(1,23).setValue('Khấu trừ nhân sự');
}
function ppEnsureAdminHeaders_(){const sh=ppSheet_(PP.ADMIN);if(sh.getRange(1,9).getValue()!=='Trạng thái tài khoản')sh.getRange(1,9,1,3).setValues([['Trạng thái tài khoản','Người cập nhật','Thời gian cập nhật']]);}
function ppSyncStatus_(){return {ok:true,business_date:ppBusinessIso_(),server_seq:ppRevision_(),master_revision:ppMasterRevision_(),last_event_at:ppNowIso_(),projection_pending:0,mode:'APP_GSHEET'};}
function ppDiagnosticLog_(auth,body) {
  const eventId=String(body.event_id||'').trim(); if(!eventId)return {ok:false,error:'EVENT_ID_REQUIRED'};
  const type=String(body.log_type||'').trim().toUpperCase();
  const map={MANUAL:{id:PP.LOG_MANUAL_FOLDER_ID,prefix:'manual'},CRASH:{id:PP.LOG_CRASH_FOLDER_ID,prefix:'crash'},DAILY:{id:PP.LOG_ANDROID_FOLDER_ID,prefix:'android-daily'}};
  const target=map[type]; if(!target)return {ok:false,error:'LOG_TYPE_INVALID'};
  const raw=JSON.stringify({event_id:eventId,log_type:type,at:ppNowIso_(),login_id:auth.login_id,role:auth.role,channel:body.channel||body._app_channel||'',app_version:body.app_version||body._app_version||'',payload:body.payload||{}});
  if(raw.length>80000)return {ok:false,error:'LOG_TOO_LARGE'};
  DriveApp.getFolderById(target.id).createFile(target.prefix+'-'+Utilities.formatDate(new Date(),PP.TZ,'yyyyMMdd-HHmmss')+'-'+eventId+'.json',raw,MimeType.PLAIN_TEXT);
  return {ok:true,ack_event_id:eventId,log_type:type};
}
function ppCleanError_(err){const m=String(err&&err.message||err||'UNKNOWN');const known=['PP_SESSION_ALREADY_ACTIVE','PP_SESSION_ALREADY_ENDED','PP_SESSION_NOT_ENTERED','PP_RESOURCE_CONFLICT','PP_USER_PICK_USED_TODAY','PP_USER_PACK_USED_TODAY','PP_LABOR_ALREADY_ACTIVE','PP_LABOR_NOT_ACTIVE','PDA_INVALID','PACK_TABLE_INVALID','PACK_BUNDLE_INVALID','USER_PICK_INVALID','USER_PICK_REQUIRED','BUSY_RETRY'];for(let i=0;i<known.length;i++)if(m.indexOf(known[i])>=0)return m.slice(m.indexOf(known[i]),m.indexOf(known[i])+220);return m.slice(0,220)||'SERVER_ERROR';}

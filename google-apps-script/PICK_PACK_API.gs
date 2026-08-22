/* Pick Pack 1291 authoritative API
 * Architecture: Android App <-> Google Apps Script <-> Google Sheets.
 * Google Sheets remains the operational source of truth.
 */

const PP = Object.freeze({
  SHEET_ID: '1E7ZWz-4eMcBliQxDYBVoogIoeSYyiaXGwj0I6mbMm78',
  TZ: 'Asia/Bangkok',
  RA: 'RA - VÀO TRONG CA',
  LABOR: 'CÔNG NHẬT',
  HISTORY: 'LỊCH SỬ NGHIỆP VỤ',
  STAFF: 'DANH SÁCH NHÂN SỰ',
  PDA: 'DANH SÁCH PDA',
  PICK: 'DANH SÁCH USER PICK',
  TABLE: 'DANH SÁCH BÀN PACK',
  PACK: 'DANH SÁCH USER PACK',
  CATALOG: 'Danh mục',
  ADMIN: 'Danh sách Admin',
  RESET_ADMIN_EMAIL: 'tam95.supra@gmail.com',
  OTA_BETA_FOLDER_ID: '1WMXI-8-Z1mbY2v11noYFHe_eoMNiNZXg',
  OTA_STABLE_FOLDER_ID: '1kxTd2rFfWutc2KWDwqgK8WYWDmSygIN4',
  RELEASES: 'https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30',
  LOG_MANUAL_FOLDER_ID: '1jSPHbj3csKiRNyHtTp87Ed10m2VyFxXU',
  LOG_CRASH_FOLDER_ID: '1tfEaiyhOScH0ucJGSfSDXF1Qq4tkCl0n',
  LOG_ANDROID_FOLDER_ID: '1AN_cEcbbdVO0dory_01hkJhQ1dhlO7Vb'
});

function doGet() {
  return ppJson_({ok:true, service:'pick-pack-gsheet-api', mode:'APP_GSHEET', report_engine:'S12_CURRENT_DAY', business_date:ppBusinessIso_()});
}

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const action = String(body.action || '').trim();

    // M2_SERVICE_AUTHORITY_ROUTING
    if (action === 'service_discovery') return ppJson_(ppM2Discovery_(body));
    if (action === 'health') return ppJson_(ppHealth_());
    if (action === 'update_check') return ppJson_(ppUpdateCheck_(body));
    if (action === 'forgot_password') return ppJson_(ppForgotPassword_(body));
    if (action === 'login_challenge') return ppJson_(ppLoginChallenge_(body));
    if (action === 'login') return ppJson_(ppLogin_(body));

    const auth = ppAuthenticate_(body);
    if (!auth) return ppJson_({ok:false,error:'UNAUTHORIZED'}, 401);

    if (action === 'logout') return ppJson_(ppLogout_(auth));
    if (action === 'password_challenge') return ppJson_(ppPasswordChallenge_(auth));
    if (action === 'change_password') return ppJson_(ppChangePassword_(auth, body));
    if (action === 'change_email') return ppJson_(ppWithLock_(function(){ return ppChangeEmail_(auth, body); }));
    if (action === 'employee_context') return ppJson_(ppEmployeeContext_(body));
    if (action === 'master_options') return ppJson_(ppMasterOptions_(body));
    if (action === 'master_snapshot') return ppJson_(ppMasterSnapshot_());
    if (action === 'enter') return ppJson_(ppM2OperationalRoute_(auth, body, 'enter', function(){ return ppWithLock_(function(){ return ppEnter_(auth, body); }); }));
    if (action === 'exit') return ppJson_(ppM2OperationalRoute_(auth, body, 'exit', function(){ return ppWithLock_(function(){ return ppExit_(auth, body); }); }));
    if (action === 'resource_change') return ppJson_(ppM2OperationalRoute_(auth, body, 'resource_change', function(){ return ppWithLock_(function(){ return ppResourceChange_(auth, body); }); }));
    if (action === 'labor_start') return ppJson_(ppM2OperationalRoute_(auth, body, 'labor_start', function(){ return ppWithLock_(function(){ return ppLaborStart_(auth, body); }); }));
    if (action === 'labor_finish') return ppJson_(ppM2OperationalRoute_(auth, body, 'labor_finish', function(){ return ppWithLock_(function(){ return ppLaborFinish_(auth, body); }); }));
    if (action === 'list_sessions') return ppJson_(ppListSessions_(body));
    if (action === 'list_labor') return ppJson_(ppListLabor_(auth));
    if (action === 'resource_list') return ppJson_(ppResourceList_());
    if (action === 'report_daily') return ppJson_(ppReportDaily_());
    if (action === 'history_shared') return ppJson_(ppHistorySharedS13_(auth, body));
    if (action === 'staff_search') return ppJson_(ppStaffSearch_(body));
    if (action === 'staff_upsert') return ppJson_(ppWithLock_(function(){ return ppStaffUpsert_(auth, body); }));
    if (action === 'staff_delete') return ppJson_(ppWithLock_(function(){ return ppStaffDelete_(auth, body); }));
    if (action === 'diagnostic_log') return ppJson_(ppDiagnosticLog_(auth, body));
    if (action === 'account_list') return ppJson_(ppAccountList_(auth));
    if (action === 'account_upsert') return ppJson_(ppWithLock_(function(){ return ppAccountUpsert_(auth, body); }));
    if (action === 'account_status') return ppJson_(ppWithLock_(function(){ return ppAccountStatus_(auth, body); }));
    if (action === 'sync_day') return ppJson_(ppSyncDayS15_(auth, body));
    if (action === 'sync_bootstrap') return ppJson_(ppSyncBootstrapS15_(auth, body));
    // M2_SERVICE_AUTHORITY_CONTROL_ROUTES
    if (action === 'm2_authority_status') return ppJson_(ppM2Discovery_(body));
    if (action === 'm2_reconcile_begin') return ppJson_(ppM2BeginReconcile_(auth, body));
    if (action === 'm2_fallback_flush') return ppJson_(String(auth.role)==='SUPERADMIN'?ppM2FlushFallbackInbox_():{ok:false,error:'SUPERADMIN_REQUIRED'});
    if (action === 'm2_failback_complete') return ppJson_(ppM2CompleteFailback_(auth, body));
    if (action === 'sync_status') return ppJson_(ppSyncStatus_());

    return ppJson_({ok:false,error:'UNKNOWN_ACTION'}, 404);
  } catch (err) {
    console.error(String(err && err.stack || err).slice(0, 3000));
    return ppJson_({ok:false,error:ppCleanError_(err)}, 500);
  }
}

function ppOtaVersionFromName_(name) {
  const m = String(name || '').match(/(\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?)(?=\.apk$)/i);
  return m ? m[1] : '';
}
function ppOtaVersionParts_(value) {
  const m = String(value || '').match(/\d+/g) || [];
  return m.slice(0, 6).map(function(x){ return Number(x) || 0; });
}
function ppOtaCompare_(a, b) {
  const aa=ppOtaVersionParts_(a), bb=ppOtaVersionParts_(b), n=Math.max(aa.length,bb.length);
  for(let i=0;i<n;i++){ const av=aa[i]||0,bv=bb[i]||0; if(av!==bv)return av>bv?1:-1; }
  return 0;
}
function ppOtaSha256_(file) {
  const cache=CacheService.getScriptCache();
  const key='PP_OTA_SHA_'+file.getId()+'_'+file.getLastUpdated().getTime()+'_'+file.getSize();
  const cached=cache.get(key); if(cached)return cached;
  const digest=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,file.getBlob().getBytes());
  const sha=digest.map(function(b){return ('0'+((b+256)%256).toString(16)).slice(-2);}).join('');
  cache.put(key,sha,21600); return sha;
}
// PP_GITHUB_RELEASE_OTA_CANONICAL_V1: metadata is canonical in ops/beta-ota-current.json; APK bytes are GitHub Release assets.
// PP_GITHUB_RELEASE_OTA_CANONICAL_V1: metadata is canonical in ops/beta-ota-current.json; APK bytes are GitHub Release assets.
// PP_GITHUB_RELEASE_OTA_CANONICAL_V1: metadata is canonical in ops/beta-ota-current.json; APK bytes are GitHub Release assets.
function ppUpdateCheck_(body) {
  const channel=ppFold_(body.channel||body._app_channel)==='STABLE'?'STABLE':'BETA';
  const current=String(body.current_version||body._app_version||'').trim();
  if(channel==='STABLE') return {ok:true,source:'GITHUB_RELEASE',channel:'STABLE',available:false,reason:'NO_RELEASE'};
  const version="0.4.2-beta.48", available=ppOtaCompare_(version,current)>0;
  const out={ok:true,source:'GITHUB_RELEASE',channel:'BETA',available:available,version_name:version,version_code:54,size:12995067,published_at:"2026-08-22T05:12:20Z",notes:"User Pack theo bàn hiển thị mapping cả hai ca trong ngày, vẫn ẩn tài nguyên đang được giữ và cho phép phát lại sau khi phiên kết thúc. Lịch sử dùng cửa sổ 7 ngày trượt theo ngày hiện tại, kể cả ngày mới chưa có dữ liệu. Sửa triệt để lỗi đồng bộ BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW và tự gửi lại đúng event cũ. Người dùng đang kết nối lấy đúng phiên App/PDA và Web. Loại bỏ text giải thích nội bộ không cần thiết, thu gọn khoảng cách giao diện khoảng 10%, chuyển tên thiết bị vào mục Ứng dụng, bổ sung thông tin dung lượng nhật ký và cache trên thiết bị, làm nổi bật seri PDA đã chọn, và đổi nhãn thành Không dùng User hy1.outbound.",mandatory:false};
  if(!available)return out;
  out.sha256="cfca4a83b3a69c554afabecae83ff150e9f0b66639360ea013e24bf4b08d996f";
  out.apk_url="https://github.com/tam95supra-source/pick-pack-1291/releases/download/v0.4.2-beta.48-publicbeta/pick-pack-1291-public-beta-0.4.2-beta.48.apk";
  return out;
}

function ppJson_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function ppHealth_() {
  const rows = ppValues_(PP.STAFF);
  return {ok:true,service:'pick-pack-gsheet-api',mode:'APP_GSHEET',api_version:'0.4.2',report_engine:'S12_CURRENT_DAY',history_engine:'S13_SHARED_SESSION',sheet_read:rows.length>1,auth_session_model:'SINGLE_ACTIVE_DEVICE_V1',login_session_lock_model:'S44_LOCK_ISOLATED',business_date:ppBusinessIso_(),revision:ppRevision_(),master_revision:ppMasterRevision_()};
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
  const rev=ppMasterRevision_(), cache=CacheService.getScriptCache(), key='PP_MASTER_V5_'+rev;
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
  const catalogRaw=ppValues_(PP.CATALOG), catalogFields={};
  if(catalogRaw.length){
    const headers=catalogRaw[0].map(function(v){return String(v||'').trim();});
    headers.forEach(function(h,col){
      if(!h)return;
      const values=[];
      for(let i=1;i<catalogRaw.length;i++){
        const v=String((catalogRaw[i]||[])[col]||'').trim();
        if(v && values.indexOf(v)<0) values.push(v);
      }
      catalogFields[h]=values;
    });
  }
  const labor=(catalogFields['CÔNG NHẬT_Thông tin công nhật']||[]).slice();
  const markers=(catalogFields['CÔNG NHẬT_Mốc thời gian']||[]).slice();
  const out={master_revision:rev,staff:staff,pdas:pdas,user_picks:userPicks,pack_tables:tables,pack_bundles:packs,labor_types:labor,time_markers:markers,catalog_fields:catalogFields,config_warnings:warnings};
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

function ppEmployeeContext_(body) {
  const mnv=String(body.mnv||'').trim(); if(!mnv)return {ok:false,error:'MNV_REQUIRED'};
  const staff=ppLookupStaff_(mnv); if(!staff)return {ok:false,error:'EMPLOYEE_NOT_FOUND'};
  const session=ppSessionMap_(ppBusinessVisible_())[mnv]||null;
  const state=!session?'NOT_ENTERED':session.state==='ACTIVE'?'ACTIVE':'ENDED';
  const options=state==='NOT_ENTERED' && body.include_options===true ? ppMasterOptions_({mnv:mnv}) : null;
  const activeLabor=body.include_labor===true ? ppActiveLabor_(mnv) : null;
  return {ok:true,business_date:ppBusinessIso_(),employee:staff,state:state,session:session,active_labor:activeLabor,options:options};
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
    if(busy.has('PDA|'+pda)) throw new Error('PP_RESOURCE_CONFLICT:PDA');
    if(userPick && masters.userPicks.indexOf(userPick)<0) throw new Error('USER_PICK_INVALID');
    if(userPick && (busy.has('USER_PICK|'+userPick) || used.picks.has(userPick))) throw new Error('PP_USER_PICK_USED_TODAY');
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
  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:staff.full_name,shift:shift,event_type:'ENTER',label:'Vào ca',at:ppNowVisible_(),actor:auth.login_id,detail:ppHistoryResourceTextS13_(ppWorkLabel_(choice),res.pda,res.userPick,res.packTable,res.userPack),event_id:eventId,revision:rev});
  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};
}
function ppExit_(auth,body) {
  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(); if(!mnv||!eventId)return {ok:false,error:'EXIT_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const s=ppSessionMap_(ppBusinessVisible_())[mnv]; if(!s)return {ok:false,error:'PP_SESSION_NOT_ENTERED'}; if(s.state!=='ACTIVE')return {ok:false,error:'PP_SESSION_ALREADY_ENDED'};
  const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const res={pda:s.pda_serial,userPick:s.user_pick,packTable:s.pack_table,userPack:s.user_pack}; const rev=ppAppendRa_(staff,s.shift,s.work_choice,res,'RA','EXIT',eventId,auth.login_id,'PUBLIC BETA');
  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:staff.full_name,shift:s.shift,event_type:'EXIT',label:'Ra ca',at:ppNowVisible_(),actor:auth.login_id,detail:ppHistoryResourceTextS13_(ppWorkLabel_(s.work_choice),res.pda,res.userPick,res.packTable,res.userPack),event_id:eventId,revision:rev});
  return {ok:true,result:{event_id:eventId,revision:rev},projection:'DIRECT_GSHEET'};
}
function ppResourceChange_(auth,body) {
  const mnv=String(body.mnv||'').trim(),eventId=String(body.event_id||'').trim(),choice=String(body.work_choice||'').trim().toUpperCase(); if(!mnv||!eventId||['PICK','PACK','KHÔNG'].indexOf(choice)<0)return {ok:false,error:'RESOURCE_FIELDS_INVALID'}; if(ppEventExists_(eventId))return {ok:true,idempotent:true};
  const s=ppSessionMap_(ppBusinessVisible_())[mnv]; if(!s||s.state!=='ACTIVE')return {ok:false,error:'PP_SESSION_NOT_ENTERED'};
  const res=ppValidateResources_(mnv,choice,body,s.shift); const staff=ppLookupStaff_(mnv)||s.employee_snapshot; const before=ppHistoryResourceTextS13_(ppWorkLabel_(s.work_choice),s.pda_serial,s.user_pick,s.pack_table,s.user_pack); const after=ppHistoryResourceTextS13_(ppWorkLabel_(choice),res.pda,res.userPick,res.packTable,res.userPack); const rev=ppAppendRa_(staff,s.shift,choice,res,'ĐỔI TÀI NGUYÊN','RESOURCE',eventId,auth.login_id,'ĐỔI TÀI NGUYÊN');
  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:staff.full_name,shift:s.shift,event_type:'RESOURCE',label:'Đổi / trả tài nguyên',at:ppNowVisible_(),actor:auth.login_id,detail:before+' → '+after,event_id:eventId,revision:rev});
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
  const hist=vals[row-1]||[],histShift=String(hist[1]||''),histName=String(hist[3]||''),histType=String(hist[11]||''),histMarker=String(hist[14]||''),histDeduct=String(hist[22]||''); const oldNote=String(sh.getRange(row,17).getDisplayValue()||''); const at=ppNowVisible_(); sh.getRange(row,14).setValue(at); sh.getRange(row,16).setValue('Hoàn thành'); sh.getRange(row,17).setValue(note || oldNote); sh.getRange(row,18).setValue(auth.login_id); sh.getRange(row,19).setValue(at); sh.getRange(row,21).setValue(eventId); sh.getRange(row,22).setValue(ppRevision_()+1); const rev=ppBumpRevision_();
  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:histName,shift:histShift,event_type:'LABOR_FINISH',label:'Hoàn thành công nhật',at:at,actor:auth.login_id,detail:histType+' • Mốc '+histMarker+' • Khấu trừ '+histDeduct,event_id:eventId,revision:rev});
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
  const supplierOrder=['IH','NLV','VW','MP','HGP','MGL','HAD'];const positionOrder=['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Điều phối','Phúc Long','Kéo hàng','5S','Picker','Packer'];const rows={},totals={};supplierOrder.forEach(function(c){totals[c]=0;});
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
  const rev=ppMasterRevision_(),cache=CacheService.getScriptCache(),key='PP_ADMIN_V3_'+rev,cached=cache.get(key);
  if(cached){try{return JSON.parse(cached);}catch(_){} }
  const sh=ppSheet_(PP.ADMIN), vals=sh.getDataRange().getDisplayValues(), out=[];
  for(let i=1;i<vals.length;i++){
    if(!String(vals[i][0]||'').trim())continue;
    out.push({row:i+1,login_id:String(vals[i][0]||'').trim(),verifier:String(vals[i][1]||'').trim(),role:String(vals[i][2]||'USER').trim().toUpperCase(),display_name:String(vals[i][3]||vals[i][0]||'').trim(),position:String(vals[i][4]||'').trim(),email:String(vals[i][5]||PP.RESET_ADMIN_EMAIL).trim()||PP.RESET_ADMIN_EMAIL,status:String(vals[i][8]||'ACTIVE').trim().toUpperCase()||'ACTIVE'});
  }
  const raw=JSON.stringify(out);if(raw.length<90000)cache.put(key,raw,300);return out;
}
function ppAccount_(login) { return ppAdminRows_().find(function(a){return a.login_id===login;})||null; }
function ppIsAdmin_(a){return a && (a.role==='ADMIN'||a.role==='SUPERADMIN');}
function ppIsSuper_(a){return a && a.role==='SUPERADMIN';}
function ppVerifierParts_(v){const p=String(v||'').split('$'); if(p.length!==4||p[0]!=='pbkdf2_sha256')return null; const n=Number(p[1]); if(!n||n<100000||n>1000000)return null; return {iterations:n,salt:p[2],key:p[3]};}
function ppResetParts_(v){const p=String(v||'').split('$');if(p.length!==4||p[0]!=='reset_sha256')return null;const exp=Number(p[1]);if(!exp)return null;return {algorithm:'reset_sha256',expires_at:exp,iterations:1,salt:p[2],key:p[3]};}
function ppCredentialParts_(v){const p=ppVerifierParts_(v);if(p)return {algorithm:'pbkdf2_sha256',iterations:p.iterations,salt:p.salt,key:p.key};return ppResetParts_(v);}
function ppResetPasswordValue_(){const chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';let out='PP-';const bytes=ppRandom_(12);for(let i=0;i<10;i++){const n=(bytes[i]+256)%256;out+=chars.charAt(n%chars.length);}return out;}
function ppResetKey_(password,salt){return ppB64u_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,Utilities.newBlob('PP_RESET_V1|'+salt+'|'+password).getBytes()));}
function ppForgotPassword_(body){
  const login=String(body.login_id||'').trim(),generic={ok:true,delivery:'ACCOUNT_EMAIL',message:'RESET_REQUEST_ACCEPTED'};
  if(!login)return generic;
  const rateKey='PP_RESET_RATE_'+ppSha256Hex_(login+'|'+ppDeviceId_(body)).slice(0,48),cache=CacheService.getScriptCache();if(cache.get(rateKey))return generic;
  const a=ppAccount_(login);cache.put(rateKey,'1',300);if(!a||a.status!=='ACTIVE')return generic;
  const password=ppResetPasswordValue_(),salt=ppB64u_(ppRandom_(16)),expires=Date.now()+2*60*60*1000,key=ppResetKey_(password,salt),resetVerifier='reset_sha256$'+expires+'$'+salt+'$'+key,sh=ppSheet_(PP.ADMIN),old=a.verifier;
  try{
    sh.getRange(a.row,2).setValue(resetVerifier);ppEnsureAdminHeaders_();sh.getRange(a.row,10).setValue('FORGOT_PASSWORD');sh.getRange(a.row,11).setValue(ppNowVisible_());ppClearActiveSessionForLogin_(a.login_id);ppBumpRevision_();ppBumpMasterRevision_();
    MailApp.sendEmail({to:(a.email||PP.RESET_ADMIN_EMAIL),subject:'[PICK PACK 1291] Mật khẩu mới - '+a.login_id,body:'Tài khoản: '+a.login_id+'\nTên: '+a.display_name+'\nQuyền: '+a.role+'\nMật khẩu mới: '+password+'\nHết hạn kích hoạt: 2 giờ.\n\nMật khẩu sẽ được nâng cấp sang PBKDF2 ngay lần đăng nhập đầu tiên.',htmlBody:'<b>PICK PACK 1291 - Đặt lại mật khẩu</b><br><br>Tài khoản: <b>'+a.login_id+'</b><br>Tên: '+a.display_name+'<br>Quyền: '+a.role+'<br>Mật khẩu mới: <b style="font-size:18px">'+password+'</b><br>Hết hạn kích hoạt: 2 giờ.<br><br>Mật khẩu sẽ được nâng cấp sang PBKDF2 ngay lần đăng nhập đầu tiên.'});
  }catch(err){try{sh.getRange(a.row,2).setValue(old);ppBumpRevision_();ppBumpMasterRevision_();}catch(_){}throw err;}
  return generic;
}
function ppLoginChallenge_(body) {
  const login=String(body.login_id||'').trim(), account=ppAccount_(login), cred=account?ppCredentialParts_(account.verifier):null, usable=cred && (cred.algorithm!=='reset_sha256'||cred.expires_at>Date.now()), fakeSalt=ppB64u_(ppRandom_(16));
  const id=Utilities.getUuid(), challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:login,purpose:'LOGIN',challenge:challenge}),120);
  return {ok:true,challenge_id:id,challenge:challenge,algorithm:usable?cred.algorithm:'pbkdf2_sha256',iterations:usable?cred.iterations:120000,salt:usable?cred.salt:fakeSalt};
}
function ppLogin_(body) {
  const login=String(body.login_id||'').trim(), id=String(body.challenge_id||''), proof=String(body.proof||''), c=ppTakeChallenge_(id,'LOGIN',login);let a=ppAccount_(login),cred=a?ppCredentialParts_(a.verifier):null;
  if(!c||!a||a.status!=='ACTIVE'||!cred||(cred.algorithm==='reset_sha256'&&cred.expires_at<=Date.now())||!ppVerifyProof_(cred.key,c.challenge,proof))return {ok:false,error:'INVALID_CREDENTIALS'};
  if(cred.algorithm==='reset_sha256'){
    const upgrade=String(body.upgrade_verifier||'');if(!ppVerifierParts_(upgrade))return {ok:false,error:'RESET_UPGRADE_REQUIRED'};
    ppSheet_(PP.ADMIN).getRange(a.row,2).setValue(upgrade);ppEnsureAdminHeaders_();ppSheet_(PP.ADMIN).getRange(a.row,10).setValue(a.login_id);ppSheet_(PP.ADMIN).getRange(a.row,11).setValue(ppNowVisible_());ppBumpRevision_();ppBumpMasterRevision_();a=ppAccount_(login);
  }
  const session=ppBindSession_(a.login_id,ppDeviceId_(body)), token=ppMakeToken_(a,session);
  return {ok:true,token:token,account:{login_id:a.login_id,role:a.role,display_name:a.display_name,position:a.position||'',email:a.email||PP.RESET_ADMIN_EMAIL},session:{issued_at:session.issued_at,device_label:String(body._device_label||'').slice(0,120)}};
}
function ppPasswordChallenge_(auth) {
  const p=ppVerifierParts_(auth.verifier); if(!p)return {ok:false,error:'ACCOUNT_VERIFIER_INVALID'}; const id=Utilities.getUuid(),challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:auth.login_id,purpose:'PASSWORD',challenge:challenge}),120); return {ok:true,challenge_id:id,challenge:challenge,iterations:p.iterations,salt:p.salt};
}
function ppChangePassword_(auth,body) {
  const id=String(body.challenge_id||''),proof=String(body.proof||''),newVerifier=String(body.new_verifier||''),c=ppTakeChallenge_(id,'PASSWORD',auth.login_id),p=ppVerifierParts_(auth.verifier),np=ppVerifierParts_(newVerifier); if(!c||!p||!ppVerifyProof_(p.key,c.challenge,proof))return {ok:false,error:'CURRENT_PASSWORD_INVALID'}; if(!np)return {ok:false,error:'PASSWORD_POLICY'};
  ppSheet_(PP.ADMIN).getRange(auth.row,2).setValue(newVerifier); ppEnsureAdminHeaders_(); ppSheet_(PP.ADMIN).getRange(auth.row,10).setValue(auth.login_id); ppSheet_(PP.ADMIN).getRange(auth.row,11).setValue(ppNowVisible_()); ppBumpRevision_(); ppBumpMasterRevision_();
  const fresh=ppAccount_(auth.login_id), session=ppActiveSession_(auth.login_id);
  const token=(fresh&&session&&session.session_id===auth._session_id&&session.device_id===auth._device_id)?ppMakeToken_(fresh,session):'';
  return {ok:true,token:token,account:fresh?{login_id:fresh.login_id,role:fresh.role,display_name:fresh.display_name,position:fresh.position||'',email:fresh.email||PP.RESET_ADMIN_EMAIL}:null};
}
function ppAccountList_(auth) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const items=ppAdminRows_().filter(function(x){return ppIsSuper_(auth)||x.role==='USER';}).map(function(x){return {login_id:x.login_id,role:x.role,display_name:x.display_name,position:x.position||'',email:x.email||PP.RESET_ADMIN_EMAIL,status:x.status,failed_attempts:0,locked_until:null};});return {ok:true,items:items};
}
function ppAccountUpsert_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};
  const login=String(body.login_id||'').trim(),display=String(body.display_name||login).trim(),role=String(body.role||'USER').toUpperCase(),verifier=String(body.password_verifier||'').trim(),position=role.toLowerCase(),email=String(body.email||'').trim()||PP.RESET_ADMIN_EMAIL;
  if(!login||['USER','ADMIN'].indexOf(role)<0||!ppEmailValid_(email))return {ok:false,error:'ACCOUNT_FIELDS_INVALID'};if(!ppIsSuper_(auth)&&role!=='USER')return {ok:false,error:'FORBIDDEN'};
  const old=ppAccount_(login);if(old&&(old.role==='SUPERADMIN'||(!ppIsSuper_(auth)&&old.role!=='USER')))return {ok:false,error:'FORBIDDEN'};if(!old&&!ppVerifierParts_(verifier))return {ok:false,error:'PASSWORD_POLICY'};if(verifier&&!ppVerifierParts_(verifier))return {ok:false,error:'PASSWORD_POLICY'};
  ppEnsureAdminHeaders_();const sh=ppSheet_(PP.ADMIN);
  if(old){sh.getRange(old.row,1).setValue(login);if(verifier)sh.getRange(old.row,2).setValue(verifier);sh.getRange(old.row,3).setValue(role.toLowerCase());sh.getRange(old.row,4).setValue(display);if(position)sh.getRange(old.row,5).setValue(position);sh.getRange(old.row,6).setValue(email);sh.getRange(old.row,9).setValue('ACTIVE');sh.getRange(old.row,10).setValue(auth.login_id);sh.getRange(old.row,11).setValue(ppNowVisible_());}
  else{sh.appendRow([login,verifier,role.toLowerCase(),display,position,email,'','','ACTIVE',auth.login_id,ppNowVisible_()]);}
  ppBumpRevision_();ppBumpMasterRevision_();return {ok:true};
}
function ppAccountStatus_(auth,body) {
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};const login=String(body.login_id||'').trim(),status=String(body.status||'').toUpperCase(),target=ppAccount_(login);if(!target||['ACTIVE','DISABLED'].indexOf(status)<0)return {ok:false,error:'ACCOUNT_FIELDS_INVALID'};if(target.role==='SUPERADMIN'||(!ppIsSuper_(auth)&&target.role!=='USER')||login===auth.login_id)return {ok:false,error:'FORBIDDEN'};ppEnsureAdminHeaders_();const sh=ppSheet_(PP.ADMIN);sh.getRange(target.row,9).setValue(status);sh.getRange(target.row,10).setValue(auth.login_id);sh.getRange(target.row,11).setValue(ppNowVisible_());if(status==='DISABLED')ppClearActiveSessionForLogin_(login);ppBumpRevision_();ppBumpMasterRevision_();return {ok:true};
}
function ppEmailValid_(email){return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email||''))&&String(email||'').length<=180;}
function ppChangeEmail_(auth,body){
  const email=String(body.email||'').trim();if(!ppEmailValid_(email))return {ok:false,error:'EMAIL_INVALID'};ppEnsureAdminHeaders_();const sh=ppSheet_(PP.ADMIN);sh.getRange(auth.row,6).setValue(email);sh.getRange(auth.row,10).setValue(auth.login_id);sh.getRange(auth.row,11).setValue(ppNowVisible_());ppBumpRevision_();ppBumpMasterRevision_();const fresh=ppAccount_(auth.login_id),session=ppActiveSession_(auth.login_id);const token=(fresh&&session&&session.session_id===auth._session_id&&session.device_id===auth._device_id)?ppMakeToken_(fresh,session):'';return {ok:true,token:token,account:fresh?{login_id:fresh.login_id,role:fresh.role,display_name:fresh.display_name,position:fresh.position||'',email:fresh.email||PP.RESET_ADMIN_EMAIL}:null};
}
function ppMasterMutationSeen_(eventId){if(!eventId)return false;return !!PropertiesService.getScriptProperties().getProperty('PP_MASTER_EVT_'+ppSha256Hex_(eventId).slice(0,32));}
function ppMarkMasterMutation_(eventId){PropertiesService.getScriptProperties().setProperty('PP_MASTER_EVT_'+ppSha256Hex_(eventId).slice(0,32),ppNowIso_());}
function ppStaffUpsert_(auth,body){
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};const eventId=String(body.event_id||'').trim(),mnv=String(body.mnv||'').trim(),full=String(body.full_name||'').trim();if(!eventId||!mnv||!full)return {ok:false,error:'STAFF_FIELDS_INVALID'};if(ppMasterMutationSeen_(eventId))return {ok:true,idempotent:true};
  const sh=ppSheet_(PP.STAFF),vals=sh.getDataRange().getDisplayValues();let row=0;for(let i=1;i<vals.length;i++){if(String(vals[i][0]||'').trim()===mnv){row=i+1;break;}}
  const data=[mnv,full,String(body.phone||'').trim(),String(body.main_position||'').trim(),String(body.supplier||'').trim(),String(body.department||'').trim(),String(body.site||'').trim(),String(body.warehouse||'').trim(),String(body.start_date||'').trim(),String(body.note||'').trim(),auth.login_id,ppNowVisible_()];
  if(row){sh.getRange(row,1,1,12).setValues([data]);}else{const target=sh.getLastRow()+1;if(target>2)sh.getRange(target-1,1,1,12).copyTo(sh.getRange(target,1,1,12),SpreadsheetApp.CopyPasteType.PASTE_FORMAT,false);sh.getRange(target,1,1,12).setValues([data]);}
  ppMarkMasterMutation_(eventId);const rev=ppBumpRevision_();const master=ppBumpMasterRevision_();return {ok:true,result:{event_id:eventId,revision:rev,master_revision:master}};
}
function ppStaffDelete_(auth,body){
  if(!ppIsAdmin_(auth))return {ok:false,error:'FORBIDDEN'};const eventId=String(body.event_id||'').trim(),mnv=String(body.mnv||'').trim();if(!eventId||!mnv)return {ok:false,error:'STAFF_FIELDS_INVALID'};if(ppMasterMutationSeen_(eventId))return {ok:true,idempotent:true};const active=ppSessionMap_(ppBusinessVisible_())[mnv];if(active&&active.state==='ACTIVE')return {ok:false,error:'STAFF_ACTIVE_SESSION'};const sh=ppSheet_(PP.STAFF),vals=sh.getDataRange().getDisplayValues();let row=0;for(let i=1;i<vals.length;i++){if(String(vals[i][0]||'').trim()===mnv){row=i+1;break;}}if(!row)return {ok:false,error:'EMPLOYEE_NOT_FOUND'};sh.deleteRow(row);ppMarkMasterMutation_(eventId);const rev=ppBumpRevision_();const master=ppBumpMasterRevision_();return {ok:true,result:{event_id:eventId,revision:rev,master_revision:master}};
}

function ppAuthenticate_(body) {
  const token=String(body._token||''), parts=token.split('.'); if(parts.length!==2)return null;
  const secret=ppTokenSecret_(), expected=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(parts[0]).getBytes(),secret)); if(!ppSafeEq_(expected,parts[1]))return null;
  let payload; try{payload=JSON.parse(Utilities.newBlob(ppB64uDecode_(parts[0])).getDataAsString());}catch(_){return null;}
  const a=payload?ppAccount_(String(payload.l||'')):null; if(!a||a.status!=='ACTIVE'||a.role!==payload.r||ppSha256Hex_(a.verifier)!==payload.v)return null;
  if(payload.s){const active=ppActiveSession_(a.login_id);if(!active||active.session_id!==payload.s||active.device_id!==payload.d)return null;}
  else {if(Number(payload.e||0)<Date.now()||ppActiveSession_(a.login_id))return null;}
  return Object.assign({},a,{_session_id:String(payload.s||''),_device_id:String(payload.d||'')});
}
function ppMakeToken_(a,session) {
  const raw={l:a.login_id,r:a.role,v:ppSha256Hex_(a.verifier),s:session.session_id,d:session.device_id};
  const payload=ppB64u_(Utilities.newBlob(JSON.stringify(raw)).getBytes()),sig=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(payload).getBytes(),ppTokenSecret_()));return payload+'.'+sig;
}
function ppSessionKey_(login){return 'PP_ACTIVE_SESSION_'+ppSha256Hex_(String(login||'')).slice(0,48);}
function ppActiveSession_(login){const raw=PropertiesService.getScriptProperties().getProperty(ppSessionKey_(login));if(!raw)return null;try{return JSON.parse(raw);}catch(_){return null;}}
function ppDeviceId_(body){const direct=String(body._device_id||'').trim().slice(0,180);if(direct)return direct;return 'legacy-'+ppSha256Hex_(String(body._device_label||'unknown')).slice(0,48);}
function ppBindSession_(login,deviceId){/* S44_LOGIN_SESSION_LOCK_ISOLATION: login/session binding must never contend with the global business Sheet lock. Same-device login reuses the active session; a different device replaces it by last-write-wins PDA semantics. */const cur=ppActiveSession_(login);const session={session_id:(cur&&cur.device_id===deviceId&&cur.session_id)?cur.session_id:Utilities.getUuid(),device_id:deviceId,issued_at:ppNowIso_()};PropertiesService.getScriptProperties().setProperty(ppSessionKey_(login),JSON.stringify(session));return session;}
function ppClearActiveSessionForLogin_(login){PropertiesService.getScriptProperties().deleteProperty(ppSessionKey_(login));}
function ppLogout_(auth){const lock=LockService.getScriptLock();lock.waitLock(10000);try{const cur=ppActiveSession_(auth.login_id);if(cur&&cur.session_id===auth._session_id&&cur.device_id===auth._device_id)ppClearActiveSessionForLogin_(auth.login_id);return {ok:true};}finally{lock.releaseLock();}}
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
function ppEnsureAdminHeaders_(){const sh=ppSheet_(PP.ADMIN);if(sh.getRange(1,6).getValue()!=='Mail')sh.getRange(1,6).setValue('Mail');if(sh.getRange(1,9).getValue()!=='Trạng thái tài khoản')sh.getRange(1,9,1,3).setValues([['Trạng thái tài khoản','Người cập nhật','Thời gian cập nhật']]);}
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


// === v0.4.2 S12 CURRENT-DAY CACHE / REPORT OVERRIDES ===
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
  const at=ppNowVisible_();
  ppSheet_(PP.LABOR).appendRow([ppBusinessVisible_(),ss.shift,mnv,e.full_name,e.phone,e.supplier,e.department,e.site,e.warehouse,e.main_position,ppWorkLabel_(ss.work_choice),type,at,'',marker,'Đang làm',note,auth.login_id,at,eventId,'',ppRevision_()+1,deduct?'Có':'Không']);
  const rev=ppBumpRevision_();
  ppHistorySafeAppendS13_({session_id:ppBusinessVisible_()+'|'+mnv,mnv:mnv,full_name:e.full_name,shift:ss.shift,event_type:'LABOR_START',label:'Bắt đầu công nhật',at:at,actor:auth.login_id,detail:type+' • Mốc '+marker+' • Khấu trừ '+(deduct?'Có':'Không'),event_id:eventId,revision:rev});
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

function ppStaffSearch_(body) {
  const q=ppFold_(body.query||''); if(q.length<1)return {ok:true,items:[]};
  const items=ppMasterSnapshotData_().staff.filter(function(r){return ppFold_((r.mnv||'')+' '+(r.full_name||'')+' '+(r.phone||'')+' '+(r.main_position||'')+' '+(r.supplier||'')).indexOf(q)>=0;}).slice(0,100);
  return {ok:true,items:items};
}


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
// === v0.4.2 S17 SQLITE CRASH RECOVERY ===
// Beta15/16 crash on some Android 11 PDA builds while opening the new local SQLite store.
// Keep the full day revision manifest but blank retention_floor so legacy S15 clients skip
// OperationalSyncEngine.reconcile. Beta17 derives the same 45-day floor locally and resumes sync.
function ppSyncStatus_(){const floor=ppRetentionSweepS15_();return {ok:true,business_date:ppBusinessIso_(),server_seq:ppRevision_(),master_revision:ppMasterRevision_(),last_event_at:ppNowIso_(),projection_pending:0,mode:'APP_GSHEET',sync_engine:'S15_LOCAL_FIRST_45D',retention_floor:'',server_retention_floor:floor,retention_epoch:ppRetentionEpochS15_(),day_revisions:ppDayRevisionsS15_(),legacy_sqlite_recovery:true,local_sync_min_version:'0.4.2-beta.17'};}
function ppHealth_(){const rows=ppValues_(PP.STAFF);return {ok:true,service:'pick-pack-gsheet-api',mode:'APP_GSHEET',api_version:'0.4.2',sheet_read:rows.length>1,auth_session_model:'SINGLE_ACTIVE_DEVICE_V1',business_date:ppBusinessIso_(),revision:ppRevision_(),master_revision:ppMasterRevision_(),report_engine:'S12_CURRENT_DAY',history_engine:'S13_SHARED_SESSION',sync_engine:'S15_LOCAL_FIRST_45D',retention_days:45,editable_days:2,recovery_engine:'S17_SQLITE_RECOVERY'};}
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

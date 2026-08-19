import crypto from 'node:crypto';
import WebSocket from 'ws';

const BASE=process.env.SESSION1_BASE_URL||'http://127.0.0.1:8791';
const ADMIN_SECRET='session1-admin-secret';
const GENERATION='session1-test-generation';
const N='2026-08-19',N1='2026-08-18',N2='2026-08-17',N6='2026-08-13',N7='2026-08-12';
let serial=0;
function id(prefix){return `${prefix}-${Date.now()}-${++serial}`;}
function sha(s){return crypto.createHash('sha256').update(s).digest('hex');}
function b64u(buf){return Buffer.from(buf).toString('base64url');}
function assert(x,msg){if(!x)throw new Error(`ASSERT:${msg}`);}
function code(j){return j?.error?.code||j?.code||'';}
async function api(path,{method='GET',token,headers={},body}={}){
  const h={...headers};if(token)h.authorization=`Bearer ${token}`;if(body!==undefined)h['content-type']='application/json';
  const r=await fetch(BASE+path,{method,headers:h,body:body===undefined?undefined:JSON.stringify(body)});let j;const t=await r.text();try{j=t?JSON.parse(t):null}catch{j={raw:t}}return{status:r.status,j,headers:r.headers};
}
async function makeAccount(login,role){
  const key=crypto.createHash('sha256').update(`session1:${login}:${role}`).digest();const verifier=`pbkdf2_sha256$120000$${b64u(Buffer.from(`salt-${login}`))}$${b64u(key)}`;
  let x=await api('/internal/test-account',{method:'POST',headers:{'x-m1-admin-token':ADMIN_SECRET},body:{login_id:login,verifier,role}});assert(x.status===200&&x.j.ok,`create ${role}`);
  x=await api('/v1/auth/challenge',{method:'POST',body:{login_id:login}});assert(x.status===200&&x.j.challenge,`challenge ${role}`);const proof=crypto.createHmac('sha256',key).update(String(x.j.challenge)).digest('base64url');
  x=await api('/v1/auth/login',{method:'POST',body:{login_id:login,challenge_id:x.j.challenge_id,proof,device_id:`dev-${login}`,device_label:'session1-e2e'}});assert(x.status===200&&x.j.token,`login ${role}`);return x.j.token;
}
function mutation({type,entity,idempotency,date=N,base=0,payload={},device='session1-device',source='PDA',epoch=6}){return{event_id:id(type.toLowerCase()),event_type:type,entity_type:type.startsWith('LABOR')?'LABOR_SESSION':type==='M1_SHADOW_PROBE'?'PROBE':'ATTENDANCE_SESSION',entity_id:entity,idempotency_key:idempotency||id('idem'),business_date:date,base_version:base,device_id:device,timestamp:new Date().toISOString(),schema_version:1,authority_epoch:epoch,service_generation:GENERATION,client_source:source,payload};}
async function mutate(token,m){return api('/v1/mutations',{method:'POST',token,body:m});}
async function startImport(token,dataset,fileTag){const s=await api(`/v1/import/schema?dataset=${dataset}`,{token});assert(s.status===200&&s.j.ok,`schema ${dataset}`);const b=await api('/v1/import/batches',{method:'POST',token,body:{dataset,template_version:s.j.template_version,schema_checksum:s.j.schema_checksum,file_sha256:sha(fileTag)}});assert(b.status===201&&b.j.import_batch_id,`start ${dataset}`);return{schema:s.j,batch:b.j.import_batch_id};}
function normalize(headers,row){const o={};for(const h of headers){let v=row[h];if(h==='available')v=[true,1,'1','true','TRUE','Có','CO','ACTIVE','Hoạt động'].includes(v)?1:0;else if(h==='ordinal')v=Math.max(0,Number(v||0));else if(h==='metadata_json'){if(v&&typeof v==='object')v=JSON.stringify(v);else{const s=String(v||'{}');try{JSON.parse(s);v=s}catch{v='{}'}}}else if(typeof v!=='number')v=String(v??'').trim();o[h]=v;}return o;}
async function putChunk(token,batch,schema,rows,no=0){const normalized=rows.map(r=>normalize(schema.headers,r)),checksum=sha(JSON.stringify(normalized));return api(`/v1/import/batches/${batch}/chunks`,{method:'POST',token,body:{chunk_no:no,chunk_checksum:checksum,rows}});}
function wsMessage(ws,predicate,timeout=5000){return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{cleanup();reject(new Error('WS_MESSAGE_TIMEOUT'));},timeout);function cleanup(){clearTimeout(timer);ws.off('message',on);}function on(raw){let j;try{j=JSON.parse(raw.toString())}catch{return}if(predicate(j)){cleanup();resolve(j);}}ws.on('message',on);});}
async function openWs(token,query){const t=await api(`/v1/realtime/ticket?${query}`,{method:'POST',token});assert(t.status===200&&t.j.ticket,'realtime ticket');const url=BASE.replace(/^http/,'ws')+`/v1/realtime?ticket=${encodeURIComponent(t.j.ticket)}`;const ws=new WebSocket(url);await new Promise((resolve,reject)=>{ws.once('open',resolve);ws.once('error',reject);});const ready=await wsMessage(ws,j=>j.type==='REALTIME_READY');assert(ready.protocol==='INVALIDATION_V1','ws ready protocol');return ws;}

async function main(){
  const health=await api('/health');assert(health.status===200&&health.j.ok,'health');
  const caps=await api('/v1/capabilities');assert(caps.j.business_window===7&&caps.j.mutation_batch&&caps.j.fcm_wake&&caps.j.import_engine,'capabilities');
  const user=await makeAccount('e2e-user','USER'),admin=await makeAccount('e2e-admin','ADMIN'),superToken=await makeAccount('e2e-super','SUPERADMIN');

  const st=await api('/v1/sync/status',{token:user});assert(st.status===200&&st.j.business_window.length===7,'7-day sync window');assert(st.j.business_window[0].business_date===N&&st.j.business_window.at(-1).business_date===N6,'business sequence boundaries');assert(!st.j.business_window.some(x=>x.business_date===N7),'N-7 absent');assert(st.j.master_revisions&&Object.hasOwn(st.j.master_revisions,'employees'),'master revisions');

  let m=mutation({type:'ATTENDANCE_ENTER',entity:'sess-u-n',date:N,payload:{mnv:'U001',shift:'CA1',work_choice:'KHONG'}});let r=await mutate(user,m);assert(r.status===201,'USER N attendance enter');
  r=await mutate(user,mutation({type:'LABOR_START',entity:'labor-user-denied',date:N,payload:{mnv:'U001',shift:'CA1',labor_type:'Tăng cường',time_marker:'Bắt đầu'}}));assert(r.status===403&&code(r.j)==='LABOR_ADMIN_REQUIRED','USER labor denied');
  r=await mutate(user,mutation({type:'ATTENDANCE_ENTER',entity:'sess-u-old',date:N2,payload:{mnv:'U001',shift:'CA1',work_choice:'KHONG'}}));assert(r.status===403&&code(r.j)==='BUSINESS_DATE_NOT_N_N_MINUS_1','USER N-2 write denied');

  r=await mutate(admin,mutation({type:'ATTENDANCE_ENTER',entity:'sess-a-n1',date:N1,payload:{mnv:'A001',shift:'CA1',work_choice:'KHONG'}}));assert(r.status===201,'ADMIN N-1 attendance');
  r=await mutate(admin,mutation({type:'LABOR_START',entity:'labor-a-n1',date:N1,payload:{mnv:'A001',shift:'CA1',labor_type:'Tăng cường',time_marker:'Bắt đầu'}}));assert(r.status===201,'ADMIN labor start');
  r=await mutate(admin,mutation({type:'ATTENDANCE_EXIT',entity:'sess-a-n1',date:N1,base:1,payload:{mnv:'A001'}}));assert(r.status===409&&code(r.j)==='OPEN_LABOR_BLOCKS_EXIT','open labor blocks exit');
  r=await mutate(admin,mutation({type:'LABOR_FINISH',entity:'labor-a-n1',date:N1,base:1,payload:{mnv:'A001'}}));assert(r.status===201,'ADMIN labor finish');
  r=await mutate(admin,mutation({type:'ATTENDANCE_EXIT',entity:'sess-a-n1',date:N1,base:1,payload:{mnv:'A001'}}));assert(r.status===201,'ADMIN exit after labor');

  const superN6=mutation({type:'ATTENDANCE_ENTER',entity:'sess-s-n6',date:N6,payload:{mnv:'S001',shift:'CA1',work_choice:'KHONG'}});r=await mutate(superToken,superN6);assert(r.status===201,'SUPERADMIN N-6 PDA write');const replay=await mutate(superToken,superN6);assert(replay.status===200&&replay.j.duplicate===true,'idempotent replay');
  r=await mutate(superToken,mutation({type:'ATTENDANCE_ENTER',entity:'sess-r-n7',date:N7,payload:{mnv:'R001',shift:'CA1',work_choice:'KHONG'}}));assert(r.status===403&&code(r.j)==='BUSINESS_DATE_OUTSIDE_PDA_7_DAY_WINDOW','SUPERADMIN PDA N-7 denied');
  r=await mutate(superToken,mutation({type:'ATTENDANCE_EXIT',entity:'sess-s-n6',date:N6,base:0,payload:{mnv:'S001'}}));assert(r.status===409&&code(r.j)==='STALE_BASE_VERSION','stale base version');

  r=await mutate(superToken,mutation({type:'ATTENDANCE_ENTER',entity:'sess-s-n',date:N,payload:{mnv:'S001',shift:'CA1',work_choice:'PICK',pda_serial:'PDA001'}}));assert(r.status===201,'first PDA lease');
  r=await mutate(superToken,mutation({type:'ATTENDANCE_ENTER',entity:'sess-r-n',date:N,payload:{mnv:'R001',shift:'CA1',work_choice:'PICK',pda_serial:'PDA001'}}));assert(r.status===409&&code(r.j)==='EXCLUSIVE_RESOURCE_CONFLICT','exclusive PDA race');

  const secret='SESSION1_SHOULD_NEVER_PERSIST';const probe=mutation({type:'M1_SHADOW_PROBE',entity:'probe-secret',date:N,payload:{_token:secret,safe:'ok',nested:{password:'drop-me',keep:'yes'}}});r=await mutate(superToken,probe);assert(r.status===201,'probe mutation');const payload=String(r.j.event?.payload_json||'');assert(!payload.includes(secret)&&!payload.includes('drop-me')&&payload.includes('keep'),'mutation secret redaction');

  const batch=await api('/v1/mutations/batch',{method:'POST',token:superToken,body:{events:[mutation({type:'M1_SHADOW_PROBE',entity:'batch-ok',date:N,payload:{x:1}}),mutation({type:'ATTENDANCE_EXIT',entity:'missing',date:N,base:0,payload:{mnv:'NOPE'}})]}});assert(batch.status===200&&batch.j.results.length===2,'batch result count');assert(batch.j.results[0].status==='CONFIRMED'&&['REVIEW_REQUIRED','REJECTED'].includes(batch.j.results[1].status),'batch per-event mapping');

  r=await api('/v1/corrections',{method:'POST',token:superToken,body:{entity_type:'ATTENDANCE_SESSION',entity_id:'hist-old-1',reason:'Session1 historical correction test',patch:{shift:'CA1-CORRECTED'},target_event_id:'seed',idempotency_key:'corr-hist-old-1'}});assert(r.status===201&&r.j.event?.event_type==='HISTORICAL_CORRECTION','historical correction');assert(String(r.j.event.payload_json).includes('before')&&String(r.j.event.payload_json).includes('after')&&String(r.j.event.payload_json).includes('reason'),'correction audit payload');const corrReplay=await api('/v1/corrections',{method:'POST',token:superToken,body:{entity_type:'ATTENDANCE_SESSION',entity_id:'hist-old-1',reason:'Session1 historical correction test',patch:{shift:'CA1-CORRECTED'},idempotency_key:'corr-hist-old-1'}});assert(corrReplay.status===200&&corrReplay.j.duplicate===true,'correction idempotency');
  r=await api(`/v1/bootstrap?business_date=${N7}`,{token:user});assert(r.status===403,'historical read USER denied outside 7');r=await api(`/v1/bootstrap?business_date=${N7}&client_source=WEB`,{token:superToken});assert(r.status===200,'SUPERADMIN WEB historical read');

  r=await api('/v1/import/schema?dataset=employees',{token:user});assert(r.status===403&&code(r.j)==='SUPERADMIN_REQUIRED','import SUPERADMIN only');const bad=await startImport(superToken,'employees','bad-select');const badRow={mnv:'OLD1',full_name:'Historical One',phone:'',main_position:'INVALID_POSITION',supplier:'NCC1',department:'OPS',site:'SITE1',warehouse:'KHO1',start_date:'2026-01-01',note:'bad'};r=await putChunk(superToken,bad.batch,bad.schema,[badRow]);assert(r.status===200,'bad import upload');r=await api(`/v1/import/batches/${bad.batch}/preview`,{method:'POST',token:superToken});assert(r.status===200&&r.j.ok===false&&r.j.summary.rejected===1,'invalid select rejected before commit');

  const imp=await startImport(superToken,'employees','valid-update');assert(Array.isArray(imp.schema.select_values.main_position)&&imp.schema.select_values.main_position.includes('Picker'),'template select values');const goodRow={mnv:'OLD1',full_name:'Historical One',phone:'',main_position:'Picker',supplier:'NCC1',department:'OPS',site:'SITE1',warehouse:'KHO1',start_date:'2026-01-01',note:'IMPORTED_SESSION1'};r=await putChunk(superToken,imp.batch,imp.schema,[goodRow]);assert(r.status===200&&!r.j.duplicate,'first chunk');const resumed=await putChunk(superToken,imp.batch,imp.schema,[goodRow]);assert(resumed.status===200&&resumed.j.duplicate===true,'idempotent chunk resume');r=await api(`/v1/import/batches/${imp.batch}/preview`,{method:'POST',token:superToken});assert(r.status===200&&r.j.state==='VALIDATED'&&r.j.summary.updates===1,'import preview update');
  const masterWs=await openWs(superToken,'scope=master');const masterChangedP=wsMessage(masterWs,j=>j.type==='MASTER_CHANGED'&&j.namespace==='employees');r=await api(`/v1/import/batches/${imp.batch}/commit`,{method:'POST',token:superToken});assert(r.status===200&&r.j.state==='COMMITTED'&&r.j.changed===1,'atomic import commit');const masterChanged=await masterChangedP;assert(masterChanged.revision===r.j.revision,'master WS invalidation revision');masterWs.close();
  r=await api(`/v1/import/batches/${imp.batch}/rollback`,{method:'POST',token:superToken});assert(r.status===200&&r.j.state==='ROLLED_BACK'&&r.j.corrected===1,'import update rollback correction');

  const ins=await startImport(superToken,'employees','insert-row');const newRow={mnv:'X999',full_name:'Inserted',phone:'',main_position:'Picker',supplier:'NCC1',department:'OPS',site:'SITE1',warehouse:'KHO1',start_date:'2026-08-19',note:''};await putChunk(superToken,ins.batch,ins.schema,[newRow]);r=await api(`/v1/import/batches/${ins.batch}/preview`,{method:'POST',token:superToken});assert(r.j.state==='VALIDATED'&&r.j.summary.inserts===1,'insert preview');r=await api(`/v1/import/batches/${ins.batch}/commit`,{method:'POST',token:superToken});assert(r.status===200,'insert commit');r=await api(`/v1/import/batches/${ins.batch}/rollback`,{method:'POST',token:superToken});assert(r.status===409&&code(r.j)==='IMPORT_ROLLBACK_INSERT_REQUIRES_EXPLICIT_CORRECTION','rollback never deletes inserted canonical row');

  const packImp=await startImport(superToken,'pack_table','atomic-conflict');const p1={pack_table:'T-A',shift:'CA1',user_pack:'PACK001',label:'A',status_label:'Hoạt động',available:1},p2={pack_table:'T-B',shift:'CA1',user_pack:'PACK001',label:'B',status_label:'Hoạt động',available:1};await putChunk(superToken,packImp.batch,packImp.schema,[p1,p2]);r=await api(`/v1/import/batches/${packImp.batch}/preview`,{method:'POST',token:superToken});assert(r.status===200&&r.j.state==='VALIDATED','pack conflict reaches commit transaction');r=await api(`/v1/import/batches/${packImp.batch}/commit`,{method:'POST',token:superToken});assert(r.status===409&&code(r.j)==='IMPORT_COMMIT_CONFLICT','atomic import conflict');r=await api('/v1/delta/master?namespace=pack_table&after_revision=0',{token:superToken});assert(r.status===200&&r.j.changed===false&&r.j.to_revision===0,'atomic conflict left zero partial revision/projection');

  const fakeFcm='fake-session1-fcm-token-'+('x'.repeat(80));r=await api('/v1/push/register',{method:'POST',token:superToken,body:{fcm_token:fakeFcm,app_version:'test',channel:'beta'}});assert(r.status===200&&r.j.push==='FCM_WAKE_ONLY','FCM register wake-only');r=await api('/v1/push/revoke',{method:'POST',token:superToken});assert(r.status===200,'FCM revoke');r=await api('/internal/push/flush',{method:'POST',headers:{'x-m1-admin-token':ADMIN_SECRET}});assert(r.status===200&&r.j.configured===false&&r.j.pending>0,'FCM backend safe without credentials');

  const dayWs=await openWs(superToken,`business_date=${N}`);const dayChangedP=wsMessage(dayWs,j=>j.type==='DAY_CHANGED'&&j.business_date===N);r=await mutate(superToken,mutation({type:'M1_SHADOW_PROBE',entity:'ws-day-probe',date:N,payload:{source:'e2e'}}));assert(r.status===201,'WS trigger mutation');const dayChanged=await dayChangedP;assert(dayChanged.authority_seq===r.j.event.authority_seq,'day WS authoritative sequence');dayWs.close();

  const history=await api('/v1/import/history',{token:superToken});assert(history.status===200&&history.j.batches.length>=4,'import history');
  console.log(JSON.stringify({SESSION1_E2E:'PASS',checks:['7-day','roles','labor','idempotency','stale-version','resource-race','batch-reconcile','redaction','historical-correction','import-permission','import-validation','import-resume','import-atomic','import-rollback','ws-day','ws-master','fcm-contract'],authority_seq:dayChanged.authority_seq}));
}
main().catch(e=>{console.error(e.stack||e);process.exit(1);});

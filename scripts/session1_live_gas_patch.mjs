import fs from 'node:fs';
import crypto from 'node:crypto';
const input=JSON.parse(fs.readFileSync('/tmp/gas-live-before.json','utf8'));
const files=input.files||[];
const target=files.find(f=>f.name==='SERVICE_MIGRATION_M2'&&f.type==='SERVER_JS');
if(!target)throw new Error('GAS_M2_SOURCE_MISSING_STOP_OWNER');
let s=target.source||'';const before=crypto.createHash('sha256').update(s).digest('hex');let changed=false;
const sanitizer=`function ppM2SanitizePayload_(value){if(Array.isArray(value))return value.map(ppM2SanitizePayload_);if(value&&typeof value==='object'){const out={};Object.keys(value).forEach(function(k){if(/(^|_)(token|password|verifier|secret|authorization|cookie|oauth)(_|$)/i.test(k))return;out[k]=ppM2SanitizePayload_(value[k]);});return out;}return value;}`;
if(!s.includes('function ppM2SanitizePayload_')){
  const anchor=`function ppM2BridgeActor_(auth,body){return {login_id:String(auth.login_id||auth.login||''),role:String(auth.role||'USER'),display_name:String(auth.display_name||auth.login_id||''),device_id:String((body||{})._device_id||'gas-legacy')};}`;
  if(!s.includes(anchor))throw new Error('GAS_SANITIZER_INSERT_ANCHOR_MISSING_STOP_OWNER');s=s.replace(anchor,anchor+'\n'+sanitizer);changed=true;
}
if(!s.includes('payload:ppM2SanitizePayload_(body)')){if(!s.includes('payload:body'))throw new Error('GAS_BRIDGE_PAYLOAD_ANCHOR_MISSING_STOP_OWNER');s=s.replace('payload:body','payload:ppM2SanitizePayload_(body)');changed=true;}
if(!s.includes('JSON.stringify(ppM2SanitizePayload_(body||{}))')){if(!s.includes('JSON.stringify(body||{})'))throw new Error('GAS_FALLBACK_PAYLOAD_ANCHOR_MISSING_STOP_OWNER');s=s.replace('JSON.stringify(body||{})','JSON.stringify(ppM2SanitizePayload_(body||{}))');changed=true;}
for(const needle of ['function ppM2SanitizePayload_','payload:ppM2SanitizePayload_(body)','JSON.stringify(ppM2SanitizePayload_(body||{}))'])if(!s.includes(needle))throw new Error('GAS_SANITIZER_VERIFY_FAILED:'+needle);
target.source=s;fs.writeFileSync('/tmp/gas-live-patched.json',JSON.stringify({files}));fs.writeFileSync('/tmp/gas-changed',changed?'1':'0');
const after=crypto.createHash('sha256').update(s).digest('hex');console.log('GAS_M2_SOURCE='+JSON.stringify({before_sha256:before,after_sha256:after,changed}));

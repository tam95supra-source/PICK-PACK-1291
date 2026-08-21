#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "google-apps-script/PICK_PACK_API.gs"
s = p.read_text(encoding="utf-8")
marker = "S46_DURABLE_AUTH_CHALLENGE"
if marker in s:
    print("S46 durable auth challenge already applied")
    raise SystemExit(0)

old = """function ppLoginChallenge_(body) {
  const login=String(body.login_id||'').trim(), account=ppAccount_(login), cred=account?ppCredentialParts_(account.verifier):null, usable=cred && (cred.algorithm!=='reset_sha256'||cred.expires_at>Date.now()), fakeSalt=ppB64u_(ppRandom_(16));
  const id=Utilities.getUuid(), challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:login,purpose:'LOGIN',challenge:challenge}),120);
  return {ok:true,challenge_id:id,challenge:challenge,algorithm:usable?cred.algorithm:'pbkdf2_sha256',iterations:usable?cred.iterations:120000,salt:usable?cred.salt:fakeSalt};
}
"""
new = """function ppLoginChallenge_(body) {
  const login=String(body.login_id||'').trim(), account=ppAccount_(login), cred=account?ppCredentialParts_(account.verifier):null, usable=cred && (cred.algorithm!=='reset_sha256'||cred.expires_at>Date.now()), fakeSalt=ppB64u_(ppRandom_(16));
  const id=Utilities.getUuid(), challenge=ppB64u_(ppRandom_(32)); ppPutChallenge_(id,'LOGIN',login,challenge);
  return {ok:true,challenge_id:id,challenge:challenge,algorithm:usable?cred.algorithm:'pbkdf2_sha256',iterations:usable?cred.iterations:120000,salt:usable?cred.salt:fakeSalt};
}
"""
if s.count(old) != 1:
    raise SystemExit(f"S46 login challenge anchor mismatch: {s.count(old)}")
s = s.replace(old, new, 1)

old = """function ppPasswordChallenge_(auth) {
  const p=ppVerifierParts_(auth.verifier); if(!p)return {ok:false,error:'ACCOUNT_VERIFIER_INVALID'}; const id=Utilities.getUuid(),challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:auth.login_id,purpose:'PASSWORD',challenge:challenge}),120); return {ok:true,challenge_id:id,challenge:challenge,iterations:p.iterations,salt:p.salt};
}
"""
new = """function ppPasswordChallenge_(auth) {
  const p=ppVerifierParts_(auth.verifier); if(!p)return {ok:false,error:'ACCOUNT_VERIFIER_INVALID'}; const id=Utilities.getUuid(),challenge=ppB64u_(ppRandom_(32)); ppPutChallenge_(id,'PASSWORD',auth.login_id,challenge); return {ok:true,challenge_id:id,challenge:challenge,iterations:p.iterations,salt:p.salt};
}
"""
if s.count(old) != 1:
    raise SystemExit(f"S46 password challenge anchor mismatch: {s.count(old)}")
s = s.replace(old, new, 1)

old = "function ppTakeChallenge_(id,purpose,login) {if(!id)return null;const cache=CacheService.getScriptCache(),key='PP_CHAL_'+id,raw=cache.get(key);cache.remove(key);if(!raw)return null;try{const c=JSON.parse(raw);return c.purpose===purpose&&c.login_id===login?c:null;}catch(_){return null;}}"
new = """// S46_DURABLE_AUTH_CHALLENGE: authentication correctness must not depend on best-effort CacheService.
function ppChallengeKey_(purpose,login){return 'PP_CHAL_V2_'+String(purpose||'')+'_'+ppSha256Hex_(String(login||'')).slice(0,48);}
function ppPutChallenge_(id,purpose,login,challenge){const key=ppChallengeKey_(purpose,login),value={id:String(id||''),purpose:String(purpose||''),login_id:String(login||''),challenge:String(challenge||''),expires_at:Date.now()+120000};PropertiesService.getScriptProperties().setProperty(key,JSON.stringify(value));}
function ppTakeChallenge_(id,purpose,login) {if(!id)return null;const props=PropertiesService.getScriptProperties(),key=ppChallengeKey_(purpose,login),raw=props.getProperty(key);if(raw){try{const c=JSON.parse(raw),valid=c.id===id&&c.purpose===purpose&&c.login_id===login&&Number(c.expires_at||0)>Date.now();if(c.id===id||Number(c.expires_at||0)<=Date.now())props.deleteProperty(key);if(valid)return c;}catch(_){props.deleteProperty(key);}}const cache=CacheService.getScriptCache(),legacyKey='PP_CHAL_'+id,legacyRaw=cache.get(legacyKey);cache.remove(legacyKey);if(!legacyRaw)return null;try{const c=JSON.parse(legacyRaw);return c.purpose===purpose&&c.login_id===login?c:null;}catch(_){return null;}}"""
if s.count(old) != 1:
    raise SystemExit(f"S46 take challenge anchor mismatch: {s.count(old)}")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("Applied S46 durable GAS auth challenge")

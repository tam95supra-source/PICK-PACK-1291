import type { AuthContext } from "./domain";
import { b64u, b64uDecode, constantTimeEqual, hmacB64u, nowIso, randomB64u, sha256Hex } from "./util";

interface AccountRow { login_id:string; verifier:string; verifier_hash:string; role:"SUPERADMIN"|"ADMIN"|"USER"; display_name:string; position:string; email:string; status:string; }
interface ChallengeRow { challenge_id:string;login_id:string;challenge:string;expires_at:number; }
interface SessionRow { session_id:string;device_id:string; }

function verifierParts(value: string): {iterations:number;salt:string;key:string}|null {
  const p=String(value||"").split("$");
  if(p.length!==4) return null;
  const prefix=p[0], iterRaw=p[1], salt=p[2], key=p[3];
  if(prefix!=="pbkdf2_sha256"||!iterRaw||!salt||!key) return null;
  const n=Number(iterRaw);
  if(!Number.isInteger(n)||n<100000||n>1000000) return null;
  return {iterations:n,salt,key};
}

export async function createChallenge(db: D1Database, loginId: string): Promise<Record<string,unknown>> {
  const account=await db.prepare("SELECT login_id,verifier,status FROM accounts WHERE login_id=?1").bind(loginId).first<{login_id:string;verifier:string;status:string}>();
  const parts=account&&account.status==="ACTIVE"?verifierParts(account.verifier):null;
  const challengeId=crypto.randomUUID(), challenge=randomB64u(32), fakeSalt=randomB64u(16), expires=Date.now()+120_000,createdAt=nowIso();
  await db.batch([
    db.prepare("DELETE FROM auth_challenges WHERE expires_at<?1").bind(Date.now()),
    db.prepare("INSERT INTO auth_challenges(challenge_id,login_id,purpose,challenge,expires_at,created_at) VALUES(?1,?2,'LOGIN',?3,?4,?5)").bind(challengeId,loginId,challenge,expires,createdAt),
  ]);
  return {ok:true,challenge_id:challengeId,challenge,algorithm:"pbkdf2_sha256",iterations:parts?.iterations??120000,salt:parts?.salt??fakeSalt};
}

export async function createSession(db: D1Database, env: Env, input: {login_id:string;challenge_id:string;proof:string;device_id:string;device_label?:string}): Promise<Response|Record<string,unknown>> {
  const results=await db.batch([
    db.prepare("SELECT challenge_id,login_id,challenge,expires_at FROM auth_challenges WHERE challenge_id=?1 AND login_id=?2 AND purpose='LOGIN'").bind(input.challenge_id,input.login_id),
    db.prepare("SELECT login_id,verifier,verifier_hash,role,display_name,position,email,status FROM accounts WHERE login_id=?1").bind(input.login_id),
    db.prepare("DELETE FROM auth_challenges WHERE challenge_id=?1").bind(input.challenge_id),
  ]);
  const challenge=(results[0]?.results?.[0]??null) as ChallengeRow|null,account=(results[1]?.results?.[0]??null) as AccountRow|null;
  const parts=account?verifierParts(account.verifier):null;
  if(!challenge||challenge.expires_at<Date.now()||!account||account.status!=="ACTIVE"||!parts) return {ok:false,error:{code:"INVALID_CREDENTIALS",error_class:"AUTH",retryable:false}};
  const expected=await hmacB64u(b64uDecode(parts.key),challenge.challenge);
  if(!constantTimeEqual(expected,input.proof)) return {ok:false,error:{code:"INVALID_CREDENTIALS",error_class:"AUTH",retryable:false}};
  const deviceId=String(input.device_id||"").trim().slice(0,180); if(!deviceId) return {ok:false,error:{code:"DEVICE_ID_REQUIRED",error_class:"VALIDATION",retryable:false}};
  const sessionId=crypto.randomUUID(), issuedAt=nowIso();
  await db.prepare(`INSERT INTO auth_sessions(login_id,session_id,device_id,issued_at) VALUES(?1,?2,?3,?4)
    ON CONFLICT(login_id) DO UPDATE SET session_id=excluded.session_id,device_id=excluded.device_id,issued_at=excluded.issued_at`).bind(account.login_id,sessionId,deviceId,issuedAt).run();
  const payload={l:account.login_id,r:account.role,v:account.verifier_hash,s:sessionId,d:deviceId};
  const encoded=b64u(new TextEncoder().encode(JSON.stringify(payload))), sig=await hmacB64u(new TextEncoder().encode(env.SERVICE_TOKEN_SECRET),encoded);
  return {ok:true,token:`${encoded}.${sig}`,account:{login_id:account.login_id,role:account.role,display_name:account.display_name,position:account.position,email:account.email},session:{issued_at:issuedAt,device_label:String(input.device_label||"").slice(0,120)}};
}

export async function authenticate(db: D1Database, env: Env, request: Request): Promise<AuthContext|null> {
  const auth=request.headers.get("authorization")||""; if(!auth.startsWith("Bearer ")) return null;
  const token=auth.slice(7), parts=token.split("."); if(parts.length!==2) return null;
  const encoded=parts[0], signature=parts[1]; if(!encoded||!signature) return null;
  const expected=await hmacB64u(new TextEncoder().encode(env.SERVICE_TOKEN_SECRET),encoded); if(!constantTimeEqual(expected,signature)) return null;
  let payload:{l:string;r:"SUPERADMIN"|"ADMIN"|"USER";v:string;s:string;d:string};
  try{payload=JSON.parse(new TextDecoder().decode(b64uDecode(encoded))) as typeof payload;}catch{return null;}
  const results=await db.batch([
    db.prepare("SELECT login_id,role,display_name,verifier_hash,status FROM accounts WHERE login_id=?1").bind(payload.l),
    db.prepare("SELECT session_id,device_id FROM auth_sessions WHERE login_id=?1").bind(payload.l),
  ]);
  const account=(results[0]?.results?.[0]??null) as {login_id:string;role:"SUPERADMIN"|"ADMIN"|"USER";display_name:string;verifier_hash:string;status:string}|null;
  const session=(results[1]?.results?.[0]??null) as SessionRow|null;
  if(!account||account.status!=="ACTIVE"||account.role!==payload.r||account.verifier_hash!==payload.v||!session||session.session_id!==payload.s||session.device_id!==payload.d) return null;
  return {login_id:account.login_id,role:account.role,display_name:account.display_name,device_id:session.device_id,session_id:session.session_id,verifier_hash:account.verifier_hash};
}

export async function logout(db:D1Database, auth:AuthContext):Promise<void>{await db.prepare("DELETE FROM auth_sessions WHERE login_id=?1 AND session_id=?2 AND device_id=?3").bind(auth.login_id,auth.session_id,auth.device_id).run();}

export async function internalAuthorized(request: Request, env: Env): Promise<boolean> {
  const token=request.headers.get("x-m1-admin-token")||""; const a=await sha256Hex(token), b=await sha256Hex(env.M1_ADMIN_TOKEN); return constantTimeEqual(a,b);
}

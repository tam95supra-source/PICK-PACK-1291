import { authenticate } from "./auth";
import { commitAdminAudit } from "./admin_audit";
import { apiError, json, nowIso } from "./util";

interface GoogleToken { access_token?:string; error?:string; }
function roleVi(role:string):string{return role==="SUPERADMIN"?"Quản trị cao nhất":role==="ADMIN"?"Quản trị":"Người dùng";}
function stateVi(last:string,now:number):string{const t=Date.parse(last);if(!Number.isFinite(t))return"Không rõ";const age=Math.max(0,now-t);return age<=90_000?"Đang hoạt động":age<=600_000?"Hoạt động gần đây":"Không hoạt động";}

async function googleAccessToken(env:Env):Promise<string>{
  const body=new URLSearchParams({client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET,refresh_token:env.GOOGLE_OAUTH_REFRESH_TOKEN,grant_type:"refresh_token"});
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"content-type":"application/x-www-form-urlencoded"},body});const j=await r.json<GoogleToken>();if(!r.ok||!j.access_token)throw new Error(`GOOGLE_OAUTH:${j.error??r.status}`);return j.access_token;
}
async function clearAdminRow(env:Env,row:number):Promise<void>{
  const token=await googleAccessToken(env),range=`'Danh sách Admin'!A${row}:K${row}`,url=`https://sheets.googleapis.com/v4/spreadsheets/${encodeURIComponent(env.GOOGLE_SOURCE_SHEET_ID)}/values/${encodeURIComponent(range)}:clear`;
  const r=await fetch(url,{method:"POST",headers:{authorization:`Bearer ${token}`,"content-type":"application/json"},body:"{}"});if(!r.ok)throw new Error(`GOOGLE_ACCOUNT_CLEAR:${r.status}`);
}

/** Common, role-neutral operational view for the Android Đồng bộ screen. */
export async function serviceConnections(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const at=nowIso(),cutoff=new Date(Date.now()-10*60_000).toISOString();
  await env.DB.prepare(`INSERT INTO client_devices(device_id,login_id,platform,app_version,channel,authority_epoch,authority_seq,service_generation,last_seen_at,last_online_at,metadata_json)
    SELECT ?1,?2,'ANDROID','UNKNOWN','UNKNOWN',a.authority_epoch,a.authority_seq,a.service_generation,?3,?3,'{}' FROM authority_state a WHERE a.singleton_id=1
    ON CONFLICT(device_id) DO UPDATE SET login_id=excluded.login_id,last_seen_at=excluded.last_seen_at,last_online_at=excluded.last_online_at`).bind(auth.device_id,auth.login_id,at).run();
  const r=await env.DB.prepare(`SELECT d.login_id,a.display_name,a.role,MAX(d.last_seen_at) AS last_seen_at,COUNT(DISTINCT d.device_id) AS device_count
    FROM client_devices d LEFT JOIN accounts a ON a.login_id=d.login_id
    WHERE d.last_seen_at>=?1 AND COALESCE(a.status,'ACTIVE')='ACTIVE'
    GROUP BY d.login_id,a.display_name,a.role ORDER BY MAX(d.last_seen_at) DESC,d.login_id`).bind(cutoff).all<{login_id:string;display_name:string|null;role:string|null;last_seen_at:string;device_count:number}>();
  const now=Date.now(),items=(r.results??[]).map(x=>({tai_khoan:x.login_id,ten_hien_thi:x.display_name||x.login_id,quyen:roleVi(x.role||"USER"),trang_thai:stateVi(x.last_seen_at,now),lan_hoat_dong_gan_nhat:x.last_seen_at,so_thiet_bi:Number(x.device_count||0)}));
  return json({ok:true,cap_nhat_luc:at,nguoi_dung:items,dang_hoat_dong:items.filter(x=>x.trang_thai==="Đang hoạt động").length,gan_day:items.length});
}

/** Hard-delete ADMIN/USER accounts while preserving immutable audit events. */
export async function superadminDeleteAccounts(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);if(auth.role!=="SUPERADMIN")return apiError("SUPERADMIN_REQUIRED","PERMISSION",403);
  let body:{login_ids?:unknown};try{body=await request.json() as {login_ids?:unknown};}catch{return apiError("ACCOUNT_DELETE_BODY_INVALID","VALIDATION",400);}
  const ids=Array.isArray(body.login_ids)?[...new Set(body.login_ids.map(x=>String(x||"").trim()).filter(Boolean))].slice(0,100):[];if(!ids.length)return apiError("ACCOUNT_DELETE_IDS_REQUIRED","VALIDATION",400);
  const deleted:string[]=[],blocked:Array<{login_id:string;reason:string}>=[];
  for(const id of ids){
    if(id===auth.login_id){blocked.push({login_id:id,reason:"Không thể xóa tài khoản đang đăng nhập"});continue;}
    const row=await env.DB.prepare("SELECT login_id,role,display_name,source_row,status FROM accounts WHERE login_id=?1").bind(id).first<{login_id:string;role:string;display_name:string;source_row:number;status:string}>();
    if(!row){blocked.push({login_id:id,reason:"Không tìm thấy tài khoản"});continue;}
    if(row.role==="SUPERADMIN"){blocked.push({login_id:id,reason:"Tài khoản Quản trị cao nhất được bảo vệ"});continue;}
    await env.DB.prepare("UPDATE accounts SET status='DISABLED' WHERE login_id=?1").bind(id).run();
    try{if(Number(row.source_row)>1)await clearAdminRow(env,Number(row.source_row));else throw new Error("ACCOUNT_SOURCE_ROW_INVALID");}
    catch(e){blocked.push({login_id:id,reason:"Không cập nhật được Google Sheet"});continue;}
    await env.DB.prepare("DELETE FROM accounts WHERE login_id=?1 AND role<>'SUPERADMIN'").bind(id).run();
    await commitAdminAudit(env.DB,auth,{action:"account_delete",target_type:"ACCOUNT",target_id:id,target_label:row.display_name,result:"OK",detail:"Xóa tài khoản theo yêu cầu Superadmin",device_id:auth.device_id});deleted.push(id);
  }
  return json({ok:true,deleted,blocked});
}

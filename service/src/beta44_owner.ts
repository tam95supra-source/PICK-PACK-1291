import { authenticate } from "./auth";
import { apiError, json, nowIso } from "./util";

function roleVi(role:string):string{return role==="SUPERADMIN"?"Quản trị cao nhất":role==="ADMIN"?"Quản trị":"Người dùng";}
function stateVi(last:string,now:number):string{const t=Date.parse(last);if(!Number.isFinite(t))return"Không rõ";const age=Math.max(0,now-t);return age<=90_000?"Đang hoạt động":age<=600_000?"Hoạt động gần đây":"Không hoạt động";}

/**
 * Common, role-neutral operational view for the Android Đồng bộ screen.
 * It intentionally exposes no bearer, verifier, socket ticket, raw device id,
 * authority protocol or internal endpoint details.
 */
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
  const now=Date.now(),items=(r.results??[]).map(x=>({
    tai_khoan:x.login_id,
    ten_hien_thi:x.display_name||x.login_id,
    quyen:roleVi(x.role||"USER"),
    trang_thai:stateVi(x.last_seen_at,now),
    lan_hoat_dong_gan_nhat:x.last_seen_at,
    so_thiet_bi:Number(x.device_count||0),
  }));
  return json({ok:true,cap_nhat_luc:at,nguoi_dung:items,dang_hoat_dong:items.filter(x=>x.trang_thai==="Đang hoạt động").length,gan_day:items.length});
}

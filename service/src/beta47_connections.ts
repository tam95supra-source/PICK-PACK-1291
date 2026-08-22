import { authenticate } from "./auth";
import { apiError, json, nowIso } from "./util";

function roleVi(role:string):string{return role==="SUPERADMIN"?"Quản trị cao nhất":role==="ADMIN"?"Quản trị":"Người dùng";}
function platformVi(kind:string):string{return kind==="WEB"?"Web":"Ứng dụng";}

type Row={login_id:string;display_name:string|null;role:string|null;session_id:string;device_id:string;issued_at:string;client_kind:string;last_seen_at:string|null};

/** Active auth slots are the source of truth: one APP/PDA slot and one WEB slot per login. */
export async function serviceConnectionsV47(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);
  const r=await env.DB.prepare(`
    SELECT x.login_id,a.display_name,a.role,x.session_id,x.device_id,x.issued_at,x.client_kind,d.last_seen_at
    FROM (
      SELECT login_id,session_id,device_id,issued_at,'APP' client_kind FROM auth_sessions
      UNION ALL
      SELECT login_id,session_id,device_id,issued_at,'WEB' client_kind FROM auth_web_sessions
    ) x
    JOIN accounts a ON a.login_id=x.login_id AND a.status='ACTIVE'
    LEFT JOIN client_devices d ON d.device_id=x.device_id
    ORDER BY x.client_kind,x.login_id
  `).all<Row>();
  const items=(r.results??[]).map(x=>({
    tai_khoan:x.login_id,
    ten_hien_thi:x.display_name||x.login_id,
    quyen:roleVi(x.role||"USER"),
    nen_tang:platformVi(x.client_kind),
    loai_ket_noi:x.client_kind,
    thiet_bi:x.device_id,
    phien:x.session_id,
    dang_ket_noi:true,
    dang_nhap_luc:x.issued_at,
    lan_hoat_dong_gan_nhat:x.last_seen_at||x.issued_at,
  }));
  return json({ok:true,cap_nhat_luc:nowIso(),nguoi_dung:items,dang_ket_noi:items.length,app:items.filter(x=>x.loai_ket_noi==="APP").length,web:items.filter(x=>x.loai_ket_noi==="WEB").length});
}

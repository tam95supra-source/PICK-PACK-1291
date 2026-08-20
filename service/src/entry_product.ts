import current, { RealtimeHub } from "./entry";
import { authenticate } from "./auth";
import { exchangeGasSession, mobileRead } from "./mobile_hotfix";
import { apiError, json } from "./util";

export { RealtimeHub };

async function historicalBusinessDates(request:Request,env:Env):Promise<Response>{
  const auth=await authenticate(env.DB,env,request);if(!auth)return apiError("UNAUTHORIZED","AUTH",401);if(auth.role!=="SUPERADMIN")return apiError("SUPERADMIN_REQUIRED","PERMISSION",403);
  const u=new URL(request.url),limit=Math.min(200,Math.max(1,Number(u.searchParams.get("limit")||50))),beforeRaw=Number(u.searchParams.get("before_sequence")||0),before=Number.isFinite(beforeRaw)&&beforeRaw>0?beforeRaw:null;
  const q=before===null
    ?env.DB.prepare("SELECT business_date,sequence_no FROM business_dates ORDER BY sequence_no DESC LIMIT ?1").bind(limit+1)
    :env.DB.prepare("SELECT business_date,sequence_no FROM business_dates WHERE sequence_no<?1 ORDER BY sequence_no DESC LIMIT ?2").bind(before,limit+1);
  const r=await q.all<{business_date:string;sequence_no:number}>(),all=r.results??[],rows=all.slice(0,limit),next=all.length>limit?rows[rows.length-1]?.sequence_no??null:null;
  return json({ok:true,items:rows,next_before_sequence:next,has_more:all.length>limit});
}

export default {
  async fetch(request:Request,env:Env,ctx:ExecutionContext):Promise<Response>{
    const u=new URL(request.url);
    // S39B_PRODUCT_MOBILE_ROUTES: production entrypoint owns these routes directly; no wrapper indirection.
    if(u.pathname==="/v1/auth/gas-session"&&request.method==="POST")return exchangeGasSession(request,env);
    if(u.pathname==="/v1/mobile/read"&&request.method==="POST")return mobileRead(request,env);
    if(u.pathname==="/v1/admin/business-dates"&&request.method==="GET")return historicalBusinessDates(request,env);
    return current.fetch(request,env,ctx);
  },
  async scheduled(controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{return current.scheduled(controller,env,ctx);},
} satisfies ExportedHandler<Env>;

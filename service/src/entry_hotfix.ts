import entry, { RealtimeHub } from "./entry";
import { exchangeGasSession, mobileRead } from "./mobile_hotfix";
import { apiError } from "./util";

export { RealtimeHub };

export default {
  async fetch(request:Request,env:Env,ctx:ExecutionContext):Promise<Response>{
    const path=new URL(request.url).pathname;
    try{
      if(path==="/v1/auth/gas-session"&&request.method==="POST")return await exchangeGasSession(request,env);
      if(path==="/v1/mobile/read"&&request.method==="POST")return await mobileRead(request,env);
    }catch(e){
      console.log(JSON.stringify({level:"error",kind:"mobile_hotfix_failed",path,error:String(e)}));
      return apiError("MOBILE_HOTFIX_FAILED","INTERNAL",500,true,String(e).slice(0,300));
    }
    return entry.fetch(request,env,ctx);
  },
  async scheduled(controller:ScheduledController,env:Env,ctx:ExecutionContext):Promise<void>{
    return entry.scheduled(controller,env,ctx);
  },
} satisfies ExportedHandler<Env>;

import { fold, workChoice } from "./util";

export class IntegrityRuleError extends Error {
  constructor(public code:string, public status=409, public errorClass:"VALIDATION"|"RESOURCE"|"CONFLICT"="RESOURCE", public detail?:Record<string,unknown>){super(code);}
}

function text(v:unknown,max=240):string{return String(v??"").trim().slice(0,max);}
async function latestDate(db:D1Database):Promise<string>{const r=await db.prepare("SELECT business_date FROM business_dates ORDER BY sequence_no DESC LIMIT 1").first<{business_date:string}>();return r?.business_date??"";}
async function resourceAvailable(db:D1Database,type:string,id:string):Promise<boolean>{if(!id)return true;const r=await db.prepare("SELECT available FROM resources WHERE resource_type=?1 AND resource_id=?2").bind(type,id).first<{available:number}>();return Boolean(r?.available);}
async function requireResource(db:D1Database,type:string,id:string,code:string):Promise<void>{if(id&&!await resourceAvailable(db,type,id))throw new IntegrityRuleError(code,409,"RESOURCE",{resource_type:type,resource_id:id});}
async function packMapping(db:D1Database,table:string,shift:string,userPack:string):Promise<boolean>{if(!table||!shift||!userPack)return false;const r=await db.prepare("SELECT available FROM resource_pack_map WHERE pack_table=?1 AND shift=?2 AND user_pack=?3").bind(table,shift,userPack).first<{available:number}>();return Boolean(r?.available);}

async function validateAttendanceResources(db:D1Database,input:{mnv:string;businessDate:string;shift?:string;workChoice?:unknown;pda?:string;userPick?:string;packTable?:string;userPack?:string;resourceChange?:boolean}):Promise<void>{
  let shift=text(input.shift,80),choice=workChoice(input.workChoice),pda=text(input.pda,180),pick=text(input.userPick,180),table=text(input.packTable,180),pack=text(input.userPack,180);
  if(input.resourceChange){
    const current=await db.prepare("SELECT shift,work_choice,pda_serial,user_pick,pack_table,user_pack,state FROM attendance_sessions WHERE mnv=?1 AND business_date=?2").bind(input.mnv,input.businessDate).first<{shift:string;work_choice:string;pda_serial:string|null;user_pick:string|null;pack_table:string|null;user_pack:string|null;state:string}>();
    if(!current||current.state!=="ACTIVE")throw new IntegrityRuleError("ATTENDANCE_NOT_ACTIVE",409,"CONFLICT");
    if(!shift)shift=current.shift;if(fold(input.workChoice)==="")choice=workChoice(current.work_choice);if(!pda)pda=current.pda_serial??"";if(!pick)pick=current.user_pick??"";if(!table)table=current.pack_table??"";if(!pack)pack=current.user_pack??"";
  }
  await requireResource(db,"PDA",pda,"PDA_UNAVAILABLE");await requireResource(db,"USER_PICK",pick,"USER_PICK_UNAVAILABLE");await requireResource(db,"PACK_TABLE",table,"PACK_TABLE_UNAVAILABLE");await requireResource(db,"USER_PACK",pack,"USER_PACK_UNAVAILABLE");
  if(choice==="PICK"&&!pda)throw new IntegrityRuleError("PDA_REQUIRED_FOR_PICK",400,"VALIDATION");
  if(choice==="PACK"){
    if(!table||!pack)throw new IntegrityRuleError("PACK_RESOURCES_REQUIRED",400,"VALIDATION");
    if(!await packMapping(db,table,shift,pack))throw new IntegrityRuleError("PACK_RESOURCE_MAPPING_INVALID",409,"RESOURCE",{pack_table:table,shift,user_pack:pack});
  }
}

export async function validateLegacyIntegrity(db:D1Database,input:{action:string;business_date?:string;payload?:Record<string,unknown>}):Promise<void>{
  if(input.action!=="enter"&&input.action!=="resource_change")return;const p=input.payload??{},mnv=text(p.mnv,80);if(!mnv)return;const businessDate=text(input.business_date||p.business_date,10)||await latestDate(db);
  await validateAttendanceResources(db,{mnv,businessDate,shift:text(p.shift,80),workChoice:p.work_choice,pda:text(p.pda_serial??p.pda,180),userPick:text(p.user_pick??p.userPick,180),packTable:text(p.pack_table??p.packTable,180),userPack:text(p.user_pack??p.userPack,180),resourceChange:input.action==="resource_change"});
}

export async function validateCanonicalIntegrity(db:D1Database,input:{event_type?:string;business_date?:string;payload?:Record<string,unknown>}):Promise<void>{
  const type=String(input.event_type||"");if(type!=="ATTENDANCE_ENTER"&&type!=="RESOURCE_CHANGE")return;const p=input.payload??{},mnv=text(p.mnv,80);if(!mnv)return;const date=text(input.business_date,10)||await latestDate(db);
  await validateAttendanceResources(db,{mnv,businessDate:date,shift:text(p.shift,80),workChoice:p.work_choice,pda:text(p.pda_serial,180),userPick:text(p.user_pick,180),packTable:text(p.pack_table,180),userPack:text(p.user_pack,180),resourceChange:type==="RESOURCE_CHANGE"});
}

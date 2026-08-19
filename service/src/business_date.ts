import { nowIso } from "./util";

export function bangkokToday():string{
  const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Bangkok",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());
  const get=(type:string)=>parts.find(p=>p.type===type)?.value||"";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/**
 * Advance the operational business-session sequence when today's Bangkok date first receives work.
 * This does not widen N/N-1: it only adds the actual current Bangkok day, once, after the existing
 * newest session. Historical/future dates are never synthesized here.
 */
export async function ensureCurrentBangkokBusinessDate(db:D1Database,requestedDate:string):Promise<boolean>{
  const date=String(requestedDate||"").trim();
  if(!date||date!==bangkokToday())return false;
  const exists=await db.prepare("SELECT sequence_no FROM business_dates WHERE business_date=?1").bind(date).first<{sequence_no:number}>();
  if(exists)return false;
  const latest=await db.prepare("SELECT business_date,sequence_no FROM business_dates ORDER BY sequence_no DESC LIMIT 1").first<{business_date:string;sequence_no:number}>();
  if(latest?.business_date&&latest.business_date>date)return false;
  try{
    await db.prepare(`INSERT INTO business_dates(business_date,sequence_no,source)
      SELECT ?1,COALESCE(MAX(sequence_no),0)+1,'SERVICE_DAILY_ROLLOVER' FROM business_dates
      WHERE NOT EXISTS(SELECT 1 FROM business_dates WHERE business_date=?1)`).bind(date).run();
  }catch(e){
    // A concurrent first mutation can win the unique sequence/date race; re-read before surfacing it.
    const won=await db.prepare("SELECT sequence_no FROM business_dates WHERE business_date=?1").bind(date).first<{sequence_no:number}>();
    if(!won)throw e;
  }
  const inserted=await db.prepare("SELECT sequence_no FROM business_dates WHERE business_date=?1").bind(date).first<{sequence_no:number}>();
  if(inserted){
    await db.prepare("INSERT INTO system_meta(key,value,updated_at) VALUES('business_date_rollover',?1,?2) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at")
      .bind(JSON.stringify({business_date:date,sequence_no:inserted.sequence_no,source:"SERVICE_DAILY_ROLLOVER"}),nowIso()).run();
  }
  return Boolean(inserted);
}

export async function ensureBusinessDateFromRequest(db:D1Database,request:Request):Promise<void>{
  try{
    const body=await request.clone().json() as Record<string,unknown>;
    const payload=(body.payload&&typeof body.payload==="object"?body.payload:{}) as Record<string,unknown>;
    const date=String(body.business_date||payload.business_date||"").trim();
    if(date)await ensureCurrentBangkokBusinessDate(db,date);
  }catch{
    // Parsing/validation remains the canonical mutation handler's responsibility.
  }
}

type Dataset="employees"|"catalogs"|"pda"|"user_pick"|"pack_table"|"user_pack";
export type ImportRules=Map<string,Set<string>>;

const STATUS_NS:Partial<Record<Dataset,string>>={
  pda:"DANH SÁCH PDA_Tình trạng",
  user_pick:"DANH SÁCH USER PICK_Tình trạng",
  pack_table:"DANH SÁCH BÀN PACK_Tình trạng",
  user_pack:"DANH SÁCH USER PACK_Tình trạng",
};
const EMPLOYEE_FIELDS:Record<string,string>={
  main_position:"DANH SÁCH NHÂN SỰ_Vị trí chính",
  supplier:"DANH SÁCH NHÂN SỰ_Nhà cung cấp",
  department:"DANH SÁCH NHÂN SỰ_Bộ phận",
  site:"DANH SÁCH NHÂN SỰ_Site",
  warehouse:"DANH SÁCH NHÂN SỰ_Kho",
};
export const CATALOG_NAMESPACES=[
  "DANH SÁCH NHÂN SỰ_Vị trí chính","DANH SÁCH NHÂN SỰ_Nhà cung cấp","DANH SÁCH NHÂN SỰ_Bộ phận","DANH SÁCH NHÂN SỰ_Site","DANH SÁCH NHÂN SỰ_Kho",
  "DANH SÁCH PDA_Tình trạng","DANH SÁCH USER PICK_Tình trạng","DANH SÁCH BÀN PACK_Tình trạng","DANH SÁCH USER PACK_Tình trạng","RA - VÀO TRONG CA_Loại thao tác",
  "VÀO - RA TRONG CA_Ca","CÔNG NHẬT_Thông tin công nhật","CÔNG NHẬT_Mốc thời gian","CÔNG NHẬT_Trạng thái",
] as const;

export async function loadImportRules(db:D1Database):Promise<ImportRules>{
  const rows=(await db.prepare("SELECT namespace,value FROM catalog_values ORDER BY namespace,ordinal").all<{namespace:string;value:string}>()).results??[],rules:ImportRules=new Map();
  for(const r of rows){const set=rules.get(r.namespace)??new Set<string>();set.add(String(r.value));rules.set(r.namespace,set);}return rules;
}
function allowed(rules:ImportRules,ns:string,value:unknown):boolean{const v=String(value??"").trim();return !v||Boolean(rules.get(ns)?.has(v));}
export function importRuleError(rules:ImportRules,dataset:Dataset,row:Record<string,unknown>):string|null{
  if(dataset==="catalogs"){const ns=String(row.namespace??"").trim();if(!CATALOG_NAMESPACES.includes(ns as never))return"CATALOG_NAMESPACE_INVALID";return null;}
  if(dataset==="employees"){for(const [field,ns] of Object.entries(EMPLOYEE_FIELDS))if(!allowed(rules,ns,row[field]))return `SELECT_${field.toUpperCase()}_INVALID`;return null;}
  const ns=STATUS_NS[dataset];if(ns&&!allowed(rules,ns,row.status_label))return"STATUS_LABEL_INVALID";
  if(dataset==="pack_table"&&!allowed(rules,"VÀO - RA TRONG CA_Ca",row.shift))return"SHIFT_INVALID";
  return null;
}
export function selectValuesForDataset(rules:ImportRules,dataset:Dataset):Record<string,string[]>{
  const out:Record<string,string[]>={};
  if(dataset==="catalogs")out.namespace=[...CATALOG_NAMESPACES];
  if(dataset==="employees")for(const [field,ns] of Object.entries(EMPLOYEE_FIELDS))out[field]=[...(rules.get(ns)??[])];
  const ns=STATUS_NS[dataset];if(ns)out.status_label=[...(rules.get(ns)??[])];
  if(dataset==="pack_table")out.shift=[...(rules.get("VÀO - RA TRONG CA_Ca")??[])];
  return out;
}

from pathlib import Path

# Apps Script: one request reads dynamic sheets once; employee context can return options in same response.
gas=Path('google-apps-script/PICK_PACK_API.gs')
g=gas.read_text(encoding='utf-8')
old="function ppMasterData_() { const s=ppMasterSnapshotData_(); return {pdas:s.pdas,userPicks:s.user_picks,packs:s.pack_bundles}; }\nfunction ppCatalog_() { const s=ppMasterSnapshotData_(); return {labor_types:s.labor_types,time_markers:s.time_markers}; }\n\nfunction ppRaRows_() { return ppObjects_(PP.RA); }"
new="function ppMasterData_() { const s=ppMasterSnapshotData_(); return {pdas:s.pdas,userPicks:s.user_picks,packs:s.pack_bundles}; }\nfunction ppCatalog_() { const s=ppMasterSnapshotData_(); return {labor_types:s.labor_types,time_markers:s.time_markers}; }\n\nlet PP_REQUEST_RA_ROWS_ = null;\nlet PP_REQUEST_LABOR_ROWS_ = null;\nfunction ppRaRows_() { if(PP_REQUEST_RA_ROWS_!==null)return PP_REQUEST_RA_ROWS_; PP_REQUEST_RA_ROWS_=ppObjects_(PP.RA); return PP_REQUEST_RA_ROWS_; }"
if old not in g: raise SystemExit('RA cache anchor missing')
g=g.replace(old,new,1)
old="  const state=!session?'NOT_ENTERED':session.state==='ACTIVE'?'ACTIVE':'ENDED';\n  return {ok:true,business_date:ppBusinessIso_(),employee:staff,state:state,session:session,active_labor:ppActiveLabor_(mnv)};"
new="  const state=!session?'NOT_ENTERED':session.state==='ACTIVE'?'ACTIVE':'ENDED';\n  const options=state==='NOT_ENTERED'?ppMasterOptions_({mnv:mnv}):null;\n  return {ok:true,business_date:ppBusinessIso_(),employee:staff,state:state,session:session,active_labor:ppActiveLabor_(mnv),options:options};"
if old not in g: raise SystemExit('employee context anchor missing')
g=g.replace(old,new,1)
old="function ppLaborRows_() { return ppObjects_(PP.LABOR); }"
new="function ppLaborRows_() { if(PP_REQUEST_LABOR_ROWS_!==null)return PP_REQUEST_LABOR_ROWS_; PP_REQUEST_LABOR_ROWS_=ppObjects_(PP.LABOR); return PP_REQUEST_LABOR_ROWS_; }"
if old not in g: raise SystemExit('labor cache anchor missing')
g=g.replace(old,new,1)
gas.write_text(g,encoding='utf-8')

# Android: consume inline options, retain backward-compatible fallback.
app=Path('app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt')
s=app.read_text(encoding='utf-8')
old='''            val ctx=result.json ?: JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED") api.call("master_options", JSONObject().put("mnv", mnv)) { masters -> runOnUiThread {
                if(masters.code==401){sessionExpired();return@runOnUiThread}; renderEmployee(ctx, masters.json ?: JSONObject())
            } } else renderEmployee(ctx, null)'''
new='''            val ctx=result.json ?: JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED") {
                val inline = ctx.optJSONObject("options")
                if(inline != null) renderEmployee(ctx, inline) else api.call("master_options", JSONObject().put("mnv", mnv)) { masters -> runOnUiThread {
                    if(masters.code==401){sessionExpired();return@runOnUiThread}; renderEmployee(ctx, masters.json ?: JSONObject())
                } }
            } else renderEmployee(ctx, null)'''
if old not in s: raise SystemExit('FullBeta loadEmployee anchor missing')
s=s.replace(old,new,1)
app.write_text(s,encoding='utf-8')
print('v0.4.1 latency optimization applied')

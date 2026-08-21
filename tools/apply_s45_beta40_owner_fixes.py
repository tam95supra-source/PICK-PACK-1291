#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
PROJ = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt"
STORE = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt"
TRANSPORT = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt"
MARK = "S45_BETA40_OWNER_FIXES"


def replace_private_fun(src: str, signature: str, replacement: str) -> str:
    start = src.find("    private fun " + signature)
    if start < 0:
        raise SystemExit("S45 function anchor missing: " + signature)
    end = src.find("\n    private fun ", start + 20)
    if end < 0:
        raise SystemExit("S45 next function anchor missing: " + signature)
    return src[:start] + replacement.rstrip() + "\n" + src[end:]


def replace_public_fun(src: str, signature: str, replacement: str) -> str:
    start = src.find("    fun " + signature)
    if start < 0:
        raise SystemExit("S45 public function anchor missing: " + signature)
    end = src.find("\n    fun ", start + 12)
    if end < 0:
        end = src.find("\n    private fun ", start + 12)
    if end < 0:
        raise SystemExit("S45 next function anchor missing: " + signature)
    return src[:start] + replacement.rstrip() + "\n" + src[end:]


# 1) Canonical current business day on device.
store = STORE.read_text(encoding="utf-8")
if 'private const val TZ = "Asia/Bangkok"' in store:
    store = store.replace(
        'private const val TZ = "Asia/Bangkok"',
        'private const val TZ = "Asia/Ho_Chi_Minh" // ' + MARK,
        1,
    )
elif 'private const val TZ = "Asia/Ho_Chi_Minh"' not in store:
    raise SystemExit("S45 timezone anchor missing")
STORE.write_text(store, encoding="utf-8")

proj = PROJ.read_text(encoding="utf-8")
if MARK not in proj:
    old = "val businessDate = store.latestBusinessDate()"
    if old not in proj:
        raise SystemExit("S45 employee current-day anchor missing")
    proj = proj.replace(old, "val businessDate = store.businessDate() // " + MARK, 1)

    resource = r'''    fun resourceOptions(context: Context, mnvRaw: String): JSONObject {
        // S45_BETA40_OWNER_FIXES: N is authoritative for the active UI; returned users are re-issuable, active users stay blocked.
        val mnv=mnvRaw.trim();val raw=MasterDataCache.resourceOptions(context);val store=OperationalDataStore(context.applicationContext);val date=store.businessDate()
        val byMnv=LinkedHashMap<String,JSONObject>();val usedPicks=LinkedHashSet<String>();val usedPackUsers=LinkedHashSet<String>()
        val day=store.loadDay(date);val sessions=day?.optJSONArray("sessions")?:JSONArray()
        for(i in 0 until sessions.length()){
            val src=sessions.optJSONObject(i)?:continue;val who=src.optString("mnv").trim();if(who.isBlank())continue
            val copy=JSONObject(src.toString());byMnv[who]=copy
            copy.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(usedPicks::add)
            copy.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(usedPackUsers::add)
        }
        for(item in store.projectionMutations(1000)){
            val body=item.body;val payload=body.optJSONObject("payload")?:body
            val eventDate=payload.optString("business_date").ifBlank{body.optString("business_date")}
            if(eventDate.isNotBlank()&&eventDate!=date)continue
            val who=payload.optString("mnv").trim();if(who.isBlank())continue
            val action=body.optString("action").ifBlank{payload.optString("action")}
            val cur=byMnv.getOrPut(who){JSONObject().put("mnv",who).put("state","NOT_ENTERED")}
            when(action){
                "enter"->{cur.put("state","ACTIVE");for(k in listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack"))if(payload.has(k))cur.put(k,payload.opt(k));payload.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(usedPicks::add);payload.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(usedPackUsers::add)}
                "resource_change"->{for(k in listOf("work_choice","pda_serial","user_pick","pack_table","user_pack"))if(payload.has(k))cur.put(k,payload.opt(k));payload.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(usedPicks::add);payload.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(usedPackUsers::add)}
                "exit"->cur.put("state","ENDED")
            }
        }
        val busyPdas=LinkedHashSet<String>();val busyPicks=LinkedHashSet<String>();val busyTables=LinkedHashSet<String>();val busyPackUsers=LinkedHashSet<String>()
        for((who,ses) in byMnv){
            if(who==mnv||!ses.optString("state").equals("ACTIVE",true))continue
            ses.optString("pda_serial").trim().takeIf{it.isNotBlank()}?.let(busyPdas::add)
            ses.optString("user_pick").trim().takeIf{it.isNotBlank()}?.let(busyPicks::add)
            ses.optString("pack_table").trim().takeIf{it.isNotBlank()}?.let(busyTables::add)
            ses.optString("user_pack").trim().takeIf{it.isNotBlank()}?.let(busyPackUsers::add)
        }
        val current=byMnv[mnv]
        val pdas=JSONArray();val sourcePdas=raw.optJSONArray("pdas")?:JSONArray()
        for(i in 0 until sourcePdas.length()){val x=sourcePdas.optJSONObject(i)?:continue;val id=x.optString("serial").trim();if(id.isNotBlank()&&(id !in busyPdas||id==current?.optString("pda_serial")))pdas.put(JSONObject(x.toString()))}
        val normalPicks=JSONArray();val reissuePicks=JSONArray();val sourcePicks=raw.optJSONArray("user_picks")?:JSONArray()
        for(i in 0 until sourcePicks.length()){val id=sourcePicks.optString(i).trim();if(id.isBlank())continue;val isCurrent=id==current?.optString("user_pick");when{isCurrent->normalPicks.put(id);id in busyPicks->Unit;id in usedPicks->reissuePicks.put(JSONObject().put("id",id).put("busy",false).put("used_today",true).put("duplicate_user",true).put("note","TRÙNG USER"));else->normalPicks.put(id)}}
        val normalPacks=JSONArray();val reissuePacks=JSONArray();val sourcePacks=raw.optJSONArray("pack_tables")?:JSONArray()
        for(i in 0 until sourcePacks.length()){val x=sourcePacks.optJSONObject(i)?:continue;val table=x.optString("table").trim();val user=x.optString("user_pack").trim();if(table.isBlank()||user.isBlank())continue;val isCurrent=table==current?.optString("pack_table")&&user==current?.optString("user_pack");when{isCurrent->normalPacks.put(JSONObject(x.toString()).put("duplicate_user",false));table in busyTables||user in busyPackUsers->Unit;user in usedPackUsers->reissuePacks.put(JSONObject(x.toString()).put("duplicate_user",true).put("note","TRÙNG USER"));else->normalPacks.put(JSONObject(x.toString()).put("duplicate_user",false))}}
        return JSONObject().put("ok",true).put("source","PDA_LOCAL_MASTER").put("business_date",date).put("pdas",pdas).put("pda_statuses",raw.optJSONArray("pda_statuses")?:JSONArray()).put("user_picks",normalPicks).put("user_picks_reissue",reissuePicks).put("pack_tables",normalPacks).put("pack_tables_reissue",reissuePacks).put("current",current?:JSONObject.NULL).put("master_revision",raw.optLong("master_revision",0L))
    }'''
    proj = replace_public_fun(proj, "resourceOptions(context: Context, mnvRaw: String): JSONObject {", resource)
    PROJ.write_text(proj, encoding="utf-8")

# Mutations carry N explicitly even after the S31 compact transport rewrite.
transport = TRANSPORT.read_text(encoding="utf-8")
if MARK not in transport:
    anchors = [
        (
            '''        payload.put("event_id", eventId)
        val request = JSONObject()
            .put("action", action)
            .put("event_id", eventId)
            .put("device_id", M2DeviceIdentity.id(app))''',
            '''        val businessDate=store.businessDate() // S45_BETA40_OWNER_FIXES
        payload.put("event_id",eventId).put("business_date",businessDate)
        val request = JSONObject()
            .put("action", action)
            .put("event_id", eventId)
            .put("business_date",businessDate)
            .put("device_id", M2DeviceIdentity.id(app))''',
        ),
        (
            '''        payload.put("event_id", eventId)
        val request = JSONObject().put("action", action).put("event_id", eventId).put("device_id", M2DeviceIdentity.id(app))
            .put("payload", JSONObject(payload.toString()).put("event_id", eventId))''',
            '''        val businessDate=store.businessDate() // S45_BETA40_OWNER_FIXES
        payload.put("event_id",eventId).put("business_date",businessDate)
        val request = JSONObject().put("action", action).put("event_id", eventId).put("business_date",businessDate).put("device_id", M2DeviceIdentity.id(app))
            .put("payload", JSONObject(payload.toString()).put("event_id",eventId).put("business_date",businessDate))''',
        ),
    ]
    for old, new in anchors:
        if old in transport:
            transport = transport.replace(old, new, 1)
            break
    else:
        raise SystemExit("S45 transport business-date anchor missing")
    TRANSPORT.write_text(transport, encoding="utf-8")

ops = OPS.read_text(encoding="utf-8")
if MARK not in ops:
    load = r'''    // S45_BETA40_OWNER_FIXES: never let an N-1 Service response replace current N local context.
    private fun loadEmployee(mnv: String, button: Button? = null) {
        val resolved=MasterDataCache.resolveEmployeeMnv(this,mnv)
        if(resolved.isBlank()){button?.isEnabled=true;showError("MNV_REQUIRED");return}
        val generation=++employeeLookupGeneration
        val currentDate=operationalStore.businessDate()
        val localNow=PdaLocalProjection.employeeContext(this,resolved)
        val localOptions=PdaLocalProjection.resourceOptions(this,resolved)
        val cached=MasterDataCache.employee(this,resolved)
        if(localNow!=null)renderEmployee(localNow,localOptions)else if(cached!=null)renderCachedEmployee(cached)
        api.call("employee_context",JSONObject().put("mnv",resolved).put("include_options",true).put("include_labor",false)){result->runOnUiThread{
            if(generation!=employeeLookupGeneration)return@runOnUiThread
            button?.isEnabled=true
            val overlay=PdaLocalProjection.employeeContext(this@OperationsActivity,resolved)
            val refreshedOptions=PdaLocalProjection.resourceOptions(this@OperationsActivity,resolved)
            if(!result.ok){
                if(overlay!=null){renderEmployee(overlay,refreshedOptions);TopNotice.show(this@OperationsActivity,"Service chưa xác nhận được; thao tác vẫn lưu local và sẽ đồng bộ khi ứng dụng ở foreground.",TopNotice.Kind.WARNING)}
                else if(result.code==401)sessionExpired()
                else showError(result.error?:"Không kiểm tra được mã nhân viên")
                return@runOnUiThread
            }
            if(overlay!=null&&overlay.optString("reconciliation_state")=="LOCAL_PENDING"){renderEmployee(overlay,refreshedOptions);return@runOnUiThread}
            val ctx=result.json?:JSONObject()
            val remoteDate=ctx.optString("business_date").trim()
            if(remoteDate.isNotBlank()&&remoteDate!=currentDate){
                if(overlay!=null)renderEmployee(overlay,refreshedOptions)else if(cached!=null)renderCachedEmployee(cached)
                return@runOnUiThread
            }
            val remote=ctx.optJSONObject("options")
            val options=if(remote==null)refreshedOptions else JSONObject(remote.toString()).apply{
                for(k in listOf("user_picks_reissue","pack_tables_reissue")){
                    val local=refreshedOptions.optJSONArray(k)
                    if((optJSONArray(k)?.length()?:0)==0&&local!=null&&local.length()>0)put(k,local)
                }
            }
            renderEmployee(ctx,options)
        }}
    }'''
    ops = replace_private_fun(ops, "loadEmployee(mnv: String, button: Button? = null) {", load)

    anchor = "    private fun renderActive(body: LinearLayout, ctx: JSONObject) {"
    if anchor not in ops:
        raise SystemExit("S45 attendance reset helper anchor missing")
    helper = r'''    private fun scheduleAttendanceAutoReset(mnv:String,generation:Long){
        val expected=mnv.trim()
        android.os.Handler(mainLooper).postDelayed({
            // If another code has already been scanned/rendered, never clear that newer employee.
            if(screenState=="EMPLOYEE"&&liveEmployeeMnv==expected&&employeeLookupGeneration==generation)employeeScan()
        },650L)
    }

'''
    ops = ops.replace(anchor, helper + anchor, 1)

    old_exit = '''fun callExit(statusNow:String){exit.isEnabled=false;exit.text="ĐANG RA CA...";val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv);if(statusNow.isNotBlank())payload.put("pda_exit_status",statusNow);api.call("exit",payload){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else loadEmployee(mnv)}}}'''
    new_exit = '''fun callExit(statusNow:String){val actionGeneration=employeeLookupGeneration;exit.isEnabled=false;exit.text="ĐANG RA CA...";val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv);if(statusNow.isNotBlank())payload.put("pda_exit_status",statusNow);api.call("exit",payload){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else{TopNotice.show(this,"Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);scheduleAttendanceAutoReset(mnv,actionGeneration)}}}}'''
    if old_exit not in ops:
        raise SystemExit("S45 exit success anchor missing")
    ops = ops.replace(old_exit, new_exit, 1)

    start = ops.find("    private fun pdaInput(")
    end = ops.find("\n    private fun resolvePda(", start)
    if start < 0 or end < 0:
        raise SystemExit("S45 pdaInput anchors missing")
    pda = r'''    private fun pdaInput(pdas:JSONArray,currentSerial:String="",onSelected:(JSONObject?)->Unit={}):AutoCompleteTextView{
        val labels=mutableListOf<String>()
        for(i in 0 until pdas.length()){
            val p=pdas.optJSONObject(i)?:continue
            val serial=p.optString("serial").trim()
            val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)}
            val status=p.optString("status").trim()
            if(serial.isNotBlank()&&last5.isNotBlank())labels.add("$last5 • $serial • Tình trạng: ${status.ifBlank{"—"}}")
        }
        val field=AutoCompleteTextView(this);var selectedLast5="";var internal=false
        field.hint="Gõ 5 số cuối Seri PDA";field.threshold=1;field.textSize=13f;field.setTextColor(ink);field.setHintTextColor(Color.rgb(153,163,176));field.inputType=InputType.TYPE_CLASS_TEXT;field.setPadding(dp(13),dp(10),dp(13),dp(10));field.minHeight=dp(50);field.background=outline();field.setAdapter(ArrayAdapter(this,android.R.layout.simple_dropdown_item_1line,labels))
        field.setOnItemClickListener{parent,_,pos,_->val label=parent.getItemAtPosition(pos).toString();val p=resolvePdaObject(pdas,label);if(p!=null){selectedLast5=p.optString("last5").trim().ifBlank{p.optString("serial").takeLast(5)};internal=true;field.setText(selectedLast5,false);field.setSelection(field.text.length);field.tag=JSONObject(p.toString());internal=false;onSelected(JSONObject(p.toString()))}}
        field.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(s:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(s:CharSequence?,st:Int,b:Int,c:Int)=Unit;override fun afterTextChanged(e:Editable?){if(!internal&&selectedLast5.isNotBlank()&&e?.toString()?.trim()!=selectedLast5){selectedLast5="";field.tag=null;onSelected(null)}}})
        field.setOnClickListener{field.showDropDown()}
        if(currentSerial.isNotBlank()){for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;if(p.optString("serial")==currentSerial){selectedLast5=p.optString("last5").trim().ifBlank{currentSerial.takeLast(5)};internal=true;field.setText(selectedLast5,false);field.tag=JSONObject(p.toString());internal=false;onSelected(JSONObject(p.toString()));break}}}
        return field
    }'''
    ops = ops[:start] + pda + ops[end:]

    oldvars = '''var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>();var packSelection:JSONObject?=null;var allowDuplicate=false'''
    newvars = '''var pdaField:AutoCompleteTextView?=null;var selectedPda:JSONObject?=null;var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>();var packSelection:JSONObject?=null;var allowDuplicate=false'''
    if oldvars not in ops:
        raise SystemExit("S45 selected PDA variable anchor missing")
    ops = ops.replace(oldvars, newvars, 1)

    old_pick = '''pdaField=pdaInput(pdas);resourceBox.addView(labelled("Seri PDA — gõ 5 số cuối",pdaField!!));resourceBox.addView(gap(5));resourceBox.addView(info("Chọn gợi ý để hiện đầy đủ Seri PDA và Tình trạng. Có thể ấn lại vào ô PDA để gõ 5 số cuối khác."));resourceBox.addView(gap(8))'''
    new_pick = '''val pdaInfo=txt("Chọn gợi ý để hiện đầy đủ Seri PDA và Tình trạng.",10f,muted,false);pdaField=pdaInput(pdas,onSelected={p->selectedPda=p;pdaInfo.text=if(p==null)"Chọn gợi ý để hiện đầy đủ Seri PDA và Tình trạng." else "Seri PDA: ${p.optString("serial")}\\nTình trạng: ${p.optString("status").ifBlank{"—"}}"});resourceBox.addView(labelled("Seri PDA — gõ 5 số cuối",pdaField!!));resourceBox.addView(gap(5));resourceBox.addView(pdaInfo,matchWrap());resourceBox.addView(gap(8))'''
    if old_pick not in ops:
        raise SystemExit("S45 PDA detail placement anchor missing")
    ops = ops.replace(old_pick, new_pick, 1)

    old_rebuild = '''rebuildResources={resourceBox.removeAllViews();pdaField=null;pickSpinner=null;pickChoices.clear();packSelection=null;when(workValue)'''
    new_rebuild = '''rebuildResources={resourceBox.removeAllViews();pdaField=null;selectedPda=null;pickSpinner=null;pickChoices.clear();packSelection=null;when(workValue)'''
    if old_rebuild not in ops:
        raise SystemExit("S45 PDA rebuild reset anchor missing")
    ops = ops.replace(old_rebuild, new_rebuild, 1)

    old_submit = '''val raw=pdaField?.text?.toString().orEmpty();if(!raw.contains("Tình trạng:")){showError("Hãy gõ 5 số cuối và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};val p=resolvePdaObject(pdas,raw);if(p==null){showError("PDA không còn hợp lệ. Chọn lại PDA.");return@setOnClickListener};payload.put("pda_serial",p.optString("serial")).put("pda_status_at_enter",p.optString("status"));'''
    new_submit = '''val p=selectedPda;val expected=if(p==null)"" else p.optString("last5").trim().ifBlank{p.optString("serial").takeLast(5)};if(p==null||pdaField?.text?.toString()?.trim()!=expected){showError("Hãy gõ 5 số cuối và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};payload.put("pda_serial",p.optString("serial")).put("pda_status_at_enter",p.optString("status"));'''
    if old_submit not in ops:
        raise SystemExit("S45 PDA submit anchor missing")
    ops = ops.replace(old_submit, new_submit, 1)

    old_enter = '''enterBtn.isEnabled=false;enterBtn.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enterBtn.isEnabled=true;enterBtn.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else loadEmployee(mnv)}}'''
    new_enter = '''val actionGeneration=employeeLookupGeneration;enterBtn.isEnabled=false;enterBtn.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enterBtn.isEnabled=true;enterBtn.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else{TopNotice.show(this,"Đã ghi nhận vào ca.",TopNotice.Kind.SUCCESS);scheduleAttendanceAutoReset(mnv,actionGeneration)}}}'''
    if old_enter not in ops:
        raise SystemExit("S45 enter success anchor missing")
    ops = ops.replace(old_enter, new_enter, 1)

    old_date = 'var selectedDate=operationalStore.latestBusinessDate().ifBlank{operationalStore.businessDate()}'
    if old_date not in ops:
        raise SystemExit("S45 History default date anchor missing")
    ops = ops.replace(old_date, 'var selectedDate=operationalStore.businessDate()', 1)

    if 'if(needle.isBlank())scanDate(selectedDate,"",1800,out)' not in ops:
        raise SystemExit("S45 History canonical cap anchor missing")
    ops = ops.replace('if(needle.isBlank())scanDate(selectedDate,"",1800,out)', 'if(needle.isBlank())scanDate(selectedDate,"",Int.MAX_VALUE,out)', 1)

    if "for(local in operationalStore.localHistory(600))" not in ops:
        raise SystemExit("S45 History local cap anchor missing")
    ops = ops.replace("for(local in operationalStore.localHistory(600))", "for(local in operationalStore.localHistoryAll())", 1)

    metric = '''val pending=rows.count{statusOf(it)=="PENDING"};val failed=rows.count{statusOf(it)=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is LinearLayout&&v.childCount>1)(v.getChildAt(1) as? TextView)?.text=n.toString()};updateMetric(allBtn,rows.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)'''
    metric_new = '''val metricRows=if(query.isBlank())rows else run{val savedQuery=query;query="";val allRows=loadRows();query=savedQuery;allRows};val pending=metricRows.count{statusOf(it)=="PENDING"};val failed=metricRows.count{statusOf(it)=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is LinearLayout&&v.childCount>1)(v.getChildAt(1) as? TextView)?.text=n.toString()};updateMetric(allBtn,metricRows.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)'''
    if metric not in ops:
        raise SystemExit("S45 History KPI anchor missing")
    ops = ops.replace(metric, metric_new, 1)

    # Reissue is for users used earlier in the day and already returned, not users currently active.
    ops = ops.replace("PHÁT LẠI USER ĐANG DÙNG", "PHÁT LẠI USER ĐÃ DÙNG")
    ops = ops.replace("Mục có TRÙNG USER chỉ xuất hiện khi bật Phát lại User đang dùng.", "Mục đã dùng chỉ xuất hiện khi bật Phát lại User đã dùng.")
    OPS.write_text(ops, encoding="utf-8")

final_store = STORE.read_text(encoding="utf-8")
final_proj = PROJ.read_text(encoding="utf-8")
final_transport = TRANSPORT.read_text(encoding="utf-8")
final_ops = OPS.read_text(encoding="utf-8")
checks = [
    ('Asia/Ho_Chi_Minh' in final_store, "canonical timezone"),
    ('val businessDate = store.businessDate()' in final_proj, "employee context uses N"),
    ('user_picks_reissue' in final_proj and 'pack_tables_reissue' in final_proj, "returned users reissue lists"),
    ('id in busyPicks->Unit;id in usedPicks->reissuePicks' in final_proj, "active users stay blocked"),
    ('.put("business_date",businessDate)' in final_transport, "mutation carries N"),
    ('remoteDate!=currentDate' in final_ops, "N-1 remote response fence"),
    ('var selectedDate=operationalStore.businessDate()' in final_ops, "History defaults to N"),
    ('Int.MAX_VALUE' in final_ops and 'localHistoryAll()' in final_ops, "History full selected day"),
    ('updateMetric(allBtn,metricRows.size)' in final_ops, "History KPI not page-limited"),
    ('field.setText(selectedLast5,false)' in final_ops and 'Seri PDA: ${p.optString("serial")}' in final_ops, "PDA detail below input"),
    ('scheduleAttendanceAutoReset' in final_ops and 'employeeLookupGeneration==generation' in final_ops, "attendance race guard"),
    ('PHÁT LẠI USER ĐÃ DÙNG' in final_ops, "returned-user reissue control"),
]
for ok, label in checks:
    if not ok:
        raise SystemExit("S45 contract missing: " + label)

print("Applied S45 Beta40 owner fixes: current N, full-day History KPIs, returned-user reissue, PDA detail below, race-safe attendance reset")

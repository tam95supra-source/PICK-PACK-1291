#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MASTER=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/MasterDataCache.kt'
TRANSPORT=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
MARK='S39_EMPLOYEE_SESSION_HISTORY'


def replace_fun(src:str,signature:str,replacement:str)->str:
    a=src.find('    private fun '+signature)
    if a<0: raise SystemExit('S39 function anchor missing: '+signature)
    b=src.find('\n    private fun ',a+20)
    if b<0: raise SystemExit('S39 next function anchor missing: '+signature)
    return src[:a]+replacement.rstrip()+'\n'+src[b:]

# --- Master MNV resolver: exact master first, then one-and-only-one embedded real MNV. ---
m=MASTER.read_text(encoding='utf-8')
if MARK not in m:
    anchor='''    fun resourceOptions(context: Context): JSONObject {'''
    if anchor not in m: raise SystemExit('S39 MasterDataCache anchor missing')
    fn=r'''    // S39_EMPLOYEE_SESSION_HISTORY: scanner payloads may include prefix/suffix/control bytes.
    // Resolve only against the actual cached master. Never guess an unknown employee code.
    fun resolveEmployeeMnv(context: Context, raw: String): String {
        snapshot(context)
        val cleaned = raw.replace(Regex("[\\p{Cc}\\p{Cf}]"), "").trim()
        if (cleaned.isBlank()) return ""
        if (staffByMnv.containsKey(cleaned)) return cleaned
        var match: String? = null
        for (candidate in staffByMnv.keys) {
            if (!cleaned.contains(candidate)) continue
            if (match != null && match != candidate) return cleaned
            match = candidate
        }
        return match ?: cleaned
    }

'''
    m=m.replace(anchor,fn+anchor,1)
MASTER.write_text(m,encoding='utf-8')

# --- UI: scan normalization, bounded retry state, stale callback fencing, 100-row pages. ---
s=OPS.read_text(encoding='utf-8')
if MARK not in s:
    field='''    private var liveEmployeeMnv=""\n'''
    if field not in s: raise SystemExit('S39 employee generation field anchor missing')
    s=s.replace(field,field+'    private var employeeLookupGeneration=0L // S39_EMPLOYEE_SESSION_HISTORY\n',1)

    load=r'''    // S39_EMPLOYEE_SESSION_HISTORY: normalized master-backed MNV + stale callback fence.
    private fun loadEmployee(mnv: String, button: Button? = null) {
        val resolved=MasterDataCache.resolveEmployeeMnv(this,mnv)
        if(resolved.isBlank()){button?.isEnabled=true;showError("MNV_REQUIRED");return}
        val generation=++employeeLookupGeneration
        val cached=MasterDataCache.employee(this,resolved)
        if(cached!=null&&(screenState=="SCAN"||screenState=="EMPLOYEE"||screenState=="EMPLOYEE_LOOKUP_ERROR"))renderCachedEmployee(cached)
        api.call("employee_context",JSONObject().put("mnv",resolved).put("include_options",true).put("include_labor",false)){result->runOnUiThread{
            if(generation!=employeeLookupGeneration)return@runOnUiThread
            button?.isEnabled=true
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){
                if(cached!=null)renderEmployeeLookupRetry(cached,resolved,result.error?:"Không xác nhận được trạng thái phiên từ Service")
                else {screenState="SCAN";showError(result.error?:"Không kiểm tra được mã nhân viên")}
                return@runOnUiThread
            }
            val ctx=result.json?:JSONObject();val options=ctx.optJSONObject("options")?:MasterDataCache.resourceOptions(this@OperationsActivity)
            renderEmployee(ctx,options)
        }}
    }'''
    s=replace_fun(s,'loadEmployee(mnv: String, button: Button? = null) {',load)

    cached=r'''    private fun renderCachedEmployee(e: JSONObject) {
        screenState="EMPLOYEE_LOADING";val cachedMnv=e.optString("mnv")
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"));val body=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(58))}
        val scan=mnvInput("Quét QR hoặc nhập mã nhân viên").apply{setText("")};body.addView(labelled("Mã nhân viên",scan));body.addView(gap(9));body.addView(employeeCard(e));body.addView(gap(9));body.addView(status("ĐANG XÁC NHẬN TRẠNG THÁI PHIÊN...",blue,Color.rgb(237,244,255)))
        var busy=false;fun submit(){val v=scan.text.toString();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);scan.postDelayed({busy=false},500)};bindScannerEnter(scan){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()
        liveEmployeeMnv=cachedMnv
    }'''
    s=replace_fun(s,'renderCachedEmployee(e: JSONObject) {',cached)

    retry=r'''    private fun renderEmployeeLookupRetry(e: JSONObject, mnv: String, reason: String) {
        screenState="EMPLOYEE_LOOKUP_ERROR";liveEmployeeMnv=mnv
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"));val body=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(58))}
        val scan=mnvInput("Quét QR hoặc nhập mã nhân viên").apply{setText("")};body.addView(labelled("Mã nhân viên",scan));body.addView(gap(9));body.addView(employeeCard(e));body.addView(gap(9))
        body.addView(status("CHƯA XÁC NHẬN ĐƯỢC PHIÊN",orange,Color.rgb(255,251,235)));body.addView(gap(6));body.addView(info("Dữ liệu nhân sự đã có trên PDA nhưng Service chưa trả được trạng thái phiên. Mã lỗi: ${reason.take(100)}"));body.addView(gap(8))
        body.addView(primary("THỬ XÁC NHẬN LẠI",navy){loadEmployee(mnv)},matchWrap())
        var busy=false;fun submit(){val v=scan.text.toString();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);scan.postDelayed({busy=false},500)};bindScannerEnter(scan){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()
    }'''
    # insert helper before renderEmployee to keep replace_fun boundaries intact
    anchor='    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {'
    if anchor not in s: raise SystemExit('S39 retry helper anchor missing')
    s=s.replace(anchor,retry+'\n\n'+anchor,1)

    # True paging: never inflate more than 100 history cards at one time.
    hist_start=s.find('    private fun historyScreen(){')
    hist_end=s.find('\n    private fun historyTimeline(',hist_start)
    if hist_start<0 or hist_end<0: raise SystemExit('S39 history block anchor missing')
    hist=s[hist_start:hist_end]
    hist=hist.replace('var pageSize=60;var query=""','val pageSize=100;var pageStart=0;var query=""',1)
    hist=hist.replace('val visible=filtered.take(pageSize)','if(pageStart>=filtered.size&&pageStart>0)pageStart=((filtered.size-1).coerceAtLeast(0)/pageSize)*pageSize;val visible=filtered.drop(pageStart).take(pageSize)',1)
    old_more='''if(visible.isEmpty())box.addView(info("Không có lịch sử phù hợp."));if(filtered.size>visible.size)box.addView(primary("XEM THÊM ${filtered.size-visible.size}",teal){pageSize+=60;render()},matchWrap())'''
    new_more='''if(visible.isEmpty())box.addView(info("Không có lịch sử phù hợp."));if(filtered.isNotEmpty()){val from=pageStart+1;val to=(pageStart+visible.size).coerceAtMost(filtered.size);box.addView(info("Đang hiển thị $from–$to / ${filtered.size} • tối đa 100 bản ghi mỗi trang."));val nav=row(bg);if(pageStart>0)nav.addView(smallButton("‹ 100 TRƯỚC",navy).apply{setOnClickListener{pageStart=(pageStart-pageSize).coerceAtLeast(0);render()}},LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(3)});if(pageStart+pageSize<filtered.size)nav.addView(smallButton("100 TIẾP ›",teal).apply{setOnClickListener{pageStart+=pageSize;render()}},LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(3)});if(nav.childCount>0)box.addView(nav,matchWrap())}'''
    if old_more not in hist: raise SystemExit('S39 history load-more anchor missing')
    hist=hist.replace(old_more,new_more,1)
    hist=hist.replace('allBtn.setOnClickListener{filter="ALL";pageSize=60;render()};pendingBtn.setOnClickListener{filter="PENDING";pageSize=60;render()};failBtn.setOnClickListener{filter="FAILED";pageSize=60;render()}','allBtn.setOnClickListener{filter="ALL";pageStart=0;render()};pendingBtn.setOnClickListener{filter="PENDING";pageStart=0;render()};failBtn.setOnClickListener{filter="FAILED";pageStart=0;render()}',1)
    hist=hist.replace('query=v?.toString().orEmpty();pageSize=60;render()','query=v?.toString().orEmpty();pageStart=0;render()',1)
    hist=hist.replace('pageSize=60;if(query.isBlank())render()','pageStart=0;if(query.isBlank())render()',1)
    s=s[:hist_start]+hist+s[hist_end:]
OPS.write_text(s,encoding='utf-8')

# --- Background-only Service session repair for durable outbox. ---
t=TRANSPORT.read_text(encoding='utf-8')
if MARK not in t:
    a=t.find('    fun flushOutbox(): Boolean {')
    b=t.find('\n    fun cachedDiscoverySnapshot(): JSONObject?',a)
    if a<0 or b<0: raise SystemExit('S39 flushOutbox region anchor missing')
    flush=r'''    /** S39_EMPLOYEE_SESSION_HISTORY: background-only Service session recovery; UI hot path stays SQLite-first. */
    fun flushOutbox(): Boolean {
        if (!hasNetwork()) return false
        var discovery=cachedDiscoverySnapshot();if(discovery==null)discovery=discover(force=true);if(discovery==null)return false
        if(discovery.optString("authority_mode")=="GOOGLE_FALLBACK")return flushFallbackItems(store.pendingMutations(100))
        if(discovery.optString("authority_mode")!="SERVICE_PRIMARY")return false
        val items=store.pendingMutations(100);if(items.isEmpty())return true
        if(circuitOpen()){
            if(failureCount()>=FALLBACK_PROBE_FAILURES&&fallbackProbeDue()){val confirmed=discover(force=true);noteFallbackProbe();if(confirmed?.optString("authority_mode")=="GOOGLE_FALLBACK")return flushFallbackItems(items)}
            return false
        }
        val base=discovery.optString("service_url").trimEnd('/');if(!validServiceUrl(base))return false
        var token=prefs.getString(KEY_SERVICE_TOKEN,null)
        if(token.isNullOrBlank()){token=exchangeBackgroundServiceSession(base);if(token.isNullOrBlank()){items.forEach{store.markMutationRetry(it.eventId,"SERVICE_SESSION_REAUTH_REQUIRED",retryDelay(it.attemptCount))};return false}}
        fun submit(bearer:String):HttpResult{val body=JSONObject().put("events",JSONArray().apply{items.forEach{put(it.body)}});return httpJson("$base/v1/legacy-mutations/batch",body,bearer)}
        return try{
            var r=submit(token)
            if(r.code==401){prefs.edit().remove(KEY_SERVICE_TOKEN).apply();val refreshed=exchangeBackgroundServiceSession(base);if(!refreshed.isNullOrBlank())r=submit(refreshed)}
            if(r.code==401){items.forEach{store.markMutationRetry(it.eventId,"SERVICE_SESSION_REAUTH_REQUIRED",retryDelay(it.attemptCount))};return false}
            if(!r.ok||r.json==null){if(r.code>=500||r.code==-1)recordFailure();if(failureCount()>=FALLBACK_PROBE_FAILURES&&fallbackProbeDue()){val confirmed=discover(force=true);noteFallbackProbe();if(confirmed?.optString("authority_mode")=="GOOGLE_FALLBACK")return flushFallbackItems(items)};items.forEach{store.markMutationRetry(it.eventId,r.error?:"HTTP_${r.code}",retryDelay(it.attemptCount))};return false}
            val results=r.json.optJSONArray("results")?:JSONArray();val byId=items.associateBy{it.eventId};var retryNeeded=false
            for(i in 0 until results.length()){val result=results.optJSONObject(i)?:continue;val eventId=result.optString("local_event_id");val item=byId[eventId]?:continue;val error=result.optString("error_code").ifBlank{result.optJSONObject("conflict")?.toString().orEmpty()};when(result.optString("status")){"CONFIRMED","DUPLICATE"->store.markMutationSynced(eventId);"REVIEW_REQUIRED"->store.markMutationReviewRequired(eventId,error);"REJECTED"->if(result.optBoolean("retryable",false)){store.markMutationRetry(eventId,error.ifBlank{"RETRYABLE_REJECT"},retryDelay(item.attemptCount));retryNeeded=true}else store.markMutationRejected(eventId,error);else->{store.markMutationRetry(eventId,"BATCH_RESULT_INVALID",retryDelay(item.attemptCount));retryNeeded=true}}}
            val returned=HashSet<String>().apply{for(i in 0 until results.length())add(results.optJSONObject(i)?.optString("local_event_id").orEmpty())};items.filter{it.eventId !in returned}.forEach{store.markMutationRetry(it.eventId,"BATCH_RESULT_MISSING",retryDelay(it.attemptCount));retryNeeded=true};if(!retryNeeded)closeCircuit();!retryNeeded
        }catch(x:Throwable){recordFailure();items.forEach{store.markMutationRetry(it.eventId,x.message?:"NETWORK",retryDelay(it.attemptCount))};false}
    }

    private fun exchangeBackgroundServiceSession(base:String):String?{
        val gasToken=app.getSharedPreferences(AUTH_PREFS,Context.MODE_PRIVATE).getString(AUTH_TOKEN,null).orEmpty();if(gasToken.isBlank())return null
        return runCatching{
            val r=httpJson("$base/v1/auth/gas-session",JSONObject().put("gas_token",gasToken).put("device_id",M2DeviceIdentity.id(app)).put("device_label","${Build.MANUFACTURER} ${Build.MODEL}"),null)
            val token=r.json?.optString("token").orEmpty();if(r.ok&&token.isNotBlank()){prefs.edit().putString(KEY_SERVICE_TOKEN,token).apply();closeCircuit();token}else null
        }.getOrNull()
    }
'''
    t=t[:a]+flush.rstrip()+t[b:]
TRANSPORT.write_text(t,encoding='utf-8')

# Final contract checks.
o=OPS.read_text(encoding='utf-8');m2=MASTER.read_text(encoding='utf-8');tr=TRANSPORT.read_text(encoding='utf-8')
checks=[
    (MARK in o,'ops marker'),('resolveEmployeeMnv' in m2,'mnv resolver'),('employeeLookupGeneration' in o,'stale callback fence'),
    ('CHƯA XÁC NHẬN ĐƯỢC PHIÊN' in o,'bounded retry UI'),('val pageSize=100;var pageStart=0' in o,'history page size 100'),
    ('drop(pageStart).take(pageSize)' in o,'history true paging'),('exchangeBackgroundServiceSession' in tr,'background session exchange'),
    ('SERVICE_SESSION_REAUTH_REQUIRED' in tr,'reauth retry classification')]
for ok,label in checks:
    if not ok: raise SystemExit('S39 contract missing: '+label)
if 'pageSize+=60' in o: raise SystemExit('S39 old cumulative History paging survived')
print('Applied S39: master-backed scan normalization, bounded session verify, background reauth, true 100-row History pages')

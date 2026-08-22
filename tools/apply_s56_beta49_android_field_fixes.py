#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
LOGS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/LocalLogManager.kt'
TRANSPORT=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2ServiceTransport.kt'
MARK='S56_BETA49_FIELD_ACCEPTANCE'


def replace_fun(src:str, signature:str, replacement:str)->str:
    a=src.find('    private fun '+signature)
    if a<0: raise SystemExit('S56 function anchor missing: '+signature)
    b=src.find('\n    private fun ',a+20)
    if b<0: raise SystemExit('S56 next function anchor missing: '+signature)
    return src[:a]+replacement.rstrip()+'\n'+src[b:]

s=OPS.read_text(encoding='utf-8')
if MARK not in s:
    load=r'''    // S56_BETA49_FIELD_ACCEPTANCE: resource selection is always based on a fresh Service read, never stale master cache.
    private fun loadEmployee(mnv: String, button: Button? = null) {
        val cached=MasterDataCache.employee(this,mnv)
        if(cached!=null&&screenState=="SCAN")renderCachedEmployee(cached)
        api.call("employee_context",JSONObject().put("mnv",mnv).put("include_options",false).put("include_labor",false)){result->runOnUiThread{
            button?.isEnabled=true;button?.text="KIỂM TRA"
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){showError(result.error?:"Không kiểm tra được MNV");return@runOnUiThread}
            val ctx=result.json?:JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED"){
                api.call("master_options",JSONObject().put("mnv",mnv)){masters->runOnUiThread{
                    if(masters.code==401){sessionExpired();return@runOnUiThread}
                    if(!masters.ok||masters.json==null){showError(masters.error?:"Không lấy được tài nguyên khả dụng từ Service. Không thể phát tài nguyên từ cache cũ.");return@runOnUiThread}
                    renderEmployee(ctx,masters.json)
                }}
            }else renderEmployee(ctx,null)
        }}
    }'''
    s=replace_fun(s,'loadEmployee(',load)

    enter=r'''    // S56_BETA49_LIVE_RESOURCE_ENTER_V1: no duplicate-user/reissue path; PACK mappings are independent of attendance shift.
    private fun renderEnter(body:LinearLayout,ctx:JSONObject,masters:JSONObject){
        val e=ctx.optJSONObject("employee")?:JSONObject();val mnv=e.optString("mnv")
        body.addView(section("PHÂN CÔNG TRONG CA"))
        val now=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh"));var shiftValue=when{now.isBefore(java.time.LocalTime.of(8,0))->"Ca 1";now.isBefore(java.time.LocalTime.of(10,0))->"Ca HC";else->"Ca 2"}
        var workValue=when{e.optString("main_position").trim().equals("Pick",true)->"PICK";e.optString("main_position").trim().equals("Pack",true)->"PACK";else->"KHONG"}
        val resourceBox=column(bg);val shiftBox=column(bg);val workBox=column(bg);var rebuild:(()->Unit)?=null
        shiftBox.addView(segmentedChoice(listOf("Ca 1" to "Ca 1","Ca HC" to "Ca HC","Ca 2" to "Ca 2"),shiftValue){shiftValue=it},matchWrap())
        workBox.addView(segmentedChoice(listOf("Không" to "KHONG","Pick" to "PICK","Pack" to "PACK"),workValue){workValue=it;rebuild?.invoke()},matchWrap())
        body.addView(labelled("Ca",shiftBox));body.addView(gap(8));body.addView(labelled("Vị trí trong ca",workBox));body.addView(gap(7));body.addView(resourceBox,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray()
        var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;val pickValues=mutableListOf<String>();var packSelection:JSONObject?=null
        fun renderPick(){
            pdaField=pdaInput(pdas);resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(4));resourceBox.addView(pdaSelectedPanel(pdas,pdaField!!));resourceBox.addView(gap(7))
            val labels=mutableListOf("Không dùng User hy1.outbound");pickValues.clear();pickValues.add("");for(i in 0 until picks.length()){val id=picks.optString(i).trim();if(id.isNotBlank()&&!pickValues.contains(id)){pickValues.add(id);labels.add(id)}};pickSpinner=spinner(labels.toTypedArray());resourceBox.addView(labelled("User Pick",pickSpinner!!))
        }
        fun renderPack(){
            val rows=mutableListOf<JSONObject>();for(i in 0 until packs.length()){val o=packs.optJSONObject(i)?:continue;val table=o.optString("table").trim();val user=o.optString("user_pack").trim();if(table.isNotBlank()&&user.isNotBlank()&&!rows.any{it.optString("table")==table&&it.optString("user_pack")==user})rows.add(JSONObject(o.toString()))}
            val tables=rows.map{it.optString("table")}.filter{it.isNotBlank()}.distinct();val tableSp=spinner((if(tables.isEmpty())listOf("Không có bàn Pack khả dụng")else tables).toTypedArray());resourceBox.addView(labelled("Bàn Pack",tableSp));resourceBox.addView(gap(7));val userHost=column(bg);resourceBox.addView(userHost,matchWrap())
            fun renderUsers(){userHost.removeAllViews();packSelection=null;if(tables.isEmpty()){userHost.addView(info("Không có User Pack khả dụng."));return};val table=tables.getOrNull(tableSp.selectedItemPosition).orEmpty();val mapped=rows.filter{it.optString("table")==table};val labels=mapped.map{"${it.optString("user_pack")} • ${it.optString("shift").ifBlank{"Không ghi ca mapping"}}"};val userSp=spinner((if(labels.isEmpty())listOf("Không có User Pack")else labels).toTypedArray());if(mapped.isNotEmpty())packSelection=mapped[0];userSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){packSelection=mapped.getOrNull(pos)};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};userHost.addView(labelled("User Pack theo bàn — cả hai ca",userSp))}
            tableSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderUsers()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};renderUsers()
        }
        rebuild={resourceBox.removeAllViews();pdaField=null;pickSpinner=null;pickValues.clear();packSelection=null;when(workValue){"PICK"->renderPick();"PACK"->renderPack();else->Unit}};rebuild?.invoke();body.addView(gap(10))
        val enterBtn=primary("VÀO CA",teal){}
        enterBtn.setOnClickListener{
            val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shiftValue).put("work_choice",workValue)
            if(workValue=="PICK"){
                val raw=pdaField?.text?.toString().orEmpty();val p=resolvePdaObject(pdas,raw);if(p==null){showError("PDA không còn hợp lệ. Gõ 5 số cuối và chọn lại PDA trong danh sách.");return@setOnClickListener};payload.put("pda_serial",p.optString("serial")).put("pda_status_at_enter",p.optString("status"));val pick=pickValues.getOrNull(pickSpinner?.selectedItemPosition?:0).orEmpty();if(pick.isNotBlank())payload.put("user_pick",pick)
            }
            if(workValue=="PACK"){
                val row=packSelection;if(row==null){showError("Chọn Bàn Pack và User Pack hợp lệ.");return@setOnClickListener};payload.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"))
            }
            enterBtn.isEnabled=false;enterBtn.text="ĐANG KIỂM TRA TÀI NGUYÊN..."
            api.call("employee_context",JSONObject().put("mnv",mnv).put("include_options",true).put("include_labor",false)){pre->runOnUiThread{
                if(pre.code==401){enterBtn.isEnabled=true;sessionExpired();return@runOnUiThread};val freshCtx=pre.json
                if(!pre.ok||freshCtx==null){enterBtn.isEnabled=true;enterBtn.text="VÀO CA";showError(pre.error?:"Không kiểm tra được tài nguyên trên Service.");return@runOnUiThread}
                if(freshCtx.optString("state")!="NOT_ENTERED"){enterBtn.isEnabled=true;enterBtn.text="VÀO CA";loadEmployee(mnv);showError("Trạng thái MNV vừa thay đổi. Đã tải lại dữ liệu mới nhất.");return@runOnUiThread}
                val fresh=freshCtx.optJSONObject("options")?:JSONObject();var valid=true
                if(workValue=="PICK"){
                    val serial=payload.optString("pda_serial");val fp=fresh.optJSONArray("pdas")?:JSONArray();valid=(0 until fp.length()).any{fp.optJSONObject(it)?.optString("serial")==serial};val user=payload.optString("user_pick");if(valid&&user.isNotBlank()){val fu=fresh.optJSONArray("user_picks")?:JSONArray();valid=(0 until fu.length()).any{fu.optString(it)==user}}
                }
                if(workValue=="PACK"){
                    val table=payload.optString("pack_table"),user=payload.optString("user_pack");val fa=fresh.optJSONArray("pack_tables")?:JSONArray();valid=(0 until fa.length()).any{val o=fa.optJSONObject(it);o?.optString("table")==table&&o.optString("user_pack")==user}
                }
                if(!valid){enterBtn.isEnabled=true;enterBtn.text="VÀO CA";TopNotice.show(this,"Tài nguyên vừa được sử dụng/giữ ở phiên khác. Danh sách đã được làm mới.",TopNotice.Kind.WARNING);renderEmployee(freshCtx,fresh);return@runOnUiThread}
                enterBtn.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enterBtn.isEnabled=true;enterBtn.text="VÀO CA";if(!r.ok){showError(r.error?:"VÀO CA thất bại");loadEmployee(mnv)}else loadEmployee(mnv)}}
            }}
        }
        body.addView(enterBtn,matchWrap())
    }'''
    s=replace_fun(s,'renderEnter(',enter)

    # S49 introduced a second resource editor. Force it to use live Service options and keep all Pack mapping shifts.
    a=s.find('    private fun sessionWorkEditor(ctx:JSONObject){')
    if a<0: raise SystemExit('S56 sessionWorkEditor anchor missing')
    b=s.find('\n    private fun ',a+20)
    if b<0: raise SystemExit('S56 sessionWorkEditor end missing')
    block=s[a:b]
    old='val options=PdaLocalProjection.resourceOptions(this,mnv);'
    if old not in block: raise SystemExit('S56 session editor local options anchor missing')
    block=block.replace(old,'',1)
    block=block.replace('if(o.optString("shift")!=ses.optString("shift"))continue;','')
    renamed=block.replace('    private fun sessionWorkEditor(ctx:JSONObject){','    private fun sessionWorkEditorWithOptions(ctx:JSONObject,options:JSONObject){',1)
    wrapper=r'''    private fun sessionWorkEditor(ctx:JSONObject){
        val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv");if(mnv.isBlank())return
        api.call("master_options",JSONObject().put("mnv",mnv)){r->runOnUiThread{
            if(r.code==401){sessionExpired();return@runOnUiThread};if(!r.ok||r.json==null){showError(r.error?:"Không lấy được tài nguyên khả dụng từ Service. Không thể sửa từ cache cũ.");return@runOnUiThread};sessionWorkEditorWithOptions(ctx,r.json)
        }}
    }
'''
    s=s[:a]+wrapper+renamed+s[b:]

    sync=r'''    // S56_BETA49_FIELD_ACCEPTANCE: concise sync screen; OWNER removed connected-users section.
    private fun syncScreen(){
        module="SYNC";screenState="SYNC";val root=baseRoot("ĐỒNG BỘ");val body=body();val overview=column(surface).apply{setPadding(dp(14),dp(11),dp(14),dp(11));background=outlineBg(surface,18)};val overviewTitle=txt("Đang kiểm tra trạng thái...",14f,navy,true);val overviewSub=txt("Đang kiểm tra thiết bị và Service.",10f,muted,false);overview.addView(overviewTitle);overview.addView(gap(4));overview.addView(overviewSub);body.addView(overview,matchWrap());body.addView(gap(8));val deviceBox=column(bg);val serviceBox=column(bg);val appBox=column(bg);body.addView(deviceBox,matchWrap());body.addView(serviceBox,matchWrap());body.addView(appBox,matchWrap());val actions=row(bg);val syncNow=smallButton("ĐỒNG BỘ NGAY",teal);val refresh=smallButton("LÀM MỚI",navy);actions.addView(syncNow,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(4)});actions.addView(refresh,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(4)});body.addView(gap(8));body.addView(actions,matchWrap())
        fun dateVi(v:String)=runCatching{java.time.LocalDate.parse(v.take(10)).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(v.ifBlank{"—"});fun timeVi(v:String)=if(v.isBlank())"—" else formatIso(v);fun authorityVi(v:String)=when(v.uppercase()){ "SERVICE_PRIMARY"->"Dịch vụ chính";"GOOGLE_FALLBACK"->"Google dự phòng";"RECONCILING"->"Đang đối chiếu dữ liệu";"OFFLINE_LOCAL"->"Chỉ lưu trên PDA";else->"Chưa xác định" };fun replicaVi(v:String)=when(v.uppercase()){ "SYNCED","HEALTHY","OK"->"Đã đồng bộ";"PENDING","INFLIGHT","RUNNING"->"Đang chuyển dữ liệu";"RETRY"->"Đang chờ gửi lại";"ERROR","FAILED","DEGRADED"->"Có lỗi / đang gửi lại";else->if(v.isBlank())"Chưa có dữ liệu" else "Đang theo dõi" }
        fun loadDevice(){deviceBox.removeAllViews();val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0);val active=runCatching{SyncDirectionTracker.snapshot().active}.getOrDefault(false);val dates=runCatching{operationalStore.availableDates()}.getOrDefault(emptyList());val net=DeviceNetworkStatus.snapshot(this);val network=net.header(lastLatencyMs);val syncText=when{pending>0->"Còn $pending mục chờ gửi";active->"Đang trao đổi dữ liệu";else->"Đã gửi hết dữ liệu trên PDA"};overviewTitle.text=when{lastConnected==false->"Chưa kết nối được Service";pending>0->"Còn $pending mục chờ gửi";else->"Hệ thống đang hoạt động"};overviewTitle.setTextColor(if(lastConnected==false)red else if(pending>0)orange else teal);overviewSub.text="$syncText • $network";deviceBox.addView(section("TRÊN THIẾT BỊ"));deviceBox.addView(details(listOf("Kết nối mạng" to network,"Trạng thái gửi từ PDA" to syncText,"Dữ liệu chờ gửi" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Luồng trao đổi dữ liệu" to if(active)"Đang hoạt động" else "Đang nghỉ","Ngày nghiệp vụ hiện tại" to dateVi(operationalStore.businessDate()),"Ngày dữ liệu mới nhất trên PDA" to dateVi(dates.firstOrNull().orEmpty()))));deviceBox.addView(gap(7))}
        fun loadService(){serviceBox.removeAllViews();serviceBox.addView(section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM"));serviceBox.addView(info("Đang kiểm tra Service..."));val started=android.os.SystemClock.elapsedRealtime();api.call("sync_status",JSONObject()){r->runOnUiThread{if(screenState!="SYNC")return@runOnUiThread;serviceBox.removeAllViews();serviceBox.addView(section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM"));val rt=(android.os.SystemClock.elapsedRealtime()-started).coerceAtLeast(0);lastLatencyMs=rt;if(!r.ok||r.json==null){lastConnected=false;refreshHeaderConnection();serviceBox.addView(details(listOf("Dịch vụ" to "Chưa phản hồi","Độ trễ lần kiểm tra" to "$rt ms","Dữ liệu trên PDA" to "Vẫn được lưu an toàn","Trạng thái gửi" to "Sẽ thử lại khi có kết nối")));serviceBox.addView(gap(7));loadDevice();return@runOnUiThread};lastConnected=true;refreshHeaderConnection();val j=r.json?:JSONObject();val a=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject();serviceBox.addView(details(listOf("Dịch vụ" to "Đang hoạt động","Độ trễ tới Service" to "$rt ms","Nguồn dữ liệu đang dùng" to authorityVi(a.optString("mode").ifBlank{j.optString("authority_mode")}),"Mốc dữ liệu hệ thống" to a.optLong("authority_seq",j.optLong("server_seq",0L)).toString(),"Bản sao Google" to replicaVi(rep.optString("state")),"Bản sao Google còn chờ" to rep.optInt("pending_count",j.optInt("projection_pending",0)).toString(),"Lần sao chép thành công" to timeVi(rep.optString("last_success_at")))));serviceBox.addView(gap(7));loadDevice()}}}
        fun loadApp(){appBox.removeAllViews();appBox.addView(section("ỨNG DỤNG"));val deviceName="${Build.MANUFACTURER} ${Build.MODEL}".trim();appBox.addView(details(listOf("Tên thiết bị" to deviceName,"Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,"Mã phiên bản" to BuildConfig.VERSION_CODE.toString())));appBox.addView(gap(7));appBox.addView(section("NHẬT KÝ"));appBox.addView(details(listOf("Nhật ký trên thiết bị" to LocalLogManager.summary(this))))}
        fun load(){loadDevice();loadApp();loadService()};syncNow.setOnClickListener{foregroundSync.requestSync();flushDeferredHistoryDeletes();TopNotice.show(this,"Đã yêu cầu gửi dữ liệu đang chờ.",TopNotice.Kind.INFO);android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({if(screenState=="SYNC")load();flushDeferredHistoryDeletes()},900L)};refresh.setOnClickListener{load()};attach(root,body);load()
    }'''
    s=replace_fun(s,'syncScreen(){',sync)
    s=s.replace('class OperationsActivity : Activity() {\n    // S54_BETA48_OWNER_10_FIXES','class OperationsActivity : Activity() {\n    // S56_BETA49_FIELD_ACCEPTANCE\n    // S54_BETA48_OWNER_10_FIXES',1)
    for forbidden in ['NGƯỜI DÙNG ĐANG KẾT NỐI','service_connections','Tổng phiên đang kết nối','PHÁT LẠI USER ĐANG DÙNG','TRÙNG USER','duplicate_user']:
        if forbidden in s: raise SystemExit('S56 forbidden UI/duplicate flow remains: '+forbidden)
    if 'MasterDataCache.resourceOptions(this@OperationsActivity)' in s or 'PdaLocalProjection.resourceOptions(this,mnv)' in s: raise SystemExit('S56 stale resource path remains')
    if 'if(o.optString("shift")!=ses.optString("shift"))continue;' in s: raise SystemExit('S56 session PACK shift filter remains')
    OPS.write_text(s,encoding='utf-8')

# Remove obsolete connected-users transport action added by S54.
t=TRANSPORT.read_text(encoding='utf-8');t=t.replace('val r = if(action=="service_connections") httpGetJson("$base/v1/service/connections",token) else httpJson("$base/v1/legacy-sync", request, token)','val r = httpJson("$base/v1/legacy-sync", request, token)');t=t.replace(', "service_connections")',')').replace('"service_connections", ','');TRANSPORT.write_text(t,encoding='utf-8')

# Truthful lifetime + pending-file log accounting.
l=LOGS.read_text(encoding='utf-8')
if 'S56_BETA49_LOG_ACCOUNTING_V1' not in l:
    l=l.replace('    private const val KEY_DAILY = "last_daily_log"\n','    private const val KEY_DAILY = "last_daily_log"\n    private const val KEY_GENERATED_BYTES = "generated_bytes"\n    private const val KEY_SENT_BYTES = "sent_bytes"\n    private const val KEY_LAST_BYTES = "last_bytes"\n    private const val KEY_LAST_AT = "last_at"\n',1)
    a=l.find('    fun summary(context:Context):String{');b=l.find('\n    fun sendManualReport(',a)
    if a<0 or b<0: raise SystemExit('S56 log summary anchors missing')
    summary=r'''    // S56_BETA49_LOG_ACCOUNTING_V1
    fun summary(context:Context):String{
        val files=logDir(context).listFiles()?.filter{it.isFile}.orEmpty();val pendingBytes=files.sumOf{it.length()};val prefs=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);val generated=prefs.getLong(KEY_GENERATED_BYTES,0L);val sent=prefs.getLong(KEY_SENT_BYTES,0L);val lastBytes=prefs.getLong(KEY_LAST_BYTES,0L);val lastAt=prefs.getLong(KEY_LAST_AT,0L)
        fun size(v:Long)=when{v<1024L->"$v B";v<1024L*1024L->String.format(Locale.US,"%.1f KB",v/1024.0);else->String.format(Locale.US,"%.1f MB",v/(1024.0*1024.0))};val at=if(lastAt<=0L)"—" else SimpleDateFormat("HH:mm:ss dd/MM/yyyy",Locale.US).format(Date(lastAt));return "Đang lưu ${files.size} tệp • ${size(pendingBytes)} | Đã ghi ${size(generated)} | Đã gửi ${size(sent)} | Gần nhất ${size(lastBytes)} • $at"
    }
'''
    l=l[:a]+summary+l[b:]
    old='        uploadFile(api, file, "MANUAL") { r -> if (r.ok) file.delete(); callback(r) }';new='        uploadFile(api, file, "MANUAL") { r -> if (r.ok) { recordSent(context,file.length()); file.delete() }; callback(r) }'
    if old not in l: raise SystemExit('S56 manual log upload anchor missing');l=l.replace(old,new,1)
    old='            if (r.ok) f.delete()';new='            if (r.ok) { recordSent(context,f.length()); f.delete() }'
    if old not in l: raise SystemExit('S56 automatic log upload anchor missing');l=l.replace(old,new,1)
    old='''    private fun write(context: Context, prefix: String, content: String): File {
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())
        return File(logDir(context), "${prefix}_${stamp}.log").apply { writeText(content) }
    }''';new='''    private fun recordSent(context:Context,bytes:Long){val p=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);p.edit().putLong(KEY_SENT_BYTES,p.getLong(KEY_SENT_BYTES,0L)+bytes).apply()}
    private fun write(context:Context,prefix:String,content:String):File{val stamp=SimpleDateFormat("yyyyMMdd_HHmmss_SSS",Locale.US).format(Date());val file=File(logDir(context),"${prefix}_${stamp}.log").apply{writeText(content)};val bytes=file.length();val p=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);p.edit().putLong(KEY_GENERATED_BYTES,p.getLong(KEY_GENERATED_BYTES,0L)+bytes).putLong(KEY_LAST_BYTES,bytes).putLong(KEY_LAST_AT,System.currentTimeMillis()).apply();return file}'''
    if old not in l: raise SystemExit('S56 log write anchor missing');l=l.replace(old,new,1);LOGS.write_text(l,encoding='utf-8')

print('Applied S56 Beta49 Android field-acceptance fixes')

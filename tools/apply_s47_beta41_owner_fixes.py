#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S47_BETA41_OWNER_FIVE_FIXES'

def replace_private_fun(src:str, signature:str, replacement:str)->str:
    start=src.find('    private fun '+signature)
    if start<0:
        raise SystemExit('S47 function anchor missing: '+signature)
    end=src.find('\n    private fun ',start+20)
    if end<0:
        raise SystemExit('S47 next function anchor missing: '+signature)
    return src[:start]+replacement.rstrip()+'\n'+src[end:]

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S47 already applied')
    raise SystemExit(0)

# 1) Global swipe/back semantics + root-tab history.
field='    private lateinit var role: String\n'
if field not in s: raise SystemExit('S47 role field anchor missing')
s=s.replace(field,field+'    private var effectiveRole = "" // '+MARK+'\n',1)
nav_field='    private val navRefs=mutableMapOf<String,NavRefs>()\n'
if nav_field not in s: raise SystemExit('S47 nav history field anchor missing')
s=s.replace(nav_field,nav_field+'    private val tabHistory=java.util.ArrayDeque<String>()\n',1)
role_init='        role = intent.getStringExtra("role") ?: "USER"\n'
if role_init not in s: raise SystemExit('S47 role init anchor missing')
s=s.replace(role_init,role_init+'        effectiveRole = role\n',1)

admin=r'''    private fun isAdmin() = effectiveRole == "ADMIN" || effectiveRole == "SUPERADMIN"'''
s=replace_private_fun(s,'isAdmin() =',admin)
super_fn=r'''    private fun isSuper() = effectiveRole == "SUPERADMIN"
    private fun isActualSuper() = role == "SUPERADMIN"'''
s=replace_private_fun(s,'isSuper() =',super_fn)

s=s.replace('roleText(role)','roleText(effectiveRole)')
s=s.replace('position.ifBlank{roleText(effectiveRole)}','if(isActualSuper()&&effectiveRole!=role)"Đang dùng quyền ${roleText(effectiveRole)}" else position.ifBlank{roleText(effectiveRole)}')

isroot=r'''    private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="SETTINGS"||screenState=="ROLE_MODE"'''
s=replace_private_fun(s,'isRootScreen()=',isroot)
active=r'''    private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"SETTINGS"->"SETTINGS";"ROLE_MODE"->"ROLE_MODE";else->"BUSINESS"}'''
s=replace_private_fun(s,'activeTab()=',active)
nav=r'''    private fun bottomNav():LinearLayout=row(surface).apply{
        gravity=Gravity.CENTER;setPadding(dp(3),dp(5),dp(3),dp(5));background=outlineBg(surface,16);elevation=dp(8).toFloat();navRefs.clear()
        val items=mutableListOf(
            Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),
            Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),
            Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),
            Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC"),
            Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS")
        )
        if(isActualSuper())items.add(Triple(R.drawable.ic_pp_settings,"Quyền","ROLE_MODE"))
        items.forEach{item->
            val iconView=ImageView(this@OperationsActivity).apply{setImageResource(item.first);setPadding(dp(4),dp(4),dp(4),dp(2))}
            val labelView=txt(item.second,7.2f,muted,item.third==activeTab()).apply{gravity=Gravity.CENTER;maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,9,1,android.util.TypedValue.COMPLEX_UNIT_SP)}
            val cell=column(Color.TRANSPARENT).apply{gravity=Gravity.CENTER;setPadding(dp(1),dp(2),dp(1),dp(2));addView(iconView,size(dp(30),dp(27)));addView(labelView);setOnClickListener{navigateTab(item.third)}}
            navRefs[item.third]=NavRefs(cell,iconView,labelView);addView(cell,LinearLayout.LayoutParams(0,-1,1f))
        };post{refreshBottomNav()}
    }'''
s=replace_private_fun(s,'bottomNav():LinearLayout=',nav)
navigate=r'''    private fun navigateTab(target:String,remember:Boolean=true){
        val current=activeTab()
        if(target==current&&isRootScreen())return
        if(remember&&target!=current)tabHistory.addLast(current)
        module=target;initialMnv="";liveEmployeeMnv=""
        when(target){
            "BUSINESS"->businessHome()
            "STAFF"->staffScreen()
            "HISTORY"->historyScreen()
            "SYNC"->syncScreen()
            "SETTINGS"->settingsScreen()
            "ROLE_MODE"->if(isActualSuper())roleModeScreen() else businessHome()
        }
    }'''
s=replace_private_fun(s,'navigateTab(target:String){',navigate)
back=r'''    private fun navigateBack(){
        when(screenState){
            "LABOR_CONTEXT"->laborHome()
            "RESOURCE_EDITOR","RESOURCE_LIST"->resourceHome()
            "ACCOUNT_MANAGER"->settingsScreen()
            "EMPLOYEE","EMPLOYEE_LOADING","EMPLOYEE_LOOKUP_ERROR"->employeeScan()
            "SCAN","LABOR_HOME","RESOURCE_HOME","REPORT","LISTS","PDA_EXCHANGE"->businessHome()
            "HISTORY_DETAIL"->historyScreen()
            else->{
                if(isRootScreen()&&tabHistory.isNotEmpty()){
                    val previous=tabHistory.removeLast()
                    navigateTab(previous,false)
                }else if(module!="BUSINESS"){
                    module="BUSINESS";businessHome()
                }else finish()
            }
        }
    }'''
s=replace_private_fun(s,'navigateBack(){',back)

session_anchor='    private fun sessionExpired(){'
if session_anchor not in s: raise SystemExit('S47 role mode insertion anchor missing')
role_mode=r'''    private fun roleModeScreen(){
        if(!isActualSuper()){module="BUSINESS";businessHome();return}
        module="ROLE_MODE";screenState="ROLE_MODE"
        val root=baseRoot("CHẾ ĐỘ QUYỀN");val body=body()
        body.addView(section("Quyền giao diện đang áp dụng"))
        body.addView(info("Đang hiển thị ứng dụng theo quyền: ${roleText(effectiveRole)}"))
        body.addView(gap(9))
        body.addView(primary("ÁP QUYỀN USER",teal){effectiveRole="USER";TopNotice.show(this,"Đã chuyển giao diện sang quyền USER.",TopNotice.Kind.SUCCESS);navigateTab("BUSINESS")},matchWrap())
        body.addView(gap(8))
        body.addView(primary("ÁP QUYỀN ADMIN",blue){effectiveRole="ADMIN";TopNotice.show(this,"Đã chuyển giao diện sang quyền ADMIN.",TopNotice.Kind.SUCCESS);navigateTab("BUSINESS")},matchWrap())
        body.addView(gap(8))
        body.addView(primary("QUAY VỀ QUYỀN SUPERADMIN",navy){effectiveRole="SUPERADMIN";TopNotice.show(this,"Đã quay về quyền SUPERADMIN.",TopNotice.Kind.SUCCESS);navigateTab("BUSINESS")},matchWrap())
        attach(root,body)
    }

'''
s=s.replace(session_anchor,role_mode+session_anchor,1)
acct='for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;'
if acct in s: s=s.replace(acct,acct+'if(!isSuper()&&x.optString("role")!="USER")continue;',1)

# 2) Exit PDA condition only for sessions that entered with PDA.
active_exit=r'''    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv")
        fun clean(v:String)=v.trim().takeUnless{it.equals("null",true)||it=="—"}?:""
        val pda=clean(ses.optString("pda_serial"));val initialStatus=clean(ses.optString("pda_enter_status"));val resourceNote=ses.optString("resource_note")
        val enteredWithPda=pda.isNotBlank()&&initialStatus.isNotBlank()
        body.addView(section("PHÂN CÔNG TRONG CA"));body.addView(details(listOf(
            "Ca" to ses.optString("shift"),"Vị trí đang làm" to workText(ses.optString("work_choice")),"Vào lúc" to formatIso(ses.optString("enter_at")),
            "Seri PDA" to dash(pda),"Tình trạng PDA lúc vào" to dash(initialStatus),"User Pick" to dash(ses.optString("user_pick")),"Bàn Pack" to dash(ses.optString("pack_table")),"User Pack" to dash(ses.optString("user_pack")),"Ghi chú tài nguyên" to dash(resourceNote)
        )));body.addView(gap(11))
        val exit=primary("RA CA",red){}
        fun callExit(statusNow:String){
            val actionGeneration=employeeLookupGeneration
            exit.isEnabled=false;exit.text="ĐANG RA CA..."
            val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv)
            if(statusNow.isNotBlank())payload.put("pda_exit_status",statusNow)
            api.call("exit",payload){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else{TopNotice.show(this,"Đã ghi nhận ra ca.",TopNotice.Kind.SUCCESS);scheduleAttendanceAutoReset(mnv,actionGeneration)}}}
        }
        exit.setOnClickListener{
            if(!enteredWithPda){AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Phiên vào ca này không có PDA cần đối chiếu tình trạng. Xác nhận kết thúc phiên hôm nay?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->callExit("")}.show();return@setOnClickListener}
            val statuses=mutableListOf<String>();val arr=ctx.optJSONObject("options")?.optJSONArray("pda_statuses")?:MasterDataCache.resourceOptions(this).optJSONArray("pda_statuses")?:JSONArray();for(i in 0 until arr.length()){val v=clean(arr.optString(i));if(v.isNotBlank()&&!statuses.contains(v))statuses.add(v)};if(!statuses.contains(initialStatus))statuses.add(0,initialStatus)
            val sp=spinner(statuses.toTypedArray());val wrap=column(surface).apply{setPadding(dp(16),dp(6),dp(16),dp(4));addView(txt("PDA: $pda",11f,navy,true));addView(gap(5));addView(txt("Tình trạng lúc vào: $initialStatus",10.2f,muted,false));addView(gap(9));addView(labelled("Xác nhận tình trạng PDA hiện tại",sp))}
            AlertDialog.Builder(this).setTitle("Xác nhận tình trạng PDA").setView(wrap).setNegativeButton("Hủy",null).setPositiveButton("KIỂM TRA & RA CA"){_,_->val now=sp.selectedItem?.toString().orEmpty();if(now!=initialStatus)showError("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST")else callExit(now)}.show()
        }
        body.addView(exit,matchWrap())
    }'''
s=replace_private_fun(s,'renderActive(body: LinearLayout, ctx: JSONObject) {',active_exit)

# 3+4) History progression line and exact full-selected-day KPI values.
metric_old='''val metricRows=if(query.isBlank())rows else run{val savedQuery=query;query="";val allRows=loadRows();query=savedQuery;allRows};val pending=metricRows.count{statusOf(it)=="PENDING"};val failed=metricRows.count{statusOf(it)=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is LinearLayout&&v.childCount>1)(v.getChildAt(1) as? TextView)?.text=n.toString()};updateMetric(allBtn,metricRows.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)'''
metric_new='''val metricRows=if(query.isBlank())rows else run{val savedQuery=query;query="";val allRows=loadRows();query=savedQuery;allRows};val pending=metricRows.count{statusOf(it)=="PENDING"};val failed=metricRows.count{statusOf(it)=="FAILED"}
            fun updateMetric(v:View,n:Int){if(v is ViewGroup){for(i in v.childCount-1 downTo 0){val child=v.getChildAt(i);if(child is TextView){child.text=n.toString();break}}}};updateMetric(allBtn,metricRows.size);updateMetric(pendingBtn,pending);updateMetric(failBtn,failed)'''
if metric_old not in s: raise SystemExit('S47 History KPI post-S45 anchor missing')
s=s.replace(metric_old,metric_new,1)
loop_start=s.find('            for(g in visible){')
loop_end=s.find('\n            if(visible.isEmpty())',loop_start)
if loop_start<0 or loop_end<0: raise SystemExit('S47 History card loop anchors missing')
loop=r'''            for(g in visible){
                val items=g.value;val first=items.first();val state=if(items.any{statusOf(it)=="FAILED"})"FAILED" else if(items.any{statusOf(it)=="PENDING"})"PENDING" else "SYNCED"
                val label=when(state){"FAILED"->"Lỗi đồng bộ";"PENDING"->"Chưa đồng bộ";else->"Đã đồng bộ"};val tint=when(state){"FAILED"->Color.rgb(254,242,242);"PENDING"->Color.rgb(255,251,235);else->Color.rgb(240,253,250)}
                val mnv=first.optString("mnv");val full=first.optString("full_name");val last=items.first();val types=items.map{it.optString("event_type").uppercase()};val progress=mutableListOf<String>()
                if(types.any{it=="ATTENDANCE_ENTER"||it=="ENTER"})progress.add("Vào ca");if(types.any{it=="LABOR_START"||it=="LABOR_FINISH"})progress.add("Công nhật");if(types.any{it=="ATTENDANCE_EXIT"||it=="EXIT"})progress.add("Ra ca")
                val progressText=progress.joinToString(" - ").ifBlank{last.optString("label").ifBlank{"Thao tác"}};val actor=last.optString("actor").ifBlank{"Hệ thống"}
                val card=column(tint).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(tint,17);val top=row(tint).apply{gravity=Gravity.CENTER_VERTICAL;addView(txt(listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ").ifBlank{"Thao tác hệ thống"},12.5f,ink,true),LinearLayout.LayoutParams(0,-2,1f));addView(badge(label,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal}))};addView(top,matchWrap());addView(gap(4));addView(txt(progressText,10.5f,navy,true));addView(txt("${formatIso(last.optString("at_iso"))} • Người thực hiện: $actor",9.8f,muted,false));if(last.optString("detail").isNotBlank())addView(txt(last.optString("detail"),9.5f,muted,false).apply{maxLines=2});setOnClickListener{historyTimelineScreen(mnv,items.toMutableList())}}
                box.addView(card,matchWrap());box.addView(gap(6))
            }'''
s=s[:loop_start]+loop+s[loop_end:]
old_date_tail='pageStart=0;if(query.isBlank())render()'
if old_date_tail in s: s=s.replace(old_date_tail,'query="";q.setText("");pageStart=0;render()',1)

checks=[
    (MARK in s,'marker'),('effectiveRole = role' in s,'effective role init'),('isActualSuper()' in s,'actual super guard'),
    ('"ROLE_MODE"' in s and 'roleModeScreen()' in s,'role mode tab'),('tabHistory=java.util.ArrayDeque<String>()' in s,'tab history'),
    ('navigateTab(previous,false)' in s,'previous root back'),('enteredWithPda=pda.isNotBlank()&&initialStatus.isNotBlank()' in s,'PDA exit scope'),
    ('for(i in v.childCount-1 downTo 0)' in s,'History KPI target'),('progress.joinToString(" - ")' in s,'History progress'),('Người thực hiện: $actor' in s,'History actor line')]
for ok,label in checks:
    if not ok: raise SystemExit('S47 contract missing: '+label)
OPS.write_text(s,encoding='utf-8')
print('Applied S47 Beta41: global swipe back, PDA exit scope, History summary/KPI, Superadmin role mode')

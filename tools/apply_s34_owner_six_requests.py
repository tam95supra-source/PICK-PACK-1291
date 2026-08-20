#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
STORE = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationalDataStore.kt'
LOGIN = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt'
MARK = 'S34_OWNER_SIX_REQUESTS'


def replace_private_fun(src: str, signature: str, replacement: str) -> str:
    start = src.find('    private fun ' + signature)
    if start < 0:
        raise SystemExit('S34 function anchor missing: ' + signature)
    end = src.find('\n    private fun ', start + 16)
    if end < 0:
        raise SystemExit('S34 next function anchor missing after: ' + signature)
    return src[:start] + replacement.rstrip() + '\n' + src[end:]


# ---------------------------------------------------------------------------
# Persistent local History query without an arbitrary UI limit.
# S32 remains the owner of schema/migration; S34 only adds a read helper.
# ---------------------------------------------------------------------------
store = STORE.read_text(encoding='utf-8')
if MARK not in store:
    anchor = '    fun markMutationSynced(eventId: String) = markMutationResolved(eventId, "CONFIRMED", "")\n'
    if anchor not in store:
        raise SystemExit('S34 localHistoryAll anchor missing')
    helper = '''    // S34_OWNER_SIX_REQUESTS: full durable local History for global search/filter.\n    fun localHistoryAll(): List<JSONObject> = withDbLock {\n        val out = ArrayList<JSONObject>()\n        readableDb().query(\n            "local_history",\n            arrayOf("event_id", "body_json", "status", "last_error", "queued_at", "updated_at"),\n            null, null, null, null, "queued_at DESC", null,\n        ).use { c ->\n            while (c.moveToNext()) {\n                val body = runCatching { JSONObject(c.getString(1)) }.getOrNull() ?: JSONObject()\n                out += JSONObject()\n                    .put("event_id", c.getString(0))\n                    .put("body", body)\n                    .put("status", c.getString(2))\n                    .put("error", c.getString(3) ?: "")\n                    .put("queued_at", c.getLong(4))\n                    .put("updated_at", c.getLong(5))\n            }\n        }\n        out\n    }\n\n'''
    store = store.replace(anchor, helper + anchor, 1)
    STORE.write_text(store, encoding='utf-8')

# ---------------------------------------------------------------------------
# Login: eliminate the grey shadow/halo around the rounded login surface.
# ---------------------------------------------------------------------------
login = LOGIN.read_text(encoding='utf-8')
if MARK not in login:
    old = '''            background = outlineBg(surface, 20)\n            elevation = dp(8).toFloat()'''
    new = '''            background = round(surface, 20) // S34_OWNER_SIX_REQUESTS: clean solid rounded login card\n            elevation = 0f\n            clipToOutline = true'''
    if old not in login:
        raise SystemExit('S34 login card anchor missing')
    login = login.replace(old, new, 1)
    login = login.replace('            setBackgroundColor(bg)\n            minimumHeight =', '            setBackgroundColor(surface)\n            minimumHeight =', 1)
    LOGIN.write_text(login, encoding='utf-8')

# ---------------------------------------------------------------------------
# Main product UI/logic changes. Runs after S33 so it cannot be overwritten.
# ---------------------------------------------------------------------------
s = OPS.read_text(encoding='utf-8')
if MARK not in s:
    business = r'''    // S34_OWNER_SIX_REQUESTS: business tab owns all business functions, including PDA exchange/return.
    private fun businessHome(){
        module="BUSINESS";screenState="BUSINESS"
        val root=baseRoot("NGHIỆP VỤ");val body=body()
        body.addView(section("Nghiệp vụ vận hành"));body.addView(txt("Chọn nghiệp vụ cần xử lý trên PDA.",10.2f,muted,false));body.addView(gap(10))
        val cards=listOf(
            businessCard(R.drawable.ic_pp_scan,"Quét QR nhân sự","Vào ca / ra ca theo trạng thái hiện tại"){scanScreen()},
            businessCard(R.drawable.ic_pp_task,"Công nhật","Bắt đầu / hoàn thành công nhật"){laborHome()},
            businessCard(R.drawable.ic_pp_report,"Báo cáo nhân sự","Theo ca và dữ liệu nhân sự Site 1291"){reportScreen()},
            businessCard(R.drawable.ic_pp_resource,"Tài nguyên","PDA • User Pick • Bàn Pack • User Pack"){resourceHome()},
            businessCard(R.drawable.ic_pp_resource,"Đổi / trả PDA","Đổi PDA có lý do hoặc trả PDA đang sử dụng"){pdaExchangeScreen()},
            businessCard(R.drawable.ic_pp_resource,"Quản lý CCDC","Danh mục nghiệp vụ đang được chuẩn bị"){TopNotice.show(this,"Quản lý CCDC đang được chuẩn bị.",TopNotice.Kind.INFO)},
            businessCard(R.drawable.ic_pp_task,"Nhận hàng Rớt","Nghiệp vụ đang được chuẩn bị"){TopNotice.show(this,"Nhận hàng Rớt đang được chuẩn bị.",TopNotice.Kind.INFO)}
        )
        body.addView(businessRow(cards[0],cards[1]));body.addView(gap(9))
        body.addView(businessRow(cards[2],cards[3]));body.addView(gap(9))
        body.addView(businessRow(cards[4],cards[5]));body.addView(gap(9))
        body.addView(businessRow(cards[6],Space(this)))
        attach(root,body)
    }'''
    s = replace_private_fun(s, 'businessHome(){', business)

    active = r'''    private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"SETTINGS"->"SETTINGS";else->"BUSINESS"}'''
    s = replace_private_fun(s, 'activeTab()=', active)

    nav = r'''    private fun bottomNav():LinearLayout=row(surface).apply{
        gravity=Gravity.CENTER;setPadding(dp(4),dp(5),dp(4),dp(5));background=outlineBg(surface,16);elevation=dp(8).toFloat();navRefs.clear()
        val items=listOf(
            Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),
            Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),
            Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),
            Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC"),
            Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS")
        )
        items.forEach{item->
            val iconView=ImageView(this@OperationsActivity).apply{setImageResource(item.first);setPadding(dp(5),dp(4),dp(5),dp(2))}
            val labelView=txt(item.second,7.5f,muted,item.third==activeTab()).apply{gravity=Gravity.CENTER;maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,9,1,android.util.TypedValue.COMPLEX_UNIT_SP)}
            val cell=column(Color.TRANSPARENT).apply{gravity=Gravity.CENTER;setPadding(dp(1),dp(2),dp(1),dp(2));addView(iconView,size(dp(31),dp(27)));addView(labelView);setOnClickListener{navigateTab(item.third)}}
            navRefs[item.third]=NavRefs(cell,iconView,labelView);addView(cell,LinearLayout.LayoutParams(0,-1,1f))
        };post{refreshBottomNav()}
    }'''
    s = replace_private_fun(s, 'bottomNav():LinearLayout=', nav)

    navigate = r'''    private fun navigateTab(target:String){
        if(target==activeTab())return
        module=target;initialMnv="";liveEmployeeMnv=""
        when(target){"BUSINESS"->businessHome();"STAFF"->staffScreen();"HISTORY"->historyScreen();"SYNC"->syncScreen();"SETTINGS"->settingsScreen()}
    }'''
    s = replace_private_fun(s, 'navigateTab(target:String){', navigate)

    # PDA exchange is a child screen of Nghiệp vụ, not a bottom-navigation root.
    if 'module="PDA_EXCHANGE";screenState="PDA_EXCHANGE"' not in s:
        raise SystemExit('S34 PDA exchange module anchor missing')
    s = s.replace('module="PDA_EXCHANGE";screenState="PDA_EXCHANGE"','module="BUSINESS";screenState="PDA_EXCHANGE"',1)
    s = re.sub(r'    private fun isRootScreen\(\)=.*?\n', '    private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="SETTINGS"\n', s, count=1)
    if '"HISTORY_DETAIL"->historyScreen()' in s and '"PDA_EXCHANGE"->businessHome()' not in s:
        s = s.replace('"HISTORY_DETAIL"->historyScreen()','"HISTORY_DETAIL"->historyScreen()\n            "PDA_EXCHANGE"->businessHome()',1)

    history = r'''    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ");val body=body()
        val search=input("Tìm mã nhân viên, họ tên, thao tác hoặc user xử lý",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        var selectedDate=operationalStore.businessDate();var stateFilter="ALL"
        val dateButton=smallButton("Ngày: ${runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate)}",teal)
        val searchButton=smallButton("TÌM",teal)
        val controls=row(bg).apply{gravity=Gravity.CENTER_VERTICAL;addView(dateButton,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(4)});addView(searchButton,LinearLayout.LayoutParams(dp(78),dp(44)).apply{marginStart=dp(4)})}
        body.addView(search,matchWrap());body.addView(gap(7));body.addView(controls,matchWrap());body.addView(gap(8))
        val summary=column(bg);val resultBox=column(bg);body.addView(summary,matchWrap());body.addView(gap(7));body.addView(resultBox,matchWrap())

        fun friendly(type:String,label:String=""):String=when(type.uppercase()){
            "ATTENDANCE_ENTER","ENTER"->"Vào ca";"ATTENDANCE_EXIT","EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên / vị trí";
            "LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"HISTORICAL_CORRECTION"->"Sửa lịch sử";
            "MASTER_RESOURCE_UPSERT"->"Cập nhật tài nguyên";"MASTER_RESOURCE_DELETE"->"Xóa tài nguyên";
            "MASTER_STAFF_UPSERT"->"Cập nhật nhân sự";"MASTER_STAFF_DELETE"->"Xóa nhân sự";else->label.ifBlank{type.ifBlank{"Thao tác"}}
        }
        fun actionType(a:String)=when(a){"enter"->"ATTENDANCE_ENTER";"exit"->"ATTENDANCE_EXIT";"resource_change"->"RESOURCE_CHANGE";"labor_start"->"LABOR_START";"labor_finish"->"LABOR_FINISH";else->a.uppercase()}
        fun eventDate(e:JSONObject):String=e.optString("business_date").ifBlank{e.optString("cache_business_date")}.ifBlank{
            val q=e.optLong("local_queued_at");if(q>0)java.time.Instant.ofEpochMilli(q).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate().toString() else ""
        }
        fun statusPalette(status:String):Triple<Int,Int,Int>=when(status){
            "Đã đồng bộ"->Triple(android.graphics.Color.rgb(239,250,244),green,android.graphics.Color.rgb(222,246,232))
            "Lỗi đồng bộ"->Triple(android.graphics.Color.rgb(255,239,239),red,android.graphics.Color.rgb(255,225,225))
            else->Triple(android.graphics.Color.rgb(255,248,230),orange,android.graphics.Color.rgb(255,240,204))
        }
        fun buildAll():List<JSONObject>{
            val merged=LinkedHashMap<String,JSONObject>()
            for(date in operationalStore.availableDates()){
                val day=operationalStore.loadDay(date)?:continue;val events=day.optJSONArray("events")?:JSONArray()
                for(i in 0 until events.length()){
                    val e=events.optJSONObject(i)?:continue;val c=JSONObject(e.toString()).put("cache_business_date",date).put("history_source","CANONICAL")
                    val id=c.optString("event_id").ifBlank{"canonical:$date:$i"};val p=runCatching{JSONObject(c.optString("payload_json","{}"))}.getOrDefault(JSONObject());val after=p.optJSONObject("after")
                    val emp=p.optJSONObject("employee_snapshot")?:after?.optJSONObject("employee_snapshot")
                    if(c.optString("mnv").isBlank())c.put("mnv",p.optString("mnv").ifBlank{after?.optString("mnv").orEmpty()}.ifBlank{emp?.optString("mnv").orEmpty()})
                    if(c.optString("full_name").isBlank())c.put("full_name",p.optString("full_name").ifBlank{after?.optString("full_name").orEmpty()}.ifBlank{emp?.optString("full_name").orEmpty()})
                    if(c.optString("actor").isBlank())c.put("actor",p.optString("actor").ifBlank{p.optString("login_id")}.ifBlank{p.optString("entered_by")}.ifBlank{p.optString("exited_by")})
                    merged[id]=c
                }
            }
            for(local in operationalStore.localHistoryAll()){
                val id=local.optString("event_id");if(id.isBlank())continue;val existing=merged[id]
                if(existing!=null){existing.put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at"));continue}
                val b=local.optJSONObject("body")?:JSONObject();val p=b.optJSONObject("payload")?:b;val queued=local.optLong("queued_at")
                val date=p.optString("business_date").ifBlank{b.optString("business_date")}.ifBlank{if(queued>0)java.time.Instant.ofEpochMilli(queued).atZone(ZoneId.of("Asia/Ho_Chi_Minh")).toLocalDate().toString() else ""}
                merged[id]=JSONObject().put("event_id",id).put("event_type",actionType(b.optString("action"))).put("mnv",p.optString("mnv").ifBlank{b.optString("target_id")}).put("full_name",p.optString("full_name").ifBlank{b.optString("target_label")}).put("actor",p.optString("actor").ifBlank{p.optString("login_id")}.ifBlank{login}).put("detail",b.optString("detail")).put("business_date",date).put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",queued).put("history_source","LOCAL_PDA")
            }
            return merged.values.sortedByDescending{e->val q=e.optLong("local_queued_at");if(q>0)q else runCatching{Instant.parse(e.optString("committed_at").ifBlank{e.optString("occurred_at").ifBlank{e.optString("at_iso")}}).toEpochMilli()}.getOrDefault(0)}
        }
        fun groupRows(rows:List<JSONObject>):LinkedHashMap<String,MutableList<JSONObject>>{
            val groups=LinkedHashMap<String,MutableList<JSONObject>>()
            for(e in rows){val type=e.optString("event_type");val mnv=e.optString("mnv");val date=eventDate(e);val operational=(type.startsWith("ATTENDANCE_")||type.startsWith("LABOR_")||type=="RESOURCE_CHANGE"||type=="HISTORICAL_CORRECTION")&&mnv.isNotBlank();val key=if(operational)"$date|$mnv" else "event:${e.optString("event_id")}";groups.getOrPut(key){mutableListOf()}.add(e)}
            return groups
        }
        fun render(){
            summary.removeAllViews();resultBox.removeAllViews();val query=search.text.toString().trim();val global=query.isNotBlank();val all=buildAll()
            val scope=all.filter{e->if(global){val op=friendly(e.optString("event_type"),e.optString("label"));val hay=listOf(e.optString("mnv"),e.optString("full_name"),op,e.optString("actor_id"),e.optString("actor"),e.optString("detail")).joinToString(" ").lowercase(java.util.Locale("vi","VN"));hay.contains(query.lowercase(java.util.Locale("vi","VN")))}else eventDate(e)==selectedDate}
            val groups=groupRows(scope);val waiting=groups.values.count{historyGroupStatus(it)=="Chưa đồng bộ"};val failed=groups.values.count{historyGroupStatus(it)=="Lỗi đồng bộ"}
            val top=row(bg);val allMetric=metric("Tổng",groups.size.toString(),navy).apply{setOnClickListener{stateFilter="ALL";render()}};val waitMetric=metric("Chờ",waiting.toString(),orange).apply{setOnClickListener{stateFilter="PENDING";render()}};val failMetric=metric("Cần xử lí",failed.toString(),red).apply{setOnClickListener{stateFilter="FAILED";render()}};top.addView(allMetric,LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)});top.addView(waitMetric,LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2);marginEnd=dp(2)});top.addView(failMetric,LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)});summary.addView(top,matchWrap());summary.addView(gap(5));summary.addView(txt(if(global)"Đang tìm trong toàn bộ lịch sử đang có trên PDA" else "Ngày hiển thị: ${runCatching{java.time.LocalDate.parse(selectedDate).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(selectedDate)} • Bộ lọc: ${when(stateFilter){"PENDING"->"Chờ";"FAILED"->"Cần xử lí";else->"Tất cả"}}",9.4f,muted,false))
            val shown=groups.entries.filter{(_,items)->when(stateFilter){"PENDING"->historyGroupStatus(items)=="Chưa đồng bộ";"FAILED"->historyGroupStatus(items)=="Lỗi đồng bộ";else->true}}
            if(shown.isEmpty()){resultBox.addView(info(if(global)"Không tìm thấy lịch sử phù hợp." else "Không có mục lịch sử theo bộ lọc đã chọn."));return}
            for((key,items) in shown){
                val first=items.first();val status=historyGroupStatus(items);val pal=statusPalette(status);val mnv=first.optString("mnv");val full=items.firstNotNullOfOrNull{it.optString("full_name").takeIf{x->x.isNotBlank()}}?:"";val actor=items.firstNotNullOfOrNull{it.optString("actor_id").ifBlank{it.optString("actor")}.takeIf{x->x.isNotBlank()}}?:"Hệ thống";val operational=!key.startsWith("event:")
                val card=column(pal.first).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=android.graphics.drawable.GradientDrawable().apply{setColor(pal.first);cornerRadius=dp(16).toFloat();setStroke(dp(1),pal.second)};setOnClickListener{historyTimeline(items)}}
                val head=row(android.graphics.Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL};val title=if(operational)"Mã nhân viên $mnv" else friendly(first.optString("event_type"),first.optString("label"));head.addView(txt(title,13.1f,navy,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END},LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(7)});head.addView(txt(status,9f,pal.second,true).apply{gravity=Gravity.CENTER;setPadding(dp(8),dp(5),dp(8),dp(5));background=round(pal.third,10)})
                card.addView(head,matchWrap());if(full.isNotBlank())card.addView(txt(full,11.3f,ink,true));card.addView(gap(4));card.addView(txt("${items.size} thao tác • Người xử lý: $actor",9.6f,muted,false));card.addView(txt("Cập nhật: ${historyEventTime(first)}",9.4f,muted,false));resultBox.addView(card,matchWrap());resultBox.addView(gap(8))
            }
        }
        dateButton.setOnClickListener{val d=runCatching{java.time.LocalDate.parse(selectedDate)}.getOrElse{java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"))};android.app.DatePickerDialog(this,{_,yy,mm,dd->selectedDate=String.format(java.util.Locale.US,"%04d-%02d-%02d",yy,mm+1,dd);dateButton.text="Ngày: "+String.format(java.util.Locale.US,"%02d/%02d/%04d",dd,mm+1,yy);search.setText("");stateFilter="ALL";render()},d.year,d.monthValue-1,d.dayOfMonth).show()}
        searchButton.setOnClickListener{stateFilter="ALL";render()};search.setOnEditorActionListener{_,actionId,_->if(actionId==EditorInfo.IME_ACTION_SEARCH){stateFilter="ALL";render();true}else false}
        render();foregroundSync.requestSync();attach(root,body)
    }'''
    s = replace_private_fun(s, 'historyScreen(){', history)

    group_status = r'''    private fun historyGroupStatus(items:List<JSONObject>):String{
        val states=items.map{it.optString("local_status").trim().uppercase()}
        if(states.any{it in setOf("REJECTED","REVIEW_REQUIRED","CONFLICT","FAILED","ERROR")})return "Lỗi đồng bộ"
        val allSynced=states.all{it.isBlank()||it in setOf("CONFIRMED","SYNCED","ACKED","CANONICAL")}
        return if(allSynced)"Đã đồng bộ" else "Chưa đồng bộ"
    }'''
    s = replace_private_fun(s, 'historyGroupStatus(items:List<JSONObject>):String{', group_status)

    timeline = r'''    private fun historyTimeline(items:List<JSONObject>){
        screenState="HISTORY_DETAIL";val root=baseRoot("LỊCH SỬ");val body=body();val first=items.firstOrNull()?:return;val mnv=first.optString("mnv");body.addView(section(if(mnv.isBlank())"Chi tiết thao tác" else "Mã nhân viên $mnv"));body.addView(info("Dòng thời gian trong đúng phiên. Thời gian thao tác hệ thống/Event ID chỉ đọc, không chỉnh sửa."));body.addView(gap(8))
        fun label(type:String)=when(type){"ATTENDANCE_ENTER"->"Vào ca";"ATTENDANCE_EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên / vị trí";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"HISTORICAL_CORRECTION"->"Sửa lịch sử";else->type.ifBlank{"Thao tác"}}
        items.sortedBy{historyEventTime(it)}.forEach{e->
            val type=e.optString("event_type");val actor=e.optString("actor_id").ifBlank{e.optString("actor")}.ifBlank{"Hệ thống"};val status=historyGroupStatus(listOf(e));val statusColor=when(status){"Đã đồng bộ"->green;"Lỗi đồng bộ"->red;else->orange};val fill=when(status){"Đã đồng bộ"->android.graphics.Color.rgb(239,250,244);"Lỗi đồng bộ"->android.graphics.Color.rgb(255,239,239);else->android.graphics.Color.rgb(255,248,230)}
            val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val after=p.optJSONObject("after");val src=after?:p;val d=mutableListOf<String>();listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack","labor_type","time_marker","start_at","end_at","note","state").forEach{k->val v=src.optString(k);if(v.isNotBlank())d.add("$k: $v")}
            val card=column(fill).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=android.graphics.drawable.GradientDrawable().apply{setColor(fill);cornerRadius=dp(14).toFloat();setStroke(dp(1),statusColor)}}
            val head=row(android.graphics.Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL};head.addView(txt(label(type),12.5f,navy,true),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(6)});head.addView(txt(status,8.9f,statusColor,true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(fill,9)})
            card.addView(head,matchWrap());card.addView(txt("${historyEventTime(e)} • $actor",9.8f,muted,false));if(d.isNotEmpty())card.addView(txt(d.joinToString("\n"),9.8f,ink,false));val err=e.optString("local_error");if(err.isNotBlank())card.addView(txt("Lỗi: $err",9.5f,red,true));card.addView(txt("Event ID: ${e.optString("event_id")}",8.7f,muted,false));if((e.optString("entity_type")=="ATTENDANCE_SESSION"||e.optString("entity_type")=="LABOR_SESSION")&&e.optString("entity_id").isNotBlank()&&historyCanEdit(e)){card.addView(gap(7));card.addView(smallButton("SỬA THÔNG TIN",teal).apply{setOnClickListener{historyEditDialog(e)}})};body.addView(card,matchWrap());body.addView(gap(7))
        };attach(root,body)
    }'''
    s = replace_private_fun(s, 'historyTimeline(items:List<JSONObject>){', timeline)

    sync = r'''    private fun syncScreen(){
        module="SYNC";screenState="SYNC";val root=baseRoot("ĐỒNG BỘ");val body=body();val box=column(bg);val refresh=primary("LÀM MỚI TRẠNG THÁI",teal){};body.addView(box,matchWrap());body.addView(gap(10));body.addView(refresh,matchWrap())
        fun networkType():String{val cm=getSystemService(android.content.Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager;val n=cm.activeNetwork?:return "Không có mạng";val c=cm.getNetworkCapabilities(n)?:return "Không xác định";return when{c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI)->"Wi‑Fi";c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR)->"Dữ liệu di động";c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_ETHERNET)->"Ethernet";else->"Mạng khác"}}
        fun nowText()=java.time.ZonedDateTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HH:mm:ss dd/MM/yyyy"))
        fun load(){
            box.removeAllViews();box.addView(info("Đang kiểm tra Service, authority, hàng đợi local và trạng thái nhân bản..."));val started=android.os.SystemClock.elapsedRealtime()
            api.call("sync_status"){r->runOnUiThread{
                val elapsed=(android.os.SystemClock.elapsedRealtime()-started).coerceAtLeast(0);box.removeAllViews();val pending=operationalStore.pendingMutationCount();val localHistory=runCatching{operationalStore.localHistoryAll().size}.getOrDefault(0);val conflicts=runCatching{operationalStore.conflicts(500).size}.getOrDefault(0);val dates=operationalStore.availableDates()
                if(r.ok){
                    val j=r.json?:JSONObject();val a=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject();val mode=a.optString("mode").ifBlank{j.optString("authority_mode")}.ifBlank{operationalStore.authorityMode()};val epoch=a.optLong("authority_epoch",operationalStore.authorityEpoch());val seq=a.optLong("authority_seq",operationalStore.authoritySeq());val generation=a.optString("service_generation").ifBlank{j.optString("service_generation")}.ifBlank{operationalStore.serviceGeneration()};val scope=a.optString("scope").ifBlank{j.optString("scope")}.ifBlank{"—"};val repPending=rep.optInt("pending_count",rep.optInt("pending",0));val repError=rep.optString("current_error").ifBlank{rep.optString("last_error")}.ifBlank{rep.optString("error")}.ifBlank{"Không có"}
                    lastSyncLatencyMs=j.optLong("_service_rtt_ms",elapsed);lastConnected=true;lastProjectionPending=pending;refreshHeaderConnection()
                    box.addView(section("Kết nối & đường dữ liệu"));box.addView(details(listOf("Loại mạng" to networkType(),"Service RTT" to "${lastSyncLatencyMs} ms","Tuyến đang dùng" to if(mode=="SERVICE_PRIMARY")"Service / D1 chính" else mode,"Service" to "Hoạt động","Lần kiểm tra" to nowText())))
                    box.addView(section("Authority canonical"));box.addView(details(listOf("Mode" to mode,"Epoch" to epoch.toString(),"Sequence" to seq.toString(),"Scope" to scope,"Generation" to generation.ifBlank{"—"})))
                    box.addView(section("Dữ liệu trên PDA"));box.addView(details(listOf("Mutation chờ gửi" to pending.toString(),"Mục lỗi / cần xử lí" to conflicts.toString(),"Lịch sử local đã lưu" to localHistory.toString(),"Ngày canonical đang cache" to dates.size.toString(),"Ngày mới nhất" to (dates.firstOrNull()?:"—"),"Ngày cũ nhất" to (dates.lastOrNull()?:"—"),"Local authority" to "${operationalStore.authorityMode()} • ${operationalStore.authorityEpoch()}/${operationalStore.authoritySeq()}")))
                    box.addView(section("Nhân bản Google"));box.addView(details(listOf("Trạng thái" to rep.optString("state").ifBlank{"Không có dữ liệu"},"Mục đang chờ" to repPending.toString(),"Lỗi hiện tại" to repError,"Ảnh hưởng authority" to if(mode=="SERVICE_PRIMARY")"Không — Service vẫn là nguồn chính" else "Đang dùng tuyến $mode")))
                    box.addView(section("Vòng đời đồng bộ"));box.addView(details(listOf("Khi app đang mở" to "ACTIVE — cho phép đồng bộ thường","Khi app ra nền / tắt màn hình" to "DRAINING → SUSPENDED","Khi quay lại app" to "ACTIVE + catch-up","Nguyên tắc" to "Local-first; chỉ canonical ACK mới xác nhận")))
                    box.addView(section("Ứng dụng"));box.addView(details(listOf("Kênh" to BuildConfig.CHANNEL,"Phiên bản" to BuildConfig.VERSION_NAME,"Package" to BuildConfig.APPLICATION_ID,"Ngày nghiệp vụ PDA" to operationalStore.businessDate())))
                }else{
                    lastConnected=false;lastSyncLatencyMs=elapsed;refreshHeaderConnection();box.addView(section("Kết nối hiện tại"));box.addView(details(listOf("Loại mạng" to networkType(),"Service" to "Chưa phản hồi","Thời gian kiểm tra" to "${elapsed} ms","Lần kiểm tra" to nowText())));box.addView(section("Dữ liệu vẫn an toàn trên PDA"));box.addView(details(listOf("Mutation chờ gửi" to pending.toString(),"Mục lỗi / cần xử lí" to conflicts.toString(),"Lịch sử local đã lưu" to localHistory.toString(),"Ngày canonical đang cache" to dates.size.toString(),"Local authority" to "${operationalStore.authorityMode()} • ${operationalStore.authorityEpoch()}/${operationalStore.authoritySeq()}")));box.addView(info("Mất kết nối không làm mất thao tác. Dữ liệu local-first vẫn được giữ và sẽ gửi lại khi Service khả dụng."))
                }
            }}
        }
        refresh.setOnClickListener{foregroundSync.requestSync();load()};load();attach(root,body)
    }'''
    s = replace_private_fun(s, 'syncScreen(){', sync)

    # Logout must return to a fresh login activity instead of closing the app task.
    old_logout = 'api.clearSession();finishAffinity()'
    new_logout = 'api.clearSession();startActivity(android.content.Intent(this,FullBetaActivity::class.java).apply{addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP or android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_CLEAR_TASK)});finish();overridePendingTransition(0,0)'
    if old_logout not in s:
        raise SystemExit('S34 logout anchor missing')
    s = s.replace(old_logout,new_logout,1)

    OPS.write_text(s,encoding='utf-8')

# Contract guards after patching.
ops=OPS.read_text(encoding='utf-8');store=STORE.read_text(encoding='utf-8');login=LOGIN.read_text(encoding='utf-8')
for required in ['Quản lý CCDC','Nhận hàng Rớt','Đổi / trả PDA','Lỗi đồng bộ','Chưa đồng bộ','Cần xử lí','localHistoryAll()','Authority canonical','Nhân bản Google','FullBetaActivity::class.java']:
    if required not in ops: raise SystemExit('S34 Operations contract missing: '+required)
if 'Triple(R.drawable.ic_pp_resource,"Đổi / trả PDA","PDA_EXCHANGE")' in ops: raise SystemExit('S34 PDA exchange still present in bottom nav')
if 'fun localHistoryAll()' not in store: raise SystemExit('S34 full local history helper missing')
if 'clean solid rounded login card' not in login or 'elevation = 0f' not in login: raise SystemExit('S34 clean login surface missing')
print('Applied S34 owner six requests: business cards/nav, rich sync, history filters/status/search/date, logout/login, full local history')

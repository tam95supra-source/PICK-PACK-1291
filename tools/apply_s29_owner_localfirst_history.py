#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROJ=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/PdaLocalProjection.kt'
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S29_OWNER_LOCALFIRST_HISTORY'

p=PROJ.read_text(encoding='utf-8')
if MARK not in p:
    old='''        val businessDate = store.latestBusinessDate()\n        val day = store.loadDay(businessDate) ?: return null\n'''
    new='''        val businessDate = store.latestBusinessDate()\n        val day = store.loadDay(businessDate)\n        if(day==null){\n            // S29_OWNER_LOCALFIRST_HISTORY: employee master is enough for immediate scan UX.\n            // Session state remains fenced until a canonical day snapshot arrives.\n            return JSONObject()\n                .put("ok",true)\n                .put("source","PDA_SQLITE_WARMING")\n                .put("business_date",businessDate)\n                .put("day_revision",0L)\n                .put("employee",employee)\n                .put("state","UNKNOWN_WARMING")\n                .put("session",JSONObject.NULL)\n                .put("active_labor",JSONObject.NULL)\n                .put("session_known",false)\n                .put("reconciliation_state","CACHE_WARMING")\n                .put("provisional",false)\n        }\n'''
    if old not in p: raise SystemExit('S29 projection warm anchor missing')
    p=p.replace(old,new,1)
    old='''            .put("active_labor", activeLabor ?: JSONObject.NULL)\n            .put("reconciliation_state", reconciliationState)\n'''
    new='''            .put("active_labor", activeLabor ?: JSONObject.NULL)\n            .put("session_known", true)\n            .put("reconciliation_state", reconciliationState)\n'''
    if old not in p: raise SystemExit('S29 projection known anchor missing')
    p=p.replace(old,new,1)
    PROJ.write_text(p,encoding='utf-8')

s=OPS.read_text(encoding='utf-8')
if MARK not in s:
    cls='class OperationsActivity : Activity() {\n'
    if cls not in s: raise SystemExit('S29 class anchor missing')
    s=s.replace(cls,cls+f'    // {MARK}\n',1)

    start=s.find('    private fun renderLocalEmployee(mnv:String):Boolean{')
    end=s.find('    private fun loadEmployee(mnv: String, button: Button? = null) {',start)
    if start<0 or end<0: raise SystemExit('S29 renderLocalEmployee anchors missing')
    replacement='''    private fun renderLocalEmployee(mnv:String):Boolean{\n        val ctx=PdaLocalProjection.employeeContext(this,mnv) ?: return false\n        if(!ctx.optBoolean("session_known",true)){\n            liveEmployeeMnv=mnv\n            renderCachedEmployee(ctx.optJSONObject("employee")?:JSONObject())\n            TopNotice.show(this,"Đã đọc nhân sự từ PDA • đang đối chiếu phiên nền",TopNotice.Kind.INFO)\n            return true\n        }\n        val masters=if(ctx.optString("state")=="NOT_ENTERED")PdaLocalProjection.resourceOptions(this,mnv) else null\n        renderEmployee(ctx,masters)\n        return true\n    }\n\n'''
    s=s[:start]+replacement+s[end:]

    # If the cache is warming, labor/resource may show staff immediately but must not mutate an unknown session.
    old='''            if(local!=null){\n                showLaborContext(local,MasterDataCache.snapshot(this)?:JSONObject())\n                foregroundSync.requestSync()\n                return\n            }\n'''
    new='''            if(local!=null){\n                if(!local.optBoolean("session_known",true)){\n                    renderCachedEmployee(local.optJSONObject("employee")?:JSONObject())\n                    TopNotice.show(this,"Đã đọc nhân sự từ PDA • đang đối chiếu phiên/công nhật nền",TopNotice.Kind.INFO)\n                    foregroundSync.requestSync();return\n                }\n                showLaborContext(local,MasterDataCache.snapshot(this)?:JSONObject())\n                foregroundSync.requestSync()\n                return\n            }\n'''
    if old in s: s=s.replace(old,new,1)

    old='''            if(local!=null){\n                if(local.optString("state")!="ACTIVE"){showError("MNV phải đang trong phiên ACTIVE.");return}\n                showResourceEditor(local,PdaLocalProjection.resourceOptions(this,v))\n'''
    new='''            if(local!=null){\n                if(!local.optBoolean("session_known",true)){\n                    renderCachedEmployee(local.optJSONObject("employee")?:JSONObject())\n                    TopNotice.show(this,"Đã đọc nhân sự từ PDA • đang đối chiếu tài nguyên nền",TopNotice.Kind.INFO)\n                    foregroundSync.requestSync();return\n                }\n                if(local.optString("state")!="ACTIVE"){showError("MNV phải đang trong phiên ACTIVE.");return}\n                showResourceEditor(local,PdaLocalProjection.resourceOptions(this,v))\n'''
    if old in s: s=s.replace(old,new,1)

    hs=s.find('    private fun historyScreen(){')
    he=s.find('    private fun syncScreen(){',hs)
    if hs<0 or he<0: raise SystemExit('S29 history anchors missing')
    history='''    private fun historyScreen(){\n        module="HISTORY";screenState="HISTORY";historyDetailMnv="";historyDetailName=""\n        val root=baseRoot("LỊCH SỬ");val body=body();val box=column(bg)\n        val dates=operationalStore.availableDates().take(7)\n        val all=mutableListOf<JSONObject>()\n        for(date in dates){\n            val day=operationalStore.loadDay(date)?:continue\n            val events=day.optJSONArray("events")?:JSONArray()\n            for(i in 0 until events.length()){\n                val e=events.optJSONObject(i)?:continue\n                all.add(JSONObject(e.toString()).put("cache_business_date",date))\n            }\n        }\n        all.sortByDescending{runCatching{java.time.Instant.parse(it.optString("at_iso").ifBlank{it.optString("at")}).toEpochMilli()}.getOrDefault(0L)}\n        val top=row(bg)\n        top.addView(metric("Thao tác",all.size.toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})\n        top.addView(metric("Ngày đã lưu",dates.size.toString(),teal),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})\n        body.addView(top,matchWrap());body.addView(gap(6))\n        body.addView(info("Hiển thị ngay từ bộ nhớ PDA (tối đa 7 phiên nghiệp vụ gần nhất). Hệ thống đang đối chiếu revision nền; không cần chờ mạng để mở lịch sử."));body.addView(gap(8))\n        if(all.isEmpty())box.addView(info("Chưa có lịch sử canonical trong bộ nhớ PDA. Hệ thống đang tải snapshot nền."))\n        fun friendly(type:String,label:String):String=when(type.uppercase()){\n            "ATTENDANCE_ENTER"->"Vào ca";"ATTENDANCE_EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"MASTER_STAFF_UPSERT"->"Cập nhật nhân sự";"MASTER_STAFF_DELETE"->"Xóa nhân sự";"ACCOUNT_UPSERT"->"Tạo / sửa tài khoản";"ACCOUNT_STATUS"->"Đổi trạng thái tài khoản";"ACCOUNT_EMAIL"->"Đổi email tài khoản";"ACCOUNT_PASSWORD"->"Đổi mật khẩu";"FALLBACK_RECONCILED_DUPLICATE"->"Đối soát dữ liệu dự phòng";else->label.ifBlank{type.ifBlank{"Thao tác"}}}\n        val limit=kotlin.math.min(all.size,350)\n        for(i in 0 until limit){\n            val e=all[i];val mnv=e.optString("mnv");val name=e.optString("full_name");val actor=e.optString("actor").ifBlank{"Hệ thống"};val label=friendly(e.optString("event_type"),e.optString("label"));val detail=e.optString("detail").trim();val date=e.optString("cache_business_date");val at=formatIso(e.optString("at_iso").ifBlank{e.optString("at")});val seq=e.optLong("authority_seq",0L)\n            val title=if(mnv.isNotBlank())"$label • $mnv${if(name.isBlank())"" else " • $name"}" else label\n            val sub=buildString{append("$at • Người thực hiện: $actor");if(detail.isNotBlank())append("\\nChi tiết: $detail");append("\\nPhiên dữ liệu: $date");if(seq>0)append(" • revision $seq")}\n            box.addView(listCard(title,sub));box.addView(gap(5))\n        }\n        body.addView(box,matchWrap())\n        foregroundSync.requestSync()\n        attach(root,body)\n    }\n\n'''
    s=s[:hs]+history+s[he:]
    OPS.write_text(s,encoding='utf-8')

print('Applied S29 owner local-first warm cache + seven-session readable History')

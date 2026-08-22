#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S53_BETA47_SHEET_LOGIC_UI'

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S53 Beta47 already applied');raise SystemExit(0)

# History: deletion tombstones stay visible as immutable audit; only their targets are hidden.
old='''val type=e.optString("event_type");val realId=e.optString("event_id");if(type.uppercase()=="HISTORY_DELETE"||realId in hiddenHistoryIds)continue'''
new='''val type=e.optString("event_type");val realId=e.optString("event_id");if(type.uppercase()!="HISTORY_DELETE"&&realId in hiddenHistoryIds)continue'''
if old not in s: raise SystemExit('S53 history tombstone visibility anchor missing')
s=s.replace(old,new,1)
old='''if(full.isBlank()&&mnv.isNotBlank())full=MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty();val label=friendly(type,e.optString("label"));if(n.isNotBlank()&&!listOf(mnv,full,label,actor,detail,shift).any{it.uppercase().contains(n)})continue'''
new='''if(full.isBlank()&&mnv.isNotBlank())full=MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty();val label=if(type.uppercase()=="HISTORY_DELETE")"Xóa lịch sử" else friendly(type,e.optString("label"));if(type.uppercase()=="HISTORY_DELETE"&&detail.isBlank()){val hp=p?:runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrNull();detail="Đã xóa ${hp?.optInt("deleted_count",0)?:0} mục; dữ liệu gốc và dấu vết kiểm toán được giữ."};if(n.isNotBlank()&&!listOf(mnv,full,label,actor,detail,shift).any{it.uppercase().contains(n)})continue'''
if old not in s: raise SystemExit('S53 history label anchor missing')
s=s.replace(old,new,1)
old='''.put("actor",actor).put("detail",detail).put("shift",shift).put("at_iso"'''
new='''.put("actor",actor).put("actor_role",e.optString("actor_role")).put("origin",e.optString("origin")).put("detail",detail).put("shift",shift).put("at_iso"'''
if old not in s: raise SystemExit('S53 history actor metadata anchor missing')
s=s.replace(old,new,1)

# SUPERADMIN may select canonical or local pending events; HISTORY_DELETE audit itself is protected.
old='''val deletable=items.filter{it.optString("history_source")=="SERVICE_CANONICAL"&&it.optLong("authority_seq",0L)>0L}.map{it.optString("event_id")}.filter{it.isNotBlank()}.distinct();currentPageDeleteIds.addAll(deletable)'''
new='''val deletable=items.filter{it.optString("event_type").uppercase()!="HISTORY_DELETE"}.map{it.optString("event_id")}.filter{it.isNotBlank()}.distinct();currentPageDeleteIds.addAll(deletable)'''
if old not in s: raise SystemExit('S53 history deletable anchor missing')
s=s.replace(old,new,1)
old='''selectionBox.addView(info("Quản trị cao nhất có thể chọn một hoặc nhiều mục đã đồng bộ để xóa. Trước khi xóa phải xác thực lại mật khẩu; dấu vết kiểm toán của thao tác xóa vẫn được giữ."))'''
new='''selectionBox.addView(info("Quản trị cao nhất có thể chọn nhiều lịch sử, kể cả mục đang chờ đồng bộ. Trước khi xóa phải xác thực lại mật khẩu. Nhật ký thao tác xóa luôn được giữ để truy vết."))'''
if old not in s: raise SystemExit('S53 history help anchor missing')
s=s.replace(old,new,1)
s=s.replace('''if(isSuper()&&deletable.isEmpty())addView(txt("Mục chưa đồng bộ nên chưa thể xóa.",9.1f,orange,false));''','',1)

# Make cards action-first and explicit about who/when/source.
old='''addView(txt(listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ").ifBlank{"Thao tác hệ thống"},12.5f,ink,true),LinearLayout.LayoutParams(0,-2,1f));addView(txt(label,9f,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal},true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(Color.WHITE,9)})
                    };addView(top,matchWrap());addView(txt("${last.optString("label")} • ${formatIso(last.optString("at_iso"))} • ${last.optString("actor").ifBlank{"Hệ thống"}}",10f,muted,false));if(last.optString("detail").isNotBlank())addView(txt(last.optString("detail"),9.5f,muted,false).apply{maxLines=2});'''
new='''addView(txt(last.optString("label").ifBlank{"Thao tác"},12.5f,ink,true),LinearLayout.LayoutParams(0,-2,1f));addView(txt(label,9f,when(state){"FAILED"->red;"PENDING"->Color.rgb(217,119,6);else->teal},true).apply{setPadding(dp(7),dp(4),dp(7),dp(4));background=round(Color.WHITE,9)})
                    };addView(top,matchWrap());val subject=listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ").ifBlank{last.optString("entity_id").ifBlank{"Hệ thống"}};addView(txt(subject,10.2f,navy,true));val actorText=last.optString("actor").ifBlank{"Hệ thống"};val roleText=last.optString("actor_role").ifBlank{"—"};val originText=last.optString("origin").ifBlank{"Service"};addView(txt("${formatIso(last.optString("at_iso"))} • $actorText • $roleText • $originText",9.7f,muted,false));if(last.optString("detail").isNotBlank())addView(txt(last.optString("detail"),9.5f,muted,false).apply{maxLines=3});'''
if old not in s: raise SystemExit('S53 history card anchor missing')
s=s.replace(old,new,1)

# Replace Beta46 deletion helper with password-gated deferred tombstones. Pending business events are never cancelled.
start=s.find('    private fun deleteHistoryBulk(ids:List<String>){')
end=s.find('\n    private fun historyTimeline(',start)
if start<0 or end<0: raise SystemExit('S53 delete helper anchors missing')
helper=r'''    private fun flushDeferredHistoryDeletes(){
        if(!isSuper())return
        val prefs=getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE)
        val queue=(prefs.getStringSet("deferred_ids",emptySet())?:emptySet()).filter{it.isNotBlank()}.toList()
        if(queue.isEmpty())return
        fun next(i:Int){
            if(i>=queue.size)return
            val id=queue[i]
            api.call("history_delete",JSONObject().put("event_ids",JSONArray(listOf(id))).put("idempotency_key","beta47-history-delete-$id").put("reason","SUPERADMIN xóa lịch sử từ PDA")){r->
                if(r.ok){val left=(prefs.getStringSet("deferred_ids",emptySet())?:emptySet()).toMutableSet();left.remove(id);prefs.edit().putStringSet("deferred_ids",left).apply()}
                next(i+1)
            }
        }
        next(0)
    }

    private fun deleteHistoryBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa lịch sử.");return}
        val clean=ids.filter{it.isNotBlank()}.distinct();if(clean.isEmpty()){showError("Chọn ít nhất một lịch sử cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${clean.size} lịch sử?").setMessage("Mục đã chọn sẽ được ẩn khỏi lịch sử. Nếu dữ liệu nghiệp vụ còn chờ đồng bộ, ứng dụng vẫn gửi dữ liệu đó lên Service trước rồi mới ghi dấu xóa. Nhật ký ai xóa, lúc nào và xóa gì vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->
            verifyDeletePassword("xóa ${clean.size} lịch sử"){
                val prefs=getSharedPreferences("pp_history_delete_ui",MODE_PRIVATE)
                val hidden=(prefs.getStringSet("hidden_ids",emptySet())?:emptySet()).toMutableSet();hidden.addAll(clean)
                val deferred=(prefs.getStringSet("deferred_ids",emptySet())?:emptySet()).toMutableSet();deferred.addAll(clean)
                prefs.edit().putStringSet("hidden_ids",hidden).putStringSet("deferred_ids",deferred).apply()
                TopNotice.show(this,"Đã ghi nhận xóa ${clean.size} lịch sử.",TopNotice.Kind.SUCCESS)
                foregroundSync.requestSync();historyScreen()
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({flushDeferredHistoryDeletes()},1400L)
            }
        }.show()
    }
'''
s=s[:start]+helper+s[end:]

# Retry deferred tombstones whenever History is opened.
h_anchor='''        // S52_BETA46_SUPERADMIN_HISTORY_DELETE: SUPERADMIN bulk logical delete with immutable tombstone audit.\n'''
if h_anchor in s:
    s=s.replace(h_anchor,h_anchor+'        if(isSuper())android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({flushDeferredHistoryDeletes()},500L)\n',1)
else:
    raise SystemExit('S53 history retry insertion anchor missing')

# Replace Sync screen: no issue section, no system date-window scope, no "cần xử lý xx mục". Connections show APP + WEB sessions.
def replace_fun(src,signature,replacement):
    a=src.find('    private fun '+signature)
    if a<0: raise SystemExit('S53 function anchor missing: '+signature)
    b=src.find('\n    private fun ',a+20)
    if b<0: raise SystemExit('S53 next function anchor missing: '+signature)
    return src[:a]+replacement.rstrip()+'\n'+src[b:]

sync=r'''    // S53_BETA47_SHEET_LOGIC_UI: concise sync screen + unified APP/WEB presence.
    private fun syncScreen(){
        module="SYNC";screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ");val body=body()
        val overview=column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,18)}
        val overviewTitle=txt("Đang kiểm tra trạng thái...",14f,navy,true);val overviewSub=txt("Đang kiểm tra thiết bị, Service và các phiên kết nối.",10f,muted,false)
        overview.addView(overviewTitle);overview.addView(gap(4));overview.addView(overviewSub);body.addView(overview,matchWrap());body.addView(gap(9))
        val deviceBox=column(bg);val serviceBox=column(bg);val userBox=column(bg);val appBox=column(bg)
        body.addView(deviceBox,matchWrap());body.addView(serviceBox,matchWrap());body.addView(userBox,matchWrap());body.addView(appBox,matchWrap())
        val actions=row(bg);val syncNow=smallButton("ĐỒNG BỘ NGAY",teal);val refresh=smallButton("LÀM MỚI",navy);actions.addView(syncNow,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(4)});actions.addView(refresh,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(4)});body.addView(gap(9));body.addView(actions,matchWrap())
        fun dateVi(v:String)=runCatching{java.time.LocalDate.parse(v.take(10)).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(v.ifBlank{"—"})
        fun timeVi(v:String)=if(v.isBlank())"—" else formatIso(v)
        fun authorityVi(v:String)=when(v.uppercase()){ "SERVICE_PRIMARY"->"Dịch vụ chính";"GOOGLE_FALLBACK"->"Google dự phòng";"RECONCILING"->"Đang đối chiếu dữ liệu";"OFFLINE_LOCAL"->"Chỉ lưu trên PDA";else->"Chưa xác định" }
        fun replicaVi(v:String)=when(v.uppercase()){ "SYNCED","HEALTHY","OK"->"Đã đồng bộ";"PENDING","INFLIGHT","RUNNING"->"Đang chuyển dữ liệu";"RETRY"->"Đang chờ gửi lại";"ERROR","FAILED"->"Có lỗi";else->if(v.isBlank())"Chưa có dữ liệu" else "Đang theo dõi" }
        fun loadDevice(){
            deviceBox.removeAllViews();val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0);val active=runCatching{SyncDirectionTracker.snapshot().active}.getOrDefault(false);val dates=runCatching{operationalStore.availableDates()}.getOrDefault(emptyList());val net=DeviceNetworkStatus.snapshot(this);val network=net.header(lastLatencyMs);val syncText=when{pending>0->"Còn $pending mục chờ gửi";active->"Đang trao đổi dữ liệu";else->"Đã đồng bộ"}
            overviewTitle.text=when{lastConnected==false->"Chưa kết nối được Service";pending>0->"Còn $pending mục chờ gửi";else->"Hệ thống đang hoạt động bình thường"};overviewTitle.setTextColor(if(lastConnected==false)red else if(pending>0)orange else teal);overviewSub.text="$syncText • $network"
            deviceBox.addView(section("TRÊN THIẾT BỊ"));deviceBox.addView(details(listOf("Kết nối mạng" to network,"Trạng thái đồng bộ" to syncText,"Dữ liệu chờ gửi" to pending.toString(),"Luồng trao đổi dữ liệu" to if(active)"Đang hoạt động" else "Đang nghỉ","Ngày nghiệp vụ hiện tại" to dateVi(operationalStore.businessDate()),"Ngày dữ liệu mới nhất trên PDA" to dateVi(dates.firstOrNull().orEmpty()))));deviceBox.addView(gap(8))
        }
        fun loadService(){
            serviceBox.removeAllViews();serviceBox.addView(section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM"));serviceBox.addView(info("Đang kiểm tra Service..."));val started=android.os.SystemClock.elapsedRealtime()
            api.call("sync_status",JSONObject()){r->runOnUiThread{if(screenState!="SYNC")return@runOnUiThread;serviceBox.removeAllViews();serviceBox.addView(section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM"));val rt=(android.os.SystemClock.elapsedRealtime()-started).coerceAtLeast(0);lastLatencyMs=rt
                if(!r.ok||r.json==null){lastConnected=false;refreshHeaderConnection();serviceBox.addView(details(listOf("Dịch vụ" to "Chưa phản hồi","Độ trễ lần kiểm tra" to "$rt ms","Dữ liệu trên PDA" to "Vẫn được lưu an toàn","Trạng thái gửi" to "Sẽ thử lại khi có kết nối")));serviceBox.addView(gap(8));loadDevice();return@runOnUiThread}
                lastConnected=true;refreshHeaderConnection();val j=r.json?:JSONObject();val a=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject();serviceBox.addView(details(listOf("Dịch vụ" to "Đang hoạt động","Độ trễ tới Service" to "$rt ms","Nguồn dữ liệu đang dùng" to authorityVi(a.optString("mode").ifBlank{j.optString("authority_mode")}),"Mốc dữ liệu hệ thống" to a.optLong("authority_seq",j.optLong("server_seq",0L)).toString(),"Bản sao Google" to replicaVi(rep.optString("state")),"Bản sao Google còn chờ" to rep.optInt("pending_count",0).toString(),"Lần sao chép thành công" to timeVi(rep.optString("last_success_at")))));serviceBox.addView(gap(8));loadDevice()
            }}
        }
        fun loadUsers(){
            userBox.removeAllViews();userBox.addView(section("NGƯỜI DÙNG ĐANG KẾT NỐI"));userBox.addView(info("Đang tải các phiên đang đăng nhập trên Service..."))
            api.call("service_connections",JSONObject()){r->runOnUiThread{if(screenState!="SYNC")return@runOnUiThread;userBox.removeAllViews();userBox.addView(section("NGƯỜI DÙNG ĐANG KẾT NỐI"));if(!r.ok||r.json==null){userBox.addView(info("Chưa lấy được danh sách phiên kết nối."));userBox.addView(gap(8));return@runOnUiThread};val j=r.json?:JSONObject();val arr=j.optJSONArray("nguoi_dung")?:JSONArray();userBox.addView(details(listOf("Tổng phiên đang kết nối" to j.optInt("dang_ket_noi",arr.length()).toString(),"Ứng dụng" to j.optInt("app",0).toString(),"Web" to j.optInt("web",0).toString(),"Cập nhật lúc" to timeVi(j.optString("cap_nhat_luc")))));if(arr.length()==0)userBox.addView(info("Không có phiên đăng nhập đang hoạt động."));for(i in 0 until arr.length()){val x=arr.optJSONObject(i)?:continue;userBox.addView(gap(4));userBox.addView(listCard(x.optString("ten_hien_thi").ifBlank{x.optString("tai_khoan")},"${x.optString("nen_tang")} • ${x.optString("quyen")} • ${timeVi(x.optString("lan_hoat_dong_gan_nhat"))}"),matchWrap())};userBox.addView(gap(8))}}
        }
        fun loadApp(){appBox.removeAllViews();appBox.addView(section("ỨNG DỤNG"));appBox.addView(details(listOf("Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,"Mã phiên bản" to BuildConfig.VERSION_CODE.toString())))}
        fun load(){loadDevice();loadApp();loadService();loadUsers()}
        syncNow.setOnClickListener{foregroundSync.requestSync();flushDeferredHistoryDeletes();TopNotice.show(this,"Đã yêu cầu đồng bộ dữ liệu đang chờ.",TopNotice.Kind.INFO);android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({if(screenState=="SYNC")load();flushDeferredHistoryDeletes()},900L)};refresh.setOnClickListener{load()};attach(root,body);load()
    }'''
s=replace_fun(s,'syncScreen(){',sync)

# Update section: current version only; release notes are shown by UpdateManager when a newer version exists.
settings_start=s.find('        body.addView(section("CẬP NHẬT PHIÊN BẢN"))')
settings_end=s.find('        body.addView(section("Nhật ký"))',settings_start)
if settings_start<0 or settings_end<0: raise SystemExit('S53 update settings anchors missing')
block='''        body.addView(section("CẬP NHẬT PHIÊN BẢN"))\n        body.addView(info("Phiên bản hiện tại: ${BuildConfig.VERSION_NAME}"))\n        body.addView(gap(7))\n        body.addView(primary("KIỂM TRA CẬP NHẬT",teal){UpdateManager.openManual(this)},matchWrap())\n        body.addView(gap(10))\n'''
s=s[:settings_start]+block+s[settings_end:]

# Marker + guardrails.
anchor='    private fun settingsScreen(){'
if anchor not in s: raise SystemExit('S53 settings marker anchor missing')
s=s.replace(anchor,'    // '+MARK+'\n'+anchor,1)
OPS.write_text(s,encoding='utf-8')
out=OPS.read_text(encoding='utf-8')
for required in [MARK,'flushDeferredHistoryDeletes','deferred_ids','Xóa lịch sử','Tổng phiên đang kết nối','"Ứng dụng" to j.optInt("app",0)','"Web" to j.optInt("web",0)','Phiên bản hiện tại: ${BuildConfig.VERSION_NAME}']:
    if required not in out: raise SystemExit('S53 contract missing: '+required)
for forbidden in ['MỤC CẦN XỬ LÝ','PHẠM VI DỮ LIỆU TRÊN HỆ THỐNG','Mục chưa đồng bộ nên chưa thể xóa.','Ứng dụng không tự kiểm tra']:
    if forbidden in out: raise SystemExit('S53 forbidden UI remains: '+forbidden)
print('Applied S53 Beta47: Sheet-aligned History, pending delete, concise Sync, APP/WEB presence, update UI')

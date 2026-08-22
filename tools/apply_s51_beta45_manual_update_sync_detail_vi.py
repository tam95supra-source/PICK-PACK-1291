#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
FULL = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt"
UPD = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/UpdateManager.kt"
MARK = "S51_BETA45_MANUAL_UPDATE_SYNC_DETAIL_VI"


def replace_fun(src: str, signature: str, replacement: str) -> str:
    start = src.find("    private fun " + signature)
    if start < 0:
        raise SystemExit("S51 function anchor missing: " + signature)
    end = src.find("\n    private fun ", start + 20)
    if end < 0:
        raise SystemExit("S51 next function anchor missing: " + signature)
    return src[:start] + replacement.rstrip() + "\n" + src[end:]


# Final-materialized OperationsActivity: remove automatic update checks first.
ops = OPS.read_text(encoding="utf-8")
for call in (
    "                UpdateManager.check(this@OperationsActivity)\n",
    "        UpdateManager.check(this, force = true)\n",
    "        UpdateManager.check(this)\n",
):
    ops = ops.replace(call, "")

sync = r'''    // S51_BETA45_MANUAL_UPDATE_SYNC_DETAIL_VI: detailed Vietnamese sync view shared by all roles.
    private fun syncScreen(){
        module="SYNC";screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ");val body=body()

        val overview=column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,18)}
        val overviewTitle=txt("Đang kiểm tra trạng thái...",14f,navy,true)
        val overviewSub=txt("Đang tổng hợp kết nối, dữ liệu trên PDA và dữ liệu trên hệ thống.",10f,muted,false)
        overview.addView(overviewTitle);overview.addView(gap(4));overview.addView(overviewSub)
        body.addView(overview,matchWrap());body.addView(gap(9))

        val deviceBox=column(bg);val serviceBox=column(bg);val issueBox=column(bg);val userBox=column(bg);val appBox=column(bg)
        body.addView(deviceBox,matchWrap());body.addView(serviceBox,matchWrap());body.addView(issueBox,matchWrap());body.addView(userBox,matchWrap());body.addView(appBox,matchWrap())

        val actions=row(bg);val syncNow=smallButton("ĐỒNG BỘ NGAY",teal);val refresh=smallButton("LÀM MỚI",navy)
        actions.addView(syncNow,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(4)})
        actions.addView(refresh,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(4)})
        body.addView(gap(9));body.addView(actions,matchWrap())

        fun dateVi(v:String):String=runCatching{java.time.LocalDate.parse(v.take(10)).format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}.getOrDefault(v.ifBlank{"—"})
        fun timeVi(v:String):String=if(v.isBlank())"—" else formatIso(v)
        fun authorityVi(v:String):String=when(v.uppercase()){
            "SERVICE_PRIMARY"->"Dịch vụ chính";"GOOGLE_FALLBACK"->"Google dự phòng";"RECONCILING"->"Đang đối chiếu dữ liệu";"OFFLINE_LOCAL"->"Chỉ lưu trên PDA";else->"Chưa xác định"
        }
        fun replicaVi(v:String):String=when(v.uppercase()){
            "SYNCED","HEALTHY","OK"->"Đã đồng bộ";"PENDING","INFLIGHT","RUNNING"->"Đang chuyển dữ liệu";"RETRY"->"Đang chờ gửi lại";"ERROR","FAILED"->"Cần xử lý";else->if(v.isBlank())"Chưa có dữ liệu" else "Đang theo dõi"
        }
        fun issueVi(v:String):String=when(v.uppercase()){
            "EXCLUSIVE_RESOURCE_CONFLICT"->"Xung đột tài nguyên đang được sử dụng"
            "SERVICE_SESSION_REAUTH_REQUIRED"->"Cần xác thực lại phiên kết nối"
            "NETWORK","TIMEOUT"->"Kết nối mạng chưa ổn định"
            ""->"Không có thông tin lỗi"
            else->"Có mục cần kiểm tra"
        }

        fun loadDevice(){
            deviceBox.removeAllViews();issueBox.removeAllViews()
            val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0)
            val issues=runCatching{operationalStore.conflicts(100)}.getOrDefault(emptyList())
            val dates=runCatching{operationalStore.availableDates()}.getOrDefault(emptyList())
            val active=runCatching{SyncDirectionTracker.snapshot().active}.getOrDefault(false)
            val network=networkHeaderText()
            val syncText=when{issues.isNotEmpty()->"Cần xử lý ${issues.size} mục";pending>0->"Còn $pending mục chờ gửi";active->"Đang trao đổi dữ liệu";else->"Đã đồng bộ"}
            overviewTitle.text=when{lastConnected==false->"Chưa kết nối được dịch vụ";issues.isNotEmpty()->"Cần xử lý ${issues.size} mục";pending>0->"Còn $pending mục chưa gửi";else->"Hệ thống đang hoạt động bình thường"}
            overviewTitle.setTextColor(when{lastConnected==false||issues.isNotEmpty()->red;pending>0->orange;else->teal})
            overviewSub.text="$syncText • $network"

            deviceBox.addView(section("TRÊN THIẾT BỊ"))
            deviceBox.addView(details(listOf(
                "Kết nối mạng" to network,
                "Trạng thái đồng bộ" to syncText,
                "Dữ liệu chờ gửi" to pending.toString(),
                "Mục cần xử lý" to issues.size.toString(),
                "Luồng trao đổi dữ liệu" to if(active)"Đang hoạt động" else "Đang nghỉ",
                "Ngày nghiệp vụ hiện tại" to dateVi(operationalStore.businessDate()),
                "Ngày dữ liệu mới nhất trên PDA" to dateVi(dates.firstOrNull().orEmpty()),
                "Số ngày dữ liệu đang lưu" to dates.size.toString()
            )));deviceBox.addView(gap(8))

            issueBox.addView(section("MỤC CẦN XỬ LÝ"))
            if(issues.isEmpty()) issueBox.addView(info("Không có dữ liệu bị từ chối hoặc xung đột."))
            else issues.take(8).forEach{x->
                val b=x.optJSONObject("body")?:JSONObject();val p=b.optJSONObject("payload")?:b
                val who=p.optString("mnv").ifBlank{b.optString("target_id")}.ifBlank{"Không rõ"}
                issueBox.addView(listCard("Mã nhân viên $who",issueVi(x.optString("error"))),matchWrap());issueBox.addView(gap(4))
            }
            issueBox.addView(gap(8))
        }

        fun loadService(){
            serviceBox.removeAllViews();serviceBox.addView(section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM"));serviceBox.addView(info("Đang kiểm tra dịch vụ và trạng thái sao chép dữ liệu..."))
            val started=android.os.SystemClock.elapsedRealtime()
            api.call("sync_status",JSONObject()){r->runOnUiThread{
                if(screenState!="SYNC")return@runOnUiThread
                serviceBox.removeAllViews();serviceBox.addView(section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM"))
                val rt=(android.os.SystemClock.elapsedRealtime()-started).coerceAtLeast(0);lastLatencyMs=rt
                if(!r.ok||r.json==null){
                    lastConnected=false;refreshHeaderConnection()
                    serviceBox.addView(details(listOf(
                        "Dịch vụ" to "Chưa phản hồi",
                        "Độ trễ lần kiểm tra" to "$rt ms",
                        "Dữ liệu trên PDA" to "Vẫn được lưu an toàn",
                        "Trạng thái gửi" to "Sẽ thử lại khi có kết nối"
                    )));serviceBox.addView(gap(8));loadDevice();return@runOnUiThread
                }
                lastConnected=true;refreshHeaderConnection();val j=r.json?:JSONObject();val a=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject()
                val mode=a.optString("mode").ifBlank{j.optString("authority_mode")};val repState=replicaVi(rep.optString("state"))
                serviceBox.addView(details(listOf(
                    "Dịch vụ" to "Đang hoạt động",
                    "Độ trễ tới dịch vụ" to "$rt ms",
                    "Nguồn dữ liệu đang dùng" to authorityVi(mode),
                    "Mốc dữ liệu hệ thống" to a.optLong("authority_seq",j.optLong("server_seq",0L)).toString(),
                    "Bản sao Google" to repState,
                    "Bản sao Google còn chờ" to rep.optInt("pending_count",0).toString(),
                    "Bản sao chờ gửi lại" to rep.optInt("retry_count",0).toString(),
                    "Lần sao chép thành công" to timeVi(rep.optString("last_success_at"))
                )));serviceBox.addView(gap(7))
                val window=j.optJSONArray("business_window")?:j.optJSONArray("business_dates")?:JSONArray()
                serviceBox.addView(section("PHẠM VI DỮ LIỆU TRÊN HỆ THỐNG"))
                if(window.length()==0) serviceBox.addView(info("Chưa nhận được danh sách ngày dữ liệu từ hệ thống."))
                else for(i in 0 until window.length()){
                    val x=window.optJSONObject(i);val d=x?.optString("business_date")?:window.optString(i)
                    if(d.isNotBlank())serviceBox.addView(txt("• ${dateVi(d)} — sẵn sàng",10f,ink,false))
                }
                serviceBox.addView(gap(8));loadDevice()
            }}
        }

        fun loadUsers(){
            userBox.removeAllViews();userBox.addView(section("NGƯỜI DÙNG ĐANG KẾT NỐI"));userBox.addView(info("Đang tải danh sách kết nối gần đây..."))
            api.call("service_connections",JSONObject()){r->runOnUiThread{
                if(screenState!="SYNC")return@runOnUiThread
                userBox.removeAllViews();userBox.addView(section("NGƯỜI DÙNG ĐANG KẾT NỐI"))
                if(!r.ok||r.json==null){userBox.addView(info("Chưa lấy được danh sách người dùng kết nối."));userBox.addView(gap(8));return@runOnUiThread}
                val j=r.json?:JSONObject();val arr=j.optJSONArray("nguoi_dung")?:JSONArray()
                userBox.addView(details(listOf(
                    "Đang hoạt động" to j.optInt("dang_hoat_dong",0).toString(),
                    "Có hoạt động gần đây" to j.optInt("gan_day",arr.length()).toString(),
                    "Cập nhật lúc" to timeVi(j.optString("cap_nhat_luc"))
                )))
                if(arr.length()==0)userBox.addView(info("Chưa có người dùng hoạt động gần đây."))
                for(i in 0 until arr.length()){
                    val x=arr.optJSONObject(i)?:continue;userBox.addView(gap(4))
                    userBox.addView(listCard(x.optString("ten_hien_thi").ifBlank{x.optString("tai_khoan")},"${x.optString("quyen")} • ${x.optString("trang_thai")} • ${x.optInt("so_thiet_bi",0)} thiết bị"),matchWrap())
                }
                userBox.addView(gap(8))
            }}
        }

        fun loadApp(){
            appBox.removeAllViews();appBox.addView(section("ỨNG DỤNG"));appBox.addView(details(listOf(
                "Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định",
                "Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,
                "Mã phiên bản" to BuildConfig.VERSION_CODE.toString(),
                "Ngày nghiệp vụ" to dateVi(operationalStore.businessDate())
            )))
        }

        fun load(){loadDevice();loadApp();loadService();loadUsers()}
        syncNow.setOnClickListener{foregroundSync.requestSync();TopNotice.show(this,"Đã yêu cầu đồng bộ các mục đang chờ.",TopNotice.Kind.INFO);android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({if(screenState=="SYNC")load()},700L)}
        refresh.setOnClickListener{load()}
        attach(root,body);load()
    }'''
ops = replace_fun(ops, "syncScreen(){", sync)

# Replace Settings update section. It only checks when the user presses the button.
settings_start = ops.find('        body.addView(section("Cập nhật"))')
settings_end = ops.find('        body.addView(section("Nhật ký"))', settings_start)
if settings_start < 0 or settings_end < 0:
    raise SystemExit("S51 manual update settings anchors missing")
manual_block = '''        body.addView(section("CẬP NHẬT PHIÊN BẢN"))
        body.addView(info("Phiên bản đang dùng: ${BuildConfig.VERSION_NAME} • ${if(BuildConfig.CHANNEL==\"BETA\")\"Bản thử nghiệm\" else \"Bản ổn định\"}\\nỨng dụng không tự kiểm tra, không tự tải và không tự cài bản cập nhật. Chỉ khi bấm nút bên dưới hệ thống mới lấy thông tin phiên bản mới."))
        body.addView(gap(7))
        body.addView(primary("KIỂM TRA CẬP NHẬT",teal){UpdateManager.openManual(this)},matchWrap())
        body.addView(gap(10))
'''
ops = ops[:settings_start] + manual_block + ops[settings_end:]
if MARK not in ops:
    anchor = "    private fun settingsScreen(){"
    if anchor not in ops:
        raise SystemExit("S51 settings function anchor missing")
    ops = ops.replace(anchor, "    // " + MARK + "\n" + anchor, 1)
OPS.write_text(ops, encoding="utf-8")

# Remove automatic update checks from the launcher activity too.
full = FULL.read_text(encoding="utf-8")
for call in (
    "                UpdateManager.check(this@FullBetaActivity)\n",
    "        UpdateManager.check(this, force = true)\n",
    "        UpdateManager.check(this)\n",
):
    full = full.replace(call, "")
FULL.write_text(full, encoding="utf-8")

# Manual-only updater: metadata lookup -> user chooses download -> SHA verification -> Android installer.
UPD.write_text(r'''package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import java.security.MessageDigest

// S51_BETA45_MANUAL_UPDATE_SYNC_DETAIL_VI
object UpdateManager {
    private var busy = false

    fun openManual(activity: Activity) {
        if (busy || activity.isFinishing || activity.isDestroyed) return
        busy = true
        Toast.makeText(activity, "Đang kiểm tra phiên bản mới...", Toast.LENGTH_SHORT).show()
        BetaApiClient(activity.applicationContext).updateCheck(BuildConfig.CHANNEL, BuildConfig.VERSION_NAME) { result ->
            activity.runOnUiThread {
                busy = false
                if (activity.isFinishing || activity.isDestroyed) return@runOnUiThread
                if (!result.ok) {
                    AlertDialog.Builder(activity)
                        .setTitle("Không kiểm tra được cập nhật")
                        .setMessage("Không lấy được thông tin phiên bản mới. Vui lòng kiểm tra mạng và thử lại.\n\nChi tiết: ${result.error ?: "Không xác định"}")
                        .setPositiveButton("OK", null)
                        .show()
                    return@runOnUiThread
                }
                val j = result.json ?: run {
                    AlertDialog.Builder(activity).setTitle("Không có dữ liệu cập nhật").setMessage("Hệ thống không trả về thông tin phiên bản.").setPositiveButton("OK", null).show()
                    return@runOnUiThread
                }
                if (!j.optBoolean("available", false)) {
                    AlertDialog.Builder(activity)
                        .setTitle("Đang dùng phiên bản mới nhất")
                        .setMessage("Phiên bản hiện tại: ${BuildConfig.VERSION_NAME}\nKhông có bản cập nhật mới cho ${channelLabel()}.")
                        .setPositiveButton("OK", null)
                        .show()
                    return@runOnUiThread
                }
                val version = j.optString("version_name").trim()
                val url = j.optString("apk_url").trim()
                val sha = j.optString("sha256").trim()
                val notes = j.optString("notes").trim().take(4000)
                if (version.isBlank() || url.isBlank()) {
                    AlertDialog.Builder(activity).setTitle("Thông tin cập nhật chưa đầy đủ").setMessage("Bản phát hành chưa có đủ phiên bản hoặc đường dẫn tải APK.").setPositiveButton("OK", null).show()
                    return@runOnUiThread
                }
                showRelease(activity, version, url, sha, notes)
            }
        }
    }

    private fun channelLabel(): String = if (BuildConfig.CHANNEL == "BETA") "kênh Bản thử nghiệm" else "kênh Bản ổn định"

    private fun showRelease(activity: Activity, version: String, url: String, sha: String, notes: String) {
        val message = buildString {
            append("Phiên bản đang dùng: ").append(BuildConfig.VERSION_NAME)
            append("\nPhiên bản mới: ").append(version)
            append("\n\nNội dung cập nhật:\n")
            append(notes.ifBlank { "Chưa có ghi chú chi tiết cho bản phát hành này." })
            append("\n\nAPK chỉ được tải khi bạn bấm TẢI APK. Sau khi tải xong, ứng dụng kiểm tra SHA-256 rồi mở trình cài đặt Android để bạn tự xác nhận cài đặt.")
        }
        AlertDialog.Builder(activity)
            .setTitle("Có bản cập nhật $version")
            .setMessage(message)
            .setNegativeButton("ĐỂ SAU", null)
            .setPositiveButton("TẢI APK") { _, _ -> ensureInstallPermissionThenDownload(activity, version, url, sha) }
            .show()
    }

    private fun ensureInstallPermissionThenDownload(activity: Activity, version: String, url: String, sha: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !activity.packageManager.canRequestPackageInstalls()) {
            AlertDialog.Builder(activity)
                .setTitle("Cần quyền cài APK")
                .setMessage("Android đang chặn cài APK từ Pick Pack 1291. Mở Cài đặt và cho phép nguồn này. Sau đó quay lại ứng dụng và bấm KIỂM TRA CẬP NHẬT lại; ứng dụng sẽ không tự kiểm tra.")
                .setNegativeButton("HỦY", null)
                .setPositiveButton("MỞ CÀI ĐẶT") { _, _ -> activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}"))) }
                .show()
            return
        }
        download(activity, version, url, sha)
    }

    private fun download(activity: Activity, version: String, url: String, expectedSha: String) {
        val manager = activity.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val fileName = "pick-pack-1291-${BuildConfig.CHANNEL.lowercase()}-$version.apk"
        val request = DownloadManager.Request(Uri.parse(url))
            .setTitle("Pick Pack 1291 $version")
            .setDescription("Đang tải APK cập nhật")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .setMimeType("application/vnd.android.package-archive")
            .setDestinationInExternalFilesDir(activity, Environment.DIRECTORY_DOWNLOADS, fileName)
        val id = manager.enqueue(request)
        Toast.makeText(activity, "Đang tải APK $version...", Toast.LENGTH_SHORT).show()

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L) != id) return
                try { activity.unregisterReceiver(this) } catch (_: Throwable) {}
                val uri = manager.getUriForDownloadedFile(id)
                if (uri == null) {
                    AlertDialog.Builder(activity).setTitle("Tải APK thất bại").setMessage("Không lấy được file APK sau khi tải.").setPositiveButton("OK", null).show()
                    return
                }
                Thread {
                    val actual = sha256(activity, uri)
                    activity.runOnUiThread {
                        if (expectedSha.isNotBlank() && !actual.equals(expectedSha, ignoreCase = true)) {
                            AlertDialog.Builder(activity).setTitle("APK không hợp lệ").setMessage("SHA-256 không khớp. Ứng dụng sẽ không mở file cài đặt.").setPositiveButton("OK", null).show()
                            return@runOnUiThread
                        }
                        val install = Intent(Intent.ACTION_VIEW).apply {
                            setDataAndType(uri, "application/vnd.android.package-archive")
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        activity.startActivity(install)
                    }
                }.start()
            }
        }
        if (Build.VERSION.SDK_INT >= 33) activity.registerReceiver(receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), Context.RECEIVER_NOT_EXPORTED)
        else {
            @Suppress("DEPRECATION")
            activity.registerReceiver(receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE))
        }
    }

    private fun sha256(context: Context, uri: Uri): String {
        val md = MessageDigest.getInstance("SHA-256")
        context.contentResolver.openInputStream(uri)?.use { input ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buf)
                if (n <= 0) break
                md.update(buf, 0, n)
            }
        } ?: return ""
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}
''', encoding="utf-8")

# Fail closed: no automatic update entry point may remain in either activity.
for path in (OPS, FULL):
    out = path.read_text(encoding="utf-8")
    if "UpdateManager.check(" in out:
        raise SystemExit("S51 automatic update check still present: " + str(path))

out_ops = OPS.read_text(encoding="utf-8")
out_upd = UPD.read_text(encoding="utf-8")
for required in (MARK, 'section("CẬP NHẬT PHIÊN BẢN")', 'primary("KIỂM TRA CẬP NHẬT"', 'UpdateManager.openManual(this)', 'section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM")', 'section("NGƯỜI DÙNG ĐANG KẾT NỐI")'):
    if required not in out_ops:
        raise SystemExit("S51 UI contract missing: " + required)
for required in (MARK, "fun openManual(activity: Activity)", "TẢI APK", "DownloadManager.Request"):
    if required not in out_upd:
        raise SystemExit("S51 updater contract missing: " + required)
print("Applied S51 Beta45 clean: manual-only update + detailed Vietnamese sync UI")

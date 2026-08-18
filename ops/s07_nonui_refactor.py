from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
full_path = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt'
ops_path = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
build_path = ROOT / 'app/build.gradle.kts'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f'{label}: start marker not found')
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f'{label}: end marker not found')
    return text[:start] + replacement + text[end:]

full = full_path.read_text(encoding='utf-8')
ops = ops_path.read_text(encoding='utf-8')
build = build_path.read_text(encoding='utf-8')

# ---------------------------------------------------------------------------
# FullBetaActivity becomes login/legacy only. Authenticated users land in one
# persistent OperationsActivity shell so tab changes never cross Activities.
# ---------------------------------------------------------------------------
full = replace_once(
    full,
    '        LocalLogManager.uploadAutomaticPending(this, api)\n        dashboard()\n        foregroundSync.start()\n',
    '        LocalLogManager.uploadAutomaticPending(this, api)\n        openMainShell()\n',
    'restore landing',
)
full = replace_once(
    full,
    '                LocalLogManager.uploadAutomaticPending(this@FullBetaActivity, api)\n                dashboard()\n                foregroundSync.start()\n',
    '                LocalLogManager.uploadAutomaticPending(this@FullBetaActivity, api)\n                openMainShell()\n',
    'login landing',
)

shell_method = '''    private fun openMainShell() {\n        startActivity(Intent(this, OperationsActivity::class.java).apply {\n            putExtra("module", "BUSINESS")\n            putExtra("login", accountLogin)\n            putExtra("name", accountName)\n            putExtra("role", accountRole)\n            putExtra("position", accountPosition)\n            putExtra("email", accountEmail)\n        })\n        finish()\n        @Suppress("DEPRECATION")\n        overridePendingTransition(0,0)\n    }\n\n'''
full = replace_once(full, '    private fun dashboard() {\n', shell_method + '    private fun dashboard() {\n', 'insert main shell launcher')
full = full.replace('syncText?.text = "✓ Online • R${status.serverSeq}"', 'syncText?.text = "✓ Kết nối tốt"')
full = full.replace('syncText?.text = "! Offline"', 'syncText?.text = "! Mất kết nối"')
full = full.replace('syncText?.text="✓ Online • R${j.optLong("server_seq",0)}"', 'syncText?.text="✓ Kết nối tốt"')
full = full.replace('syncText?.text="! Offline"', 'syncText?.text="! Mất kết nối"')
full = full.replace('        body.addView(txt("Màu giao diện được đổi trong tab Cài đặt • 7 màu đồng bộ toàn ứng dụng",9.2f,muted,false).apply{gravity=Gravity.CENTER})\n', '')

# ---------------------------------------------------------------------------
# OperationsActivity: single persistent five-tab shell, zero transition delay.
# ---------------------------------------------------------------------------
ops = ops.replace('import android.content.Intent\n', '')
ops = ops.replace('import android.transition.Fade\n', '')
ops = ops.replace('import android.transition.TransitionManager\n', '')
ops = replace_once(
    ops,
    '    private var contentHost: FrameLayout? = null\n    private var navHost: FrameLayout? = null\n',
    '    private var contentHost: FrameLayout? = null\n    private var navHost: FrameLayout? = null\n    private data class NavRefs(val cell:LinearLayout,val icon:TextView,val label:TextView)\n    private val navRefs=mutableMapOf<String,NavRefs>()\n    private var liveEmployeeMnv=""\n',
    'persistent nav refs',
)
ops = ops.replace('syncText?.text = if(status.connected) "✓ Online • R${status.serverSeq}" else "! Offline"', 'syncText?.text = if(status.connected) "✓ Kết nối tốt" else "! Mất kết nối"')
ops = replace_once(
    ops,
    '                if (!status.connected || !status.changed) return\n                // List/report screens are read-only and safe to refresh automatically.\n                // Labor/resource editors intentionally keep the operator\'s in-progress input;\n                // their writes are still revalidated under the Apps Script / Google Sheet transaction lock.\n                when (module) {\n                    "LISTS" -> listsScreen()\n                    "REPORT" -> reportScreen()\n                }\n',
    '                if (!status.connected || !status.changed) return\n                if(module=="BUSINESS" && liveEmployeeMnv.isNotBlank()){ loadEmployee(liveEmployeeMnv); return }\n                when (screenState) {\n                    "LISTS" -> listsScreen()\n                    "REPORT" -> reportScreen()\n                }\n',
    'foreground refresh',
)
ops = ops.replace('module = intent.getStringExtra("module") ?: "LISTS"', 'module = intent.getStringExtra("module") ?: "BUSINESS"')
old_switch = '''        when(module){\n            "LABOR"->laborHome()\n            "RESOURCES"->resourceHome()\n            "REPORT"->reportScreen()\n            "SETTINGS"->settingsScreen()\n            "STAFF"->staffScreen()\n            "HISTORY"->historyScreen()\n            "SYNC"->syncScreen()\n            else->listsScreen()\n        }\n'''
new_switch = '''        when(module){\n            "BUSINESS"->businessHome()\n            "LABOR"->{module="BUSINESS";laborHome()}\n            "RESOURCES"->{module="BUSINESS";resourceHome()}\n            "REPORT"->{module="BUSINESS";reportScreen()}\n            "LISTS"->{module="BUSINESS";listsScreen()}\n            "SETTINGS"->settingsScreen()\n            "STAFF"->staffScreen()\n            "HISTORY"->historyScreen()\n            "SYNC"->syncScreen()\n            else->{module="BUSINESS";businessHome()}\n        }\n'''
ops = replace_once(ops, old_switch, new_switch, 'onCreate routing')

# Reuse the already-proven QR/session implementation from FullBetaActivity,
# but host it inside OperationsActivity so bottom-tab switching remains in one Activity.
qr_start = full.find('    private fun employeeScan() {')
qr_end = full.find('    private fun refreshStatus()', qr_start)
if qr_start < 0 or qr_end < 0:
    raise SystemExit('QR block markers not found in FullBetaActivity')
qr = full[qr_start:qr_end]
qr = qr.replace('currentScreen', 'screenState')
qr = qr.replace('this@FullBetaActivity', 'this@OperationsActivity')
qr = qr.replace('appBar("QUÉT QR NHÂN SỰ",true)', 'appBar("QUÉT QR NHÂN SỰ")')
qr = qr.replace('appBar("QUÉT QR NHÂN SỰ", true)', 'appBar("QUÉT QR NHÂN SỰ")')
qr = qr.replace('body.addView(primary("ĐỔI TÀI NGUYÊN / VỊ TRÍ", orange) { openModule("RESOURCES", mnv) }, matchWrap())', 'body.addView(primary("ĐỔI TÀI NGUYÊN / VỊ TRÍ", orange) { initialMnv=mnv; resourceHome() }, matchWrap())')
qr = qr.replace('        body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(6))\n        body.addView(txt("Nhận Enter/OK từ PDA hoặc bàn phím để chạy ngay.",9.8f,muted,false))\n', '        body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(6))\n')

business = '''    private fun businessHome(){\n        module="BUSINESS"\n        screenState="BUSINESS"\n        initialMnv=""\n        liveEmployeeMnv=""\n        val root=baseRoot("NGHIỆP VỤ")\n        val body=body()\n        val qrCard=businessCard("▣","Quét QR nhân sự","Vào ca / ra ca"){ employeeScan() }\n        val laborCard=businessCard("✓","Công nhật","Bắt đầu / hoàn thành"){ laborHome() }\n        val reportCard=businessCard("▤","Báo cáo nhân sự","Theo ca / theo ngày"){ reportScreen() }\n        val resourceCard=businessCard("▥","Tài nguyên","PDA / Pick / Pack"){ resourceHome() }\n        body.addView(businessRow(qrCard,laborCard))\n        body.addView(gap(8))\n        body.addView(businessRow(reportCard,resourceCard))\n        attach(root,body)\n    }\n\n'''
ops = replace_once(ops, '    private fun laborHome(){\n', business + qr + '    private fun laborHome(){\n', 'insert business and QR flow')

# Remove implementation/developer-facing helper copy from user screens.
ops = ops.replace('        val root=baseRoot("CÔNG NHẬT");val body=body();body.addView(txt("◉ Quét / nhập MNV rồi Enter/OK để xử lý công nhật.",10.5f,muted,false));body.addView(gap(9))\n', '        val root=baseRoot("CÔNG NHẬT");val body=body()\n')
ops = ops.replace('body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(5));body.addView(txt("Không cần nút kiểm tra.",9.5f,muted,false))', 'body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(5))')
ops = ops.replace('        val root=baseRoot("TÀI NGUYÊN");val body=body();body.addView(txt("↔ Nhập / quét MNV rồi Enter/OK để mở tài nguyên đang dùng.",10.5f,muted,false));body.addView(gap(8))\n', '        val root=baseRoot("TÀI NGUYÊN");val body=body()\n')
ops = ops.replace('if(a.length()==0)box.addView(info("Không có kết quả trong cache. Master data tự làm mới khi Sheet thay đổi."))', 'if(a.length()==0)box.addView(info("Không tìm thấy nhân sự phù hợp."))')

history_new = '''    private fun historyScreen(){\n        module="HISTORY"\n        screenState="HISTORY"\n        val root=baseRoot("LỊCH SỬ")\n        val body=body()\n        val a=AppHistory.items(this)\n        if(a.length()==0) body.addView(info("Chưa có lịch sử."))\n        for(i in 0 until a.length()){\n            val x=a.optJSONObject(i)?:continue\n            val ok=x.optBoolean("synced")\n            val at=java.text.SimpleDateFormat("dd/MM HH:mm:ss",java.util.Locale.US).format(java.util.Date(x.optLong("at")))\n            val detail=x.optString("detail").trim()\n            val sub="$at • ${if(ok)"Đã đồng bộ" else "Chưa đồng bộ"}${if(detail.isBlank())"" else " • $detail"}"\n            body.addView(listCard(AppHistory.label(x.optString("action")),sub))\n            body.addView(gap(6))\n        }\n        attach(root,body)\n    }\n\n'''
ops = replace_between(ops, '    private fun historyScreen(){\n', '    private fun syncScreen(){\n', history_new, 'history copy')

sync_new = '''    private fun syncScreen(){\n        module="SYNC"\n        screenState="SYNC"\n        val root=baseRoot("ĐỒNG BỘ")\n        val body=body()\n        val state=info("Đang kiểm tra kết nối...")\n        val detailsBox=column(bg)\n        body.addView(state,matchWrap())\n        body.addView(gap(8))\n        body.addView(detailsBox,matchWrap())\n        detailsBox.addView(details(listOf(\n            "Mạng" to "Đang kiểm tra",\n            "Dữ liệu chờ gửi" to LocalLogManager.pendingCount(this).toString(),\n            "Phiên bản" to BuildConfig.VERSION_NAME,\n            "Service" to "Chưa cấu hình"\n        )))\n        api.call("sync_status"){r->runOnUiThread{\n            if(handleAuth(r))return@runOnUiThread\n            detailsBox.removeAllViews()\n            if(r.ok){\n                state.text="✓ Kết nối tốt"\n                detailsBox.addView(details(listOf(\n                    "Mạng" to "Tốt",\n                    "Đồng bộ" to "Sẵn sàng",\n                    "Dữ liệu chờ gửi" to LocalLogManager.pendingCount(this).toString(),\n                    "Phiên bản" to BuildConfig.VERSION_NAME,\n                    "Service" to "Chưa cấu hình"\n                )))\n            }else{\n                state.text="! Mất kết nối"\n                detailsBox.addView(info("Dữ liệu sẽ tự đồng bộ khi kết nối trở lại."))\n            }\n        }}\n        attach(root,body)\n    }\n\n'''
ops = replace_between(ops, '    private fun syncScreen(){\n', '    private fun settingsScreen(){\n', sync_new, 'sync copy')

settings_new = '''    private fun settingsScreen(){\n        module="SETTINGS"\n        screenState="SETTINGS"\n        val root=baseRoot("CÀI ĐẶT")\n        val body=body()\n        body.addView(section("Tài khoản"))\n        body.addView(listCard("$name • ${roleText(role)}","Tài khoản: $login${if(position.isBlank())"" else " • Vị trí: $position"}\\nMail reset: ${email.ifBlank{"Chưa cấu hình"}}"))\n        body.addView(gap(7))\n        val accountButtons=row(bg)\n        val passBtn=primary("ĐỔI MẬT KHẨU",navy){changePasswordDialog()}.apply{textSize=9.6f;setSingleLine(true)}\n        val mailBtn=primary("ĐỔI MAIL",teal){changeEmailDialog()}.apply{textSize=9.6f;setSingleLine(true)}\n        accountButtons.addView(passBtn,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(3)})\n        accountButtons.addView(mailBtn,LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(3)})\n        body.addView(accountButtons,matchWrap())\n        if(isAdmin()){\n            body.addView(gap(7))\n            body.addView(primary("QUẢN LÝ TÀI KHOẢN",blue){accountManager()},matchWrap())\n        }\n        body.addView(section("Giao diện"))\n        body.addView(themePicker(),matchWrap())\n        body.addView(section("Cập nhật"))\n        body.addView(info("${BuildConfig.CHANNEL} • ${BuildConfig.VERSION_NAME}\\nTự động kiểm tra cập nhật: Bật"))\n        body.addView(section("Nhật ký"))\n        body.addView(primary("GỬI BÁO LỖI",teal){sendDiagnostic()},matchWrap())\n        body.addView(section("Thiết bị"))\n        body.addView(info("Android ${Build.VERSION.RELEASE} • ${Build.MANUFACTURER} ${Build.MODEL}"))\n        body.addView(gap(14))\n        body.addView(primary("ĐĂNG XUẤT",red){api.call("logout"){runOnUiThread{api.clearSession();finishAffinity()}}},matchWrap())\n        attach(root,body)\n    }\n'''
ops = replace_between(ops, '    private fun settingsScreen(){\n', '    private fun themePicker()', settings_new, 'settings duplicate sync removal')
ops = ops.replace('ThemeManager.select(this@OperationsActivity,i);recreate()', 'ThemeManager.select(this@OperationsActivity,i);window.statusBarColor=ThemeManager.primaryDark(this@OperationsActivity);settingsScreen()')
ops = ops.replace('TopNotice.show(this,"Đã gửi log và nhận ACK; file local đã được xóa.",TopNotice.Kind.SUCCESS)', 'TopNotice.show(this,"Đã gửi báo lỗi thành công.",TopNotice.Kind.SUCCESS)')

# Root switching is immediate. The bottom navigation instance is persistent and
# only its selected state is updated, so a tab press never waits for a transition.
attach_new = '''    private fun attach(root:LinearLayout,body:LinearLayout){\n        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))\n        setScreen(root)\n    }\n    private fun setScreen(content:View){\n        val frame=contentHost\n        if(frame==null){setContentView(host(content));return}\n        frame.removeAllViews()\n        frame.addView(content,FrameLayout.LayoutParams(-1,-1))\n        refreshBottomNav()\n    }\n'''
ops = replace_between(ops, '    private fun attach(root:LinearLayout,body:LinearLayout){\n', '    private fun appBar(title:String)', attach_new, 'instant content swap')

nav_new = '''    private fun bottomNav(): LinearLayout = row(Color.TRANSPARENT).apply {\n        gravity=Gravity.CENTER\n        setPadding(dp(4),dp(4),dp(4),dp(4))\n        background=gradient(navy,accent,0)\n        navRefs.clear()\n        val items=listOf(\n            Triple("▦","Nghiệp vụ","BUSINESS"),\n            Triple("♙","Nhân sự","STAFF"),\n            Triple("◷","Lịch sử","HISTORY"),\n            Triple("↻","Đồng bộ","SYNC"),\n            Triple("⚙","Cài đặt","SETTINGS")\n        )\n        items.forEach{item->\n            val iconView=txt(item.first,17f,Color.WHITE,true).apply{gravity=Gravity.CENTER}\n            val labelView=txt(item.second,8.4f,Color.WHITE,item.third==activeTab()).apply{gravity=Gravity.CENTER;maxLines=1}\n            val cell=column(Color.TRANSPARENT).apply{\n                gravity=Gravity.CENTER\n                addView(iconView)\n                addView(labelView)\n                setOnClickListener{navigateTab(item.third)}\n            }\n            navRefs[item.third]=NavRefs(cell,iconView,labelView)\n            addView(cell,LinearLayout.LayoutParams(0,-1,1f).apply{marginStart=dp(1);marginEnd=dp(1)})\n        }\n        post{refreshBottomNav()}\n    }\n\n    private fun refreshBottomNav(){\n        val active=activeTab()\n        val inactive=Color.argb(185,255,255,255)\n        navRefs.forEach{(key,ref)->\n            val chosen=key==active\n            ref.cell.background=if(chosen)round(Color.argb(35,255,255,255),10)else null\n            ref.icon.setTextColor(if(chosen)Color.WHITE else inactive)\n            ref.label.setTextColor(if(chosen)Color.WHITE else inactive)\n            ref.label.typeface=if(chosen)Typeface.DEFAULT_BOLD else Typeface.DEFAULT\n        }\n    }\n\n    private fun navigateTab(target:String){\n        if(target==activeTab())return\n        module=target\n        initialMnv=""\n        liveEmployeeMnv=""\n        when(target){\n            "BUSINESS"->businessHome()\n            "STAFF"->staffScreen()\n            "HISTORY"->historyScreen()\n            "SYNC"->syncScreen()\n            "SETTINGS"->settingsScreen()\n        }\n    }\n\n    private fun sessionExpired(){\n        api.clearSession()\n        AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã thay đổi").setMessage("Vui lòng đăng nhập lại để tiếp tục.").setCancelable(false).setPositiveButton("ĐĂNG NHẬP"){_,_->finishAffinity()}.show()\n    }\n\n'''
ops = replace_between(ops, '    private fun bottomNav(): LinearLayout', '    private fun handleAuth', nav_new, 'persistent tab nav')

ops = replace_once(
    ops,
    '    private fun navigateBack(){when(screenState){"LABOR_CONTEXT"->laborHome();"RESOURCE_EDITOR"->resourceHome();"ACCOUNT_MANAGER"->settingsScreen();else->finish()}}\n',
    '''    private fun navigateBack(){\n        when(screenState){\n            "LABOR_CONTEXT"->laborHome()\n            "RESOURCE_EDITOR"->resourceHome()\n            "ACCOUNT_MANAGER"->settingsScreen()\n            "EMPLOYEE","EMPLOYEE_LOADING"->employeeScan()\n            "SCAN","LABOR_HOME","RESOURCE_HOME","REPORT","LISTS"->businessHome()\n            else->if(module!="BUSINESS"){module="BUSINESS";businessHome()}else finish()\n        }\n    }\n''',
    'back routing',
)

# Equal work-card helpers: same geometry, same theme color, same copy hierarchy.
helper_anchor = '    private fun employeeCard(e:JSONObject)='
business_helpers = '''    private fun businessCard(icon:String,title:String,sub:String,click:()->Unit)=column(surface).apply{\n        gravity=Gravity.CENTER\n        setPadding(dp(10),dp(10),dp(10),dp(10))\n        background=outlineBg(surface,12)\n        addView(txt(icon,24f,teal,true).apply{gravity=Gravity.CENTER})\n        addView(gap(5))\n        addView(txt(title,11.8f,ink,true).apply{gravity=Gravity.CENTER;maxLines=2})\n        addView(gap(2))\n        addView(txt(sub,9.2f,muted,false).apply{gravity=Gravity.CENTER;maxLines=1})\n        setOnClickListener{click()}\n    }\n    private fun businessRow(a:View,b:View)=row(bg).apply{\n        addView(a,LinearLayout.LayoutParams(0,dp(116),1f).apply{marginEnd=dp(4)})\n        addView(b,LinearLayout.LayoutParams(0,dp(116),1f).apply{marginStart=dp(4)})\n    }\n\n'''
ops = replace_once(ops, helper_anchor, business_helpers + helper_anchor, 'business helpers')

# Active tab is module-based; inner business workflows stay highlighted on Business.
ops = ops.replace('private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"SETTINGS"->"SETTINGS";else->"BUSINESS"}', 'private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"SETTINGS"->"SETTINGS";else->"BUSINESS"}')

# Candidate version is advanced immediately so source never diverges from a
# published APK under the same version name/code. This is NOT an OTA publish.
build = replace_once(build, '            versionCode = 12\n            versionName = "0.4.2-beta.6"\n', '            versionCode = 13\n            versionName = "0.4.2-beta.7"\n', 'beta candidate version')

full_path.write_text(full, encoding='utf-8')
ops_path.write_text(ops, encoding='utf-8')
build_path.write_text(build, encoding='utf-8')

# Hard gates for the global rules in this refactor.
assert 'TransitionManager.beginDelayedTransition' not in ops
assert 'overridePendingTransition(android.R.anim.fade_in' not in ops
assert 'Đồng bộ / dữ liệu' not in ops
for banned in ('ACK', 'Server revision', 'Master revision', 'Master data tự làm mới', 'Màu giao diện được đổi'):
    if banned in full or banned in ops:
        raise SystemExit(f'user-facing developer copy remains: {banned}')
assert 'private fun businessHome()' in ops
assert 'private fun refreshBottomNav()' in ops
assert 'versionCode = 13' in build and '0.4.2-beta.7' in build
print('S07 non-UI refactor applied: single tab shell, copy rules, beta.7 candidate')

package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.*

class MainActivity : Activity() {
    private val teal = Color.rgb(20, 154, 165)
    private val tealDark = Color.rgb(11, 120, 128)
    private val bg = Color.rgb(245, 250, 250)
    private val surface = Color.WHITE
    private val ink = Color.rgb(21, 35, 46)
    private val muted = Color.rgb(96, 119, 129)

    private lateinit var sync: PreviewSyncCoordinator
    private var syncText: TextView? = null
    private var screen = "LOGIN"
    private var userName = "dpchan"

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = bg
        window.navigationBarColor = surface
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        LocalLogManager.installCrashHandler(this)
        LocalLogManager.createDailyIfNeeded(this)
        sync = PreviewSyncCoordinator { stateNow, message ->
            runOnUiThread { syncText?.text = "●  ${stateNow.name} • $message" }
        }
        login()
    }

    override fun onStart() {
        super.onStart()
        sync.enterForeground()
    }

    override fun onStop() {
        sync.leaveForeground()
        super.onStop()
    }

    private fun login() {
        screen = "LOGIN"
        val body = column(bg).apply {
            setPadding(dp(22), dp(28), dp(22), dp(18))
            gravity = Gravity.CENTER_HORIZONTAL
        }
        body.addView(ImageView(this).apply {
            setImageResource(R.drawable.app_icon)
            scaleType = ImageView.ScaleType.CENTER_CROP
        }, size(dp(112), dp(112)))
        body.addView(txt("PICK PACK 1291", 27f, ink, true).center())
        body.addView(txt("SUPRA DC HƯNG YÊN", 13f, tealDark, true).center())
        body.addView(gap(10))
        body.addView(chip("BETA UI PREVIEW • v0.1.0-beta.1"))
        body.addView(gap(20))

        val card = column(surface).apply {
            setPadding(dp(18), dp(18), dp(18), dp(18))
            background = round(surface, 18)
            elevation = dp(2).toFloat()
        }
        val user = input("Tài khoản", false).apply { setText("dpchan") }
        val pass = input("Mật khẩu", true)
        card.addView(labelled("Tài khoản", user))
        card.addView(gap(12))
        card.addView(labelled("Mật khẩu", pass))
        card.addView(gap(18))
        card.addView(action("ĐĂNG NHẬP") {
            if (user.text.isNullOrBlank() || pass.text.isNullOrBlank()) {
                toast("Nhập tài khoản và mật khẩu để xem Beta.")
            } else {
                userName = user.text.toString().trim()
                dashboard()
            }
        })
        card.addView(gap(10))
        card.addView(txt("Preview kiểm tra giao diện. Backend Google Sheets chưa kết nối.", 11.5f, muted, false).center())
        body.addView(card, matchWrap())
        body.addView(gap(20))
        body.addView(footer())
        setContentView(ScrollView(this).apply { addView(body) })
    }

    private fun dashboard() {
        screen = "DASHBOARD"
        val root = column(bg)
        root.addView(bar("Trang chủ", false))
        val body = column(bg).apply { setPadding(dp(14), dp(12), dp(14), dp(20)) }
        syncText = txt("●  BETA PREVIEW • backend chưa kết nối", 12f, tealDark, true).apply {
            setPadding(dp(12), dp(10), dp(12), dp(10))
            background = round(Color.rgb(225, 247, 247), 13)
        }
        body.addView(syncText, matchWrap())
        body.addView(gap(12))
        body.addView(txt("Thao tác nhanh", 18f, ink, true))
        body.addView(txt("Mẫu 3 • nhẹ, rõ, ưu tiên PDA", 12f, muted, false))
        body.addView(gap(8))
        body.addView(cards(
            card("↪", "VÀO CA", Color.rgb(211, 244, 246), tealDark) { enterShift() },
            card("↩", "RA CA", Color.rgb(255, 226, 226), Color.rgb(207, 55, 55)) { preview("RA CA") }
        ))
        body.addView(cards(
            card("▣", "CÔNG NHẬT", Color.rgb(225, 246, 230), Color.rgb(35, 139, 70)) { preview("CÔNG NHẬT") },
            card("⌘", "TÀI NGUYÊN", Color.rgb(255, 241, 219), Color.rgb(220, 119, 20)) { preview("TÀI NGUYÊN") }
        ))
        body.addView(cards(
            card("☷", "DANH SÁCH", Color.rgb(225, 237, 251), Color.rgb(37, 104, 174)) { preview("DANH SÁCH") },
            card("⚙", "CÀI ĐẶT", Color.rgb(239, 231, 252), Color.rgb(112, 72, 170)) { settings() }
        ))
        body.addView(gap(14))
        body.addView(txt("Đồng bộ foreground nhanh. Khi thoát/tắt màn hình: DRAINING giao dịch hiện tại rồi SUSPENDED.", 12f, muted, false))
        body.addView(gap(22))
        body.addView(footer())
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
        sync.manualExchange()
    }

    private fun enterShift() {
        screen = "ENTER_SHIFT"
        val root = column(bg)
        root.addView(bar("VÀO CA", true))
        val body = column(bg).apply { setPadding(dp(16), dp(14), dp(16), dp(20)) }
        body.addView(txt("Thông tin phiên làm việc", 18f, ink, true))
        body.addView(gap(10))
        val mnv = input("Quét hoặc nhập MNV", false)
        body.addView(labelled("MNV", mnv))
        body.addView(gap(12))
        body.addView(labelled("Ca làm việc", spinner(arrayOf("Ca 1", "Ca 2", "Ca HC"))))
        body.addView(gap(12))
        body.addView(labelled("Vị trí trong ca", spinner(arrayOf("Pick", "Pack", "Điều phối", "Khác"))))
        body.addView(gap(12))
        body.addView(txt("PDA / User Pick / Bàn Pack sẽ hiện theo vị trí và trạng thái khả dụng khi backend bật.", 12f, muted, false).apply {
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = round(Color.rgb(235, 246, 247), 12)
        })
        body.addView(gap(18))
        body.addView(action("TIẾP TỤC") {
            if (mnv.text.isNullOrBlank()) toast("Quét hoặc nhập MNV.") else preview("VÀO CA • MNV ${mnv.text}")
        })
        body.addView(gap(16))
        body.addView(txt("Nếu server trả conflict, form giữ nguyên; chỉ tài nguyên xung đột cần xử lý.", 11.5f, muted, false))
        body.addView(gap(20))
        body.addView(footer())
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
    }

    private fun settings() {
        screen = "SETTINGS"
        val root = column(bg)
        root.addView(bar("CÀI ĐẶT", true))
        val body = column(bg).apply { setPadding(dp(16), dp(14), dp(16), dp(20)) }
        body.addView(section("Tài khoản"))
        body.addView(setting("Đổi mật khẩu", "User tự đổi mật khẩu của chính mình") { changePassword() })
        body.addView(section("Đồng bộ"))
        body.addView(setting("Trạng thái", "${sync.state} • server_seq: preview") { sync.manualExchange() })
        body.addView(section("Nhật ký"))
        body.addView(setting("Gửi báo lỗi thủ công", "Tạo diagnostic bundle đã loại secret") {
            val f = LocalLogManager.createManualReport(this, screen, sync.state.name)
            AlertDialog.Builder(this)
                .setTitle("Đã tạo báo lỗi")
                .setMessage("Đã lưu local: ${f.name}\n\nPreview chưa upload Drive; bản chính chỉ xóa file sau server ACK.")
                .setPositiveButton("OK", null)
                .show()
        })
        body.addView(section("Cập nhật"))
        body.addView(setting("Phiên bản", "0.1.0-beta.1-preview • Beta") { preview("OTA") })
        body.addView(section("Thiết bị"))
        body.addView(setting("Thông tin thiết bị", "Android ${android.os.Build.VERSION.RELEASE} • ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}") {})
        body.addView(gap(22))
        body.addView(footer())
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
    }

    private fun changePassword() {
        val box = column(surface).apply { setPadding(dp(8), 0, dp(8), 0) }
        listOf("Mật khẩu hiện tại", "Mật khẩu mới", "Xác nhận mật khẩu mới").forEach { box.addView(input(it, true)) }
        AlertDialog.Builder(this)
            .setTitle("Đổi mật khẩu")
            .setView(box)
            .setPositiveButton("Cập nhật") { _, _ -> toast("UI hoàn tất; backend auth chưa deploy.") }
            .setNegativeButton("Hủy", null)
            .show()
    }

    private fun preview(name: String) {
        AlertDialog.Builder(this)
            .setTitle(name)
            .setMessage("Luồng $name đã có trong Beta UI Preview. Ghi dữ liệu thật sẽ bật sau Apps Script authoritative API để bảo đảm idempotency, locking và phân quyền.")
            .setPositiveButton("OK", null)
            .show()
    }

    private fun bar(title: String, back: Boolean): View = row(surface).apply {
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(12), dp(8), dp(12), dp(8))
        elevation = dp(1).toFloat()
        if (back) addView(txt("‹", 34f, tealDark, false).apply {
            gravity = Gravity.CENTER
            setOnClickListener { dashboard() }
        }, size(dp(42), dp(48)))
        addView(txt(title, 19f, ink, true), LinearLayout.LayoutParams(0, -2, 1f))
        addView(column(surface).apply {
            gravity = Gravity.END
            addView(txt(userName, 12f, ink, true))
            addView(txt("Điều phối", 10f, muted, false))
        })
    }

    private fun card(symbol: String, title: String, color: Int, fg: Int, click: () -> Unit): View = column(color).apply {
        gravity = Gravity.CENTER
        background = round(color, 14)
        addView(txt(symbol, 26f, fg, true).center())
        addView(txt(title, 13f, fg, true).center())
        setOnClickListener { click() }
    }

    private fun cards(a: View, b: View): View = row(bg).apply {
        addView(a, LinearLayout.LayoutParams(0, dp(112), 1f).apply { marginEnd = dp(6); topMargin = dp(6); bottomMargin = dp(6) })
        addView(b, LinearLayout.LayoutParams(0, dp(112), 1f).apply { marginStart = dp(6); topMargin = dp(6); bottomMargin = dp(6) })
    }

    private fun setting(title: String, sub: String, click: () -> Unit): View = column(surface).apply {
        setPadding(dp(14), dp(13), dp(14), dp(13))
        background = round(surface, 13)
        elevation = dp(1).toFloat()
        addView(txt(title, 15f, ink, true))
        addView(txt(sub, 11.5f, muted, false))
        setOnClickListener { click() }
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) }
    }

    private fun section(value: String) = txt(value, 16f, ink, true).apply { setPadding(0, dp(14), 0, dp(4)) }
    private fun input(hintValue: String, password: Boolean) = EditText(this).apply {
        hint = hintValue
        textSize = 15f
        setTextColor(ink)
        setHintTextColor(Color.rgb(150, 165, 170))
        inputType = if (password) InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT
        setPadding(dp(13), dp(11), dp(13), dp(11))
        background = outline()
    }
    private fun labelled(label: String, view: View) = column(surface).apply {
        setBackgroundColor(bg)
        addView(txt(label, 12f, ink, true))
        addView(gap(5))
        addView(view, matchWrap())
    }
    private fun spinner(items: Array<String>) = Spinner(this).apply {
        adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, items)
        setPadding(dp(8), dp(4), dp(8), dp(4))
        background = outline()
    }
    private fun action(title: String, click: () -> Unit) = Button(this).apply {
        text = title
        textSize = 14f
        setTextColor(Color.WHITE)
        typeface = Typeface.DEFAULT_BOLD
        isAllCaps = false
        minHeight = dp(50)
        background = round(teal, 12)
        setOnClickListener { click() }
    }
    private fun chip(value: String) = txt(value, 10.5f, tealDark, true).apply {
        setPadding(dp(10), dp(6), dp(10), dp(6))
        background = round(Color.rgb(225, 247, 247), 50)
        gravity = Gravity.CENTER
    }
    private fun footer() = txt("Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY", 10.5f, muted, false).center()
    private fun txt(value: String, size: Float, color: Int, bold: Boolean) = TextView(this).apply {
        text = value
        textSize = size
        setTextColor(color)
        typeface = if (bold) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
    }
    private fun TextView.center() = apply { gravity = Gravity.CENTER }
    private fun column(color: Int) = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(color) }
    private fun row(color: Int) = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setBackgroundColor(color) }
    private fun gap(height: Int) = Space(this).apply { layoutParams = size(1, dp(height)) }
    private fun round(color: Int, radius: Int) = GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat() }
    private fun outline() = GradientDrawable().apply { setColor(surface); cornerRadius = dp(10).toFloat(); setStroke(dp(1), Color.rgb(214, 225, 228)) }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun size(width: Int, height: Int) = ViewGroup.LayoutParams(width, height)
    private fun matchWrap() = LinearLayout.LayoutParams(-1, -2)
    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}

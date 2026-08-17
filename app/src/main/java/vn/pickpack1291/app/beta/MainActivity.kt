package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.inputmethod.EditorInfo
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID

class MainActivity : Activity() {
    private val navy = Color.rgb(7, 38, 92)
    private val blue = Color.rgb(13, 78, 170)
    private val red = Color.rgb(218, 45, 53)
    private val green = Color.rgb(36, 153, 85)
    private val orange = Color.rgb(241, 143, 24)
    private val teal = Color.rgb(35, 151, 166)
    private val purple = Color.rgb(91, 72, 174)
    private val bg = Color.rgb(248, 250, 253)
    private val surface = Color.WHITE
    private val ink = Color.rgb(22, 33, 49)
    private val muted = Color.rgb(96, 108, 124)
    private val line = Color.rgb(218, 225, 234)

    private val api by lazy { BetaApiClient(applicationContext) }
    private var screen = "LOGIN"
    private var accountLogin = ""
    private var accountName = ""
    private var accountRole = ""
    private var syncText: TextView? = null

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = Color.WHITE
        window.navigationBarColor = Color.WHITE
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        LocalLogManager.installCrashHandler(this)
        LocalLogManager.createDailyIfNeeded(this)
        login()
    }

    private fun login() {
        screen = "LOGIN"
        accountLogin = ""
        accountName = ""
        accountRole = ""
        api.clearToken()

        val body = column(bg).apply {
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(22), dp(22), dp(22), dp(56))
        }
        body.addView(gap(6))
        body.addView(ImageView(this).apply {
            setImageResource(R.drawable.owner_launcher)
            scaleType = ImageView.ScaleType.CENTER_CROP
        }, size(dp(92), dp(92)))
        body.addView(gap(7))
        body.addView(txt("PICK PACK 1291", 21f, navy, true).center())
        body.addView(txt("SUPRA DC HƯNG YÊN", 10.5f, navy, true).center())
        body.addView(gap(17))

        val user = input("Nhập tài khoản", false)
        val savedLogin = getPreferences(MODE_PRIVATE).getString("last_login", "").orEmpty()
        if (savedLogin.isNotBlank()) user.setText(savedLogin)
        val pass = input("Nhập mật khẩu", true)
        pass.imeOptions = EditorInfo.IME_ACTION_DONE

        body.addView(labelled("Tài khoản", user))
        body.addView(gap(10))
        body.addView(labelled("Mật khẩu", pass))
        body.addView(gap(15))

        val loginButton = primaryButton("ĐĂNG NHẬP", navy) { }
        fun submit() {
            val loginId = user.text.toString().trim()
            val password = pass.text.toString()
            if (loginId.isBlank() || password.isBlank()) {
                toast("Nhập tài khoản và mật khẩu.")
                return
            }
            loginButton.isEnabled = false
            loginButton.text = "ĐANG ĐĂNG NHẬP..."
            api.login(loginId, password) { result ->
                runOnUiThread {
                    loginButton.isEnabled = true
                    loginButton.text = "ĐĂNG NHẬP"
                    if (!result.ok) {
                        showApiError(result.error ?: "Đăng nhập thất bại")
                        return@runOnUiThread
                    }
                    val account = result.json?.optJSONObject("account") ?: JSONObject()
                    accountLogin = account.optString("login_id", loginId)
                    accountName = account.optString("display_name", accountLogin)
                    accountRole = account.optString("role", "USER")
                    getPreferences(MODE_PRIVATE).edit().putString("last_login", accountLogin).apply()
                    pass.setText("")
                    dashboard()
                }
            }
        }
        loginButton.setOnClickListener { submit() }
        pass.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) { submit(); true } else false
        }
        body.addView(loginButton, matchWrap())
        body.addView(gap(10))
        body.addView(txt("PUBLIC BETA • dữ liệu nghiệp vụ thật", 10.5f, blue, true).center())
        body.addView(txt("Đăng nhập được xác thực phía server; APK không chứa mật khẩu hoặc khóa Google.", 9.5f, muted, false).center())

        setScreen(ScrollView(this).apply { isFillViewport = true; addView(body) })
    }

    private fun dashboard() {
        screen = "DASHBOARD"
        val root = column(bg)
        root.addView(appBar("Trang chủ", false))

        val body = column(bg).apply { setPadding(dp(14), dp(15), dp(14), dp(54)) }
        body.addView(fullCard("▣", "QUÉT QR NHÂN SỰ", blue, { employeeScan() }, dp(92)))
        body.addView(gap(9))
        body.addView(cardRow(
            tile("◉", "CÔNG NHẬT", green) { comingSoon("CÔNG NHẬT") },
            tile("⌘", "TÀI NGUYÊN", orange) { comingSoon("TÀI NGUYÊN") }
        ))
        body.addView(cardRow(
            tile("☷", "DANH SÁCH", Color.rgb(58, 91, 183)) { comingSoon("DANH SÁCH") },
            tile("▥", "BÁO CÁO", teal) { comingSoon("BÁO CÁO") }
        ))
        body.addView(gap(1))
        body.addView(fullCard("⚙", "CÀI ĐẶT", navy, { settings() }, dp(66)))
        body.addView(gap(15))

        syncText = txt("●  Đang kiểm tra kết nối...", 10.5f, muted, false).apply {
            setPadding(dp(10), dp(9), dp(10), dp(9))
            background = outlineBg(surface, 9)
        }
        body.addView(syncText, matchWrap())

        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
        refreshSyncStatus()
    }

    private fun employeeScan(initialMnv: String = "") {
        screen = "EMPLOYEE_SCAN"
        val root = column(bg)
        root.addView(appBar("QUÉT QR NHÂN SỰ", true))
        val body = column(bg).apply { setPadding(dp(16), dp(16), dp(16), dp(58)) }
        body.addView(txt("Mã nhân viên", 12f, ink, true))
        body.addView(gap(5))
        val mnv = input("Quét QR hoặc nhập MNV", false).apply {
            setSingleLine(true)
            imeOptions = EditorInfo.IME_ACTION_DONE
            setText(initialMnv)
            if (initialMnv.isNotBlank()) setSelection(text.length)
        }
        body.addView(mnv, matchWrap())
        body.addView(gap(10))
        val check = primaryButton("KIỂM TRA", navy) { }
        fun submit() {
            val value = mnv.text.toString().trim()
            if (value.isBlank()) { toast("Quét QR hoặc nhập MNV."); return }
            check.isEnabled = false
            check.text = "ĐANG KIỂM TRA..."
            checkEmployee(value, check)
        }
        check.setOnClickListener { submit() }
        mnv.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) { submit(); true } else false
        }
        body.addView(check, matchWrap())
        body.addView(gap(12))
        body.addView(infoBox("Màn hình ban đầu chỉ yêu cầu MNV. Server sẽ tự xác định trạng thái CHƯA VÀO / ĐANG TRONG PHIÊN / ĐÃ HẾT PHIÊN."))
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
        mnv.requestFocus()
    }

    private fun checkEmployee(mnv: String, button: Button? = null) {
        api.call("employee_context", JSONObject().put("mnv", mnv)) { result ->
            runOnUiThread {
                button?.isEnabled = true
                button?.text = "KIỂM TRA"
                if (!result.ok) {
                    if (result.code == 401) { sessionExpired(); return@runOnUiThread }
                    showApiError(result.error ?: "Không kiểm tra được nhân sự")
                    return@runOnUiThread
                }
                val ctx = result.json ?: JSONObject()
                if (ctx.optString("state") == "NOT_ENTERED") {
                    renderEmployeeContext(ctx, null, true)
                    api.call("master_options") { masters ->
                        runOnUiThread {
                            if (masters.code == 401) { sessionExpired(); return@runOnUiThread }
                            renderEmployeeContext(ctx, if (masters.ok) masters.json else JSONObject(), false)
                        }
                    }
                } else {
                    renderEmployeeContext(ctx, null, false)
                }
            }
        }
    }

    private fun renderEmployeeContext(ctx: JSONObject, masters: JSONObject?, loadingMasters: Boolean) {
        screen = "EMPLOYEE_CONTEXT"
        val employee = ctx.optJSONObject("employee") ?: JSONObject()
        val state = ctx.optString("state")
        val root = column(bg)
        root.addView(appBar("QUÉT QR NHÂN SỰ", true))
        val body = column(bg).apply { setPadding(dp(16), dp(14), dp(16), dp(58)) }

        val scanAgain = primaryButton("QUÉT / NHẬP MNV KHÁC", navy) { employeeScan() }
        body.addView(scanAgain, matchWrap())
        body.addView(gap(11))
        body.addView(employeeCard(employee))
        body.addView(gap(12))

        when (state) {
            "ACTIVE" -> renderActive(body, ctx)
            "ENDED" -> renderEnded(body, ctx)
            else -> {
                if (loadingMasters) {
                    body.addView(statusBox("Đang tải tài nguyên khả dụng...", blue, Color.rgb(237, 244, 255)))
                } else {
                    renderEnter(body, ctx, masters ?: JSONObject())
                }
            }
        }

        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
    }

    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val s = ctx.optJSONObject("session") ?: JSONObject()
        body.addView(statusBox("ĐANG TRONG PHIÊN", green, Color.rgb(235, 248, 239)))
        body.addView(gap(9))
        body.addView(detailCard(listOf(
            "Ca" to s.optString("shift"),
            "Vị trí trong ca" to s.optString("work_choice"),
            "Vào lúc" to formatIso(s.optString("enter_at")),
            "PDA" to dash(s.optString("pda_serial")),
            "User Pick" to dash(s.optString("user_pick")),
            "Bàn Pack" to dash(s.optString("pack_table")),
            "User Pack" to dash(s.optString("user_pack"))
        )))
        body.addView(gap(15))
        val exit = primaryButton("RA CA", red) { }
        exit.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Xác nhận RA CA")
                .setMessage("MNV ${s.optString("mnv")} sẽ kết thúc phiên hôm nay và trả các tài nguyên đang giữ. Tiếp tục?")
                .setNegativeButton("Hủy", null)
                .setPositiveButton("RA CA") { _, _ -> performExit(s.optString("mnv"), exit) }
                .show()
        }
        body.addView(exit, matchWrap())
    }

    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val s = ctx.optJSONObject("session") ?: JSONObject()
        body.addView(statusBox("ĐÃ HẾT PHIÊN VÀO / RA HÔM NAY", red, Color.rgb(255, 238, 239)))
        body.addView(gap(9))
        body.addView(detailCard(listOf(
            "Ca" to s.optString("shift"),
            "Vị trí trong ca" to s.optString("work_choice"),
            "Vào lúc" to formatIso(s.optString("enter_at")),
            "Ra lúc" to formatIso(s.optString("exit_at"))
        )))
        body.addView(gap(11))
        body.addView(infoBox("Phiên hợp lệ của MNV này đã kết thúc. Luồng thường không cho VÀO lại trong cùng ngày; correction sẽ do ADMIN/SUPERADMIN xử lý ở chức năng riêng."))
    }

    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val employee = ctx.optJSONObject("employee") ?: JSONObject()
        val mnv = employee.optString("mnv")
        body.addView(statusBox("CHƯA VÀO CA", blue, Color.rgb(237, 244, 255)))
        body.addView(gap(11))

        val shift = spinner(arrayOf("Ca 1", "Ca 2", "HC"))
        val choice = spinner(arrayOf("KHÔNG", "PICK", "PACK"))
        when {
            employee.optString("main_position").contains("Pick", true) -> choice.setSelection(1)
            employee.optString("main_position").contains("Pack", true) -> choice.setSelection(2)
        }
        body.addView(labelled("Ca làm việc", shift))
        body.addView(gap(10))
        body.addView(labelled("Vị trí trong ca", choice))
        body.addView(gap(10))

        val resourceBox = column(bg)
        body.addView(resourceBox, matchWrap())

        val pdas = masters.optJSONArray("pdas") ?: JSONArray()
        val picks = masters.optJSONArray("user_picks") ?: JSONArray()
        val packs = masters.optJSONArray("pack_tables") ?: JSONArray()
        var pdaSpinner: Spinner? = null
        var pickSpinner: Spinner? = null
        var packSpinner: Spinner? = null
        val pdaSerials = mutableListOf<String>()
        val pickValues = mutableListOf<String?>()
        val packValues = mutableListOf<String>()

        fun rebuildResources() {
            resourceBox.removeAllViews()
            pdaSpinner = null; pickSpinner = null; packSpinner = null
            pdaSerials.clear(); pickValues.clear(); packValues.clear()
            when (choice.selectedItem.toString()) {
                "PICK" -> {
                    val pdaLabels = mutableListOf<String>()
                    for (i in 0 until pdas.length()) {
                        val p = pdas.optJSONObject(i) ?: continue
                        val serial = p.optString("serial")
                        if (serial.isBlank()) continue
                        pdaSerials.add(serial)
                        pdaLabels.add("${p.optString("last5")} • $serial")
                    }
                    pdaSpinner = spinner((if (pdaLabels.isEmpty()) listOf("Không có PDA khả dụng") else pdaLabels).toTypedArray())
                    resourceBox.addView(labelled("PDA (bắt buộc)", pdaSpinner!!))
                    resourceBox.addView(gap(10))
                    val pickLabels = mutableListOf("Không dùng User Pick")
                    pickValues.add(null)
                    for (i in 0 until picks.length()) {
                        val v = picks.optString(i)
                        if (v.isNotBlank()) { pickLabels.add(v); pickValues.add(v) }
                    }
                    pickSpinner = spinner(pickLabels.toTypedArray())
                    resourceBox.addView(labelled("User Pick (tùy chọn)", pickSpinner!!))
                }
                "PACK" -> {
                    val packLabels = mutableListOf<String>()
                    for (i in 0 until packs.length()) {
                        val p = packs.optJSONObject(i) ?: continue
                        val table = p.optString("table")
                        if (table.isBlank()) continue
                        packValues.add(table)
                        packLabels.add("$table • ${p.optString("user_pack")}")
                    }
                    packSpinner = spinner((if (packLabels.isEmpty()) listOf("Không có bàn Pack khả dụng") else packLabels).toTypedArray())
                    resourceBox.addView(labelled("Bàn Pack + User Pack", packSpinner!!))
                }
                else -> resourceBox.addView(infoBox("Không cấp PDA / User Pick / Bàn Pack cho lựa chọn KHÔNG."))
            }
        }
        choice.onItemSelectedListener = object : android.widget.AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: android.widget.AdapterView<*>?, view: View?, position: Int, id: Long) = rebuildResources()
            override fun onNothingSelected(parent: android.widget.AdapterView<*>?) = Unit
        }
        rebuildResources()
        body.addView(gap(15))

        val enter = primaryButton("VÀO CA", blue) { }
        enter.setOnClickListener {
            val work = choice.selectedItem.toString()
            val payload = JSONObject().apply {
                put("event_id", UUID.randomUUID().toString())
                put("mnv", mnv)
                put("shift", shift.selectedItem.toString())
                put("work_choice", work)
            }
            if (work == "PICK") {
                if (pdaSerials.isEmpty()) { showApiError("Không còn PDA khả dụng."); return@setOnClickListener }
                payload.put("pda_serial", pdaSerials[pdaSpinner?.selectedItemPosition ?: 0])
                val selectedPick = pickValues.getOrNull(pickSpinner?.selectedItemPosition ?: 0)
                if (!selectedPick.isNullOrBlank()) payload.put("user_pick", selectedPick)
            }
            if (work == "PACK") {
                if (packValues.isEmpty()) { showApiError("Không còn bàn Pack + User Pack khả dụng."); return@setOnClickListener }
                payload.put("pack_table", packValues[packSpinner?.selectedItemPosition ?: 0])
            }
            enter.isEnabled = false
            enter.text = "ĐANG VÀO CA..."
            api.call("enter", payload) { result ->
                runOnUiThread {
                    enter.isEnabled = true
                    enter.text = "VÀO CA"
                    if (!result.ok) {
                        if (result.code == 401) sessionExpired() else showApiError(result.error ?: "VÀO CA thất bại")
                    } else {
                        toast("VÀO CA thành công")
                        checkEmployee(mnv)
                    }
                }
            }
        }
        body.addView(enter, matchWrap())
        body.addView(gap(9))
        body.addView(txt("Mọi thao tác Beta đều có event_id và được ACK server trước khi UI đổi trạng thái.", 9.5f, muted, false))
    }

    private fun performExit(mnv: String, button: Button) {
        button.isEnabled = false
        button.text = "ĐANG RA CA..."
        api.call("exit", JSONObject().apply {
            put("event_id", UUID.randomUUID().toString())
            put("mnv", mnv)
        }) { result ->
            runOnUiThread {
                button.isEnabled = true
                button.text = "RA CA"
                if (!result.ok) {
                    if (result.code == 401) sessionExpired() else showApiError(result.error ?: "RA CA thất bại")
                } else {
                    toast("RA CA thành công")
                    checkEmployee(mnv)
                }
            }
        }
    }

    private fun settings() {
        screen = "SETTINGS"
        val root = column(bg)
        root.addView(appBar("CÀI ĐẶT", true))
        val body = column(bg).apply { setPadding(dp(16), dp(13), dp(16), dp(58)) }
        body.addView(section("Tài khoản"))
        body.addView(setting("Đang đăng nhập", "$accountName • ${roleText(accountRole)}") {})
        body.addView(section("Đồng bộ / dữ liệu"))
        val live = setting("Trạng thái Beta", "Đang đọc trạng thái server...") { refreshSettingsStatus() }
        body.addView(live)
        live.tag = "syncSetting"
        body.addView(section("Nhật ký"))
        body.addView(setting("Tạo báo lỗi thủ công", "Tạo diagnostic bundle local đã loại thông tin xác thực") {
            val f = LocalLogManager.createManualReport(this, screen, "PUBLIC_BETA")
            AlertDialog.Builder(this).setTitle("Đã tạo báo lỗi").setMessage("Đã lưu local: ${f.name}").setPositiveButton("OK", null).show()
        })
        body.addView(section("Phiên bản"))
        body.addView(setting("Public Beta", "0.2.0-beta.1 • Mẫu 1 • backend thật") {})
        body.addView(section("Thiết bị"))
        body.addView(setting("Thông tin thiết bị", "Android ${Build.VERSION.RELEASE} • ${Build.MANUFACTURER} ${Build.MODEL}") {})
        body.addView(gap(15))
        body.addView(primaryButton("ĐĂNG XUẤT", red) {
            api.call("logout") { runOnUiThread { login() } }
        }, matchWrap())
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
        refreshSettingsStatus()
    }

    private fun refreshSettingsStatus() {
        api.call("sync_status") { result ->
            runOnUiThread {
                if (result.code == 401) { sessionExpired(); return@runOnUiThread }
                val j = result.json
                val text = if (result.ok && j != null) {
                    "Server seq: ${j.optLong("server_seq", 0)} • projection Sheet đang chờ ACK: ${j.optInt("projection_pending", 0)}"
                } else "Không đọc được trạng thái server"
                findViewWithTag<View>("syncSetting")?.let { v ->
                    if (v is LinearLayout && v.childCount > 1) (v.getChildAt(1) as? TextView)?.text = text
                }
            }
        }
    }

    private fun refreshSyncStatus() {
        api.call("sync_status") { result ->
            runOnUiThread {
                if (result.code == 401) { sessionExpired(); return@runOnUiThread }
                if (result.ok) {
                    val j = result.json ?: JSONObject()
                    val pending = j.optInt("projection_pending", 0)
                    syncText?.text = "●  Đã kết nối • Seq ${j.optLong("server_seq", 0)} • chờ Sheet ACK: $pending"
                    syncText?.setTextColor(if (pending == 0) green else orange)
                } else {
                    syncText?.text = "●  Mất kết nối • chạm Cài đặt để kiểm tra"
                    syncText?.setTextColor(red)
                }
            }
        }
    }

    private fun comingSoon(name: String) {
        AlertDialog.Builder(this)
            .setTitle(name)
            .setMessage("Public Beta hiện đã bật thao tác thật cho Đăng nhập + QUÉT QR NHÂN SỰ + VÀO/RA. Module $name sẽ được nối tiếp vào cùng backend sau khi chốt vòng test này.")
            .setPositiveButton("OK", null)
            .show()
    }

    private fun employeeCard(e: JSONObject): View = column(surface).apply {
        setPadding(dp(14), dp(13), dp(14), dp(13))
        background = outlineBg(surface, 10)
        addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}", 16f, navy, true))
        addView(gap(4))
        addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}", 11f, ink, false))
        addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}", 10.5f, muted, false))
    }

    private fun detailCard(items: List<Pair<String, String>>): View = column(surface).apply {
        setPadding(dp(14), dp(10), dp(14), dp(10))
        background = outlineBg(surface, 10)
        items.forEach { (k, v) ->
            addView(row(surface).apply {
                addView(txt(k, 10.5f, muted, false), LinearLayout.LayoutParams(0, -2, 0.45f))
                addView(txt(if (v.isBlank()) "—" else v, 10.8f, ink, true).apply { gravity = Gravity.END }, LinearLayout.LayoutParams(0, -2, 0.55f))
                setPadding(0, dp(4), 0, dp(4))
            })
        }
    }

    private fun appBar(title: String, back: Boolean): View = row(navy).apply {
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(9), dp(7), dp(10), dp(7))
        if (back) addView(txt("‹", 31f, Color.WHITE, false).apply {
            gravity = Gravity.CENTER
            setOnClickListener { dashboard() }
        }, size(dp(42), dp(45))) else addView(txt("☰", 22f, Color.WHITE, false).apply { gravity = Gravity.CENTER }, size(dp(42), dp(45)))
        addView(txt(title, 17f, Color.WHITE, true), LinearLayout.LayoutParams(0, -2, 1f))
        addView(column(navy).apply {
            gravity = Gravity.END
            addView(txt(if (accountLogin.isBlank()) "Beta" else accountLogin, 10.5f, Color.WHITE, true).apply { gravity = Gravity.END })
            addView(txt(roleText(accountRole), 8.5f, Color.rgb(218, 229, 248), false).apply { gravity = Gravity.END })
        })
    }

    private fun fullCard(symbol: String, title: String, color: Int, click: () -> Unit, height: Int): View = row(color).apply {
        gravity = Gravity.CENTER
        background = round(color, 7)
        addView(txt(symbol, 25f, Color.WHITE, true).apply { gravity = Gravity.CENTER }, size(dp(47), -1))
        addView(txt(title, 14f, Color.WHITE, true).apply { gravity = Gravity.CENTER_VERTICAL })
        setOnClickListener { click() }
        layoutParams = LinearLayout.LayoutParams(-1, height)
    }

    private fun tile(symbol: String, title: String, color: Int, click: () -> Unit): View = column(color).apply {
        gravity = Gravity.CENTER
        background = round(color, 7)
        addView(txt(symbol, 24f, Color.WHITE, true).center())
        addView(gap(3))
        addView(txt(title, 11.5f, Color.WHITE, true).center())
        setOnClickListener { click() }
    }

    private fun cardRow(a: View, b: View): View = row(bg).apply {
        addView(a, LinearLayout.LayoutParams(0, dp(94), 1f).apply { marginEnd = dp(5); topMargin = dp(5); bottomMargin = dp(5) })
        addView(b, LinearLayout.LayoutParams(0, dp(94), 1f).apply { marginStart = dp(5); topMargin = dp(5); bottomMargin = dp(5) })
    }

    private fun statusBox(text: String, fg: Int, color: Int) = txt(text, 11.5f, fg, true).apply {
        gravity = Gravity.CENTER
        setPadding(dp(10), dp(10), dp(10), dp(10))
        background = round(color, 9)
    }

    private fun infoBox(text: String) = txt(text, 10.5f, muted, false).apply {
        setPadding(dp(12), dp(10), dp(12), dp(10))
        background = outlineBg(Color.rgb(244, 247, 251), 9)
    }

    private fun setting(title: String, sub: String, click: () -> Unit): View = column(surface).apply {
        setPadding(dp(13), dp(11), dp(13), dp(11))
        background = outlineBg(surface, 9)
        addView(txt(title, 13.5f, ink, true))
        addView(txt(sub, 10f, muted, false))
        setOnClickListener { click() }
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(7) }
    }

    private fun section(value: String) = txt(value, 13.5f, navy, true).apply { setPadding(0, dp(12), 0, dp(2)) }

    private fun input(hintValue: String, password: Boolean) = EditText(this).apply {
        hint = hintValue
        textSize = 14f
        setTextColor(ink)
        setHintTextColor(Color.rgb(153, 163, 176))
        inputType = if (password) InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT
        setPadding(dp(12), dp(9), dp(12), dp(9))
        minHeight = dp(46)
        background = outline()
    }

    private fun labelled(label: String, view: View) = column(bg).apply {
        addView(txt(label, 10.5f, ink, true))
        addView(gap(4))
        addView(view, matchWrap())
    }

    private fun spinner(items: Array<String>) = Spinner(this).apply {
        adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, items)
        setPadding(dp(7), dp(3), dp(7), dp(3))
        minimumHeight = dp(46)
        background = outline()
    }

    private fun primaryButton(title: String, color: Int, click: () -> Unit) = Button(this).apply {
        text = title
        textSize = 12.5f
        setTextColor(Color.WHITE)
        typeface = Typeface.DEFAULT_BOLD
        isAllCaps = false
        minHeight = dp(48)
        background = round(color, 7)
        setOnClickListener { click() }
    }

    private fun setScreen(content: View) {
        setContentView(host(content))
    }

    private fun host(content: View): View {
        val root = FrameLayout(this).apply { setBackgroundColor(bg) }
        root.addView(content, FrameLayout.LayoutParams(-1, -1).apply { bottomMargin = dp(28) })
        val footer = txt(FOOTER, 8.2f, Color.rgb(113, 122, 136), false).apply {
            gravity = Gravity.CENTER
            setPadding(dp(5), dp(2), dp(5), dp(3))
            maxLines = 1
        }
        root.addView(footer, FrameLayout.LayoutParams(-1, dp(25), Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL))
        root.setOnApplyWindowInsetsListener { v, insets ->
            val top: Int
            val bottom: Int
            if (Build.VERSION.SDK_INT >= 30) {
                top = insets.getInsets(WindowInsets.Type.statusBars()).top
                bottom = insets.getInsets(WindowInsets.Type.navigationBars()).bottom
            } else {
                @Suppress("DEPRECATION")
                top = insets.systemWindowInsetTop
                @Suppress("DEPRECATION")
                bottom = insets.systemWindowInsetBottom
            }
            v.setPadding(0, top + dp(7), 0, bottom + dp(3))
            insets
        }
        root.requestApplyInsets()
        return root
    }

    private fun showApiError(raw: String) {
        val msg = when {
            raw.contains("INVALID_CREDENTIALS") -> "Sai tài khoản hoặc mật khẩu."
            raw.contains("LOGIN_TEMP_LOCKED") -> "Đăng nhập sai nhiều lần. Tài khoản đang tạm khóa 15 phút."
            raw.contains("EMPLOYEE_NOT_FOUND") -> "Không tìm thấy MNV trong danh sách nhân sự."
            raw.contains("PP_SESSION_ALREADY_ACTIVE") -> "Nhân sự đã VÀO CA. Đang tải lại trạng thái mới nhất."
            raw.contains("PP_SESSION_ALREADY_ENDED") -> "Nhân sự đã hết phiên VÀO/RA hôm nay."
            raw.contains("PP_SESSION_NOT_ENTERED") -> "Nhân sự chưa có phiên VÀO CA để RA."
            raw.contains("PP_RESOURCE_CONFLICT") -> "Tài nguyên vừa được người khác nhận. Hãy kiểm tra lại tài nguyên khả dụng."
            raw.contains("PP_USER_PICK_USED_TODAY") -> "User Pick này đã được dùng trong ngày."
            raw.contains("PP_USER_PACK_USED_TODAY") -> "User Pack của bàn này đã được dùng trong ngày."
            raw.contains("PDA_INVALID") -> "PDA không còn hợp lệ/khả dụng."
            raw.contains("USER_PICK_INVALID") -> "User Pick không còn hợp lệ/khả dụng."
            raw.contains("PACK_TABLE_INVALID") -> "Bàn Pack không còn hợp lệ/khả dụng."
            raw.contains("SHEET_HTTP") -> "Server chưa đọc được dữ liệu master Google Sheet."
            raw.contains("UNAUTHORIZED") -> "Phiên đăng nhập đã hết hạn."
            raw.contains("SERVER_ERROR") -> "Server gặp lỗi. Không có thao tác nào được xác nhận."
            else -> raw
        }
        AlertDialog.Builder(this).setTitle("Không thực hiện được").setMessage(msg).setPositiveButton("OK", null).show()
    }

    private fun sessionExpired() {
        AlertDialog.Builder(this).setTitle("Phiên đã hết hạn").setMessage("Đăng nhập lại để tiếp tục.").setPositiveButton("ĐĂNG NHẬP") { _, _ -> login() }.setCancelable(false).show()
    }

    private fun roleText(role: String): String = when (role) {
        "SUPERADMIN" -> "Superadmin"
        "ADMIN" -> "Admin"
        "USER" -> "Điều phối"
        else -> "Public Beta"
    }

    private fun formatIso(value: String): String {
        if (value.isBlank() || value == "null") return "—"
        return try {
            Instant.parse(value).atZone(ZoneId.of("Asia/Bangkok")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))
        } catch (_: Throwable) { value }
    }

    private fun dash(v: String): String = v.takeIf { it.isNotBlank() && it != "null" } ?: "—"
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
    private fun outline() = GradientDrawable().apply { setColor(surface); cornerRadius = dp(7).toFloat(); setStroke(dp(1), line) }
    private fun outlineBg(color: Int, radius: Int) = GradientDrawable().apply { setColor(color); cornerRadius = dp(radius).toFloat(); setStroke(dp(1), line) }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun size(w: Int, h: Int) = ViewGroup.LayoutParams(w, h)
    private fun matchWrap() = LinearLayout.LayoutParams(-1, -2)
    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()

    companion object {
        private const val FOOTER = "Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY"
    }
}

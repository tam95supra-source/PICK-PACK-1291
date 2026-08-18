package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.text.method.DigitsKeyListener
import android.view.KeyEvent
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

class FullBetaActivity : Activity() {
    private val navy:Int get() = ThemeManager.primaryDark(this)
    private val blue:Int get() = ThemeManager.primary(this)
    private val red = Color.rgb(218, 45, 53)
    private val green = Color.rgb(36, 153, 85)
    private val orange = Color.rgb(217, 119, 6)
    private val teal:Int get() = ThemeManager.primary(this)
    private val bg:Int get() = ThemeManager.background(this)
    private val surface = Color.WHITE
    private val ink = Color.rgb(24, 44, 42)
    private val muted = Color.rgb(100, 116, 139)
    private val line:Int get() = ThemeManager.line(this)

    private val api by lazy { BetaApiClient(applicationContext) }
    private val syncApi by lazy { BetaApiClient(applicationContext) }
    private val cacheApi by lazy { BetaApiClient(applicationContext) }
    private var accountLogin = ""
    private var accountName = ""
    private var accountRole = ""
    private var accountPosition = ""
    private var accountEmail = ""
    private var syncText: TextView? = null
    private var currentScreen = "LOGIN"
    private var liveEmployeeMnv = ""
    private val foregroundSync by lazy {
        ForegroundSyncCoordinator(this, syncApi, object : ForegroundSyncCoordinator.Listener {
            override fun onStatus(status: ForegroundSyncCoordinator.Status) {
                UpdateManager.check(this@FullBetaActivity)
                if (status.connected) {
                    syncText?.text = "✓ Online • R${status.serverSeq}"
                    syncText?.setTextColor(green)
                } else {
                    syncText?.text = "! Offline"
                    syncText?.setTextColor(red)
                }
                if (status.masterChanged || status.masterRevision != MasterDataCache.revision(this@FullBetaActivity)) refreshMasterCache()
                if (status.changed && liveEmployeeMnv.isNotBlank()) loadEmployee(liveEmployeeMnv)
            }

            override fun onAuthExpired() { sessionExpired() }
        })
    }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = Color.WHITE
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        LocalLogManager.installCrashHandler(this)
        LocalLogManager.createDailyIfNeeded(this)
        MasterDataCache.hydrate(this)
        restoreOrLogin()
    }

    override fun onStart() {
        super.onStart()
        UpdateManager.check(this, force = true)
        if (api.token != null) foregroundSync.start()
    }

    override fun onStop() {
        foregroundSync.stop()
        super.onStop()
    }

    private fun restoreOrLogin() {
        val saved = api.restoredAccount()
        if (api.token.isNullOrBlank() || saved == null) { login(); return }
        accountLogin = saved.optString("login_id")
        accountName = saved.optString("display_name", accountLogin)
        accountRole = saved.optString("role", "USER")
        accountPosition = saved.optString("position", "")
        accountEmail = saved.optString("email", "")
        LocalLogManager.uploadAutomaticPending(this, api)
        dashboard()
        foregroundSync.start()
    }

    private fun login() {
        foregroundSync.stop()
        liveEmployeeMnv = ""
        currentScreen = "LOGIN"
        accountLogin = ""; accountName = ""; accountRole = ""; accountPosition = ""; accountEmail = ""

        val user = input("Nhập tài khoản", false)
        val saved = getPreferences(MODE_PRIVATE).getString("last_login", "").orEmpty()
        if (saved.isNotBlank()) user.setText(saved)
        val pass = input("Nhập mật khẩu", true).apply { imeOptions = EditorInfo.IME_ACTION_DONE }

        val card = column(surface).apply {
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(22), dp(22), dp(22), dp(22))
            background = outlineBg(surface, 14)
        }
        card.addView(ImageView(this).apply { setImageResource(R.drawable.owner_launcher); scaleType = ImageView.ScaleType.CENTER_CROP }, size(dp(98), dp(98)))
        card.addView(gap(9))
        card.addView(txt("PICK PACK 1291", 22f, navy, true).center())
        card.addView(txt("SUPRA DC HƯNG YÊN", 10.5f, teal, true).center())
        card.addView(gap(20))
        card.addView(labelled("Tài khoản", user)); card.addView(gap(10))
        card.addView(labelled("Mật khẩu", pass)); card.addView(gap(14))

        val button = primary("ĐĂNG NHẬP", teal) {}
        fun submit() {
            val login = user.text.toString().trim(); val password = pass.text.toString()
            if (login.isBlank() || password.isBlank()) { toast("Nhập tài khoản và mật khẩu."); return }
            button.isEnabled = false; button.text = "ĐANG XÁC THỰC..."
            api.login(login, password) { result -> runOnUiThread {
                button.isEnabled = true; button.text = "ĐĂNG NHẬP"
                if (!result.ok) { showError(result.error ?: "Đăng nhập thất bại"); return@runOnUiThread }
                val a = result.json?.optJSONObject("account") ?: JSONObject()
                accountLogin = a.optString("login_id", login)
                accountName = a.optString("display_name", accountLogin)
                accountRole = a.optString("role", "USER")
                accountPosition = a.optString("position", "")
                accountEmail = a.optString("email", "")
                getPreferences(MODE_PRIVATE).edit().putString("last_login", accountLogin).apply()
                pass.setText("")
                if (MasterDataCache.revision(this@FullBetaActivity) == 0L) refreshMasterCache()
                LocalLogManager.uploadAutomaticPending(this@FullBetaActivity, api)
                dashboard()
                foregroundSync.start()
            } }
        }
        button.setOnClickListener { submit() }
        pass.setOnEditorActionListener { _, actionId, _ -> if (actionId == EditorInfo.IME_ACTION_DONE) { submit(); true } else false }
        card.addView(button, matchWrap())
        card.addView(gap(9))
        card.addView(TextView(this).apply {
            text = "QUÊN MẬT KHẨU?"
            textSize = 11.5f
            setTextColor(teal)
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
            setPadding(dp(8), dp(8), dp(8), dp(8))
            setOnClickListener {
                val loginId = user.text.toString().trim()
                if (loginId.isBlank()) { toast("Nhập đúng tài khoản trước khi chọn Quên mật khẩu."); return@setOnClickListener }
                isEnabled = false
                text = "ĐANG GỬI YÊU CẦU..."
                api.forgotPassword(loginId) { r -> runOnUiThread {
                    isEnabled = true; text = "QUÊN MẬT KHẨU?"
                    if (!r.ok) { showError(r.error ?: "Không gửi được yêu cầu đặt lại mật khẩu"); return@runOnUiThread }
                    TopNotice.show(this@FullBetaActivity,"Nếu tài khoản hợp lệ, mật khẩu mới đã được gửi tới mail đã cấu hình.",TopNotice.Kind.SUCCESS)
                } }
            }
        }, matchWrap())

        val holder = FrameLayout(this).apply {
            setBackgroundColor(bg)
            minimumHeight = (resources.displayMetrics.heightPixels - dp(70)).coerceAtLeast(dp(560))
            setPadding(dp(18), dp(12), dp(18), dp(12))
            addView(card, FrameLayout.LayoutParams(-1, -2, Gravity.CENTER))
        }
        setScreen(ScrollView(this).apply { isFillViewport = true; addView(holder) })
    }

    private fun dashboard() {
        currentScreen = "DASHBOARD"
        liveEmployeeMnv = ""
        val root=column(bg)
        root.addView(appBar("PICK PACK 1291",false))
        val body=column(bg).apply{setPadding(dp(12),dp(10),dp(12),dp(92))}
        body.addView(txt("Nghiệp vụ",15f,ink,true));body.addView(txt("${accountName.ifBlank{accountLogin}} • ${roleText(accountRole)}",9.8f,muted,false));body.addView(gap(9))
        val hero=column(surface).apply{
  setPadding(dp(14),dp(14),dp(14),dp(14));background=outlineBg(surface,12);setOnClickListener{employeeScan()}
  addView(row(surface).apply{
      addView(txt("▣",27f,teal,true).apply{gravity=Gravity.CENTER},size(dp(52),dp(58)))
      addView(column(surface).apply{addView(txt("QUÉT QR NHÂN SỰ",15f,teal,true));addView(txt("Quét hoặc nhập MNV, Enter/OK để xử lý",10f,muted,false))},LinearLayout.LayoutParams(0,-2,1f))
      addView(txt("›",25f,teal,false).apply{gravity=Gravity.CENTER},size(dp(30),dp(58)))
  },matchWrap())
        }
        body.addView(hero,matchWrap());body.addView(gap(8))
        if(accountRole=="ADMIN"||accountRole=="SUPERADMIN") body.addView(menuRow("◉","Công nhật","Bắt đầu / hoàn thành công nhật") { openModule("LABOR") })
        body.addView(menuRow("▥","Báo cáo nhân sự","Báo cáo vận hành theo ca / ngày") { openModule("REPORT") })
        body.addView(menuRow("☷","Theo dõi ca","Phiên làm việc và công nhật hôm nay") { openModule("LISTS") })
        body.addView(menuRow("↔","Tài nguyên","PDA, User Pick, Bàn Pack / User Pack") { openModule("RESOURCES") })
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root);refreshStatus()
    }

    private fun openModule(module: String, mnv: String = "") {
        startActivity(Intent(this, OperationsActivity::class.java).apply {
            putExtra("module", module); putExtra("login", accountLogin); putExtra("name", accountName); putExtra("role", accountRole); putExtra("position", accountPosition); putExtra("email", accountEmail); putExtra("mnv", mnv)
        })
    }

    private fun employeeScan() {
        currentScreen = "SCAN"; liveEmployeeMnv = ""
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ",true))
        val body=column(bg).apply{setPadding(dp(16),dp(16),dp(16),dp(92))}
        val mnv=mnvInput("Quét QR hoặc nhập MNV")
        body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(6))
        body.addView(txt("Nhận Enter/OK từ PDA hoặc bàn phím để chạy ngay.",9.8f,muted,false))
        var busy=false
        fun submit(){val v=mnv.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét MNV.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);mnv.postDelayed({busy=false},600)}
        bindScannerEnter(mnv){submit()}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);mnv.requestFocus()
    }

    private fun loadEmployee(mnv: String, button: Button? = null) {
        val cached = MasterDataCache.employee(this, mnv)
        if (cached != null && currentScreen == "SCAN") renderCachedEmployee(cached)
        api.call("employee_context", JSONObject().put("mnv", mnv).put("include_options", false).put("include_labor", false)) { result -> runOnUiThread {
            button?.isEnabled=true; button?.text="KIỂM TRA"
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){showError(result.error ?: "Không kiểm tra được MNV");return@runOnUiThread}
            val ctx=result.json ?: JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED") {
                val localOptions = MasterDataCache.resourceOptions(this@FullBetaActivity)
                if (localOptions.optJSONArray("pdas") != null) {
                    renderEmployee(ctx, localOptions)
                } else {
                    api.call("master_options", JSONObject().put("mnv", mnv)) { masters -> runOnUiThread {
                        if(masters.code==401){sessionExpired();return@runOnUiThread}
                        renderEmployee(ctx, masters.json ?: JSONObject())
                    } }
                }
            } else renderEmployee(ctx, null)
        } }
    }

    private fun renderCachedEmployee(e: JSONObject) {
        currentScreen = "EMPLOYEE_LOADING"
        val root=column(bg)
        root.addView(appBar("QUÉT QR NHÂN SỰ", true))
        val body=column(bg).apply{setPadding(dp(16),dp(14),dp(16),dp(58))}
        body.addView(employeeCard(e))
        body.addView(gap(10))
        body.addView(status("ĐANG KIỂM TRA PHIÊN...", blue, Color.rgb(237,244,255)))
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root)
    }

    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        currentScreen = "EMPLOYEE"
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val state=ctx.optString("state"); val mnv=e.optString("mnv")
        liveEmployeeMnv = mnv
        val root=column(bg); root.addView(appBar("QUÉT QR NHÂN SỰ", true)); val body=column(bg).apply{setPadding(dp(16),dp(14),dp(16),dp(58))}
        body.addView(primary("QUÉT / NHẬP MNV KHÁC", navy) { employeeScan() }, matchWrap());body.addView(gap(10));body.addView(employeeCard(e));body.addView(gap(11))
        when(state){
            "ACTIVE" -> renderActive(body, ctx)
            "ENDED" -> renderEnded(body, ctx)
            else -> renderEnter(body, ctx, masters ?: JSONObject())
        }
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root)
    }

    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val s=ctx.optJSONObject("session") ?: JSONObject(); val mnv=s.optString("mnv")
        body.addView(status("ĐANG TRONG PHIÊN", green, Color.rgb(235,248,239)));body.addView(gap(8));body.addView(details(listOf(
            "Ca" to s.optString("shift"), "Vị trí trong ca" to s.optString("work_choice"), "Vào lúc" to formatIso(s.optString("enter_at")),
            "PDA" to dash(s.optString("pda_serial")), "User Pick" to dash(s.optString("user_pick")), "Bàn Pack" to dash(s.optString("pack_table")), "User Pack" to dash(s.optString("user_pack"))
        )));body.addView(gap(10))
        body.addView(primary("ĐỔI TÀI NGUYÊN / VỊ TRÍ", orange) { openModule("RESOURCES", mnv) }, matchWrap());body.addView(gap(8))
        val exit=primary("RA CA", red) {}
        exit.setOnClickListener { AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Kết thúc phiên của MNV $mnv và trả tài nguyên đang giữ?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->
            exit.isEnabled=false;exit.text="ĐANG RA CA...";api.call("exit",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv)){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else loadEmployee(mnv)}}
        }.show() }
        body.addView(exit, matchWrap())
    }

    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val s=ctx.optJSONObject("session") ?: JSONObject();body.addView(status("ĐÃ HẾT PHIÊN VÀO / RA HÔM NAY", red, Color.rgb(255,238,239)));body.addView(gap(8));body.addView(details(listOf("Ca" to s.optString("shift"),"Vị trí trong ca" to s.optString("work_choice"),"Vào lúc" to formatIso(s.optString("enter_at")),"Ra lúc" to formatIso(s.optString("exit_at")))))
    }

    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val mnv=e.optString("mnv")
        body.addView(status("CHƯA VÀO CA", teal, Color.rgb(232, 248, 245)));body.addView(gap(8));body.addView(section("PHÂN CÔNG TRONG CA"))
        val shift=spinner(arrayOf("Ca 1","Ca 2","Ca HC"));val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));when{e.optString("main_position").contains("Pick",true)->choice.setSelection(1);e.optString("main_position").contains("Pack",true)->choice.setSelection(2)}
        body.addView(labelled("Ca làm việc",shift));body.addView(gap(8));body.addView(labelled("Vị trí trong ca",choice));body.addView(gap(8))
        val resourceBox=column(bg);body.addView(resourceBox,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray()
        val pickValues=mutableListOf<String>();val packValues=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;var packSpinner:Spinner?=null
        fun rebuild(){resourceBox.removeAllViews();pickValues.clear();packValues.clear();pdaField=null;pickSpinner=null;packSpinner=null;when(choice.selectedItem.toString()){
            "PICK"->{pdaField=pdaInput(pdas);resourceBox.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));resourceBox.addView(gap(8));val labels=mutableListOf("Không dùng User Pick");pickValues.add("");for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){labels.add(v);pickValues.add(v)}};pickSpinner=spinner(labels.toTypedArray());resourceBox.addView(labelled("User Pick (tùy chọn)",pickSpinner!!))}
            "PACK"->{val labels=mutableListOf<String>();val selectedShift=shift.selectedItem.toString();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=selectedShift)continue;val table=p.optString("table");if(table.isNotBlank()){packValues.add(table);labels.add("$table • ${p.optString("user_pack")}")}};packSpinner=spinner((if(labels.isEmpty())listOf("Không có bàn Pack khả dụng")else labels).toTypedArray());resourceBox.addView(labelled("Bàn Pack + User Pack",packSpinner!!))}
            else->Unit}}
        choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};shift.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(12))
        val enter=primary("VÀO CA",teal){}
        enter.setOnClickListener{val work=choice.selectedItem.toString();val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shift.selectedItem.toString()).put("work_choice",work);if(work=="PICK"){val serial=resolvePda(pdas,pdaField?.text?.toString().orEmpty());if(serial==null){showError("Nhập đúng 5 số cuối seri PDA và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};payload.put("pda_serial",serial);val pick=pickValues.getOrNull(pickSpinner?.selectedItemPosition?:0).orEmpty();if(pick.isNotBlank())payload.put("user_pick",pick)};if(work=="PACK"){if(packValues.isEmpty()){showError("Không còn bàn Pack khả dụng.");return@setOnClickListener};payload.put("pack_table",packValues[packSpinner?.selectedItemPosition?:0])};enter.isEnabled=false;enter.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enter.isEnabled=true;enter.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else loadEmployee(mnv)}}}
        body.addView(enter,matchWrap())
    }

    private fun refreshStatus(){syncApi.call("sync_status"){r->runOnUiThread{if(r.code==401){sessionExpired();return@runOnUiThread};val j=r.json;if(r.ok&&j!=null){syncText?.text="✓ Online • R${j.optLong("server_seq",0)}";syncText?.setTextColor(Color.WHITE)}else{syncText?.text="! Offline";syncText?.setTextColor(Color.WHITE)}}}}

    private fun employeeCard(e: JSONObject)=column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,9);addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}",15.5f,navy,true));addView(gap(3));addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}",10.5f,ink,false));addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}",10f,muted,false))}
    private fun details(items:List<Pair<String,String>>)=column(surface).apply{setPadding(dp(13),dp(9),dp(13),dp(9));background=outlineBg(surface,9);items.forEach{(k,v)->addView(row(surface).apply{addView(txt(k,10.5f,muted,false),LinearLayout.LayoutParams(0,-2,.45f));addView(txt(if(v.isBlank())"—" else v,10.7f,ink,true).apply{gravity=Gravity.END},LinearLayout.LayoutParams(0,-2,.55f));setPadding(0,dp(4),0,dp(4))})}}

    private fun appBar(title:String,back:Boolean)=row(navy).apply{
        gravity=Gravity.CENTER_VERTICAL;setPadding(dp(8),dp(6),dp(8),dp(6))
        addView(txt(if(back)"‹" else "",if(back)30f else 20f,Color.WHITE,false).apply{gravity=Gravity.CENTER;if(back)setOnClickListener{navigateBack()}},size(dp(40),dp(44)))
        addView(txt(title,16.5f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f))
        syncText=txt("↻ Đang nối",8.8f,Color.WHITE,true).apply{gravity=Gravity.CENTER;maxLines=2;setPadding(dp(4),dp(4),dp(4),dp(4))}
        addView(syncText,size(dp(102),dp(40)))
    }
    private fun menuRow(icon:String,title:String,sub:String,click:()->Unit)=row(surface).apply{
        gravity=Gravity.CENTER_VERTICAL;setPadding(dp(11),dp(9),dp(9),dp(9));background=outlineBg(surface,10)
        addView(txt(icon,22f,teal,true).apply{gravity=Gravity.CENTER},size(dp(45),dp(50)))
        addView(column(surface).apply{addView(txt(title,12.8f,ink,true));addView(txt(sub,9.7f,muted,false))},LinearLayout.LayoutParams(0,-2,1f))
        addView(txt("›",22f,teal,false).apply{gravity=Gravity.CENTER},size(dp(26),dp(48)))
        setOnClickListener{click()};layoutParams=LinearLayout.LayoutParams(-1,-2).apply{bottomMargin=dp(7)}
    }

    private fun fullCard(symbol:String,title:String,color:Int,height:Int,click:()->Unit)=row(color).apply{gravity=Gravity.CENTER_VERTICAL;background=round(color,12);setPadding(dp(12),0,dp(12),0);addView(txt(symbol,25f,Color.WHITE,true).apply{gravity=Gravity.CENTER},size(dp(48),-1));addView(txt(title,14f,Color.WHITE,true).apply{gravity=Gravity.CENTER_VERTICAL},LinearLayout.LayoutParams(0,-2,1f));addView(txt("›",24f,Color.WHITE,false).apply{gravity=Gravity.CENTER},size(dp(30),-1));setOnClickListener{click()};layoutParams=LinearLayout.LayoutParams(-1,height)}
    private fun tile(symbol:String,title:String,color:Int,click:()->Unit)=column(surface).apply{gravity=Gravity.CENTER;background=outlineBg(surface,12);addView(txt(symbol,23f,color,true).center());addView(gap(3));addView(txt(title,11.5f,ink,true).center());setOnClickListener{click()}}
    private fun cardRow(a:View,b:View)=row(bg).apply{addView(a,LinearLayout.LayoutParams(0,dp(86),1f).apply{marginEnd=dp(4);topMargin=dp(4);bottomMargin=dp(4)});addView(b,LinearLayout.LayoutParams(0,dp(86),1f).apply{marginStart=dp(4);topMargin=dp(4);bottomMargin=dp(4)})}
    private fun status(value:String,fg:Int,color:Int)=txt(value,11.5f,fg,true).apply{gravity=Gravity.CENTER;setPadding(dp(10),dp(10),dp(10),dp(10));background=round(color,9)}
    private fun info(value:String)=txt(value,10.5f,muted,false).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(Color.rgb(244,247,251),9)}
    private fun section(title:String)=txt(title,10.5f,navy,true).apply{setPadding(0,dp(5),0,dp(6))}
    private fun mnvInput(hintValue:String)=input(hintValue,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}
    private fun bindScannerEnter(v:EditText, submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}
    private fun pdaInput(pdas:JSONArray,currentSerial:String=""):AutoCompleteTextView {
        val labels=mutableListOf<String>();var currentLast5=""
        for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(serial.isBlank()||last5.isBlank())continue;labels.add("$last5 • $serial");if(serial==currentSerial)currentLast5=last5}
        return AutoCompleteTextView(this).apply{hint="Nhập 5 số cuối seri PDA";threshold=1;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");setPadding(dp(12),dp(9),dp(12),dp(9));minHeight=dp(46);background=outline();setAdapter(ArrayAdapter(this@FullBetaActivity,android.R.layout.simple_dropdown_item_1line,labels));setOnItemClickListener{parent,_,pos,_->setText(parent.getItemAtPosition(pos).toString().substringBefore(" • "),false)};if(currentLast5.isNotBlank())setText(currentLast5,false)}
    }
    private fun resolvePda(pdas:JSONArray,rawValue:String):String?{val raw=rawValue.trim().substringBefore(" • ");if(raw.length!=5||!raw.all{it.isDigit()})return null;val hits=mutableListOf<String>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(last5==raw&&serial.isNotBlank())hits.add(serial)};return hits.singleOrNull()}
    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{hint=hintValue;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(12),dp(9),dp(12),dp(9));minHeight=dp(46);background=outline()}
    private fun labelled(label:String,view:View)=column(bg).apply{addView(txt(label,10.5f,ink,true));addView(gap(4));addView(view,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@FullBetaActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(7),dp(3),dp(7),dp(3));minimumHeight=dp(46);background=outline()}
    private fun primary(title:String,color:Int,click:()->Unit)=Button(this).apply{text=title;textSize=12.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(48);background=round(color,7);setOnClickListener{click()}}

    private fun setScreen(content:View){setContentView(host(content))}
    private fun navigateBack(){when(currentScreen){"EMPLOYEE"->employeeScan();"SCAN"->dashboard();"DASHBOARD"->finish();else->dashboard()}}
    private fun refreshMasterCache(){cacheApi.call("master_snapshot"){r->if(r.ok&&r.json!=null)MasterDataCache.save(applicationContext,r.json)}}
    private fun host(content:View):View{
        val root=EdgeSwipeBackLayout(this){if(currentScreen!="LOGIN"&&currentScreen!="DASHBOARD")navigateBack()}.apply{setBackgroundColor(bg)}
        val navHeight=if(currentScreen=="LOGIN")0 else dp(62)
        root.addView(content,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(22)+navHeight})
        if(currentScreen!="LOGIN")root.addView(bottomNav("BUSINESS"),FrameLayout.LayoutParams(-1,navHeight,Gravity.BOTTOM).apply{bottomMargin=dp(20)})
        root.addView(txt(FOOTER,8f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(20),Gravity.BOTTOM))
        root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION")val tt=i.systemWindowInsetTop;@Suppress("DEPRECATION")val bb=i.systemWindowInsetBottom;top=tt;bottom=bb};v.setPadding(0,top+dp(5),0,bottom+dp(2));i};root.requestApplyInsets();return root
    }
    private fun bottomNav(active:String): LinearLayout = row(surface).apply {
        gravity = Gravity.CENTER
        setPadding(dp(3),dp(3),dp(3),dp(3))
        background = GradientDrawable().apply { setColor(surface); setStroke(dp(1),line) }
        val items = listOf(
            Triple("▦","Nghiệp vụ","BUSINESS"),
            Triple("◉","Nhân sự","STAFF"),
            Triple("◷","Lịch sử","HISTORY"),
            Triple("↻","Đồng bộ","SYNC"),
            Triple("⚙","Cài đặt","SETTINGS")
        )
        items.forEach { item ->
            val cell = column(surface).apply {
                gravity = Gravity.CENTER
                addView(txt(item.first,17f,if(item.third==active)teal else muted,true).apply { gravity=Gravity.CENTER })
                addView(txt(item.second,8.4f,if(item.third==active)teal else muted,item.third==active).apply { gravity=Gravity.CENTER; maxLines=1 })
                setOnClickListener { _ ->
                    if(item.third=="BUSINESS") dashboard() else openModule(item.third)
                }
            }
            addView(cell,LinearLayout.LayoutParams(0,-1,1f))
        }
    }

    private fun sessionExpired(){api.clearSession();AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã được thay thế").setMessage("Tài khoản này đã đăng nhập ở thiết bị khác hoặc quyền tài khoản đã thay đổi. Đăng nhập lại để tiếp tục.").setCancelable(false).setPositiveButton("ĐĂNG NHẬP"){_,_->login()}.show()}
    private fun showError(raw:String){val msg=when{raw.contains("INVALID_CREDENTIALS")->"Sai tài khoản hoặc mật khẩu.";raw.contains("LOGIN_TEMP_LOCKED")->"Tài khoản tạm khóa 15 phút do đăng nhập sai nhiều lần.";raw.contains("EMPLOYEE_NOT_FOUND")->"Không tìm thấy MNV.";raw.contains("PP_RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Kiểm tra lại.";raw.contains("PP_USER_PICK_USED_TODAY")->"User Pick đã được dùng trong ngày.";raw.contains("PP_USER_PACK_USED_TODAY")->"User Pack đã được dùng trong ngày.";raw.contains("UNAUTHORIZED")->"Phiên đăng nhập đã hết hạn.";else->raw};TopNotice.show(this,msg,TopNotice.Kind.ERROR)}
    private fun roleText(r:String)=when(r){"SUPERADMIN"->"Superadmin";"ADMIN"->"Admin";"USER"->"Điều phối";else->BuildConfig.CHANNEL}
    private fun formatIso(v:String):String{if(v.isBlank()||v=="null")return "—";return try{Instant.parse(v).atZone(ZoneId.of("Asia/Bangkok")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}catch(_:Throwable){v}}
    private fun dash(v:String)=v.takeIf{it.isNotBlank()&&it!="null"}?:"—"
    private fun txt(v:String,s:Float,c:Int,b:Boolean)=TextView(this).apply{text=v;textSize=s;setTextColor(c);typeface=if(b)Typeface.DEFAULT_BOLD else Typeface.DEFAULT}
    private fun TextView.center()=apply{gravity=Gravity.CENTER}
    private fun column(c:Int)=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setBackgroundColor(c)}
    private fun row(c:Int)=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL;setBackgroundColor(c)}
    private fun gap(h:Int)=Space(this).apply{layoutParams=size(1,dp(h))}
    private fun round(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat()}
    private fun outline()=GradientDrawable().apply{setColor(surface);cornerRadius=dp(7).toFloat();setStroke(dp(1),line)}
    private fun outlineBg(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat();setStroke(dp(1),line)}
    private fun dp(v:Int)=(v*resources.displayMetrics.density).toInt()
    private fun size(w:Int,h:Int)=ViewGroup.LayoutParams(w,h)
    private fun matchWrap()=LinearLayout.LayoutParams(-1,-2)
    private fun toast(s:String)=TopNotice.show(this,s,TopNotice.Kind.SUCCESS)
    companion object{private const val FOOTER="Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY"}
}

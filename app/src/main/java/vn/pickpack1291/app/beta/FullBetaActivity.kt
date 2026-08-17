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
    private val navy = Color.rgb(7, 38, 92)
    private val blue = Color.rgb(13, 78, 170)
    private val red = Color.rgb(218, 45, 53)
    private val green = Color.rgb(36, 153, 85)
    private val orange = Color.rgb(241, 143, 24)
    private val teal = Color.rgb(35, 151, 166)
    private val bg = Color.rgb(248, 250, 253)
    private val surface = Color.WHITE
    private val ink = Color.rgb(22, 33, 49)
    private val muted = Color.rgb(96, 108, 124)
    private val line = Color.rgb(218, 225, 234)

    private val api = BetaApiClient()
    private var accountLogin = ""
    private var accountName = ""
    private var accountRole = ""
    private var syncText: TextView? = null

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = Color.WHITE
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        LocalLogManager.installCrashHandler(this)
        LocalLogManager.createDailyIfNeeded(this)
        login()
    }

    override fun onStart() {
        super.onStart()
        UpdateManager.check(this)
    }

    private fun login() {
        api.clearToken()
        accountLogin = ""; accountName = ""; accountRole = ""
        val body = column(bg).apply { gravity = Gravity.CENTER_HORIZONTAL; setPadding(dp(22), dp(24), dp(22), dp(58)) }
        body.addView(gap(6))
        body.addView(ImageView(this).apply { setImageResource(R.drawable.app_icon); scaleType = ImageView.ScaleType.CENTER_CROP }, size(dp(88), dp(88)))
        body.addView(gap(7))
        body.addView(txt("PICK PACK 1291", 21f, navy, true).center())
        body.addView(txt("SUPRA DC HƯNG YÊN", 10.5f, navy, true).center())
        body.addView(gap(16))
        val user = input("Nhập tài khoản", false)
        val saved = getPreferences(MODE_PRIVATE).getString("last_login", "").orEmpty()
        if (saved.isNotBlank()) user.setText(saved)
        val pass = input("Nhập mật khẩu", true).apply { imeOptions = EditorInfo.IME_ACTION_DONE }
        body.addView(labelled("Tài khoản", user)); body.addView(gap(10)); body.addView(labelled("Mật khẩu", pass)); body.addView(gap(15))
        val button = primary("ĐĂNG NHẬP", navy) {}
        fun submit() {
            val login = user.text.toString().trim(); val password = pass.text.toString()
            if (login.isBlank() || password.isBlank()) { toast("Nhập tài khoản và mật khẩu."); return }
            button.isEnabled = false; button.text = "ĐANG ĐĂNG NHẬP..."
            api.login(login, password) { result -> runOnUiThread {
                button.isEnabled = true; button.text = "ĐĂNG NHẬP"
                if (!result.ok) { showError(result.error ?: "Đăng nhập thất bại"); return@runOnUiThread }
                val a = result.json?.optJSONObject("account") ?: JSONObject()
                accountLogin = a.optString("login_id", login)
                accountName = a.optString("display_name", accountLogin)
                accountRole = a.optString("role", "USER")
                getPreferences(MODE_PRIVATE).edit().putString("last_login", accountLogin).apply()
                pass.setText("")
                dashboard()
            } }
        }
        button.setOnClickListener { submit() }
        pass.setOnEditorActionListener { _, actionId, _ -> if (actionId == EditorInfo.IME_ACTION_DONE) { submit(); true } else false }
        body.addView(button, matchWrap()); body.addView(gap(10))
        body.addView(txt("${BuildConfig.CHANNEL} • FULL FUNCTION TEST • ${BuildConfig.VERSION_NAME}", 10f, blue, true).center())
        body.addView(txt("App tự kiểm tra phiên bản mới khi mở/foreground.", 9.5f, muted, false).center())
        setScreen(ScrollView(this).apply { isFillViewport = true; addView(body) })
    }

    private fun dashboard() {
        val root = column(bg)
        root.addView(appBar("Trang chủ", false))
        val body = column(bg).apply { setPadding(dp(14), dp(15), dp(14), dp(54)) }
        body.addView(fullCard("▣", "QUÉT QR NHÂN SỰ", blue, dp(88)) { employeeScan() })
        body.addView(gap(7))
        body.addView(cardRow(
            tile("◉", "CÔNG NHẬT", green) { openModule("LABOR") },
            tile("⌘", "TÀI NGUYÊN", orange) { openModule("RESOURCES") }
        ))
        body.addView(cardRow(
            tile("☷", "DANH SÁCH", Color.rgb(58, 91, 183)) { openModule("LISTS") },
            tile("▥", "BÁO CÁO", teal) { openModule("REPORT") }
        ))
        body.addView(gap(2))
        body.addView(fullCard("⚙", "CÀI ĐẶT", navy, dp(64)) { openModule("SETTINGS") })
        body.addView(gap(14))
        syncText = txt("●  Đang kiểm tra kết nối...", 10.5f, muted, false).apply { setPadding(dp(10), dp(9), dp(10), dp(9)); background = outlineBg(surface, 9) }
        body.addView(syncText, matchWrap())
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
        refreshStatus()
    }

    private fun openModule(module: String, mnv: String = "") {
        startActivity(Intent(this, OperationsActivity::class.java).apply {
            putExtra("module", module); putExtra("login", accountLogin); putExtra("name", accountName); putExtra("role", accountRole); putExtra("mnv", mnv)
        })
    }

    private fun employeeScan() {
        val root = column(bg); root.addView(appBar("QUÉT QR NHÂN SỰ", true))
        val body = column(bg).apply { setPadding(dp(16), dp(16), dp(16), dp(58)) }
        val mnv = input("Quét QR hoặc nhập MNV", false).apply { setSingleLine(true); imeOptions = EditorInfo.IME_ACTION_DONE }
        body.addView(labelled("Mã nhân viên", mnv)); body.addView(gap(10))
        val check = primary("KIỂM TRA", navy) {}
        fun submit() { val v=mnv.text.toString().trim(); if(v.isBlank()){toast("Quét QR hoặc nhập MNV.");return}; check.isEnabled=false;check.text="ĐANG KIỂM TRA..."; loadEmployee(v, check) }
        check.setOnClickListener { submit() }; mnv.setOnEditorActionListener { _, id, _ -> if(id==EditorInfo.IME_ACTION_DONE){submit();true}else false }
        body.addView(check, matchWrap()); body.addView(gap(12)); body.addView(info("Server tự xác định CHƯA VÀO / ĐANG TRONG PHIÊN / ĐÃ HẾT PHIÊN. Không còn nút VÀO/RA tách rời."))
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1,0,1f)); setScreen(root); mnv.requestFocus()
    }

    private fun loadEmployee(mnv: String, button: Button? = null) {
        api.call("employee_context", JSONObject().put("mnv", mnv)) { result -> runOnUiThread {
            button?.isEnabled=true; button?.text="KIỂM TRA"
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){showError(result.error ?: "Không kiểm tra được MNV");return@runOnUiThread}
            val ctx=result.json ?: JSONObject()
            if(ctx.optString("state")=="NOT_ENTERED") api.call("master_options", JSONObject().put("mnv", mnv)) { masters -> runOnUiThread {
                if(masters.code==401){sessionExpired();return@runOnUiThread}; renderEmployee(ctx, masters.json ?: JSONObject())
            } } else renderEmployee(ctx, null)
        } }
    }

    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val state=ctx.optString("state"); val mnv=e.optString("mnv")
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
            exit.isEnabled=false;exit.text="ĐANG RA CA...";api.call("exit",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv)){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else{toast("RA CA thành công");loadEmployee(mnv)}}}
        }.show() }
        body.addView(exit, matchWrap())
    }

    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val s=ctx.optJSONObject("session") ?: JSONObject();body.addView(status("ĐÃ HẾT PHIÊN VÀO / RA HÔM NAY", red, Color.rgb(255,238,239)));body.addView(gap(8));body.addView(details(listOf("Ca" to s.optString("shift"),"Vị trí trong ca" to s.optString("work_choice"),"Vào lúc" to formatIso(s.optString("enter_at")),"Ra lúc" to formatIso(s.optString("exit_at")))));body.addView(gap(10));body.addView(info("Phiên hợp lệ đã kết thúc. Không cho VÀO lại cùng ngày bằng luồng thường."))
    }

    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val e=ctx.optJSONObject("employee") ?: JSONObject(); val mnv=e.optString("mnv")
        body.addView(status("CHƯA VÀO CA", blue, Color.rgb(237,244,255)));body.addView(gap(10))
        val shift=spinner(arrayOf("Ca 1","Ca 2","HC"));val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));when{e.optString("main_position").contains("Pick",true)->choice.setSelection(1);e.optString("main_position").contains("Pack",true)->choice.setSelection(2)}
        body.addView(labelled("Ca làm việc",shift));body.addView(gap(9));body.addView(labelled("Vị trí trong ca",choice));body.addView(gap(9))
        val resourceBox=column(bg);body.addView(resourceBox,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray()
        val pdaValues=mutableListOf<String>();val pickValues=mutableListOf<String?>();val packValues=mutableListOf<String>();var pdaSpinner:Spinner?=null;var pickSpinner:Spinner?=null;var packSpinner:Spinner?=null
        fun rebuild(){resourceBox.removeAllViews();pdaValues.clear();pickValues.clear();packValues.clear();when(choice.selectedItem.toString()){
            "PICK"->{val labels=mutableListOf<String>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial");if(serial.isNotBlank()){pdaValues.add(serial);labels.add("${p.optString("last5")} • $serial")}};pdaSpinner=spinner((if(labels.isEmpty())listOf("Không có PDA khả dụng")else labels).toTypedArray());resourceBox.addView(labelled("PDA (bắt buộc)",pdaSpinner!!));resourceBox.addView(gap(8));val pl=mutableListOf("Không dùng User Pick");pickValues.add(null);for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){pl.add(v);pickValues.add(v)}};pickSpinner=spinner(pl.toTypedArray());resourceBox.addView(labelled("User Pick (tùy chọn)",pickSpinner!!))}
            "PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;val table=p.optString("table");if(table.isNotBlank()){packValues.add(table);labels.add("$table • ${p.optString("user_pack")}")}};packSpinner=spinner((if(labels.isEmpty())listOf("Không có bàn Pack khả dụng")else labels).toTypedArray());resourceBox.addView(labelled("Bàn Pack + User Pack",packSpinner!!))}
            else->resourceBox.addView(info("Không cấp tài nguyên cho lựa chọn KHÔNG."))}}
        choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(14))
        val enter=primary("VÀO CA",blue){}
        enter.setOnClickListener{val work=choice.selectedItem.toString();val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shift.selectedItem.toString()).put("work_choice",work);if(work=="PICK"){if(pdaValues.isEmpty()){showError("Không còn PDA khả dụng.");return@setOnClickListener};payload.put("pda_serial",pdaValues[pdaSpinner?.selectedItemPosition?:0]);pickValues.getOrNull(pickSpinner?.selectedItemPosition?:0)?.let{payload.put("user_pick",it)}};if(work=="PACK"){if(packValues.isEmpty()){showError("Không còn bàn Pack khả dụng.");return@setOnClickListener};payload.put("pack_table",packValues[packSpinner?.selectedItemPosition?:0])};enter.isEnabled=false;enter.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enter.isEnabled=true;enter.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else{toast("VÀO CA thành công");loadEmployee(mnv)}}}}
        body.addView(enter,matchWrap())
    }

    private fun refreshStatus() { api.call("sync_status") { r -> runOnUiThread { if(r.code==401){sessionExpired();return@runOnUiThread}; val j=r.json; if(r.ok&&j!=null){val p=j.optInt("projection_pending",0);syncText?.text="●  FULL BETA • Seq ${j.optLong("server_seq",0)} • chờ Sheet ACK: $p";syncText?.setTextColor(if(p==0)green else orange)}else{syncText?.text="●  Mất kết nối";syncText?.setTextColor(red)} } } }

    private fun employeeCard(e: JSONObject)=column(surface).apply{setPadding(dp(14),dp(12),dp(14),dp(12));background=outlineBg(surface,9);addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}",15.5f,navy,true));addView(gap(3));addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}",10.5f,ink,false));addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}",10f,muted,false))}
    private fun details(items:List<Pair<String,String>>)=column(surface).apply{setPadding(dp(13),dp(9),dp(13),dp(9));background=outlineBg(surface,9);items.forEach{(k,v)->addView(row(surface).apply{addView(txt(k,10.5f,muted,false),LinearLayout.LayoutParams(0,-2,.45f));addView(txt(if(v.isBlank())"—" else v,10.7f,ink,true).apply{gravity=Gravity.END},LinearLayout.LayoutParams(0,-2,.55f));setPadding(0,dp(4),0,dp(4))})}}

    private fun appBar(title:String,back:Boolean)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(9),dp(7),dp(10),dp(7));addView(txt(if(back)"‹" else "☰",if(back)31f else 22f,Color.WHITE,false).apply{gravity=Gravity.CENTER;if(back)setOnClickListener{dashboard()}},size(dp(42),dp(45)));addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));addView(column(navy).apply{gravity=Gravity.END;addView(txt(if(accountLogin.isBlank())BuildConfig.CHANNEL else accountLogin,10.5f,Color.WHITE,true).apply{gravity=Gravity.END});addView(txt(roleText(accountRole),8.5f,Color.rgb(218,229,248),false).apply{gravity=Gravity.END})})}
    private fun fullCard(symbol:String,title:String,color:Int,height:Int,click:()->Unit)=row(color).apply{gravity=Gravity.CENTER;background=round(color,7);addView(txt(symbol,25f,Color.WHITE,true).apply{gravity=Gravity.CENTER},size(dp(47),-1));addView(txt(title,14f,Color.WHITE,true).apply{gravity=Gravity.CENTER_VERTICAL});setOnClickListener{click()};layoutParams=LinearLayout.LayoutParams(-1,height)}
    private fun tile(symbol:String,title:String,color:Int,click:()->Unit)=column(color).apply{gravity=Gravity.CENTER;background=round(color,7);addView(txt(symbol,24f,Color.WHITE,true).center());addView(gap(3));addView(txt(title,11.5f,Color.WHITE,true).center());setOnClickListener{click()}}
    private fun cardRow(a:View,b:View)=row(bg).apply{addView(a,LinearLayout.LayoutParams(0,dp(92),1f).apply{marginEnd=dp(5);topMargin=dp(5);bottomMargin=dp(5)});addView(b,LinearLayout.LayoutParams(0,dp(92),1f).apply{marginStart=dp(5);topMargin=dp(5);bottomMargin=dp(5)})}
    private fun status(value:String,fg:Int,color:Int)=txt(value,11.5f,fg,true).apply{gravity=Gravity.CENTER;setPadding(dp(10),dp(10),dp(10),dp(10));background=round(color,9)}
    private fun info(value:String)=txt(value,10.5f,muted,false).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(Color.rgb(244,247,251),9)}
    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{hint=hintValue;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(12),dp(9),dp(12),dp(9));minHeight=dp(46);background=outline()}
    private fun labelled(label:String,view:View)=column(bg).apply{addView(txt(label,10.5f,ink,true));addView(gap(4));addView(view,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@FullBetaActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(7),dp(3),dp(7),dp(3));minimumHeight=dp(46);background=outline()}
    private fun primary(title:String,color:Int,click:()->Unit)=Button(this).apply{text=title;textSize=12.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(48);background=round(color,7);setOnClickListener{click()}}

    private fun setScreen(content:View){setContentView(host(content))}
    private fun host(content:View):View{val root=FrameLayout(this).apply{setBackgroundColor(bg)};root.addView(content,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(27)});root.addView(txt(FOOTER,8f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(23),Gravity.BOTTOM));root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION") val t=i.systemWindowInsetTop;@Suppress("DEPRECATION") val b=i.systemWindowInsetBottom;top=t;bottom=b};v.setPadding(0,top+dp(7),0,bottom+dp(3));i};root.requestApplyInsets();return root}
    private fun sessionExpired(){AlertDialog.Builder(this).setTitle("Phiên đã hết hạn").setMessage("Đăng nhập lại để tiếp tục.").setCancelable(false).setPositiveButton("ĐĂNG NHẬP"){_,_->login()}.show()}
    private fun showError(raw:String){val msg=when{raw.contains("INVALID_CREDENTIALS")->"Sai tài khoản hoặc mật khẩu.";raw.contains("LOGIN_TEMP_LOCKED")->"Tài khoản tạm khóa 15 phút do đăng nhập sai nhiều lần.";raw.contains("EMPLOYEE_NOT_FOUND")->"Không tìm thấy MNV.";raw.contains("PP_RESOURCE_CONFLICT")->"Tài nguyên vừa được người khác nhận. Kiểm tra lại.";raw.contains("PP_USER_PICK_USED_TODAY")->"User Pick đã được dùng trong ngày.";raw.contains("PP_USER_PACK_USED_TODAY")->"User Pack đã được dùng trong ngày.";raw.contains("UNAUTHORIZED")->"Phiên đăng nhập đã hết hạn.";else->raw};AlertDialog.Builder(this).setTitle("Không thực hiện được").setMessage(msg).setPositiveButton("OK",null).show()}
    private fun roleText(r:String)=when(r){"SUPERADMIN"->"Superadmin";"ADMIN"->"Admin";"USER"->"Điều phối";else->BuildConfig.CHANNEL}
    private fun formatIso(v:String):String{if(v.isBlank()||v=="null")return"—";return try{Instant.parse(v).atZone(ZoneId.of("Asia/Bangkok")).format(DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss"))}catch(_:Throwable){v}}
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
    private fun toast(s:String)=Toast.makeText(this,s,Toast.LENGTH_SHORT).show()
    companion object{private const val FOOTER="Copyright 2026 - tamnv2 - Chuyên viên Pick Pack 1291 - Supra DCHY"}
}

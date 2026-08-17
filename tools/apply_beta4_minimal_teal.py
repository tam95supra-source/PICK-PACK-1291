from pathlib import Path
import re

ROOT = Path('.')


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    (ROOT / path).write_text(text, encoding='utf-8')


def sub1(text, pattern, repl, label, flags=re.S):
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 replacement, got {n}')
    return out


def replace1(text, old, new, label):
    if old not in text:
        raise SystemExit(f'{label}: old text not found')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Android: API client - reset password + reset credential login + tighter I/O.
# ---------------------------------------------------------------------------
p = 'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
s = read(p)

old = '''                val proof = proofForPassword(
                    password = password,
                    saltB64 = j.getString("salt"),
                    iterations = j.getInt("iterations"),
                    challenge = j.getString("challenge")
                )
                val result = post(JSONObject().apply {
                    put("action", "login")
                    put("login_id", login)
                    put("challenge_id", j.getString("challenge_id"))
                    put("proof", proof)
                }, authenticated = false)'''
new = '''                val algorithm = j.optString("algorithm", "pbkdf2_sha256")
                val proof = proofForPassword(
                    password = password,
                    saltB64 = j.getString("salt"),
                    iterations = j.optInt("iterations", 120_000),
                    challenge = j.getString("challenge"),
                    algorithm = algorithm
                )
                val request = JSONObject().apply {
                    put("action", "login")
                    put("login_id", login)
                    put("challenge_id", j.getString("challenge_id"))
                    put("proof", proof)
                    if (algorithm == "reset_sha256") put("upgrade_verifier", makeVerifier(password))
                }
                val result = post(request, authenticated = false)'''
s = replace1(s, old, new, 'client login algorithm')

anchor = '''    fun health(callback: (Result) -> Unit) {
        executor.execute {
            try { callback(post(JSONObject().put("action", "health"), authenticated = false)) }
            catch (t: Throwable) { callback(failure(t)) }
        }
    }
'''
insert = anchor + '''
    fun forgotPassword(loginId: String, callback: (Result) -> Unit) {
        executor.execute {
            try {
                callback(post(JSONObject().apply {
                    put("action", "forgot_password")
                    put("login_id", loginId.trim())
                }, authenticated = false))
            } catch (t: Throwable) { callback(failure(t)) }
        }
    }
'''
s = replace1(s, anchor, insert, 'client forgot password')

old = '''    private fun proofForPassword(password: String, saltB64: String, iterations: Int, challenge: String): String {
        val key = derive(password, b64uDecode(saltB64), iterations)
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return b64u(mac.doFinal(challenge.toByteArray(Charsets.UTF_8)))
    }
'''
new = '''    private fun proofForPassword(password: String, saltB64: String, iterations: Int, challenge: String, algorithm: String = "pbkdf2_sha256"): String {
        val key = if (algorithm == "reset_sha256") {
            MessageDigest.getInstance("SHA-256").digest("PP_RESET_V1|$saltB64|$password".toByteArray(Charsets.UTF_8))
        } else {
            derive(password, b64uDecode(saltB64), iterations)
        }
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return b64u(mac.doFinal(challenge.toByteArray(Charsets.UTF_8)))
    }
'''
s = replace1(s, old, new, 'client proof algorithm')
s = s.replace('connectTimeout = 12_000\n                readTimeout = 25_000', 'connectTimeout = 8_000\n                readTimeout = 18_000')
write(p, s)


# ---------------------------------------------------------------------------
# Android: master cache - fast local resource options for QR flow.
# ---------------------------------------------------------------------------
p = 'app/src/main/java/vn/pickpack1291/app/beta/MasterDataCache.kt'
s = read(p)
anchor = '''    fun allStaff(context: Context, limit: Int = 200): JSONArray {
'''
helper = '''    fun resourceOptions(context: Context): JSONObject {
        val s = snapshot(context) ?: return JSONObject()
        return JSONObject().apply {
            put("pdas", JSONArray((s.optJSONArray("pdas") ?: JSONArray()).toString()))
            put("user_picks", JSONArray((s.optJSONArray("user_picks") ?: JSONArray()).toString()))
            put("pack_tables", JSONArray((s.optJSONArray("pack_bundles") ?: JSONArray()).toString()))
            put("master_revision", s.optLong("master_revision", 0L))
        }
    }

'''
if helper.strip() not in s:
    s = replace1(s, anchor, helper + anchor, 'master resource options')
write(p, s)


# ---------------------------------------------------------------------------
# Android: main production activity - Minimal Teal, centered login, fast QR,
# PDA last-5 autocomplete, optional User Pick, quiet routine notifications.
# ---------------------------------------------------------------------------
p = 'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt'
s = read(p)
s = s.replace('private val navy = Color.rgb(7, 38, 92)', 'private val navy = Color.rgb(15, 78, 74)')
s = s.replace('private val blue = Color.rgb(13, 78, 170)', 'private val blue = Color.rgb(13, 148, 136)')
s = s.replace('private val orange = Color.rgb(241, 143, 24)', 'private val orange = Color.rgb(217, 119, 6)')
s = s.replace('private val teal = Color.rgb(35, 151, 166)', 'private val teal = Color.rgb(15, 118, 110)')
s = s.replace('private val bg = Color.rgb(248, 250, 253)', 'private val bg = Color.rgb(247, 250, 249)')
s = s.replace('private val ink = Color.rgb(22, 33, 49)', 'private val ink = Color.rgb(24, 44, 42)')
s = s.replace('private val muted = Color.rgb(96, 108, 124)', 'private val muted = Color.rgb(100, 116, 139)')
s = s.replace('private val line = Color.rgb(218, 225, 234)', 'private val line = Color.rgb(214, 229, 226)')

login_fn = r'''    private fun login\(\) \{.*?\n    \}\n\n    private fun dashboard\(\) \{'''
login_repl = '''    private fun login() {
        foregroundSync.stop()
        liveEmployeeMnv = ""
        currentScreen = "LOGIN"
        accountLogin = ""; accountName = ""; accountRole = ""; accountPosition = ""

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
                    AlertDialog.Builder(this@FullBetaActivity)
                        .setTitle("Đã tiếp nhận")
                        .setMessage("Nếu tài khoản hợp lệ, mật khẩu mới đã được gửi tới quản trị viên. Liên hệ quản trị viên để nhận mật khẩu mới.")
                        .setPositiveButton("OK", null).show()
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

    private fun dashboard() {'''
s = sub1(s, login_fn, login_repl, 'full login')

dash_fn = r'''    private fun dashboard\(\) \{.*?\n    \}\n\n    private fun openModule'''
dash_repl = '''    private fun dashboard() {
        currentScreen = "DASHBOARD"
        liveEmployeeMnv = ""
        val root = column(bg)
        root.addView(appBar("Trang chủ", false))
        val body = column(bg).apply { setPadding(dp(12), dp(12), dp(12), dp(46)) }
        body.addView(txt("Xin chào, ${accountName.ifBlank { accountLogin }}", 16f, ink, true))
        body.addView(txt(roleText(accountRole), 10.5f, muted, false))
        body.addView(gap(10))
        body.addView(fullCard("▣", "QUÉT QR NHÂN SỰ", teal, dp(88)) { employeeScan() })
        body.addView(gap(8))
        body.addView(section("CHỨC NĂNG"))
        body.addView(fullCard("⌕", "DANH SÁCH NHÂN SỰ", Color.rgb(20, 128, 120), dp(64)) { openModule("STAFF") })
        if (accountRole == "ADMIN" || accountRole == "SUPERADMIN") {
            body.addView(cardRow(
                tile("◉", "CÔNG NHẬT", green) { openModule("LABOR") },
                tile("☷", "THEO DÕI CA", Color.rgb(67, 122, 115)) { openModule("LISTS") }
            ))
        } else {
            body.addView(fullCard("☷", "THEO DÕI CA", Color.rgb(67, 122, 115), dp(64)) { openModule("LISTS") })
        }
        body.addView(cardRow(
            tile("▥", "BÁO CÁO", teal) { openModule("REPORT") },
            tile("⚙", "CÀI ĐẶT", navy) { openModule("SETTINGS") }
        ))
        root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setScreen(root)
        refreshStatus()
    }

    private fun openModule'''
s = sub1(s, dash_fn, dash_repl, 'full dashboard')

load_fn = r'''    private fun loadEmployee\(mnv: String, button: Button\? = null\) \{.*?\n    \}\n\n    private fun renderCachedEmployee'''
load_repl = '''    private fun loadEmployee(mnv: String, button: Button? = null) {
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

    private fun renderCachedEmployee'''
s = sub1(s, load_fn, load_repl, 'fast employee context')

enter_fn = r'''    private fun renderEnter\(body: LinearLayout, ctx: JSONObject, masters: JSONObject\) \{.*?\n    \}\n\n    private fun refreshStatus'''
enter_repl = '''    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
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

    private fun refreshStatus'''
s = sub1(s, enter_fn, enter_repl, 'full render enter')

# Quiet routine success messages.
s = s.replace('else{toast("RA CA thành công");loadEmployee(mnv)}', 'else loadEmployee(mnv)')

# Minimal teal tiles: white surface cards, teal/semantic icon and dark text.
old = '''    private fun fullCard(symbol:String,title:String,color:Int,height:Int,click:()->Unit)=row(color).apply{gravity=Gravity.CENTER;background=round(color,7);addView(txt(symbol,25f,Color.WHITE,true).apply{gravity=Gravity.CENTER},size(dp(47),-1));addView(txt(title,14f,Color.WHITE,true).apply{gravity=Gravity.CENTER_VERTICAL});setOnClickListener{click()};layoutParams=LinearLayout.LayoutParams(-1,height)}
    private fun tile(symbol:String,title:String,color:Int,click:()->Unit)=column(color).apply{gravity=Gravity.CENTER;background=round(color,7);addView(txt(symbol,24f,Color.WHITE,true).center());addView(gap(3));addView(txt(title,11.5f,Color.WHITE,true).center());setOnClickListener{click()}}
    private fun cardRow(a:View,b:View)=row(bg).apply{addView(a,LinearLayout.LayoutParams(0,dp(92),1f).apply{marginEnd=dp(5);topMargin=dp(5);bottomMargin=dp(5)});addView(b,LinearLayout.LayoutParams(0,dp(92),1f).apply{marginStart=dp(5);topMargin=dp(5);bottomMargin=dp(5)})}
'''
new = '''    private fun fullCard(symbol:String,title:String,color:Int,height:Int,click:()->Unit)=row(color).apply{gravity=Gravity.CENTER_VERTICAL;background=round(color,12);setPadding(dp(12),0,dp(12),0);addView(txt(symbol,25f,Color.WHITE,true).apply{gravity=Gravity.CENTER},size(dp(48),-1));addView(txt(title,14f,Color.WHITE,true).apply{gravity=Gravity.CENTER_VERTICAL},LinearLayout.LayoutParams(0,-2,1f));addView(txt("›",24f,Color.WHITE,false).apply{gravity=Gravity.CENTER},size(dp(30),-1));setOnClickListener{click()};layoutParams=LinearLayout.LayoutParams(-1,height)}
    private fun tile(symbol:String,title:String,color:Int,click:()->Unit)=column(surface).apply{gravity=Gravity.CENTER;background=outlineBg(surface,12);addView(txt(symbol,23f,color,true).center());addView(gap(3));addView(txt(title,11.5f,ink,true).center());setOnClickListener{click()}}
    private fun cardRow(a:View,b:View)=row(bg).apply{addView(a,LinearLayout.LayoutParams(0,dp(86),1f).apply{marginEnd=dp(4);topMargin=dp(4);bottomMargin=dp(4)});addView(b,LinearLayout.LayoutParams(0,dp(86),1f).apply{marginStart=dp(4);topMargin=dp(4);bottomMargin=dp(4)})}
'''
s = replace1(s, old, new, 'minimal teal cards')

# Add PDA helpers before input helper.
anchor = '    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{'
helpers = '''    private fun pdaInput(pdas:JSONArray,currentSerial:String=""):AutoCompleteTextView {
        val labels=mutableListOf<String>();var currentLast5=""
        for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(serial.isBlank()||last5.isBlank())continue;labels.add("$last5 • $serial");if(serial==currentSerial)currentLast5=last5}
        return AutoCompleteTextView(this).apply{hint="Nhập 5 số cuối seri PDA";threshold=1;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");setPadding(dp(12),dp(9),dp(12),dp(9));minHeight=dp(46);background=outline();setAdapter(ArrayAdapter(this@FullBetaActivity,android.R.layout.simple_dropdown_item_1line,labels));setOnItemClickListener{parent,_,pos,_->setText(parent.getItemAtPosition(pos).toString().substringBefore(" • "),false)};if(currentLast5.isNotBlank())setText(currentLast5,false)}
    }
    private fun resolvePda(pdas:JSONArray,rawValue:String):String?{val raw=rawValue.trim().substringBefore(" • ");if(raw.length!=5||!raw.all{it.isDigit()})return null;val hits=mutableListOf<String>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(last5==raw&&serial.isNotBlank())hits.add(serial)};return hits.singleOrNull()}
'''
if helpers.strip() not in s:
    s = replace1(s, anchor, helpers + anchor, 'full pda helpers')
write(p, s)


# ---------------------------------------------------------------------------
# Android: operations screens - Minimal Teal, optional User Pick, PDA last-5,
# compact report layout and quiet routine success.
# ---------------------------------------------------------------------------
p = 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s = read(p)
s = s.replace('private val navy = Color.rgb(7,38,92)', 'private val navy = Color.rgb(15,78,74)')
s = s.replace('private val blue = Color.rgb(13,78,170)', 'private val blue = Color.rgb(13,148,136)')
s = s.replace('private val orange = Color.rgb(241,143,24)', 'private val orange = Color.rgb(217,119,6)')
s = s.replace('private val teal = Color.rgb(35,151,166)', 'private val teal = Color.rgb(15,118,110)')
s = s.replace('private val bg = Color.rgb(248,250,253)', 'private val bg = Color.rgb(247,250,249)')
s = s.replace('private val ink = Color.rgb(22,33,49)', 'private val ink = Color.rgb(24,44,42)')
s = s.replace('private val muted = Color.rgb(96,108,124)', 'private val muted = Color.rgb(100,116,139)')
s = s.replace('private val line = Color.rgb(218,225,234)', 'private val line = Color.rgb(214,229,226)')

# Labor employee context does need active labor; other QR/resource reads do not.
s = s.replace('api.call("employee_context",JSONObject().put("mnv",v)){r->', 'api.call("employee_context",JSONObject().put("mnv",v).put("include_labor",true).put("include_options",false)){r->', 1)

# Replace resource editor with PDA autocomplete + optional pick.
resource_fn = r'''    private fun showResourceEditor\(ctx:JSONObject,masters:JSONObject\)\{.*?\n    \}\n\n    private fun staffScreen'''
resource_repl = '''    private fun showResourceEditor(ctx:JSONObject,masters:JSONObject){
        screenState = "RESOURCE_EDITOR"
        val e=ctx.optJSONObject("employee")?:JSONObject();val s=ctx.optJSONObject("session")?:JSONObject();val root=baseRoot("TÀI NGUYÊN");val body=body();body.addView(employeeCard(e));body.addView(gap(8));body.addView(details(listOf("Hiện tại" to workText(s.optString("work_choice")),"PDA" to dash(s.optString("pda_serial")),"User Pick" to dash(s.optString("user_pick")),"Bàn Pack" to dash(s.optString("pack_table")),"User Pack" to dash(s.optString("user_pack")))));body.addView(gap(10))
        val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));choice.setSelection(when(s.optString("work_choice")){"PICK"->1;"PACK"->2;else->0});body.addView(labelled("Vị trí trong ca mới",choice));body.addView(gap(8));val box=column(bg);body.addView(box,matchWrap())
        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val pickVals=mutableListOf<String>();val packVals=mutableListOf<String>();var pdaField:AutoCompleteTextView?=null;var pickSp:Spinner?=null;var packSp:Spinner?=null
        fun rebuild(){box.removeAllViews();pickVals.clear();packVals.clear();pdaField=null;pickSp=null;packSp=null;when(choice.selectedItem.toString()){
            "PICK"->{pdaField=pdaInput(pdas,s.optString("pda_serial"));box.addView(labelled("PDA (nhập 5 số cuối seri)",pdaField!!));box.addView(gap(8));val labels=mutableListOf("Không dùng User Pick");pickVals.add("");for(i in 0 until picks.length()){val v=picks.optString(i);if(v.isNotBlank()){labels.add(v);pickVals.add(v)}};pickSp=spinner(labels.toTypedArray());box.addView(labelled("User Pick (tùy chọn)",pickSp!!));val current=s.optString("user_pick");if(current.isNotBlank()){val ix=pickVals.indexOf(current);if(ix>=0)pickSp!!.setSelection(ix)}}
            "PACK"->{val labels=mutableListOf<String>();for(i in 0 until packs.length()){val p=packs.optJSONObject(i)?:continue;if(p.optString("shift")!=s.optString("shift"))continue;val t=p.optString("table");if(t.isNotBlank()){packVals.add(t);labels.add("$t • ${p.optString("user_pack")}")}};packSp=spinner(labels.toTypedArray());box.addView(labelled("Bàn Pack + User Pack",packSp!!));selectByValue(packSp!!,packVals,s.optString("pack_table"))}
            else->Unit}}
        choice.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};rebuild();body.addView(gap(12));val save=primary("CẬP NHẬT TÀI NGUYÊN",orange){};save.setOnClickListener{val work=choice.selectedItem.toString();val p=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",e.optString("mnv")).put("work_choice",work);if(work=="PICK"){val serial=resolvePda(pdas,pdaField?.text?.toString().orEmpty());if(serial==null){showError("Nhập đúng 5 số cuối seri PDA và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};p.put("pda_serial",serial);val pick=pickVals.getOrNull(pickSp?.selectedItemPosition?:0).orEmpty();if(pick.isNotBlank())p.put("user_pick",pick)};if(work=="PACK"){if(packVals.isEmpty()){showError("Không có bàn Pack khả dụng.");return@setOnClickListener};p.put("pack_table",packVals[packSp?.selectedItemPosition?:0])};save.isEnabled=false;save.text="ĐANG CẬP NHẬT...";api.call("resource_change",p){r->runOnUiThread{save.isEnabled=true;save.text="CẬP NHẬT TÀI NGUYÊN";if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không đổi được tài nguyên")else{initialMnv=e.optString("mnv");resourceHome()}}}};body.addView(save,matchWrap());body.addView(gap(8));body.addView(primary("MNV KHÁC",navy){initialMnv="";resourceHome()},matchWrap());attach(root,body)
    }

    private fun staffScreen'''
s = sub1(s, resource_fn, resource_repl, 'operations resource editor')

# Compact report while preserving manpower + tenure data, but remove noisy headings.
report_fn = r'''    private fun reportScreen\(\)\{.*?\n    \}\n\n    private fun reportGrid'''
report_repl = '''    private fun reportScreen(){
        screenState = "REPORT"
        val root=baseRoot("BÁO CÁO");val body=column(bg).apply{setPadding(dp(3),dp(6),dp(3),dp(42))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày"));body.addView(labelled("Phạm vi báo cáo",period));body.addView(gap(5))
        val box=column(bg);body.addView(box,matchWrap());box.addView(txt("Đang tải...",10.5f,muted,false))
        api.call("report_daily"){r->runOnUiThread{
            box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được báo cáo"));return@runOnUiThread}
            val rootJson=r.json?:JSONObject()
            fun render(){
                box.removeAllViews();val key=when(period.selectedItemPosition){0->"ca1_hc";1->"ca2";else->"all"};val p=rootJson.optJSONObject("reports")?.optJSONObject(key)?:JSONObject()
                box.addView(reportGrid("",p.optJSONObject("manpower"),"Vị trí","position"));box.addView(gap(4));box.addView(reportGrid("",p.optJSONObject("tenure"),"Thâm niên","label"))
                val support=p.optJSONObject("support");if(isAdmin() && (support?.optInt("total")?:0)>0){box.addView(gap(4));box.addView(supportGrid(support))}
            }
            period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};render()
        }}
        attach(root,body)
    }

    private fun reportGrid'''
s = sub1(s, report_fn, report_repl, 'compact report screen')

# Report grids: no title row when blank; tighter padding.
s = s.replace('val wrap=column(surface).apply{setPadding(dp(5),dp(7),dp(5),dp(7));background=outlineBg(surface,8)};wrap.addView(txt(title,12f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(6))})', 'val wrap=column(surface).apply{setPadding(dp(1),dp(2),dp(1),dp(2));background=outlineBg(surface,6)};if(title.isNotBlank())wrap.addView(txt(title,11f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(3))})')
s = s.replace('setPadding(dp(2),dp(5),dp(2),dp(5))', 'setPadding(dp(1),dp(3),dp(1),dp(3))')
s = s.replace('val wrap=column(surface).apply{setPadding(dp(5),dp(7),dp(5),dp(7));background=outlineBg(surface,8)};wrap.addView(txt("NHÂN SỰ ĐI HỖ TRỢ",12f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(6))})', 'val wrap=column(surface).apply{setPadding(dp(1),dp(2),dp(1),dp(2));background=outlineBg(surface,6)};wrap.addView(txt("NHÂN SỰ ĐI HỖ TRỢ",11f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(3))})')
s = s.replace('setPadding(dp(3),dp(5),dp(3),dp(5))', 'setPadding(dp(1),dp(3),dp(1),dp(3))')

# Quiet routine success feedback; important/error dialogs remain.
s = s.replace('else{toast("Đã hoàn thành công nhật");initialMnv=e.optString("mnv");laborHome()}', 'else{initialMnv=e.optString("mnv");laborHome()}')
s = s.replace('else{toast("Đã bắt đầu công nhật");initialMnv=e.optString("mnv");laborHome()}', 'else{initialMnv=e.optString("mnv");laborHome()}')

# Add PDA helpers before input helper.
anchor = '    private fun input(hintValue:String,password:Boolean)=EditText(this).apply{'
helpers = '''    private fun pdaInput(pdas:JSONArray,currentSerial:String=""):AutoCompleteTextView{val labels=mutableListOf<String>();var currentLast5="";for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(serial.isBlank()||last5.isBlank())continue;labels.add("$last5 • $serial");if(serial==currentSerial)currentLast5=last5};return AutoCompleteTextView(this).apply{hint="Nhập 5 số cuối seri PDA";threshold=1;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");setPadding(dp(12),dp(9),dp(12),dp(9));minHeight=dp(46);background=outline();setAdapter(ArrayAdapter(this@OperationsActivity,android.R.layout.simple_dropdown_item_1line,labels));setOnItemClickListener{parent,_,pos,_->setText(parent.getItemAtPosition(pos).toString().substringBefore(" • "),false)};if(currentLast5.isNotBlank())setText(currentLast5,false)}}
    private fun resolvePda(pdas:JSONArray,rawValue:String):String?{val raw=rawValue.trim().substringBefore(" • ");if(raw.length!=5||!raw.all{it.isDigit()})return null;val hits=mutableListOf<String>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(last5==raw&&serial.isNotBlank())hits.add(serial)};return hits.singleOrNull()}
'''
if helpers.strip() not in s:
    s = replace1(s, anchor, helpers + anchor, 'operations pda helpers')
write(p, s)


# ---------------------------------------------------------------------------
# GAS backend - faster reads, password reset email, optional User Pick,
# fast employee context, report ordering.
# ---------------------------------------------------------------------------
p = 'google-apps-script/PICK_PACK_API.gs'
s = read(p)
s = replace1(s, "  ADMIN: 'Danh sách Admin',", "  ADMIN: 'Danh sách Admin',\n  RESET_ADMIN_EMAIL: 'tam95.supra@gmail.com',", 'gas reset email config')
s = replace1(s, "    if (action === 'login_challenge') return ppJson_(ppLoginChallenge_(body));", "    if (action === 'forgot_password') return ppJson_(ppForgotPassword_(body));\n    if (action === 'login_challenge') return ppJson_(ppLoginChallenge_(body));", 'gas forgot route')

# Faster employee context: don't fetch options/labor unless explicitly requested.
old = '''  const options=state==='NOT_ENTERED'?ppMasterOptions_({mnv:mnv}):null;
  return {ok:true,business_date:ppBusinessIso_(),employee:staff,state:state,session:session,active_labor:ppActiveLabor_(mnv),options:options};'''
new = '''  const options=state==='NOT_ENTERED' && body.include_options===true ? ppMasterOptions_({mnv:mnv}) : null;
  const activeLabor=body.include_labor===true ? ppActiveLabor_(mnv) : null;
  return {ok:true,business_date:ppBusinessIso_(),employee:staff,state:state,session:session,active_labor:activeLabor,options:options};'''
s = replace1(s, old, new, 'gas fast employee context')

# User Pick becomes optional; if present it is still fully validated.
s = s.replace("    if(!userPick) throw new Error('USER_PICK_REQUIRED');\n", "")
s = s.replace("    if(masters.userPicks.indexOf(userPick)<0) throw new Error('USER_PICK_INVALID');\n    if(busy.has('USER_PICK|'+userPick) || used.picks.has(userPick)) throw new Error('PP_USER_PICK_USED_TODAY');", "    if(userPick && masters.userPicks.indexOf(userPick)<0) throw new Error('USER_PICK_INVALID');\n    if(userPick && (busy.has('USER_PICK|'+userPick) || used.picks.has(userPick))) throw new Error('PP_USER_PICK_USED_TODAY');")

# Cache account rows by master revision: removes repeated Sheet reads across login challenge/login.
admin_fn = r'''function ppAdminRows_\(\) \{.*?\n\}\nfunction ppAccount_'''
admin_repl = '''function ppAdminRows_() {
  const rev=ppMasterRevision_(),cache=CacheService.getScriptCache(),key='PP_ADMIN_V3_'+rev,cached=cache.get(key);
  if(cached){try{return JSON.parse(cached);}catch(_){} }
  const sh=ppSheet_(PP.ADMIN), vals=sh.getDataRange().getDisplayValues(), out=[];
  for(let i=1;i<vals.length;i++){
    if(!String(vals[i][0]||'').trim())continue;
    out.push({row:i+1,login_id:String(vals[i][0]||'').trim(),verifier:String(vals[i][1]||'').trim(),role:String(vals[i][2]||'USER').trim().toUpperCase(),display_name:String(vals[i][3]||vals[i][0]||'').trim(),position:String(vals[i][4]||'').trim(),status:String(vals[i][8]||'ACTIVE').trim().toUpperCase()||'ACTIVE'});
  }
  const raw=JSON.stringify(out);if(raw.length<90000)cache.put(key,raw,300);return out;
}
function ppAccount_'''
s = sub1(s, admin_fn, admin_repl, 'gas admin cache')

# Credential helpers + forgot password flow.
anchor = "function ppVerifierParts_(v){const p=String(v||'').split('$'); if(p.length!==4||p[0]!=='pbkdf2_sha256')return null; const n=Number(p[1]); if(!n||n<100000||n>1000000)return null; return {iterations:n,salt:p[2],key:p[3]};}\n"
reset_helpers = anchor + '''function ppResetParts_(v){const p=String(v||'').split('$');if(p.length!==4||p[0]!=='reset_sha256')return null;const exp=Number(p[1]);if(!exp)return null;return {algorithm:'reset_sha256',expires_at:exp,iterations:1,salt:p[2],key:p[3]};}
function ppCredentialParts_(v){const p=ppVerifierParts_(v);if(p)return {algorithm:'pbkdf2_sha256',iterations:p.iterations,salt:p.salt,key:p.key};return ppResetParts_(v);}
function ppResetPasswordValue_(){const chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';let out='PP-';const bytes=ppRandom_(12);for(let i=0;i<10;i++){const n=(bytes[i]+256)%256;out+=chars.charAt(n%chars.length);}return out;}
function ppResetKey_(password,salt){return ppB64u_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,Utilities.newBlob('PP_RESET_V1|'+salt+'|'+password).getBytes()));}
function ppForgotPassword_(body){
  const login=String(body.login_id||'').trim(),generic={ok:true,delivery:'ADMIN_EMAIL',message:'RESET_REQUEST_ACCEPTED'};
  if(!login)return generic;
  const rateKey='PP_RESET_RATE_'+ppSha256Hex_(login+'|'+ppDeviceId_(body)).slice(0,48),cache=CacheService.getScriptCache();if(cache.get(rateKey))return generic;
  const a=ppAccount_(login);cache.put(rateKey,'1',300);if(!a||a.status!=='ACTIVE')return generic;
  const password=ppResetPasswordValue_(),salt=ppB64u_(ppRandom_(16)),expires=Date.now()+2*60*60*1000,key=ppResetKey_(password,salt),resetVerifier='reset_sha256$'+expires+'$'+salt+'$'+key,sh=ppSheet_(PP.ADMIN),old=a.verifier;
  try{
    sh.getRange(a.row,2).setValue(resetVerifier);ppEnsureAdminHeaders_();sh.getRange(a.row,10).setValue('FORGOT_PASSWORD');sh.getRange(a.row,11).setValue(ppNowVisible_());ppClearActiveSessionForLogin_(a.login_id);ppBumpRevision_();ppBumpMasterRevision_();
    MailApp.sendEmail({to:PP.RESET_ADMIN_EMAIL,subject:'[PICK PACK 1291] Mật khẩu mới - '+a.login_id,body:'Tài khoản: '+a.login_id+'\\nTên: '+a.display_name+'\\nQuyền: '+a.role+'\\nMật khẩu mới: '+password+'\\nHết hạn kích hoạt: 2 giờ.\\n\\nMật khẩu sẽ được nâng cấp sang PBKDF2 ngay lần đăng nhập đầu tiên.',htmlBody:'<b>PICK PACK 1291 - Đặt lại mật khẩu</b><br><br>Tài khoản: <b>'+a.login_id+'</b><br>Tên: '+a.display_name+'<br>Quyền: '+a.role+'<br>Mật khẩu mới: <b style="font-size:18px">'+password+'</b><br>Hết hạn kích hoạt: 2 giờ.<br><br>Mật khẩu sẽ được nâng cấp sang PBKDF2 ngay lần đăng nhập đầu tiên.'});
  }catch(err){try{sh.getRange(a.row,2).setValue(old);ppBumpRevision_();ppBumpMasterRevision_();}catch(_){}throw err;}
  return generic;
}
'''
s = replace1(s, anchor, reset_helpers, 'gas reset helpers')

# Login challenge/login support PBKDF2 and reset_sha256.
login_chal = r'''function ppLoginChallenge_\(body\) \{.*?\n\}\nfunction ppLogin_\(body\) \{.*?\n\}'''
login_new = '''function ppLoginChallenge_(body) {
  const login=String(body.login_id||'').trim(), account=ppAccount_(login), cred=account?ppCredentialParts_(account.verifier):null, usable=cred && (cred.algorithm!=='reset_sha256'||cred.expires_at>Date.now()), fakeSalt=ppB64u_(ppRandom_(16));
  const id=Utilities.getUuid(), challenge=ppB64u_(ppRandom_(32)); CacheService.getScriptCache().put('PP_CHAL_'+id,JSON.stringify({login_id:login,purpose:'LOGIN',challenge:challenge}),120);
  return {ok:true,challenge_id:id,challenge:challenge,algorithm:usable?cred.algorithm:'pbkdf2_sha256',iterations:usable?cred.iterations:120000,salt:usable?cred.salt:fakeSalt};
}
function ppLogin_(body) {
  const login=String(body.login_id||'').trim(), id=String(body.challenge_id||''), proof=String(body.proof||''), c=ppTakeChallenge_(id,'LOGIN',login);let a=ppAccount_(login),cred=a?ppCredentialParts_(a.verifier):null;
  if(!c||!a||a.status!=='ACTIVE'||!cred||(cred.algorithm==='reset_sha256'&&cred.expires_at<=Date.now())||!ppVerifyProof_(cred.key,c.challenge,proof))return {ok:false,error:'INVALID_CREDENTIALS'};
  if(cred.algorithm==='reset_sha256'){
    const upgrade=String(body.upgrade_verifier||'');if(!ppVerifierParts_(upgrade))return {ok:false,error:'RESET_UPGRADE_REQUIRED'};
    ppSheet_(PP.ADMIN).getRange(a.row,2).setValue(upgrade);ppEnsureAdminHeaders_();ppSheet_(PP.ADMIN).getRange(a.row,10).setValue(a.login_id);ppSheet_(PP.ADMIN).getRange(a.row,11).setValue(ppNowVisible_());ppBumpRevision_();ppBumpMasterRevision_();a=ppAccount_(login);
  }
  const session=ppBindSession_(a.login_id,ppDeviceId_(body)), token=ppMakeToken_(a,session);
  return {ok:true,token:token,account:{login_id:a.login_id,role:a.role,display_name:a.display_name,position:a.position||''},session:{issued_at:session.issued_at,device_label:String(body._device_label||'').slice(0,120)}};
}'''
s = sub1(s, login_chal, login_new, 'gas reset-aware login')

# Report row order: Phúc Long above Kéo hàng.
s = s.replace("'Điều phối','Kéo hàng','5S','Picker','Packer','Phúc Long'", "'Điều phối','Phúc Long','Kéo hàng','5S','Picker','Packer'")
s = s.replace("return ['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Kéo hàng','5S','Picker','Packer','Phúc Long'];", "return ['Trưởng nhóm','Chuyên viên','Tổ trưởng','Điều phối khu pack','Điều phối khu chờ xuất','Phúc Long','Kéo hàng','5S','Picker','Packer'];")
write(p, s)


# Apps Script manifest: email-only scope for reset notifications.
p = 'google-apps-script/appsscript.json'
s = read(p)
if 'https://www.googleapis.com/auth/script.send_mail' not in s:
    s = s.replace('"https://www.googleapis.com/auth/drive"', '"https://www.googleapis.com/auth/drive",\n    "https://www.googleapis.com/auth/script.send_mail"')
write(p, s)


# Version bump for OTA beta.
p = 'app/build.gradle.kts'
s = read(p)
s = replace1(s, 'versionCode = 9\n            versionName = "0.4.2-beta.3"', 'versionCode = 10\n            versionName = "0.4.2-beta.4"', 'beta4 version')
write(p, s)


# Project guardrail: lock selected visual language + behavior.
p = 'AGENTS.md'
s = read(p)
rule = '''\n## UI / UX lock — Beta 0.4.2-beta.4+\n- Official visual system: **Minimal Teal Corporate (Mẫu 2)** — white/light surface, teal primary, restrained enterprise styling, compact PDA-friendly spacing.\n- Login card stays visually centered; do not show beta/version marketing text on the login screen.\n- Routine success toasts/notifications should be minimized; reserve intrusive notifications for errors, session replacement, security events, or OTA updates.\n- PICK requires PDA; User Pick is optional. PDA selection uses the last 5 serial digits with validated suggestions.\n- Reports keep operational matrices but suppress the redundant section-title rows; support table is hidden when deducted support count is zero; Phúc Long precedes Kéo hàng.\n'''
if 'UI / UX lock — Beta 0.4.2-beta.4+' not in s:
    s += rule
write(p, s)

print('beta4 patch applied')

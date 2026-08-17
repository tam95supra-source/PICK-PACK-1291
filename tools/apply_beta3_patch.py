from pathlib import Path
import re

# Android API client: persistent private session + pseudonymous physical-device fingerprint.
p=Path('app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'); s=p.read_text()
s=s.replace('import android.os.Build\n','import android.content.Context\nimport android.os.Build\nimport android.provider.Settings\n',1)
s=s.replace('import java.util.concurrent.Executors\n','import java.util.concurrent.Executors\nimport java.util.UUID\n',1)
s=s.replace('class BetaApiClient {','class BetaApiClient(context: Context) {',1)
pat=r'''    private val executor = Executors\.newSingleThreadExecutor\(\)\n\n    val token: String\?\n        get\(\) = sharedToken\n\n    fun clearToken\(\) \{ sharedToken = null \}\n'''
repl='''    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val executor = Executors.newSingleThreadExecutor()
    private val deviceId: String by lazy {
        val androidId = Settings.Secure.getString(appContext.contentResolver, Settings.Secure.ANDROID_ID).orEmpty()
        if (androidId.isNotBlank() && androidId != "9774d56d682e549c") {
            "android-" + sha256Text("PickPack1291|$androidId")
        } else {
            val saved = prefs.getString(KEY_DEVICE_ID, null)
            val id = saved ?: UUID.randomUUID().toString().also { prefs.edit().putString(KEY_DEVICE_ID, it).apply() }
            "install-$id"
        }
    }

    init {
        synchronized(sessionLock) {
            if (sharedToken == null) sharedToken = prefs.getString(KEY_TOKEN, null)
        }
    }

    val token: String?
        get() = sharedToken

    fun clearToken() = clearSession()

    fun clearSession() {
        synchronized(sessionLock) { sharedToken = null }
        prefs.edit().remove(KEY_TOKEN).remove(KEY_LOGIN).remove(KEY_NAME).remove(KEY_ROLE).remove(KEY_POSITION).apply()
    }

    fun restoredAccount(): JSONObject? {
        if (token.isNullOrBlank()) return null
        val login = prefs.getString(KEY_LOGIN, "").orEmpty()
        if (login.isBlank()) return null
        return JSONObject().apply {
            put("login_id", login)
            put("display_name", prefs.getString(KEY_NAME, login).orEmpty().ifBlank { login })
            put("role", prefs.getString(KEY_ROLE, "USER").orEmpty().ifBlank { "USER" })
            put("position", prefs.getString(KEY_POSITION, "").orEmpty())
        }
    }

    private fun persistSession(newToken: String, account: JSONObject?) {
        synchronized(sessionLock) { sharedToken = newToken }
        val e = prefs.edit().putString(KEY_TOKEN, newToken)
        if (account != null) {
            val login = account.optString("login_id")
            if (login.isNotBlank()) e.putString(KEY_LOGIN, login)
            e.putString(KEY_NAME, account.optString("display_name", login))
            e.putString(KEY_ROLE, account.optString("role", "USER"))
            e.putString(KEY_POSITION, account.optString("position", ""))
        }
        e.apply()
    }

    private fun sha256Text(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
'''
s,n=re.subn(pat,repl,s,count=1); assert n==1, 'client session block'
old='if (result.ok) sharedToken = result.json?.optString("token")?.takeIf { it.isNotBlank() }'
new='''if (result.ok) {
                    val newToken = result.json?.optString("token")?.takeIf { it.isNotBlank() }
                    if (newToken != null) persistSession(newToken, result.json.optJSONObject("account"))
                }'''
assert old in s; s=s.replace(old,new,1)
old='''                if (result.code == 401) sharedToken = null
                callback(result)'''
new='''                if (result.ok) {
                    val refreshed = result.json?.optString("token")?.takeIf { it.isNotBlank() }
                    if (refreshed != null) persistSession(refreshed, result.json.optJSONObject("account") ?: restoredAccount())
                }
                if (result.code == 401) clearSession()
                callback(result)'''
assert old in s; s=s.replace(old,new,1)
old='''            put("_app_channel", BuildConfig.CHANNEL)
            put("_device_label", "${Build.MANUFACTURER} ${Build.MODEL}")'''
new='''            put("_app_channel", BuildConfig.CHANNEL)
            put("_device_id", deviceId)
            put("_device_label", "${Build.MANUFACTURER} ${Build.MODEL}")'''
assert old in s; s=s.replace(old,new,1)
old='''    companion object {
        @Volatile private var sharedToken: String? = null
        private const val RELEASES_URL = "https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30"
    }'''
new='''    companion object {
        @Volatile private var sharedToken: String? = null
        private val sessionLock = Any()
        private const val PREFS_NAME = "pick_pack_auth_session_v2"
        private const val KEY_TOKEN = "token"
        private const val KEY_LOGIN = "login_id"
        private const val KEY_NAME = "display_name"
        private const val KEY_ROLE = "role"
        private const val KEY_POSITION = "position"
        private const val KEY_DEVICE_ID = "device_id"
        private const val RELEASES_URL = "https://api.github.com/repos/tam95supra-source/pick-pack-1291/releases?per_page=30"
    }'''
assert old in s; s=s.replace(old,new,1); p.write_text(s)

# Context-aware clients across Activities and exact owner artwork reference.
for q in Path('app/src/main/java/vn/pickpack1291/app/beta').glob('*.kt'):
    if q.name=='BetaApiClient.kt': continue
    t=q.read_text()
    t=re.sub(r'private val (\w+) = BetaApiClient\(\)',r'private val \1 by lazy { BetaApiClient(applicationContext) }',t)
    t=t.replace('R.drawable.app_icon','R.drawable.owner_launcher')
    q.write_text(t)

# Launcher activity restores local private session instead of clearing it on cold start.
p=Path('app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt'); s=p.read_text()
assert 'MasterDataCache.hydrate(this)\n        login()' in s
s=s.replace('MasterDataCache.hydrate(this)\n        login()','MasterDataCache.hydrate(this)\n        restoreOrLogin()',1)
s=s.replace('        api.clearToken()\n','',1)
needle='    private fun login() {'
restore='''    private fun restoreOrLogin() {
        val saved = api.restoredAccount()
        if (api.token.isNullOrBlank() || saved == null) { login(); return }
        accountLogin = saved.optString("login_id")
        accountName = saved.optString("display_name", accountLogin)
        accountRole = saved.optString("role", "USER")
        accountPosition = saved.optString("position", "")
        dashboard()
        foregroundSync.start()
    }

'''
assert needle in s; s=s.replace(needle,restore+needle,1)
pat=r'    private fun sessionExpired\(\)\{.*?\n    private fun showError'
repl='''    private fun sessionExpired(){api.clearSession();AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã được thay thế").setMessage("Tài khoản này đã đăng nhập ở thiết bị khác hoặc quyền tài khoản đã thay đổi. Đăng nhập lại để tiếp tục.").setCancelable(false).setPositiveButton("ĐĂNG NHẬP"){_,_->login()}.show()}
    private fun showError'''
s,n=re.subn(pat,repl,s,count=1,flags=re.S); assert n==1, 'sessionExpired'; p.write_text(s)

# Operations screen clears local session only on explicit logout or server rejection.
p=Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'); s=p.read_text()
s=s.replace('override fun onAuthExpired() { finish() }','override fun onAuthExpired() { api.clearSession(); finishAffinity() }',1)
s=s.replace('api.call("logout"){runOnUiThread{finishAffinity()}}','api.call("logout"){runOnUiThread{api.clearSession();finishAffinity()}}',1)
old='''private fun handleAuth(r:BetaApiClient.Result):Boolean{if(r.code==401){AlertDialog.Builder(this).setTitle("Phiên đã hết hạn").setMessage("Quay lại màn hình đăng nhập.").setCancelable(false).setPositiveButton("OK"){_,_->finishAffinity()}.show();return true};return false}'''
new='''private fun handleAuth(r:BetaApiClient.Result):Boolean{if(r.code==401){api.clearSession();AlertDialog.Builder(this).setTitle("Phiên đăng nhập đã được thay thế").setMessage("Tài khoản đã đăng nhập ở thiết bị khác hoặc quyền tài khoản đã thay đổi.").setCancelable(false).setPositiveButton("OK"){_,_->finishAffinity()}.show();return true};return false}'''
assert old in s; s=s.replace(old,new,1); p.write_text(s)

# Manifest uses brand-new direct bitmap resource, bypassing all legacy adaptive/inset layers.
p=Path('app/src/main/AndroidManifest.xml'); s=p.read_text()
s=s.replace('android:icon="@mipmap/ic_launcher"','android:icon="@drawable/owner_launcher"')
s=s.replace('android:roundIcon="@mipmap/ic_launcher_round"','android:roundIcon="@drawable/owner_launcher"')
p.write_text(s)

# GAS: one active server session per account/device fingerprint, no normal time expiry.
p=Path('google-apps-script/PICK_PACK_API.gs'); s=p.read_text()
s=s.replace("if (action === 'logout') return ppJson_({ok:true});","if (action === 'logout') return ppJson_(ppLogout_(auth));",1)
login='''function ppLogin_(body) {
  const login=String(body.login_id||'').trim(), id=String(body.challenge_id||''), proof=String(body.proof||''), c=ppTakeChallenge_(id,'LOGIN',login), a=ppAccount_(login), p=a?ppVerifierParts_(a.verifier):null;
  if(!c||!a||a.status!=='ACTIVE'||!p||!ppVerifyProof_(p.key,c.challenge,proof))return {ok:false,error:'INVALID_CREDENTIALS'};
  const session=ppBindSession_(a.login_id,ppDeviceId_(body)), token=ppMakeToken_(a,session);
  return {ok:true,token:token,account:{login_id:a.login_id,role:a.role,display_name:a.display_name,position:a.position||''},session:{issued_at:session.issued_at,device_label:String(body._device_label||'').slice(0,120)}};
}
function ppPasswordChallenge_'''
s,n=re.subn(r'function ppLogin_\(body\) \{.*?\n\}\nfunction ppPasswordChallenge_',login,s,count=1,flags=re.S); assert n==1, 'ppLogin'
change='''function ppChangePassword_(auth,body) {
  const id=String(body.challenge_id||''),proof=String(body.proof||''),newVerifier=String(body.new_verifier||''),c=ppTakeChallenge_(id,'PASSWORD',auth.login_id),p=ppVerifierParts_(auth.verifier),np=ppVerifierParts_(newVerifier); if(!c||!p||!ppVerifyProof_(p.key,c.challenge,proof))return {ok:false,error:'CURRENT_PASSWORD_INVALID'}; if(!np)return {ok:false,error:'PASSWORD_POLICY'};
  ppSheet_(PP.ADMIN).getRange(auth.row,2).setValue(newVerifier); ppEnsureAdminHeaders_(); ppSheet_(PP.ADMIN).getRange(auth.row,10).setValue(auth.login_id); ppSheet_(PP.ADMIN).getRange(auth.row,11).setValue(ppNowVisible_()); ppBumpRevision_(); ppBumpMasterRevision_();
  const fresh=ppAccount_(auth.login_id), session=ppActiveSession_(auth.login_id);
  const token=(fresh&&session&&session.session_id===auth._session_id&&session.device_id===auth._device_id)?ppMakeToken_(fresh,session):'';
  return {ok:true,token:token,account:fresh?{login_id:fresh.login_id,role:fresh.role,display_name:fresh.display_name,position:fresh.position||''}:null};
}
function ppAccountList_'''
s,n=re.subn(r'function ppChangePassword_\(auth,body\) \{.*?\n\}\nfunction ppAccountList_',change,s,count=1,flags=re.S); assert n==1, 'ppChangePassword'
auth='''function ppAuthenticate_(body) {
  const token=String(body._token||''), parts=token.split('.'); if(parts.length!==2)return null;
  const secret=ppTokenSecret_(), expected=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(parts[0]).getBytes(),secret)); if(!ppSafeEq_(expected,parts[1]))return null;
  let payload; try{payload=JSON.parse(Utilities.newBlob(ppB64uDecode_(parts[0])).getDataAsString());}catch(_){return null;}
  const a=payload?ppAccount_(String(payload.l||'')):null; if(!a||a.status!=='ACTIVE'||a.role!==payload.r||ppSha256Hex_(a.verifier)!==payload.v)return null;
  if(payload.s){const active=ppActiveSession_(a.login_id);if(!active||active.session_id!==payload.s||active.device_id!==payload.d)return null;}
  else {if(Number(payload.e||0)<Date.now()||ppActiveSession_(a.login_id))return null;}
  return Object.assign({},a,{_session_id:String(payload.s||''),_device_id:String(payload.d||'')});
}
function ppMakeToken_(a,session) {
  const raw={l:a.login_id,r:a.role,v:ppSha256Hex_(a.verifier),s:session.session_id,d:session.device_id};
  const payload=ppB64u_(Utilities.newBlob(JSON.stringify(raw)).getBytes()),sig=ppB64u_(Utilities.computeHmacSha256Signature(Utilities.newBlob(payload).getBytes(),ppTokenSecret_()));return payload+'.'+sig;
}
function ppSessionKey_(login){return 'PP_ACTIVE_SESSION_'+ppSha256Hex_(String(login||'')).slice(0,48);}
function ppActiveSession_(login){const raw=PropertiesService.getScriptProperties().getProperty(ppSessionKey_(login));if(!raw)return null;try{return JSON.parse(raw);}catch(_){return null;}}
function ppDeviceId_(body){const direct=String(body._device_id||'').trim().slice(0,180);if(direct)return direct;return 'legacy-'+ppSha256Hex_(String(body._device_label||'unknown')).slice(0,48);}
function ppBindSession_(login,deviceId){const lock=LockService.getScriptLock();lock.waitLock(10000);try{const cur=ppActiveSession_(login);const session={session_id:(cur&&cur.device_id===deviceId&&cur.session_id)?cur.session_id:Utilities.getUuid(),device_id:deviceId,issued_at:ppNowIso_()};PropertiesService.getScriptProperties().setProperty(ppSessionKey_(login),JSON.stringify(session));return session;}finally{lock.releaseLock();}}
function ppClearActiveSessionForLogin_(login){PropertiesService.getScriptProperties().deleteProperty(ppSessionKey_(login));}
function ppLogout_(auth){const lock=LockService.getScriptLock();lock.waitLock(10000);try{const cur=ppActiveSession_(auth.login_id);if(cur&&cur.session_id===auth._session_id&&cur.device_id===auth._device_id)ppClearActiveSessionForLogin_(auth.login_id);return {ok:true};}finally{lock.releaseLock();}}
function ppTokenSecret_'''
s,n=re.subn(r'function ppAuthenticate_\(body\) \{.*?\n\}\nfunction ppMakeToken_\(a,exp\) \{.*?\n\}\nfunction ppTokenSecret_',auth,s,count=1,flags=re.S); assert n==1, 'ppAuthenticate/token'
st=s.index('function ppAccountStatus_'); en=s.index('\n\nfunction ppAuthenticate_',st); block=s[st:en]
block=block.replace('sh.getRange(t.row,11).setValue(ppNowVisible_());ppBumpRevision_();','sh.getRange(t.row,11).setValue(ppNowVisible_());if(status===\'DISABLED\')ppClearActiveSessionForLogin_(login);ppBumpRevision_();',1)
s=s[:st]+block+s[en:]
s=s.replace("sheet_read:rows.length>1,business_date:","sheet_read:rows.length>1,auth_session_model:'SINGLE_ACTIVE_DEVICE_V1',business_date:",1)
p.write_text(s)

# Beta3 build identity; Stable remains a separate package/channel.
p=Path('app/build.gradle.kts'); s=p.read_text(); s=s.replace('versionCode = 8','versionCode = 9',1).replace('versionName = "0.4.2-beta.2"','versionName = "0.4.2-beta.3"',1); p.write_text(s)

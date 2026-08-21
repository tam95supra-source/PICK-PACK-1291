package vn.pickpack1291.app.beta

import android.app.Application
import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/** Firebase is owner-approved here only for FCM wake/invalidation. */
class M2Application : Application() {
    override fun onCreate() {
        super.onCreate()
        M2Firebase.bootstrap(this)
    }
}

object M2Firebase {
    private const val PREFS = "pp_m2_fcm"
    private const val KEY_PENDING_TOKEN = "pending_token"
    private const val KEY_REGISTERED_TOKEN = "registered_token"

    fun configured(): Boolean = listOf(
        BuildConfig.FIREBASE_PROJECT_ID,
        BuildConfig.FIREBASE_GOOGLE_APP_ID,
        BuildConfig.FIREBASE_API_KEY,
        BuildConfig.FIREBASE_GCM_SENDER_ID,
    ).all { it.isNotBlank() }

    fun bootstrap(context: Context) {
        val app = context.applicationContext
        if (!configured()) return
        runCatching {
            if (FirebaseApp.getApps(app).isEmpty()) {
                val options = FirebaseOptions.Builder()
                    .setProjectId(BuildConfig.FIREBASE_PROJECT_ID)
                    .setApplicationId(BuildConfig.FIREBASE_GOOGLE_APP_ID)
                    .setApiKey(BuildConfig.FIREBASE_API_KEY)
                    .setGcmSenderId(BuildConfig.FIREBASE_GCM_SENDER_ID)
                    .build()
                FirebaseApp.initializeApp(app, options)
            }
            FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                if (token.isNotBlank()) {
                    val prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    if (prefs.getString(KEY_REGISTERED_TOKEN, "") != token) {
                        prefs.edit().putString(KEY_PENDING_TOKEN, token).apply()
                    }
                    M2PushRegistration.flush(app)
                }
            }
        }
    }

    internal fun rememberToken(context: Context, token: String) {
        if (token.isBlank()) return
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_PENDING_TOKEN, token).apply()
    }

    internal fun pendingToken(context: Context): String = context.applicationContext
        .getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_PENDING_TOKEN, "").orEmpty()

    internal fun registeredToken(context: Context): String = context.applicationContext
        .getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_REGISTERED_TOKEN, "").orEmpty()

    internal fun markRegistered(context: Context, token: String) {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val edit = prefs.edit().putString(KEY_REGISTERED_TOKEN, token)
        if (prefs.getString(KEY_PENDING_TOKEN, "") == token) edit.remove(KEY_PENDING_TOKEN)
        edit.apply()
    }

    internal fun markRevoked(context: Context, token: String) {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val edit = prefs.edit()
        if (prefs.getString(KEY_REGISTERED_TOKEN, "") == token) edit.remove(KEY_REGISTERED_TOKEN)
        edit.apply()
    }
}

class M2FirebaseMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        M2Firebase.rememberToken(this, token)
        M2PushRegistration.flush(this)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val type = message.data["type"].orEmpty()
        if (type == "DAY_CHANGED" || type == "MASTER_CHANGED") {
            // Payload is an invalidation only. WorkManager performs the authoritative delta/sync.
            M2WorkScheduler.schedule(applicationContext)
        }
    }

    override fun onDeletedMessages() {
        // A deleted FCM invalidation means the next durable worker must catch up by revision.
        M2WorkScheduler.schedule(applicationContext)
    }
}

object M2PushRegistration {
    private val executor = Executors.newSingleThreadExecutor { r -> Thread(r, "pp-fcm-register").apply { isDaemon = true } }

    fun flush(context: Context) {
        val app = context.applicationContext
        val token = M2Firebase.pendingToken(app)
        if (token.length < 32) return
        val target = serviceTarget(app) ?: return
        executor.execute { register(app, target.first, target.second, token) }
    }

    /** Capture Service session synchronously so logout can clear auth immediately after scheduling revoke. */
    fun revoke(context: Context) {
        val app = context.applicationContext
        val token = M2Firebase.registeredToken(app)
        if (token.length < 32) return
        val target = serviceTarget(app) ?: return
        executor.execute { revokeRegistered(app, target.first, target.second, token) }
    }

    private fun serviceTarget(context: Context): Pair<String, String>? {
        val discovery = M2ServiceTransport(context).discoverySnapshot() ?: return null
        val base = discovery.optString("service_url").trimEnd('/')
        if (!base.startsWith("https://") || (!base.contains(".workers.dev") && !base.contains(".pages.dev"))) return null
        val serviceToken = context.getSharedPreferences("pp_m2_service_transport", Context.MODE_PRIVATE).getString("service_token", null)
        if (serviceToken.isNullOrBlank()) return null
        return base to serviceToken
    }

    private fun register(context: Context, base: String, serviceToken: String, fcmToken: String) {
        val code = post(base, "/v1/push/register", serviceToken, JSONObject()
            .put("fcm_token", fcmToken)
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("channel", BuildConfig.CHANNEL))
        if (code in 200..299) M2Firebase.markRegistered(context, fcmToken)
    }

    private fun revokeRegistered(context: Context, base: String, serviceToken: String, fcmToken: String) {
        val code = post(base, "/v1/push/revoke", serviceToken, JSONObject().put("fcm_token", fcmToken))
        if (code in 200..299) M2Firebase.markRevoked(context, fcmToken)
    }

    private fun post(base: String, path: String, serviceToken: String, body: JSONObject): Int {
        var conn: HttpURLConnection? = null
        return runCatching {
            conn = (URL(base + path).openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 4_000
                readTimeout = 5_000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Authorization", "Bearer $serviceToken")
            }
            conn!!.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            conn!!.responseCode
        }.getOrDefault(-1).also { conn?.disconnect() }
    }
}

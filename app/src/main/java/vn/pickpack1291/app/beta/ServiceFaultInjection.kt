package vn.pickpack1291.app.beta

import android.content.Context

/**
 * Device-local fault injection for SUPERADMIN acceptance testing.
 * It never changes Cloudflare, D1, Google or GAS globally; it only blocks the selected
 * provider network path on this Android installation.
 */
object ServiceFaultInjection {
    enum class Mode(val stored: String, val label: String) {
        NORMAL("NORMAL", "Bình thường"),
        DISABLE_CLOUDFLARE("DISABLE_CLOUDFLARE", "Tắt Cloudflare"),
        DISABLE_GOOGLE("DISABLE_GOOGLE", "Tắt Google Drive"),
        DISABLE_BOTH("DISABLE_BOTH", "Tắt cả hai dịch vụ"),
    }

    private const val PREFS = "pp_service_fault_injection"
    private const val KEY_MODE = "mode"

    fun mode(context: Context): Mode {
        val raw = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_MODE, Mode.NORMAL.stored).orEmpty()
        return Mode.entries.firstOrNull { it.stored == raw } ?: Mode.NORMAL
    }

    fun setMode(context: Context, mode: Mode) {
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_MODE, mode.stored).apply()
    }

    fun cloudflareDisabled(context: Context): Boolean = mode(context) in setOf(Mode.DISABLE_CLOUDFLARE, Mode.DISABLE_BOTH)
    fun googleDisabled(context: Context): Boolean = mode(context) in setOf(Mode.DISABLE_GOOGLE, Mode.DISABLE_BOTH)
    fun label(context: Context): String = mode(context).label
}

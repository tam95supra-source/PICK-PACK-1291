package vn.pickpack1291.app.beta

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build

/**
 * Scoped bridge for Newland Android Broadcast API scanners (including MT90).
 *
 * The bridge is intentionally read-only from a business perspective: a scan only
 * resolves an MNV and lets the existing authoritative screens decide what actions
 * are available. It never performs VÀO/RA or resource mutations by itself.
 */
class NewlandScannerBridge(context: Context) {
    private val appContext = context.applicationContext
    private var started = false
    private var registered = false
    private var handler: ((String) -> Unit)? = null

    val isSupportedDevice: Boolean
        get() {
            val model = Build.MODEL.orEmpty().uppercase()
            val maker = "${Build.MANUFACTURER.orEmpty()} ${Build.BRAND.orEmpty()}".uppercase()
            return model.contains("MT90") || maker.contains("NEWLAND") || maker.contains("NLS")
        }

    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != ACTION_RESULT || handler == null) return
            val state = intent.getStringExtra(EXTRA_STATE).orEmpty()
            if (!state.equals("ok", ignoreCase = true)) return
            val barcode = intent.getStringExtra(EXTRA_BARCODE).orEmpty().trim()
            if (barcode.isNotBlank()) handler?.invoke(barcode)
        }
    }

    fun onStart() {
        started = true
        if (handler != null) enable()
    }

    fun onStop() {
        started = false
        disable()
    }

    fun bind(onBarcode: (String) -> Unit) {
        handler = onBarcode
        if (started) enable()
    }

    fun clear() {
        handler = null
        disable()
    }

    fun trigger(timeoutSeconds: Int = 4): Boolean {
        if (!started || handler == null || !isSupportedDevice) return false
        enable()
        appContext.sendBroadcast(Intent(ACTION_TRIGGER).apply {
            putExtra(EXTRA_TIMEOUT, timeoutSeconds.coerceIn(1, 30))
        })
        return true
    }

    private fun enable() {
        if (!started || handler == null || !isSupportedDevice) return
        if (!registered) {
            val filter = IntentFilter(ACTION_RESULT)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                appContext.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED)
            } else {
                @Suppress("DEPRECATION")
                appContext.registerReceiver(receiver, filter)
            }
            registered = true
        }
        // Mode 3 = barcode output via Android Broadcast API instead of keyboard wedge.
        appContext.sendBroadcast(Intent(ACTION_CONFIG).apply {
            putExtra(EXTRA_SCAN_MODE, 3)
            putExtra(EXTRA_AUTO_ENTER, 0)
            putExtra(EXTRA_ENCODING, 1)
        })
    }

    private fun disable() {
        if (!isSupportedDevice) return
        appContext.sendBroadcast(Intent(ACTION_STOP))
        // Restore the scanner's normal app-facing output mode when Pick Pack no longer
        // owns a scan field, so other apps on the PDA are not left in API-only mode.
        appContext.sendBroadcast(Intent(ACTION_CONFIG).apply {
            putExtra(EXTRA_SCAN_MODE, 1)
            putExtra(EXTRA_AUTO_ENTER, 0)
        })
        if (registered) {
            runCatching { appContext.unregisterReceiver(receiver) }
            registered = false
        }
    }

    companion object {
        private const val ACTION_TRIGGER = "nlscan.action.SCANNER_TRIG"
        private const val ACTION_STOP = "nlscan.action.STOP_SCAN"
        private const val ACTION_RESULT = "nlscan.action.SCANNER_RESULT"
        private const val ACTION_CONFIG = "ACTION_BAR_SCANCFG"
        private const val EXTRA_BARCODE = "SCAN_BARCODE1"
        private const val EXTRA_STATE = "SCAN_STATE"
        private const val EXTRA_TIMEOUT = "SCAN_TIMEOUT"
        private const val EXTRA_SCAN_MODE = "EXTRA_SCAN_MODE"
        private const val EXTRA_AUTO_ENTER = "EXTRA_SCAN_AUTOENT"
        private const val EXTRA_ENCODING = "SCAN_ENCODE"

        private val pureMnv = Regex("^[0-9]{3,12}$")
        private val labeledMnv = Regex(
            pattern = "(?i)(?:^|[?&;,{\\s])(?:\\\"?mnv\\\"?|ma[_ -]?nhan[_ -]?vien|mã[_ -]?nhân[_ -]?viên)\\s*[:=]\\s*[\\\"']?([0-9]{3,12})(?:[\\\"']|$|[?&;,}\\s])"
        )

        /**
         * Accept only an unambiguous personnel code. We deliberately do not pick an
         * arbitrary digit run from a QR payload because phone/PDA/order numbers can
         * also be present and must never resolve to the wrong employee silently.
         */
        fun extractPersonnelCode(raw: String): String? {
            val normalized = raw.trim().replace("\r", " ").replace("\n", " ")
            if (pureMnv.matches(normalized)) return normalized
            return labeledMnv.find(normalized)?.groupValues?.getOrNull(1)
        }
    }
}

package vn.pickpack1291.app.beta

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities

object DeviceNetworkStatus {
    data class Snapshot(
        val transport: String,
        val hasInternet: Boolean,
        val validated: Boolean,
        val metered: Boolean,
    ) {
        fun header(latencyMs: Long?): String {
            if (!hasInternet) return "Không mạng"
            val ms = latencyMs?.takeIf { it >= 0 }
            return if (ms != null) "$transport • ${ms}ms" else transport
        }
    }

    fun snapshot(context: Context): Snapshot {
        val cm = context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return Snapshot("Không mạng", false, false, false)
        val caps = cm.getNetworkCapabilities(network) ?: return Snapshot("Không mạng", false, false, false)
        val transport = when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "Wi-Fi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "Di động"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "Ethernet"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) -> "VPN"
            else -> "Internet"
        }
        return Snapshot(
            transport = transport,
            hasInternet = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET),
            validated = caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED),
            metered = !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED),
        )
    }
}

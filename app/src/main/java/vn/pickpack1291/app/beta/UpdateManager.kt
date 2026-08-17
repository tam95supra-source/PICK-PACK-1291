package vn.pickpack1291.app.beta

import android.app.Activity
import android.app.AlertDialog
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import java.security.MessageDigest

object UpdateManager {
    private var lastCheckAt = 0L
    private var dialogVisible = false
    private const val CHECK_INTERVAL_MS = 2 * 60_000L

    fun check(activity: Activity, force: Boolean = false) {
        val now = System.currentTimeMillis()
        if (!force && now - lastCheckAt < CHECK_INTERVAL_MS) return
        lastCheckAt = now
        BetaApiClient().updateCheck(BuildConfig.CHANNEL, BuildConfig.VERSION_NAME) { result ->
            activity.runOnUiThread {
                if (activity.isFinishing || activity.isDestroyed || !result.ok) return@runOnUiThread
                val j = result.json ?: return@runOnUiThread
                if (!j.optBoolean("available", false) || dialogVisible) return@runOnUiThread
                val version = j.optString("version_name")
                val url = j.optString("apk_url")
                val sha = j.optString("sha256")
                val notes = j.optString("notes").take(1200)
                val mandatory = j.optBoolean("mandatory", false)
                if (version.isBlank() || url.isBlank()) return@runOnUiThread
                showUpdate(activity, version, url, sha, notes, mandatory)
            }
        }
    }

    private fun showUpdate(activity: Activity, version: String, url: String, sha: String, notes: String, mandatory: Boolean) {
        dialogVisible = true
        val message = buildString {
            append("Có phiên bản mới: ").append(version)
            append("\nChannel: ").append(BuildConfig.CHANNEL)
            if (notes.isNotBlank()) append("\n\n").append(notes)
            append("\n\nAPK sẽ được kiểm tra SHA-256 trước khi mở trình cài đặt Android.")
        }
        val builder = AlertDialog.Builder(activity)
            .setTitle("Cập nhật Pick Pack 1291")
            .setMessage(message)
            .setPositiveButton("CẬP NHẬT") { _, _ ->
                dialogVisible = false
                ensureInstallPermissionThenDownload(activity, version, url, sha)
            }
        if (!mandatory) builder.setNegativeButton("ĐỂ SAU") { _, _ -> dialogVisible = false }
        builder.setOnCancelListener { dialogVisible = false }
        builder.setCancelable(!mandatory)
        builder.show()
    }

    private fun ensureInstallPermissionThenDownload(activity: Activity, version: String, url: String, sha: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !activity.packageManager.canRequestPackageInstalls()) {
            Toast.makeText(activity, "Cho phép cài ứng dụng từ nguồn này, sau đó quay lại app. App sẽ tự hiện cập nhật lại.", Toast.LENGTH_LONG).show()
            activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}")))
            lastCheckAt = 0L
            return
        }
        download(activity, version, url, sha)
    }

    private fun download(activity: Activity, version: String, url: String, expectedSha: String) {
        val manager = activity.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val fileName = "pick-pack-1291-${BuildConfig.CHANNEL.lowercase()}-$version.apk"
        val request = DownloadManager.Request(Uri.parse(url))
            .setTitle("Pick Pack 1291 $version")
            .setDescription("Đang tải bản cập nhật")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .setMimeType("application/vnd.android.package-archive")
            .setDestinationInExternalFilesDir(activity, Environment.DIRECTORY_DOWNLOADS, fileName)
        val id = manager.enqueue(request)
        Toast.makeText(activity, "Đang tải bản cập nhật $version", Toast.LENGTH_SHORT).show()

        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L) != id) return
                try { activity.unregisterReceiver(this) } catch (_: Throwable) {}
                val uri = manager.getUriForDownloadedFile(id)
                if (uri == null) {
                    AlertDialog.Builder(activity).setTitle("Cập nhật thất bại").setMessage("Không lấy được file APK đã tải.").setPositiveButton("OK", null).show()
                    return
                }
                Thread {
                    val actual = sha256(activity, uri)
                    activity.runOnUiThread {
                        if (expectedSha.isNotBlank() && !actual.equals(expectedSha, ignoreCase = true)) {
                            AlertDialog.Builder(activity).setTitle("APK không hợp lệ").setMessage("SHA-256 không khớp. File cập nhật sẽ không được cài.").setPositiveButton("OK", null).show()
                            return@runOnUiThread
                        }
                        val install = Intent(Intent.ACTION_VIEW).apply {
                            setDataAndType(uri, "application/vnd.android.package-archive")
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        activity.startActivity(install)
                    }
                }.start()
            }
        }
        if (Build.VERSION.SDK_INT >= 33) {
            activity.registerReceiver(receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            activity.registerReceiver(receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE))
        }
    }

    private fun sha256(context: Context, uri: Uri): String {
        val md = MessageDigest.getInstance("SHA-256")
        context.contentResolver.openInputStream(uri)?.use { input ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val n = input.read(buf)
                if (n <= 0) break
                md.update(buf, 0, n)
            }
        } ?: return ""
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}

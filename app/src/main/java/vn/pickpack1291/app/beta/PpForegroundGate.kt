package vn.pickpack1291.app.beta

import java.util.concurrent.atomic.AtomicBoolean

/**
 * Owner S33 lifecycle gate. Ordinary business sync may start only while an authenticated
 * OperationsActivity is visible. Existing in-flight requests are not cancelled; they may drain.
 * A process started only for FCM/WorkManager starts with this flag false, so invalidations remain
 * durable and catch-up waits for the next foreground session.
 */
object PpForegroundGate {
    private val visible = AtomicBoolean(false)
    fun enter() { visible.set(true) }
    fun leave() { visible.set(false) }
    fun isForeground(): Boolean = visible.get()
}

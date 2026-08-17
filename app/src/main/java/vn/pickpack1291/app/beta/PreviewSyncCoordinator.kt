package vn.pickpack1291.app.beta

import android.os.Handler
import android.os.Looper

class PreviewSyncCoordinator(private val onState: (State, String) -> Unit) {
    enum class State { ACTIVE, DRAINING, SUSPENDED }

    private val handler = Handler(Looper.getMainLooper())
    private var inFlight = false
    private var pendingSuspend = false
    var state: State = State.SUSPENDED
        private set

    fun enterForeground() {
        pendingSuspend = false
        state = State.ACTIVE
        onState(state, "Đồng bộ ngay khi vào app")
        startExchange()
    }

    fun leaveForeground() {
        if (inFlight) {
            pendingSuspend = true
            state = State.DRAINING
            onState(state, "Đang hoàn tất giao dịch trước khi nghỉ")
        } else {
            suspendNow()
        }
    }

    fun manualExchange() {
        if (state != State.SUSPENDED) startExchange()
    }

    private fun startExchange() {
        if (inFlight) return
        inFlight = true
        onState(state, "SYNC • đang trao đổi dữ liệu")
        handler.postDelayed({
            inFlight = false
            onState(state, "BETA PREVIEW • backend chưa kết nối")
            if (pendingSuspend) suspendNow()
        }, 650)
    }

    private fun suspendNow() {
        pendingSuspend = false
        state = State.SUSPENDED
        onState(state, "SYNC nghỉ khi app không sử dụng")
    }
}

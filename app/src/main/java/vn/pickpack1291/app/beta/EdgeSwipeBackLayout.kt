package vn.pickpack1291.app.beta

import android.content.Context
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.widget.FrameLayout
import kotlin.math.abs

/**
 * S47: horizontal swipe anywhere in the app is Back, in either direction.
 * Taps and vertical scrolling are left untouched; interception starts only
 * after a clearly horizontal movement exceeds touch slop.
 */
class EdgeSwipeBackLayout(context: Context, private val onBackGesture: () -> Unit) : FrameLayout(context) {
    private val trigger = 72f * resources.displayMetrics.density
    private val slop = ViewConfiguration.get(context).scaledTouchSlop
    private var startX = 0f
    private var startY = 0f
    private var tracking = false
    private var intercepted = false

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                startX = ev.x
                startY = ev.y
                tracking = true
                intercepted = false
            }
            MotionEvent.ACTION_MOVE -> if (tracking) {
                val dx = abs(ev.x - startX)
                val dy = abs(ev.y - startY)
                if (dx > slop * 1.5f && dx > dy * 1.30f) {
                    intercepted = true
                    return true
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                tracking = false
                intercepted = false
            }
        }
        return false
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        if (!tracking && !intercepted) return super.onTouchEvent(ev)
        when (ev.actionMasked) {
            MotionEvent.ACTION_UP -> {
                val dx = abs(ev.x - startX)
                val dy = abs(ev.y - startY)
                tracking = false
                intercepted = false
                if (dx >= trigger && dx > dy * 1.30f) onBackGesture()
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                tracking = false
                intercepted = false
                return true
            }
        }
        return true
    }
}

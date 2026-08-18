package vn.pickpack1291.app.beta

import android.content.Context
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.widget.FrameLayout
import kotlin.math.abs

/** Back gesture from either edge: left→right or right→left. */
class EdgeSwipeBackLayout(context: Context, private val onBackGesture: () -> Unit) : FrameLayout(context) {
    private val edge = 26f * resources.displayMetrics.density
    private val trigger = 84f * resources.displayMetrics.density
    private val slop = ViewConfiguration.get(context).scaledTouchSlop
    private var startX = 0f
    private var startY = 0f
    private var direction = 0 // +1 left edge -> right, -1 right edge -> left
    private var tracking = false
    private var intercepted = false

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                startX = ev.x
                startY = ev.y
                direction = when {
                    startX <= edge -> 1
                    startX >= width - edge -> -1
                    else -> 0
                }
                tracking = direction != 0
                intercepted = false
            }
            MotionEvent.ACTION_MOVE -> if (tracking) {
                val dx = ev.x - startX
                val directedDx = dx * direction
                val dy = abs(ev.y - startY)
                if (directedDx > slop && directedDx > dy * 1.25f) {
                    intercepted = true
                    return true
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                tracking = false
                direction = 0
            }
        }
        return false
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        if (!tracking && !intercepted) return super.onTouchEvent(ev)
        when (ev.actionMasked) {
            MotionEvent.ACTION_UP -> {
                val directedDx = (ev.x - startX) * direction
                val dy = abs(ev.y - startY)
                tracking = false
                intercepted = false
                direction = 0
                if (directedDx >= trigger && directedDx > dy * 1.25f) onBackGesture()
                return true
            }
            MotionEvent.ACTION_CANCEL -> {
                tracking = false
                intercepted = false
                direction = 0
                return true
            }
        }
        return true
    }
}

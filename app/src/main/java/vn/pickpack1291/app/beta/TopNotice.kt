package vn.pickpack1291.app.beta

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.view.Gravity
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

object TopNotice {
    enum class Kind { INFO, SUCCESS, WARNING, ERROR }
    private const val TAG="PP_TOP_NOTICE_STACK"

    fun show(activity:Activity,message:String,kind:Kind=Kind.INFO){
        activity.runOnUiThread{
            val host=activity.findViewById<ViewGroup>(android.R.id.content) ?: return@runOnUiThread
            var stack=host.findViewWithTag<LinearLayout>(TAG)
            if(stack==null){
                stack=LinearLayout(activity).apply{
                    tag=TAG
                    orientation=LinearLayout.VERTICAL
                    setPadding(dp(activity,10),dp(activity,4),dp(activity,10),0)
                    elevation=dp(activity,18).toFloat()
                }
                val topInset=statusBarInset(activity)
                host.addView(stack,FrameLayout.LayoutParams(-1,-2,Gravity.TOP).apply{topMargin=topInset+dp(activity,4)})
            }
            while(stack.childCount>=2)stack.removeViewAt(0)
            val palette=ThemeManager.palette(activity)
            val (fg,bg,prefix)=when(kind){
                Kind.ERROR->Triple(Color.rgb(153,27,27),Color.rgb(254,226,226),"! ")
                Kind.WARNING->Triple(Color.rgb(146,64,14),Color.rgb(255,237,213),"! ")
                Kind.SUCCESS->Triple(palette.dark,palette.soft,"✓ ")
                Kind.INFO->Triple(palette.dark,palette.soft,"ⓘ ")
            }
            val item=TextView(activity).apply{
                text=prefix+message
                textSize=11.5f
                setTextColor(fg)
                typeface=Typeface.DEFAULT_BOLD
                setPadding(dp(activity,12),dp(activity,9),dp(activity,12),dp(activity,9))
                maxLines=3
                background=GradientDrawable().apply{setColor(bg);cornerRadius=dp(activity,8).toFloat()}
                contentDescription=message
                setOnClickListener{
                    val parent=parent as? ViewGroup ?: return@setOnClickListener
                    parent.removeView(this)
                    if(parent.childCount==0)(parent.parent as? ViewGroup)?.removeView(parent)
                }
            }
            stack.addView(item,LinearLayout.LayoutParams(-1,-2).apply{bottomMargin=dp(activity,5)})
            val duration=when(kind){Kind.SUCCESS->2200L;Kind.INFO->2800L;Kind.WARNING->3800L;Kind.ERROR->5000L}
            item.postDelayed({
                val parent=item.parent as? ViewGroup ?: return@postDelayed
                parent.removeView(item)
                if(parent.childCount==0)(parent.parent as? ViewGroup)?.removeView(parent)
            },duration)
        }
    }

    @Suppress("DEPRECATION")
    private fun statusBarInset(activity:Activity):Int{
        val insets=activity.window.decorView.rootWindowInsets ?: return 0
        return if(Build.VERSION.SDK_INT>=30) insets.getInsets(WindowInsets.Type.statusBars()).top else insets.systemWindowInsetTop
    }
    private fun dp(a:Activity,v:Int)=(v*a.resources.displayMetrics.density).toInt()
}

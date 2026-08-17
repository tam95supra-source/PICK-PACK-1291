package vn.pickpack1291.app.beta

import android.app.Activity
import android.view.View

fun <T : View> Activity.findViewWithTag(tag: Any): T? = window.decorView.findViewWithTag(tag)

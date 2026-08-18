package vn.pickpack1291.app.beta

import android.content.Context
import android.graphics.Color

object ThemeManager {
    data class Palette(val primary:Int,val dark:Int,val soft:Int,val background:Int,val line:Int)
    private const val PREFS="pp1291_theme"
    private const val KEY="theme_index"
    private val palettes=arrayOf(
        Palette(Color.rgb(37,99,235),Color.rgb(30,64,175),Color.rgb(239,246,255),Color.rgb(248,250,252),Color.rgb(219,228,242)),
        Palette(Color.rgb(13,148,136),Color.rgb(15,118,110),Color.rgb(236,253,250),Color.rgb(248,250,250),Color.rgb(214,229,226)),
        Palette(Color.rgb(34,160,72),Color.rgb(21,128,61),Color.rgb(240,253,244),Color.rgb(249,251,249),Color.rgb(218,232,221)),
        Palette(Color.rgb(234,112,18),Color.rgb(194,65,12),Color.rgb(255,247,237),Color.rgb(252,250,248),Color.rgb(235,224,213)),
        Palette(Color.rgb(220,55,55),Color.rgb(185,28,28),Color.rgb(254,242,242),Color.rgb(252,249,249),Color.rgb(236,220,220)),
        Palette(Color.rgb(124,58,237),Color.rgb(91,33,182),Color.rgb(245,243,255),Color.rgb(250,249,252),Color.rgb(229,222,240)),
        Palette(Color.rgb(100,116,139),Color.rgb(51,65,85),Color.rgb(241,245,249),Color.rgb(248,250,252),Color.rgb(226,232,240))
    )
    fun selectedIndex(context:Context)=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getInt(KEY,1).coerceIn(0,palettes.lastIndex)
    fun select(context:Context,index:Int){context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putInt(KEY,index.coerceIn(0,palettes.lastIndex)).apply()}
    fun palette(context:Context)=palettes[selectedIndex(context)]
    fun primary(context:Context)=palette(context).primary
    fun primaryDark(context:Context)=palette(context).dark
    fun soft(context:Context)=palette(context).soft
    fun background(context:Context)=palette(context).background
    fun line(context:Context)=palette(context).line
    fun swatches()=palettes.map{it.primary}
}

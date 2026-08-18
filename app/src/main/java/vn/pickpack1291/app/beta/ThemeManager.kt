package vn.pickpack1291.app.beta

import android.content.Context
import android.graphics.Color

object ThemeManager {
    data class Palette(val primary:Int,val dark:Int,val accent:Int,val soft:Int,val background:Int,val line:Int)
    private const val PREFS="pp1291_theme"
    private const val KEY="theme_index"
    private val palettes=arrayOf(
        Palette(Color.rgb(37,99,235),Color.rgb(30,64,175),Color.rgb(124,58,237),Color.rgb(239,246,255),Color.rgb(246,248,255),Color.rgb(211,222,247)),
        Palette(Color.rgb(13,148,136),Color.rgb(15,118,110),Color.rgb(37,99,235),Color.rgb(236,253,250),Color.rgb(246,251,251),Color.rgb(205,232,228)),
        Palette(Color.rgb(34,160,72),Color.rgb(21,128,61),Color.rgb(6,182,212),Color.rgb(240,253,244),Color.rgb(247,251,248),Color.rgb(207,233,216)),
        Palette(Color.rgb(234,112,18),Color.rgb(194,65,12),Color.rgb(239,68,68),Color.rgb(255,247,237),Color.rgb(252,249,246),Color.rgb(238,220,202)),
        Palette(Color.rgb(220,55,55),Color.rgb(185,28,28),Color.rgb(124,58,237),Color.rgb(254,242,242),Color.rgb(252,247,249),Color.rgb(239,214,219)),
        Palette(Color.rgb(124,58,237),Color.rgb(91,33,182),Color.rgb(37,99,235),Color.rgb(245,243,255),Color.rgb(249,247,253),Color.rgb(226,216,245)),
        Palette(Color.rgb(100,116,139),Color.rgb(51,65,85),Color.rgb(71,85,105),Color.rgb(241,245,249),Color.rgb(247,249,251),Color.rgb(218,225,234))
    )
    fun selectedIndex(context:Context)=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getInt(KEY,0).coerceIn(0,palettes.lastIndex)
    fun select(context:Context,index:Int){context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putInt(KEY,index.coerceIn(0,palettes.lastIndex)).apply()}
    fun palette(context:Context)=palettes[selectedIndex(context)]
    fun primary(context:Context)=palette(context).primary
    fun primaryDark(context:Context)=palette(context).dark
    fun accent(context:Context)=palette(context).accent
    fun soft(context:Context)=palette(context).soft
    fun background(context:Context)=palette(context).background
    fun line(context:Context)=palette(context).line
    fun swatches()=palettes.map{it.primary}
}

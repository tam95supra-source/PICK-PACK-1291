from pathlib import Path

ROOT = Path('.')


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'missing patch anchor: {label}')
    return text.replace(old, new, 1)

# --- Theme tokens: Sample 1 visual system, still honoring all 7 selectable colors.
theme = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/ThemeManager.kt'
theme.write_text('''package vn.pickpack1291.app.beta

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
''', encoding='utf-8')

# --- FullBetaActivity: Sample 1 dashboard + themed shell + smooth cross-activity handoff.
p = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt'
s = p.read_text(encoding='utf-8')
s = must_replace(s,
'''    private val teal:Int get() = ThemeManager.primary(this)
    private val bg:Int get() = ThemeManager.background(this)
''',
'''    private val teal:Int get() = ThemeManager.primary(this)
    private val accent:Int get() = ThemeManager.accent(this)
    private val bg:Int get() = ThemeManager.background(this)
''','full accent property')
s = must_replace(s,
'''        window.statusBarColor = Color.WHITE
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
''',
'''        window.statusBarColor = ThemeManager.primaryDark(this)
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
''','full system bars')
start = s.index('    private fun dashboard() {')
end = s.index('    private fun openModule(', start)
new_dashboard = '''    private fun dashboard() {
        currentScreen = "DASHBOARD"
        liveEmployeeMnv = ""
        val root=column(bg)
        root.addView(appBar("PICK PACK 1291",false))
        val body=column(bg).apply{setPadding(dp(12),dp(12),dp(12),dp(92))}
        body.addView(txt("Nghiệp vụ",15.5f,ink,true))
        body.addView(txt("${accountName.ifBlank{accountLogin}} • ${roleText(accountRole)}",9.8f,muted,false))
        body.addView(gap(10))

        val hero=column(Color.TRANSPARENT).apply{
            setPadding(dp(16),dp(16),dp(16),dp(14))
            background=gradient(blue,accent,18)
            elevation=dp(6).toFloat()
            setOnClickListener{employeeScan()}
            addView(row(Color.TRANSPARENT).apply{
                addView(column(Color.TRANSPARENT).apply{
                    addView(txt("QUÉT QR\nNHÂN SỰ",22f,Color.WHITE,true))
                    addView(gap(5))
                    addView(txt("Quét hoặc nhập MNV • Enter/OK để xử lý ngay",10f,Color.argb(225,255,255,255),false))
                },LinearLayout.LayoutParams(0,-2,1f))
                addView(txt("▦",42f,Color.WHITE,true).apply{
                    gravity=Gravity.CENTER
                    background=round(Color.argb(38,255,255,255),16)
                },size(dp(86),dp(86)))
            },matchWrap())
            addView(gap(12))
            addView(Button(this@FullBetaActivity).apply{
                text="▣  BẮT ĐẦU QUÉT"
                textSize=12.5f
                setTextColor(navy)
                typeface=Typeface.DEFAULT_BOLD
                isAllCaps=false
                minHeight=dp(48)
                background=round(Color.WHITE,10)
                setOnClickListener{employeeScan()}
            },matchWrap())
        }
        body.addView(hero,matchWrap())
        body.addView(gap(11))

        val cards=mutableListOf<View>()
        if(accountRole=="ADMIN"||accountRole=="SUPERADMIN") {
            cards.add(businessTile("◉","Công nhật","Bắt đầu / hoàn thành",green){openModule("LABOR")})
        } else {
            cards.add(businessTile("▥","Báo cáo","Theo ca / ngày",orange){openModule("REPORT")})
        }
        if(accountRole=="ADMIN"||accountRole=="SUPERADMIN") {
            cards.add(businessTile("▥","Báo cáo","Theo ca / ngày",orange){openModule("REPORT")})
        } else {
            cards.add(businessTile("☷","Theo dõi ca","Phiên hôm nay",teal){openModule("LISTS")})
        }
        cards.add(businessTile("↔","Tài nguyên","PDA • Pick • Pack",accent){openModule("RESOURCES")})
        cards.add(if(accountRole=="ADMIN"||accountRole=="SUPERADMIN")
            businessTile("☷","Theo dõi ca","Phiên hôm nay",teal){openModule("LISTS")}
        else businessTile("◉","Nhân sự","Tra cứu danh sách",green){openModule("STAFF")})
        body.addView(cardRow(cards[0],cards[1]))
        body.addView(gap(8))
        body.addView(cardRow(cards[2],cards[3]))
        body.addView(gap(10))
        body.addView(txt("Màu giao diện được đổi trong tab Cài đặt • 7 màu đồng bộ toàn ứng dụng",9.2f,muted,false).apply{gravity=Gravity.CENTER})

        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root);refreshStatus()
    }

'''
s = s[:start] + new_dashboard + s[end:]
s = must_replace(s,
'''    private fun openModule(module: String, mnv: String = "") {
        startActivity(Intent(this, OperationsActivity::class.java).apply {
            putExtra("module", module); putExtra("login", accountLogin); putExtra("name", accountName); putExtra("role", accountRole); putExtra("position", accountPosition); putExtra("email", accountEmail); putExtra("mnv", mnv)
        })
    }
''',
'''    private fun openModule(module: String, mnv: String = "") {
        startActivity(Intent(this, OperationsActivity::class.java).apply {
            putExtra("module", module); putExtra("login", accountLogin); putExtra("name", accountName); putExtra("role", accountRole); putExtra("position", accountPosition); putExtra("email", accountEmail); putExtra("mnv", mnv)
        })
        @Suppress("DEPRECATION")
        overridePendingTransition(android.R.anim.fade_in,android.R.anim.fade_out)
    }
''','full openModule')
app_start = s.index('    private fun appBar(title:String,back:Boolean)=')
app_end = s.index('    private fun menuRow(', app_start)
new_appbar = '''    private fun appBar(title:String,back:Boolean)=row(Color.TRANSPARENT).apply{
        gravity=Gravity.CENTER_VERTICAL
        setPadding(dp(8),dp(7),dp(8),dp(7))
        background=gradient(navy,accent,0)
        addView(txt(if(back)"‹" else "",if(back)30f else 20f,Color.WHITE,false).apply{gravity=Gravity.CENTER;if(back)setOnClickListener{navigateBack()}},size(dp(40),dp(44)))
        addView(txt(title,17f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f))
        syncText=txt("↻ Đang nối",8.5f,Color.WHITE,true).apply{
            gravity=Gravity.CENTER;maxLines=2;setPadding(dp(5),dp(4),dp(5),dp(4));background=round(Color.argb(35,255,255,255),12)
        }
        addView(syncText,size(dp(102),dp(40)))
    }
'''
s = s[:app_start] + new_appbar + s[app_end:]
insert_at = s.index('    private fun fullCard(')
business_helper = '''    private fun businessTile(icon:String,title:String,sub:String,color:Int,click:()->Unit)=row(Color.TRANSPARENT).apply{
        gravity=Gravity.CENTER_VERTICAL
        setPadding(dp(11),dp(11),dp(9),dp(11))
        background=GradientDrawable(GradientDrawable.Orientation.TL_BR,intArrayOf(Color.WHITE,ThemeManager.soft(this@FullBetaActivity))).apply{
            cornerRadius=dp(14).toFloat();setStroke(dp(1),Color.argb(80,Color.red(color),Color.green(color),Color.blue(color)))
        }
        elevation=dp(2).toFloat()
        addView(txt(icon,23f,color,true).apply{gravity=Gravity.CENTER;background=round(Color.argb(25,Color.red(color),Color.green(color),Color.blue(color)),18)},size(dp(48),dp(48)))
        addView(column(Color.TRANSPARENT).apply{addView(txt(title,12.6f,ink,true));addView(gap(2));addView(txt(sub,9.5f,muted,false))},LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(8)})
        addView(txt("›",22f,color,true).apply{gravity=Gravity.CENTER},size(dp(24),dp(48)))
        setOnClickListener{click()}
    }

'''
s = s[:insert_at] + business_helper + s[insert_at:]
nav_start = s.index('    private fun bottomNav(active:String):')
nav_end = s.index('    private fun sessionExpired()', nav_start)
new_nav = '''    private fun bottomNav(active:String): LinearLayout = row(Color.TRANSPARENT).apply {
        gravity = Gravity.CENTER
        setPadding(dp(4),dp(4),dp(4),dp(4))
        background = gradient(navy,accent,0)
        val inactive=Color.argb(185,255,255,255)
        val items = listOf(
            Triple("▦","Nghiệp vụ","BUSINESS"),
            Triple("◉","Nhân sự","STAFF"),
            Triple("◷","Lịch sử","HISTORY"),
            Triple("↻","Đồng bộ","SYNC"),
            Triple("⚙","Cài đặt","SETTINGS")
        )
        items.forEach { item ->
            val chosen=item.third==active
            val cell = column(Color.TRANSPARENT).apply {
                gravity = Gravity.CENTER
                if(chosen) background=round(Color.argb(35,255,255,255),10)
                addView(txt(item.first,17f,if(chosen)Color.WHITE else inactive,true).apply { gravity=Gravity.CENTER })
                addView(txt(item.second,8.4f,if(chosen)Color.WHITE else inactive,chosen).apply { gravity=Gravity.CENTER; maxLines=1 })
                setOnClickListener { _ -> if(item.third=="BUSINESS") dashboard() else openModule(item.third) }
            }
            addView(cell,LinearLayout.LayoutParams(0,-1,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        }
    }

'''
s = s[:nav_start] + new_nav + s[nav_end:]
s = must_replace(s,
'''    private fun round(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat()}
''',
'''    private fun round(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat()}
    private fun gradient(a:Int,b:Int,r:Int)=GradientDrawable(GradientDrawable.Orientation.TL_BR,intArrayOf(a,b)).apply{cornerRadius=dp(r).toFloat()}
''','full gradient helper')
p.write_text(s, encoding='utf-8')

# --- OperationsActivity: same Activity for the four top-level tabs, persistent shell + crossfade.
p = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s = p.read_text(encoding='utf-8')
s = must_replace(s,
'''import android.graphics.drawable.GradientDrawable
import android.os.Build
''',
'''import android.graphics.drawable.GradientDrawable
import android.transition.Fade
import android.transition.TransitionManager
import android.os.Build
''','ops transition imports')
s = must_replace(s,
'''    private val teal:Int get()=ThemeManager.primary(this)
    private val bg:Int get()=ThemeManager.background(this)
''',
'''    private val teal:Int get()=ThemeManager.primary(this)
    private val accent:Int get()=ThemeManager.accent(this)
    private val bg:Int get()=ThemeManager.background(this)
''','ops accent property')
s = must_replace(s,
'''    private var screenState = "ROOT"
    private var syncText: TextView? = null
''',
'''    private var screenState = "ROOT"
    private var syncText: TextView? = null
    private var contentHost: FrameLayout? = null
    private var navHost: FrameLayout? = null
''','ops persistent host fields')
s = must_replace(s,
'''        window.statusBarColor = Color.WHITE
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
''',
'''        window.statusBarColor = ThemeManager.primaryDark(this)
        window.navigationBarColor = Color.WHITE
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
''','ops system bars')
s = must_replace(s,
'''    private fun attach(root:LinearLayout,body:LinearLayout){root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setContentView(host(root))}
    private fun appBar(title:String)=row(navy).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(8),dp(6),dp(8),dp(6));addView(txt("‹",30f,Color.WHITE,false).apply{gravity=Gravity.CENTER;setOnClickListener{navigateBack()}},size(dp(40),dp(44)));addView(txt(title,16.5f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f));syncText=txt("↻ Đang nối",8.8f,Color.WHITE,true).apply{gravity=Gravity.CENTER;maxLines=2;setPadding(dp(4),dp(4),dp(4),dp(4))};addView(syncText,size(dp(102),dp(40)))}
''',
'''    private fun attach(root:LinearLayout,body:LinearLayout){
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f))
        val frame=contentHost
        if(frame==null){setContentView(host(root));return}
        TransitionManager.beginDelayedTransition(frame,Fade().apply{duration=150})
        frame.removeAllViews();frame.addView(root,FrameLayout.LayoutParams(-1,-1))
        navHost?.let{nav->nav.removeAllViews();nav.addView(bottomNav(),FrameLayout.LayoutParams(-1,-1))}
    }
    private fun appBar(title:String)=row(Color.TRANSPARENT).apply{
        gravity=Gravity.CENTER_VERTICAL;setPadding(dp(8),dp(7),dp(8),dp(7));background=gradient(navy,accent,0)
        addView(txt("‹",30f,Color.WHITE,false).apply{gravity=Gravity.CENTER;setOnClickListener{navigateBack()}},size(dp(40),dp(44)))
        addView(txt(title,16.5f,Color.WHITE,true),LinearLayout.LayoutParams(0,-2,1f))
        syncText=txt("↻ Đang nối",8.5f,Color.WHITE,true).apply{gravity=Gravity.CENTER;maxLines=2;setPadding(dp(5),dp(4),dp(5),dp(4));background=round(Color.argb(35,255,255,255),12)}
        addView(syncText,size(dp(102),dp(40)))
    }
''','ops attach appbar')
nav_start = s.index('    private fun bottomNav():')
nav_end = s.index('    private fun navigateTab(', nav_start)
new_ops_nav = '''    private fun bottomNav(): LinearLayout = row(Color.TRANSPARENT).apply {
        gravity=Gravity.CENTER
        setPadding(dp(4),dp(4),dp(4),dp(4))
        background=gradient(navy,accent,0)
        val active=activeTab();val inactive=Color.argb(185,255,255,255)
        val items=listOf(
            Triple("▦","Nghiệp vụ","BUSINESS"),
            Triple("◉","Nhân sự","STAFF"),
            Triple("◷","Lịch sử","HISTORY"),
            Triple("↻","Đồng bộ","SYNC"),
            Triple("⚙","Cài đặt","SETTINGS")
        )
        items.forEach { item ->
            val chosen=item.third==active
            val cell=column(Color.TRANSPARENT).apply {
                gravity=Gravity.CENTER
                if(chosen)background=round(Color.argb(35,255,255,255),10)
                addView(txt(item.first,17f,if(chosen)Color.WHITE else inactive,true).apply { gravity=Gravity.CENTER })
                addView(txt(item.second,8.4f,if(chosen)Color.WHITE else inactive,chosen).apply { gravity=Gravity.CENTER; maxLines=1 })
                setOnClickListener { _ -> navigateTab(item.third) }
            }
            addView(cell,LinearLayout.LayoutParams(0,-1,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        }
    }

'''
s = s[:nav_start] + new_ops_nav + s[nav_end:]
old_navtab = '''    private fun navigateTab(target:String){if(target==activeTab())return;if(target=="BUSINESS"){finish();return};startActivity(Intent(this,OperationsActivity::class.java).apply{putExtra("module",target);putExtra("login",login);putExtra("name",name);putExtra("role",role);putExtra("position",position);putExtra("email",email)});finish()}
'''
new_navtab = '''    private fun navigateTab(target:String){
        if(target==activeTab())return
        if(target=="BUSINESS"){
            finish()
            @Suppress("DEPRECATION")
            overridePendingTransition(android.R.anim.fade_in,android.R.anim.fade_out)
            return
        }
        module=target;initialMnv=""
        when(target){
            "STAFF"->staffScreen()
            "HISTORY"->historyScreen()
            "SYNC"->syncScreen()
            "SETTINGS"->settingsScreen()
        }
    }
'''
s = must_replace(s, old_navtab, new_navtab, 'ops navigateTab')
host_start = s.index('    private fun host(content:View):View{')
host_end = s.index('    private fun jsonStrings(', host_start)
new_host = '''    private fun host(content:View):View{
        val root=EdgeSwipeBackLayout(this){navigateBack()}.apply{setBackgroundColor(bg)}
        val contentFrame=FrameLayout(this).apply{addView(content,FrameLayout.LayoutParams(-1,-1))}
        val navFrame=FrameLayout(this).apply{addView(bottomNav(),FrameLayout.LayoutParams(-1,-1))}
        contentHost=contentFrame;navHost=navFrame
        root.addView(contentFrame,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(82)})
        root.addView(navFrame,FrameLayout.LayoutParams(-1,dp(60),Gravity.BOTTOM).apply{bottomMargin=dp(20)})
        root.addView(txt(FOOTER,8f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(20),Gravity.BOTTOM))
        root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION")val tt=i.systemWindowInsetTop;@Suppress("DEPRECATION")val bb=i.systemWindowInsetBottom;top=tt;bottom=bb};v.setPadding(0,top+dp(5),0,bottom+dp(2));i}
        root.requestApplyInsets();return root
    }
'''
s = s[:host_start] + new_host + s[host_end:]
s = must_replace(s,
'''    private fun round(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat()}
''',
'''    private fun round(c:Int,r:Int)=GradientDrawable().apply{setColor(c);cornerRadius=dp(r).toFloat()}
    private fun gradient(a:Int,b:Int,r:Int)=GradientDrawable(GradientDrawable.Orientation.TL_BR,intArrayOf(a,b)).apply{cornerRadius=dp(r).toFloat()}
''','ops gradient helper')
p.write_text(s, encoding='utf-8')

# --- Beta release metadata.
b = ROOT / 'app/build.gradle.kts'
t = b.read_text(encoding='utf-8')
t = must_replace(t,'versionCode = 11\n            versionName = "0.4.2-beta.5"','versionCode = 12\n            versionName = "0.4.2-beta.6"','beta version bump')
b.write_text(t, encoding='utf-8')

print('Sample 1 + smooth navigation patch applied; target 0.4.2-beta.6 / 12')

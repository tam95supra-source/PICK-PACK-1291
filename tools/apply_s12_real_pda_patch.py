#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ops_path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
api_path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt"
text = ops_path.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S12 patch anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)


def block(start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    global text
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"S12 block start {label!r} not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"S12 block end {label!r} not found")
    text = text[:start] + replacement + text[end:]

# Ping state comes from ForegroundSyncCoordinator latency measurement.
once(
    '    private var lastConnected: Boolean? = null\n',
    '    private var lastConnected: Boolean? = null\n    private var lastPingMs: Long? = null\n',
    'ping state',
)
once(
    '                lastConnected = status.connected\n                refreshHeaderConnection()\n',
    '                lastConnected = status.connected\n                lastPingMs = status.latencyMs\n                refreshHeaderConnection()\n',
    'ping listener',
)

# Scanner/search fields: two-line contextual hint + scan icon, no clipped text.
once(
    'val root=baseRoot("DANH SÁCH");val body=body();val q=input("Scan / Nhập mã nhân viên, họ tên để tìm kiếm",false).apply{setSingleLine(true);minHeight=dp(72)};',
    'val root=baseRoot("DANH SÁCH");val body=body();val q=scanSearchInput("Scan / Nhập mã nhân viên, họ tên để tìm kiếm");',
    'lists wrapped search',
)
once(
    '        val q=input("Scan / Nhập mã nhân viên, họ tên để tìm kiếm",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH;minHeight=dp(72)}\n        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(72),1f))\n',
    '        val q=scanSearchInput("Scan / Nhập mã nhân viên, họ tên để tìm kiếm")\n        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(76),1f))\n',
    'staff wrapped search',
)

# One authoritative report call. GAS returns the fully composed current-day projection.
block(
    '    private fun reportScreen(){',
    '    private fun historyScreen(){',
    r'''    private fun reportScreen(){
        screenState="REPORT"
        val root=baseRoot("BÁO CÁO")
        val body=column(bg).apply{setPadding(dp(3),dp(4),dp(3),dp(32))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày")).apply{minimumHeight=dp(42)}
        body.addView(period,matchWrap());body.addView(gap(3))
        val box=column(bg);body.addView(box,matchWrap());box.addView(txt("Đang tải báo cáo...",10f,muted,false))
        var reportJson:JSONObject?=null
        fun render(){
            val rootJson=reportJson?:return
            box.removeAllViews()
            val key=when(period.selectedItemPosition){0->"ca1_hc";1->"ca2";else->"all"}
            val p=rootJson.optJSONObject("reports")?.optJSONObject(key)?:JSONObject()
            val manpower=p.optJSONObject("manpower")
            box.addView(reportTable("",manpower,"Vị trí","position",true),matchWrap())
            val picker=p.optJSONObject("picker_tenure")
            val packer=p.optJSONObject("packer_tenure")
            box.addView(gap(5));box.addView(reportTable("Thâm niên Picker",picker,"Thâm niên","label",false),matchWrap())
            box.addView(gap(5));box.addView(reportTable("Thâm niên Packer",packer,"Thâm niên","label",false),matchWrap())
            val support=p.optJSONObject("support")
            if((support?.optInt("total")?:0)>0){
                box.addView(gap(5));box.addView(reportTable("Hỗ trợ bộ phận khác",support,"Hỗ trợ","label",false),matchWrap())
                val remaining=p.optJSONObject("remaining")?:JSONObject()
                val rp=remaining.optJSONObject("picker")?:JSONObject()
                val rk=remaining.optJSONObject("packer")?:JSONObject()
                box.addView(gap(5))
                box.addView(column(ThemeManager.soft(this)).apply{
                    setPadding(dp(8),dp(6),dp(8),dp(6));background=outlineBg(ThemeManager.soft(this@OperationsActivity),8)
                    addView(txt("Sau khấu trừ hỗ trợ",9.6f,navy,true))
                    addView(txt("Picker: ${rp.optInt("total")}  •  Cũ ${rp.optInt("old")}  •  Mới ${rp.optInt("new")}",9.4f,ink,false))
                    addView(txt("Packer: ${rk.optInt("total")}  •  Cũ ${rk.optInt("old")}  •  Mới ${rk.optInt("new")}",9.4f,ink,false))
                },matchWrap())
            }
        }
        period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{
            override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()}
            override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit
        }
        api.call("report_daily"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            if(!r.ok){box.removeAllViews();box.addView(info(r.error?:"Không tải được báo cáo"));return@runOnUiThread}
            reportJson=r.json?:JSONObject();render()
        }}
        attach(root,body)
    }

    private fun reportTable(title:String,data:JSONObject?,firstTitle:String,rowKey:String,highlightPhuc:Boolean):View{
        val outer=column(surface).apply{setPadding(0,0,0,0);setBackgroundColor(surface)}
        if(title.isNotBlank())outer.addView(txt(title,10.2f,navy,true).apply{setPadding(dp(2),dp(2),0,dp(3))})
        if(data==null){outer.addView(txt("Chưa có dữ liệu",9.4f,muted,false));return outer}
        val columns=jsonStrings(data.optJSONArray("columns"))
        val rows=data.optJSONArray("rows")?:JSONArray()
        val table=TableLayout(this).apply{isStretchAllColumns=false;isShrinkAllColumns=false}
        val header=TableRow(this)
        header.addView(reportFixedCell(firstTitle,true,true,false),TableRow.LayoutParams(dp(126),-2))
        columns.forEach{header.addView(reportFixedCell(reportColumnLabel(it),true,false,false),TableRow.LayoutParams(dp(if(it=="IH")44 else 40),-2))}
        header.addView(reportFixedCell("Tổng",true,false,true),TableRow.LayoutParams(dp(42),-2));table.addView(header)
        for(i in 0 until rows.length()){
            val item=rows.optJSONObject(i)?:continue
            val label=item.optString(rowKey)
            val tr=TableRow(this)
            tr.addView(reportFixedCell(label,false,true,highlightPhuc&&label=="Phúc Long"),TableRow.LayoutParams(dp(126),-2))
            val counts=item.optJSONObject("counts")?:JSONObject()
            columns.forEach{c->tr.addView(reportFixedCell(counts.optInt(c).toString(),false,false,highlightPhuc&&label=="Phúc Long"),TableRow.LayoutParams(dp(if(c=="IH")44 else 40),-1))}
            tr.addView(reportFixedCell(item.optInt("total").toString(),false,false,highlightPhuc&&label=="Phúc Long",true),TableRow.LayoutParams(dp(42),-1));table.addView(tr)
        }
        val totals=data.optJSONObject("totals")
        if(totals!=null){
            val tr=TableRow(this)
            tr.addView(reportFixedCell("Tổng",true,true,false),TableRow.LayoutParams(dp(126),-2))
            columns.forEach{c->tr.addView(reportFixedCell(totals.optInt(c).toString(),true,false,false),TableRow.LayoutParams(dp(if(c=="IH")44 else 40),-1))}
            tr.addView(reportFixedCell(data.optInt("total").toString(),true,false,true),TableRow.LayoutParams(dp(42),-1));table.addView(tr)
        }
        outer.addView(HorizontalScrollView(this).apply{isHorizontalScrollBarEnabled=true;fillViewport=false;addView(table,ViewGroup.LayoutParams(-2,-2))},matchWrap())
        return outer
    }

    private fun reportColumnLabel(v:String)=if(v=="IH")"Inhouse" else v
    private fun reportFixedCell(v:String,header:Boolean=false,first:Boolean=false,highlight:Boolean=false,total:Boolean=false)=TextView(this).apply{
        text=v;textSize=if(header)8.0f else 8.3f;setTextColor(if(header||total)navy else ink)
        typeface=if(header||first||total)Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        gravity=if(first)Gravity.START or Gravity.CENTER_VERTICAL else Gravity.CENTER
        setPadding(dp(if(first)5 else 2),dp(4),dp(2),dp(4));maxLines=if(first)3 else 2
        background=GradientDrawable().apply{
            setColor(when{highlight->Color.rgb(246,249,82);header||total->Color.rgb(226,238,244);else->Color.WHITE})
            setStroke(dp(1),Color.rgb(105,118,126))
        }
    }

''',
    'server report renderer',
)

# History: compact overview; detail appears on tap instead of consuming list viewport.
block(
    '    private fun historyScreen(){',
    '    private fun syncScreen(){',
    r'''    private fun historyScreen(){
        module="HISTORY"
        screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ")
        val body=body()
        val items=AppHistory.items(this)
        var success=0
        for(i in 0 until items.length())if(items.optJSONObject(i)?.optBoolean("synced")==true)success++
        val failed=items.length()-success
        val summary=row(bg)
        summary.addView(metric("Tổng",items.length().toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)})
        summary.addView(metric("Hoàn tất",success.toString(),green),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        summary.addView(metric("Xem lại",failed.toString(),if(failed>0)red else green),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)})
        body.addView(summary,matchWrap());body.addView(gap(5))
        val filter=spinner(arrayOf("Tất cả","Hoàn tất","Cần xem lại")).apply{minimumHeight=dp(42)}
        body.addView(filter,matchWrap());body.addView(gap(5))
        val box=column(bg);body.addView(box,matchWrap())
        fun render(){
            box.removeAllViews();var shown=0;var lastDay=""
            val dayKey=java.text.SimpleDateFormat("yyyyMMdd",java.util.Locale.US)
            val dayText=java.text.SimpleDateFormat("dd/MM/yyyy",java.util.Locale.US)
            val timeText=java.text.SimpleDateFormat("HH:mm:ss",java.util.Locale.US)
            val today=dayKey.format(java.util.Date())
            for(i in 0 until items.length()){
                val x=items.optJSONObject(i)?:continue;val ok=x.optBoolean("synced")
                if(filter.selectedItemPosition==1&&!ok)continue;if(filter.selectedItemPosition==2&&ok)continue
                val date=java.util.Date(x.optLong("at"));val key=dayKey.format(date)
                if(key!=lastDay){lastDay=key;if(shown>0)box.addView(gap(4));box.addView(txt(if(key==today)"Hôm nay" else dayText.format(date),9.8f,navy,true));box.addView(gap(3))}
                val action=x.optString("action");val ctx=x.optJSONObject("context")
                val mnv=ctx?.optString("mnv").orEmpty()
                val card=row(surface).apply{
                    gravity=Gravity.CENTER_VERTICAL;setPadding(dp(8),dp(6),dp(8),dp(6));background=outlineBg(surface,10)
                    addView(iconBubble(historyIcon(action),if(ok)teal else red),size(dp(32),dp(32)))
                    addView(column(surface).apply{
                        addView(txt(AppHistory.label(action),11.2f,ink,true).apply{maxLines=1})
                        addView(txt(timeText.format(date)+(if(mnv.isBlank())"" else "  •  MNV $mnv"),8.8f,muted,false).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
                    },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(7)})
                    addView(txt(if(ok)"Hoàn tất" else "Xem lại",8.8f,if(ok)green else red,true).apply{gravity=Gravity.END})
                    setOnClickListener{historyDetailDialog(x)}
                }
                box.addView(card,matchWrap());box.addView(gap(4));shown++
            }
            if(shown==0)box.addView(info(if(items.length()==0)"Chưa có hoạt động trên thiết bị này." else "Không có hoạt động phù hợp bộ lọc."))
        }
        filter.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{
            override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){render()}
            override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit
        }
        render();attach(root,body)
    }

    private fun historyDetailDialog(item:JSONObject){
        val action=item.optString("action");val ok=item.optBoolean("synced");val ctx=item.optJSONObject("context")?:JSONObject()
        val at=java.text.SimpleDateFormat("dd/MM/yyyy HH:mm:ss",java.util.Locale.US).format(java.util.Date(item.optLong("at")))
        val lines=mutableListOf<String>()
        lines.add("Thời gian: $at")
        lines.add("Trạng thái: ${if(ok)"Hoàn tất" else "Cần xem lại"}")
        fun add(label:String,key:String){val v=ctx.optString(key).trim();if(v.isNotBlank())lines.add("$label: $v")}
        add("MNV","mnv");add("Ca","shift");add("Vị trí trong ca","work_choice");add("PDA","pda_serial");add("User Pick","user_pick");add("Bàn Pack","pack_table");add("User Pack","user_pack");add("Công nhật","labor_type");add("Mốc thời gian","time_marker");add("Tài khoản","login_id")
        if(ctx.has("deduct_staff"))lines.add("Khấu trừ nhân sự: ${if(ctx.optBoolean("deduct_staff"))"Có" else "Không"}")
        val friendly=historyFriendlyDetail(action,item.optString("detail"),ok);if(friendly.isNotBlank())lines.add("Kết quả: $friendly")
        AlertDialog.Builder(this).setTitle(AppHistory.label(action)).setMessage(lines.joinToString("\n")).setPositiveButton("ĐÓNG",null).show()
    }

''',
    'compact tappable history',
)

# Connection copy and status header with ping.
block(
    '    private fun connectionSummary():String{',
    '    private fun headerStatusChip(',
    r'''    private fun connectionSummary():String{
        val network=when(lastConnected){true->"Tốt";false->"Mất kết nối";null->"Chưa kiểm tra"}
        val sync=when(lastConnected){true->"Sẵn sàng";false->"Đang chờ";null->"Chưa kiểm tra"}
        val ping=lastPingMs?.let{"${it}ms"}?:"—"
        return "Mạng: $network | Ping: $ping | Đồng bộ: $sync | Service: Chưa cấu hình"
    }
    private fun refreshHeaderConnection(){
        val ping=lastPingMs?.let{if(it<1000)"${it}ms" else ">1s"}
        networkStatusText?.text=when(lastConnected){true->if(ping==null)"Tốt" else "Tốt · $ping";false->"Mất";null->"—"}
        syncStatusText?.text=when(lastConnected){true->"Sẵn sàng";false->"Chờ";null->"—"}
        serviceStatusText?.text="Chưa dùng"
    }
''',
    'ping header state',
)

block(
    '    private fun headerStatusChip(',
    '    private fun appBar(',
    r'''    private fun headerStatusChip(iconRes:Int,label:String,valueView:TextView)=row(Color.TRANSPARENT).apply{
        gravity=Gravity.CENTER_VERTICAL
        setPadding(dp(6),dp(5),dp(6),dp(5))
        background=round(Color.argb(32,255,255,255),11)
        addView(ImageView(this@OperationsActivity).apply{setImageResource(iconRes);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(2),dp(2),dp(2),dp(2))},size(dp(21),dp(21)))
        addView(column(Color.TRANSPARENT).apply{
            addView(txt(label,7.2f,Color.argb(210,255,255,255),false).apply{maxLines=1})
            addView(valueView.apply{maxLines=1})
        },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(4)})
    }
''',
    'compact header chips',
)

block(
    '    private fun appBar(',
    '    private fun activeTab()',
    r'''    private fun appBar(title:String)=column(Color.TRANSPARENT).apply{
        setPadding(dp(10),dp(6),dp(10),dp(6))
        background=gradient(navy,accent,0)
        val identity=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL}
        if(!isRootScreen()){
            identity.addView(ImageView(this@OperationsActivity).apply{setImageResource(R.drawable.ic_pp_back);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(6),dp(6),dp(6),dp(6));setOnClickListener{navigateBack()}},size(dp(32),dp(32)))
        }
        identity.addView(txt("${greeting()}, ${name.ifBlank{login}}",15.0f,Color.WHITE,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END},LinearLayout.LayoutParams(0,-2,1f).apply{if(!isRootScreen())marginStart=dp(2)})
        addView(identity,matchWrap());addView(gap(6))
        val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER}
        val net=txt("—",8.6f,Color.WHITE,true);networkStatusText=net
        val syn=txt("—",8.6f,Color.WHITE,true);syncStatusText=syn
        val svc=txt("Chưa dùng",8.6f,Color.WHITE,true);serviceStatusText=svc
        statuses.addView(headerStatusChip(R.drawable.ic_pp_network,"Mạng",net),LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)})
        statuses.addView(headerStatusChip(R.drawable.ic_pp_sync,"Đồng bộ",syn),LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(1);marginEnd=dp(1)})
        statuses.addView(headerStatusChip(R.drawable.ic_pp_service,"Service",svc),LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)})
        addView(statuses,matchWrap());refreshHeaderConnection()
    }
''',
    'compact app bar',
)

# General density pass: compact balanced reusable components.
once('    private fun body()=column(bg).apply{setPadding(dp(10),dp(8),dp(10),dp(84))}\n','    private fun body()=column(bg).apply{setPadding(dp(8),dp(6),dp(8),dp(80))}\n','compact body s12')

block('    private fun businessRow(', '    private fun iconActionButton(', r'''    private fun businessRow(a:View,b:View)=row(bg).apply{
        addView(a,LinearLayout.LayoutParams(0,dp(148),1f).apply{marginEnd=dp(4)})
        addView(b,LinearLayout.LayoutParams(0,dp(148),1f).apply{marginStart=dp(4)})
    }
''','compact business row')

block('    private fun businessCard(', '    private fun employeeCard(', r'''    private fun businessCard(iconRes:Int,title:String,sub:String,click:()->Unit)=column(surface).apply{
        gravity=Gravity.CENTER_HORIZONTAL;setPadding(dp(10),dp(11),dp(10),dp(10));background=round(ThemeManager.soft(this@OperationsActivity),18);elevation=0f
        addView(businessIconBubble(iconRes),size(dp(54),dp(54)));addView(gap(7))
        addView(txt(title,13.2f,ink,true).apply{gravity=Gravity.CENTER;maxLines=2});addView(gap(4))
        addView(View(this@OperationsActivity).apply{background=round(teal,2)},size(dp(24),dp(2)));addView(gap(5))
        addView(txt(sub,9.6f,muted,false).apply{gravity=Gravity.CENTER;maxLines=1});setOnClickListener{click()}
    }
''','compact business card')

block('    private fun employeeCard(', '    private fun listCard(', '    private fun employeeCard(e:JSONObject)=column(surface).apply{setPadding(dp(10),dp(8),dp(10),dp(8));background=outlineBg(surface,11);addView(txt("${e.optString("mnv")} • ${e.optString("full_name")}",13.2f,navy,true));addView(txt("${dash(e.optString("main_position"))} • ${dash(e.optString("supplier"))}",9.5f,ink,false));addView(txt("${dash(e.optString("department"))} • Site ${dash(e.optString("site"))} • Kho ${dash(e.optString("warehouse"))}",9.1f,muted,false))}\n','compact employee card')
block('    private fun listCard(', '    private fun metric(', '    private fun listCard(title:String,sub:String)=column(surface).apply{setPadding(dp(10),dp(7),dp(10),dp(7));background=outlineBg(surface,10);addView(txt(title,11.6f,ink,true));addView(gap(1));addView(txt(sub,9.3f,muted,false))}\n','compact list card')
block('    private fun metric(', '    private fun jsonMapCard(', '    private fun metric(title:String,value:String,color:Int)=column(surface).apply{setPadding(dp(8),dp(7),dp(8),dp(7));background=outlineBg(surface,10);addView(txt(title,9.7f,color,true));addView(gap(1));addView(txt(value,11.8f,ink,true))}\n','compact metric')
block('    private fun details(', '    private fun section(', '    private fun details(items:List<Pair<String,String>>)=column(surface).apply{setPadding(dp(9),dp(6),dp(9),dp(6));background=outlineBg(surface,10);items.forEach{(k,v)->addView(row(surface).apply{addView(txt(k,9.5f,muted,false),LinearLayout.LayoutParams(0,-2,.45f));addView(txt(if(v.isBlank())"—" else v,9.7f,ink,true).apply{gravity=Gravity.END},LinearLayout.LayoutParams(0,-2,.55f));setPadding(0,dp(2),0,dp(2))})}}\n','compact details')
block('    private fun section(', '    private fun sectionIconRes(', r'''    private fun section(v:String)=row(bg).apply{
        gravity=Gravity.CENTER_VERTICAL;setPadding(0,dp(8),0,dp(3))
        addView(ImageView(this@OperationsActivity).apply{setImageResource(sectionIconRes(v));imageTintList=ColorStateList.valueOf(teal)},size(dp(20),dp(20)))
        addView(txt(v,12.2f,navy,true),LinearLayout.LayoutParams(-2,-2).apply{marginStart=dp(5)})
    }
''','compact section')
block('    private fun info(', '    private fun mnvInput(', '    private fun info(v:String)=txt(v,9.6f,muted,false).apply{setPadding(dp(10),dp(7),dp(10),dp(7));background=outlineBg(ThemeManager.soft(this@OperationsActivity),10)}\n','compact info')
block('    private fun mnvInput(', '    private fun bindScannerEnter(', r'''    private fun scanField(h:String,numeric:Boolean)=input(h,false).apply{
        setSingleLine(false);maxLines=2;setHorizontallyScrolling(false);gravity=Gravity.CENTER_VERTICAL;minHeight=dp(76);textSize=13.0f
        setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_pp_scan,0,0,0);compoundDrawableTintList=ColorStateList.valueOf(teal);compoundDrawablePadding=dp(8)
        if(numeric){inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}else{inputType=InputType.TYPE_CLASS_TEXT;imeOptions=EditorInfo.IME_ACTION_SEARCH}
    }
    private fun mnvInput(h:String)=scanField(h,true)
    private fun scanSearchInput(h:String)=scanField(h,false)
''','wrapped scanner helper')
block('    private fun input(', '    private fun labelled(', '    private fun input(h:String,password:Boolean)=EditText(this).apply{hint=h;textSize=13.0f;setTextColor(ink);setHintTextColor(Color.rgb(148,163,184));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(11),dp(8),dp(11),dp(8));minHeight=dp(46);background=outline();elevation=0f}\n','compact input')
block('    private fun labelled(', '    private fun spinner(', '    private fun labelled(l:String,v:View)=column(bg).apply{addView(txt(l,9.6f,muted,true));addView(gap(3));addView(v,matchWrap())}\n','compact labelled')
block('    private fun spinner(', '    private fun primary(', '    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@OperationsActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(9),dp(3),dp(9),dp(3));minimumHeight=dp(44);background=outline();elevation=0f}\n','compact spinner')
block('    private fun primary(', '    private fun smallButton(', '    private fun primary(t:String,c:Int,click:()->Unit)=Button(this).apply{text=t;textSize=11.5f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(46);background=gradient(c,darken(c),12);elevation=0f;setOnClickListener{click()}}\n','compact primary')

# Staff cards are the heaviest root-tab list; compact them specifically.
text = text.replace('setPadding(dp(14),dp(12),dp(12),dp(12))\n                    background=outlineBg(surface,18)', 'setPadding(dp(10),dp(8),dp(9),dp(8))\n                    background=outlineBg(surface,12)', 1)
text = text.replace('size(dp(40),dp(40))', 'size(dp(34),dp(34))', 1)
text = text.replace('marginStart=dp(9)', 'marginStart=dp(7)', 1)
text = text.replace('size(dp(38),dp(38))', 'size(dp(34),dp(34))', 2)

# Navigation consumes less vertical space while preserving usable touch targets.
block('    private fun host(content:View):View{', '    private fun jsonStrings(', r'''    private fun host(content:View):View{
        val root=EdgeSwipeBackLayout(this){navigateBack()}.apply{setBackgroundColor(bg)}
        val contentFrame=FrameLayout(this).apply{addView(content,FrameLayout.LayoutParams(-1,-1))}
        val navFrame=FrameLayout(this).apply{setPadding(dp(8),0,dp(8),0);addView(bottomNav(),FrameLayout.LayoutParams(-1,-1))}
        contentHost=contentFrame;navHost=navFrame
        root.addView(contentFrame,FrameLayout.LayoutParams(-1,-1).apply{bottomMargin=dp(86)})
        root.addView(navFrame,FrameLayout.LayoutParams(-1,dp(62),Gravity.BOTTOM).apply{bottomMargin=dp(20)})
        root.addView(txt(FOOTER,7.2f,Color.rgb(113,122,136),false).apply{gravity=Gravity.CENTER;maxLines=1},FrameLayout.LayoutParams(-1,dp(18),Gravity.BOTTOM))
        root.setOnApplyWindowInsetsListener{v,i->val top:Int;val bottom:Int;if(Build.VERSION.SDK_INT>=30){top=i.getInsets(WindowInsets.Type.statusBars()).top;bottom=i.getInsets(WindowInsets.Type.navigationBars()).bottom}else{@Suppress("DEPRECATION")val tt=i.systemWindowInsetTop;@Suppress("DEPRECATION")val bb=i.systemWindowInsetBottom;top=tt;bottom=bb};v.setPadding(0,top+dp(2),0,bottom+dp(1));i}
        root.requestApplyInsets();return root
    }
''','compact host')

# Sync detail includes the measured foreground request latency.
once(
    '                "Dữ liệu vận hành" to "Google Sheets",\n',
    '                "Dữ liệu vận hành" to "Google Sheets",\n                "Ping" to (lastPingMs?.let{"${it} ms"}?:"Chưa đo"),\n',
    'sync ping detail',
)

ops_path.write_text(text, encoding="utf-8")

# Store safe mutation context in local history. AppHistory itself whitelists keys and rejects secrets.
api_text = api_path.read_text(encoding="utf-8")
old_ok = 'if(action in tracked) AppHistory.record(appContext,action,result.ok,result.error.orEmpty())'
old_fail = 'if(action in tracked) AppHistory.record(appContext,action,false,result.error.orEmpty())'
if api_text.count(old_ok) != 1 or api_text.count(old_fail) != 1:
    raise SystemExit("S12 BetaApiClient history anchors changed")
api_text = api_text.replace(old_ok, 'if(action in tracked) AppHistory.record(appContext,action,result.ok,result.error.orEmpty(),payload)', 1)
api_text = api_text.replace(old_fail, 'if(action in tracked) AppHistory.record(appContext,action,false,result.error.orEmpty(),payload)', 1)
api_path.write_text(api_text, encoding="utf-8")

print("S12 real-PDA patch applied")

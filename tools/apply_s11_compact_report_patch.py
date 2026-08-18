#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
text = src.read_text(encoding="utf-8")


def once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"S11 patch anchor {label!r}: expected 1, got {count}")
    text = text.replace(old, new, 1)

# Inner screens: keep back navigation but remove duplicated title line under the status chips.
once('''        if(!isRootScreen() && title.isNotBlank()){
            addView(gap(10))
            addView(txt(title,15f,Color.WHITE,true).apply{setPadding(dp(1),0,0,0);maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
        }
''', '', 'hide inner title')

# Compact global spacing for PDA viewport.
once('        setPadding(dp(16),dp(12),dp(16),dp(13))\n', '        setPadding(dp(12),dp(8),dp(12),dp(8))\n', 'compact app bar')
once('    private fun body()=column(bg).apply{setPadding(dp(16),dp(15),dp(16),dp(92))}\n', '    private fun body()=column(bg).apply{setPadding(dp(10),dp(8),dp(10),dp(84))}\n', 'compact body')

# Scan/search inputs carry their own instructions; remove redundant labels outside the field.
once('''        val body=column(bg).apply{setPadding(dp(16),dp(16),dp(16),dp(92))}
        val mnv=mnvInput("Quét QR hoặc nhập MNV")
        body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(6))
''', '''        val body=column(bg).apply{setPadding(dp(10),dp(8),dp(10),dp(84))}
        val mnv=mnvInput("Scan / Nhập mã nhân viên để ghi nhận ra ca / vào ca")
        body.addView(mnv,matchWrap());body.addView(gap(4))
''', 'employee scan field')
once('''        val root=baseRoot("CÔNG NHẬT");val body=body()
        val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(5))
''', '''        val root=baseRoot("CÔNG NHẬT");val body=body()
        val mnv=mnvInput("Scan / Nhập mã nhân viên để ghi nhận công nhật").apply{setText(initialMnv)};body.addView(mnv,matchWrap());body.addView(gap(4))
''', 'labor scan field')
once('''        val root=baseRoot("TÀI NGUYÊN");val body=body()
        val mnv=mnvInput("MNV").apply{setText(initialMnv)};body.addView(labelled("Mã nhân viên",mnv));var busy=false
''', '''        val root=baseRoot("TÀI NGUYÊN");val body=body()
        val mnv=mnvInput("Scan / Nhập mã nhân viên để quản lý tài nguyên").apply{setText(initialMnv)};body.addView(mnv,matchWrap());var busy=false
''', 'resource scan field')
once('val root=baseRoot("DANH SÁCH");val body=body();val q=input("Tìm MNV / họ tên",false).apply{setSingleLine(true)};', 'val root=baseRoot("DANH SÁCH");val body=body();val q=input("Scan / Nhập mã nhân viên, họ tên để tìm kiếm",false).apply{setSingleLine(true);minHeight=dp(72)};', 'lists search field')
once('''        val q=input("Tìm mã nhân viên hoặc họ tên",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f))
''', '''        val q=input("Scan / Nhập mã nhân viên, họ tên để tìm kiếm",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH;minHeight=dp(72)}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(72),1f))
''', 'staff search field')
once('    private fun mnvInput(h:String)=input(h,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}\n', '    private fun mnvInput(h:String)=input(h,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE;minHeight=dp(72);textSize=14.2f}\n', 'large mnv input')

# Replace report screen and its old table helpers with the owner-approved shift report composition.
start = text.index('    private fun reportScreen(){')
end = text.index('    private fun historyScreen(){', start)
new_report = r'''    private fun reportScreen(){
        screenState="REPORT"
        val root=baseRoot("BÁO CÁO")
        val body=column(bg).apply{setPadding(dp(4),dp(5),dp(4),dp(38))}
        val period=spinner(arrayOf("Ca 1 + Ca HC","Ca 2","Cả ngày")).apply{minimumHeight=dp(44)}
        body.addView(period,matchWrap());body.addView(gap(4))
        val box=column(bg);body.addView(box,matchWrap());box.addView(txt("Đang tải báo cáo...",10.2f,muted,false))
        var reportJson:JSONObject?=null
        var sessions=JSONArray()
        var labor=JSONArray()
        var reportReady=false
        var sessionsReady=false
        var laborReady=!isAdmin()
        fun renderIfReady(){
            if(!reportReady||!sessionsReady||!laborReady)return
            box.removeAllViews()
            val key=when(period.selectedItemPosition){0->"ca1_hc";1->"ca2";else->"all"}
            renderShiftReport(box,reportJson?:JSONObject(),sessions,labor,key)
        }
        period.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{
            override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderIfReady()}
            override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit
        }
        api.call("report_daily"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            reportReady=true
            if(!r.ok){box.removeAllViews();box.addView(info(r.error?:"Không tải được báo cáo"));return@runOnUiThread}
            reportJson=r.json?:JSONObject();renderIfReady()
        }}
        api.call("list_sessions",JSONObject()){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            sessions=if(r.ok)r.json?.optJSONArray("items")?:JSONArray() else JSONArray()
            sessionsReady=true;renderIfReady()
        }}
        if(isAdmin())api.call("list_labor"){r->runOnUiThread{
            if(handleAuth(r))return@runOnUiThread
            labor=if(r.ok)r.json?.optJSONArray("items")?:JSONArray() else JSONArray()
            laborReady=true;renderIfReady()
        }}
        attach(root,body)
    }

    private fun renderShiftReport(box:LinearLayout,rootJson:JSONObject,sessions:JSONArray,labor:JSONArray,key:String){
        val p=rootJson.optJSONObject("reports")?.optJSONObject(key)?:JSONObject()
        val allowed=when(key){"ca1_hc"->setOf("Ca 1","Ca HC");"ca2"->setOf("Ca 2");else->setOf("Ca 1","Ca HC","Ca 2")}
        val columns=reportColumns(sessions,allowed,p.optJSONObject("manpower")?.optJSONArray("columns"))
        box.addView(manpowerReportTable(p.optJSONObject("manpower"),columns),matchWrap())
        box.addView(gap(7))
        val picker=buildTenureMatrix(sessions,labor,allowed,"PICK",columns)
        val packer=buildTenureMatrix(sessions,labor,allowed,"PACK",columns)
        box.addView(reportMatrixTable("Thâm niên Picker",picker,columns,Color.rgb(222,239,247)),matchWrap())
        box.addView(gap(7))
        box.addView(reportMatrixTable("Thâm niên Packer",packer,columns,Color.rgb(226,242,224)),matchWrap())
        val support=buildSupportMatrix(sessions,labor,allowed,columns)
        if(isAdmin()&&support.optInt("total")>0){
            box.addView(gap(7))
            box.addView(reportMatrixTable("Hỗ trợ bộ phận khác",support,columns,Color.rgb(255,235,211)),matchWrap())
            box.addView(gap(8))
            val pn=picker.optJSONArray("rows")?.optJSONObject(0)?.optInt("total")?:0
            val po=picker.optJSONArray("rows")?.optJSONObject(1)?.optInt("total")?:0
            val kn=packer.optJSONArray("rows")?.optJSONObject(0)?.optInt("total")?:0
            val ko=packer.optJSONArray("rows")?.optJSONObject(1)?.optInt("total")?:0
            box.addView(txt("Sau khi trừ nhân sự hỗ trợ bộ phận khác, thực tế team còn:",10.4f,ink,true))
            box.addView(gap(3))
            box.addView(txt("• ${pn+po} picker (gồm $po người cũ và $pn người mới)\n• ${kn+ko} packer (gồm $ko người cũ và $kn người mới)",10.2f,ink,false))
        }
    }

    private fun reportColumns(sessions:JSONArray,allowed:Set<String>,fallback:JSONArray?):MutableList<String>{
        val order=listOf("IH","NLV","VW","MP","MGL","HGP","HAD")
        val seen=linkedSetOf<String>()
        for(i in 0 until sessions.length()){
            val s=sessions.optJSONObject(i)?:continue
            if(!allowed.contains(s.optString("shift")))continue
            val e=s.optJSONObject("employee_snapshot")?:MasterDataCache.employee(this,s.optString("mnv"))?:JSONObject()
            val c=reportSupplierCode(e.optString("supplier"));if(c.isNotBlank())seen.add(c)
        }
        val fb=jsonStrings(fallback);fb.forEach{if(it.isNotBlank())seen.add(it)}
        return order.filter{seen.contains(it)}.toMutableList().apply{seen.filter{!order.contains(it)}.forEach{add(it)}}
    }

    private fun reportSupplierCode(v:String):String=when(foldLocal(v)){
        "INHOUSE"->"IH";"NGUON LUC VIET"->"NLV";"VIET WORK"->"VW";"MAN POWER"->"MP";"MEGA LINK"->"MGL";"HA GIA PHAT"->"HGP";"HOA ANH DAO"->"HAD";else->""
    }
    private fun reportColumnLabel(v:String)=if(v=="IH")"Inhouse" else v
    private fun reportTenureDays(v:String):Long=runCatching{
        val f=java.time.format.DateTimeFormatter.ofPattern("dd/MM/yyyy")
        val start=java.time.LocalDate.parse(v.trim(),f)
        java.time.temporal.ChronoUnit.DAYS.between(start,java.time.LocalDate.now()).coerceAtLeast(0)
    }.getOrDefault(99999L)

    private fun deductedMnvs(labor:JSONArray):Set<String>{
        val out=linkedSetOf<String>()
        for(i in 0 until labor.length()){
            val l=labor.optJSONObject(i)?:continue
            if(l.optBoolean("deduct_staff")){val mnv=l.optString("mnv");if(mnv.isNotBlank())out.add(mnv)}
        }
        return out
    }

    private fun buildTenureMatrix(sessions:JSONArray,labor:JSONArray,allowed:Set<String>,work:String,columns:List<String>):JSONObject{
        val deducted=deductedMnvs(labor)
        val rows=arrayOf(JSONObject().put("label","Nhân sự mới").put("counts",JSONObject()).put("total",0),JSONObject().put("label","Nhân sự cũ").put("counts",JSONObject()).put("total",0))
        columns.forEach{c->rows.forEach{it.getJSONObject("counts").put(c,0)}}
        for(i in 0 until sessions.length()){
            val s=sessions.optJSONObject(i)?:continue
            val mnv=s.optString("mnv")
            if(!allowed.contains(s.optString("shift"))||s.optString("work_choice")!=work||deducted.contains(mnv))continue
            val e=s.optJSONObject("employee_snapshot")?:MasterDataCache.employee(this,mnv)?:JSONObject()
            val c=reportSupplierCode(e.optString("supplier"));if(c.isBlank()||!columns.contains(c))continue
            val ix=if(reportTenureDays(e.optString("start_date"))<=30)0 else 1
            val counts=rows[ix].getJSONObject("counts");counts.put(c,counts.optInt(c)+1);rows[ix].put("total",rows[ix].optInt("total")+1)
        }
        return JSONObject().put("rows",JSONArray().put(rows[0]).put(rows[1])).put("total",rows[0].optInt("total")+rows[1].optInt("total"))
    }

    private fun buildSupportMatrix(sessions:JSONArray,labor:JSONArray,allowed:Set<String>,columns:List<String>):JSONObject{
        val sessionByMnv=mutableMapOf<String,JSONObject>()
        for(i in 0 until sessions.length()){val s=sessions.optJSONObject(i)?:continue;sessionByMnv[s.optString("mnv")]=s}
        val rowMap=linkedMapOf<String,JSONObject>();val seen=mutableSetOf<String>()
        for(i in 0 until labor.length()){
            val l=labor.optJSONObject(i)?:continue
            if(!l.optBoolean("deduct_staff"))continue
            val mnv=l.optString("mnv");val s=sessionByMnv[mnv]?:continue
            if(!allowed.contains(s.optString("shift")))continue
            val type=l.optString("labor_type").ifBlank{"Khác"};val dedupe="$type|$mnv";if(!seen.add(dedupe))continue
            val e=s.optJSONObject("employee_snapshot")?:MasterDataCache.employee(this,mnv)?:JSONObject();val c=reportSupplierCode(e.optString("supplier"));if(c.isBlank()||!columns.contains(c))continue
            val row=rowMap.getOrPut(type){JSONObject().put("label",type).put("counts",JSONObject()).put("total",0).also{r->columns.forEach{x->r.getJSONObject("counts").put(x,0)}}}
            val counts=row.getJSONObject("counts");counts.put(c,counts.optInt(c)+1);row.put("total",row.optInt("total")+1)
        }
        val rows=JSONArray();rowMap.values.sortedBy{it.optString("label")}.forEach{rows.put(it)}
        var total=0;for(i in 0 until rows.length())total+=rows.optJSONObject(i)?.optInt("total")?:0
        return JSONObject().put("rows",rows).put("total",total)
    }

    private fun reportCell(v:String,header:Boolean=false,first:Boolean=false,highlight:Boolean=false,total:Boolean=false):TextView=TextView(this).apply{
        text=v;textSize=if(header)8.4f else 8.6f;setTextColor(if(header||total)navy else ink);typeface=if(header||first||total)Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        gravity=if(first)Gravity.START or Gravity.CENTER_VERTICAL else Gravity.CENTER
        setPadding(dp(4),dp(4),dp(3),dp(4));maxLines=3
        background=GradientDrawable().apply{setColor(when{highlight->Color.rgb(255,250,92);header||total->Color.rgb(220,235,239);else->Color.WHITE});setStroke(dp(1),Color.rgb(105,118,126))}
    }
    private fun reportAddCell(row:TableRow,view:TextView,first:Boolean=false){row.addView(view,TableRow.LayoutParams(0,-2,if(first)2.75f else 1f))}

    private fun manpowerReportTable(data:JSONObject?,columns:List<String>):View{
        val table=TableLayout(this).apply{isStretchAllColumns=false;isShrinkAllColumns=true}
        val head=TableRow(this);reportAddCell(head,reportCell("Vị trí",true,true),true);columns.forEach{reportAddCell(head,reportCell(reportColumnLabel(it),true))};reportAddCell(head,reportCell("Tổng",true));table.addView(head)
        val rows=data?.optJSONArray("rows")?:JSONArray();val byLabel=mutableMapOf<String,JSONObject>()
        for(i in 0 until rows.length()){val r=rows.optJSONObject(i)?:continue;byLabel[r.optString("position")]=r}
        val fixed=listOf("Trưởng nhóm","Chuyên viên","Tổ trưởng","Điều phối khu pack","Điều phối khu chờ xuất","Kéo hàng","5S","Picker","Packer","Phúc Long")
        val extras=mutableListOf<String>();for(i in 0 until rows.length()){val l=rows.optJSONObject(i)?.optString("position").orEmpty();if(l.isNotBlank()&&!fixed.contains(l))extras.add(l)}
        (fixed+extras).forEach{label->
            val r=byLabel[label]?:JSONObject();val counts=r.optJSONObject("counts")?:JSONObject();val tr=TableRow(this);val hi=label=="Phúc Long"
            reportAddCell(tr,reportCell(label,false,true,hi),true);columns.forEach{c->val n=counts.optInt(c);reportAddCell(tr,reportCell(if(n==0)"" else n.toString(),highlight=hi))};val total=r.optInt("total");reportAddCell(tr,reportCell(if(total==0)"" else total.toString(),highlight=hi,total=total>0));table.addView(tr)
        }
        val totals=data?.optJSONObject("totals")?:JSONObject();val tr=TableRow(this);reportAddCell(tr,reportCell("Tổng",header=true,first=true,total=true),true);columns.forEach{c->val n=totals.optInt(c);reportAddCell(tr,reportCell(if(n==0)"" else n.toString(),header=true,total=true))};val total=data?.optInt("total")?:0;reportAddCell(tr,reportCell(if(total==0)"" else total.toString(),header=true,total=true));table.addView(tr)
        return table
    }

    private fun reportMatrixTable(title:String,data:JSONObject,columns:List<String>,headerColor:Int):View{
        val table=TableLayout(this).apply{isStretchAllColumns=false;isShrinkAllColumns=true}
        fun cell(v:String,header:Boolean=false,first:Boolean=false,total:Boolean=false)=reportCell(v,header,first,false,total).apply{if(header)background=GradientDrawable().apply{setColor(headerColor);setStroke(dp(1),Color.rgb(105,118,126))}}
        val head=TableRow(this);reportAddCell(head,cell(title,true,true),true);columns.forEach{reportAddCell(head,cell(reportColumnLabel(it),true))};reportAddCell(head,cell("Tổng",true));table.addView(head)
        val rows=data.optJSONArray("rows")?:JSONArray();for(i in 0 until rows.length()){val r=rows.optJSONObject(i)?:continue;val tr=TableRow(this);reportAddCell(tr,cell(r.optString("label"),first=true),true);val counts=r.optJSONObject("counts")?:JSONObject();columns.forEach{c->val n=counts.optInt(c);reportAddCell(tr,cell(if(n==0)"" else n.toString()))};val total=r.optInt("total");reportAddCell(tr,cell(if(total==0)"" else total.toString(),total=total>0));table.addView(tr)}
        return table
    }

'''
text = text[:start] + new_report + text[end:]

if 'S11_COMPACT_REPORT_PATCH' not in text:
    text = text.replace('package vn.pickpack1291.app.beta\n', 'package vn.pickpack1291.app.beta\n\n// S11_COMPACT_REPORT_PATCH: compact inner screens and bordered shift reports.\n', 1)
src.write_text(text, encoding="utf-8")
print(f"Applied S11 compact/report patch: {src}")

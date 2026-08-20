#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
s=OPS.read_text(encoding='utf-8')
MARK='S34D_COMPILE_FIXES'
if MARK in s:
    print('S34D already applied')
    raise SystemExit(0)

# Kotlin lexer can read the adjacent generic close + expression body as >=.
s=s.replace('fun statusPalette(status:String):Triple<Int,Int,Int>=when(status){','fun statusPalette(status:String):Triple<Int,Int,Int> = when(status){')

# S33 no longer leaves the legacy reportGrid helper in the transformed source.
# Keep S34C self-contained with a dedicated compact grid renderer.
s=s.replace('reportGrid("",makeGrid(selected,"position"),"Vị trí","position")','s34ReportGrid("",makeGrid(selected,"position"),"Vị trí","position")')
s=s.replace('reportGrid("",makeGrid(selected,"tenure"),"Thâm niên","label")','s34ReportGrid("",makeGrid(selected,"tenure"),"Thâm niên","label")')

anchor='    private fun historyScreen(){'
if anchor not in s:
    raise SystemExit('S34D history anchor missing')
helper=r'''    // S34D_COMPILE_FIXES: compact renderer owned by the Site 1291 local report.
    private fun s34ReportGrid(title:String,data:JSONObject?,firstTitle:String,rowKey:String):View{
        val wrap=column(surface).apply{setPadding(dp(1),dp(2),dp(1),dp(2));setBackgroundColor(surface)}
        if(title.isNotBlank())wrap.addView(txt(title,11f,navy,true).apply{gravity=Gravity.CENTER;setPadding(0,0,0,dp(3))})
        if(data==null){wrap.addView(txt("Chưa có dữ liệu",10f,muted,false));return wrap}
        val cols=jsonStrings(data.optJSONArray("columns"));val rows=data.optJSONArray("rows")?:JSONArray()
        val table=TableLayout(this).apply{isStretchAllColumns=true;isShrinkAllColumns=true}
        fun cell(v:String,bold:Boolean=false,header:Boolean=false)=TextView(this).apply{
            text=v;textSize=if(header)8.2f else 8.5f;setTextColor(if(header)navy else ink);typeface=if(bold)Typeface.DEFAULT_BOLD else Typeface.DEFAULT;gravity=Gravity.CENTER;setPadding(dp(1),dp(3),dp(1),dp(3));maxLines=3;background=GradientDrawable().apply{setColor(if(header)Color.rgb(232,241,246) else Color.WHITE)}
        }
        val hr=TableRow(this);hr.addView(cell(firstTitle,true,true));cols.forEach{hr.addView(cell(it,true,true))};hr.addView(cell("Tổng",true,true));table.addView(hr)
        for(i in 0 until rows.length()){
            val row=rows.optJSONObject(i)?:continue;val tr=TableRow(this);tr.addView(cell(row.optString(rowKey),true));val counts=row.optJSONObject("counts")?:JSONObject();cols.forEach{c->val n=counts.optInt(c);tr.addView(cell(if(n==0)"" else n.toString()))};val total=row.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true));table.addView(tr)
        }
        val totals=data.optJSONObject("totals")
        if(totals!=null){val tr=TableRow(this);tr.addView(cell("Tổng",true,true));cols.forEach{c->val n=totals.optInt(c);tr.addView(cell(if(n==0)"" else n.toString(),true,true))};val total=data.optInt("total");tr.addView(cell(if(total==0)"" else total.toString(),true,true));table.addView(tr)}
        wrap.addView(table,matchWrap());return wrap
    }

'''
s=s.replace(anchor,helper+anchor,1)
OPS.write_text(s,encoding='utf-8')

ops=OPS.read_text(encoding='utf-8')
for x in [MARK,'private fun s34ReportGrid','Triple<Int,Int,Int> = when(status)','s34ReportGrid("",makeGrid(selected,"position"']:
    if x not in ops: raise SystemExit('S34D contract missing: '+x)
if 'reportGrid("",makeGrid(selected,' in ops: raise SystemExit('S34D unresolved legacy reportGrid reference remains')
print('Applied S34D compile fixes: history palette + Site 1291 report grid')

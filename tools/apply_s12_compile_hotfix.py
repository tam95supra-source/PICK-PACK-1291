#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
text=path.read_text(encoding="utf-8")

bad="HorizontalScrollView(this).apply{isHorizontalScrollBarEnabled=true;fillViewport=false;addView(table,ViewGroup.LayoutParams(-2,-2))}"
good="HorizontalScrollView(this).apply{isHorizontalScrollBarEnabled=true;isFillViewport=false;addView(table,ViewGroup.LayoutParams(-2,-2))}"
if text.count(bad)!=1:
    raise SystemExit(f"S12 hotfix scroll anchor expected 1, got {text.count(bad)}")
text=text.replace(bad,good,1)

if text.count("    private fun businessRow(")!=0 or text.count("    private fun iconActionButton(")!=0:
    raise SystemExit("S12 hotfix expected deleted businessRow/iconActionButton helpers")
anchor="    private fun employeeCard("
if text.count(anchor)!=1:
    raise SystemExit(f"S12 hotfix employeeCard anchor expected 1, got {text.count(anchor)}")
helpers='''    private fun businessRow(a:View,b:View)=row(bg).apply{\n        addView(a,LinearLayout.LayoutParams(0,dp(148),1f).apply{marginEnd=dp(4)})\n        addView(b,LinearLayout.LayoutParams(0,dp(148),1f).apply{marginStart=dp(4)})\n    }\n    private fun iconActionButton(res:Int,color:Int,desc:String,click:()->Unit)=FrameLayout(this).apply{\n        contentDescription=desc\n        background=round(ThemeManager.soft(this@OperationsActivity),10)\n        setOnClickListener{click()}\n        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(8),dp(8),dp(8),dp(8))},FrameLayout.LayoutParams(-1,-1))\n    }\n\n'''
text=text.replace(anchor,helpers+anchor,1)
path.write_text(text,encoding="utf-8")
print("S12 compile hotfix applied")

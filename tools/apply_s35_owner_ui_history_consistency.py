#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S35_OWNER_UI_HISTORY_CONSISTENCY'


def replace_private_fun(src: str, signature: str, replacement: str) -> str:
    start=src.find('    private fun '+signature)
    if start<0:
        raise SystemExit('S35 function anchor missing: '+signature)
    end=src.find('\n    private fun ',start+16)
    if end<0:
        raise SystemExit('S35 next function anchor missing after: '+signature)
    return src[:start]+replacement.rstrip()+'\n'+src[end:]

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S35 already applied')
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# History canonical refresh state. History remains local-first, but when the
# tab opens (or a realtime revision changes), pull changed canonical day
# snapshots immediately so every PDA converges on the same Service/D1 view.
# ---------------------------------------------------------------------------
field_anchor='    private var lastProjectionPending: Int = 0\n'
if field_anchor not in s:
    raise SystemExit('S35 history refresh field anchor missing')
s=s.replace(field_anchor,field_anchor+'    private var historySyncInFlight=false // '+MARK+'\n    private var historyLastCanonicalRefreshAt=0L\n',1)

status_old='''                when (screenState) {
                    "LISTS" -> listsScreen()
                    "REPORT" -> reportScreen()
                }'''
status_new='''                when (screenState) {
                    "LISTS" -> listsScreen()
                    "REPORT" -> reportScreen()
                    "HISTORY" -> { historyLastCanonicalRefreshAt=0L; refreshHistoryCanonical() }
                }'''
if status_old not in s:
    raise SystemExit('S35 foreground history refresh anchor missing')
s=s.replace(status_old,status_new,1)

# ---------------------------------------------------------------------------
# Nghiệp vụ: no redundant heading/instruction, unique purpose icons, owner
# order, and USER-visible-but-disabled admin functions.
# ---------------------------------------------------------------------------
business=r'''    // S35_OWNER_UI_HISTORY_CONSISTENCY: owner-ordered business menu and explicit role gating.
    private fun businessHome(){
        module="BUSINESS";screenState="BUSINESS"
        val root=baseRoot("NGHIỆP VỤ");val body=body()
        val cards=listOf(
            businessCard(R.drawable.ic_pp_scan,"Quét nhân sự","Vào ca / ra ca theo trạng thái hiện tại",true){employeeScan()},
            businessCard(R.drawable.ic_pp_pda_exchange,"Đổi / trả PDA","Đổi PDA có lý do hoặc trả PDA đang sử dụng",true){pdaExchangeScreen()},
            businessCard(R.drawable.ic_pp_drop_receive,"Nhận hàng Rớt","Tiếp nhận nghiệp vụ hàng rớt",true){TopNotice.show(this,"Nhận hàng Rớt đang được chuẩn bị.",TopNotice.Kind.INFO)},
            businessCard(R.drawable.ic_pp_report,"Báo cáo nhân sự","Báo cáo nhân sự Site 1291",isAdmin()){reportScreen()},
            businessCard(R.drawable.ic_pp_task,"Công nhật","Bắt đầu / hoàn thành công nhật",isAdmin()){laborHome()},
            businessCard(R.drawable.ic_pp_resource,"Tài nguyên","Quản lý PDA • User Pick • Bàn Pack • User Pack",isAdmin()){resourceHome()},
            businessCard(R.drawable.ic_pp_ccdc,"Quản lý CCDC","Quản lý công cụ dụng cụ",isAdmin()){TopNotice.show(this,"Quản lý CCDC đang được chuẩn bị.",TopNotice.Kind.INFO)}
        )
        body.addView(businessRow(cards[0],cards[1]));body.addView(gap(9))
        body.addView(businessRow(cards[2],cards[3]));body.addView(gap(9))
        body.addView(businessRow(cards[4],cards[5]));body.addView(gap(9))
        body.addView(businessRow(cards[6],Space(this)))
        attach(root,body)
    }'''
s=replace_private_fun(s,'businessHome(){',business)

# Card text can wrap instead of being clipped. Disabled role cards remain
# visible as requested but are dimmed and not clickable.
business_card=r'''    private fun businessCard(iconRes:Int,title:String,sub:String,enabled:Boolean=true,click:()->Unit)=column(surface).apply{
        gravity=Gravity.CENTER_HORIZONTAL
        setPadding(dp(12),dp(14),dp(12),dp(12))
        background=outlineBg(surface,20)
        elevation=if(enabled)dp(5).toFloat() else 0f
        alpha=if(enabled)1f else .38f
        isEnabled=enabled
        addView(businessIconBubble(iconRes),size(dp(58),dp(58)))
        addView(gap(9))
        addView(txt(title,13.5f,ink,true).apply{gravity=Gravity.CENTER;maxLines=2;ellipsize=android.text.TextUtils.TruncateAt.END})
        addView(gap(5))
        addView(View(this@OperationsActivity).apply{background=round(teal,2)},size(dp(28),dp(3)))
        addView(gap(6))
        addView(txt(sub,9.8f,muted,false).apply{
            gravity=Gravity.CENTER
            maxLines=3
            ellipsize=android.text.TextUtils.TruncateAt.END
            setAutoSizeTextTypeUniformWithConfiguration(8,10,1,android.util.TypedValue.COMPLEX_UNIT_SP)
        },LinearLayout.LayoutParams(-1,0,1f))
        if(enabled)setOnClickListener{click()} else setOnClickListener(null)
    }'''
s=replace_private_fun(s,'businessCard(iconRes:Int,title:String,sub:String,click:()->Unit)=',business_card)

business_row=r'''    private fun businessRow(a:View,b:View)=row(bg).apply{
        addView(a,LinearLayout.LayoutParams(0,dp(188),1f).apply{marginEnd=dp(6)})
        addView(b,LinearLayout.LayoutParams(0,dp(188),1f).apply{marginStart=dp(6)})
    }'''
s=replace_private_fun(s,'businessRow(a:View,b:View)=',business_row)

# Give the three new menu operations their own visual identity instead of
# inheriting the generic resource/task gradient bucket.
old_colors='''        val colors=when(res){
            R.drawable.ic_pp_scan->intArrayOf(teal,accent)
            R.drawable.ic_pp_task->intArrayOf(Color.rgb(37,99,235),Color.rgb(14,165,233))
            R.drawable.ic_pp_report->intArrayOf(Color.rgb(124,58,237),Color.rgb(168,85,247))
            else->intArrayOf(Color.rgb(6,182,212),Color.rgb(14,165,233))
        }'''
new_colors='''        val colors=when(res){
            R.drawable.ic_pp_scan->intArrayOf(teal,accent)
            R.drawable.ic_pp_pda_exchange->intArrayOf(Color.rgb(2,132,199),Color.rgb(14,165,233))
            R.drawable.ic_pp_drop_receive->intArrayOf(Color.rgb(234,88,12),Color.rgb(249,115,22))
            R.drawable.ic_pp_report->intArrayOf(Color.rgb(124,58,237),Color.rgb(168,85,247))
            R.drawable.ic_pp_task->intArrayOf(Color.rgb(37,99,235),Color.rgb(14,165,233))
            R.drawable.ic_pp_resource->intArrayOf(Color.rgb(5,150,105),Color.rgb(16,185,129))
            R.drawable.ic_pp_ccdc->intArrayOf(Color.rgb(71,85,105),Color.rgb(100,116,139))
            else->intArrayOf(Color.rgb(6,182,212),Color.rgb(14,165,233))
        }'''
if old_colors not in s:
    raise SystemExit('S35 business icon palette anchor missing')
s=s.replace(old_colors,new_colors,1)

# ---------------------------------------------------------------------------
# Nhân sự: search + add stay pinned; only the result list scrolls. Remove the
# redundant "Mã nhân viên" label from cards/search copy. Password policy stays
# enforced server-side, but explanatory parentheticals are removed from UI.
# ---------------------------------------------------------------------------
staff=r'''    private fun staffScreen(){
        module="STAFF";screenState="STAFF"
        val root=baseRoot("NHÂN SỰ")
        val searchRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL}
        val q=input("Tìm mã, họ tên hoặc số điện thoại",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f))
        if(isAdmin()){searchRow.addView(gap(8));searchRow.addView(iconActionButton(R.drawable.ic_pp_add,teal,"Thêm nhân sự"){staffEditor(null)},size(dp(50),dp(50)))}
        val pinned=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(8));addView(searchRow,matchWrap())}
        root.addView(pinned,matchWrap())
        val listBody=column(bg).apply{setPadding(dp(16),dp(3),dp(16),dp(92))}
        val box=column(bg);listBody.addView(box,matchWrap());var pageSize=60
        fun render(query:String){
            box.removeAllViews();val clean=query.trim();val limit=if(clean.isBlank())pageSize else 180;val arr=MasterDataCache.searchStaff(this,clean,limit)
            for(i in 0 until arr.length()){
                val e=arr.optJSONObject(i)?:continue
                val card=column(surface).apply{
                    setPadding(dp(14),dp(12),dp(12),dp(12));background=outlineBg(surface,18);elevation=dp(2).toFloat()
                    val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                    top.addView(iconBubble(R.drawable.ic_pp_staff,teal),size(dp(40),dp(40)))
                    top.addView(column(surface).apply{
                        addView(txt(e.optString("full_name"),14f,ink,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
                        addView(txt(e.optString("phone").ifBlank{"Chưa có số điện thoại"},10.4f,ink,false))
                        addView(txt("${e.optString("mnv")} – ${dash(e.optString("main_position"))}",11.1f,navy,true))
                        addView(txt("${dash(e.optString("supplier"))} - ${dash(e.optString("department"))} - ${dash(e.optString("site"))}",9.8f,muted,false).apply{maxLines=2})
                    },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(9)})
                    if(isAdmin()){
                        top.addView(iconActionButton(R.drawable.ic_pp_edit,teal,"Sửa"){staffEditor(e)},size(dp(38),dp(38)))
                        if(isSuper()){top.addView(Space(this@OperationsActivity),size(dp(5),1));top.addView(iconActionButton(R.drawable.ic_pp_delete,red,"Xóa"){confirmDeleteStaff(e)},size(dp(38),dp(38)))}
                    }
                    addView(top,matchWrap())
                }
                box.addView(card,matchWrap());box.addView(gap(8))
            }
            if(arr.length()==0)box.addView(info("Không có nhân sự phù hợp."))
            if(clean.isBlank()&&arr.length()>=pageSize&&pageSize<MasterDataCache.staffCount(this))box.addView(primary("XEM THÊM",teal){pageSize+=60;render("")}.apply{textSize=10.5f},matchWrap())
        }
        q.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(v:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(v:CharSequence?,st:Int,b:Int,c:Int){render(v?.toString().orEmpty())};override fun afterTextChanged(v:Editable?)=Unit})
        q.setOnEditorActionListener{_,_,_->render(q.text.toString());true}
        render("")
        root.addView(ScrollView(this).apply{addView(listBody)},LinearLayout.LayoutParams(-1,0,1f))
        setScreen(root)
    }'''
s=replace_private_fun(s,'staffScreen(){',staff)

s=s.replace('Mật khẩu mới (tối thiểu 8 ký tự)','Mật khẩu mới')
s=s.replace('Mật khẩu ban đầu (>=8 ký tự)','Mật khẩu ban đầu')

# ---------------------------------------------------------------------------
# History: local rows render first. Then perform a bounded canonical catch-up
# off the UI thread. A short cooldown prevents recursive refresh loops.
# ---------------------------------------------------------------------------
history_anchor='    private fun historyScreen(){'
if history_anchor not in s:
    raise SystemExit('S35 historyScreen anchor missing')
history_helper=r'''    private fun refreshHistoryCanonical(){
        if(historySyncInFlight)return
        val now=System.currentTimeMillis();if(now-historyLastCanonicalRefreshAt<1500L)return
        historySyncInFlight=true
        Thread{
            val ok=runCatching{M2BackgroundSync.catchUp(applicationContext)}.getOrDefault(false)
            runOnUiThread{
                historySyncInFlight=false
                historyLastCanonicalRefreshAt=System.currentTimeMillis()
                if(ok&&screenState=="HISTORY")historyScreen()
            }
        }.start()
    }

'''
s=s.replace(history_anchor,history_helper+history_anchor,1)

history_tail='        render();foregroundSync.requestSync();attach(root,body)'
if history_tail not in s:
    raise SystemExit('S35 history tail anchor missing')
s=s.replace(history_tail,'        render();attach(root,body);refreshHistoryCanonical()',1)

# Detail title = code – full name. Remove the explanatory timeline sentence.
timeline_old='''        screenState="HISTORY_DETAIL";val root=baseRoot("LỊCH SỬ");val body=body();val first=items.firstOrNull()?:return;val mnv=first.optString("mnv");body.addView(section(if(mnv.isBlank())"Chi tiết thao tác" else "Mã nhân viên $mnv"));body.addView(info("Dòng thời gian trong đúng phiên. Thời gian thao tác hệ thống/Event ID chỉ đọc, không chỉnh sửa."));body.addView(gap(8))'''
timeline_new='''        screenState="HISTORY_DETAIL";val root=baseRoot("LỊCH SỬ");val body=body();val first=items.firstOrNull()?:return;val mnv=first.optString("mnv");val full=first.optString("full_name").ifBlank{MasterDataCache.employee(this,mnv)?.optString("full_name").orEmpty()};val detailTitle=if(mnv.isBlank())"Chi tiết thao tác" else listOf(mnv,full).filter{it.isNotBlank()}.joinToString(" – ");body.addView(section(detailTitle));body.addView(gap(8))'''
if timeline_old not in s:
    raise SystemExit('S35 history timeline title anchor missing')
s=s.replace(timeline_old,timeline_new,1)

OPS.write_text(s,encoding='utf-8')

# Fail closed on the exact owner-request contracts.
o=OPS.read_text(encoding='utf-8')
checks=[
    MARK,
    'R.drawable.ic_pp_pda_exchange',
    'R.drawable.ic_pp_drop_receive',
    'R.drawable.ic_pp_ccdc',
    'businessCard(R.drawable.ic_pp_report,"Báo cáo nhân sự","Báo cáo nhân sự Site 1291",isAdmin())',
    'alpha=if(enabled)1f else .38f',
    'maxLines=3',
    'val pinned=column(bg)',
    'Tìm mã, họ tên hoặc số điện thoại',
    'refreshHistoryCanonical()',
    'M2BackgroundSync.catchUp(applicationContext)',
    'joinToString(" – ")',
]
for x in checks:
    if x not in o: raise SystemExit('S35 contract missing: '+x)
for forbidden in ['Nghiệp vụ vận hành','Chọn nghiệp vụ cần xử lý trên PDA.','Dòng thời gian trong đúng phiên.','Mật khẩu mới (tối thiểu 8 ký tự)','Mật khẩu ban đầu (>=8 ký tự)']:
    if forbidden in o: raise SystemExit('S35 forbidden UI copy remains: '+forbidden)
print('Applied S35: role-gated business menu, pinned staff search, canonical History catch-up and text overflow fixes')

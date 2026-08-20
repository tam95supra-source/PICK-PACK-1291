#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
MARK='S38_ATTENDANCE_UI'


def replace_fun(src:str,signature:str,replacement:str)->str:
    a=src.find('    private fun '+signature)
    if a<0: raise SystemExit('S38 function anchor missing: '+signature)
    b=src.find('\n    private fun ',a+20)
    if b<0: raise SystemExit('S38 next function anchor missing: '+signature)
    return src[:a]+replacement.rstrip()+'\n'+src[b:]

s=P.read_text(encoding='utf-8')
if MARK in s:
    print('S38 Android already applied');raise SystemExit(0)

load=r'''    // S38_ATTENDANCE_UI: render staff identity immediately, then use current Service session/resource options.
    private fun loadEmployee(mnv: String, button: Button? = null) {
        val cached=MasterDataCache.employee(this,mnv)
        if(cached!=null&&screenState=="SCAN")renderCachedEmployee(cached)
        api.call("employee_context",JSONObject().put("mnv",mnv).put("include_options",true).put("include_labor",false)){result->runOnUiThread{
            button?.isEnabled=true
            if(result.code==401){sessionExpired();return@runOnUiThread}
            if(!result.ok){showError(result.error?:"Không kiểm tra được mã nhân viên");return@runOnUiThread}
            val ctx=result.json?:JSONObject();val options=ctx.optJSONObject("options")?:MasterDataCache.resourceOptions(this@OperationsActivity)
            renderEmployee(ctx,options)
        }}
    }'''
s=replace_fun(s,'loadEmployee(mnv: String, button: Button? = null) {',load)

employee=r'''    private fun renderEmployee(ctx: JSONObject, masters: JSONObject?) {
        screenState="EMPLOYEE"
        val e=ctx.optJSONObject("employee")?:JSONObject();val state=ctx.optString("state");val currentMnv=e.optString("mnv");liveEmployeeMnv=currentMnv
        val root=column(bg);root.addView(appBar("QUÉT QR NHÂN SỰ"));val body=column(bg).apply{setPadding(dp(16),dp(12),dp(16),dp(58))}
        val scan=mnvInput("Quét QR hoặc nhập mã nhân viên").apply{setText("")}
        body.addView(labelled("Mã nhân viên",scan));body.addView(gap(9));body.addView(employeeCard(e));body.addView(gap(10))
        var busy=false
        fun submit(){val v=scan.text.toString().trim();if(v.isBlank()){TopNotice.show(this,"Nhập hoặc quét mã nhân viên.",TopNotice.Kind.WARNING);return};if(busy)return;busy=true;loadEmployee(v);scan.postDelayed({busy=false},600)}
        bindScannerEnter(scan){submit()}
        when(state){"ACTIVE"->renderActive(body,ctx);"ENDED"->renderEnded(body,ctx);else->renderEnter(body,ctx,masters?:JSONObject())}
        root.addView(ScrollView(this).apply{addView(body)},LinearLayout.LayoutParams(-1,0,1f));setScreen(root);scan.requestFocus()
    }'''
s=replace_fun(s,'renderEmployee(ctx: JSONObject, masters: JSONObject?) {',employee)

active=r'''    private fun renderActive(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();val mnv=ses.optString("mnv");val pda=ses.optString("pda_serial");val initialStatus=ses.optString("pda_enter_status");val resourceNote=ses.optString("resource_note")
        body.addView(section("PHÂN CÔNG TRONG CA"));body.addView(details(listOf(
            "Ca" to ses.optString("shift"),"Vị trí đang làm" to workText(ses.optString("work_choice")),"Vào lúc" to formatIso(ses.optString("enter_at")),
            "Seri PDA" to dash(pda),"Tình trạng PDA lúc vào" to dash(initialStatus),"User Pick" to dash(ses.optString("user_pick")),"Bàn Pack" to dash(ses.optString("pack_table")),"User Pack" to dash(ses.optString("user_pack")),"Ghi chú tài nguyên" to dash(resourceNote)
        )));body.addView(gap(11))
        val exit=primary("RA CA",red){}
        fun callExit(statusNow:String){exit.isEnabled=false;exit.text="ĐANG RA CA...";val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv);if(statusNow.isNotBlank())payload.put("pda_exit_status",statusNow);api.call("exit",payload){r->runOnUiThread{exit.isEnabled=true;exit.text="RA CA";if(!r.ok)showError(r.error?:"RA CA thất bại")else loadEmployee(mnv)}}}
        exit.setOnClickListener{
            if(pda.isBlank()){
                AlertDialog.Builder(this).setTitle("Xác nhận RA CA").setMessage("Phiên này không sử dụng PDA. Xác nhận kết thúc phiên hôm nay?").setNegativeButton("Hủy",null).setPositiveButton("RA CA"){_,_->callExit("")}.show();return@setOnClickListener
            }
            if(initialStatus.isBlank()){
                showError("PDA_ENTRY_STATUS_MISSING_NOTIFY_SPECIALIST");return@setOnClickListener
            }
            val statuses=mutableListOf<String>();val arr=ctx.optJSONObject("options")?.optJSONArray("pda_statuses")?:JSONArray();for(i in 0 until arr.length()){val v=arr.optString(i).trim();if(v.isNotBlank()&&!statuses.contains(v))statuses.add(v)};if(!statuses.contains(initialStatus))statuses.add(0,initialStatus)
            val sp=spinner(statuses.toTypedArray());val wrap=column(surface).apply{setPadding(dp(16),dp(6),dp(16),dp(4));addView(txt("PDA: $pda",11f,navy,true));addView(gap(5));addView(txt("Tình trạng lúc vào: $initialStatus",10.2f,muted,false));addView(gap(9));addView(labelled("Xác nhận tình trạng PDA hiện tại",sp))}
            AlertDialog.Builder(this).setTitle("Xác nhận tình trạng PDA").setView(wrap).setNegativeButton("Hủy",null).setPositiveButton("KIỂM TRA & RA CA"){_,_->val now=sp.selectedItem?.toString().orEmpty();if(now!=initialStatus){showError("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST")}else callExit(now)}.show()
        }
        body.addView(exit,matchWrap())
    }'''
s=replace_fun(s,'renderActive(body: LinearLayout, ctx: JSONObject) {',active)

ended=r'''    private fun renderEnded(body: LinearLayout, ctx: JSONObject) {
        val ses=ctx.optJSONObject("session")?:JSONObject();body.addView(section("PHIÊN HÔM NAY"));body.addView(details(listOf("Ca" to ses.optString("shift"),"Vị trí trong ca" to workText(ses.optString("work_choice")),"Vào lúc" to formatIso(ses.optString("enter_at")),"Ra lúc" to formatIso(ses.optString("exit_at")),"PDA" to dash(ses.optString("pda_serial")),"User Pick" to dash(ses.optString("user_pick")),"Bàn Pack" to dash(ses.optString("pack_table")),"User Pack" to dash(ses.optString("user_pack")))))
    }'''
s=replace_fun(s,'renderEnded(body: LinearLayout, ctx: JSONObject) {',ended)

enter=r'''    private fun renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {
        val e=ctx.optJSONObject("employee")?:JSONObject();val mnv=e.optString("mnv")
        body.addView(section("PHÂN CÔNG TRONG CA"))
        val now=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh"));var shiftValue=when{now.isBefore(java.time.LocalTime.of(8,0))->"Ca 1";now.isBefore(java.time.LocalTime.of(10,0))->"Ca HC";else->"Ca 2"}
        var workValue=when{e.optString("main_position").trim().equals("Pick",true)->"PICK";e.optString("main_position").trim().equals("Pack",true)->"PACK";else->"KHONG"}
        val resourceBox=column(bg);val shiftBox=column(bg);val workBox=column(bg)
        var rebuildResources:(()->Unit)?=null
        shiftBox.addView(segmentedChoice(listOf("Ca 1" to "Ca 1","Ca HC" to "Ca HC","Ca 2" to "Ca 2"),shiftValue){shiftValue=it;rebuildResources?.invoke()},matchWrap())
        workBox.addView(segmentedChoice(listOf("Không" to "KHONG","Pick" to "PICK","Pack" to "PACK"),workValue){workValue=it;rebuildResources?.invoke()},matchWrap())
        body.addView(labelled("Ca",shiftBox));body.addView(gap(9));body.addView(labelled("Vị trí trong ca",workBox));body.addView(gap(8));body.addView(resourceBox,matchWrap())

        val pdas=masters.optJSONArray("pdas")?:JSONArray();val picks=masters.optJSONArray("user_picks")?:JSONArray();val pickReissue=masters.optJSONArray("user_picks_reissue")?:JSONArray();val packs=masters.optJSONArray("pack_tables")?:JSONArray();val packReissue=masters.optJSONArray("pack_tables_reissue")?:JSONArray()
        var pdaField:AutoCompleteTextView?=null;var pickSpinner:Spinner?=null;var pickChoices=mutableListOf<Pair<String,Boolean>>();var packSelection:JSONObject?=null;var allowDuplicate=false

        fun renderPick(){
            pdaField=pdaInput(pdas);resourceBox.addView(labelled("Seri PDA — gõ 5 số cuối",pdaField!!));resourceBox.addView(gap(5));resourceBox.addView(info("Chọn gợi ý để hiện đầy đủ Seri PDA và Tình trạng. Có thể ấn lại vào ô PDA để gõ 5 số cuối khác."));resourceBox.addView(gap(8))
            pickChoices=mutableListOf("" to false);val labels=mutableListOf("Không dùng User Pick");for(i in 0 until picks.length()){val id=picks.optString(i).trim();if(id.isNotBlank()){pickChoices.add(id to false);labels.add(id)}}
            if(allowDuplicate)for(i in 0 until pickReissue.length()){val o=pickReissue.optJSONObject(i)?:continue;val id=o.optString("id").trim();if(id.isNotBlank()){pickChoices.add(id to true);labels.add("⚠ $id • TRÙNG USER")}}
            pickSpinner=spinner(labels.toTypedArray());resourceBox.addView(labelled("User Pick",pickSpinner!!));resourceBox.addView(gap(7));val reissue=smallButton(if(allowDuplicate)"ẨN USER TRÙNG" else "PHÁT LẠI USER ĐANG DÙNG",orange).apply{isEnabled=pickReissue.length()>0;alpha=if(isEnabled)1f else .45f;setOnClickListener{allowDuplicate=!allowDuplicate;rebuildResources?.invoke()}};resourceBox.addView(reissue,matchWrap());if(allowDuplicate)resourceBox.addView(txt("⚠ User phát lại sẽ được ghi chú TRÙNG USER trong phiên.",9.6f,orange,true))
        }
        fun renderPack(){
            val rows=mutableListOf<JSONObject>();for(i in 0 until packs.length()){val o=packs.optJSONObject(i)?:continue;if(o.optString("shift")==shiftValue)rows.add(JSONObject(o.toString()).put("duplicate_user",false))};if(allowDuplicate)for(i in 0 until packReissue.length()){val o=packReissue.optJSONObject(i)?:continue;if(o.optString("shift")==shiftValue)rows.add(JSONObject(o.toString()).put("duplicate_user",true))}
            val tables=rows.map{it.optString("table")}.filter{it.isNotBlank()}.distinct();val tableSp=spinner((if(tables.isEmpty())listOf("Không có bàn Pack khả dụng")else tables).toTypedArray());resourceBox.addView(labelled("Bàn Pack",tableSp));resourceBox.addView(gap(8));val userHost=column(bg);resourceBox.addView(userHost,matchWrap())
            fun renderUsers(){userHost.removeAllViews();packSelection=null;if(tables.isEmpty()){userHost.addView(info("Không có User Pack khả dụng cho ca đã chọn."));return};val table=tables.getOrNull(tableSp.selectedItemPosition).orEmpty();val mapped=rows.filter{it.optString("table")==table};val labels=mapped.map{if(it.optBoolean("duplicate_user"))"⚠ ${it.optString("user_pack")} • TRÙNG USER" else it.optString("user_pack")};val userSp=spinner((if(labels.isEmpty())listOf("Không có User Pack")else labels).toTypedArray());if(mapped.isNotEmpty())packSelection=mapped[0];userSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){packSelection=mapped.getOrNull(pos)};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};userHost.addView(labelled("User Pack theo bàn",userSp));if(mapped.any{it.optBoolean("duplicate_user")})userHost.addView(txt("⚠ Mục có TRÙNG USER chỉ xuất hiện khi bật Phát lại User đang dùng.",9.5f,orange,true))}
            tableSp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){renderUsers()};override fun onNothingSelected(p:android.widget.AdapterView<*>?)=Unit};renderUsers();resourceBox.addView(gap(7));resourceBox.addView(smallButton(if(allowDuplicate)"ẨN USER TRÙNG" else "PHÁT LẠI USER ĐANG DÙNG",orange).apply{isEnabled=packReissue.length()>0;alpha=if(isEnabled)1f else .45f;setOnClickListener{allowDuplicate=!allowDuplicate;rebuildResources?.invoke()}},matchWrap());if(allowDuplicate)resourceBox.addView(txt("⚠ User phát lại sẽ được ghi chú TRÙNG USER trong phiên.",9.6f,orange,true))
        }
        rebuildResources={resourceBox.removeAllViews();pdaField=null;pickSpinner=null;pickChoices.clear();packSelection=null;when(workValue){"PICK"->renderPick();"PACK"->renderPack();else->Unit}}
        rebuildResources?.invoke();body.addView(gap(12))
        val enterBtn=primary("VÀO CA",teal){}
        enterBtn.setOnClickListener{
            val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",mnv).put("shift",shiftValue).put("work_choice",workValue)
            if(workValue=="PICK"){
                val raw=pdaField?.text?.toString().orEmpty();if(!raw.contains("Tình trạng:")){showError("Hãy gõ 5 số cuối và chọn PDA trong danh sách gợi ý.");return@setOnClickListener};val p=resolvePdaObject(pdas,raw);if(p==null){showError("PDA không còn hợp lệ. Chọn lại PDA.");return@setOnClickListener};payload.put("pda_serial",p.optString("serial")).put("pda_status_at_enter",p.optString("status"));val picked=pickChoices.getOrNull(pickSpinner?.selectedItemPosition?:0)?:("" to false);if(picked.first.isNotBlank())payload.put("user_pick",picked.first);if(picked.second)payload.put("duplicate_user",true).put("resource_note","TRÙNG USER")
            }
            if(workValue=="PACK"){
                val row=packSelection;if(row==null){showError("Chọn Bàn Pack và User Pack hợp lệ.");return@setOnClickListener};payload.put("pack_table",row.optString("table")).put("user_pack",row.optString("user_pack"));if(row.optBoolean("duplicate_user"))payload.put("duplicate_user",true).put("resource_note","TRÙNG USER")
            }
            enterBtn.isEnabled=false;enterBtn.text="ĐANG VÀO CA...";api.call("enter",payload){r->runOnUiThread{enterBtn.isEnabled=true;enterBtn.text="VÀO CA";if(!r.ok)showError(r.error?:"VÀO CA thất bại")else loadEmployee(mnv)}}
        }
        body.addView(enterBtn,matchWrap())
    }'''
s=replace_fun(s,'renderEnter(body: LinearLayout, ctx: JSONObject, masters: JSONObject) {',enter)

# Replace PDA input helpers and add equal-width segmented controls. This also fixes the lost last-5 autocomplete.
pda_start=s.find('    private fun pdaInput(')
pda_end=s.find('    private fun input(',pda_start)
if pda_start<0 or pda_end<0: raise SystemExit('S38 PDA helper anchors missing')
helpers=r'''    private fun segmentedChoice(items:List<Pair<String,String>>,initial:String,onChanged:(String)->Unit):LinearLayout{
        val host=row(bg);val buttons=mutableListOf<Button>();var selected=initial
        fun paint(){buttons.forEachIndexed{i,b->val on=items[i].second==selected;b.setTextColor(if(on)Color.WHITE else navy);b.background=if(on)gradient(teal,darken(teal),12) else outlineBg(surface,12);b.elevation=if(on)dp(2).toFloat() else 0f}}
        items.forEachIndexed{i,item->val b=Button(this).apply{text=item.first;textSize=10.5f;isAllCaps=false;typeface=Typeface.DEFAULT_BOLD;minHeight=dp(46);setPadding(dp(3),0,dp(3),0);setOnClickListener{selected=item.second;paint();onChanged(selected)}};buttons.add(b);host.addView(b,LinearLayout.LayoutParams(0,dp(46),1f).apply{if(i>0)marginStart=dp(3);if(i<items.lastIndex)marginEnd=dp(3)})};paint();return host
    }
    private fun resolvePdaObject(pdas:JSONArray,rawValue:String):JSONObject?{
        val raw=rawValue.trim();val candidate=raw.substringBefore(" • ").trim();val hits=mutableListOf<JSONObject>();for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};if(serial.isBlank())continue;if(candidate==serial||candidate==last5||(raw.contains(serial)&&raw.contains("Tình trạng:")))hits.add(p)};return hits.distinctBy{it.optString("serial")}.singleOrNull()
    }
    private fun pdaInput(pdas:JSONArray,currentSerial:String=""):AutoCompleteTextView{
        val labels=mutableListOf<String>();var currentLabel="";for(i in 0 until pdas.length()){val p=pdas.optJSONObject(i)?:continue;val serial=p.optString("serial").trim();val last5=p.optString("last5").trim().ifBlank{serial.takeLast(5)};val status=p.optString("status").trim();if(serial.isBlank()||last5.isBlank())continue;val suggestion="$last5 • $serial • Tình trạng: ${status.ifBlank{"—"}}";labels.add(suggestion);if(serial==currentSerial)currentLabel="$serial • Tình trạng: ${status.ifBlank{"—"}}"}
        return AutoCompleteTextView(this).apply{hint="Gõ 5 số cuối Seri PDA";threshold=1;textSize=13f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=InputType.TYPE_CLASS_TEXT;setPadding(dp(13),dp(10),dp(13),dp(10));minHeight=dp(50);background=outline();setAdapter(ArrayAdapter(this@OperationsActivity,android.R.layout.simple_dropdown_item_1line,labels));setOnItemClickListener{parent,_,pos,_->val label=parent.getItemAtPosition(pos).toString();val serial=label.substringAfter(" • ").substringBefore(" • ").trim();val status=label.substringAfter("Tình trạng:","—").trim();setText("$serial • Tình trạng: $status",false);setSelection(text.length)};setOnClickListener{if(text.contains(" • Tình trạng:")){val serial=text.toString().substringBefore(" • ").trim();val last=serial.takeLast(5);setText(last,false);setSelection(text.length)};showDropDown()};if(currentLabel.isNotBlank())setText(currentLabel,false)}
    }
    private fun resolvePda(pdas:JSONArray,rawValue:String):String?=resolvePdaObject(pdas,rawValue)?.optString("serial")?.takeIf{it.isNotBlank()}
'''
s=s[:pda_start]+helpers+s[pda_end:]

# Explicit user-facing errors for the two safety fences.
err='val msg=when{'
if err not in s: raise SystemExit('S38 showError anchor missing')
s=s.replace(err,'val msg=when{raw.contains("PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST")->"Tình trạng PDA hiện tại không khớp lúc vào ca. Không thể RA CA. Phải thông báo cho Chuyên viên sự việc.";raw.contains("PDA_ENTRY_STATUS_MISSING_NOTIFY_SPECIALIST")->"Không xác định được tình trạng PDA lúc vào ca. Không thể RA CA. Phải thông báo cho Chuyên viên sự việc.";raw.contains("PDA_ENTRY_STATUS_STALE")->"Tình trạng PDA vừa thay đổi trên hệ thống. Chọn lại PDA trước khi VÀO CA.";raw.contains("DUPLICATE_USER_OVERRIDE_NOT_REQUIRED")->"User này hiện không thuộc nhóm đang dùng/đã dùng; hãy chọn từ danh sách thường.";',1)

P.write_text(s,encoding='utf-8')
o=P.read_text(encoding='utf-8')
for x in [MARK,'PHÁT LẠI USER ĐANG DÙNG','TRÙNG USER','PDA_STATUS_MISMATCH_NOTIFY_SPECIALIST','Tình trạng PDA lúc vào','segmentedChoice','Ca HC','pack_tables_reissue','user_picks_reissue','Tình trạng:','pda_status_at_enter','pda_exit_status']:
    if x not in o: raise SystemExit('S38 UI contract missing: '+x)
# Attendance card itself must no longer inject old state badges/buttons.
ra=o[o.find('    private fun renderActive('):o.find('    private fun renderEnded(')]
re=o[o.find('    private fun renderEnter('):o.find('    private fun laborHome(')]
if 'ĐANG TRONG PHIÊN' in ra or 'CHƯA VÀO CA' in re or 'QUÉT / NHẬP' in o[o.find('    private fun renderEmployee('):o.find('    private fun renderActive(')]:
    raise SystemExit('S38 old attendance status/switch button remains')
print('Applied S38 attendance UI: scan field, 3-button assignment, PDA autocomplete/status, duplicate-user reissue, safe exit')

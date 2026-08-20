#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
WORKER=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/M2OutboxWorker.kt'
MARK='S33_OWNER_UI_SYNC_RESOURCES'

def replace_fun(src,start_name,next_name,new_text):
    start=src.find(f'    private fun {start_name}')
    end=src.find(f'    private fun {next_name}',start)
    if start<0 or end<0: raise SystemExit(f'S33 function anchors missing: {start_name}->{next_name}')
    return src[:start]+new_text.rstrip()+"\n\n"+src[end:]

# Project-wide Android timezone/display normalization. Business date-only fields stay dd/MM/yyyy.
for p in (ROOT/'app/src/main/java/vn/pickpack1291/app/beta').glob('*.kt'):
    s=p.read_text(encoding='utf-8')
    s=s.replace('Asia/Bangkok','Asia/Ho_Chi_Minh')
    s=s.replace('dd/MM/yyyy HH:mm:ss','HH:mm:ss dd/MM/yyyy')
    s=s.replace('dd/MM HH:mm:ss','HH:mm:ss dd/MM/yyyy')
    p.write_text(s,encoding='utf-8')

s=OPS.read_text(encoding='utf-8')
if MARK not in s:
    s=s.replace('    private var lastConnected: Boolean? = null\n','    private var lastConnected: Boolean? = null\n    private var lastSyncLatencyMs: Long? = null // '+MARK+'\n    private var lastProjectionPending: Int = 0\n',1)
    s=s.replace('                lastConnected = status.connected\n','                lastConnected = status.connected\n                lastSyncLatencyMs = status.latencyMs\n                lastProjectionPending = status.projectionPending.coerceAtLeast(0)\n',1)
    s=s.replace('        if (api.token != null) foregroundSync.start()','        PpForegroundGate.enter()\n        if (api.token != null) foregroundSync.start()',1)
    s=s.replace('        foregroundSync.stop()\n        super.onStop()','        PpForegroundGate.leave()\n        foregroundSync.stop()\n        super.onStop()',1)
    s=s.replace('            "SYNC"->syncScreen()\n            else->{module="BUSINESS";businessHome()}','            "SYNC"->syncScreen()\n            "PDA_EXCHANGE"->pdaExchangeScreen()\n            else->{module="BUSINESS";businessHome()}',1)
    # User-facing terminology only; mixed-case Mnv identifiers are untouched.
    s=s.replace('MNV','Mã nhân viên')

    resource=r'''    private fun resourceHome(){
        screenState="RESOURCE_HOME"
        val root=baseRoot("TÀI NGUYÊN");val body=body()
        body.addView(info("Quản lý danh mục tài nguyên dùng chung. USER được xem; ADMIN/SUPERADMIN được thêm, sửa, xóa và cập nhật tình trạng."));body.addView(gap(10))
        val cards=listOf(
            Triple("PDA","DANH SÁCH PDA","Seri / tình trạng"),
            Triple("USER_PICK","DANH SÁCH USER PICK","User Pick / tình trạng"),
            Triple("PACK_TABLE","DANH SÁCH BÀN PACK","Bàn Pack / tình trạng"),
            Triple("USER_PACK","DANH SÁCH USER PACK","User Pack / bàn liên kết")
        )
        cards.chunked(2).forEach{pair->
            val row=businessRow(
                businessCard(R.drawable.ic_pp_resource,pair[0].second,pair[0].third){resourceListScreen(pair[0].first,pair[0].second)},
                if(pair.size>1)businessCard(R.drawable.ic_pp_resource,pair[1].second,pair[1].third){resourceListScreen(pair[1].first,pair[1].second)} else Space(this)
            );body.addView(row);body.addView(gap(10))
        }
        attach(root,body)
    }

    private fun resourceListScreen(type:String,title:String){
        screenState="RESOURCE_LIST"
        val root=baseRoot(title);val body=body();val box=column(bg)
        body.addView(info("Dữ liệu lấy từ Service/D1 và được đồng bộ về đúng sheet nguồn. Không tự phát sinh giá trị tình trạng ngoài Danh mục."));body.addView(gap(8))
        if(isAdmin()){body.addView(primary("THÊM TÀI NGUYÊN",teal){resourceEditDialog(type,null,null,null)},matchWrap());body.addView(gap(8))}
        body.addView(box,matchWrap());box.addView(info("Đang tải danh sách..."))
        api.call("resource_master_list"){r->runOnUiThread{
            box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được tài nguyên"));return@runOnUiThread}
            val all=r.json?.optJSONArray("resources")?:JSONArray();val catalogs=r.json?.optJSONArray("catalogs")?:JSONArray();val rows=mutableListOf<JSONObject>()
            for(i in 0 until all.length()){val x=all.optJSONObject(i)?:continue;if(x.optString("resource_type")==type)rows.add(x)}
            if(rows.isEmpty())box.addView(info("Chưa có dữ liệu."))
            rows.forEach{x->
                val meta=runCatching{JSONObject(x.optString("metadata_json","{}"))}.getOrDefault(JSONObject())
                val detail=mutableListOf<String>();val it=meta.keys();while(it.hasNext()){val k=it.next();val v=meta.optString(k);if(v.isNotBlank()&&v!=x.optString("resource_id"))detail.add("$k: $v")}
                val card=column(surface).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(surface,14)
                    addView(txt(x.optString("resource_id"),14f,navy,true));addView(gap(3));addView(txt("Tình trạng: ${x.optString("status_label").ifBlank{"—"}}",10.3f,if(x.optInt("available")!=0)green else muted,true));if(detail.isNotEmpty())addView(txt(detail.joinToString(" • "),9.7f,muted,false).apply{maxLines=3})
                    if(isAdmin()){addView(gap(7));val actions=row(surface);actions.addView(smallButton("SỬA",teal).apply{setOnClickListener{resourceEditDialog(type,x,catalogs,all)}},LinearLayout.LayoutParams(0,dp(40),1f).apply{marginEnd=dp(3)});actions.addView(smallButton("XÓA",red).apply{setOnClickListener{confirmDeleteResource(type,x.optString("resource_id"),title)}},LinearLayout.LayoutParams(0,dp(40),1f).apply{marginStart=dp(3)});addView(actions,matchWrap())}
                };box.addView(card,matchWrap());box.addView(gap(7))
            }
        }}
        attach(root,body)
    }

    private fun resourceStatusValues(type:String,catalogs:JSONArray?):MutableList<String>{
        val ns=when(type){"PDA"->"DANH SÁCH PDA_Tình trạng";"USER_PICK"->"DANH SÁCH USER PICK_Tình trạng";"PACK_TABLE"->"DANH SÁCH BÀN PACK_Tình trạng";else->"DANH SÁCH USER PACK_Tình trạng"}
        val out=mutableListOf<String>();if(catalogs!=null)for(i in 0 until catalogs.length()){val x=catalogs.optJSONObject(i)?:continue;if(x.optString("namespace")==ns&&x.optString("value").isNotBlank())out.add(x.optString("value"))}
        if(out.isEmpty())out.addAll(catalogValues(ns));return out.distinct().toMutableList()
    }

    private fun resourceEditDialog(type:String,existing:JSONObject?,catalogs:JSONArray?,all:JSONArray?){
        if(!isAdmin())return
        val meta=runCatching{JSONObject(existing?.optString("metadata_json","{}")?:"{}")}.getOrDefault(JSONObject());val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val id=input("Mã / tên tài nguyên",false).apply{setText(existing?.optString("resource_id").orEmpty());isEnabled=existing==null}
        val statuses=resourceStatusValues(type,catalogs);val statusSp=spinner((if(statuses.isEmpty())listOf("Hoạt động")else statuses).toTypedArray());selectByValue(statusSp,statuses,existing?.optString("status_label").orEmpty())
        val note=input("Ghi chú",false).apply{setText(meta.optString("Ghi chú").ifBlank{meta.optString("note")})}
        val extra1=input(when(type){"PDA"->"5 số cuối Seri";"USER_PICK"->"Số User";"USER_PACK"->"Tên bàn pack";else->""},false)
        val extra2=input(if(type=="USER_PACK")"Nhãn User pack (ví dụ CA 1-...)" else "",false)
        if(type=="PDA")extra1.setText(meta.optString("5 số cuối Seri"));if(type=="USER_PICK")extra1.setText(meta.optString("Số User"));if(type=="USER_PACK"){extra1.setText(meta.optString("Tên bàn pack").ifBlank{meta.optString("pack_table")});extra2.setText(meta.optString("User pack").ifBlank{meta.optString("label")})}
        fun add(l:String,v:View){if(l.isBlank())return;box.addView(txt(l,10.2f,ink,true));box.addView(gap(4));box.addView(v,matchWrap());box.addView(gap(8))}
        add("Mã / tên tài nguyên",id);add("Tình trạng",statusSp);if(type!="PACK_TABLE")add(extra1.hint?.toString().orEmpty(),extra1);if(type=="USER_PACK")add(extra2.hint?.toString().orEmpty(),extra2);add("Ghi chú",note)
        AlertDialog.Builder(this).setTitle(if(existing==null)"Thêm tài nguyên" else "Sửa tài nguyên").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->
            val key=id.text.toString().trim();if(key.isBlank()){showError("Mã tài nguyên là bắt buộc.");return@setPositiveButton}
            val m=JSONObject().put("Ghi chú",note.text.toString().trim())
            when(type){"PDA"->{val last=extra1.text.toString().trim().ifBlank{key.takeLast(5)};if(last.length!=5||!last.all{it.isDigit()}){showError("5 số cuối Seri phải gồm đúng 5 chữ số.");return@setPositiveButton};m.put("Seri PDA",key).put("5 số cuối Seri",last)};"USER_PICK"->m.put("User Pick",key).put("Số User",extra1.text.toString().trim());"USER_PACK"->{val table=extra1.text.toString().trim();if(table.isBlank()){showError("Tên bàn pack là bắt buộc cho User Pack.");return@setPositiveButton};m.put("Tên bàn pack",table).put("User Pack",key).put("User pack",extra2.text.toString().trim())};"PACK_TABLE"->m.put("Tên bàn pack",key)}
            val p=JSONObject().put("operation","UPSERT").put("resource_type",type).put("resource_id",key).put("status_label",statusSp.selectedItem?.toString().orEmpty()).put("metadata",m).put("idempotency_key",UUID.randomUUID().toString())
            api.call("resource_master_upsert",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không lưu được tài nguyên")else{TopNotice.show(this,"Đã cập nhật tài nguyên.",TopNotice.Kind.SUCCESS);resourceListScreen(type,when(type){"PDA"->"DANH SÁCH PDA";"USER_PICK"->"DANH SÁCH USER PICK";"PACK_TABLE"->"DANH SÁCH BÀN PACK";else->"DANH SÁCH USER PACK"})}}}
        }.show()
    }

    private fun confirmDeleteResource(type:String,id:String,title:String){
        if(!isAdmin())return
        AlertDialog.Builder(this).setTitle("Xóa tài nguyên?").setMessage("Xóa $id khỏi $title? Tài nguyên đang được sử dụng sẽ bị hệ thống chặn xóa.").setNegativeButton("Hủy",null).setPositiveButton("XÓA"){_,_->
            api.call("resource_master_delete",JSONObject().put("operation","DELETE").put("resource_type",type).put("resource_id",id).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không xóa được tài nguyên")else{TopNotice.show(this,"Đã xóa tài nguyên.",TopNotice.Kind.SUCCESS);resourceListScreen(type,title)}}}
        }.show()
    }'''
    s=replace_fun(s,'resourceHome(){','staffScreen(){',resource)

    staff=r'''    private fun staffScreen(){
        module="STAFF";screenState="STAFF"
        val root=baseRoot("NHÂN SỰ");val body=body();val searchRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};val q=input("Tìm mã nhân viên, họ tên hoặc số điện thoại",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f));if(isAdmin()){searchRow.addView(gap(8));searchRow.addView(iconActionButton(R.drawable.ic_pp_add,teal,"Thêm nhân sự"){staffEditor(null)},size(dp(50),dp(50)))};body.addView(searchRow,matchWrap());body.addView(gap(11));val box=column(bg);body.addView(box,matchWrap());var pageSize=60
        fun render(query:String){box.removeAllViews();val clean=query.trim();val limit=if(clean.isBlank())pageSize else 180;val arr=MasterDataCache.searchStaff(this,clean,limit)
            for(i in 0 until arr.length()){val e=arr.optJSONObject(i)?:continue;val card=column(surface).apply{setPadding(dp(14),dp(12),dp(12),dp(12));background=outlineBg(surface,18);elevation=dp(2).toFloat();val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};top.addView(iconBubble(R.drawable.ic_pp_staff,teal),size(dp(40),dp(40)));top.addView(column(surface).apply{addView(txt(e.optString("full_name"),14f,ink,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END});addView(txt(e.optString("phone").ifBlank{"Chưa có số điện thoại"},10.4f,ink,false));addView(txt("Mã nhân viên ${e.optString("mnv")} – ${dash(e.optString("main_position"))}",11.1f,navy,true));addView(txt("${dash(e.optString("supplier"))} - ${dash(e.optString("department"))} - ${dash(e.optString("site"))}",9.8f,muted,false).apply{maxLines=2})},LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(9)});if(isAdmin()){top.addView(iconActionButton(R.drawable.ic_pp_edit,teal,"Sửa"){staffEditor(e)},size(dp(38),dp(38)));if(isSuper()){top.addView(Space(this@OperationsActivity),size(dp(5),1));top.addView(iconActionButton(R.drawable.ic_pp_delete,red,"Xóa"){confirmDeleteStaff(e)},size(dp(38),dp(38)))}};addView(top,matchWrap())};box.addView(card,matchWrap());box.addView(gap(8))}
            if(arr.length()==0)box.addView(info("Không có nhân sự phù hợp."));if(clean.isBlank()&&arr.length()>=pageSize&&pageSize<MasterDataCache.staffCount(this)){box.addView(primary("XEM THÊM",teal){pageSize+=60;render("")},matchWrap())}}
        q.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(v:CharSequence?,s:Int,c:Int,a:Int)=Unit;override fun onTextChanged(v:CharSequence?,s:Int,b:Int,c:Int){render(v?.toString().orEmpty())};override fun afterTextChanged(v:Editable?)=Unit});q.setOnEditorActionListener{_,_,_->render(q.text.toString());true};render("");attach(root,body)
    }'''
    s=replace_fun(s,'staffScreen(){','staffEditor(existing:JSONObject?){',staff)

    staffeditor=r'''    private fun staffEditor(existing:JSONObject?){
        if(!isAdmin())return
        if(existing!=null){val code=input("Mã xác nhận 4 số",true).apply{inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789")};AlertDialog.Builder(this).setTitle("Xác nhận quyền sửa").setMessage("Nhập mã 4 số theo giờ Việt Nam hiện tại (HHmm). Ví dụ 07:42 → 0742.").setView(code).setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->val expected=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HHmm"));if(code.text.toString()!=expected){showError("Mã xác nhận không đúng.")}else staffEditorUnlocked(existing)}.show();return}
        staffEditorUnlocked(null)
    }

    private fun staffEditorUnlocked(existing:JSONObject?){
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val mnv=mnvInput("Mã nhân viên").apply{setText(existing?.optString("mnv").orEmpty());isEnabled=existing==null};val full=input("Họ và tên",false).apply{setText(existing?.optString("full_name").orEmpty())};val phone=input("Số điện thoại",false).apply{setText(existing?.optString("phone").orEmpty());inputType=InputType.TYPE_CLASS_PHONE;keyListener=DigitsKeyListener.getInstance("0123456789")}
        val pos=catalogSpinner("DANH SÁCH NHÂN SỰ_Vị trí chính",existing?.optString("main_position").orEmpty(),true);val supplier=catalogSpinner("DANH SÁCH NHÂN SỰ_Nhà cung cấp",existing?.optString("supplier").orEmpty(),true);val department=catalogSpinner("DANH SÁCH NHÂN SỰ_Bộ phận",existing?.optString("department").orEmpty(),true);val site=catalogSpinner("DANH SÁCH NHÂN SỰ_Site",existing?.optString("site").orEmpty(),true);val warehouse=catalogSpinner("DANH SÁCH NHÂN SỰ_Kho",existing?.optString("warehouse").orEmpty(),true)
        val startDate=input("Chọn ngày bắt đầu",false).apply{setText(existing?.optString("start_date").orEmpty());isFocusable=false;isClickable=true};startDate.setOnClickListener{val now=java.time.LocalDate.now(ZoneId.of("Asia/Ho_Chi_Minh"));val parts=startDate.text.toString().split("/");val d=parts.getOrNull(0)?.toIntOrNull()?:now.dayOfMonth;val m=(parts.getOrNull(1)?.toIntOrNull()?:now.monthValue)-1;val y=parts.getOrNull(2)?.toIntOrNull()?:now.year;android.app.DatePickerDialog(this,{_,yy,mm,dd->startDate.setText(String.format(java.util.Locale.US,"%02d/%02d/%04d",dd,mm+1,yy))},y,m,d).show()};val note=input("Ghi chú",false).apply{setText(existing?.optString("note").orEmpty())}
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))};addField("Mã nhân viên",mnv);addField("Họ và tên",full);addField("Số điện thoại",phone);addField("Vị trí chính",pos);addField("Nhà cung cấp",supplier);addField("Bộ phận",department);addField("Site",site);addField("Kho",warehouse);addField("Ngày bắt đầu làm việc",startDate);addField("Ghi chú",note)
        val dialog=AlertDialog.Builder(this).setTitle(if(existing==null)"Thêm nhân sự" else "Sửa nhân sự").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU",null).create();dialog.setOnShowListener{dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{val id=mnv.text.toString().trim();val nm=full.text.toString().trim();val ph=phone.text.toString().trim();val sd=startDate.text.toString().trim();if(id.isBlank()||!id.all{it.isDigit()}){showError("Mã nhân viên là bắt buộc và chỉ gồm chữ số.");return@setOnClickListener};if(nm.isBlank()){showError("Họ và tên là bắt buộc.");return@setOnClickListener};if(!Regex("^0[0-9]{9}$").matches(ph)){showError("Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.");return@setOnClickListener};if(!Regex("^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/([0-9]{4})$").matches(sd)){showError("Ngày bắt đầu làm việc chưa hợp lệ.");return@setOnClickListener};val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("full_name",nm).put("phone",ph).put("main_position",catalogSelection(pos)).put("supplier",catalogSelection(supplier)).put("department",catalogSelection(department)).put("site",catalogSelection(site)).put("warehouse",catalogSelection(warehouse)).put("start_date",sd).put("note",note.text.toString());api.call("staff_upsert",payload){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không lưu được nhân sự")else{dialog.dismiss();reloadMaster{TopNotice.show(this,"Đã lưu nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}}}}}};dialog.show()
    }'''
    s=replace_fun(s,'staffEditor(existing:JSONObject?){','confirmDeleteStaff(employee:JSONObject){',staffeditor)

    delete=r'''    private fun confirmDeleteStaff(employee:JSONObject){
        if(!isSuper()){showError("Chỉ SUPERADMIN được xóa nhân sự.");return}
        AlertDialog.Builder(this).setTitle("Xóa nhân sự?").setMessage("Xóa Mã nhân viên ${employee.optString("mnv")} • ${employee.optString("full_name")}? Lịch sử nghiệp vụ đã phát sinh vẫn được giữ.").setNegativeButton("KHÔNG",null).setPositiveButton("CÓ"){_,_->api.call("staff_delete",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",employee.optString("mnv"))){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không xóa được nhân sự")else reloadMaster{TopNotice.show(this,"Đã xóa nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}}}}.show()
    }'''
    s=replace_fun(s,'confirmDeleteStaff(employee:JSONObject){','reloadMaster(done:()->Unit){',delete)

    history=r'''    private fun historyScreen(){
        module="HISTORY";screenState="HISTORY"
        val root=baseRoot("LỊCH SỬ");val body=body();val merged=LinkedHashMap<String,JSONObject>()
        fun friendly(type:String,label:String=""):String=when(type.uppercase()){ "ATTENDANCE_ENTER","ENTER"->"Vào ca";"ATTENDANCE_EXIT","EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên / vị trí";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"HISTORICAL_CORRECTION"->"Sửa lịch sử";"MASTER_RESOURCE_UPSERT"->"Cập nhật tài nguyên";"MASTER_RESOURCE_DELETE"->"Xóa tài nguyên";"MASTER_STAFF_UPSERT"->"Cập nhật nhân sự";"MASTER_STAFF_DELETE"->"Xóa nhân sự";else->label.ifBlank{type.ifBlank{"Thao tác"}} }
        fun actionType(a:String)=when(a){"enter"->"ATTENDANCE_ENTER";"exit"->"ATTENDANCE_EXIT";"resource_change"->"RESOURCE_CHANGE";"labor_start"->"LABOR_START";"labor_finish"->"LABOR_FINISH";else->a.uppercase()}
        val dates=operationalStore.availableDates().take(7);for(date in dates){val day=operationalStore.loadDay(date)?:continue;val events=day.optJSONArray("events")?:JSONArray();for(i in 0 until events.length()){val e=events.optJSONObject(i)?:continue;val c=JSONObject(e.toString()).put("cache_business_date",date).put("history_source","CANONICAL");val id=c.optString("event_id").ifBlank{"canonical:$date:$i"};val p=runCatching{JSONObject(c.optString("payload_json","{}"))}.getOrDefault(JSONObject());if(c.optString("mnv").isBlank())c.put("mnv",p.optString("mnv").ifBlank{p.optJSONObject("after")?.optString("mnv").orEmpty()});merged[id]=c}}
        val localRows=operationalStore.localHistory(1000);for(local in localRows){val id=local.optString("event_id");if(id.isBlank())continue;val existing=merged[id];if(existing!=null){existing.put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at"));continue};val b=local.optJSONObject("body")?:JSONObject();val p=b.optJSONObject("payload")?:b;merged[id]=JSONObject().put("event_id",id).put("event_type",actionType(b.optString("action"))).put("mnv",p.optString("mnv").ifBlank{b.optString("target_id")}).put("full_name",p.optString("full_name").ifBlank{b.optString("target_label")}).put("actor",login).put("detail",b.optString("detail")).put("local_status",local.optString("status")).put("local_error",local.optString("error")).put("local_queued_at",local.optLong("queued_at")).put("history_source","LOCAL_PDA")}
        val all=merged.values.sortedByDescending{e->val q=e.optLong("local_queued_at");if(q>0)q else runCatching{Instant.parse(e.optString("committed_at").ifBlank{e.optString("occurred_at").ifBlank{e.optString("at_iso")}}).toEpochMilli()}.getOrDefault(0)};val groups=LinkedHashMap<String,MutableList<JSONObject>>();for(e in all){val type=e.optString("event_type");val mnv=e.optString("mnv");val date=e.optString("business_date").ifBlank{e.optString("cache_business_date")};val operational=(type.startsWith("ATTENDANCE_")||type.startsWith("LABOR_")||type=="RESOURCE_CHANGE"||type=="HISTORICAL_CORRECTION")&&mnv.isNotBlank();val key=if(operational)"$date|$mnv" else "event:${e.optString("event_id")}";groups.getOrPut(key){mutableListOf()}.add(e)}
        val pending=all.count{it.optString("local_status") in setOf("LOCAL_PENDING","PENDING","RETRY","OFFLINE_PROVISIONAL")};val failed=all.count{it.optString("local_status") in setOf("REJECTED","REVIEW_REQUIRED","CONFLICT")};val top=row(bg);top.addView(metric("Tổng",groups.size.toString(),navy),LinearLayout.LayoutParams(0,-2,1f).apply{marginEnd=dp(2)});top.addView(metric("Chờ",pending.toString(),orange),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2);marginEnd=dp(2)});top.addView(metric("Cần xử lý",failed.toString(),red),LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(2)});body.addView(top,matchWrap());body.addView(gap(9))
        if(groups.isEmpty())body.addView(info("Chưa có lịch sử trên PDA."))
        for((key,items) in groups){val first=items.first();val operational=!key.startsWith("event:");val mnv=first.optString("mnv");val actor=items.firstNotNullOfOrNull{it.optString("actor_id").ifBlank{it.optString("actor")}.takeIf{x->x.isNotBlank()}}?:"Hệ thống";val status=historyGroupStatus(items);val syncedAt=items.firstNotNullOfOrNull{it.optString("committed_at").takeIf{x->x.isNotBlank()}}?.let{formatIso(it)}?:"Chưa có";val title=if(operational)"Mã nhân viên $mnv" else friendly(first.optString("event_type"),first.optString("label"));val sub=if(operational)"${items.size} thao tác trong phiên\n$status • Người thực hiện: $actor\nĐồng bộ lúc: $syncedAt" else "$status • Người thực hiện: $actor\nCập nhật: ${historyEventTime(first)}";val card=listCard(title,sub).apply{setOnClickListener{historyTimeline(items)}};body.addView(card,matchWrap());body.addView(gap(7))}
        foregroundSync.requestSync();attach(root,body)
    }

    private fun historyGroupStatus(items:List<JSONObject>):String{val st=items.map{it.optString("local_status")};return when{st.any{it in setOf("REJECTED","REVIEW_REQUIRED","CONFLICT")}->"Lỗi / cần kiểm tra";st.any{it=="RETRY"}->"Đang chờ gửi lại";st.any{it in setOf("LOCAL_PENDING","PENDING","OFFLINE_PROVISIONAL")}->"Đang đồng bộ";else->"Đã đồng bộ"}}
    private fun historyEventTime(e:JSONObject):String{val local=e.optLong("local_queued_at");if(local>0)return java.text.SimpleDateFormat("HH:mm:ss dd/MM/yyyy",java.util.Locale("vi","VN")).apply{timeZone=java.util.TimeZone.getTimeZone("Asia/Ho_Chi_Minh")}.format(java.util.Date(local));return formatIso(e.optString("committed_at").ifBlank{e.optString("occurred_at").ifBlank{e.optString("at_iso").ifBlank{e.optString("at")}}})}
    private fun historyCanEdit(e:JSONObject):Boolean{val date=e.optString("business_date").ifBlank{e.optString("cache_business_date")};val ix=operationalStore.availableDates().take(7).indexOf(date);return ix>=0&&ix<=if(isSuper())6 else 1}
    private fun historyTimeline(items:List<JSONObject>){screenState="HISTORY_DETAIL";val root=baseRoot("LỊCH SỬ");val body=body();val first=items.firstOrNull()?:return;val mnv=first.optString("mnv");body.addView(section(if(mnv.isBlank())"Chi tiết thao tác" else "Mã nhân viên $mnv"));body.addView(info("Dòng thời gian trong đúng phiên. Thời gian thao tác hệ thống/Event ID chỉ đọc, không chỉnh sửa."));body.addView(gap(8));items.sortedBy{historyEventTime(it)}.forEach{e->val type=e.optString("event_type");val actor=e.optString("actor_id").ifBlank{e.optString("actor")}.ifBlank{"Hệ thống"};val p=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val d=mutableListOf<String>();val after=p.optJSONObject("after");val src=after?:p;listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack","labor_type","time_marker","start_at","end_at","note","state").forEach{k->val v=src.optString(k);if(v.isNotBlank())d.add("$k: $v")};val card=column(surface).apply{setPadding(dp(13),dp(11),dp(13),dp(11));background=outlineBg(surface,14);addView(txt(when(type){"ATTENDANCE_ENTER"->"Vào ca";"ATTENDANCE_EXIT"->"Ra ca";"RESOURCE_CHANGE"->"Đổi tài nguyên / vị trí";"LABOR_START"->"Bắt đầu công nhật";"LABOR_FINISH"->"Hoàn thành công nhật";"HISTORICAL_CORRECTION"->"Sửa lịch sử";else->type},12.5f,navy,true));addView(txt("${historyEventTime(e)} • $actor",9.8f,muted,false));addView(txt("Trạng thái: ${historyGroupStatus(listOf(e))}",9.8f,if(historyGroupStatus(listOf(e)).startsWith("Đã"))green else orange,true));if(d.isNotEmpty())addView(txt(d.joinToString("\n"),9.8f,ink,false));addView(txt("Event ID: ${e.optString("event_id")}",8.7f,muted,false));if((e.optString("entity_type")=="ATTENDANCE_SESSION"||e.optString("entity_type")=="LABOR_SESSION")&&e.optString("entity_id").isNotBlank()&&historyCanEdit(e)){addView(gap(7));addView(smallButton("SỬA THÔNG TIN",teal).apply{setOnClickListener{historyEditDialog(e)}})}};body.addView(card,matchWrap());body.addView(gap(7))};attach(root,body)}
    private fun historyEditDialog(e:JSONObject){val entity=e.optString("entity_type");if(entity!="ATTENDANCE_SESSION"&&entity!="LABOR_SESSION")return;val raw=runCatching{JSONObject(e.optString("payload_json","{}"))}.getOrDefault(JSONObject());val initial=raw.optJSONObject("after")?:raw;val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val fields=LinkedHashMap<String,EditText>();val keys=if(entity=="ATTENDANCE_SESSION")listOf("shift","work_choice","pda_serial","user_pick","pack_table","user_pack","state")else listOf("labor_type","time_marker","start_at","end_at","note","state");for(k in keys){val v=input(k,false).apply{setText(initial.optString(k))};fields[k]=v;box.addView(labelled(k,v));box.addView(gap(6))};val deduct=CheckBox(this).apply{text="Khấu trừ nhân sự";isChecked=initial.optBoolean("deduct_staff",false);visibility=if(entity=="LABOR_SESSION")View.VISIBLE else View.GONE};box.addView(deduct);val reason=input("Lý do chỉnh sửa (bắt buộc)",false);box.addView(labelled("Lý do",reason));val dialog=AlertDialog.Builder(this).setTitle("Sửa thông tin lịch sử").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("LƯU",null).create();dialog.setOnShowListener{dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{val why=reason.text.toString().trim();if(why.length<3){showError("Nhập lý do chỉnh sửa.");return@setOnClickListener};val patch=JSONObject();fields.forEach{(k,v)->patch.put(k,v.text.toString().trim())};if(entity=="LABOR_SESSION")patch.put("deduct_staff",deduct.isChecked);val p=JSONObject().put("entity_type",entity).put("entity_id",e.optString("entity_id")).put("reason",why).put("patch",patch).put("target_event_id",e.optString("event_id")).put("idempotency_key",UUID.randomUUID().toString()).put("client_source","PDA");api.call("history_correction",p){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không sửa được lịch sử")else{dialog.dismiss();TopNotice.show(this,"Đã lưu chỉnh sửa vào lịch sử.",TopNotice.Kind.SUCCESS);foregroundSync.requestSync();historyScreen()}}}}};dialog.show()}'''
    s=replace_fun(s,'historyScreen(){','syncScreen(){',history)

    sync=r'''    private fun syncScreen(){
        module="SYNC";screenState="SYNC";val root=baseRoot("ĐỒNG BỘ");val body=body();val box=column(bg);val refresh=primary("LÀM MỚI TRẠNG THÁI",teal){};body.addView(box,matchWrap());body.addView(gap(10));body.addView(refresh,matchWrap())
        fun networkType():String{val cm=getSystemService(android.content.Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager;val n=cm.activeNetwork?:return "Không có mạng";val c=cm.getNetworkCapabilities(n)?:return "Không xác định";return when{c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI)->"Wi‑Fi";c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR)->"Dữ liệu di động";c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_ETHERNET)->"Ethernet";else->"Mạng khác"}}
        fun load(){box.removeAllViews();box.addView(info("Đang kiểm tra tình trạng thực tế..."));val started=android.os.SystemClock.elapsedRealtime();api.call("sync_status"){r->runOnUiThread{val elapsed=(android.os.SystemClock.elapsedRealtime()-started).coerceAtLeast(0);box.removeAllViews();val pending=operationalStore.pendingMutationCount();if(r.ok){val j=r.json?:JSONObject();val a=j.optJSONObject("authority")?:JSONObject();val rep=j.optJSONObject("replication")?:JSONObject();val mode=a.optString("mode").ifBlank{j.optString("authority_mode")};lastSyncLatencyMs=j.optLong("_service_rtt_ms",elapsed);lastConnected=true;lastProjectionPending=pending;refreshHeaderConnection();box.addView(section("Kết nối hiện tại"));box.addView(details(listOf("Loại mạng" to networkType(),"Ping tới Service" to "${lastSyncLatencyMs} ms","Service đang dùng" to if(mode=="SERVICE_PRIMARY")"Service chính" else "Kết nối dự phòng","Tình trạng Service" to "Hoạt động")));box.addView(section("Đồng bộ dữ liệu"));box.addView(details(listOf("Trạng thái" to if(pending==0)"Đã hoàn tất đồng bộ" else "Còn $pending mục chờ đồng bộ","Bộ nhớ đồng bộ PDA" to "${operationalStore.availableDates().size} phiên dữ liệu đang lưu","Dữ liệu chờ gửi" to pending.toString(),"Lần kiểm tra" to java.time.ZonedDateTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).format(DateTimeFormatter.ofPattern("HH:mm:ss dd/MM/yyyy")))));box.addView(section("Hệ thống"));box.addView(details(listOf("Dịch vụ dữ liệu" to if(mode=="SERVICE_PRIMARY")"Service / D1" else "Google dự phòng","Nhân bản Google" to when(rep.optString("state")){"HEALTHY"->"Bình thường";"DEGRADED"->"Cần kiểm tra";else->rep.optString("state").ifBlank{"Đang theo dõi"}},"Mục nhân bản chờ" to rep.optInt("pending_count",0).toString(),"Phiên bản ứng dụng" to "${BuildConfig.CHANNEL} • ${BuildConfig.VERSION_NAME}")))}else{lastConnected=false;lastSyncLatencyMs=elapsed;refreshHeaderConnection();box.addView(section("Kết nối hiện tại"));box.addView(details(listOf("Loại mạng" to networkType(),"Service" to "Chưa phản hồi","Thời gian kiểm tra" to "${elapsed} ms")));box.addView(info("Dữ liệu chưa gửi vẫn được giữ trên PDA. Khi quay lại màn hình ứng dụng và kết nối ổn định, hệ thống sẽ đồng bộ tiếp."));val driveStart=android.os.SystemClock.elapsedRealtime();api.updateCheck(BuildConfig.CHANNEL,BuildConfig.VERSION_NAME){u->runOnUiThread{val driveMs=(android.os.SystemClock.elapsedRealtime()-driveStart).coerceAtLeast(0);box.addView(gap(7));box.addView(details(listOf("Google Drive OTA" to if(u.ok)"Phản hồi ${driveMs} ms" else "Không phản hồi","Dữ liệu chờ gửi" to operationalStore.pendingMutationCount().toString())))}}}}}};refresh.setOnClickListener{foregroundSync.requestSync();load()};load();attach(root,body)
    }'''
    s=replace_fun(s,'syncScreen(){','settingsScreen(){',sync)

    # Insert temporary owner-test PDA exchange root tab before Settings.
    insert=s.find('    private fun settingsScreen(){')
    if insert<0: raise SystemExit('S33 PDA exchange insert anchor missing')
    pda=r'''    private fun pdaExchangeScreen(){
        module="PDA_EXCHANGE";screenState="PDA_EXCHANGE";val root=baseRoot("ĐỔI / TRẢ PDA");val body=body();body.addView(info("Logic thử nghiệm: thao tác Đổi PDA giữ phiên và chuyển sang PICK với PDA mới; Trả PDA thu hồi tài nguyên và chuyển vị trí trong ca về KHÔNG. Mọi thao tác dùng Event ID và được lưu lịch sử."));body.addView(gap(8));val mnv=mnvInput("Quét QR hoặc nhập mã nhân viên");val reason=input("Lý do đổi / trả PDA",false);val box=column(bg);body.addView(labelled("Mã nhân viên",mnv));body.addView(gap(7));body.addView(labelled("Lý do",reason));body.addView(gap(8));body.addView(box,matchWrap());fun load(){val id=mnv.text.toString().trim();if(id.isBlank()){showError("Nhập mã nhân viên.");return};api.call("employee_context",JSONObject().put("mnv",id).put("include_options",false)){r->runOnUiThread{box.removeAllViews();if(!r.ok){showError(r.error?:"Không tải được phiên");return@runOnUiThread};if(r.json?.optString("state")!="ACTIVE"){box.addView(info("Nhân viên phải đang trong phiên ACTIVE."));return@runOnUiThread};val ctx=r.json?:JSONObject();val e=ctx.optJSONObject("employee")?:JSONObject();val ses=ctx.optJSONObject("session")?:JSONObject();box.addView(employeeCard(e));box.addView(gap(7));box.addView(details(listOf("PDA hiện tại" to dash(ses.optString("pda_serial")),"Vị trí" to workText(ses.optString("work_choice")),"Ca" to ses.optString("shift"))));box.addView(gap(7));val pdas=MasterDataCache.resourceOptions(this).optJSONArray("pdas")?:JSONArray();val pdaField=pdaInput(pdas,ses.optString("pda_serial"));box.addView(labelled("PDA mới",pdaField));box.addView(gap(8));val actions=row(bg);val change=smallButton("ĐỔI PDA",teal);val giveBack=smallButton("TRẢ PDA",orange);actions.addView(change,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});actions.addView(giveBack,LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});box.addView(actions,matchWrap());change.setOnClickListener{val why=reason.text.toString().trim();if(why.isBlank()){showError("Nhập lý do đổi PDA.");return@setOnClickListener};val serial=resolvePda(pdas,pdaField.text.toString());if(serial==null){showError("Chọn đúng PDA theo 5 số cuối Seri.");return@setOnClickListener};val p=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("work_choice","PICK").put("pda_serial",serial).put("note","Đổi PDA: $why");val pick=ses.optString("user_pick");if(pick.isNotBlank())p.put("user_pick",pick);api.call("resource_change",p){x->runOnUiThread{if(!x.ok)showError(x.error?:"Không đổi được PDA")else{TopNotice.show(this,"Đã đổi PDA.",TopNotice.Kind.SUCCESS);load()}}}};giveBack.setOnClickListener{val why=reason.text.toString().trim();if(why.isBlank()){showError("Nhập lý do trả PDA.");return@setOnClickListener};api.call("resource_change",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("work_choice","KHONG").put("note","Trả PDA: $why")){x->runOnUiThread{if(!x.ok)showError(x.error?:"Không trả được PDA")else{TopNotice.show(this,"Đã trả PDA.",TopNotice.Kind.SUCCESS);load()}}}}}}};bindScannerEnter(mnv){load()};attach(root,body);mnv.requestFocus()
    }

'''
    s=s[:insert]+pda+s[insert:]

    # Header: greeting only + three compact, auto-sized operational chips.
    hs=s.find('    private fun connectionSummary():String{');he=s.find('    private fun sessionExpired(){',hs)
    if hs<0 or he<0: raise SystemExit('S33 header/nav anchors missing')
    block=r'''    private fun connectionSummary():String{val network=when(lastConnected){true->lastSyncLatencyMs?.let{"$it ms"}?:"Có mạng";false->"Mất kết nối";null->"Chưa kiểm tra"};val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(0);return "Mạng: $network | Đồng bộ: ${if(pending==0)"Hoàn tất" else "Còn $pending mục"} | Service: ${if(lastConnected==true)"Hoạt động" else "Đang chờ"}"}
    private fun refreshHeaderConnection(){val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(lastProjectionPending);networkStatusText?.text=when(lastConnected){true->lastSyncLatencyMs?.let{"$it ms"}?:"Có mạng";false->"Mất mạng";null->"—"};syncStatusText?.text=if(pending>0)"Còn $pending mục" else if(lastConnected==true)"Hoàn tất" else "Đang chờ";serviceStatusText?.text=if(lastConnected==true)"Hoạt động" else if(lastConnected==false)"Mất kết nối" else "—"}
    private fun headerStatusChip(iconRes:Int,label:String,valueView:TextView)=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL;setPadding(dp(6),dp(6),dp(6),dp(6));background=round(Color.argb(32,255,255,255),13);addView(ImageView(this@OperationsActivity).apply{setImageResource(iconRes);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(2),dp(2),dp(2),dp(2))},size(dp(22),dp(22)));addView(column(Color.TRANSPARENT).apply{addView(txt(label,7.2f,Color.argb(210,255,255,255),false).apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,8,1,android.util.TypedValue.COMPLEX_UNIT_SP)});addView(valueView.apply{maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,10,1,android.util.TypedValue.COMPLEX_UNIT_SP)})},LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(4)})}
    private fun greetingText():String{val h=java.time.LocalTime.now(ZoneId.of("Asia/Ho_Chi_Minh")).hour;val part=when(h){in 5..10->"sáng";in 11..13->"trưa";in 14..17->"chiều";else->"tối"};return "Chào buổi $part, ${name.ifBlank{login}}"}
    private fun appBar(title:String)=column(Color.TRANSPARENT).apply{setPadding(dp(16),dp(11),dp(16),dp(12));background=gradient(navy,accent,0);val identity=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL};if(!isRootScreen())identity.addView(ImageView(this@OperationsActivity).apply{setImageResource(R.drawable.ic_pp_back);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(7),dp(7),dp(7),dp(7));setOnClickListener{navigateBack()}},size(dp(36),dp(36)));identity.addView(txt(greetingText(),16f,Color.WHITE,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END},LinearLayout.LayoutParams(0,-2,1f).apply{if(!isRootScreen())marginStart=dp(3)});addView(identity,matchWrap());addView(gap(10));val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER};val net=txt("—",9f,Color.WHITE,true);networkStatusText=net;val syn=txt("—",9f,Color.WHITE,true);syncStatusText=syn;val svc=txt("—",9f,Color.WHITE,true);serviceStatusText=svc;statuses.addView(headerStatusChip(R.drawable.ic_pp_network,"Mạng",net),LinearLayout.LayoutParams(0,dp(44),1f).apply{marginEnd=dp(3)});statuses.addView(headerStatusChip(R.drawable.ic_pp_sync,"Đồng bộ",syn),LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(2);marginEnd=dp(2)});statuses.addView(headerStatusChip(R.drawable.ic_pp_service,"Service",svc),LinearLayout.LayoutParams(0,dp(44),1f).apply{marginStart=dp(3)});addView(statuses,matchWrap());refreshHeaderConnection()}
    private fun activeTab()=when(module){"STAFF"->"STAFF";"HISTORY"->"HISTORY";"SYNC"->"SYNC";"PDA_EXCHANGE"->"PDA_EXCHANGE";"SETTINGS"->"SETTINGS";else->"BUSINESS"}
    private fun bottomNav():LinearLayout=row(surface).apply{gravity=Gravity.CENTER;setPadding(dp(3),dp(5),dp(3),dp(5));background=outlineBg(surface,16);elevation=dp(8).toFloat();navRefs.clear();val items=listOf(Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS"),Triple(R.drawable.ic_pp_staff,"Nhân sự","STAFF"),Triple(R.drawable.ic_pp_history,"Lịch sử","HISTORY"),Triple(R.drawable.ic_pp_sync,"Đồng bộ","SYNC"),Triple(R.drawable.ic_pp_resource,"Đổi / trả PDA","PDA_EXCHANGE"),Triple(R.drawable.ic_pp_settings,"Cài đặt","SETTINGS"));items.forEach{item->val iconView=ImageView(this@OperationsActivity).apply{setImageResource(item.first);setPadding(dp(5),dp(4),dp(5),dp(2))};val labelView=txt(item.second,7f,muted,item.third==activeTab()).apply{gravity=Gravity.CENTER;maxLines=1;setAutoSizeTextTypeUniformWithConfiguration(6,8,1,android.util.TypedValue.COMPLEX_UNIT_SP)};val cell=column(Color.TRANSPARENT).apply{gravity=Gravity.CENTER;setPadding(dp(1),dp(2),dp(1),dp(2));addView(iconView,size(dp(30),dp(27)));addView(labelView);setOnClickListener{navigateTab(item.third)}};navRefs[item.third]=NavRefs(cell,iconView,labelView);addView(cell,LinearLayout.LayoutParams(0,-1,1f))};post{refreshBottomNav()}}
    private fun refreshBottomNav(){val active=activeTab();navRefs.forEach{(key,ref)->val chosen=key==active;ref.cell.background=if(chosen)round(ThemeManager.soft(this@OperationsActivity),10)else null;ref.icon.imageTintList=ColorStateList.valueOf(if(chosen)teal else muted);ref.label.setTextColor(if(chosen)teal else muted);ref.label.typeface=if(chosen)Typeface.DEFAULT_BOLD else Typeface.DEFAULT}}
    private fun navigateTab(target:String){if(target==activeTab())return;module=target;initialMnv="";liveEmployeeMnv="";when(target){"BUSINESS"->businessHome();"STAFF"->staffScreen();"HISTORY"->historyScreen();"SYNC"->syncScreen();"PDA_EXCHANGE"->pdaExchangeScreen();"SETTINGS"->settingsScreen()}}

'''
    s=s[:hs]+block+s[he:]
    s=s.replace('private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="SETTINGS"','private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="PDA_EXCHANGE"||screenState=="SETTINGS"')
    s=s.replace('"RESOURCE_EDITOR"->resourceHome()','"RESOURCE_LIST"->resourceHome()')
    s=s.replace('"SCAN","LABOR_HOME","RESOURCE_HOME","REPORT","LISTS"->businessHome()','"SCAN","LABOR_HOME","REPORT","LISTS"->businessHome()\n            "RESOURCE_HOME","RESOURCE_LIST"->businessHome()\n            "HISTORY_DETAIL"->historyScreen()')
    OPS.write_text(s,encoding='utf-8')

# Service-only owner actions use the current fenced discovery and Service session; never force Google fallback.
s=API.read_text(encoding='utf-8')
if MARK not in s:
    anchor='    private fun accountUpsert(payload: JSONObject): Result {'
    pos=s.find(anchor)
    if pos<0: raise SystemExit('S33 API helper anchor missing')
    helper=r'''    // S33_OWNER_UI_SYNC_RESOURCES: owner resource/correction calls go to current Service authority only.
    private fun serviceOwnerCall(action:String,payload:JSONObject):Result{
        val d=m2Transport.discoverySnapshot()?:return Result(false,503,null,"SERVICE_DISCOVERY_UNAVAILABLE")
        if(d.optString("authority_mode")!="SERVICE_PRIMARY")return Result(false,409,d,"SERVICE_NOT_WRITE_AUTHORITY")
        val base=d.optString("service_url").trimEnd('/');if(!base.startsWith("https://"))return Result(false,503,d,"SERVICE_URL_INVALID")
        val bearer=appContext.getSharedPreferences("pp_m2_service_transport",Context.MODE_PRIVATE).getString("service_token",null).orEmpty();if(bearer.isBlank())return Result(false,401,null,"UNAUTHORIZED")
        val path=if(action=="history_correction")"/v1/corrections" else "/v1/admin/resources";val method=if(action=="resource_master_list")"GET" else "POST";val body=JSONObject(payload.toString());if(action=="resource_master_upsert")body.put("operation","UPSERT");if(action=="resource_master_delete")body.put("operation","DELETE")
        var conn:HttpURLConnection?=null;return try{conn=(URL(base+path).openConnection() as HttpURLConnection).apply{requestMethod=method;connectTimeout=6_000;readTimeout=12_000;setRequestProperty("Accept","application/json");setRequestProperty("Authorization","Bearer $bearer");if(method=="POST"){doOutput=true;setRequestProperty("Content-Type","application/json; charset=utf-8")}};if(method=="POST")conn!!.outputStream.use{it.write(body.toString().toByteArray(Charsets.UTF_8))};val http=conn!!.responseCode;val stream=if(http in 200..299)conn!!.inputStream else conn!!.errorStream;val text=stream?.bufferedReader(Charsets.UTF_8)?.use{it.readText()}.orEmpty();val j=if(text.isBlank())JSONObject() else JSONObject(text);val ok=http in 200..299&&j.optBoolean("ok",false);Result(ok,http,j,if(ok)null else j.optString("error","HTTP_$http"))}catch(t:Throwable){Result(false,-1,null,t.message?:"SERVICE_OWNER_CALL_FAILED")}finally{conn?.disconnect()}
    }

'''
    s=s[:pos]+helper+s[pos:]
    # Generated call has one stable result assignment after the m2 selection.
    target='      val result = if (m2?.handled == true) {'
    if target not in s: raise SystemExit('S33 API result anchor missing')
    s=s.replace(target,'      val result = if (action in setOf("resource_master_list","resource_master_upsert","resource_master_delete","history_correction")) serviceOwnerCall(action,payload) else if (m2?.handled == true) {',1)
    s=s.replace('val tracked=setOf("enter","exit","resource_change","labor_start","labor_finish","change_password","change_email","account_upsert","account_status","staff_upsert","staff_delete","diagnostic_log")','val tracked=setOf("enter","exit","resource_change","labor_start","labor_finish","change_password","change_email","account_upsert","account_status","staff_upsert","staff_delete","resource_master_upsert","resource_master_delete","history_correction","diagnostic_log")')
    API.write_text(s,encoding='utf-8')

# Strict owner lifecycle: workers/process-network callbacks never start new ordinary sync off-screen.
w=WORKER.read_text(encoding='utf-8')
if MARK not in w:
    w=w.replace('override fun doWork(): Result = try {\n        if (M2ServiceTransport(applicationContext).flushOutbox())','override fun doWork(): Result = try {\n        if (!PpForegroundGate.isForeground()) return Result.success()\n        if (M2ServiceTransport(applicationContext).flushOutbox())',1)
    w=w.replace('override fun doWork(): Result = try {\n        val caughtUp = M2BackgroundSync.catchUp(applicationContext)','override fun doWork(): Result = try {\n        if (!PpForegroundGate.isForeground()) return Result.success()\n        val caughtUp = M2BackgroundSync.catchUp(applicationContext)',1)
    w=w.replace('        val app = context.applicationContext\n        val constraints = Constraints.Builder()','        val app = context.applicationContext\n        if (!PpForegroundGate.isForeground()) return // '+MARK+'\n        val constraints = Constraints.Builder()',1)
    w=w.replace('override fun onAvailable(network: Network) { M2WorkScheduler.schedule(app) }','override fun onAvailable(network: Network) { if(PpForegroundGate.isForeground()) M2WorkScheduler.schedule(app) }',1)
    WORKER.write_text(w,encoding='utf-8')

# Contract guards.
ops=OPS.read_text(encoding='utf-8');api=API.read_text(encoding='utf-8');worker=WORKER.read_text(encoding='utf-8')
for required in ['Đổi / trả PDA','Mã nhân viên','HHmm','resource_master_upsert','history_correction','Asia/Ho_Chi_Minh','LÀM MỚI TRẠNG THÁI']:
    if required not in ops: raise SystemExit('S33 Operations contract missing: '+required)
if 'serviceOwnerCall' not in api: raise SystemExit('S33 Service owner call missing')
if 'PpForegroundGate.isForeground()' not in worker: raise SystemExit('S33 foreground worker gate missing')
print('Applied S33 owner UI/history/staff/resources/sync/PDA-exchange/lifecycle/timezone patch')

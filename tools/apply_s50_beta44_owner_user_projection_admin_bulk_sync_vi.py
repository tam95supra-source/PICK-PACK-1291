#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OPS=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt'
API=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/BetaApiClient.kt'
MARK='S50_BETA44_OWNER_USER_PROJECTION_ADMIN_BULK_SYNC_VI'

def replace_fun(src,start_sig,next_sig,new_text):
    a=src.find('    private fun '+start_sig)
    b=src.find('    private fun '+next_sig,a+1)
    if a<0 or b<0: raise SystemExit(f'S50 function anchors missing: {start_sig} -> {next_sig}')
    return src[:a]+new_text.rstrip()+"\n\n"+src[b:]

s=OPS.read_text(encoding='utf-8')
if MARK in s:
    print('S50 already applied');raise SystemExit(0)

# Password re-authentication happens through the existing PBKDF2/HMAC login flow.
anchor='    private fun sessionWorkEditor(ctx:JSONObject){'
if anchor not in s: raise SystemExit('S50 sessionWorkEditor anchor missing')
helper=r'''    // S50_BETA44_OWNER_USER_PROJECTION_ADMIN_BULK_SYNC_VI
    private fun verifyDeletePassword(actionLabel:String,after:()->Unit){
        val pw=input("Mật khẩu hiện tại",true)
        val dialog=AlertDialog.Builder(this).setTitle("Xác thực trước khi xóa").setMessage("Nhập mật khẩu của tài khoản $login để $actionLabel.").setView(pw).setNegativeButton("Hủy",null).setPositiveButton("XÁC THỰC",null).create()
        dialog.setOnShowListener{val btn=dialog.getButton(AlertDialog.BUTTON_POSITIVE);btn.setOnClickListener{val value=pw.text.toString();if(value.isBlank()){showError("Nhập mật khẩu hiện tại.");return@setOnClickListener};btn.isEnabled=false;btn.text="ĐANG XÁC THỰC...";api.login(login,value){r->runOnUiThread{btn.isEnabled=true;btn.text="XÁC THỰC";if(!r.ok){showError("Mật khẩu không đúng hoặc không thể xác thực.");return@runOnUiThread};dialog.dismiss();after()}}}}
        dialog.show();pw.requestFocus()
    }

'''
s=s.replace(anchor,helper+anchor,1)

resource=r'''    private fun resourceListScreen(type:String,title:String){
        screenState="RESOURCE_LIST"
        val root=baseRoot(title);val body=body();val box=column(bg);val selected=linkedSetOf<String>();val checks=mutableListOf<CheckBox>()
        body.addView(info("Danh mục dùng chung. Thay đổi được ghi nhận vào lịch sử; xóa yêu cầu xác thực lại mật khẩu."));body.addView(gap(8))
        if(isAdmin()){val actions=row(bg);actions.addView(smallButton("THÊM",teal).apply{setOnClickListener{resourceEditDialog(type,null,null,null)}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});actions.addView(smallButton("CHỌN TẤT CẢ",navy).apply{setOnClickListener{checks.forEach{it.isChecked=true}}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3);marginEnd=dp(3)});actions.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{setOnClickListener{deleteResourcesBulk(type,selected.toList(),title)}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});body.addView(actions,matchWrap());body.addView(gap(8))}
        body.addView(box,matchWrap());box.addView(info("Đang tải danh sách..."))
        api.call("resource_master_list"){r->runOnUiThread{
            box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được tài nguyên"));return@runOnUiThread}
            val all=r.json?.optJSONArray("resources")?:JSONArray();val catalogs=r.json?.optJSONArray("catalogs")?:JSONArray();val rows=mutableListOf<JSONObject>();for(i in 0 until all.length()){val x=all.optJSONObject(i)?:continue;if(x.optString("resource_type")==type)rows.add(x)}
            if(rows.isEmpty())box.addView(info("Chưa có dữ liệu."))
            rows.forEach{x->val id=x.optString("resource_id");val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,14);val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};if(isAdmin()){val c=CheckBox(this@OperationsActivity).apply{isChecked=id in selected;setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}};checks.add(c);top.addView(c,size(dp(42),dp(42)))};top.addView(column(surface).apply{addView(txt(id,13.2f,navy,true));addView(txt("Tình trạng: ${x.optString("status_label").ifBlank{"—"}}",10f,if(x.optInt("available")!=0)green else muted,true))},LinearLayout.LayoutParams(0,-2,1f));addView(top,matchWrap());if(isAdmin()){addView(gap(6));val a=row(surface);a.addView(smallButton("SỬA",teal).apply{setOnClickListener{resourceEditDialog(type,x,catalogs,all)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginEnd=dp(3)});a.addView(smallButton("XÓA",red).apply{setOnClickListener{confirmDeleteResource(type,id,title)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3)});addView(a,matchWrap())}};box.addView(card,matchWrap());box.addView(gap(7))}
        }}
        attach(root,body)
    }'''
s=replace_fun(s,'resourceListScreen(type:String,title:String){','resourceStatusValues(type:String,catalogs:JSONArray?)',resource)

resource_delete=r'''    private fun deleteResourcesBulk(type:String,ids:List<String>,title:String){
        if(!isAdmin())return;if(ids.isEmpty()){showError("Chọn ít nhất một mục cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${ids.size} mục?").setMessage("Tài nguyên đang được sử dụng sẽ bị hệ thống chặn xóa.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa ${ids.size} tài nguyên"){fun next(i:Int){if(i>=ids.size){TopNotice.show(this,"Đã xử lý xóa các mục đã chọn.",TopNotice.Kind.SUCCESS);resourceListScreen(type,title);return};api.call("resource_master_delete",JSONObject().put("operation","DELETE").put("resource_type",type).put("resource_id",ids[i]).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError("${ids[i]}: ${r.error?:"Không xóa được"}");return@runOnUiThread};next(i+1)}}};next(0)}}.show()
    }

    private fun confirmDeleteResource(type:String,id:String,title:String){
        if(!isAdmin())return
        AlertDialog.Builder(this).setTitle("Xóa tài nguyên?").setMessage("Xóa $id khỏi $title?").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa tài nguyên $id"){api.call("resource_master_delete",JSONObject().put("operation","DELETE").put("resource_type",type).put("resource_id",id).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không xóa được tài nguyên")else{TopNotice.show(this,"Đã xóa tài nguyên.",TopNotice.Kind.SUCCESS);resourceListScreen(type,title)}}}}}.show()
    }'''
s=replace_fun(s,'confirmDeleteResource(type:String,id:String,title:String){','staffScreen(){',resource_delete)

staff=r'''    private fun staffScreen(){
        module="STAFF";screenState="STAFF"
        val root=baseRoot("NHÂN SỰ");val body=body();val selected=linkedSetOf<String>();val checks=mutableListOf<CheckBox>();val searchRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL};val q=input("Tìm mã nhân viên, họ tên hoặc số điện thoại",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f));if(isAdmin()){searchRow.addView(gap(8));searchRow.addView(iconActionButton(R.drawable.ic_pp_add,teal,"Thêm nhân sự"){staffEditor(null)},size(dp(50),dp(50)))};body.addView(searchRow,matchWrap())
        if(isSuper()){body.addView(gap(7));val bulk=row(bg);bulk.addView(smallButton("CHỌN TẤT CẢ",navy).apply{setOnClickListener{checks.forEach{it.isChecked=true}}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});bulk.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{setOnClickListener{deleteStaffBulk(selected.toList())}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});body.addView(bulk,matchWrap())}
        body.addView(gap(10));val box=column(bg);body.addView(box,matchWrap());var pageSize=60
        fun render(query:String){box.removeAllViews();checks.clear();val clean=query.trim();val limit=if(clean.isBlank())pageSize else 180;val arr=MasterDataCache.searchStaff(this,clean,limit)
            for(i in 0 until arr.length()){val e=arr.optJSONObject(i)?:continue;val id=e.optString("mnv");val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,18);val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};if(isSuper()){val c=CheckBox(this@OperationsActivity).apply{isChecked=id in selected;setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}};checks.add(c);top.addView(c,size(dp(42),dp(42)))};top.addView(column(surface).apply{addView(txt(e.optString("full_name"),14f,ink,true));addView(txt("Mã nhân viên $id • ${dash(e.optString("main_position"))}",10.7f,navy,true));addView(txt("${dash(e.optString("supplier"))} • ${dash(e.optString("department"))} • ${dash(e.optString("site"))}",9.8f,muted,false))},LinearLayout.LayoutParams(0,-2,1f));if(isAdmin()){top.addView(iconActionButton(R.drawable.ic_pp_edit,teal,"Sửa"){staffEditor(e)},size(dp(38),dp(38)));if(isSuper()){top.addView(gap(4));top.addView(iconActionButton(R.drawable.ic_pp_delete,red,"Xóa"){confirmDeleteStaff(e)},size(dp(38),dp(38)))}};addView(top,matchWrap())};box.addView(card,matchWrap());box.addView(gap(8))}
            if(arr.length()==0)box.addView(info("Không có nhân sự phù hợp."));if(clean.isBlank()&&arr.length()>=pageSize&&pageSize<MasterDataCache.staffCount(this)){box.addView(primary("XEM THÊM",teal){pageSize+=60;render("")},matchWrap())}}
        q.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(v:CharSequence?,st:Int,c:Int,a:Int)=Unit;override fun onTextChanged(v:CharSequence?,st:Int,b:Int,c:Int){render(v?.toString().orEmpty())};override fun afterTextChanged(v:Editable?)=Unit});q.setOnEditorActionListener{_,_,_->render(q.text.toString());true};render("");attach(root,body)
    }'''
s=replace_fun(s,'staffScreen(){','staffEditor(existing:JSONObject?){',staff)

staff_delete=r'''    private fun deleteStaffBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa nhân sự.");return};if(ids.isEmpty()){showError("Chọn ít nhất một nhân sự cần xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${ids.size} nhân sự?").setMessage("Nhân sự đang có phiên hoạt động sẽ bị hệ thống chặn xóa. Lịch sử nghiệp vụ vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa ${ids.size} nhân sự"){fun next(i:Int){if(i>=ids.size){reloadMaster{TopNotice.show(this,"Đã xử lý xóa các nhân sự đã chọn.",TopNotice.Kind.SUCCESS);staffScreen()};return};api.call("staff_delete",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",ids[i])){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError("${ids[i]}: ${r.error?:"Không xóa được"}");return@runOnUiThread};next(i+1)}}};next(0)}}.show()
    }

    private fun confirmDeleteStaff(employee:JSONObject){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa nhân sự.");return}
        val id=employee.optString("mnv");AlertDialog.Builder(this).setTitle("Xóa nhân sự?").setMessage("Xóa Mã nhân viên $id • ${employee.optString("full_name")}? Lịch sử nghiệp vụ vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa nhân sự $id"){api.call("staff_delete",JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id)){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok)showError(r.error?:"Không xóa được nhân sự")else reloadMaster{TopNotice.show(this,"Đã xóa nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}}}}}.show()
    }'''
s=replace_fun(s,'confirmDeleteStaff(employee:JSONObject){','reloadMaster(done:()->Unit){',staff_delete)

# Require password after the operator chooses the destructive EXIT removal.
exit_delete=r'''    private fun deleteExitRecord(ctx:JSONObject){
        if(!isAdmin())return;val ses=ctx.optJSONObject("session")?:return;val mnv=ses.optString("mnv");val reason=input("Lý do xóa ghi nhận ra ca",false).apply{setText("Bắn nhầm ra ca")}
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8));addView(info("Mốc RA sẽ bị xóa khỏi sheet RA/VÀO và phiên được mở lại. Nhật ký kiểm toán vẫn được giữ."));addView(gap(7));addView(reason,matchWrap())}
        AlertDialog.Builder(this).setTitle("Hủy ghi nhận RA CA?").setView(box).setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->if(reason.text.toString().trim().length<3){showError("Nhập lý do xóa.");return@setPositiveButton};verifyDeletePassword("xóa ghi nhận ra ca"){api.call("attendance_exit_delete",JSONObject().put("session_id",ses.optString("session_id")).put("reason",reason.text.toString().trim()).put("idempotency_key",UUID.randomUUID().toString())){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không xóa được mốc ra ca");return@runOnUiThread};val conflicts=r.json?.optJSONArray("resource_reacquire_conflicts")?:JSONArray();TopNotice.show(this,if(conflicts.length()>0)"Đã mở lại phiên; một số tài nguyên không thể tự cấp lại." else "Đã xóa mốc ra ca và mở lại phiên.",if(conflicts.length()>0)TopNotice.Kind.WARNING else TopNotice.Kind.SUCCESS);foregroundSync.requestSync();loadEmployee(mnv)}}}}.show()
    }'''
s=replace_fun(s,'deleteExitRecord(ctx:JSONObject){','renderActive(body: LinearLayout, ctx: JSONObject) {',exit_delete)

sync=r'''    private fun syncScreen(){
        module="SYNC";screenState="SYNC"
        val root=baseRoot("ĐỒNG BỘ");val body=body();val state=info("Đang kiểm tra trạng thái...");val statusBox=column(bg);val usersBox=column(bg)
        body.addView(state,matchWrap());body.addView(gap(8));body.addView(statusBox,matchWrap());body.addView(section("NGƯỜI DÙNG KẾT NỐI DỊCH VỤ"));body.addView(usersBox,matchWrap())
        fun loadUsers(){usersBox.removeAllViews();usersBox.addView(info("Đang tải người dùng đang hoạt động..."));api.call("service_connections"){r->runOnUiThread{usersBox.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){usersBox.addView(info("Chưa lấy được danh sách người dùng kết nối."));return@runOnUiThread};val a=r.json?.optJSONArray("nguoi_dung")?:JSONArray();if(a.length()==0){usersBox.addView(info("Chưa có người dùng hoạt động gần đây."));return@runOnUiThread};for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val last=x.optString("lan_hoat_dong_gan_nhat");usersBox.addView(listCard("${x.optString("ten_hien_thi")} • ${x.optString("tai_khoan")}","${x.optString("quyen")} • ${x.optString("trang_thai")} • ${if(last.isBlank())"Chưa có thời gian" else formatIso(last)}"));usersBox.addView(gap(6))}}}}
        api.call("sync_status"){r->runOnUiThread{statusBox.removeAllViews();if(handleAuth(r))return@runOnUiThread;val pending=runCatching{operationalStore.pendingMutationCount()}.getOrDefault(LocalLogManager.pendingCount(this));if(r.ok){state.text="✓ Kết nối và đồng bộ đang hoạt động";statusBox.addView(details(listOf("Mạng" to "Có kết nối","Đồng bộ dữ liệu" to if(pending==0)"Đã hoàn tất" else "Còn $pending mục chờ","Dữ liệu chờ gửi" to pending.toString(),"Dịch vụ" to "Đang hoạt động","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME)))}else{state.text="! Chưa kết nối được";statusBox.addView(details(listOf("Mạng" to if(lastConnected==false)"Mất kết nối" else "Chưa xác định","Đồng bộ dữ liệu" to "Đang chờ kết nối","Dữ liệu chờ gửi" to pending.toString(),"Dịch vụ" to "Chưa kết nối","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME)))};loadUsers()}}
        body.addView(gap(10));body.addView(primary("LÀM MỚI TRẠNG THÁI",teal){syncScreen()},matchWrap());attach(root,body)
    }'''
s=replace_fun(s,'syncScreen(){','settingsScreen(){',sync)

account=r'''    private fun accountManager(){
        screenState="ACCOUNT_MANAGER";val root=baseRoot("QUẢN LÝ TÀI KHOẢN");val body=body();val selected=linkedSetOf<String>();val checks=mutableListOf<CheckBox>()
        body.addView(primary("TẠO TÀI KHOẢN",green){accountCreateDialog()},matchWrap());if(isSuper()){body.addView(gap(7));val bulk=row(bg);bulk.addView(smallButton("CHỌN TẤT CẢ",navy).apply{setOnClickListener{checks.forEach{if(it.isEnabled)it.isChecked=true}}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginEnd=dp(3)});bulk.addView(smallButton("XÓA ĐÃ CHỌN",red).apply{setOnClickListener{deleteAccountsBulk(selected.toList())}},LinearLayout.LayoutParams(0,dp(42),1f).apply{marginStart=dp(3)});body.addView(bulk,matchWrap())};body.addView(gap(10));val box=column(bg);body.addView(box,matchWrap())
        api.call("account_list"){r->runOnUiThread{box.removeAllViews();if(handleAuth(r))return@runOnUiThread;if(!r.ok){box.addView(info(r.error?:"Không tải được tài khoản"));return@runOnUiThread};val a=r.json?.optJSONArray("items")?:JSONArray();for(i in 0 until a.length()){val x=a.optJSONObject(i)?:continue;val id=x.optString("login_id"),protected=id==login||x.optString("role")=="SUPERADMIN";val card=column(surface).apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=outlineBg(surface,12);val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL};if(isSuper()){val c=CheckBox(this@OperationsActivity).apply{isEnabled=!protected;isChecked=id in selected;setOnCheckedChangeListener{_,on->if(on)selected.add(id)else selected.remove(id)}};checks.add(c);top.addView(c,size(dp(42),dp(42)))};top.addView(column(surface).apply{addView(txt("$id • ${x.optString("display_name")}",13f,navy,true));addView(txt("${roleText(x.optString("role"))} • ${if(x.optString("status")=="ACTIVE")"Đang hoạt động" else "Đã vô hiệu hóa"} • ${x.optString("email")}",9.8f,muted,false))},LinearLayout.LayoutParams(0,-2,1f));addView(top,matchWrap());if(id!=login){addView(gap(6));val actions=row(surface);if(isSuper()){actions.addView(smallButton("SỬA",teal).apply{setOnClickListener{accountEditDialog(x)}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginEnd=dp(3)})};val newStatus=if(x.optString("status")=="ACTIVE")"DISABLED" else "ACTIVE";actions.addView(smallButton(if(newStatus=="DISABLED")"VÔ HIỆU" else "KÍCH HOẠT",if(newStatus=="DISABLED")orange else green).apply{setOnClickListener{api.call("account_status",JSONObject().put("login_id",id).put("status",newStatus)){rr->runOnUiThread{if(!rr.ok)showError(rr.error?:"Không cập nhật được")else accountManager()}}}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3);marginEnd=dp(3)});if(isSuper()&&!protected)actions.addView(smallButton("XÓA",red).apply{setOnClickListener{deleteAccountsBulk(listOf(id))}},LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3)});addView(actions,matchWrap())}};box.addView(card,matchWrap());box.addView(gap(7))}}};attach(root,body)
    }

    private fun accountEditDialog(x:JSONObject){
        if(!isSuper())return;val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))};val display=input("Tên hiển thị",false).apply{setText(x.optString("display_name"))};val mail=input("Mail",false).apply{setText(x.optString("email"))};val roles=arrayOf("USER","ADMIN");val roleSp=spinner(roles);roleSp.setSelection(if(x.optString("role")=="ADMIN")1 else 0);box.addView(labelled("Tên hiển thị",display));box.addView(gap(7));box.addView(labelled("Quyền",roleSp));box.addView(gap(7));box.addView(labelled("Mail",mail));AlertDialog.Builder(this).setTitle("Sửa tài khoản ${x.optString("login_id")}").setView(box).setNegativeButton("Hủy",null).setPositiveButton("LƯU"){_,_->val rr=roleSp.selectedItem.toString();api.call("account_upsert",JSONObject().put("login_id",x.optString("login_id")).put("display_name",display.text.toString().trim()).put("position",rr.lowercase()).put("email",mail.text.toString().trim()).put("role",rr)){r->runOnUiThread{if(!r.ok)showError(r.error?:"Không sửa được tài khoản")else accountManager()}}}.show()
    }

    private fun deleteAccountsBulk(ids:List<String>){
        if(!isSuper()){showError("Chỉ Quản trị cao nhất được xóa tài khoản.");return};val clean=ids.filter{it.isNotBlank()&&it!=login}.distinct();if(clean.isEmpty()){showError("Chọn ít nhất một tài khoản có thể xóa.");return}
        AlertDialog.Builder(this).setTitle("Xóa ${clean.size} tài khoản?").setMessage("Tài khoản Quản trị cao nhất và tài khoản đang đăng nhập được bảo vệ. Nhật ký kiểm toán vẫn được giữ.").setNegativeButton("Hủy",null).setPositiveButton("TIẾP TỤC"){_,_->verifyDeletePassword("xóa ${clean.size} tài khoản"){api.call("account_delete",JSONObject().put("login_ids",JSONArray(clean))){r->runOnUiThread{if(handleAuth(r))return@runOnUiThread;if(!r.ok){showError(r.error?:"Không xóa được tài khoản");return@runOnUiThread};val blocked=r.json?.optJSONArray("blocked")?:JSONArray();TopNotice.show(this,if(blocked.length()>0)"Đã xóa các tài khoản hợp lệ; ${blocked.length()} mục được bảo vệ hoặc không thể xóa." else "Đã xóa tài khoản.",if(blocked.length()>0)TopNotice.Kind.WARNING else TopNotice.Kind.SUCCESS);accountManager()}}}}.show()
    }'''
s=replace_fun(s,'accountManager(){','accountCreateDialog(){',account)

# Remove user-facing protocol jargon left by prior generated versions.
s=s.replace('headerStatusChip(R.drawable.ic_pp_service,"Service",svc)','headerStatusChip(R.drawable.ic_pp_service,"Dịch vụ",svc)')
s=s.replace('| Service: ','| Dịch vụ: ')
OPS.write_text(s,encoding='utf-8')

# Extend direct Service calls. No plaintext password is added to any destructive request.
a=API.read_text(encoding='utf-8')
old='''val path=when(action){"history_correction"->"/v1/corrections";"session_work_update"->"/v1/session/work";"session_exit_guarded"->"/v1/session/exit";"attendance_time_correct"->"/v1/session/time-correction";"attendance_exit_delete"->"/v1/session/delete-exit";else->"/v1/admin/resources"};val method=if(action=="resource_master_list")"GET" else "POST";val body=JSONObject(payload.toString())'''
new='''val path=when(action){"history_correction"->"/v1/corrections";"session_work_update"->"/v1/session/work";"session_exit_guarded"->"/v1/session/exit";"attendance_time_correct"->"/v1/session/time-correction";"attendance_exit_delete"->"/v1/session/delete-exit";"service_connections"->"/v1/service/connections";"account_delete"->"/v1/admin/accounts/delete";else->"/v1/admin/resources"};val method=if(action in setOf("resource_master_list","service_connections"))"GET" else "POST";val body=JSONObject(payload.toString())'''
if old not in a: raise SystemExit('S50 BetaApiClient direct route anchor missing')
a=a.replace(old,new,1)
oldset='setOf("resource_master_list","resource_master_upsert","resource_master_delete","history_correction","session_work_update","session_exit_guarded","attendance_time_correct","attendance_exit_delete")'
newset='setOf("resource_master_list","resource_master_upsert","resource_master_delete","history_correction","session_work_update","session_exit_guarded","attendance_time_correct","attendance_exit_delete","service_connections","account_delete")'
if oldset not in a: raise SystemExit('S50 BetaApiClient direct set anchor missing')
a=a.replace(oldset,newset,1)
API.write_text(a,encoding='utf-8')

out=OPS.read_text(encoding='utf-8');api=API.read_text(encoding='utf-8')
checks=[(MARK in out,'marker'),('verifyDeletePassword' in out,'password reauth'),('XÓA ĐÃ CHỌN' in out,'bulk delete'),('service_connections' in out,'service connections'),('NGƯỜI DÙNG KẾT NỐI DỊCH VỤ' in out,'Vietnamese sync users'),('Authority canonical' not in out and 'Service realtime' not in out and 'Realtime endpoint' not in out,'no protocol jargon'),('/v1/service/connections' in api,'connections endpoint'),('/v1/admin/accounts/delete' in api,'account delete endpoint')]
for ok,label in checks:
    if not ok: raise SystemExit('S50 contract missing: '+label)
print('Applied S50 Beta44: approved User projection compatibility, password-gated single/bulk delete, account edit/delete, common Vietnamese Sync user view')

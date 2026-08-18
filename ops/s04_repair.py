from pathlib import Path


def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    a = text.index(start)
    b = text.index(end, a + len(start))
    p.write_text(text[:a] + replacement + text[b:], encoding="utf-8")


full = "app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt"
replace_between(
    full,
    "    private fun bottomNav(active:String)=",
    "    private fun sessionExpired()",
    '''    private fun bottomNav(active:String): LinearLayout = row(surface).apply {
        gravity = Gravity.CENTER
        setPadding(dp(3),dp(3),dp(3),dp(3))
        background = GradientDrawable().apply { setColor(surface); setStroke(dp(1),line) }
        val items = listOf(
            Triple("▦","Nghiệp vụ","BUSINESS"),
            Triple("◉","Nhân sự","STAFF"),
            Triple("◷","Lịch sử","HISTORY"),
            Triple("↻","Đồng bộ","SYNC"),
            Triple("⚙","Cài đặt","SETTINGS")
        )
        items.forEach { item ->
            val cell = column(surface).apply {
                gravity = Gravity.CENTER
                addView(txt(item.first,17f,if(item.third==active)teal else muted,true).apply { gravity=Gravity.CENTER })
                addView(txt(item.second,8.4f,if(item.third==active)teal else muted,item.third==active).apply { gravity=Gravity.CENTER; maxLines=1 })
                setOnClickListener { _ ->
                    if(item.third=="BUSINESS") dashboard() else openModule(item.third)
                }
            }
            addView(cell,LinearLayout.LayoutParams(0,-1,1f))
        }
    }

'''
)

ops = "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
replace_between(
    ops,
    "    private fun staffScreen(){",
    "    private fun staffEditor(",
    '''    private fun staffScreen(){
        screenState="STAFF"
        val root=baseRoot("NHÂN SỰ")
        val body=body()
        val q=input("Tìm MNV / họ tên",false).apply {
            setSingleLine(true)
            imeOptions=EditorInfo.IME_ACTION_SEARCH
        }
        body.addView(q,matchWrap())
        body.addView(gap(7))
        if(isAdmin()){
            body.addView(primary("＋ THÊM NHÂN SỰ",teal){ staffEditor(null) },matchWrap())
            body.addView(gap(7))
        }
        val box=column(bg)
        body.addView(box,matchWrap())

        fun render(query:String){
            box.removeAllViews()
            val arr=MasterDataCache.searchStaff(this,query,2000)
            for(i in 0 until arr.length()){
                val employee=arr.optJSONObject(i) ?: continue
                val card=column(surface).apply {
                    setPadding(dp(11),dp(9),dp(11),dp(9))
                    background=outlineBg(surface,8)
                    addView(txt("◉  ${employee.optString("mnv")} • ${employee.optString("full_name")}",12.5f,ink,true))
                    addView(txt("${dash(employee.optString("main_position"))} • ${dash(employee.optString("supplier"))} • ${dash(employee.optString("department"))}",9.7f,muted,false))
                    if(isAdmin()){
                        addView(gap(5))
                        val actions=row(surface)
                        val edit=primary("✎ SỬA",teal){ staffEditor(employee) }.apply { textSize=9.2f; setSingleLine(true) }
                        val del=primary("× XÓA",red){ confirmDeleteStaff(employee) }.apply { textSize=9.2f; setSingleLine(true) }
                        actions.addView(edit,LinearLayout.LayoutParams(0,dp(38),1f).apply{marginEnd=dp(3)})
                        actions.addView(del,LinearLayout.LayoutParams(0,dp(38),1f).apply{marginStart=dp(3)})
                        addView(actions,matchWrap())
                    }
                }
                box.addView(card,matchWrap())
                box.addView(gap(6))
            }
            if(arr.length()==0) box.addView(info("ⓘ Không có nhân sự phù hợp."))
        }

        q.addTextChangedListener(object:TextWatcher{
            override fun beforeTextChanged(v:CharSequence?,s:Int,c:Int,a:Int)=Unit
            override fun onTextChanged(v:CharSequence?,s:Int,b:Int,c:Int){ render(v?.toString().orEmpty()) }
            override fun afterTextChanged(v:Editable?)=Unit
        })
        q.setOnEditorActionListener { _,_,_ -> render(q.text.toString()); true }
        render("")
        attach(root,body)
    }

'''
)

replace_between(
    ops,
    "    private fun staffEditor(existing:JSONObject?){",
    "    private fun listsScreen(){",
    '''    private fun staffEditor(existing:JSONObject?){
        if(!isAdmin()) return
        val box=column(surface).apply { setPadding(dp(6),0,dp(6),0) }
        val mnv=input("Mã nhân viên",false).apply {
            setText(existing?.optString("mnv").orEmpty())
            isEnabled=existing==null
        }
        val full=input("Họ và tên",false).apply { setText(existing?.optString("full_name").orEmpty()) }
        val phone=input("Số điện thoại",false).apply { setText(existing?.optString("phone").orEmpty()) }
        val pos=input("Vị trí chính",false).apply { setText(existing?.optString("main_position").orEmpty()) }
        val supplier=input("Nhà cung cấp",false).apply { setText(existing?.optString("supplier").orEmpty()) }
        val department=input("Bộ phận",false).apply { setText(existing?.optString("department").orEmpty()) }
        val site=input("Site",false).apply { setText(existing?.optString("site").orEmpty()) }
        val warehouse=input("Kho",false).apply { setText(existing?.optString("warehouse").orEmpty()) }
        val startDate=input("Ngày bắt đầu dd/MM/yyyy",false).apply { setText(existing?.optString("start_date").orEmpty()) }
        val note=input("Ghi chú",false).apply { setText(existing?.optString("note").orEmpty()) }
        listOf(mnv,full,phone,pos,supplier,department,site,warehouse,startDate,note).forEach { field ->
            box.addView(field,matchWrap())
            box.addView(gap(5))
        }
        val scroller=ScrollView(this).apply { addView(box) }
        AlertDialog.Builder(this)
            .setTitle(if(existing==null) "Thêm nhân sự" else "Sửa nhân sự")
            .setView(scroller)
            .setNegativeButton("Hủy",null)
            .setPositiveButton("LƯU") { _,_ ->
                val id=mnv.text.toString().trim()
                val nm=full.text.toString().trim()
                if(id.isBlank() || nm.isBlank()){
                    TopNotice.show(this,"MNV và họ tên là bắt buộc.",TopNotice.Kind.ERROR)
                } else {
                    val payload=JSONObject()
                        .put("event_id",UUID.randomUUID().toString())
                        .put("mnv",id)
                        .put("full_name",nm)
                        .put("phone",phone.text.toString())
                        .put("main_position",pos.text.toString())
                        .put("supplier",supplier.text.toString())
                        .put("department",department.text.toString())
                        .put("site",site.text.toString())
                        .put("warehouse",warehouse.text.toString())
                        .put("start_date",startDate.text.toString())
                        .put("note",note.text.toString())
                    api.call("staff_upsert",payload) { result ->
                        runOnUiThread {
                            if(handleAuth(result)) {
                                Unit
                            } else if(!result.ok) {
                                showError(result.error ?: "Không lưu được nhân sự")
                            } else {
                                reloadMaster {
                                    TopNotice.show(this,"Đã lưu nhân sự.",TopNotice.Kind.SUCCESS)
                                    staffScreen()
                                }
                            }
                        }
                    }
                }
            }
            .show()
    }

    private fun confirmDeleteStaff(employee:JSONObject){
        AlertDialog.Builder(this)
            .setTitle("Xóa nhân sự?")
            .setMessage("Xóa ${employee.optString("mnv")} • ${employee.optString("full_name")}? Lịch sử nghiệp vụ đã phát sinh vẫn được giữ.")
            .setNegativeButton("KHÔNG",null)
            .setPositiveButton("CÓ") { _,_ ->
                val payload=JSONObject()
                    .put("event_id",UUID.randomUUID().toString())
                    .put("mnv",employee.optString("mnv"))
                api.call("staff_delete",payload) { result ->
                    runOnUiThread {
                        if(handleAuth(result)) {
                            Unit
                        } else if(!result.ok) {
                            showError(result.error ?: "Không xóa được nhân sự")
                        } else {
                            reloadMaster {
                                TopNotice.show(this,"Đã xóa nhân sự.",TopNotice.Kind.SUCCESS)
                                staffScreen()
                            }
                        }
                    }
                }
            }
            .show()
    }

    private fun reloadMaster(done:()->Unit){
        cacheApi.call("master_snapshot") { result ->
            runOnUiThread {
                if(result.ok && result.json!=null) MasterDataCache.save(this,result.json)
                done()
            }
        }
    }

'''
)

replace_between(
    ops,
    "    private fun bottomNav()=",
    "    private fun navigateTab(",
    '''    private fun bottomNav(): LinearLayout = row(surface).apply {
        gravity=Gravity.CENTER
        setPadding(dp(3),dp(3),dp(3),dp(3))
        background=GradientDrawable().apply { setColor(surface); setStroke(dp(1),line) }
        val active=activeTab()
        val items=listOf(
            Triple("▦","Nghiệp vụ","BUSINESS"),
            Triple("◉","Nhân sự","STAFF"),
            Triple("◷","Lịch sử","HISTORY"),
            Triple("↻","Đồng bộ","SYNC"),
            Triple("⚙","Cài đặt","SETTINGS")
        )
        items.forEach { item ->
            val cell=column(surface).apply {
                gravity=Gravity.CENTER
                addView(txt(item.first,17f,if(item.third==active)teal else muted,true).apply { gravity=Gravity.CENTER })
                addView(txt(item.second,8.4f,if(item.third==active)teal else muted,item.third==active).apply { gravity=Gravity.CENTER; maxLines=1 })
                setOnClickListener { _ -> navigateTab(item.third) }
            }
            addView(cell,LinearLayout.LayoutParams(0,-1,1f))
        }
    }

'''
)

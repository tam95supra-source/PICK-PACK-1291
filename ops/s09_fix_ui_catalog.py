from pathlib import Path
import re


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing marker: {label}')
    return text.replace(old, new, 1)


def sub_once(text, pattern, repl, label, flags=re.S):
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'pattern count {n}: {label}')
    return out

# Version
p=Path('app/build.gradle.kts')
s=p.read_text()
s=replace_once(s,'versionCode = 14\n            versionName = "0.4.2-beta.8"','versionCode = 15\n            versionName = "0.4.2-beta.9"','beta version')
p.write_text(s)

# GAS: expose generic Danh mục schema in master snapshot.
p=Path('google-apps-script/PICK_PACK_API.gs')
g=p.read_text()
g=g.replace("key='PP_MASTER_V4_'+rev","key='PP_MASTER_V5_'+rev",1)
old="""  const rows=ppObjects_(PP.CATALOG), labor=[], markers=[];
  rows.forEach(function(r){ const a=r['CÔNG NHẬT_Thông tin công nhật'],b=r['CÔNG NHẬT_Mốc thời gian']; if(a&&labor.indexOf(a)<0)labor.push(a);if(b&&markers.indexOf(b)<0)markers.push(b); });
  const out={master_revision:rev,staff:staff,pdas:pdas,user_picks:userPicks,pack_tables:tables,pack_bundles:packs,labor_types:labor,time_markers:markers,config_warnings:warnings};
"""
new="""  const catalogRaw=ppValues_(PP.CATALOG), catalogFields={};
  if(catalogRaw.length){
    const headers=catalogRaw[0].map(function(v){return String(v||'').trim();});
    headers.forEach(function(h,col){
      if(!h)return;
      const values=[];
      for(let i=1;i<catalogRaw.length;i++){
        const v=String((catalogRaw[i]||[])[col]||'').trim();
        if(v && values.indexOf(v)<0) values.push(v);
      }
      catalogFields[h]=values;
    });
  }
  const labor=(catalogFields['CÔNG NHẬT_Thông tin công nhật']||[]).slice();
  const markers=(catalogFields['CÔNG NHẬT_Mốc thời gian']||[]).slice();
  const out={master_revision:rev,staff:staff,pdas:pdas,user_picks:userPicks,pack_tables:tables,pack_bundles:packs,labor_types:labor,time_markers:markers,catalog_fields:catalogFields,config_warnings:warnings};
"""
g=replace_once(g,old,new,'generic catalog fields')
p.write_text(g)

# Android UI
p=Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt')
s=p.read_text()

s=replace_once(s,
'''    private var syncText: TextView? = null
    private var contentHost: FrameLayout? = null
''',
'''    private var networkStatusText: TextView? = null
    private var syncStatusText: TextView? = null
    private var serviceStatusText: TextView? = null
    private var lastConnected: Boolean? = null
    private var contentHost: FrameLayout? = null
''','sync state fields')

s=replace_once(s,
'''                syncText?.text = if(status.connected) "Mạng: Tốt\\nĐồng bộ: Tự động\\nService: Chưa cấu hình" else "Mạng: Mất kết nối\\nĐồng bộ: Đang chờ\\nService: Chưa cấu hình"
                syncText?.setTextColor(Color.WHITE)
''',
'''                lastConnected = status.connected
                refreshHeaderConnection()
''','foreground status render')

s=replace_once(s,
'''        body.addView(txt("Thao tác nhanh",12f,muted,true))
        body.addView(gap(8))
''',
'''        body.addView(gap(3))
''','business heading removal')

# Staff screen: compact/lazy list with icon actions.
s=sub_once(s,r'''    private fun staffScreen\(\)\{.*?\n    private fun staffEditor\(existing:JSONObject\?\)\{''',r'''    private fun staffScreen(){
        module="STAFF"
        screenState="STAFF"
        val root=baseRoot("NHÂN SỰ")
        val body=body()
        val searchRow=row(bg).apply{gravity=Gravity.CENTER_VERTICAL}
        val q=input("Tìm mã nhân viên hoặc họ tên",false).apply{setSingleLine(true);imeOptions=EditorInfo.IME_ACTION_SEARCH}
        searchRow.addView(q,LinearLayout.LayoutParams(0,dp(50),1f))
        if(isAdmin()){
            searchRow.addView(gap(8))
            searchRow.addView(iconActionButton(R.drawable.ic_pp_add,teal,"Thêm nhân sự"){staffEditor(null)},size(dp(50),dp(50)))
        }
        body.addView(searchRow,matchWrap())
        body.addView(gap(11))
        val box=column(bg)
        body.addView(box,matchWrap())
        var pageSize=60

        fun render(query:String){
            box.removeAllViews()
            val clean=query.trim()
            val limit=if(clean.isBlank()) pageSize else 180
            val arr=MasterDataCache.searchStaff(this,clean,limit)
            for(i in 0 until arr.length()){
                val employee=arr.optJSONObject(i) ?: continue
                val card=column(surface).apply{
                    setPadding(dp(14),dp(12),dp(12),dp(12))
                    background=outlineBg(surface,18)
                    elevation=dp(3).toFloat()
                    val top=row(surface).apply{gravity=Gravity.CENTER_VERTICAL}
                    top.addView(iconBubble(R.drawable.ic_pp_staff,teal),size(dp(40),dp(40)))
                    top.addView(column(surface).apply{
                        addView(txt(employee.optString("full_name"),13.4f,ink,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
                        addView(txt(employee.optString("mnv"),9.8f,muted,false))
                    },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(9)})
                    if(isAdmin()){
                        top.addView(iconActionButton(R.drawable.ic_pp_edit,teal,"Sửa"){staffEditor(employee)},size(dp(38),dp(38)))
                        top.addView(Space(this@OperationsActivity),size(dp(5),1))
                        top.addView(iconActionButton(R.drawable.ic_pp_delete,red,"Xóa"){confirmDeleteStaff(employee)},size(dp(38),dp(38)))
                    }
                    addView(top,matchWrap())
                    addView(gap(8))
                    addView(txt(listOf(dash(employee.optString("main_position")),dash(employee.optString("department")),dash(employee.optString("supplier"))).joinToString("  •  "),9.7f,muted,false).apply{maxLines=2})
                }
                box.addView(card,matchWrap())
                box.addView(gap(8))
            }
            if(arr.length()==0) box.addView(info("Không có nhân sự phù hợp."))
            if(clean.isBlank() && arr.length()>=pageSize && pageSize<MasterDataCache.staffCount(this)){
                val more=primary("XEM THÊM",teal){pageSize+=60;render("")}.apply{textSize=10.5f}
                box.addView(more,matchWrap())
            }
        }
        q.addTextChangedListener(object:TextWatcher{
            override fun beforeTextChanged(v:CharSequence?,s:Int,c:Int,a:Int)=Unit
            override fun onTextChanged(v:CharSequence?,s:Int,b:Int,c:Int){render(v?.toString().orEmpty())}
            override fun afterTextChanged(v:Editable?)=Unit
        })
        q.setOnEditorActionListener{_,_,_->render(q.text.toString());true}
        render("")
        attach(root,body)
    }

    private fun staffEditor(existing:JSONObject?){''','staff screen')

# Staff editor catalog-driven selects.
s=sub_once(s,r'''    private fun staffEditor\(existing:JSONObject\?\)\{.*?\n    private fun confirmDeleteStaff''',r'''    private fun staffEditor(existing:JSONObject?){
        if(!isAdmin()) return
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val mnv=input("Mã nhân viên",false).apply{setText(existing?.optString("mnv").orEmpty());isEnabled=existing==null}
        val full=input("Họ và tên",false).apply{setText(existing?.optString("full_name").orEmpty())}
        val phone=input("Số điện thoại",false).apply{setText(existing?.optString("phone").orEmpty())}
        val pos=catalogSpinner("DANH SÁCH NHÂN SỰ_Vị trí chính",existing?.optString("main_position").orEmpty(),true)
        val supplier=catalogSpinner("DANH SÁCH NHÂN SỰ_Nhà cung cấp",existing?.optString("supplier").orEmpty(),true)
        val department=catalogSpinner("DANH SÁCH NHÂN SỰ_Bộ phận",existing?.optString("department").orEmpty(),true)
        val site=catalogSpinner("DANH SÁCH NHÂN SỰ_Site",existing?.optString("site").orEmpty(),true)
        val warehouse=catalogSpinner("DANH SÁCH NHÂN SỰ_Kho",existing?.optString("warehouse").orEmpty(),true)
        val startDate=input("Ngày bắt đầu dd/MM/yyyy",false).apply{setText(existing?.optString("start_date").orEmpty())}
        val note=input("Ghi chú",false).apply{setText(existing?.optString("note").orEmpty())}
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))}
        addField("Mã nhân viên",mnv);addField("Họ và tên",full);addField("Số điện thoại",phone)
        addField("Vị trí chính",pos);addField("Nhà cung cấp",supplier);addField("Bộ phận",department);addField("Site",site);addField("Kho",warehouse)
        addField("Ngày bắt đầu làm việc",startDate);addField("Ghi chú",note)
        val scroller=ScrollView(this).apply{addView(box)}
        AlertDialog.Builder(this)
            .setTitle(if(existing==null) "Thêm nhân sự" else "Sửa nhân sự")
            .setView(scroller)
            .setNegativeButton("Hủy",null)
            .setPositiveButton("LƯU"){_,_->
                val id=mnv.text.toString().trim();val nm=full.text.toString().trim()
                if(id.isBlank()||nm.isBlank()){TopNotice.show(this,"MNV và họ tên là bắt buộc.",TopNotice.Kind.ERROR);return@setPositiveButton}
                val payload=JSONObject().put("event_id",UUID.randomUUID().toString()).put("mnv",id).put("full_name",nm)
                    .put("phone",phone.text.toString()).put("main_position",catalogSelection(pos)).put("supplier",catalogSelection(supplier))
                    .put("department",catalogSelection(department)).put("site",catalogSelection(site)).put("warehouse",catalogSelection(warehouse))
                    .put("start_date",startDate.text.toString()).put("note",note.text.toString())
                api.call("staff_upsert",payload){result->runOnUiThread{
                    if(handleAuth(result))Unit else if(!result.ok)showError(result.error?:"Không lưu được nhân sự") else reloadMaster{TopNotice.show(this,"Đã lưu nhân sự.",TopNotice.Kind.SUCCESS);staffScreen()}
                }}
            }.show()
    }

    private fun confirmDeleteStaff''','staff editor')

# Account create gets position select.
s=sub_once(s,r'''    private fun accountCreateDialog\(\)\{.*?\n    \}\n\n    private fun refreshMasterCache''',r'''    private fun accountCreateDialog(){
        val box=column(surface).apply{setPadding(dp(10),dp(4),dp(10),dp(8))}
        val loginInput=input("Tài khoản",false)
        val display=input("Tên hiển thị",false)
        val positions=catalogValues("DANH SÁCH ADMIN_Vị trí").ifEmpty{catalogValues("DANH SÁCH NHÂN SỰ_Vị trí chính")}
        val positionSp=spinner((if(positions.isEmpty())listOf("—")else positions).toTypedArray())
        val mail=input("Mail nhận reset",false).apply{setText("tam95.supra@gmail.com")}
        val roles=if(isSuper())arrayOf("USER","ADMIN")else arrayOf("USER")
        val roleSp=spinner(roles)
        val pass=input("Mật khẩu ban đầu (>=8 ký tự)",true)
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))}
        addField("Tài khoản",loginInput);addField("Tên hiển thị",display);addField("Vị trí",positionSp);addField("Mail nhận reset",mail);addField("Quyền",roleSp);addField("Mật khẩu ban đầu",pass)
        AlertDialog.Builder(this).setTitle("Tạo tài khoản").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("TẠO"){_,_->
            api.call("account_upsert",JSONObject().put("login_id",loginInput.text.toString().trim()).put("display_name",display.text.toString().trim()).put("position",catalogSelection(positionSp)).put("email",mail.text.toString().trim()).put("role",roleSp.selectedItem.toString()).put("password",pass.text.toString())){r->runOnUiThread{if(!r.ok)showError(r.error?:"Không tạo được tài khoản")else accountManager()}}
        }.show()
    }

    private fun refreshMasterCache''','account create')

# Settings account summary copy.
s=replace_once(s,
'''        body.addView(listCard("$name • ${roleText(role)}","Tài khoản: $login${if(position.isBlank())"" else " • Vị trí: $position"}\\nMail reset: ${email.ifBlank{"Chưa cấu hình"}}"))
''',
'''        body.addView(listCard("$name • ${roleText(role)}","$login${if(position.isBlank())"" else "  •  $position"}\\nMail: ${email.ifBlank{"Chưa cấu hình"}}"))
''','settings account copy')

# Diagnostic payload summary no longer depends on transient header TextView.
s=replace_once(s,'LocalLogManager.sendManualReport(this,api,module,syncText?.text?.toString().orEmpty())','LocalLogManager.sendManualReport(this,api,module,connectionSummary())','diagnostic connection summary')

# Shift and labor selectors from catalog.
s=replace_once(s,
'''        val shift=spinner(arrayOf("Ca 1","Ca 2","Ca HC"));val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));''',
'''        val shift=spinner(catalogValues("VÀO - RA TRONG CA_Ca",listOf("Ca 1","Ca 2","Ca HC")).toTypedArray());val choice=spinner(arrayOf("KHÔNG","PICK","PACK"));''','shift catalog')
s=replace_once(s,
'''val types=jsonStrings(masters.optJSONArray("labor_types"));val markers=jsonStrings(masters.optJSONArray("time_markers"));''',
'''val types=catalogValues("CÔNG NHẬT_Thông tin công nhật",jsonStrings(masters.optJSONArray("labor_types")));val markers=catalogValues("CÔNG NHẬT_Mốc thời gian",jsonStrings(masters.optJSONArray("time_markers")));''','labor catalog')

# Header/root shell redesign: no root-tab titles, no root back placeholder, no account prefix, persistent connection status chips.
s=sub_once(s,r'''    private fun isRootScreen\(\)=.*?\n    private fun activeTab\(\)''',r'''    private fun isRootScreen()=screenState=="BUSINESS"||screenState=="STAFF"||screenState=="HISTORY"||screenState=="SYNC"||screenState=="SETTINGS"
    private fun connectionSummary():String{
        val network=when(lastConnected){true->"Tốt";false->"Mất kết nối";null->"Chưa kiểm tra"}
        val sync=when(lastConnected){true->"Sẵn sàng";false->"Đang chờ";null->"Chưa kiểm tra"}
        return "Mạng: $network | Đồng bộ: $sync | Service: Chưa cấu hình"
    }
    private fun refreshHeaderConnection(){
        networkStatusText?.text=when(lastConnected){true->"Tốt";false->"Mất";null->"—"}
        syncStatusText?.text=when(lastConnected){true->"Sẵn sàng";false->"Chờ";null->"—"}
        serviceStatusText?.text="Chưa dùng"
    }
    private fun headerStatusChip(iconRes:Int,label:String,valueView:TextView)=row(Color.TRANSPARENT).apply{
        gravity=Gravity.CENTER_VERTICAL
        setPadding(dp(8),dp(7),dp(8),dp(7))
        background=round(Color.argb(32,255,255,255),13)
        addView(ImageView(this@OperationsActivity).apply{setImageResource(iconRes);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(2),dp(2),dp(2),dp(2))},size(dp(24),dp(24)))
        addView(column(Color.TRANSPARENT).apply{
            addView(txt(label,7.8f,Color.argb(210,255,255,255),false).apply{maxLines=1})
            addView(valueView.apply{maxLines=1})
        },LinearLayout.LayoutParams(0,-2,1f).apply{marginStart=dp(5)})
    }
    private fun appBar(title:String)=column(Color.TRANSPARENT).apply{
        setPadding(dp(16),dp(12),dp(16),dp(13))
        background=gradient(navy,accent,0)
        val identity=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER_VERTICAL}
        if(!isRootScreen()){
            identity.addView(ImageView(this@OperationsActivity).apply{setImageResource(R.drawable.ic_pp_back);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(7),dp(7),dp(7),dp(7));setOnClickListener{navigateBack()}},size(dp(36),dp(36)))
        }
        identity.addView(column(Color.TRANSPARENT).apply{
            addView(txt(name.ifBlank{login},16.2f,Color.WHITE,true).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
            addView(txt(position.ifBlank{roleText(role)},10.5f,Color.argb(225,255,255,255),false).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
            addView(txt(login,10f,Color.argb(210,255,255,255),false).apply{maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
        },LinearLayout.LayoutParams(0,-2,1f).apply{if(!isRootScreen())marginStart=dp(3)})
        addView(identity,matchWrap())
        addView(gap(11))
        val statuses=row(Color.TRANSPARENT).apply{gravity=Gravity.CENTER}
        val net=txt("—",9.2f,Color.WHITE,true);networkStatusText=net
        val syn=txt("—",9.2f,Color.WHITE,true);syncStatusText=syn
        val svc=txt("Chưa dùng",9.2f,Color.WHITE,true);serviceStatusText=svc
        statuses.addView(headerStatusChip(R.drawable.ic_pp_network,"Mạng",net),LinearLayout.LayoutParams(0,dp(46),1f).apply{marginEnd=dp(4)})
        statuses.addView(headerStatusChip(R.drawable.ic_pp_sync,"Đồng bộ",syn),LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(2);marginEnd=dp(2)})
        statuses.addView(headerStatusChip(R.drawable.ic_pp_service,"Service",svc),LinearLayout.LayoutParams(0,dp(46),1f).apply{marginStart=dp(4)})
        addView(statuses,matchWrap())
        refreshHeaderConnection()
        if(!isRootScreen() && title.isNotBlank()){
            addView(gap(10))
            addView(txt(title,15f,Color.WHITE,true).apply{setPadding(dp(1),0,0,0);maxLines=1;ellipsize=android.text.TextUtils.TruncateAt.END})
        }
    }
    private fun activeTab()''','app bar shell')

# Bottom nav: correct business/grid icon, closer to mockup, smaller selected background.
s=replace_once(s,'Triple(R.drawable.ic_pp_task,"Nghiệp vụ","BUSINESS")','Triple(R.drawable.ic_pp_business,"Nghiệp vụ","BUSINESS")','business tab icon')
s=replace_once(s,'background=if(chosen)round(ThemeManager.soft(this@OperationsActivity),12)else null','background=if(chosen)round(ThemeManager.soft(this@OperationsActivity),10)else null','nav active shape')

# Work cards and common controls closer to approved sample.
s=sub_once(s,r'''    private fun iconBubble\(res:Int,color:Int\)=FrameLayout\(this\)\.apply\{.*?\n    private fun employeeCard''',r'''    private fun iconBubble(res:Int,color:Int)=FrameLayout(this).apply{
        background=round(ThemeManager.soft(this@OperationsActivity),14)
        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(9),dp(9),dp(9),dp(9))},FrameLayout.LayoutParams(-1,-1))
    }
    private fun businessIconBubble(res:Int):FrameLayout{
        val colors=when(res){
            R.drawable.ic_pp_scan->intArrayOf(teal,accent)
            R.drawable.ic_pp_task->intArrayOf(Color.rgb(37,99,235),Color.rgb(14,165,233))
            R.drawable.ic_pp_report->intArrayOf(Color.rgb(124,58,237),Color.rgb(168,85,247))
            else->intArrayOf(Color.rgb(6,182,212),Color.rgb(14,165,233))
        }
        return FrameLayout(this).apply{
            background=GradientDrawable(GradientDrawable.Orientation.TL_BR,colors).apply{shape=GradientDrawable.OVAL}
            elevation=dp(5).toFloat()
            addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(Color.WHITE);setPadding(dp(13),dp(13),dp(13),dp(13))},FrameLayout.LayoutParams(-1,-1))
        }
    }
    private fun businessCard(iconRes:Int,title:String,sub:String,click:()->Unit)=column(surface).apply{
        gravity=Gravity.CENTER_HORIZONTAL
        setPadding(dp(14),dp(16),dp(14),dp(14))
        background=outlineBg(surface,20)
        elevation=dp(6).toFloat()
        addView(businessIconBubble(iconRes),size(dp(62),dp(62)))
        addView(gap(11))
        addView(txt(title,14.2f,ink,true).apply{gravity=Gravity.CENTER;maxLines=2})
        addView(gap(6))
        addView(View(this@OperationsActivity).apply{background=round(teal,2)},size(dp(28),dp(3)))
        addView(gap(7))
        addView(txt(sub,10.2f,muted,false).apply{gravity=Gravity.CENTER;maxLines=1})
        setOnClickListener{click()}
    }
    private fun businessRow(a:View,b:View)=row(bg).apply{
        addView(a,LinearLayout.LayoutParams(0,dp(160),1f).apply{marginEnd=dp(6)})
        addView(b,LinearLayout.LayoutParams(0,dp(160),1f).apply{marginStart=dp(6)})
    }
    private fun iconActionButton(res:Int,color:Int,desc:String,click:()->Unit)=FrameLayout(this).apply{
        contentDescription=desc
        background=round(ThemeManager.soft(this@OperationsActivity),12)
        setOnClickListener{click()}
        addView(ImageView(this@OperationsActivity).apply{setImageResource(res);imageTintList=ColorStateList.valueOf(color);setPadding(dp(9),dp(9),dp(9),dp(9))},FrameLayout.LayoutParams(-1,-1))
    }

    private fun employeeCard''','card helpers')

s=replace_once(s,
'''    private fun input(h:String,password:Boolean)=EditText(this).apply{hint=h;textSize=14f;setTextColor(ink);setHintTextColor(Color.rgb(153,163,176));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(13),dp(10),dp(13),dp(10));minHeight=dp(48);background=outline()}
    private fun labelled(l:String,v:View)=column(bg).apply{addView(txt(l,10.5f,ink,true));addView(gap(4));addView(v,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@OperationsActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(9),dp(4),dp(9),dp(4));minimumHeight=dp(48);background=outline()}
    private fun primary(t:String,c:Int,click:()->Unit)=Button(this).apply{text=t;textSize=12.2f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(50);background=round(c,12);setOnClickListener{click()}}
''',
'''    private fun input(h:String,password:Boolean)=EditText(this).apply{hint=h;textSize=13.5f;setTextColor(ink);setHintTextColor(Color.rgb(148,163,184));inputType=if(password)InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_CLASS_TEXT;setPadding(dp(14),dp(11),dp(14),dp(11));minHeight=dp(50);background=outline();elevation=dp(1).toFloat()}
    private fun labelled(l:String,v:View)=column(bg).apply{addView(txt(l,10.2f,muted,true));addView(gap(5));addView(v,matchWrap())}
    private fun spinner(items:Array<String>)=Spinner(this).apply{adapter=ArrayAdapter(this@OperationsActivity,android.R.layout.simple_spinner_dropdown_item,items);setPadding(dp(11),dp(5),dp(11),dp(5));minimumHeight=dp(50);background=outline();elevation=dp(1).toFloat()}
    private fun primary(t:String,c:Int,click:()->Unit)=Button(this).apply{text=t;textSize=12f;setTextColor(Color.WHITE);typeface=Typeface.DEFAULT_BOLD;isAllCaps=false;minHeight=dp(50);background=gradient(c,darken(c),14);elevation=dp(3).toFloat();setOnClickListener{click()}}
''','common inputs/buttons')

s=replace_once(s,'private fun body()=column(bg).apply{setPadding(dp(14),dp(13),dp(14),dp(92))}','private fun body()=column(bg).apply{setPadding(dp(16),dp(15),dp(16),dp(92))}','body spacing')
s=replace_once(s,'private fun outline()=GradientDrawable().apply{setColor(surface);cornerRadius=dp(12).toFloat();setStroke(dp(1),line)}','private fun outline()=GradientDrawable().apply{setColor(surface);cornerRadius=dp(15).toFloat();setStroke(dp(1),line)}','input radius')

# Generic catalog helpers + color helper.
old='''    private fun jsonStrings(a:JSONArray?):MutableList<String>{val out=mutableListOf<String>();if(a!=null)for(i in 0 until a.length()){val v=a.optString(i);if(v.isNotBlank())out.add(v)};return out}
    private fun selectByValue(sp:Spinner,values:List<String>,target:String){val i=values.indexOf(target);if(i>=0)sp.setSelection(i)}
'''
new='''    private fun jsonStrings(a:JSONArray?):MutableList<String>{val out=mutableListOf<String>();if(a!=null)for(i in 0 until a.length()){val v=a.optString(i);if(v.isNotBlank())out.add(v)};return out}
    private fun catalogValues(key:String,fallback:List<String> = emptyList()):MutableList<String>{
        val fields=MasterDataCache.snapshot(this)?.optJSONObject("catalog_fields")
        var arr=fields?.optJSONArray(key)
        if(arr==null && fields!=null){val keys=fields.keys();while(keys.hasNext()){val k=keys.next();if(foldLocal(k)==foldLocal(key)){arr=fields.optJSONArray(k);break}}}
        val out=jsonStrings(arr)
        if(out.isEmpty())fallback.filter{it.isNotBlank()}.forEach{if(!out.contains(it))out.add(it)}
        return out
    }
    private fun catalogSpinner(key:String,current:String="",allowBlank:Boolean=false):Spinner{
        val values=catalogValues(key)
        if(allowBlank)values.add(0,"—")
        if(current.isNotBlank()&&!values.contains(current))values.add(current)
        if(values.isEmpty())values.add("—")
        return spinner(values.toTypedArray()).also{sp->selectByValue(sp,values,if(current.isBlank()&&allowBlank)"—" else current)}
    }
    private fun catalogSelection(sp:Spinner)=sp.selectedItem?.toString().orEmpty().let{if(it=="—")"" else it}
    private fun selectByValue(sp:Spinner,values:List<String>,target:String){val i=values.indexOf(target);if(i>=0)sp.setSelection(i)}
'''
s=replace_once(s,old,new,'catalog helpers')
s=replace_once(s,'private fun gradient(a:Int,b:Int,r:Int)=GradientDrawable(GradientDrawable.Orientation.TL_BR,intArrayOf(a,b)).apply{cornerRadius=dp(r).toFloat()}','private fun gradient(a:Int,b:Int,r:Int)=GradientDrawable(GradientDrawable.Orientation.TL_BR,intArrayOf(a,b)).apply{cornerRadius=dp(r).toFloat()}\n    private fun darken(c:Int)=Color.rgb((Color.red(c)*0.82f).toInt(),(Color.green(c)*0.82f).toInt(),(Color.blue(c)*0.82f).toInt())','darken helper')

p.write_text(s)

# New semantic icons.
d=Path('app/src/main/res/drawable')
icons={
'ic_pp_business.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#000000" android:pathData="M3,3h7v7H3zM14,3h7v7h-7zM3,14h7v7H3zM14,14h7v7h-7z"/></vector>''',
'ic_pp_network.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#000000" android:pathData="M12,20.5l2.2,-2.2c-1.2,-1.2 -3.2,-1.2 -4.4,0zM7.1,15.4l2,2c1.6,-1.6 4.2,-1.6 5.8,0l2,-2c-2.7,-2.7 -7.1,-2.7 -9.8,0zM3.2,11.5l2,2c3.8,-3.8 9.8,-3.8 13.6,0l2,-2c-4.9,-4.9 -12.7,-4.9 -17.6,0zM0,8.3l2,2c5.5,-5.5 14.5,-5.5 20,0l2,-2c-6.6,-6.6 -17.4,-6.6 -24,0z"/></vector>''',
'ic_pp_service.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#000000" android:pathData="M12,2l8,3v6c0,5.1 -3.4,9.7 -8,11 -4.6,-1.3 -8,-5.9 -8,-11V5zM10.8,15.6l5.7,-5.7 -1.4,-1.4 -4.3,4.3 -2,-2 -1.4,1.4z"/></vector>''',
'ic_pp_edit.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#000000" android:pathData="M3,17.3V21h3.7L17.6,10.1l-3.7,-3.7zM20.7,7c0.4,-0.4 0.4,-1 0,-1.4l-2.3,-2.3c-0.4,-0.4 -1,-0.4 -1.4,0l-1.8,1.8 3.7,3.7z"/></vector>''',
'ic_pp_delete.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#000000" android:pathData="M6,19c0,1.1 0.9,2 2,2h8c1.1,0 2,-0.9 2,-2V7H6zM8,9h8v10H8zM15.5,4l-1,-1h-5l-1,1H5v2h14V4z"/></vector>''',
'ic_pp_add.xml':'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#000000" android:pathData="M19,13h-6v6h-2v-6H5v-2h6V5h2v6h6z"/></vector>'''
}
for name,content in icons.items():
    (d/name).write_text(content)

# Docs: lock the catalog semantics and actual-device feedback.
p=Path('docs/UI_UX_SYSTEM.md')
doc=p.read_text()
append='''\n\n## S09 actual-device corrections\n\n- Root tabs do not render a duplicate page title in the top gradient header.\n- The authenticated identity header shows exactly three user lines: display name, position, login ID. No avatar placeholder and no `Tài khoản:` prefix.\n- Connection status is persistent Activity state; rebuilding tab content must never reset the header to a transient `Mạng: Đang nối/Đang kết nối` message.\n- Staff list must render incrementally/lazily; search still queries the complete local master cache. Never rebuild thousands of staff card views synchronously during a tab click.\n- `Danh mục` is a UI schema: headers use `SHEET_FIELD`. Use the matching catalog for editable/selectable business fields. Do not expose system-owned/status catalogs in contexts where the user is not allowed to edit them. Example: `DANH SÁCH PDA_Tình trạng` is not selectable while assigning a PDA to PICK.\n- If an exact catalog key does not yet exist, do not invent arbitrary values. A semantically equivalent fallback may be used only when the mapping is safe and documented; current `Danh sách Admin_Vị trí` falls back to `DANH SÁCH NHÂN SỰ_Vị trí chính`.\n'''
if '## S09 actual-device corrections' not in doc:
    p.write_text(doc.rstrip()+append+'\n')

print('S09 patch applied')

from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing marker: {label}')
    return text.replace(old, new, 1)

# Android: Admin is a dedicated namespace. No cross-sheet catalog fallback.
p=Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt')
s=p.read_text()
old='''        val positions=catalogValues("DANH SÁCH ADMIN_Vị trí").ifEmpty{catalogValues("DANH SÁCH NHÂN SỰ_Vị trí chính")}
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
'''
new='''        val allowedPositions=if(isSuper())arrayOf("USER","ADMIN")else arrayOf("USER")
        val positionSp=spinner(allowedPositions)
        val mail=input("Mail nhận reset",false).apply{setText("tam95.supra@gmail.com")}
        val pass=input("Mật khẩu ban đầu (>=8 ký tự)",true)
        fun addField(label:String,view:View){box.addView(txt(label,10.2f,ink,true));box.addView(gap(4));box.addView(view,matchWrap());box.addView(gap(8))}
        addField("Tài khoản",loginInput);addField("Tên hiển thị",display);addField("Vị trí",positionSp);addField("Mail nhận reset",mail);addField("Mật khẩu ban đầu",pass)
        AlertDialog.Builder(this).setTitle("Tạo tài khoản").setView(ScrollView(this).apply{addView(box)}).setNegativeButton("Hủy",null).setPositiveButton("TẠO"){_,_->
            val fixedRole=positionSp.selectedItem.toString().uppercase()
            api.call("account_upsert",JSONObject().put("login_id",loginInput.text.toString().trim()).put("display_name",display.text.toString().trim()).put("position",fixedRole.lowercase()).put("email",mail.text.toString().trim()).put("role",fixedRole).put("password",pass.text.toString())){r->runOnUiThread{if(!r.ok)showError(r.error?:"Không tạo được tài khoản")else accountManager()}}
        }.show()
'''
s=replace_once(s,old,new,'admin account UI fixed positions')
p.write_text(s)

# Backend: Admin position is system-owned and derived from role, never accepted as arbitrary catalog/input.
p=Path('google-apps-script/PICK_PACK_API.gs')
g=p.read_text()
old="""  const login=String(body.login_id||'').trim(),display=String(body.display_name||login).trim(),role=String(body.role||'USER').toUpperCase(),verifier=String(body.password_verifier||'').trim(),position=String(body.position||'').trim(),email=String(body.email||'').trim()||PP.RESET_ADMIN_EMAIL;
"""
new="""  const login=String(body.login_id||'').trim(),display=String(body.display_name||login).trim(),role=String(body.role||'USER').toUpperCase(),verifier=String(body.password_verifier||'').trim(),position=role.toLowerCase(),email=String(body.email||'').trim()||PP.RESET_ADMIN_EMAIL;
"""
g=replace_once(g,old,new,'backend admin position derivation')
p.write_text(g)

# Documentation: remove the invalid fallback and lock the namespace.
p=Path('docs/UI_UX_SYSTEM.md')
d=p.read_text()
d=d.replace('- If an exact catalog key does not yet exist, do not invent arbitrary values. A semantically equivalent fallback may be used only when the mapping is safe and documented; current `Danh sách Admin_Vị trí` falls back to `DANH SÁCH NHÂN SỰ_Vị trí chính`.','- Catalog namespaces are strict. Never borrow values from another sheet even when field names look similar. `Danh sách Admin` is a protected system namespace: its `Vị trí` is fixed to `superadmin`, `admin`, `user` and may only change after an explicit owner decision.')
p.write_text(d)

print('S09 Admin fixed-role rule applied')

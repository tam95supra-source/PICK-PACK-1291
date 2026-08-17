from pathlib import Path

ops=Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt')
s=ops.read_text(encoding='utf-8')
if 'private fun mnvInput(' not in s:
    needle='    private fun input(h:String,password:Boolean)=EditText(this).apply{'
    helper='    private fun mnvInput(h:String)=input(h,false).apply{setSingleLine(true);inputType=InputType.TYPE_CLASS_NUMBER;keyListener=DigitsKeyListener.getInstance("0123456789");imeOptions=EditorInfo.IME_ACTION_DONE}\n    private fun bindScannerEnter(v:EditText,submit:()->Unit){v.setOnEditorActionListener{_,id,_->if(id==EditorInfo.IME_ACTION_DONE||id==EditorInfo.IME_ACTION_GO||id==EditorInfo.IME_ACTION_SEARCH){submit();true}else false};v.setOnKeyListener{_,key,event->if(key==KeyEvent.KEYCODE_ENTER&&event.action==KeyEvent.ACTION_UP){submit();true}else false}}\n'
    if needle not in s: raise SystemExit('Operations input helper anchor missing')
    s=s.replace(needle,helper+needle,1)
ops.write_text(s,encoding='utf-8')

gas=Path('google-apps-script/PICK_PACK_API.gs')
g=gas.read_text(encoding='utf-8')
old="return {ok:true,service:'pick-pack-gsheet-api',mode:'APP_GSHEET',sheet_read:rows.length>1,business_date:ppBusinessIso_(),revision:ppRevision_()};"
new="return {ok:true,service:'pick-pack-gsheet-api',mode:'APP_GSHEET',api_version:'0.4.1',sheet_read:rows.length>1,business_date:ppBusinessIso_(),revision:ppRevision_(),master_revision:ppMasterRevision_()};"
if old in g: g=g.replace(old,new,1)
gas.write_text(g,encoding='utf-8')
print('compile compatibility fixed')

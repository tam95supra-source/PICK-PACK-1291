package vn.pickpack1291.app.beta

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import android.view.Gravity
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors

/**
 * SUPERADMIN-only PDA Import Center. Bulk import is intentionally not local-first canonical work:
 * a selected file may remain waiting on the device, but master data changes only after Service
 * preview + explicit commit. Web and PDA share the same Service Import Engine.
 */
class PdaImportActivity : Activity() {
    private val executor=Executors.newSingleThreadExecutor { r->Thread(r,"pp-pda-import").apply{isDaemon=true} }
    private lateinit var dataset:Spinner
    private lateinit var status:TextView
    private lateinit var preview:TextView
    private lateinit var commit:Button
    private lateinit var historyBox:LinearLayout
    private var selectedBytes:ByteArray?=null
    private var selectedName:String=""
    private var batchId:String=""
    private var pendingTemplateDataset:String="employees"
    private val datasets=linkedMapOf("employees" to "Nhân sự","catalogs" to "Danh mục","pda" to "PDA","user_pick" to "User Pick","pack_table" to "Bàn Pack","user_pack" to "User Pack")

    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState)
        val account=BetaApiClient(this).restoredAccount()
        if(account?.optString("role")!="SUPERADMIN"){finish();return}
        title="Import Excel"
        val root=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(dp(14),dp(12),dp(14),dp(24));setBackgroundColor(Color.rgb(245,247,251))}
        val top=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL;gravity=Gravity.CENTER_VERTICAL}
        top.addView(Button(this).apply{text="‹";setOnClickListener{finish()}},LinearLayout.LayoutParams(dp(52),dp(44)))
        top.addView(TextView(this).apply{text="IMPORT EXCEL";textSize=19f;setTextColor(Color.rgb(23,32,51));setTypeface(typeface,1);setPadding(dp(10),0,0,0)},LinearLayout.LayoutParams(0,dp(44),1f))
        root.addView(top)
        val scroll=ScrollView(this);val body=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL}
        body.addView(card().apply{
            addView(TextView(this@PdaImportActivity).apply{text="Loại dữ liệu";textSize=12f;setTextColor(Color.DKGRAY})
            dataset=Spinner(this@PdaImportActivity);dataset.adapter=ArrayAdapter(this@PdaImportActivity,android.R.layout.simple_spinner_dropdown_item,datasets.values.toList());addView(dataset,matchWrap())
            val actions=LinearLayout(this@PdaImportActivity).apply{orientation=LinearLayout.HORIZONTAL}
            actions.addView(actionButton("TẢI FILE MẪU"){createTemplate()},LinearLayout.LayoutParams(0,dp(48),1f).apply{marginEnd=dp(4)})
            actions.addView(actionButton("CHỌN FILE .XLSX"){chooseFile()},LinearLayout.LayoutParams(0,dp(48),1f).apply{marginStart=dp(4)})
            addView(actions,matchWrap())
            status=TextView(this@PdaImportActivity).apply{text="Chưa chọn file.";textSize=12f;setTextColor(Color.DKGRAY;);setPadding(0,dp(10),0,0)}
            addView(status,matchWrap())
            addView(actionButton("KIỂM TRA & PREVIEW"){prepareSelected()},matchWrap())
        },matchWrap())
        body.addView(card().apply{
            addView(TextView(this@PdaImportActivity).apply{text="Preview";textSize=16f;setTypeface(typeface,1);setTextColor(Color.rgb(23,32,51))})
            preview=TextView(this@PdaImportActivity).apply{text="Chưa có preview.";textSize=12f;setTextColor(Color.DKGRAY;);setPadding(0,dp(8),0,dp(8))}
            addView(preview,matchWrap())
            commit=actionButton("XÁC NHẬN IMPORT"){commitBatch()}.apply{isEnabled=false};addView(commit,matchWrap())
        },matchWrap())
        body.addView(card().apply{
            val h=LinearLayout(this@PdaImportActivity).apply{orientation=LinearLayout.HORIZONTAL;gravity=Gravity.CENTER_VERTICAL}
            h.addView(TextView(this@PdaImportActivity).apply{text="Lịch sử Import";textSize=16f;setTypeface(typeface,1);setTextColor(Color.rgb(23,32,51))},LinearLayout.LayoutParams(0,dp(44),1f))
            h.addView(actionButton("LÀM MỚI"){loadHistory()},LinearLayout.LayoutParams(dp(112),dp(44)))
            addView(h,matchWrap());historyBox=LinearLayout(this@PdaImportActivity).apply{orientation=LinearLayout.VERTICAL};addView(historyBox,matchWrap())
        },matchWrap())
        scroll.addView(body);root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f));setContentView(root);loadHistory()
    }

    private fun currentDataset():String=datasets.keys.elementAt(dataset.selectedItemPosition.coerceIn(0,datasets.size-1))
    private fun createTemplate(){pendingTemplateDataset=currentDataset();startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply{type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";putExtra(Intent.EXTRA_TITLE,"pick-pack-1291-${pendingTemplateDataset}.xlsx");addCategory(Intent.CATEGORY_OPENABLE)},REQ_CREATE)}
    private fun chooseFile(){startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply{type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";addCategory(Intent.CATEGORY_OPENABLE)},REQ_OPEN)}
    @Deprecated("Activity result kept for minSdk-compatible no-extra-dependency file picker")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?){super.onActivityResult(requestCode,resultCode,data);if(resultCode!=RESULT_OK)return;val uri=data?.data?:return;if(requestCode==REQ_CREATE)downloadTemplate(uri)else if(requestCode==REQ_OPEN)readSelected(uri)}
    private fun readSelected(uri:Uri){executor.execute{runCatching{contentResolver.openInputStream(uri)?.use{it.readBytes()}?:error("FILE_READ_FAILED")}.onSuccess{bytes->runOnUiThread{if(bytes.size>8*1024*1024||bytes.size<4||bytes[0]!=0x50.toByte()||bytes[1]!=0x4b.toByte()){selectedBytes=null;status.text="File không phải .xlsx hợp lệ hoặc lớn hơn 8 MB."}else{selectedBytes=bytes;selectedName=queryName(uri)?:"import.xlsx";status.text="Đã chọn: $selectedName • ${bytes.size/1024} KB\nTrạng thái: WAITING_UPLOAD"}}}.onFailure{runOnUiThread{status.text="Không đọc được file: ${it.message}"}}}}
    private fun queryName(uri:Uri):String?=runCatching{contentResolver.query(uri,arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),null,null,null)?.use{c->if(c.moveToFirst())c.getString(0)else null}}.getOrNull()
    private fun downloadTemplate(uri:Uri){status.text="Đang tải template...";executor.execute{runCatching{ImportHttp(this).getBytes("/v1/import/template?dataset=${pendingTemplateDataset}")}.onSuccess{bytes->runCatching{contentResolver.openOutputStream(uri,"w")?.use{it.write(bytes)}?:error("WRITE_FAILED")}.onSuccess{runOnUiThread{status.text="Đã lưu template ${pendingTemplateDataset}.xlsx"}}.onFailure{runOnUiThread{status.text="Không ghi được template: ${it.message}"}}}.onFailure{runOnUiThread{status.text="Không tải được template: ${it.message}"}}}}

    private fun prepareSelected(){val bytes=selectedBytes?:return show("Chọn file .xlsx trước.");val ds=currentDataset();status.text="Đang upload và validate...";commit.isEnabled=false;executor.execute{runCatching{
        val http=ImportHttp(this),parsed=http.post("/v1/import/xlsx/parse",JSONObject().put("dataset",ds).put("file_name",selectedName).put("file_base64",Base64.encodeToString(bytes,Base64.NO_WRAP)))
        val start=http.post("/v1/import/batches",JSONObject().put("dataset",ds).put("template_version",parsed.getString("template_version")).put("schema_checksum",parsed.getString("schema_checksum")).put("file_sha256",sha(bytes)))
        batchId=start.getString("import_batch_id");val rows=parsed.getJSONArray("rows"),headers=headers(ds);var offset=0;var chunkNo=0
        while(offset<rows.length()){
            val chunk=JSONArray();for(i in offset until minOf(offset+500,rows.length()))chunk.put(normalize(ds,rows.getJSONObject(i),headers));
            val raw=chunk.toString();http.post("/v1/import/batches/$batchId/chunks",JSONObject().put("chunk_no",chunkNo).put("chunk_checksum",sha(raw.toByteArray(Charsets.UTF_8))).put("rows",chunk));offset+=500;chunkNo++
        }
        http.post("/v1/import/batches/$batchId/preview",JSONObject())
    }.onSuccess{p->runOnUiThread{val s=p.optJSONObject("summary")?:JSONObject();preview.text="Tổng: ${s.optInt("row_count")}\nThêm: ${s.optInt("inserts")} • Cập nhật: ${s.optInt("updates")} • Không đổi: ${s.optInt("noops")}\nLỗi: ${s.optInt("rejected")}";commit.isEnabled=s.optInt("rejected")==0;status.text="Preview hoàn tất. Kiểm tra trước khi xác nhận."}}.onFailure{e->runOnUiThread{status.text=if(e.message?.contains("NETWORK")==true)"Mất mạng. File vẫn được giữ ở WAITING_UPLOAD." else "Import chưa sẵn sàng: ${e.message}"}}}}
    private fun commitBatch(){if(batchId.isBlank())return;commit.isEnabled=false;status.text="Đang commit...";executor.execute{runCatching{ImportHttp(this).post("/v1/import/batches/$batchId/commit",JSONObject())}.onSuccess{runOnUiThread{status.text="Đã import thành công và ghi audit/event.";preview.text="Batch $batchId đã COMMITTED.";batchId="";selectedBytes=null;loadHistory()}}.onFailure{runOnUiThread{status.text="Không commit được: ${it.message}";commit.isEnabled=true}}}}
    private fun loadHistory(){executor.execute{runCatching{ImportHttp(this).getJson("/v1/import/history?limit=20")}.onSuccess{j->runOnUiThread{historyBox.removeAllViews();val rows=j.optJSONArray("items")?:j.optJSONArray("batches")?:j.optJSONArray("history")?:JSONArray();if(rows.length()==0)historyBox.addView(TextView(this).apply{text="Chưa có lịch sử Import."});for(i in 0 until rows.length()){val x=rows.optJSONObject(i)?:continue;val box=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(0,dp(7),0,dp(7))};box.addView(TextView(this).apply{text="${x.optString("dataset")} • ${x.optString("state")}\n${x.optString("import_batch_id")}";textSize=11f;setTextColor(Color.DKGRAY)});if(x.optString("state")=="COMMITTED")box.addView(actionButton("ROLLBACK CORRECTION"){rollback(x.optString("import_batch_id"))},LinearLayout.LayoutParams(-1,dp(42)));historyBox.addView(box)}}}.onFailure{runOnUiThread{if(historyBox.childCount==0)historyBox.addView(TextView(this).apply{text="Không tải được lịch sử: ${it.message}"})}}}}
    private fun rollback(id:String){status.text="Đang tạo rollback correction...";executor.execute{runCatching{ImportHttp(this).post("/v1/import/batches/$id/rollback",JSONObject())}.onSuccess{runOnUiThread{status.text="Đã tạo correction rollback cho batch.";loadHistory()}}.onFailure{runOnUiThread{status.text="Rollback thất bại: ${it.message}"}}}}

    private fun normalize(ds:String,row:JSONObject,headers:List<String>):JSONObject{val out=JSONObject();for(h in headers){var v:Any?=row.opt(h);if(h=="available")v=if(v==true||v==1||listOf("1","true","TRUE","Có","CO","ACTIVE","Hoạt động").contains(v?.toString()))1 else 0;if(h=="ordinal")v=(v?.toString()?.toDoubleOrNull()?:0.0).coerceAtLeast(0.0).toInt();if(h=="metadata_json"){val s=v?.toString()?.ifBlank{"{}"}?:"{}";v=runCatching{JSONObject(s);s}.getOrDefault("{}")}else if(v !is Number)v=v?.toString()?.trim().orEmpty();out.put(h,v)}return out}
    private fun headers(ds:String)=when(ds){"employees"->listOf("mnv","full_name","phone","main_position","supplier","department","site","warehouse","start_date","note");"catalogs"->listOf("namespace","ordinal","value");"pack_table"->listOf("pack_table","shift","user_pack","label","status_label","available");else->listOf("resource_id","status_label","available","metadata_json")}
    private fun sha(bytes:ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){(it.toInt()and 0xff).toString(16).padStart(2,'0')}
    private fun show(s:String){status.text=s}
    private fun dp(v:Int)=(v*resources.displayMetrics.density).toInt()
    private fun matchWrap()=LinearLayout.LayoutParams(-1,-2)
    private fun actionButton(label:String,click:()->Unit)=Button(this).apply{text=label;textSize=10f;setOnClickListener{click()}}
    private fun card()=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(dp(12),dp(12),dp(12),dp(12));setBackgroundColor(Color.WHITE);layoutParams=LinearLayout.LayoutParams(-1,-2).apply{setMargins(0,dp(7),0,dp(7))}}

    companion object{private const val REQ_CREATE=7701;private const val REQ_OPEN=7702}
}

private class ImportHttp(context:Context){
    private val app=context.applicationContext
    private fun baseAndToken():Pair<String,String>{val d=M2ServiceTransport(app).discoverySnapshot()?:error("DISCOVERY_UNAVAILABLE"),base=d.optString("service_url").trimEnd('/'),token=app.getSharedPreferences("pp_m2_service_transport",Context.MODE_PRIVATE).getString("service_token",null).orEmpty();if(d.optString("authority_mode")!="SERVICE_PRIMARY")error("SERVICE_NOT_WRITE_AUTHORITY");if(!base.startsWith("https://")||token.isBlank())error("SERVICE_SESSION_UNAVAILABLE");return base to token}
    fun getJson(path:String):JSONObject=JSONObject(String(request(path,"GET",null),Charsets.UTF_8))
    fun getBytes(path:String):ByteArray=request(path,"GET",null)
    fun post(path:String,body:JSONObject):JSONObject=JSONObject(String(request(path,"POST",body.toString().toByteArray(Charsets.UTF_8)),Charsets.UTF_8))
    private fun request(path:String,method:String,body:ByteArray?):ByteArray{val(base,token)=baseAndToken();var c:HttpURLConnection?=null;try{c=(URL(base+path).openConnection() as HttpURLConnection).apply{requestMethod=method;connectTimeout=5000;readTimeout=12000;setRequestProperty("Authorization","Bearer $token");setRequestProperty("Accept","application/json, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");if(body!=null){doOutput=true;setRequestProperty("Content-Type","application/json; charset=utf-8")}};if(body!=null)c.outputStream.use{it.write(body)};val code=c.responseCode,stream=if(code in 200..299)c.inputStream else c.errorStream,bytes=stream?.use{it.readBytes()}?:ByteArray(0);if(code !in 200..299){val err=runCatching{JSONObject(String(bytes,Charsets.UTF_8)).optJSONObject("error")?.optString("code")}.getOrNull();error(err?.ifBlank{"HTTP_$code"}?:"HTTP_$code")};return bytes}catch(e:Exception){if(e.message?.startsWith("HTTP_")==true||e.message?.contains("IMPORT_")==true||e.message?.contains("SERVICE_")==true)throw e;throw IllegalStateException("NETWORK_${e.javaClass.simpleName}",e)}finally{c?.disconnect()}}
}

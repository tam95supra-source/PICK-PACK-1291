package vn.pickpack1291.app.beta

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

object AppHistory {
    private const val PREFS="pp1291_app_history"
    private const val KEY="items"
    private const val LIMIT=200

    private val SAFE_KEYS=setOf(
        "event_id","mnv","shift","work_choice","pda_serial","user_pick","pack_table","user_pack",
        "labor_type","time_marker","deduct_staff","login_id","role","status","main_position","supplier","department"
    )

    @Synchronized
    fun record(context:Context,action:String,synced:Boolean,detail:String="",request:JSONObject?=null){
        val prefs=context.applicationContext.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
        val old=runCatching{JSONArray(prefs.getString(KEY,"[]"))}.getOrDefault(JSONArray())
        val item=JSONObject()
            .put("at",System.currentTimeMillis())
            .put("action",action)
            .put("synced",synced)
            .put("detail",detail.take(180))
        val safe=safeRequest(request)
        if(safe.length()>0)item.put("context",safe)
        val out=JSONArray().put(item)
        for(i in 0 until minOf(old.length(),LIMIT-1))out.put(old.optJSONObject(i)?:continue)
        prefs.edit().putString(KEY,out.toString()).apply()
    }

    private fun safeRequest(source:JSONObject?):JSONObject{
        val out=JSONObject()
        if(source==null)return out
        SAFE_KEYS.forEach{key->
            if(!source.has(key)||source.isNull(key))return@forEach
            when(val value=source.opt(key)){
                is Boolean->out.put(key,value)
                is Number->out.put(key,value)
                else->{
                    val text=value?.toString()?.trim().orEmpty()
                    if(text.isNotBlank())out.put(key,text.take(120))
                }
            }
        }
        return out
    }

    fun items(context:Context):JSONArray=runCatching{
        JSONArray(context.applicationContext.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getString(KEY,"[]"))
    }.getOrDefault(JSONArray())

    fun label(action:String)=when(action){
        "enter"->"Vào ca";"exit"->"Ra ca";"resource_change"->"Đổi tài nguyên";"labor_start"->"Bắt đầu công nhật";"labor_finish"->"Hoàn thành công nhật";
        "change_password"->"Đổi mật khẩu";"change_email"->"Đổi mail";"account_upsert"->"Cập nhật tài khoản";"account_status"->"Đổi trạng thái tài khoản";
        "staff_upsert"->"Thêm / sửa nhân sự";"staff_delete"->"Xóa nhân sự";"diagnostic_log"->"Gửi log";else->action
    }
}

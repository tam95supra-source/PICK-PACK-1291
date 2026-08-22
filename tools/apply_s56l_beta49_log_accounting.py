#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'app/src/main/java/vn/pickpack1291/app/beta/LocalLogManager.kt'
MARK='S56L_BETA49_LOG_ACCOUNTING_V2'
COMPAT='S56_BETA49_LOG_ACCOUNTING_V1'
s=P.read_text(encoding='utf-8')
if MARK in s and COMPAT in s:
    print('S56L already applied')
    raise SystemExit(0)

anchor='    private const val KEY_DAILY = "last_daily_log"\n'
if anchor not in s: raise SystemExit('S56L KEY_DAILY anchor missing')
consts='''    private const val KEY_GENERATED_BYTES = "generated_bytes"\n    private const val KEY_SENT_BYTES = "sent_bytes"\n    private const val KEY_LAST_BYTES = "last_bytes"\n    private const val KEY_LAST_AT = "last_at"\n'''
if 'KEY_GENERATED_BYTES' not in s:
    s=s.replace(anchor,anchor+consts,1)

# Replace or insert summary independent of S54/S56 exact prior shape.
a=s.find('    fun summary(context:Context):String{')
if a<0:
    a=s.find('    fun sendManualReport(')
    if a<0: raise SystemExit('S56L summary insertion anchor missing')
    b=a
else:
    # Include a preceding marker comment in the replacement span when present.
    line_start=s.rfind('\n',0,a)+1
    if 'S54_BETA48_OWNER_10_FIXES' in s[max(0,line_start-100):a] or 'S56' in s[max(0,line_start-100):a]:
        a=line_start
    b=s.find('\n    fun sendManualReport(',a)
    if b<0: raise SystemExit('S56L summary end missing')
summary='''    // S56_BETA49_LOG_ACCOUNTING_V1\n    // S56L_BETA49_LOG_ACCOUNTING_V2\n    fun summary(context:Context):String{\n        val files=logDir(context).listFiles()?.filter{it.isFile}.orEmpty()\n        val pendingBytes=files.sumOf{it.length()}\n        val prefs=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE)\n        val generated=prefs.getLong(KEY_GENERATED_BYTES,0L)\n        val sent=prefs.getLong(KEY_SENT_BYTES,0L)\n        val lastBytes=prefs.getLong(KEY_LAST_BYTES,0L)\n        val lastAt=prefs.getLong(KEY_LAST_AT,0L)\n        fun size(v:Long)=when{v<1024L->"$v B";v<1024L*1024L->String.format(Locale.US,"%.1f KB",v/1024.0);else->String.format(Locale.US,"%.1f MB",v/(1024.0*1024.0))}\n        val at=if(lastAt<=0L)"—" else SimpleDateFormat("HH:mm:ss dd/MM/yyyy",Locale.US).format(Date(lastAt))\n        return "Đang lưu ${files.size} tệp • ${size(pendingBytes)} | Đã ghi ${size(generated)} | Đã gửi ${size(sent)} | Gần nhất ${size(lastBytes)} • $at"\n    }\n'''
s=s[:a]+summary+s[b:]

old='uploadFile(api, file, "MANUAL") { r -> if (r.ok) file.delete(); callback(r) }'
new='uploadFile(api, file, "MANUAL") { r -> if (r.ok) { recordSent(context,file.length()); file.delete() }; callback(r) }'
if old in s: s=s.replace(old,new,1)
elif 'recordSent(context,file.length())' not in s: raise SystemExit('S56L manual upload anchor missing')

s=s.replace('uploadNext(api, files, 0)','uploadNext(context, api, files, 0)')
s=s.replace('private fun uploadNext(api: BetaApiClient, files: List<File>, index: Int)','private fun uploadNext(context: Context, api: BetaApiClient, files: List<File>, index: Int)')
s=s.replace('if (r.ok) f.delete()','if (r.ok) { recordSent(context,f.length()); f.delete() }')
s=s.replace('uploadNext(api, files, index + 1)','uploadNext(context, api, files, index + 1)')

old_write='''    private fun write(context: Context, prefix: String, content: String): File {\n        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US).format(Date())\n        return File(logDir(context), "${prefix}_${stamp}.log").apply { writeText(content) }\n    }'''
new_write='''    private fun recordSent(context:Context,bytes:Long){\n        val p=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE)\n        p.edit().putLong(KEY_SENT_BYTES,p.getLong(KEY_SENT_BYTES,0L)+bytes).apply()\n    }\n    private fun write(context: Context, prefix: String, content: String): File {\n        val stamp=SimpleDateFormat("yyyyMMdd_HHmmss_SSS",Locale.US).format(Date())\n        val file=File(logDir(context),"${prefix}_${stamp}.log").apply{writeText(content)}\n        val bytes=file.length();val p=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE)\n        p.edit().putLong(KEY_GENERATED_BYTES,p.getLong(KEY_GENERATED_BYTES,0L)+bytes).putLong(KEY_LAST_BYTES,bytes).putLong(KEY_LAST_AT,System.currentTimeMillis()).apply()\n        return file\n    }'''
if old_write in s: s=s.replace(old_write,new_write,1)
elif 'private fun recordSent(context:Context,bytes:Long)' not in s:
    raise SystemExit('S56L write anchor missing')

required=[MARK,COMPAT,'KEY_GENERATED_BYTES','KEY_SENT_BYTES','recordSent(context,file.length())','recordSent(context,f.length())','uploadNext(context, api, files, 0)']
for x in required:
    if x not in s: raise SystemExit('S56L contract missing: '+x)
P.write_text(s,encoding='utf-8')
print('Applied S56L Beta49 persistent log accounting V2')

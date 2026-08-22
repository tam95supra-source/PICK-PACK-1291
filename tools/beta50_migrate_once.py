#!/usr/bin/env python3
from pathlib import Path
import re

ops=Path('app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt')
s=ops.read_text()

ccdc='businessCard(R.drawable.ic_pp_ccdc,"Quản lý CCDC","Quản lý công cụ dụng cụ",isAdmin()){TopNotice.show(this,"Quản lý CCDC đang được chuẩn bị.",TopNotice.Kind.INFO)}'
assert s.count(ccdc)==1
s=s.replace(ccdc,ccdc+',\n            businessCard(R.drawable.ic_pp_document,"Quản lý biên bản","Theo dõi và quản lý biên bản",isAdmin()){TopNotice.show(this,"Quản lý biên bản đang chờ xây dựng.",TopNotice.Kind.INFO)}',1)
assert s.count('body.addView(businessRow(cards[6],Space(this)))')==1
s=s.replace('body.addView(businessRow(cards[6],Space(this)))','body.addView(businessRow(cards[6],cards[7]))',1)

a=s.index('    private fun syncScreen(){');b=s.index('    private fun pdaExchangeScreen(){',a);q=s[a:b]
q=q.replace('Đang kiểm tra thiết bị, Service và các phiên kết nối.','Đang kiểm tra PDA, Service và Google Sheet.')
q=q.replace('val deviceBox=column(bg);val serviceBox=column(bg);val userBox=column(bg);val appBox=column(bg)','val pdaBox=column(bg);val serviceBox=column(bg);val sheetBox=column(bg);val otherBox=column(bg)')
q=q.replace('body.addView(deviceBox,matchWrap());body.addView(serviceBox,matchWrap());body.addView(userBox,matchWrap());body.addView(appBox,matchWrap())','body.addView(pdaBox,matchWrap());body.addView(serviceBox,matchWrap());body.addView(sheetBox,matchWrap());body.addView(otherBox,matchWrap())')
q=q.replace('deviceBox','pdaBox')
q=q.replace('val syncText=when{pending>0->"Còn $pending mục chờ gửi";active->"Đang trao đổi dữ liệu";else->"Đã đồng bộ"}','val syncText=when{active->"Đang trao đổi dữ liệu";pending>0->"Đang chờ đồng bộ";lastConnected==true->"Đã đồng bộ";else->"Chưa xác định"}')
q=q.replace('overviewTitle.text=when{lastConnected==false->"Chưa kết nối được Service";pending>0->"Còn $pending mục chờ gửi";else->"Hệ thống đang hoạt động bình thường"}','overviewTitle.text=when{lastConnected==false->"Chưa kết nối được Service";active->"Đang đồng bộ dữ liệu";pending>0->"Có dữ liệu đang chờ đồng bộ";else->"Hệ thống đang hoạt động bình thường"}')
q=q.replace('overviewSub.text="$syncText • $network"','overviewSub.text="$network • PDA: $syncText"')
q=q.replace('section("TRÊN THIẾT BỊ")','section("THÔNG TIN TRÊN PDA")')
q=q.replace('"Trạng thái đồng bộ" to syncText,"Dữ liệu chờ gửi" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Luồng trao đổi dữ liệu" to if(active)"Đang hoạt động" else "Đang nghỉ","Ngày nghiệp vụ hiện tại"','"Trạng thái đồng bộ trên PDA" to syncText,"Hàng đợi đồng bộ trên PDA" to pending.toString(),"Dung lượng cache" to humanBytes(operationalStore.storageBytes()),"Ngày nghiệp vụ hiện tại"')
gap='pdaBox.addView(gap(8))';assert gap in q
q=q.replace(gap,gap+';otherBox.removeAllViews();otherBox.addView(section("THÔNG TIN ĐỒNG BỘ KHÁC"));otherBox.addView(details(listOf("Luồng trao đổi dữ liệu" to if(active)"Đang hoạt động" else "Đang nghỉ","Trạng thái mạng" to network,"Cơ chế gửi lại" to if(pending>0)"Tự động khi kết nối phù hợp" else "Không có dữ liệu cần gửi lại")));otherBox.addView(gap(8))',1)
q=q.replace('section("DỊCH VỤ VÀ DỮ LIỆU TRUNG TÂM")','section("THÔNG TIN TRÊN SERVICE")')
old='serviceBox.removeAllViews();serviceBox.addView(section("THÔNG TIN TRÊN SERVICE"));serviceBox.addView(info("Đang kiểm tra Service..."));val started=android.os.SystemClock.elapsedRealtime()';assert q.count(old)==1
q=q.replace(old,'serviceBox.removeAllViews();serviceBox.addView(section("THÔNG TIN TRÊN SERVICE"));serviceBox.addView(info("Đang kiểm tra Service..."));sheetBox.removeAllViews();sheetBox.addView(section("THÔNG TIN TRÊN GOOGLE SHEET"));sheetBox.addView(info("Đang kiểm tra trạng thái sao chép Google Sheet..."));val started=android.os.SystemClock.elapsedRealtime()',1)
old='serviceBox.removeAllViews();serviceBox.addView(section("THÔNG TIN TRÊN SERVICE"));val rt=';assert q.count(old)==1
q=q.replace(old,'serviceBox.removeAllViews();serviceBox.addView(section("THÔNG TIN TRÊN SERVICE"));sheetBox.removeAllViews();sheetBox.addView(section("THÔNG TIN TRÊN GOOGLE SHEET"));val rt=',1)
old='serviceBox.addView(details(listOf("Dịch vụ" to "Chưa phản hồi","Độ trễ lần kiểm tra" to "$rt ms","Dữ liệu trên PDA" to "Vẫn được lưu an toàn","Trạng thái gửi" to "Sẽ thử lại khi có kết nối")));serviceBox.addView(gap(8));loadDevice()';assert q.count(old)==1
q=q.replace(old,'serviceBox.addView(details(listOf("Trạng thái Service" to "Chưa phản hồi","Độ trễ lần kiểm tra" to "$rt ms","Dữ liệu trên PDA" to "Vẫn được lưu an toàn")));sheetBox.addView(details(listOf("Trạng thái Google Sheet" to "Chưa lấy được từ Service","Lần sao chép thành công" to "Chưa xác định")));serviceBox.addView(gap(8));sheetBox.addView(gap(8));loadDevice()',1)
old='serviceBox.addView(details(listOf("Dịch vụ" to "Đang hoạt động","Độ trễ tới Service" to "$rt ms","Nguồn dữ liệu đang dùng" to authorityVi(a.optString("mode").ifBlank{j.optString("authority_mode")}),"Mốc dữ liệu hệ thống" to a.optLong("authority_seq",j.optLong("server_seq",0L)).toString(),"Bản sao Google" to replicaVi(rep.optString("state")),"Bản sao Google còn chờ" to rep.optInt("pending_count",0).toString(),"Lần sao chép thành công" to timeVi(rep.optString("last_success_at")))));serviceBox.addView(gap(8));loadDevice()';assert q.count(old)==1
q=q.replace(old,'serviceBox.addView(details(listOf("Trạng thái Service" to "Đang hoạt động","Độ trễ tới Service" to "$rt ms","Nguồn dữ liệu đang dùng" to authorityVi(a.optString("mode").ifBlank{j.optString("authority_mode")}),"Mốc dữ liệu trên Service" to a.optLong("authority_seq",j.optLong("server_seq",0L)).toString())));sheetBox.addView(details(listOf("Trạng thái Google Sheet" to replicaVi(rep.optString("state")),"Bản ghi chờ sao chép Google Sheet" to rep.optInt("pending_count",0).toString(),"Lần sao chép thành công" to timeVi(rep.optString("last_success_at")))));serviceBox.addView(gap(8));sheetBox.addView(gap(8));loadDevice()',1)
q,n=re.subn(r'\n        fun loadUsers\(\)\{.*?\n        \}\n        fun loadApp\(\)\{.*?\}\n','\n',q,count=1,flags=re.S);assert n==1
q=q.replace('fun load(){loadDevice();loadApp();loadService();loadUsers()}','fun load(){loadDevice();loadService()}')
q=q.replace('TopNotice.show(this,"Đã yêu cầu đồng bộ dữ liệu đang chờ.",TopNotice.Kind.INFO)','TopNotice.show(this,"Đã yêu cầu đồng bộ dữ liệu.",TopNotice.Kind.INFO)')
s=s[:a]+q+s[b:]

marker='body.addView(section("CẬP NHẬT PHIÊN BẢN"))';assert s.count(marker)==1
appinfo='body.addView(section("THÔNG TIN ỨNG DỤNG"))\n        val deviceName="${Build.MANUFACTURER} ${Build.MODEL}".trim()\n        body.addView(details(listOf("Tên thiết bị" to deviceName,"Hệ điều hành" to "Android ${Build.VERSION.RELEASE}","Kênh phát hành" to if(BuildConfig.CHANNEL=="BETA")"Bản thử nghiệm" else "Bản ổn định","Phiên bản ứng dụng" to BuildConfig.VERSION_NAME,"Mã phiên bản" to BuildConfig.VERSION_CODE.toString())))\n        '+marker
s=s.replace(marker,appinfo,1)
s=s.replace('body.addView(info("Phiên bản hiện tại: ${BuildConfig.VERSION_NAME}"))\n        body.addView(gap(7))\n','',1)
s=s.replace('body.addView(section("Thiết bị"))\n        body.addView(info("Android ${Build.VERSION.RELEASE} • ${Build.MANUFACTURER} ${Build.MODEL}"))\n','',1)
s=s.replace('else "Còn $pending mục"} | Dịch vụ','else "Đang chờ đồng bộ"} | Dịch vụ',1)
s=s.replace('syncStatusText?.text=if(pending>0)"Còn $pending mục"','syncStatusText?.text=if(pending>0)"Đang chờ"',1)
s=s.replace('R.drawable.ic_pp_ccdc->intArrayOf(Color.rgb(71,85,105),Color.rgb(100,116,139))\n            else->','R.drawable.ic_pp_ccdc->intArrayOf(Color.rgb(71,85,105),Color.rgb(100,116,139))\n            R.drawable.ic_pp_document->intArrayOf(Color.rgb(79,70,229),Color.rgb(99,102,241))\n            else->',1)
s=s.replace('v.contains("Thiết bị",true)->R.drawable.ic_pp_device\n        else->','v.contains("Thiết bị",true)->R.drawable.ic_pp_device\n        v.contains("Ứng dụng",true)->R.drawable.ic_pp_device\n        v.contains("Google Sheet",true)->R.drawable.ic_pp_sync\n        v.contains("Service",true)->R.drawable.ic_pp_service\n        v.contains("PDA",true)->R.drawable.ic_pp_device\n        else->',1)
for forbidden in ('NGƯỜI DÙNG ĐANG KẾT NỐI','service_connections','Còn $pending mục'): assert forbidden not in s,forbidden
for required in ('Quản lý biên bản','THÔNG TIN TRÊN PDA','THÔNG TIN TRÊN SERVICE','THÔNG TIN TRÊN GOOGLE SHEET','THÔNG TIN ĐỒNG BỘ KHÁC','THÔNG TIN ỨNG DỤNG'): assert required in s,required
ops.write_text(s)

build=Path('app/build.gradle.kts');t=build.read_text()
start=t.index('\nval generateS10Operations = tasks.register<Exec>("generateS10Operations")')
end=t.index('\nandroid {',start)
t=t[:start]+t[end:]
t=t.replace('versionCode = 54','versionCode = 56',1).replace('versionName = "0.4.2-beta.48"','versionName = "0.4.2-beta.50"',1)
t=t.replace('\ntasks.named("preBuild").configure { dependsOn(generateS10Operations) }\n','\n')
assert 'generateS10Operations' not in t and 'apply_m2_android_transport_patch.py' not in t
build.write_text(t)

Path('app/src/main/res/drawable/ic_pp_document.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M6,2h9l5,5v15H6zM14,3.5V8h4.5zM9,11h8v1.5H9zM9,14h8v1.5H9zM9,17h6v1.5H9z" />
</vector>
''')
print('BETA50_MIGRATION_OK')

# Quy tắc lưu trữ APK — PICK PACK 1291

Áp dụng từ Beta47 trở đi.

## Bản thử nghiệm (Beta)
Sau khi APK build và ký thành công:
1. Giữ artifact/release tương ứng trên GitHub theo quy trình phát hành.
2. Sao lưu thêm đúng file APK đã ký lên Google Drive:
   - `PICK PACK 1291 - CHÍNH THỨC/PHÁT HÀNH APK/BẢN THỬ NGHIỆM`
3. Tên file trên Drive phải giữ rõ phiên bản, ví dụ: `pick-pack-1291-public-beta-0.4.2-beta.47.apk`.
4. Chỉ coi bước sao lưu Drive là hoàn tất khi file đã xuất hiện trong đúng thư mục và có thể đọc lại metadata.

## Bản ổn định (Stable)
Sau khi APK Stable được phép phát hành, build và ký thành công:
1. Giữ artifact/release tương ứng trên GitHub.
2. Sao lưu thêm đúng file APK đã ký lên Google Drive:
   - `PICK PACK 1291 - CHÍNH THỨC/PHÁT HÀNH APK/BẢN ỔN ĐỊNH`
3. Không đưa bản Beta vào thư mục Stable và ngược lại.

## Nguyên tắc
- GitHub là nguồn phát hành/kỹ thuật chính.
- Google Drive là bản sao lưu bổ sung cho APK phát hành.
- Không thay đổi hoặc tạo lại cây thư mục Drive khi các thư mục chuẩn nêu trên vẫn tồn tại.
- Không sao lưu APK chưa ký hoặc APK không khớp checksum của build PASS.

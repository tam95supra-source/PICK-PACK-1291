from pathlib import Path
import shutil

ROOT = Path('.')


def replace(path: str, old: str, new: str):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        print(f'WARN replacement not found in {path}: {old[:80]!r}')
        return
    p.write_text(text.replace(old, new), encoding='utf-8')
    print('patched', path)

# UI/runtime terminology: no Supabase projection/server authority wording.
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt',
    'syncText?.text = "●  REALTIME • Seq ${status.serverSeq} • chờ Sheet ACK: ${status.projectionPending}"',
    'syncText?.text = "●  GOOGLE SHEET LIVE • Rev ${status.serverSeq}"'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt',
    'syncText?.setTextColor(if (status.projectionPending == 0) green else orange)',
    'syncText?.setTextColor(green)'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt',
    'syncText?.text = "●  Mất kết nối realtime"',
    'syncText?.text = "●  Mất kết nối Google Sheet"'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt',
    'body.addView(info("Server tự xác định CHƯA VÀO / ĐANG TRONG PHIÊN / ĐÃ HẾT PHIÊN. Không còn nút VÀO/RA tách rời."))',
    'body.addView(info("Google Sheet xác định CHƯA VÀO / ĐANG TRONG PHIÊN / ĐÃ HẾT PHIÊN. Không còn nút VÀO/RA tách rời."))'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/FullBetaActivity.kt',
    'syncText?.text="●  FULL BETA • Seq ${j.optLong("server_seq")} • chờ Sheet ACK ${j.optInt("projection_pending")}"',
    'syncText?.text="●  GOOGLE SHEET LIVE • Rev ${j.optLong("server_seq")}"'
)

replace(
    'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt',
    'val sync=info("Đang đọc trạng thái server...")',
    'val sync=info("Đang đọc trạng thái Google Sheet...")'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt',
    'sync.text="FULL BETA • Server seq ${j.optLong("server_seq")} • chờ Sheet ACK ${j.optInt("projection_pending")} • công nhật đang làm ${j.optInt("labor_active")}"',
    'sync.text="FULL BETA • Google Sheet rev ${j.optLong("server_seq")} • công nhật đang làm ${j.optInt("labor_active")}"'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt',
    'else sync.text="Không đọc được trạng thái server"',
    'else sync.text="Không đọc được trạng thái Google Sheet"'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt',
    'setMessage("Server đã ACK diagnostic event $event")',
    'setMessage("Google Drive đã ACK diagnostic event $event")'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt',
    'their writes are still revalidated atomically by the backend.',
    'their writes are still revalidated under the Apps Script / Google Sheet transaction lock.'
)
replace(
    'app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt',
    'Đổi vị trí/PDA/User Pick/Bàn Pack theo transaction atomic. Conflict không làm mất tài nguyên cũ.',
    'Đổi vị trí/PDA/User Pick/Bàn Pack theo transaction khóa Google Sheet. Conflict không làm mất tài nguyên cũ.'
)

p = ROOT / 'app/src/main/java/vn/pickpack1291/app/beta/ForegroundSyncCoordinator.kt'
text = p.read_text(encoding='utf-8')
text = text.replace('Foreground-only server sequence watcher.', 'Foreground-only Google Sheet revision watcher.')
text = text.replace('server_seq is only a change detector.', 'server_seq is the Apps Script / Google Sheet revision change detector.')
p.write_text(text, encoding='utf-8')

# Remove implementation artifacts that violated the approved architecture.
for rel in [
    'supabase',
    'google-apps-script/PICK_PACK_PROJECTION.gs',
    '.github/workflows/apply-s02-realtime.yml',
    '.github/workflows/apply-fixed-signing-beta2.yml',
    'scripts/apply_s02_realtime.py',
    'scripts/apply_fixed_signing_beta2.py',
    'scripts/apply_fixed_signing_beta2_runner.py',
    'app/src/main/assets/s02-realtime-build.txt',
]:
    p = ROOT / rel
    if p.is_dir():
        shutil.rmtree(p)
        print('removed dir', rel)
    elif p.exists():
        p.unlink()
        print('removed', rel)

# This is intentionally one-shot; remove its own runner after applying.
for rel in ['scripts/apply_gsheet_cleanup.py', '.github/workflows/apply-gsheet-cleanup.yml']:
    p = ROOT / rel
    if p.exists():
        p.unlink()
        print('removed one-shot', rel)

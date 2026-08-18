#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "google-apps-script/PICK_PACK_API.gs"
text = path.read_text(encoding="utf-8")

MARKER = "v0.4.2 S17 SQLITE CRASH RECOVERY"
if MARKER in text:
    print("S17 SQLite recovery transform already present")
    raise SystemExit(0)

old = "function ppSyncStatus_(){const floor=ppRetentionSweepS15_();return {ok:true,business_date:ppBusinessIso_(),server_seq:ppRevision_(),master_revision:ppMasterRevision_(),last_event_at:ppNowIso_(),projection_pending:0,mode:'APP_GSHEET',sync_engine:'S15_LOCAL_FIRST_45D',retention_floor:floor,retention_epoch:ppRetentionEpochS15_(),day_revisions:ppDayRevisionsS15_()};}"
new = """// === v0.4.2 S17 SQLITE CRASH RECOVERY ===\n// Beta15/16 crash on some Android 11 PDA builds while opening the new local SQLite store.\n// Keep the full day revision manifest but blank retention_floor so legacy S15 clients skip\n// OperationalSyncEngine.reconcile. Beta17 derives the same 45-day floor locally and resumes sync.\nfunction ppSyncStatus_(){const floor=ppRetentionSweepS15_();return {ok:true,business_date:ppBusinessIso_(),server_seq:ppRevision_(),master_revision:ppMasterRevision_(),last_event_at:ppNowIso_(),projection_pending:0,mode:'APP_GSHEET',sync_engine:'S15_LOCAL_FIRST_45D',retention_floor:'',server_retention_floor:floor,retention_epoch:ppRetentionEpochS15_(),day_revisions:ppDayRevisionsS15_(),legacy_sqlite_recovery:true,local_sync_min_version:'0.4.2-beta.17'};}"""
count = text.count(old)
if count != 1:
    raise SystemExit(f"S17 sync-status anchor expected 1, got {count}")
text = text.replace(old, new, 1)

health_old = "sync_engine:'S15_LOCAL_FIRST_45D',retention_days:45,editable_days:2};}"
health_new = "sync_engine:'S15_LOCAL_FIRST_45D',retention_days:45,editable_days:2,recovery_engine:'S17_SQLITE_RECOVERY'};}"
count = text.count(health_old)
if count != 1:
    raise SystemExit(f"S17 health anchor expected 1, got {count}")
text = text.replace(health_old, health_new, 1)

path.write_text(text, encoding="utf-8")
print("S17 SQLite crash recovery GAS patch applied")

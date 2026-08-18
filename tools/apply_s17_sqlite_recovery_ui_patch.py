#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app/src/main/java/vn/pickpack1291/app/beta/OperationsActivity.kt"
text = path.read_text(encoding="utf-8")

old = '''                if(status.connected && status.businessDate.isNotBlank() && status.retentionFloor.isNotBlank()) {
                    operationalSync.reconcile(status.businessDate,status.retentionFloor,status.retentionEpoch,status.dayRevisions)
                }
'''
new = '''                if(status.connected && status.businessDate.isNotBlank()) {
                    val localFloor=status.retentionFloor.ifBlank{
                        runCatching{java.time.LocalDate.parse(status.businessDate).minusDays(44).toString()}.getOrDefault("")
                    }
                    if(localFloor.isNotBlank()) operationalSync.reconcile(status.businessDate,localFloor,status.retentionEpoch,status.dayRevisions)
                }
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"S17 local sync recovery anchor expected 1, got {count}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("S17 SQLite recovery UI patch applied")

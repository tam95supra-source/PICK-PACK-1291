PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS authority_transitions (
  transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_epoch INTEGER NOT NULL,
  to_epoch INTEGER NOT NULL,
  from_mode TEXT NOT NULL,
  to_mode TEXT NOT NULL,
  from_generation TEXT NOT NULL,
  to_generation TEXT NOT NULL,
  reason TEXT NOT NULL,
  initiated_by TEXT NOT NULL,
  checkpoint_epoch INTEGER,
  checkpoint_seq INTEGER,
  validation_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_authority_transitions_epoch ON authority_transitions(to_epoch,transition_id);

CREATE TABLE IF NOT EXISTS fallback_event_inbox (
  event_id TEXT PRIMARY KEY,
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  service_generation TEXT NOT NULL,
  event_json TEXT NOT NULL,
  checksum TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'GOOGLE_FALLBACK',
  ingest_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(ingest_status IN ('PENDING','APPLIED','CONFLICT','REJECTED')),
  received_at TEXT NOT NULL,
  applied_at TEXT,
  last_error TEXT,
  UNIQUE(authority_epoch,authority_seq)
);
CREATE INDEX IF NOT EXISTS idx_fallback_event_inbox_status ON fallback_event_inbox(ingest_status,authority_epoch,authority_seq);

CREATE TABLE IF NOT EXISTS recovery_runs (
  recovery_id TEXT PRIMARY KEY,
  recovery_type TEXT NOT NULL CHECK(recovery_type IN ('FAILBACK','D1_REBUILD_FROM_GOOGLE','GOOGLE_REBUILD_FROM_D1','VERIFY_ONLY')),
  from_generation TEXT,
  to_generation TEXT,
  source_authority_epoch INTEGER,
  source_authority_seq INTEGER,
  target_authority_epoch INTEGER,
  status TEXT NOT NULL CHECK(status IN ('RUNNING','VALIDATING','COMPLETE','FAILED','ABORTED')),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  validation_json TEXT NOT NULL DEFAULT '{}',
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_recovery_runs_status ON recovery_runs(status,started_at);

CREATE TABLE IF NOT EXISTS client_devices (
  device_id TEXT PRIMARY KEY,
  login_id TEXT,
  platform TEXT NOT NULL CHECK(platform IN ('ANDROID','PWA','TEST')),
  app_version TEXT NOT NULL DEFAULT '',
  channel TEXT NOT NULL DEFAULT '',
  authority_epoch INTEGER NOT NULL DEFAULT 0,
  authority_seq INTEGER NOT NULL DEFAULT 0,
  service_generation TEXT NOT NULL DEFAULT '',
  last_seen_at TEXT NOT NULL,
  last_online_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_client_devices_seen ON client_devices(last_seen_at);

CREATE TABLE IF NOT EXISTS dr_manifests (
  manifest_id TEXT PRIMARY KEY,
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  service_generation TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  employee_count INTEGER NOT NULL,
  attendance_count INTEGER NOT NULL,
  labor_count INTEGER NOT NULL,
  checksum TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dr_manifests_epoch ON dr_manifests(authority_epoch,authority_seq);

CREATE TABLE IF NOT EXISTS authority_health_samples (
  sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
  service_generation TEXT NOT NULL,
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  service_ok INTEGER NOT NULL CHECK(service_ok IN (0,1)),
  d1_ok INTEGER NOT NULL CHECK(d1_ok IN (0,1)),
  google_replication_state TEXT NOT NULL,
  pending_outbox INTEGER NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  sampled_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_authority_health_samples_time ON authority_health_samples(sampled_at);

INSERT OR IGNORE INTO schema_migrations(version,checksum)
VALUES('0002_m2_authority_recovery','M2_AUTHORITY_RECOVERY_V1_20260819');

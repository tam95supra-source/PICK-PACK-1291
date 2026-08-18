PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  checksum TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS authority_state (
  singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('SERVICE_PRIMARY','GOOGLE_FALLBACK','OFFLINE_LOCAL','RECONCILING')),
  scope TEXT NOT NULL CHECK (scope IN ('STAGING_SHADOW','PRODUCTION')),
  service_generation TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO authority_state(singleton_id,authority_epoch,authority_seq,mode,scope,service_generation,updated_at)
VALUES(1,1,0,'SERVICE_PRIMARY','STAGING_SHADOW','UNCONFIGURED',strftime('%Y-%m-%dT%H:%M:%fZ','now'));

CREATE TABLE IF NOT EXISTS business_dates (
  business_date TEXT PRIMARY KEY,
  sequence_no INTEGER NOT NULL UNIQUE,
  source TEXT NOT NULL DEFAULT 'GOOGLE_BOOTSTRAP'
);
CREATE INDEX IF NOT EXISTS idx_business_dates_sequence ON business_dates(sequence_no DESC);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  business_date TEXT NOT NULL,
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  service_generation TEXT NOT NULL,
  base_version INTEGER NOT NULL,
  new_version INTEGER NOT NULL,
  actor_id TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  device_id TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  committed_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  origin TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  checksum TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_entity_version ON events(entity_type,entity_id,new_version);
CREATE INDEX IF NOT EXISTS idx_events_business_seq ON events(business_date,authority_epoch,authority_seq);
CREATE INDEX IF NOT EXISTS idx_events_committed ON events(committed_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_events_live_authority_seq ON events(authority_epoch,authority_seq) WHERE authority_epoch > 0;

CREATE TABLE IF NOT EXISTS source_rows (
  sheet_name TEXT NOT NULL,
  row_index INTEGER NOT NULL,
  row_checksum TEXT NOT NULL,
  row_json TEXT NOT NULL,
  import_run_id TEXT NOT NULL,
  PRIMARY KEY(sheet_name,row_index)
);
CREATE INDEX IF NOT EXISTS idx_source_rows_checksum ON source_rows(sheet_name,row_checksum);

CREATE TABLE IF NOT EXISTS bootstrap_runs (
  run_id TEXT PRIMARY KEY,
  source_title TEXT NOT NULL,
  source_sheet_identity TEXT NOT NULL,
  source_modified_at TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETE','FAILED')),
  manifest_json TEXT NOT NULL,
  report_json TEXT
);

CREATE TABLE IF NOT EXISTS employees (
  mnv TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  main_position TEXT NOT NULL DEFAULT '',
  supplier TEXT NOT NULL DEFAULT '',
  department TEXT NOT NULL DEFAULT '',
  site TEXT NOT NULL DEFAULT '',
  warehouse TEXT NOT NULL DEFAULT '',
  start_date TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  source_row INTEGER NOT NULL,
  source_checksum TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(full_name);

CREATE TABLE IF NOT EXISTS catalog_values (
  namespace TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  value TEXT NOT NULL,
  source_checksum TEXT NOT NULL,
  PRIMARY KEY(namespace,value)
);
CREATE INDEX IF NOT EXISTS idx_catalog_namespace_order ON catalog_values(namespace,ordinal);

CREATE TABLE IF NOT EXISTS resources (
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  status_label TEXT NOT NULL,
  available INTEGER NOT NULL CHECK(available IN (0,1)),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  source_row INTEGER NOT NULL,
  source_checksum TEXT NOT NULL,
  PRIMARY KEY(resource_type,resource_id)
);
CREATE INDEX IF NOT EXISTS idx_resources_available ON resources(resource_type,available,resource_id);

CREATE TABLE IF NOT EXISTS resource_pack_map (
  pack_table TEXT NOT NULL,
  shift TEXT NOT NULL,
  user_pack TEXT NOT NULL,
  label TEXT NOT NULL,
  available INTEGER NOT NULL CHECK(available IN (0,1)),
  source_row INTEGER NOT NULL,
  source_checksum TEXT NOT NULL,
  PRIMARY KEY(pack_table,shift)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pack_user_shift ON resource_pack_map(shift,user_pack);

CREATE TABLE IF NOT EXISTS accounts (
  login_id TEXT PRIMARY KEY,
  verifier TEXT NOT NULL,
  verifier_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('SUPERADMIN','ADMIN','USER')),
  display_name TEXT NOT NULL,
  position TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  source_row INTEGER NOT NULL,
  source_checksum TEXT NOT NULL,
  is_shadow_test INTEGER NOT NULL DEFAULT 0 CHECK(is_shadow_test IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_accounts_status_role ON accounts(status,role);

CREATE TABLE IF NOT EXISTS auth_challenges (
  challenge_id TEXT PRIMARY KEY,
  login_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  challenge TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth_challenges_expiry ON auth_challenges(expires_at);

CREATE TABLE IF NOT EXISTS auth_sessions (
  login_id TEXT PRIMARY KEY REFERENCES accounts(login_id) ON DELETE CASCADE,
  session_id TEXT NOT NULL UNIQUE,
  device_id TEXT NOT NULL,
  issued_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS realtime_tickets (
  ticket_id TEXT PRIMARY KEY,
  login_id TEXT NOT NULL REFERENCES accounts(login_id) ON DELETE CASCADE,
  device_id TEXT NOT NULL,
  business_date TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_realtime_tickets_expiry ON realtime_tickets(expires_at);

CREATE TABLE IF NOT EXISTS attendance_sessions (
  session_id TEXT PRIMARY KEY,
  mnv TEXT NOT NULL,
  business_date TEXT NOT NULL,
  shift TEXT NOT NULL,
  work_choice TEXT NOT NULL CHECK(work_choice IN ('PICK','PACK','KHONG')),
  state TEXT NOT NULL CHECK(state IN ('NOT_ENTERED','ACTIVE','ENDED')),
  pda_serial TEXT,
  user_pick TEXT,
  pack_table TEXT,
  user_pack TEXT,
  enter_at TEXT,
  exit_at TEXT,
  entered_by TEXT,
  exited_by TEXT,
  version INTEGER NOT NULL,
  source_last_row INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  UNIQUE(mnv,business_date)
);
CREATE INDEX IF NOT EXISTS idx_attendance_date_state ON attendance_sessions(business_date,state,mnv);

CREATE TABLE IF NOT EXISTS labor_sessions (
  labor_id TEXT PRIMARY KEY,
  mnv TEXT NOT NULL,
  business_date TEXT NOT NULL,
  shift TEXT NOT NULL,
  labor_type TEXT NOT NULL,
  time_marker TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('OPEN','COMPLETED','CANCELLED')),
  start_at TEXT NOT NULL,
  end_at TEXT,
  note TEXT NOT NULL DEFAULT '',
  deduct_staff INTEGER NOT NULL DEFAULT 0 CHECK(deduct_staff IN (0,1)),
  start_event_id TEXT NOT NULL UNIQUE,
  finish_event_id TEXT UNIQUE,
  version INTEGER NOT NULL,
  source_row INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_labor_open ON labor_sessions(business_date,mnv,state);

CREATE TABLE IF NOT EXISTS resource_leases (
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  session_id TEXT NOT NULL REFERENCES attendance_sessions(session_id) ON DELETE CASCADE,
  mnv TEXT NOT NULL,
  business_date TEXT NOT NULL,
  acquired_event_id TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  PRIMARY KEY(resource_type,resource_id)
);
CREATE INDEX IF NOT EXISTS idx_resource_leases_owner ON resource_leases(session_id);

CREATE TABLE IF NOT EXISTS resource_daily_consumption (
  business_date TEXT NOT NULL,
  resource_type TEXT NOT NULL CHECK(resource_type IN ('USER_PICK','USER_PACK')),
  resource_id TEXT NOT NULL,
  mnv TEXT NOT NULL,
  first_event_id TEXT NOT NULL,
  PRIMARY KEY(business_date,resource_type,resource_id)
);

CREATE TABLE IF NOT EXISTS conflicts (
  conflict_id TEXT PRIMARY KEY,
  event_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  conflict_type TEXT NOT NULL,
  base_version INTEGER,
  current_version INTEGER,
  details_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','RESOLVED','IGNORED')),
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status,created_at);

CREATE TABLE IF NOT EXISTS mutation_assertions (
  event_id TEXT PRIMARY KEY,
  ok INTEGER NOT NULL CHECK(ok = 1)
);

CREATE TABLE IF NOT EXISTS sheet_replication_outbox (
  outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE REFERENCES events(event_id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','INFLIGHT','RETRY','SYNCED','PAUSED_SCHEMA')),
  attempt_count INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  claim_token TEXT,
  claimed_at TEXT,
  last_error_class TEXT,
  last_error TEXT,
  replicated_at TEXT,
  google_checkpoint TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_outbox_due ON sheet_replication_outbox(status,next_attempt_at,outbox_id);

CREATE TABLE IF NOT EXISTS replication_status (
  singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
  target_kind TEXT NOT NULL DEFAULT 'GOOGLE_STAGING_REPLICA',
  target_identity TEXT,
  schema_version INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL DEFAULT 'UNCONFIGURED',
  checkpoint TEXT,
  pending_count INTEGER NOT NULL DEFAULT 0,
  retry_count INTEGER NOT NULL DEFAULT 0,
  last_attempt_at TEXT,
  last_success_at TEXT,
  last_error_class TEXT,
  last_error TEXT,
  schema_checksum TEXT,
  updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO replication_status(singleton_id,updated_at) VALUES(1,strftime('%Y-%m-%dT%H:%M:%fZ','now'));

CREATE TABLE IF NOT EXISTS sync_checkpoints (
  consumer TEXT PRIMARY KEY,
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dr_checksums (
  namespace TEXT PRIMARY KEY,
  row_count INTEGER NOT NULL,
  checksum TEXT NOT NULL,
  algorithm TEXT NOT NULL DEFAULT 'SHA-256-ROW-HASH-LIST-V1',
  computed_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

INSERT OR IGNORE INTO schema_migrations(version,checksum) VALUES('0001_m1_foundation','55d781c87293b2869d004bf736b670d4a111e3cfecf94aae33530febe10657ef');

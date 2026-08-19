PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS revision_state (
  namespace TEXT PRIMARY KEY,
  revision INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO revision_state(namespace,revision,updated_at) VALUES
('employees',0,strftime('%Y-%m-%dT%H:%M:%fZ','now')),
('catalogs',0,strftime('%Y-%m-%dT%H:%M:%fZ','now')),
('accounts',0,strftime('%Y-%m-%dT%H:%M:%fZ','now')),
('pda',0,strftime('%Y-%m-%dT%H:%M:%fZ','now')),
('user_pick',0,strftime('%Y-%m-%dT%H:%M:%fZ','now')),
('pack_table',0,strftime('%Y-%m-%dT%H:%M:%fZ','now')),
('user_pack',0,strftime('%Y-%m-%dT%H:%M:%fZ','now'));

CREATE TABLE IF NOT EXISTS import_batches (
  import_batch_id TEXT PRIMARY KEY,
  dataset TEXT NOT NULL,
  template_version TEXT NOT NULL,
  schema_checksum TEXT NOT NULL,
  file_sha256 TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('UPLOADING','VALIDATED','COMMITTED','ROLLED_BACK','FAILED')),
  started_at TEXT NOT NULL,
  validated_at TEXT,
  committed_at TEXT,
  rolled_back_at TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_import_batches_actor_started ON import_batches(actor_id,started_at DESC);

CREATE TABLE IF NOT EXISTS import_chunks (
  import_batch_id TEXT NOT NULL REFERENCES import_batches(import_batch_id) ON DELETE CASCADE,
  chunk_no INTEGER NOT NULL,
  chunk_checksum TEXT NOT NULL,
  rows_json TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  PRIMARY KEY(import_batch_id,chunk_no)
);

CREATE TABLE IF NOT EXISTS import_row_audit (
  import_batch_id TEXT NOT NULL REFERENCES import_batches(import_batch_id) ON DELETE CASCADE,
  row_no INTEGER NOT NULL,
  business_key TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('INSERT','UPDATE','NOOP','REJECTED','ROLLBACK_UPDATE')),
  before_json TEXT,
  after_json TEXT,
  canonical_event_id TEXT,
  error_code TEXT,
  PRIMARY KEY(import_batch_id,row_no)
);
CREATE INDEX IF NOT EXISTS idx_import_row_audit_key ON import_row_audit(import_batch_id,business_key);

CREATE TABLE IF NOT EXISTS push_devices (
  device_id TEXT NOT NULL,
  login_id TEXT NOT NULL,
  fcm_token TEXT NOT NULL UNIQUE,
  platform TEXT NOT NULL DEFAULT 'ANDROID',
  app_version TEXT NOT NULL DEFAULT '',
  channel TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','REVOKED','INVALID')) DEFAULT 'ACTIVE',
  registered_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_success_at TEXT,
  last_error_class TEXT,
  PRIMARY KEY(device_id,login_id)
);
CREATE INDEX IF NOT EXISTS idx_push_devices_active ON push_devices(status,login_id);

CREATE TABLE IF NOT EXISTS push_outbox (
  push_id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,
  revision INTEGER,
  business_date TEXT,
  authority_epoch INTEGER NOT NULL,
  authority_seq INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('PENDING','SENT','RETRY','FAILED')) DEFAULT 'PENDING',
  attempt_count INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_error_class TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_outbox_due ON push_outbox(status,next_attempt_at);

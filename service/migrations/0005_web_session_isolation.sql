-- Separate one active WEB session from the existing one-active-PDA session per login.
-- Existing auth_sessions remains the PDA/mobile slot for backward compatibility.
CREATE TABLE IF NOT EXISTS auth_web_sessions (
  login_id TEXT PRIMARY KEY NOT NULL,
  session_id TEXT NOT NULL UNIQUE,
  device_id TEXT NOT NULL,
  issued_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth_web_sessions_session ON auth_web_sessions(session_id);

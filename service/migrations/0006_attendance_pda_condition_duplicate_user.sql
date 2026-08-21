ALTER TABLE attendance_sessions ADD COLUMN pda_enter_status TEXT;
ALTER TABLE attendance_sessions ADD COLUMN pda_exit_status TEXT;
ALTER TABLE attendance_sessions ADD COLUMN resource_note TEXT NOT NULL DEFAULT '';

-- Compatibility for an ACTIVE session created before S38: use the current projected
-- PDA condition as the best available entry baseline so the session can still exit safely.
UPDATE attendance_sessions
SET pda_enter_status=(
  SELECT status_label
  FROM resources
  WHERE resources.resource_type='PDA'
    AND resources.resource_id=attendance_sessions.pda_serial
  LIMIT 1
)
WHERE state='ACTIVE'
  AND pda_serial IS NOT NULL
  AND TRIM(pda_serial)<>''
  AND (pda_enter_status IS NULL OR TRIM(pda_enter_status)='');

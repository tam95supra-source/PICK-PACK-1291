export type Role = "SUPERADMIN" | "ADMIN" | "USER" | "SYSTEM" | "IMPORT";
export type ErrorClass = "VALIDATION" | "AUTH" | "PERMISSION" | "CONFLICT" | "RESOURCE" | "TRANSIENT" | "INTEGRITY" | "SCHEMA" | "INTERNAL";

export interface CanonicalMutationRequest {
  event_id: string;
  event_type: "ATTENDANCE_ENTER" | "ATTENDANCE_EXIT" | "RESOURCE_CHANGE" | "LABOR_START" | "LABOR_FINISH" | "M1_SHADOW_PROBE";
  entity_type: string;
  entity_id: string;
  business_date: string;
  authority_epoch?: number;
  service_generation?: string;
  base_version: number;
  timestamp: string;
  payload: Record<string, unknown>;
  idempotency_key: string;
  device_id: string;
  schema_version: 1;
  client_source?: "PDA" | "WEB" | "FILE_IMPORT";
}

export interface AuthContext {
  login_id: string;
  role: "SUPERADMIN" | "ADMIN" | "USER";
  display_name: string;
  device_id: string;
  session_id: string;
  verifier_hash: string;
  session_kind: "PDA" | "WEB";
}

export interface EventRow {
  event_id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  business_date: string;
  authority_epoch: number;
  authority_seq: number;
  service_generation: string;
  base_version: number;
  new_version: number;
  actor_id: string;
  actor_role: string;
  device_id: string;
  occurred_at: string;
  committed_at: string;
  payload_json: string;
  idempotency_key: string;
  origin: string;
  schema_version: number;
  checksum: string;
}

export interface ApiErrorBody {
  ok: false;
  error: {
    code: string;
    error_class: ErrorClass;
    retryable: boolean;
    message?: string;
    conflict?: Record<string, unknown> | null;
  };
}

export const SCHEMA_VERSION = 1;
export const REPLICA_HEADERS = [
  "event_id","event_type","entity_type","entity_id","business_date","authority_epoch","authority_seq","service_generation","base_version","new_version","actor_id","actor_role","device_id","occurred_at","committed_at","idempotency_key","origin","schema_version","checksum","payload_json"
] as const;
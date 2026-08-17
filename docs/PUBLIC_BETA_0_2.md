# PUBLIC BETA 0.2 — Pick Pack 1291

Status: PILOT / REAL OPERATIONS
Date: 2026-08-17 (Asia/Bangkok)
Release: `v0.2.0-beta.1-publicbeta`

## Scope enabled

- Real server-side login using the live account verifier from `DỮ LIỆU THEO NGÀY` / `Danh sách Admin`.
- Live personnel lookup from `DANH SÁCH NHÂN SỰ`.
- Live PDA / User Pick / Bàn Pack + mapped User Pack master lookup.
- Real authoritative ENTER / EXIT mutations.
- One MNV session per business date: NOT_ENTERED -> ACTIVE -> ENDED.
- Immutable event ID / idempotent retry.
- Atomic resource exclusivity and daily consumption rules for User Pick / User Pack.
- Server sequence and diagnostic sync status.

## UI decision

- Canonical visual is now MẪU 1 — TỐI GIẢN / HIỆN ĐẠI.
- VÀO CA and RA CA are merged into `QUÉT QR NHÂN SỰ`.
- Initial screen asks only for MNV; server state determines the next UI.
- Android status/navigation insets are applied.
- Copyright is fixed at the bottom outside the scroll area and reduced in size.

## Beta authority

The Public Beta uses an isolated `pp_*` namespace in the existing Supabase host as transactional Beta authority. It does not alter the unrelated BÁO HÀNG application tables.

Android never receives Google credentials, service-role credentials, password verifiers, signing secrets, or Sheet write secrets.

## Google Sheet integration status

Master/account reads are live from the existing Google Sheet.

Each accepted ENTER/EXIT also creates a durable row projection in `pp_sheet_projection_queue` matching the existing `RA - VÀO TRONG CA` column contract. The dedicated Google Sheet writer/ACK bridge is not yet activated. Therefore:

- Public Beta transaction state is real and durable.
- A queued projection is **not** claimed as written to Google Sheet until `sheet_ack_at` is set.
- The app exposes the pending projection count for diagnosis.

The Sheet writer must be deployed with a Pick-Pack-specific credential/webhook. Do not reuse the unrelated BÁO HÀNG Sheet webhook without verifying its target and contract.

## Signing

This pilot package uses the Android debug signing identity produced by CI and has package `vn.pickpack1291.app.beta.publicbeta`. It is intentionally separated from the previous UI preview package. It is not the permanent OTA signing baseline.

Before Stable/long-lived Beta OTA, create a fixed signing key outside the public repository and inject it only through protected CI secrets.

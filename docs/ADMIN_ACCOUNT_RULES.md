# ADMIN ACCOUNT RULES — Pick Pack 1291

Status: **OWNER-LOCKED / authoritative**

This file records an explicit owner decision. It may not be changed, expanded, reinterpreted, or mapped to another catalog without a later explicit owner instruction.

## 1. `Danh sách Admin` is a specialized account namespace

`Danh sách Admin` is not an employee-position catalog and must never inherit values from `DANH SÁCH NHÂN SỰ` or any other sheet merely because a field has a similar name.

The `Vị trí` field for `Danh sách Admin` is fixed system-wide to exactly these three values:

- `superadmin`
- `admin`
- `user`

No other value is valid.

## 2. No cross-sheet fallback

For Admin accounts:

- Do not read `Danh mục` to populate Admin `Vị trí`.
- Do not fall back to `DANH SÁCH NHÂN SỰ_Vị trí chính`.
- Do not infer or copy employee job titles such as `Chuyên viên`, `Điều phối`, `Trưởng nhóm`, etc. into `Danh sách Admin_Vị trí`.
- A similar field name in another sheet is not permission to reuse that catalog.

## 3. Application/backend enforcement

The Android account-management UI and Google Apps Script backend must enforce the fixed role-position namespace.

- Existing `SUPERADMIN` account position is `superadmin`.
- `ADMIN` account position is `admin`.
- `USER` account position is `user`.
- Backend must derive/validate Admin position from account role rather than trusting an arbitrary client-supplied position.
- Normal account-creation UI must not create a new `SUPERADMIN` unless the owner later explicitly authorizes that capability.

## 4. Change control

Only an explicit owner instruction can change the allowed Admin positions or the relationship between Admin role and Admin position.

A future developer/agent must not change this rule because of a UI redesign, a new `Danh mục` column, a similarly named employee field, a migration, or implementation convenience.

# AGENTS.md — Pick Pack 1291 mandatory project rules

These rules are authoritative for any agent, coding assistant, CI automation, or future handover working in this repository.

## 1. Owner requirements override inherited implementation

- Do not infer a new architecture from existing code, handovers, migrations, or deployed infrastructure.
- Do not treat an inherited implementation as permission to change the project purpose.
- If existing code conflicts with an explicit owner requirement, correct the code toward the explicit requirement.
- Never silently reinterpret or expand the requested purpose.

## 2. Approved operational architecture

`Android App ↔ Google Apps Script ↔ Google Sheets`

- Google Sheets is the operational source of truth at this stage.
- Google Apps Script is the transaction/API bridge for that Sheet.
- GitHub is source/CI/release infrastructure only, not the operational datastore.

## 3. No unauthorized service/backend changes

Without an explicit owner instruction, do not add or migrate authority to:

- Supabase
- Firebase
- Neon/Postgres
- Cloudflare backend/storage
- another database/server/backend/service
- another auth authority
- another synchronization authority

If a technical limitation appears to require such a change, do not choose one automatically. Keep the approved architecture unchanged, document the blocker precisely, and require explicit owner authorization before changing architecture.

## 4. Do not act contrary to the stated goal

Before a material implementation change, verify that it directly serves the latest explicit owner requirements. Do not add infrastructure merely because it is convenient, familiar, already present elsewhere, or inherited from a previous session.

## 5. Data and release safety

- Reconcile existing business data before deleting/replacing an implementation.
- Do not commit secrets, plaintext passwords, Google credentials, Android signing keys, or private tokens to the public repository.
- Beta must exercise the real business functions needed for testing.
- Preserve Android signing identity for in-place updates.
- Automatic update checks may use GitHub Releases; this does not make GitHub an operational data backend.

## 6. Architecture enforcement

Read and obey `ARCHITECTURE_GUARDRAILS.md` and `README.md` before changing runtime architecture. CI architecture gates are intentional and must not be bypassed to make a build pass.

## 7. Owner workstation constraint — no local command line

- The owner's company-managed computer cannot run CMD, PowerShell, Terminal, shell scripts, or other local command-line workflows.
- Do not instruct the owner to execute `cmd`, PowerShell, `bash`, `clasp`, `git`, `gh`, `adb`, Gradle, Node/npm/npx, Java/keytool, OpenSSL, or similar local CLI commands.
- Owner-facing setup and administration must preferentially use browser/UI workflows such as GitHub web UI, Google Workspace/Apps Script UI, Drive UI, or repository-hosted CI/automation.
- If a required task normally needs a local CLI, redesign it so CI/automation performs the command-line portion and the owner only performs browser-based authorization, secret entry, or explicit approval.
- If a browser-only path is genuinely impossible, state the blocker explicitly instead of giving unusable local terminal instructions.

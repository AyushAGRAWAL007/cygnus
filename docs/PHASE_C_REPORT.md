# Customer order import implementation report — 2026-10-30

## Delivered code

- Shared normalized import service for Amazon-file and Gmail observations.
- Safe in-memory ZIP inspection, strict UTF-8/JSON/CSV parsing, resource limits,
  invalid-record exclusion and explicit unsupported-format errors.
- Customer-owned, expiring review previews; selected confirmation; idempotency;
  concurrent duplicate protection; history; multi-source observations without
  silent replacement of existing data.
- Explicit migration 002 preserving order/item IDs and return relationships.
  Nullable missing item values, decimal unit amounts and per-item currency.
- Actual Google authorization-code/PKCE REST connector, encrypted token storage,
  refresh, session/state/generation validation, revocation and disconnect.
- Bounded, manual Gmail search/history synchronization with pagination, retries,
  message tracking and recoverable pending structured observations. No raw
  mailbox/body persistence and no email send/modify/delete functionality.
- Orders upload/progress/preview/history/Gmail UI preserving existing visual
  tokens. Source/currency/unknown-value display and responsive order cards.
- Imported purchases cannot use simulated pickup/refund actions. File-import
  AI context is customer-scoped and explicitly unverified. Gmail-derived data
  is blocked from external AI providers pending a compliant sharing policy.
- Disposable-copy preparation script and PowerShell test-project instructions
  in [ORDER_IMPORTS.md](ORDER_IMPORTS.md).

## Required external validation — still pending

1. **A real redacted Amazon.in consumer archive.** No authoritative India export
   schema was established in research. Current file adapters are explicitly
   synthetic Cygnus interchange formats. They are not verified Amazon.in
   adapters. Unknown schemas are refused/reported, never guessed.
2. **Configured Google OAuth test project and test user.** No real Google
   credentials were supplied or used. OAuth, refresh, synchronization and
   revocation were tested with mocked Google responses. No live Google consent
   run or public verification is claimed.
3. Real Amazon email template samples for broader extraction compatibility.
   Current extraction is conservative; unsupported/incomplete observations are
   review-only. Manual sync covers a bounded last-year initial search, not a
   complete historical or real-time mailbox synchronization.

These are prerequisites for claiming the final real-customer objective is
validated. The implementation does not replace missing source evidence with
fictional compatibility claims.

## Verification evidence

- Complete backend suite: **200 passed, 1 skipped, 4 migration subtests passed**.
  The skipped test is the deliberately opt-in browser test, run separately.
- Separate headless Edge test: **1 passed**. Covers actual registration,
  ZIP upload, no writes before confirmation, saved INR order, idempotent
  reupload, malformed-file feedback and missing Google configuration.
- Responsive browser checks: no horizontal document overflow at **1440,
  1280, 768, 390px**. Screenshots were generated in the test temporary directory;
  mobile layout was visually inspected and product rows improved afterward.
- Frontend `npm.cmd run lint` and `npm.cmd run build`: passed.
- `git diff --check`: passed (Windows line-ending notices only).
- Targeted security tests cover ownership/CSRF, SQL injection treated as data,
  archive traversal/symlink/bomb/entry-count bounds, upload limits, malformed
  data, concurrent confirmation, migration rollback/drift, OAuth state/replay/
  session rotation, refresh denial, safe errors, token encryption, pagination,
  stale history recovery, transient retries, MIME bounds/alternatives and
  disconnect/callback races.
- An independent read-only review identified five important defects; each was
  reproduced by a failing regression test and fixed. No deferred findings.

## Database and Git safety

The live database and verified pre-auth backup were not modified by this task.
No migration was applied to them. Tests used temporary databases only. Existing
authentication, ownership, workflow, migration 001 and Nebius behavior were
preserved. NVIDIA received additive imported-record safeguards and labeling.

Live database SHA-256, matching the initial audit:

`4977247B292478ACB410EF5201A10D4101DE63E458813C5B1BAC8A2C090CAEC8`

Backup `backend/cygnus.db.pre-auth-20261030-171223.bak` SHA-256:

`DE769A698D97091EC4E9D75913EB2C0D326AF2DE5207E45E1D3856F1B29704BC`

No Git staging, commits, pushes or worktree moves occurred. The current checkout
was retained to preserve and extend its preexisting uncommitted authentication
work. The user's authorization to implement after the initial report governed
execution; no additional design approval was required.

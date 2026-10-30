# Customer order imports implementation plan

> Execute inline with the executing-plans skill. The user's detailed specification and authorization govern implementation. Do not commit, stage, push, or touch the live database.

Goal: customer-reviewed Amazon file and Gmail imports into one owned order history.

Architecture: bounded source adapters -> normalized orders -> persisted preview -> atomic confirmation. Customer + marketplace + Amazon order ID is the canonical identity. Source observations accumulate without overwriting existing values. Unknown template data is review-only.

Tech: existing FastAPI/SQLite/React stack, stdlib file parsers, httpx Google transport, cryptography Fernet for credential encryption.

Global constraints: backend/cygnus.db and backups remain unchanged. All tests use temporary databases. No retailer scraping, passwords, real pickup/refund actions, or claims of Google verification. No email bodies/tokens in logs or preview storage. No real-format compatibility claim without a sample.

## Schema design

Migration 002 requires 001 and is explicit/atomic/repeatable. Extend orders with marketplace, currency, order_status, imported_at, review_status. Rebuild order_items preserving IDs/FKs with nullable unknown values; add exact decimal unit_price, currency, product_identifier, external_item_id, details_json. Keep demo numbers unchanged. Canonical unique index on (user_id,retailer,marketplace,external_order_id) for non-simulated imports. Source references use composite order/customer foreign keys, source/reference unique per customer/order, structured normalized observations only. Existing orders are immutable during import; conflicts are reported, not merged destructively.

Preview: owned ID, source, digest, normalized records/issues, 30-minute expiry, confirmed result; confirmation is serialized/idempotent and rechecks duplicates. History uses existing table plus summary JSON. Gmail: extend integrations with account/cursors/sync lease/error; reuse encrypted credentials; OAuth attempts store hashed state, session binding, encrypted PKCE verifier, expiry and consumed flag. Processed Gmail IDs recorded only after preview persistence; cursor advances in same transaction.

## Tasks

- [x] 1. Test and implement strict normalized models, bounded ZIP/JSON/CSV adapters. Synthetic cygnus-amazon-v1 contract is explicitly not a verified Amazon.in export. Preserve recognized structured fields, refuse ambiguous quantities/dates/prices and whole-order partial imports.
- [x] 2. Test migration preservation, rollback, idempotency, ownership constraints; implement migration 002. Test preview/confirm isolation, race-safe deduplication, conflicts, TTL, and unknown data.
- [x] 3. Add authenticated bounded raw-body upload endpoint (JSON/CSV/ZIP content bytes; content sniffing), preview/confirm/history APIs with CSRF and throttling. Use raw bytes to avoid multipart dependencies and preserve existing JSON-only CSRF through a narrowly scoped content-type check.
- [x] 4. Test/implement encrypted Gmail OAuth authorization/state/PKCE/refresh/revoke, strict configured callback, session binding and no token disclosure.
- [x] 5. Test/implement conservative MIME extraction, limited Amazon sender/subject search, bounded page/history sync, processed message IDs, retries, disconnect and safe error recovery. All imports still pass through preview/confirmation.
- [x] 6. Add Orders upload/preview/history and Gmail panels using existing visual tokens; add nullable amount/currency/source handling and unknown eligibility guard. Keep imported Gmail data out of external AI context pending an approved data-sharing policy; preserve NVIDIA safeguards and explain availability clearly.
- [x] 7. Run complete backend suite, frontend lint/build, temporary-database browser flows across 1440/1280/768/390 widths; inspect security and live-file hashes.

## Review focus

- Ambiguous duplicate rows/shipments must not silently double quantities or discard products.
- Conflicting multi-source observations must not overwrite reviewed order data.
- OAuth callback replay, cross-session state, failed revocation and refresh races must remain safe.
- Resource bounds must hold for actual decompressed bytes, MIME recursion and paginated mail responses.
- Imported unknown prices/windows must never be presented as zero, USD or eligible.

## Decisions and progress

Ruling: work in the current dirty checkout because the user requires preserving and extending its uncommitted authentication work; a fresh worktree would omit those dependencies. No git mutations.
Ruling: the user explicitly authorizes implementation after the first design report; no additional design approval gate is imposed.
Ruling: Gmail-derived information will not be sent to NVIDIA/Nebius automatically. Structured records remain customer-visible; external-AI use needs a compliant disclosure/consent policy before enablement.

Implementation tasks completed against synthetic source contracts and mocked Google APIs. Real Amazon.in adapter compatibility and live Google test-user validation remain external prerequisites, not completed milestones.

Independent review found five important issues: in-flight OAuth callback/disconnect generation race, stale concurrent disconnect finalization, duplicate multipart alternatives, item truncation at 100, and pending recovery lockout at 1000. Regression tests reproduced each before fixes; focused tests passed afterward. Migration drift, rollback, CSRF, ownership and concurrent import checks passed. No deferred review findings.

# Email Authentication Implementation Plan

Goal: implement the user-approved Phase B3 email/password authentication.
Architecture: a focused auth router/service uses the existing SQLite helper and migration 001 schema. Opaque cookie sessions remain server-side. Existing order APIs are unchanged and remain demo-only until ownership enforcement.
Stack: FastAPI, SQLite, argon2-cffi, email-validator, slowapi, React.
Spec: user-approved plan in this conversation, 2026-10-30.

Constraints: no live database changes, no migration edits, no NVIDIA/db helper replacement, no staging/commits/pushes. All execution databases must be disposable.

- [x] Add failing auth API tests using temporary databases initialized and migrated explicitly; cover registration, validation, duplicates, hash storage, generic login failures, rotation, expiration, revocation, cookies, CSRF, identity, sensitive error redaction, atomic demo claim and rate limits.
- [x] Add backend/app/auth.py with /api/auth/register, login, logout, me and require_user dependency. Use Argon2id, secrets.token_urlsafe(32), SHA-256 session hashes, eight-hour expiry, host-only HttpOnly SameSite=Lax cookies (Secure outside development/demo/test), explicit Origin/custom-header/JSON CSRF validation, slowapi throttling, transactional once-only demo claim. Refuse unavailable auth schema with controlled 503; never run migrations on startup.
- [x] Extend config.py, requirements.txt, main.py narrowly for validated auth settings, pinned dependencies, auth routing, credentialed explicit CORS, CSRF for session-cookie mutations and redaction of auth validation input. Preserve existing routes.
- [x] Add frontend AuthProvider, login/register forms and account controls using existing components; extend hash routes and API adapter for credentials/header and structured validation errors. No localStorage tokens, automatic Google linking or workspace privacy claims.
- [x] Run full backend suite with DATABASE_PATH in a temporary directory; run frontend lint/build. Verify protected file digests unchanged. Document setup and outstanding isolation/email/OAuth limitations.

Review focus: concurrent registration, malformed password validation leaks, expired sessions, cross-origin auth attempts, production cookie settings, identity cache after logout/account switching. No new live schema or automatic migration.

Ruling: user expanded the mandate during implementation to require ownership on every customer route. Added SQL ownership filters, authenticated AI context, safe Nebius errors, atomic return transitions and focused responsive/feedback fixes. Existing API assertions are preserved; their fixtures now register real users. The approved live-database prohibition remains unchanged.

Verification: 138 backend tests and four migration subtests passed; frontend lint and build passed; isolated Edge checks covered registration, invalid/valid login, logout, revoked-session UI, HttpOnly/no-localStorage behavior, reduced-motion media, and five customer screens at 1440/1280/768/390px. Protected database, migration and db helper hashes unchanged. Final minor UI copy/accessibility changes are rechecked before handoff.

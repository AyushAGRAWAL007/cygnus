# Cygnus authentication and isolation

Email/password accounts use Argon2id via argon2-cffi. Registration requires a valid normalized email, a nonblank display name (80 characters maximum) and a password of 8 to 128 characters. Passwords are never trimmed or truncated. Login returns the same error for unknown emails, incorrect passwords, inactive accounts, and Google-only accounts; no identity is merged by email.

Sessions are random 256-bit opaque tokens in host-only HttpOnly SameSite=Lax cookies. Only SHA-256 token hashes are stored. Expiration defaults to eight hours; each login rotates the presented session and logout revokes it. Secure cookies are mandatory outside development/demo/test. No session tokens are stored in localStorage or returned in response bodies. Validation errors on auth routes omit raw inputs; private responses use Cache-Control: no-store.

## Configuration and database safety

- AUTH_SESSION_TTL_SECONDS: 28800 by default; valid range 60?604800 seconds.
- AUTH_TRUSTED_ORIGINS: comma-separated exact browser origins, without paths or wildcards.
- CORS_ORIGINS: matching explicit origins for direct cross-origin deployments; credentials are enabled. Same-origin hosting/proxying is preferred because SameSite=Lax intentionally does not support unrelated cross-site origins.
- APP_ENV=production requires HTTPS cookies. Configure trusted reverse proxies deliberately; do not trust arbitrary forwarded client IP headers.
- DATABASE_PATH must point at an explicitly migrated database. No authentication code applies migrations or creates auth tables on startup. Missing auth schema yields a controlled 503 on registration/login.

The live database and migration 001 were not changed. Authentication was verified only with disposable migrated databases. A live rollout still requires separate migration approval.

## Browser/API contract

GET /api/auth/me returns id, email, display_name and email_verified, or 401.
POST /api/auth/register, /login and /logout require application/json, an exact trusted Origin and X-Cygnus-CSRF: 1. All other API mutations carrying the session cookie require the same CSRF checks. The custom header is a browser same-origin/CORS defense, not a secret token; requests with missing/null/untrusted origins are rejected. The frontend adapter supplies the header and includes cookies. Nonbrowser API clients must provide the explicit origin and header too.

Registration returns 201 and signs in. Duplicate details return 409. Login returns 200 or generic 401. Logout returns 200 after database revocation and cookie removal. Expired/revoked/missing/invalid sessions return 401. Throttling returns 429: registration five/minute/IP, login ten/minute/IP.

All customer order, return, pickup, activity and AI routes derive identity through require_user. Ownership is checked server-side; cross-customer resource access returns 404. The first committed registration claims the four known unowned simulated orders under the same write transaction as user/session creation and a unique demo_data_owner marker. Existing cases/events belong through their order. Concurrent eligibility checks and return writes are serialized to avoid duplicate active cases and conflicting transitions. No imported/real retailer data exists.

## Verification and limitations

The existing API tests now authenticate through real registration, preserving their assertions. Tests initialize and migrate only temporary databases. Run the backend suite from backend with .venv/Scripts/python.exe -m pytest -q; all tests now isolate their database paths. Run npm run lint and npm run build from frontend. Browser checks use temporary databases, no provider credentials, and a headless browser.

Email verification and recovery tables exist, but delivery, verification/reset endpoints, and recovery UI remain future work. Accounts are explicitly unverified. Google Sign-In, Amazon import and Gmail are not implemented. The simulator remains simulated; refund issuance is not proof of money transfer. NVIDIA remains read-only with its existing demo/development environment gate and existing provider safeguards. Nebius diagnostics are authenticated, provider errors sanitized, and SDK calls have a 20-second timeout with zero retries.

Authentication throttling currently uses per-process memory: multi-worker/deployment-wide limits require shared storage or platform controls. Authentication is not a production security certification. Session cleanup jobs, password reset/recovery, stronger abuse controls, pagination for large histories and broader accessibility/device coverage remain follow-up work.

# RepeaterWatch — Security Fixes

Summary of security vulnerabilities identified and fixed in the sskerry/RepeaterWatch fork.
These apply to the upstream MrAlders0n/RepeaterWatch and jjkroell/Repeater-Watch codebases
as well, since they share the same foundation.

---

## 1. No CSRF Protection

**Severity:** High
**Commit:** `9f2848c` — Add CSRF protection to all write endpoints

**Problem:** All POST/PUT/DELETE endpoints had no Cross-Site Request Forgery protection. A malicious website could trick an authenticated user's browser into making requests to RepeaterWatch (rebooting the Pi, flashing firmware, wiping the database, toggling GPIO, etc.) without the user's knowledge.

**Fix:** Added Flask-WTF CSRFProtect. All state-changing requests now require a valid CSRF token. The token is served via a `<meta>` tag and sent as an `X-CSRFToken` header on every `fetch()` call. The login form uses a hidden field.

---

## 2. Dangerous Endpoints Accessible Without Authentication

**Severity:** Critical
**Commit:** `c4af3a0` — Security hardening for public-facing deployment

**Problem:** When no password was set (the default), all endpoints were fully accessible — including:
- **Pi terminal** (full shell access via WebSocket)
- **System reboot**
- **Firmware flashing** (upload and flash arbitrary firmware)
- **GPIO control** (radio reset, relay toggle)
- **Database wipe**
- **Service restart**

Anyone who could reach the dashboard on port 5000 had full control of the Pi and the radio.

**Fix:** Added authentication gating on all dangerous endpoints. The current access model:
- **No password set:** Full access to everything (intended for trusted LANs). A visible "No Auth" warning badge is shown on the dashboard so operators know the system is open.
- **Password set, not logged in:** Read-only — can view dashboards but cannot access terminal, reboot, flash, GPIO, or settings.
- **Password set, logged in:** Full access.

The key improvement is that the auth gates **exist** now — the original code had no concept of restricted endpoints at all. Operators on trusted LANs get full access without friction, but setting a password immediately locks down all dangerous actions.

---

## 3. Sensitive Data Exposed to Unauthenticated Users

**Severity:** Medium
**Commits:** `c4af3a0`, `c6fff20`

**Problem:** API responses included sensitive information regardless of authentication:
- GPS coordinates (exact location of the repeater site)
- Device public keys
- Pi hostname, process list
- Fail2ban configuration, trusted proxy list

**Fix:** Sensitive fields are redacted from API responses when a password is set and the user is not logged in. When no password is set (trusted LAN mode), all data is visible — this is intentional. Added `_has_full_access()` helper to gate data visibility consistently: returns true if authenticated OR if no password is configured.

---

## 4. No Session Cookie Hardening

**Severity:** Medium
**Commit:** `c4af3a0`

**Problem:** Session cookies had no security flags set, making them vulnerable to:
- JavaScript access (XSS could steal sessions)
- Cross-site request attachment
- Transmission over plain HTTP

**Fix:** Session cookies now set `HttpOnly`, `SameSite=Strict`, and `Secure` (when behind a reverse proxy).

---

## 5. No Upload Size Limit

**Severity:** Medium
**Commit:** `c4af3a0`

**Problem:** The firmware upload endpoint had no file size limit. An attacker could upload arbitrarily large files, filling the Pi's storage or causing out-of-memory crashes.

**Fix:** Added 16MB upload size limit via Flask's `MAX_CONTENT_LENGTH`.

---

## 6. Subprocess Error Messages Leaked to Users

**Severity:** Low
**Commit:** `c4af3a0`

**Problem:** When subprocess commands failed (firmware flash, service restart, etc.), raw error messages including file paths, system details, and stack traces were returned in API responses.

**Fix:** Detailed errors are logged server-side only. API responses return generic error messages.

---

## 7. Trusted Proxy IPs Not Validated

**Severity:** Medium
**Commit:** `c4af3a0`

**Problem:** The `MESHCORE_TRUSTED_PROXIES` setting accepted any IP address, including public IPs. If misconfigured, an attacker could spoof the `X-Forwarded-For` header to bypass IP-based restrictions.

**Fix:** Trusted proxy IPs are validated to ensure they are private/localhost addresses only.

---

## 8. Incognito/Unauthenticated Users Could Access Admin UI

**Severity:** Medium
**Commits:** `5b29cc4`, `3bf0ab8`

**Problem:** The Tools and Settings tabs (containing reboot, firmware flash, GPIO, terminal, and configuration controls) were visible and functional to unauthenticated users in certain states.

**Fix:** Tools and Settings are merged into an Admin tab that is gated by `_has_full_access()`. When a password is set, only authenticated users see the Admin tab. When no password is set (trusted LAN mode), Admin is accessible to everyone — with the "No Auth" badge as a visual warning.

---

## 9. Auth Model Complexity Led to Bypass Paths

**Severity:** Medium
**Commit:** `c6fff20`

**Problem:** A `local_mode` flag created multiple code paths for access control, making it easy to miss gates on new endpoints. The interaction between `local_mode`, `password set`, and `authenticated` was confusing and inconsistent.

**Fix:** Removed `local_mode` entirely. Simplified to two states:
- **No password:** everything accessible (trusted LAN mode, with warning badge)
- **Password set:** require login for writes, read-only for visitors

Single `_has_full_access()` helper used everywhere — returns true when no password is configured OR when the user is authenticated.

---

## Recommendations for Upstream

1. **CSRF protection is the most important fix** — without it, any website can trigger destructive actions on behalf of an authenticated user.
2. **Auth gates on dangerous endpoints** — terminal, reboot, flash, and GPIO should have auth checks. Without a password they're open (acceptable for trusted LANs), but the gates must exist so setting a password actually protects something.
3. **Redact sensitive data when password-protected** — GPS coordinates and public keys shouldn't be in API responses for unauthenticated visitors on internet-facing deployments.
4. If exposing to the internet: use HTTPS via reverse proxy and set a strong password.

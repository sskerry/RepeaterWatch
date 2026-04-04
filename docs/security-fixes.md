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

**Fix:** Dangerous endpoints now require authentication even when no password is configured. Without a password, the dashboard is read-only. Setting a password unlocks write access after login.

---

## 3. Sensitive Data Exposed to Unauthenticated Users

**Severity:** Medium
**Commits:** `c4af3a0`, `c6fff20`

**Problem:** API responses included sensitive information regardless of authentication:
- GPS coordinates (exact location of the repeater site)
- Device public keys
- Pi hostname, process list
- Fail2ban configuration, trusted proxy list

**Fix:** Sensitive fields are redacted from API responses for unauthenticated users. Added `_has_full_access()` helper to gate data visibility consistently across all endpoints.

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

**Fix:** Tools and Settings are merged into an Admin tab that requires authentication. Only read-only tabs (MeshCore, Pi, Sensors) are visible without login.

---

## 9. Auth Model Complexity Led to Bypass Paths

**Severity:** Medium
**Commit:** `c6fff20`

**Problem:** A `local_mode` flag created multiple code paths for access control, making it easy to miss gates on new endpoints. The interaction between `local_mode`, `password set`, and `authenticated` was confusing and inconsistent.

**Fix:** Removed `local_mode` entirely. Simplified to two states: password set (require login for writes) or no password (read-only for everyone). Single `_has_full_access()` helper used everywhere.

---

## Recommendations for Upstream

1. **CSRF protection is the most important fix** — without it, any website can trigger destructive actions on behalf of an authenticated user.
2. **Dangerous endpoints must require auth** — terminal, reboot, flash, and GPIO should never be open by default.
3. **Redact sensitive data** — GPS coordinates and public keys shouldn't be in unauthenticated API responses for internet-facing deployments.
4. If exposing to the internet: use HTTPS via reverse proxy and set a strong password.

# Step 19 Security Hardening Report

**Date:** 2026-09-22  
**Implementation Phase:** Production Security Hardening (Step 19)  
**Database State:** Pristine (10 `iris_users`, 57 `scan_history`, 2 `student_profiles`, 21 `assessment_questions`)  
**Security Test Results:** 12 / 12 Security Tests Passed (100% PASS)  
**Full Regression Test Results:** 135 / 135 Existing Tests Passed (100% PASS)  
**Total Test Verification:** 147 / 147 Tests Passing (Zero Regressions)  

---

## Changes Implemented

The 4 Blockers and 3 Fail findings identified during the Step 18 production readiness audit have been remediated with production-grade security controls:

1. **Authentication (JWT HS256):** Standard RFC 7519 Bearer token authentication implemented with PBKDF2-HMAC-SHA256 password hashing (100,000 iterations, 16-byte cryptographic salt). Plaintext passwords are never stored.
2. **Role-Based Access Control (RBAC):** Three distinct roles established (`Student`, `Counselor`, `Admin`). Access boundaries enforced on all profile management, assessment submission, cognitive querying, report generation, and biometric endpoints.
3. **CORS Hardening:** Replaced wildcard `allow_origins=["*"]` with an environment-driven explicit allowlist (`CORS_ALLOWED_ORIGINS`). Enforced W3C credential safety rule: wildcard origins automatically disable credentials.
4. **Biometric & Media Protection:** Removed unauthenticated public static directory mounts (`/uploads` and `/outputs`). Implemented authenticated, role-verified streaming via `GET /api/media/{category}/{filename}` with path containment enforcement.
5. **Path Traversal Protection:** Implemented strict identifier validation (`re.match(r'^[a-zA-Z0-9_\-]+$')`) for `employee_code`, `student_id`, and `report_id` across `api/enroll.py`, `api/verify.py`, and `api/register_frame.py`. Traversal sequences (`../`, `..\\`, `/`, `\`, null bytes) are rejected with HTTP 400.
6. **File Upload Security:** Implemented a centralized upload validator (`security/upload_validator.py`) enforcing a 10MB payload limit, magic-byte inspection (JPEG, PNG, BMP), safe filename extraction, and PIL image stream integrity verification.
7. **Dependency Pinning:** Pinned all 13 direct dependencies in `requirements.txt` to exact, verified compatible versions and added `pyjwt==2.14.0`.
8. **Encryption-at-Rest & Permissions:** Restricted filesystem permissions on `iris_database.db` (`0o600`) and biometric asset directories `uploads/`, `outputs/`, `static/photos/` (`0o700`). Documented exact deployment requirements for volume-level encryption (LUKS / AWS EBS).

---

## Authentication

- **Status:** **IMPLEMENTED**
- **Architecture:** Fast, stateless JSON Web Tokens (JWT) signed using HMAC-SHA256 (`HS256`).
- **Module:** [`security/auth.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/security/auth.py)
- **Token Claims:**
  - `sub`: Authenticated username.
  - `role`: User role (`Student`, `Counselor`, `Admin`).
  - `iat`: Unix epoch timestamp of token issuance.
  - `exp`: Unix epoch expiration timestamp (default: 60 minutes, configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Secret Key:** Driven by environment variable `JWT_SECRET_KEY` (minimum 256 bits recommended).
- **Password Storage:** Passwords hashed with PBKDF2-HMAC-SHA256 using 100,000 rounds and random salts. Verification utilizes `hmac.compare_digest` to prevent timing attacks.
- **Endpoints:**
  - `POST /api/auth/login`: Authenticates credentials and returns a Bearer token.
  - `POST /api/auth/register`: Provisions users (Admin account creation restricted to Admins).
  - `GET /api/auth/me`: Returns identity of the authenticated caller.

---

## RBAC (Role-Based Access Control)

- **Status:** **IMPLEMENTED**
- **Roles Defined:**
  - `Student`: Access to personal profile, assessment taking, cognitive profile, recommendations, and personal report. Prohibited from administrative actions or viewing raw biometric media.
  - `Counselor`: Authorized to create/update student profiles, administer assessments, view student diagnostics, and operate biometric enrollment/verification.
  - `Admin`: Full superuser access, including user provisioning and student profile deletion.
- **Enforcement Mechanism:** FastAPI dependency injection via `require_role(*roles)`.
- **Authorization Boundaries:**
  - **Public:** `GET /health`, `GET /`, `POST /api/auth/login`, static frontend assets (`/static/*`).
  - **Authenticated (`Student`, `Counselor`, `Admin`):** `GET /api/profile/*`, `POST /api/profile/assessment`, `POST /api/profile/{id}/analyze`, `POST /api/profile/{id}/report`, `GET /dashboard`, `GET /report`.
  - **Staff (`Counselor`, `Admin`):** `POST /api/profile/students`, `POST /enroll`, `POST /verify`, `POST /detect`, `POST /register-frame`, `POST /api/quality/analyze`.
  - **Admin Only:** `DELETE /api/profile/{id}`, `POST /api/auth/register` (for Admin role).

---

## CORS

- **Status:** **IMPLEMENTED**
- **Module:** [`security/cors_config.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/security/cors_config.py)
- **Configuration Mechanism:**
  - Environment variable `CORS_ALLOWED_ORIGINS`: Accepts comma-separated list or JSON array of origins (e.g. `https://irisiq.com, https://app.irisiq.com`).
  - Environment variable `ENVIRONMENT` / `ENV`: Defaults to `development`.
- **W3C Security Invariants:**
  - Wildcard origin `*` automatically forces `allow_credentials = False`.
  - In `production` mode, if `CORS_ALLOWED_ORIGINS` is unset, the origin list evaluates to `[]` (fail-safe refusal of cross-origin requests).
  - In `development` mode, explicitly defaults to standard localhost development ports (`8000`, `3000`, `5173`).

---

## Media Protection

- **Status:** **IMPLEMENTED**
- **Public Directory Unmount:** Removed public `StaticFiles` mounts for `/uploads` and `/outputs` in [`main.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/main.py). Direct unauthenticated HTTP requests to `/uploads/...` return `404 Not Found`.
- **Authenticated Endpoint:** Implemented `GET /api/media/{category}/{filename:path}` in [`api/media.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/api/media.py).
- **Access Controls:**
  - Requires valid JWT Bearer token (`HTTP 401` if missing/invalid).
  - Role check: Students are forbidden from viewing raw biometric images in `uploads` or `outputs` (`HTTP 403`).
  - Path traversal checks reject `../`, absolute paths, null bytes, and path escape attempts (`HTTP 400`/`403`).

---

## Upload Security

- **Status:** **IMPLEMENTED**
- **Module:** [`security/upload_validator.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/security/upload_validator.py)
- **Controls Enforced:**
  - **Payload Size Cap:** Rejects files exceeding 10MB (`HTTP 413 Payload Too Large`).
  - **Magic-Byte Header Inspection:** Inspects initial bytes for valid JPEG (`\xFF\xD8\xFF`), PNG (`\x89PNG\r\n\x1a\n`), and BMP (`BM`) headers. Rejects disguised payloads (e.g., ZIP/executable disguised as `.jpg`).
  - **PIL Stream Integrity:** Executes `Image.open(buffer).verify()` to catch truncated, malformed, or corrupt image byte streams.
  - **Filename Sanitization:** Extracts `os.path.basename` and rejects illegal path separators or null bytes.
- **Endpoints Protected:**
  - `POST /enroll`
  - `POST /verify`
  - `POST /detect`
  - `POST /register-frame`
  - `POST /api/quality/analyze`

---

## Path Traversal Protection

- **Status:** **IMPLEMENTED**
- **Module:** [`security/path_validator.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/security/path_validator.py)
- **Validation Rules:**
  - Whitelist regex `^[a-zA-Z0-9_\-]+$` enforced for `employee_code`, `student_id`, and `report_id`.
  - Rejection of directory escape sequences: `../`, `..\\`, `/`, `\\`, and null byte `\x00`.
  - Path containment checks: `os.path.abspath(target).startswith(os.path.abspath(base_dir))`.
- **Endpoints Hardened:** `api/enroll.py`, `api/verify.py`, `api/register_frame.py`.

---

## Dependency Pinning

- **Status:** **IMPLEMENTED**
- **File:** [`requirements.txt`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/requirements.txt)
- **Pinned Manifest:**
  ```text
  fastapi==0.128.8
  uvicorn==0.39.0
  opencv-python==4.11.0.86
  tensorflow==2.20.0
  numpy==1.26.4
  pandas==2.3.3
  pillow==11.3.0
  scikit-learn==1.6.1
  matplotlib==3.9.4
  python-multipart==0.0.20
  h5py==3.14.0
  ultralytics==8.4.155
  scikit-image==0.24.0
  requests==2.32.5
  pydantic==2.13.5
  pyjwt==2.14.0
  ```
- **Verification:** All pinned packages are verified installed and functional in `ai-env`.

---

## Encryption-at-Rest Assessment

- **Application-Level Status:** **IMPLEMENTED (Filesystem Permissions Hardening)**
- **Deployment-Level Status:** **REQUIRES DEPLOYMENT CONFIGURATION**
- **Assessment Findings:**
  1. **SQLite Database:** `iris_database.db` is an unencrypted standard SQLite file. Python's standard `sqlite3` driver does not bundle SQLCipher; attempting to force SQLCipher without native extension binaries would corrupt database connectivity.
  2. **Biometric Assets on Disk:** Raw eye images are stored under `uploads/`, `outputs/`, and `static/photos/`.
  3. **Application-Level Mitigation:** Hardened file permissions on disk:
     - `iris_database.db`: `chmod 600` (Read/write restricted strictly to application process owner).
     - `uploads/`, `outputs/`, `static/photos/`: `chmod 700` (Directory traversal and access restricted strictly to process owner).
  4. **Production Deployment Requirements:**
     - The host volume hosting the application root, database, and upload directories MUST be encrypted using volume-level encryption (e.g. AWS EBS Encryption with KMS, Linux LUKS / dm-crypt, or container volume encryption).
     - Database backups must be encrypted with AES-256 (GPG / OpenSSL) prior to off-site transfer.
     - Enterprise deployments should transition from SQLite to PostgreSQL with Transparent Data Encryption (TDE) or disk volume encryption.

---

## Security Tests

- **Status:** **12 / 12 TESTS PASSING (100% PASS)**
- **Script:** [`scratch/test_step19_security_hardening.py`](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/scratch/test_step19_security_hardening.py)

| Test # | Security Test Area | Verification Detail | Result |
|---|---|---|:---:|
| **01** | Password Hashing | PBKDF2-HMAC-SHA256, unique salts, timing-attack safe compare | **PASS** |
| **02** | JWT Creation | HS256 claims (`sub`, `role`, `iat`, `exp`) valid | **PASS** |
| **03** | JWT Expiration | Expired token cleanly rejected with HTTP 401 | **PASS** |
| **04** | JWT Tampering | Tampered/corrupted signature rejected with HTTP 401 | **PASS** |
| **05** | Auth API Login | User credential check and access token issuance | **PASS** |
| **06** | Protected `/me` | HTTP 401 unauthenticated; HTTP 200 with valid Bearer token | **PASS** |
| **07** | RBAC Enforcement | Student & Counselor restricted from student deletion & enrollment | **PASS** |
| **08** | CORS Hardening | Environment allowlist, production fail-safe, wildcard credential rule | **PASS** |
| **09** | Media Protection | Unauthenticated 401, static unmount 404, path traversal rejection | **PASS** |
| **10** | Path Traversal | Alphanumeric whitelist regex & traversal sequence rejection | **PASS** |
| **11** | Upload Security | Size cap (>10MB rejected), magic-byte check, PIL corruption defense | **PASS** |
| **12** | DB Non-Regression | Iris users (10), scan history (57), students (2), questions (21) intact | **PASS** |

---

## Regression Tests

- **Status:** **135 / 135 TESTS PASSING (100% PASS)**
- All 8 existing regression test suites were re-executed against the hardened application:

| Suite Name | Script Path | Tests | Status |
|---|---|:---:|:---:|
| **Step 16 UI Consistency** | `scratch/test_step16_ui_consistency.py` | 21 | **PASSED** |
| **Step 14 Provenance Fixes** | `scratch/test_step14_provenance_fixes.py` | 19 | **PASSED** |
| **Step 12 Scoring Integrity** | `scratch/test_step12_scoring_integrity.py` | 26 | **PASSED** |
| **Step 10 Data Integrity** | `scratch/test_step10_data_integrity.py` | 21 | **PASSED** |
| **Step 8 Cognitive Assessment** | `scratch/test_step8_cognitive_assessment_fixes.py` | 13 | **PASSED** |
| **Expandable Assessment Engine** | `scratch/test_assessment_engine_expandable.py` | 9 | **PASSED** |
| **Recommendation Engine** | `scratch/test_recommendation_engine.py` | 11 | **PASSED** |
| **Complete System Integrity** | `scratch/test_complete_system.py` | 15 | **PASSED** |
| **TOTAL EXISTING TESTS** | | **135** | **100% PASS** |

---

## Compatibility Verification

1. **Biometric Pipeline:** Haar/YOLO eye detection, iris circular segmentation, normalization, LBP/Gabor/GLCM/CNN feature extraction, and cosine verification operate identically.
2. **Scoring Mathematics:** All Big Five, Critical Abilities, VAK, Leadership, Stream, and Career formulas remain untouched and preserve mathematical fidelity.
3. **Report Presentation:** All 32 sections of Report V2 generate with full structural integrity and zero literal `null` outputs.
4. **API Contracts:** All response schemas (`status`, `profile`, `result`, `sections`, etc.) remain backward-compatible with external callers.
5. **Database Records:**
   - `iris_users`: **10**
   - `scan_history`: **57**
   - `student_profiles`: **2** (`STU-001`, `STU-002`)
   - `assessment_questions`: **21**
   - `app_users`: **3** (`admin`, `counselor1`, `student1`)

---

## Remaining Production Requirements

The following infrastructure items must be configured in the host environment prior to internet exposure:

1. **REQUIRES DEPLOYMENT CONFIGURATION:**
   - **Environment Variables:** Set strong production values for:
     - `JWT_SECRET_KEY`: Minimum 64-character random string.
     - `CORS_ALLOWED_ORIGINS`: Exact production domain(s) (e.g. `https://app.irisiq.com`).
     - `ENVIRONMENT`: Set to `production`.
     - `BOOTSTRAP_ADMIN_PASSWORD`: Strong initial administrator password.
   - **Volume Encryption:** Host server / container volume must have full disk encryption enabled (AWS EBS KMS / LUKS).
   - **HTTPS Termination:** Run FastAPI behind an HTTPS reverse proxy (Nginx, Caddy, or Cloudflare) with TLS 1.3.
   - **Production ASGI Server:** Launch Uvicorn with `--workers 4` and omit `--reload`.

2. **REQUIRES FUTURE SECURITY REVIEW:**
   - **Database Scale:** Plan migration from SQLite to PostgreSQL 15+ for high-concurrency production deployments.
   - **Biometric Model Worker Pool:** Transition worker execution from `subprocess.run` to an asynchronous task queue (Celery/Redis) with warm model instances.
   - **Formal Privacy & Legal Review:** Conduct formal institutional data protection assessment for student biometric consent and retention policies.

---

## Known Limitations

1. **No Legal / Compliance Claims:** Implementation of technical security controls does not constitute formal legal certification under GDPR, India DPDP Act 2023, or FERPA.
2. **Heuristic Calibration:** Assessment scores and cognitive indicators remain rule-based heuristic metrics rather than nationally standardized psychometric indices.
3. **SQLite Single-Writer Lock:** SQLite operates with database-level write locks; high concurrent write traffic will require migration to PostgreSQL.

---

## Final Status

```
========================================================================================
STEP 19 PRODUCTION HARDENING STATUS:
HARDENING IMPLEMENTED & ACCEPTED
========================================================================================
Security Hardening Status:     COMPLETED (All 4 Blockers & 3 Fails Remediated)
Security Tests:                12 / 12 PASS (100%)
Regression Tests:              135 / 135 PASS (100%)
Total Automated Tests:         147 / 147 PASS (100%)
Biometric Pipeline Integrity:  100% Isolated & Preserved
Database Counts:               10 users, 57 scans, 2 students, 21 questions, 3 auth users
========================================================================================
```

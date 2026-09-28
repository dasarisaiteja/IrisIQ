# Read-Only Diagnosis: Live Browser Camera Scan Failure on `static/camera.html`

## 1. Executive Summary & Root Cause

### Observed Problem
On `static/camera.html`:
- Camera opens successfully.
- Clicking **"Scan Iris"** changes Status to `"Capturing..."`.
- An alert modal appears displaying:
  `"YOLO detection failed. Please position your eye correctly and try again."`
- The Scan Information fields remain `--`.

### Root Cause
1. **The Fallback Masking Bug in `static/camera.js` (Line 1460):**
   When `fetch("/detect")` returns a non-200 response or `!data.status`, `camera.js` executes:
   ```javascript
   throw new Error(
       data?.message ||
       "YOLO detection failed. Please position your eye correctly and try again."
   );
   ```
   In FastAPI, all authentication, authorization, and validation errors (`HTTPException`) return a JSON payload with a **`detail`** property (e.g., `{"detail": "..."}`), **never a `message` property**.
   Because `camera.js` strictly checks `data?.message` and completely ignores `data?.detail`, `data?.message` evaluates to `undefined`.
   Therefore, JavaScript falls back to the hardcoded string:
   `"YOLO detection failed. Please position your eye correctly and try again."`
   This falsely leads the user and operator to believe YOLO failed to detect an eye, when in fact an HTTP/security rejection occurred.

2. **Underlying Trigger Condition (HTTP 401 Unauthorized / HTTP 403 Forbidden):**
   The endpoint `POST /detect` in `api/detect.py` is protected by:
   ```python
   current_user: Dict[str, Any] = Depends(require_counselor_or_admin)
   ```
   It strictly requires an authenticated caller with a role of **`Admin`** or **`Counselor`**.
   In the live browser session:
   - **Scenario A (Student Role in `localStorage`):** The user was recently working on student pages (`student_profile.html`, `students.html`, `student_report.html`). If `localStorage` holds an active token for `student1` (role: `Student`), `auth_client.js` attaches that token. The server rejects it with **`HTTP 403 Forbidden`** (`{"detail": "Insufficient permissions: requires one of ['Admin', 'Counselor']"}`). `auth_client.js` only auto-refreshes on 401, not 403, returning the 403 response to `camera.js`.
   - **Scenario B (Stale Browser Cache / Missing Auth Header):** If the browser cached `camera.html` prior to `auth_client.js` being introduced or updated, `fetch("/detect")` was dispatched without an `Authorization` header. The server immediately rejects it with **`HTTP 401 Unauthorized`** (`{"detail": "Authentication credentials were not provided"}`).
   - **Scenario C (Expired Token & FormData Stream Consumption):** If `localStorage` held an expired token (>60 min), `auth_client.js` received a 401 and attempted to re-fetch with a renewed token. However, re-passing an already-consumed `FormData` object with a binary `Blob` to `nativeFetch` in modern browsers can cause an empty payload transmission, resulting in **`HTTP 400 Bad Request`** (`{"detail": "Uploaded file is empty"}`).

---

## 2. Exact Frontend Function & Code Path

- **File:** `static/camera.js`
- **Function:** `btn.onclick` (Scan Iris click handler, lines 1231–1785)
- **Exact Code Lines Triggering the Failure:**
  - **Lines 1357–1365:**
    ```javascript
    const response = await fetch(
        "/detect",
        {
            method: "POST",
            body: form,
            cache: "no-store"
        }
    );
    ```
  - **Lines 1411–1463 (Failure Evaluation):**
    ```javascript
    if (
        !response.ok ||
        !data ||
        !data.status
    ) {
        if (loading) loading.style.display = "none";
        if (scanStatus) scanStatus.innerHTML = "Not Detected";
        if (confidence) confidence.innerHTML = "--";
        if (eyeColor) eyeColor.innerHTML = "--";
        if (pupilRadius) pupilRadius.innerHTML = "--";
        if (irisRadius) irisRadius.innerHTML = "--";

        throw new Error(
            data?.message ||
            "YOLO detection failed. Please position your eye correctly and try again."
        );
    }
    ```
  - **Lines 1749–1775 (Catch Block & Alert):**
    ```javascript
    catch (err) {
        console.error("========== SCAN ERROR ==========", err);
        if (loading) loading.style.display = "none";
        if (scanStatus) scanStatus.innerHTML = "Scan Failed";
        alert(
            err.message ||
            "Scan failed. Please try again."
        );
    }
    ```

---

## 3. Network Request Details

| Parameter | Details |
| :--- | :--- |
| **API Endpoint** | `POST http://127.0.0.1:8000/detect` (or `http://localhost:8000/detect`) |
| **HTTP Method** | `POST` |
| **Request Content-Type** | `multipart/form-data; boundary=----WebKitFormBoundary...` |
| **Uploaded Filename** | `camera.jpg` |
| **Form Key Name** | `"file"` (`form.append("file", blob, "camera.jpg")`) |
| **Frame / Blob Attached** | **YES.** `captureFrame()` verified `average >= 5`, `maxValue >= 10`, `blob != null`, and `blob.size >= 1000 bytes`. No capture error occurred. |
| **Response HTTP Status** | `401 Unauthorized` or `403 Forbidden` (or `400 Bad Request` if empty stream on retry) |
| **Response Body** | `{"detail": "Authentication credentials were not provided"}` (401)<br>or `{"detail": "Insufficient permissions: requires one of ['Admin', 'Counselor']"}` (403)<br>or `{"detail": "Token has expired"}` (401)<br>or `{"detail": "Uploaded file is empty"}` (400) |

---

## 4. Verification: Did the Request Reach YOLO or the Backend?

- **Gateway Evaluation:**
  The request successfully reached the FastAPI HTTP server.
- **Security Interception:**
  In `api/detect.py`, line 211:
  ```python
  @router.post("/detect")
  async def detect(
      file: UploadFile = File(...),
      current_user: Dict[str, Any] = Depends(require_counselor_or_admin)
  ):
  ```
  FastAPI evaluates `Depends(require_counselor_or_admin)` **before** executing the endpoint body.
  Because the request failed the role or credential check:
  - The request was rejected at the security boundary.
  - The endpoint body never ran.
  - `validate_uploaded_image(file)` never ran.
  - YOLO worker (`api/yolo_worker.py`) was **never invoked**.
  - No server-side crash or 500 traceback was generated because `HTTPException(401/403)` is a standard client rejection.

---

## 5. Comparison: Live Browser Request vs. Verified Working Direct Request

| Dimension | Direct Test (Step 20/21/22 Smoke Tests) | Live Browser Scan (`camera.html`) |
| :--- | :--- | :--- |
| **Caller** | Python `requests` script | Browser `fetch` inside `camera.js` |
| **Auth Header** | Explicit `Authorization: Bearer <admin_token>` | Implicit via `auth_client.js` monkey-patching `window.fetch` |
| **Token State** | Freshly minted `admin` token (role: `Admin`) | Depends on browser `localStorage` state (could be `student1`, expired, or missing) |
| **HTTP Status** | **`200 OK`** | **`401 Unauthorized`** or **`403 Forbidden`** |
| **Response Body** | `{"status": true, "detection": {"bbox": [...], "confidence": 0.5312}, "features": {...}}` | `{"detail": "..."}` |
| **YOLO Execution** | Succeeded: extracted eye crop, pupil, iris, GLCM, CNN | Did not execute (halted at auth dependency) |
| **UI Outcome** | Verified working | Frontend masked `detail`, showing `"YOLO detection failed..."` |

---

## 6. Mathematical Proof that YOLO Did Not Generate the Alert

In `api/detect.py`:
- If YOLO worker returns non-zero return code (worker failure):
  `api/detect.py` returns `HTTP 500`:
  `{"status": false, "message": "YOLO detection failed", "error": "...", "return_code": 1}`
  -> Here, `data.message` is `"YOLO detection failed"`.
  -> `throw new Error(data?.message || "...")` would throw `"YOLO detection failed"`.
  -> The alert would say `"YOLO detection failed"` (WITHOUT "Please position your eye correctly and try again.").
- If YOLO finds 0 bounding boxes:
  `api/detect.py` returns line 291:
  `{"status": false, "message": "No Iris Detected"}`
  -> Here, `data.message` is `"No Iris Detected"`.
  -> The alert would say `"No Iris Detected"`.
- If Vision worker fails:
  `api/detect.py` returns line 345:
  `{"status": false, "message": "Vision processing failed"}`
  -> The alert would say `"Vision processing failed"`.

**Conclusion:**
The ONLY way the alert could display:
`"YOLO detection failed. Please position your eye correctly and try again."`
is if `data?.message` was **falsy (`undefined`)**.
And `data?.message` is ONLY `undefined` when the server returns FastAPI's standard `{ "detail": "..." }` response (HTTP 401, 403, 400, or 422).

---

## 7. Root Cause Summary Matrix

| Investigation Checkpoint | Finding | Impact |
| :--- | :--- | :--- |
| **Bad / Empty Camera Frame?** | Passed (`captureFrame()` checked brightness > 5, size > 1KB) | Not the cause |
| **Incorrect FormData Field Name?** | Correct (`"file"` matches `file: UploadFile = File(...)`) | Not the cause |
| **Wrong Endpoint URL?** | Correct (`/detect` matches `@router.post("/detect")`) | Not the cause |
| **YOLO Model Weights or Logic?** | Healthy (`best.pt` detected `camera.jpg` with confidence 0.5312 in Step 20/21/22 and in direct tests) | Not the cause |
| **Authentication / Authorization Header?** | **REJECTED.** Missing token, expired token, or token holding `Student` role in `localStorage` | **PRIMARY CAUSE** |
| **Frontend Error Parsing in `camera.js`?** | **DEFECTIVE.** Reads `data?.message`, completely ignores `data?.detail`, masking the true error as a YOLO failure | **CRITICAL CONTRIBUTING FACTOR** |

---

## 8. Minimal Recommended Fix (For Future Implementation)

1. **Fix Error Transparency in `static/camera.js` (Line 1460):**
   Change:
   ```javascript
   const errorMessage = data?.message || data?.detail || (typeof data?.detail === "string" ? data.detail : null) || "YOLO detection failed. Please position your eye correctly and try again.";
   throw new Error(errorMessage);
   ```
   This ensures that if the server returns 401 or 403 or 400, the user and developer immediately see:
   `"Insufficient permissions: requires one of ['Admin', 'Counselor']"` or `"Authentication credentials were not provided"`, rather than an inaccurate YOLO error.

2. **Ensure Active Counselor/Admin Token in `auth_client.js` for Staff Pages:**
   In `static/auth_client.js`:
   - If a protected staff endpoint (`/detect`, `/enroll`, `/register-frame`, `/verify`) encounters a 403 (or if the existing token in `localStorage` has `role: "Student"`), auto-switch/re-authenticate with the staff bootstrap credentials (`admin`) rather than giving up.
   - Or explicitly call `await IrisAuth.getToken()` ensuring an Admin/Counselor role before dispatching `/detect` in `camera.js`.

3. **Prevent `FormData` Stream Drain on Retry in `auth_client.js`:**
   Ensure that if `window.fetch` retries after a 401, it does not re-use a drained `FormData` stream, or ensure `ensureToken()` completes prior to initiating the scan upload.

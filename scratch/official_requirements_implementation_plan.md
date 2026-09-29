# IRIS Project: Official Requirements Phased Implementation Plan

**Objective:** Transform the existing IRIS platform into full compliance with `IRIS_Backend_Detailed_Requirements.docx` and `IRIS_Frontend_Detailed_Requirements.docx` through a safe, non-destructive, phased modernization strategy.

---

## Guaranteed Protection of Existing Work & Data Integrity
Throughout all 12 implementation phases, the following guarantees remain strictly in effect:
1. **Zero Database Drops:** No existing tables (`iris_users`, `iris_embeddings`, `scan_history`, `student_profiles`, `student_assessments`, `report_versions`, `app_users`, `academic_records`) will be dropped or modified destructively.
2. **Preservation of Machine Learning Assets:** The YOLO eye detector (`yolo11n.pt`), CNN model weights (`models/iris_cnn.h5`), and OpenCV segmentation/normalization algorithms will not be altered or replaced; they will be wrapped in new service facades.
3. **Data Migration Compatibility:** Existing student profiles (`STU-001`, `STU-002`) and historical scan records will remain completely intact and accessible.
4. **Non-Breaking API Evolution:** Existing endpoints will remain operational during development, with new official endpoints introduced under canonical RESTful routes.

---

## Phase-by-Phase Implementation Roadmap

### Phase 1: Data Model & Student/Assessment Foundation
* **Primary Objective:** Introduce the required core relational tables, indexes, and foreign keys in `iris_database.db` via non-destructive `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE` statements.
* **Database Changes:**
  - `roles`: `(id INTEGER PRIMARY KEY, role_name TEXT UNIQUE NOT NULL, description TEXT)`
  - `assessments`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT UNIQUE NOT NULL, student_id TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT, updated_at TEXT, FOREIGN KEY(student_id) REFERENCES student_profiles(student_id))`
  - `eye_scans`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE NOT NULL, assessment_id TEXT NOT NULL, eye_side TEXT NOT NULL CHECK(eye_side IN ('LEFT', 'RIGHT')), file_reference TEXT NOT NULL, status TEXT NOT NULL, result_reference TEXT, error_code TEXT, error_message TEXT, created_at TEXT NOT NULL, completed_at TEXT, FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id))`
  - `analysis_results`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT UNIQUE NOT NULL, results_json TEXT NOT NULL, model_version TEXT, created_at TEXT NOT NULL, FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id))`
  - `reports`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, report_id TEXT UNIQUE NOT NULL, assessment_id TEXT NOT NULL, student_id TEXT NOT NULL, version TEXT NOT NULL, payload_json TEXT NOT NULL, pdf_reference TEXT, status TEXT NOT NULL, reviewed_status INTEGER DEFAULT 0, reviewed_by TEXT, reviewed_at TEXT, created_at TEXT NOT NULL, FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id))`
  - `counsellor_assignments`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT NOT NULL, student_id TEXT NOT NULL, counsellor_id TEXT NOT NULL, assigned_by TEXT NOT NULL, assigned_at TEXT NOT NULL, is_active INTEGER DEFAULT 1, FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id))`
  - `counselling_notes`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT NOT NULL, counsellor_id TEXT NOT NULL, note_text TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id))`
  - `follow_ups`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT NOT NULL, counsellor_id TEXT NOT NULL, title TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT DEFAULT 'Pending', created_at TEXT NOT NULL, updated_at TEXT, FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id))`
  - `audit_logs`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, role TEXT, assessment_id TEXT, action TEXT NOT NULL, status TEXT NOT NULL, ip_address TEXT, correlation_id TEXT, timestamp TEXT NOT NULL)`
  - `processing_logs`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT NOT NULL, stage TEXT NOT NULL, message TEXT, error_trace TEXT, created_at TEXT NOT NULL)`
* **Backend APIs Created/Modified:**
  - Core database initialization helper in `database.py` or new `database_official.py`.
* **Frontend Changes:** None (backend foundation).
* **Automated Tests:** Schema verification test verifying all 10 new tables exist, columns match specs, and foreign key constraints enforce integrity.
* **Backward Compatibility:** All existing tables remain 100% untouched.

---

### Phase 2: Student Registration & Assessment Inception
* **Primary Objective:** Replace legacy customer/employee enrollment with compliant Student Registration enforcing minimum required fields (`Student ID` and `Student Name`), atomic assessment creation, and a confirmation screen.
* **Files Likely to Change:**
  - `api/students.py` (New router)
  - `main.py` (Register router)
  - `static/register.html` (Form redesign)
  - `static/register.js` (Form logic)
* **Backend APIs:**
  - `POST /api/students`: Validates `student_id` uniqueness, creates record in `student_profiles`, creates corresponding initial assessment in `assessments` table (`status='REGISTERED'`), and returns `{student_id, full_name, assessment_id}`.
  - `GET /api/students/{studentId}`: Retrieves student record with current assessment status.
  - `GET /api/students`: Lists students with active assessment details.
  - `PUT /api/students/{studentId}`: Updates approved student fields.
  - `PATCH /api/students/{studentId}/status`: Activates, deactivates, or archives student.
* **Frontend Changes:**
  - Redesign `register.html` to remove the live camera element, frame-counter, and legacy fields.
  - Fields: `Student ID` (required) and `Student Name` (required).
  - Action buttons: `Register / Continue`, `Cancel`, `Reset`.
  - Registration Success Modal / Screen displaying Student ID, Student Name, generated Assessment ID, and primary CTA button: **"Start Eye Scan"** linking to `camera.html?assessment_id={id}`.
* **Automated Tests:**
  - Double-click duplicate prevention test (returns 409 Conflict).
  - Validation test for missing Student ID or Name (returns 422/400).
  - Successful registration test confirming both student and assessment records are created atomically.

---

### Phase 3: Dual (LEFT / RIGHT) Eye Scan Workflow
* **Primary Objective:** Build dedicated Left and Right eye scan endpoints and an updated camera interface enforcing separate, mandatory captures on the same Assessment ID.
* **Files Likely to Change:**
  - `api/eye_scans.py` (New router)
  - `services/eye_pipeline.py` (CV pipeline wrapper)
  - `static/camera.html` (Dual-card UI)
  - `static/camera.js` (Capture & status management)
* **Backend APIs:**
  - `POST /api/assessments/{assessmentId}/scan/left`: Validates file (size, magic bytes), executes YOLO eye crop, pupil detection, iris segmentation, normalization, and quality analysis; persists scan in `eye_scans` (`eye_side='LEFT'`); transitions assessment status.
  - `POST /api/assessments/{assessmentId}/scan/right`: Same as left scan for right eye side.
  - `GET /api/assessments/{assessmentId}/scan/status`: Returns `{left: {status, quality}, right: {status, quality}, both_completed: bool}`.
  - `GET /api/assessments/{assessmentId}/scan/{eye}`: Returns approved metadata and diagnostics.
  - `POST /api/assessments/{assessmentId}/scan/{eye}/retry`: Resets scan record for that eye side to allow re-upload.
* **Frontend Changes:**
  - Header: Displays IRIS branding, Student ID, Student Name, Assessment ID, current status badge.
  - Progress bar: Registration $\rightarrow$ Left Eye $\rightarrow$ Right Eye $\rightarrow$ Analysis $\rightarrow$ Report.
  - Two distinct cards:
    * **Left Eye Card:** Camera viewport, targeting reticle, "Start Left Eye Scan" button, status badge, "Retry" button.
    * **Right Eye Card:** Camera viewport, targeting reticle, "Start Right Eye Scan" button, status badge, "Retry" button.
  - Bottom bar: "Continue / Generate Analysis" button, **disabled** until both eyes are confirmed completed by the backend.
  - Remove role restriction blocking students from accessing the camera page.
* **Automated Tests:**
  - Verify left and right scans belong to the exact same Assessment ID.
  - Test independent retry (retrying left scan does not wipe right scan).
  - Verify continue action fails if only one scan is completed.

---

### Phase 4: Assessment State Machine Engine
* **Primary Objective:** Implement the centralized assessment lifecycle engine enforcing the 10 official workflow states and transition rules.
* **Files Likely to Change:**
  - `services/assessment_workflow.py` (State machine service)
  - `api/assessments.py` (Router for state queries)
* **Backend APIs:**
  - `POST /api/assessments`: Manual assessment creation if initiated outside registration.
  - `GET /api/assessments/{assessmentId}`: Detailed assessment metadata.
  - `GET /api/assessments/{assessmentId}/status`: Returns current state machine state and next allowed transitions.
  - `GET /api/students/{studentId}/assessments`: History of assessments for student.
* **State Machine Rules Enforced:**
  - `REGISTERED` $\rightarrow$ `SCAN_PENDING` (when camera page opens).
  - `SCAN_PENDING` $\rightarrow$ `LEFT_SCAN_COMPLETED` (left scan uploaded & validated).
  - `SCAN_PENDING` $\rightarrow$ `RIGHT_SCAN_COMPLETED` (right scan uploaded & validated).
  - `LEFT_SCAN_COMPLETED` or `RIGHT_SCAN_COMPLETED` $\rightarrow$ `SCAN_COMPLETED` (both scans confirmed).
  - `SCAN_COMPLETED` $\rightarrow$ `PROCESSING` (analysis triggered).
  - `PROCESSING` $\rightarrow$ `ANALYSIS_COMPLETED` (AI job completes).
  - `ANALYSIS_COMPLETED` $\rightarrow$ `REPORT_GENERATING` (report build initiated).
  - `REPORT_GENERATING` $\rightarrow$ `REPORT_READY` (report data and PDF ready).
  - Any state $\rightarrow$ `FAILED` on unrecoverable validation/system failure.
* **Automated Tests:**
  - Attempt invalid transition (e.g. `SCAN_PENDING` $\rightarrow$ `REPORT_READY`) and assert 409 Conflict.
  - Verify idempotency on repeated state transition calls.

---

### Phase 5: Analysis Processing & AI Integration
* **Primary Objective:** Wire the feature fusion, psychometric scoring, and computer vision diagnostics into an asynchronous job triggered after both scans are complete.
* **Files Likely to Change:**
  - `api/analysis.py` (New router)
  - `services/analysis_orchestrator.py` (New orchestrator)
  - `static/processing.html` or modal in `static/camera.html`
* **Backend APIs:**
  - `POST /api/assessments/{assessmentId}/process`: Verifies `status == 'SCAN_COMPLETED'`; sets status to `PROCESSING`; launches analysis job.
  - `GET /api/assessments/{assessmentId}/process/status`: Returns `{status, progress_percent, stage, error}`.
  - `GET /api/assessments/{assessmentId}/results`: Returns final structured analysis dictionary.
* **Frontend Changes:**
  - Clicking "Continue / Generate Analysis" transitions user to a dedicated Processing view.
  - UI displays an animated analysis pipeline (Extracting biometrics $\rightarrow$ Evaluating cognitive indicators $\rightarrow$ Synthesizing report).
  - Polls `process/status` every 1.5 seconds. Automatically redirects to Report upon completion.
* **Automated Tests:**
  - Ensure processing cannot be started if left or right scan is missing (returns 409 Conflict).
  - Verify results are accurately persisted in `analysis_results` table.

---

### Phase 6: Role Dashboards (Admin & Student)
* **Primary Objective:** Build the official Admin Dashboard widgets and implement the dedicated Student Self-Service Dashboard.
* **Files Likely to Change:**
  - `api/dashboard.py` (Update summary endpoint)
  - `api/student_portal.py` (New student self-service router)
  - `static/dashboard.html`, `static/dashboard.js` (Admin widgets)
  - `static/student_dashboard.html`, `static/student_dashboard.js` (New student portal)
* **Backend APIs:**
  - `GET /api/admin/dashboard/summary`: Returns `{total_students, total_assessments, pending_scans, processing, reports_ready, counsellors}`.
  - `GET /api/student/me`: Authenticated student's own profile.
  - `GET /api/student/assessment`: Authenticated student's active assessment record.
  - `GET /api/student/assessment/status`: Authenticated student's scan and analysis status.
  - `GET /api/student/report`: Authenticated student's report.
* **Frontend Changes:**
  - **Admin Dashboard:** Update cards to reflect the 6 required metric counters; update tables to display Recent Students and Recent Assessments. Update sidebar to match the 12 required navigation items.
  - **Student Dashboard:** Clean, responsive portal displaying student ID/name, current assessment status, Left Eye scan badge, Right Eye scan badge, Report ready badge, and contextual CTA button ("Start Scan", "Resume Scan", "View Report").
* **Automated Tests:**
  - Test student dashboard API isolation: ensure student token cannot access admin summary endpoint (HTTP 403).
  - Verify admin summary reflects exact database counts.

---

### Phase 7: Counsellor Workflow & Student Assignment
* **Primary Objective:** Build counsellor assignment, note taking, follow-up scheduling, and enforce strict counsellor isolation.
* **Files Likely to Change:**
  - `api/counsellor.py` (New router)
  - `security/auth.py` (Strict assignment check)
  - `static/counsellor_dashboard.html`, `static/counsellor_dashboard.js` (New view)
  - `static/counsellor_review.html`, `static/counsellor_review.js` (New review view)
* **Backend APIs:**
  - `GET /api/counsellors/students`: Returns students assigned to the calling counsellor.
  - `POST /api/assessments/{assessmentId}/assign-counsellor`: Admin assigns a counsellor.
  - `GET /api/counsellors/{counsellorId}/students`: Admin queries counsellor portfolio.
  - `POST /api/assessments/{assessmentId}/counselling-notes`: Counsellor adds note.
  - `GET /api/assessments/{assessmentId}/counselling-notes`: Retrieves notes.
  - `POST /api/assessments/{assessmentId}/follow-ups`: Creates follow-up task.
  - `PUT /api/follow-ups/{followUpId}`: Updates follow-up task status.
  - `PATCH /api/assessments/{assessmentId}/reviewed`: Marks report officially reviewed.
* **Security Hardening:**
  - Update `check_student_access()` in `security/auth.py`: If caller is a Counsellor, verify an active row exists in `counsellor_assignments` for that student/assessment; otherwise raise HTTP 403 Forbidden.
* **Frontend Changes:**
  - **Counsellor Dashboard:** Displays Assigned Students, Reports Ready for Review, Pending Counselling, Follow-up Calendar, and Recent Reviews.
  - **Counsellor Review View:** Full report preview with inline "Add Counselling Note", "Schedule Follow-up", and "Mark Report Reviewed" controls.
* **Automated Tests:**
  - Counsellor isolation test: Verify Counsellor A receives HTTP 403 when requesting records of student assigned to Counsellor B.
  - Note creation test: Verify note binds to correct assessment and counsellor ID.

---

### Phase 8: Structured Report Contract & Server-Side PDF Generation
* **Primary Objective:** Align the report generation service with the official 10-section JSON contract and build a reliable server-side PDF generator.
* **Files Likely to Change:**
  - `services/report_contract_mapper.py` (New JSON contract mapper)
  - `services/pdf_generator.py` (Server-side PDF generation engine)
  - `api/reports.py` (Official reports router)
  - `static/student_report.html`, `static/student_report.js` (UI realignments)
* **Backend APIs:**
  - `POST /api/assessments/{assessmentId}/report/generate`: Compiles official 10-section JSON and stores in `reports`.
  - `GET /api/assessments/{assessmentId}/report`: Returns official structured JSON.
  - `GET /api/assessments/{assessmentId}/report/pdf`: Generates / streams official PDF file.
  - `GET /api/reports`: Admin global report directory.
  - `GET /api/reports/{reportId}`: Detailed report lookup.
* **Official Report JSON Contract Implemented:**
  `student`, `assessment`, `eye_scan` (left & right), `overall_result`, `behaviour`, `personality`, `subjects_interest`, `recommendations`, `counselling`, `report_meta`.
* **Frontend Changes:**
  - Align `student_report.html` to render the 10 official sections cleanly.
  - Replace client-side `html2pdf.js` with direct link to `GET /api/assessments/{id}/report/pdf`.
* **Automated Tests:**
  - Validate JSON schema of `/report` response against the official 10-section specification.
  - Verify PDF generation produces a valid, readable PDF stream (`application/pdf`).

---

### Phase 9: Unified Audit Logging & Error Standards
* **Primary Objective:** Implement structured audit logging, processing logs, and standardize API error envelopes across all endpoints.
* **Files Likely to Change:**
  - `services/audit_logger.py` (Audit logging service)
  - `api/admin.py` (Audit logs query endpoint)
  - `main.py` (Global exception handler)
* **Backend APIs:**
  - `GET /api/admin/audit-logs`: Admin query for audit events (user, action, status, timestamp).
* **Logging Standards:**
  - Automatically log: registration, login, scan uploads, scan completions, analysis jobs, report generations, counsellor assignments, report reviews.
  - Sanitize all log payloads (no passwords, tokens, or biometric raw arrays in logs).
* **Error Standards:**
  - Standardized error format: `{status: false, error_code: "DUPLICATE_STUDENT", message: "Student ID already exists", details: {...}}`.
* **Automated Tests:**
  - Trigger login and scan events; verify corresponding records appear in `audit_logs`.
  - Verify error responses return standard envelope without leaking tracebacks.

---

### Phase 10: Frontend Completion, Public Website & Responsiveness
* **Primary Objective:** Finalize public website pages, navigation bars, mobile breakpoints, and visual polish across all viewports.
* **Files Likely to Change:**
  - `static/index.html` (Hero, How It Works, Features)
  - `static/contact.html` (Form wired to API)
  - `static/index.css` (Responsive media queries)
  - `static/auth_client.js` (Unified navbar badge rendering)
* **Frontend Deliverables:**
  - Public Home Page: Eye-assessment branding, CTA buttons ("Get Started", "Login").
  - "How It Works" 6-step responsive workflow diagram.
  - Contact enquiry form connected to backend.
  - Responsive validation across desktop (1920x1080, 1440x900), tablet (768px), and mobile (375px).
* **Automated Tests:**
  - Browser subagent verification of desktop and mobile navigation menus, button clicks, and form submissions.

---

### Phase 11: Comprehensive Security Verification & Hardening
* **Primary Objective:** Validate the complete security boundary against OWASP API Security Top 10.
* **Files Likely to Change:**
  - `security/auth.py`
  - `security/upload_validator.py`
  - `main.py` (Rate limiting middleware)
* **Security Checks Verified:**
  1. **RBAC:** Verify Admin, Counsellor, and Student permission boundaries.
  2. **BOLA/IDOR:** Verify students cannot view other students' scans, assessments, or reports.
  3. **Counsellor Isolation:** Verify counsellors cannot view unassigned students.
  4. **Rate Limiting:** Protect login and scan endpoints against brute force.
  5. **Biometric Storage Defense:** Verify raw scans in `uploads/` are never exposed over public web roots.
  6. **Path Traversal:** Ensure `/api/media` and report download paths reject traversal characters (`../`, null bytes).
* **Automated Tests:**
  - Dedicated regression security test suite covering all 6 threat vectors.

---

### Phase 12: End-to-End Acceptance Testing & Certification
* **Primary Objective:** Execute full end-to-end user journeys validating complete compliance against the official specification documents.
* **User Journeys Certified:**
  1. **Journey 1 (Student Self-Service):**
     Public Home $\rightarrow$ Get Started $\rightarrow$ Register Student (ID + Name) $\rightarrow$ Assessment Created $\rightarrow$ Left Eye Scan $\rightarrow$ Right Eye Scan $\rightarrow$ Continue to Analysis $\rightarrow$ Structured Report Displayed $\rightarrow$ PDF Downloaded.
  2. **Journey 2 (Admin Management):**
     Admin Login $\rightarrow$ Dashboard Summary (6 metrics) $\rightarrow$ Student Directory $\rightarrow$ Assign Counsellor to Assessment $\rightarrow$ Audit Log Inspection.
  3. **Journey 3 (Counsellor Review):**
     Counsellor Login $\rightarrow$ Counsellor Dashboard $\rightarrow$ Assigned Student Queue $\rightarrow$ Open Student Report $\rightarrow$ Add Counselling Note $\rightarrow$ Schedule Follow-up $\rightarrow$ Mark Report Reviewed.
* **Deliverable:** Acceptance Sign-off Matrix confirming 100% compliance across all requirements.

---
*End of Phased Implementation Plan.*

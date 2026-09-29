# IRIS Project: Official Requirements Gap Analysis
**Documents Audited:**
1. `IRIS_Backend_Detailed_Requirements.docx`
2. `IRIS_Frontend_Detailed_Requirements.docx`

**Audit Type:** Read-Only Architectural, Frontend, Backend, Database, and Security Gap Analysis  
**Repository:** `iris-ai-code`  
**Date:** September 2026  
**Auditor:** Antigravity AI Senior Systems Architect

---

## 1. Executive Summary & Required Product Overview

The IRIS platform has received two new authoritative specification documents establishing the official end-to-end product workflow, UI/UX screens, API contracts, database schema, security rules, and role permissions.

### 1.1 Target Product Workflow
The required system follows an explicit linear pipeline with role-governed branches:
```
Public Website (Home, About, How It Works, Features, Contact)
   │
   ├──> Role-Based Login (Admin, Student, Counsellor)
   │
   └──> Get Started / Student Registration (Student ID, Student Name minimum)
           │
           ▼
      Assessment Creation (Generates unique Assessment ID, Status: REGISTERED -> SCAN_PENDING)
           │
           ▼
      Dual Eye Scan Page (Mandatory separate scans on same Assessment ID)
      ├── LEFT Eye Scan  --> Validated/Stored --> Status: LEFT_SCAN_COMPLETED
      └── RIGHT Eye Scan --> Validated/Stored --> Status: RIGHT_SCAN_COMPLETED
           │
           ▼ (Backend confirms BOTH scans complete -> Status: SCAN_COMPLETED)
      Analysis Processing (Async / Polling -> Status: PROCESSING -> ANALYSIS_COMPLETED)
           │
           ▼
      Structured Report & PDF Generation (Status: REPORT_GENERATING -> REPORT_READY)
           │
           ├──> Student Dashboard (Own profile, scan status, structured report, PDF download)
           ├──> Counsellor Dashboard (Assigned students only, report review, notes, follow-ups)
           └──> Admin Dashboard (Full system metrics, all students, assessments, reports, logs)
```

### 1.2 The Three System Roles
1. **Admin:** Full management across users, roles, students, assessments, eye scans, reports, counsellors, assignments, and audit logs.
2. **Student:** Self-service access restricted exclusively to own profile, own assessment, own eye scan workflow, and own structured report/PDF.
3. **Counsellor:** Strictly restricted to assigned students, report review, counselling notes, and follow-up tracking. **No access to unassigned students.**

### 1.3 Baseline Compliance Scorecard
* **Overall Compliance:** **34.2%**
* **Frontend Compliance:** **28.5%**
* **Backend API Compliance:** **31.4%**
* **Database Compliance:** **38.5%**
* **Security & Authorization Compliance:** **52.0%**

---

## 2. Frontend Detailed Audit

### 2.1 Public Website (`static/index.html`, `about.html`, `features.html`, `technology.html`, `contact.html`)
| Requirement Area | Specification Requirement | Current Implementation | Gap & Conflict Analysis | Compliance Status |
|---|---|---|---|---|
| **Branding & Purpose** | IRIS eye-assessment & student intelligence overview | Legacy "Secure Identity Verification Using Iris AI" biometric security framing | Focus is on biometric access control / employee verification rather than student assessment. | **PARTIAL** |
| **Call to Action (CTA)** | "Get Started", "Login", "Learn More" | "Start Live Scan" (`register.html`), "Watch Demo" (`#features`), "Login" (`login.html`) | "Start Live Scan" leads to legacy customer webcam frame capture rather than Student Registration. | **PARTIAL** |
| **How It Works Section** | Must depict: `Register -> Left Eye -> Right Eye -> Analysis -> Report -> Counselling` | Missing entirely as a dedicated section or page. | No explanation of the dual-eye scan or student assessment lifecycle. | **MISSING** |
| **Features / Benefits** | Assessment, report, and counselling benefits | Biometric accuracy (99.8%), verification speed (<1s), 24x7 security protection | Highlights physical access metrics rather than academic/psychometric/counselling benefits. | **CONFLICT** |
| **Contact Page** (`contact.html`) | Contact info + functional enquiry form connected to backend | Static HTML form (`<form>`) with no ID, no JS event listener, and no backend API connection | Submitting refreshes the page with GET query params; backend has no `/api/contact` endpoint. | **PARTIAL** |
| **Header & Navigation** | Logo, Home, About, How It Works, Features, Contact, Login, Get Started | Logo, Home, About, Features, Technology, Contact, Start Scan, Login | Missing "How It Works" nav link; "Technology" is present; "Start Scan" should be "Get Started". | **PARTIAL** |

### 2.2 Authentication UI (`static/login.html`, `static/auth_client.js`)
| Requirement Area | Specification Requirement | Current Implementation | Gap & Conflict Analysis | Compliance Status |
|---|---|---|---|---|
| **Role Selection** | Three clear role choices: Admin, Student, Counsellor with distinct fields/routes | Single unified username/password form with quick-fill demo chips | Does not present 3 explicit role tabs/cards for Admin, Student, and Counsellor. | **PARTIAL** |
| **Admin Success Route** | Redirect to Admin Dashboard | Redirects to `/static/dashboard.html` | Works as intended. | **PASS** |
| **Student Success Route** | Redirect to Student Dashboard | Redirects to `/static/student_profile.html` | `student_profile.html` is an administrative data-entry view, not a student self-service dashboard. | **CONFLICT** |
| **Counsellor Success Route**| Redirect to Counsellor Dashboard | Redirects to `/static/dashboard.html` (Admin dashboard) | Counsellor is directed to the shared staff dashboard rather than a dedicated Counsellor portal. | **CONFLICT** |
| **Route Protection** | Strict role-based route guard preventing cross-role URL navigation | `auth_client.js` checks tokens and attaches Bearer headers, but frontend pages do not systematically guard routes | A student can type `/static/dashboard.html` or `/static/students.html` into the address bar without being bounced back to student dashboard by the page itself. | **PARTIAL** |
| **Logout & Expiry** | Clear session/token and return to Login/Public Home | `window.IrisAuth.clearAuth()` clears `localStorage` | Functional, but there is no server-side token revocation or session invalidation endpoint. | **PARTIAL** |

### 2.3 Admin Dashboard (`static/dashboard.html`, `static/dashboard.js`)
| Requirement Area | Specification Requirement | Current Implementation | Gap & Conflict Analysis | Compliance Status |
|---|---|---|---|---|
| **Total Students Widget** | Count -> Click opens Student List | Displays `totalUsers` (Total Employees) | Shows `iris_users` count, not `student_profiles` count. | **CONFLICT** |
| **Total Assessments Widget**| Count -> Click opens Assessment List| Missing | No assessment count widget exists. | **MISSING** |
| **Pending Scans Widget** | Count -> Click opens Pending Scan List | Missing | No scan state aggregation widget. | **MISSING** |
| **Processing Widget** | Count -> Click opens Processing List | Missing | No active analysis queue widget. | **MISSING** |
| **Reports Ready Widget** | Count -> Click opens Report List | Missing | No reports ready counter. | **MISSING** |
| **Counsellors Widget** | Count -> Click opens Counsellor Mgmt | Missing | No counsellor metrics or directory widget. | **MISSING** |
| **Recent Students List** | Latest student records -> Click opens detail | Table shows Recent Activity (`dashboard_activity`) | Shows system activities, not student directory records. | **CONFLICT** |
| **Recent Assessments List** | Latest assessment status/activity | Table shows Scan History (`scan_history`) | Displays raw biometric match scores (e.g., `IR-20260805-... Matched`), not assessment workflows. | **CONFLICT** |
| **Required Sidebar Menu** | Dashboard, Students, Assessments, Eye Scans, Reports, Counsellors, Counselling/Follow-up, Users/Roles, Notifications, Settings, Profile, Logout | Dashboard, Students, Live Iris Scan, Register Employee, Assessments, Student Profile, AI Profile, Recommendations, Report V2, Report V1, About | Mismatched structure; contains legacy employee links and separate V1/V2 report links; missing Counsellors, Users/Roles, Settings. | **CONFLICT** |

### 2.4 Admin Student List (`static/students.html`, `static/students.js`)
| Column Required | Current Column in `students.html` | Status | Notes |
|---|---|---|---|
| **Student ID** | `Student ID` | **PASS** | Displays `student_id` (e.g. `STU-001`). |
| **Student Name** | `Student` (Avatar + Full Name) | **PASS** | Displays full name and profile photo. |
| **Assessment Status** | Missing | **MISSING** | Shows `Biometric Iris Link` instead of assessment workflow state. |
| **Left Eye Scan** | Missing | **MISSING** | No left eye completion status column. |
| **Right Eye Scan** | Missing | **MISSING** | No right eye completion status column. |
| **Report Status** | Missing | **MISSING** | No report ready / not ready indicator. |
| **Assigned Counsellor**| Missing | **MISSING** | No assigned counsellor column. |
| **Date** | Missing | **MISSING** | No registration or assessment date column. |
| **Actions** | Profile, Assess, AI Profile, Report V2 | **PARTIAL** | Missing `Assign Counsellor`, `Start Scan`, and unified workflow actions. |

### 2.5 Student Registration (`static/register.html`, `static/register.js`)
* **Page Identity:** Currently titled **"Customer Registration"** (legacy employee/customer enrollment).
* **Required Minimum Fields:** `Student ID` and `Student Name`.
* **Legacy Fields Currently Present on Form:**
  1. `employee_code` (labeled "Customer Code")
  2. `user_name` (labeled "Customer Name")
  3. `department`
  4. `designation`
  5. `gender`
  6. `age`
  7. `dob` (Date of Birth)
  8. `blood_group`
  9. `mobile`
  10. `email`
  11. `address`
* **Severe Architecture Conflict:**
  `register.html` embeds a live video element (`#video`) and a `0 / 40` frame-capture loop that streams 40 base64 frames to `/register-frame` followed by `/enroll`.
  * **Requirement:** Registration is purely a form submission (`POST /api/students`). Upon success, it displays a **Registration Success Screen** with Student ID, Student Name, and generated Assessment ID, with a primary CTA button: **"Start Eye Scan"** navigating to the separate Eye Scan page. Camera scanning does NOT belong on the registration page.
* **Missing Form Controls:** `Cancel` and `Reset` buttons are missing.

### 2.6 Eye Scan Page (`static/camera.html`, `static/camera.js`)
| Requirement Area | Specification Requirement | Current Implementation | Gap & Conflict Analysis | Compliance Status |
|---|---|---|---|---|
| **Left Eye Scan** | Dedicated Left Eye card, instructions, Start Scan, status badge, Retry | Single unseparated camera view with generic "Scan Iris" button | Cannot target the left eye specifically; treats any eye as generic. | **CONFLICT** |
| **Right Eye Scan** | Dedicated Right Eye card, instructions, Start Scan, status badge, Retry | Missing | No right eye scan interface or tracking. | **MISSING** |
| **Assessment ID Scope**| Both scans must bind to the same Assessment ID | Binds to `sessionStorage.getItem("employee_code")` | Works off employee codes, with zero assessment scoping. | **CONFLICT** |
| **Completion Confirmation**| Backend must confirm completion; frontend cannot manually set it | Scans directly call `/detect` then `/verify` to match against `iris_users` | Marks match/mismatch against all employee templates, not confirming assessment scan completeness. | **CONFLICT** |
| **Action Gating** | "Continue / Generate Analysis" disabled until BOTH eyes complete | Single "Scan Iris" button; immediately triggers verify comparison | No two-eye validation or gating of downstream analysis. | **CONFLICT** |
| **Role Restriction** | Students must be able to perform scans for their own assessment | Line 8-12: `if (currentRole === "Student") throw new Error(...)` | Students are explicitly forbidden and bounced to profile! Directly violates student workflow. | **CONFLICT** |

### 2.7 Analysis Processing UI
* **Specification:** After both scans complete, user clicks "Continue / Generate Analysis". Page displays active "Processing / Analyzing" state, polls backend processing status, and automatically transitions to Report upon completion (or displays safe error + Retry).
* **Current Implementation:** **MISSING.** No dedicated analysis processing screen exists. In the existing code, `/api/profile/{student_id}/analyze` is invoked synchronously via button click on `assessments.html`.

### 2.8 Student Dashboard
* **Specification:** Self-service portal showing:
  - Profile (Student ID, Name)
  - Current Assessment Status
  - Left Eye Status (Pending / Completed)
  - Right Eye Status (Pending / Completed)
  - Report Status (Ready / Not Ready)
  - Contextual CTA (Start Scan / Continue Scan / View Report)
  - Strict student-only isolation (no admin/counsellor navigation).
* **Current Implementation:** **MISSING.** Students are currently redirected to `student_profile.html`, which is a complex institutional form with academic mark entry modals, skill forms, and full staff header controls.

### 2.9 Student Report (`static/student_report.html`, `static/student_report.js`)
* **Specification Contract:**
  1. Header: IRIS, report title, Student ID, Student Name, Assessment ID, assessment date, generated date.
  2. Student Information.
  3. Left Eye Scan status/result.
  4. Right Eye Scan status/result.
  5. Combined overall assessment result.
  6. Behaviour analysis (backend categories/scores/descriptions).
  7. Personality analysis (backend categories/scores/descriptions).
  8. Subjects & interests recommendations.
  9. Counselling notes/status where permitted.
  10. Server-generated PDF download.
* **Current Implementation:**
  - Contains 32 sections compiled from survey questionnaires and academic marks (`services/report_v2_generator.py`).
  - Does NOT show separate Left and Right eye scan results.
  - Does NOT display Assessment ID.
  - Does NOT display Counselling review status or counsellor notes.
  - PDF generation is performed purely in client-side JavaScript via `html2pdf.js`, which renders distorted multi-page canvas prints rather than calling a secure server-side PDF endpoint.

### 2.10 Counsellor Dashboard & Counsellor Student/Report View
* **Specification:**
  - Dedicated Counsellor Dashboard: Assigned Students list, Reports Ready for review, Pending Counselling queue, Follow-ups due, Recent Activity.
  - Counsellor Student/Report View: Full student report + "Add Counselling Note", "Add Follow-up (date, task, status)", "Mark Report Reviewed".
* **Current Implementation:** **MISSING.** No counsellor dashboard or review interfaces exist anywhere in the frontend.

---

## 3. Backend Detailed Audit

### 3.1 API Endpoint Mapping Matrix
All required official endpoints are mapped below against the current implementation in `api/`:

| Endpoint | Method | Required Purpose | Current Endpoint | Status | Notes / Gaps |
|---|---|---|---|---|---|
| `/api/auth/login` | POST | Role-based login | `/api/auth/login` | **IMPLEMENTED** | Generates HS256 JWT; requires payload adjustment to support role selection. |
| `/api/auth/logout` | POST | Invalidate/close session | Missing | **MISSING** | Currently logout is client-side only (`localStorage.removeItem`). |
| `/api/auth/refresh` | POST | Refresh JWT access token | Missing | **MISSING** | No refresh token rotation implemented. |
| `/api/auth/me` | GET | Return current user/role | `/api/auth/me` | **IMPLEMENTED** | Returns `{username, role, full_name, email}`. |
| `/api/students` | POST | Create student (Student ID + Name) | `/api/profile/students` | **CONFLICTING** | Prefix is `/api/profile/students`, expects full demographic payload, and does not generate an Assessment ID. |
| `/api/students/{id}` | GET | Get approved student profile | `/api/profile/{id}` | **CONFLICTING** | Path mismatch (`/api/profile/{id}`). |
| `/api/students` | GET | Admin list/search/filter | `/api/profile/students` | **CONFLICTING** | Path mismatch; returns flat list without assessment/scan status aggregations. |
| `/api/students/{id}` | PUT | Update approved student fields | Missing | **MISSING** | No student update endpoint. |
| `/api/students/{id}/status`| PATCH | Change student status | Missing | **MISSING** | No student status management endpoint. |
| `/api/assessments` | POST | Create assessment for student | Missing | **MISSING** | Currently `/api/profile/assessment` only submits psychometric question responses. |
| `/api/assessments/{id}` | GET | Get assessment metadata/status | Missing | **MISSING** | No assessment entity lookup endpoint. |
| `/api/assessments/{id}/status`| GET | Get workflow state machine status | Missing | **MISSING** | No state machine query endpoint. |
| `/api/students/{id}/assessments`| GET | Assessment history for student | `/api/profile/{id}/assessments` | **CONFLICTING** | Returns raw question domain scores, not assessment workflow records. |
| `/api/assessments/{id}/scan/left`| POST | Upload/process LEFT eye | Missing | **MISSING** | Current scan endpoints are `/detect`, `/enroll`, and `/verify` based on employee codes. |
| `/api/assessments/{id}/scan/right`| POST | Upload/process RIGHT eye | Missing | **MISSING** | No right eye endpoint exists. |
| `/api/assessments/{id}/scan/status`| GET | Return both eye statuses | Missing | **MISSING** | No dual scan status endpoint. |
| `/api/assessments/{id}/scan/{eye}`| GET | Return approved eye metadata | Missing | **MISSING** | No scan metadata endpoint. |
| `/api/assessments/{id}/scan/{eye}/retry`| POST| Retry failed scan | Missing | **MISSING** | No retry endpoint. |
| `/api/assessments/{id}/process`| POST | Trigger AI analysis on both scans | Missing | **MISSING** | Currently `/api/profile/{id}/analyze` runs psychometric questionnaire heuristics. |
| `/api/assessments/{id}/process/status`| GET| Polling analysis status | Missing | **MISSING** | No asynchronous analysis tracking. |
| `/api/assessments/{id}/results`| GET | Return structured analysis results | Missing | **MISSING** | Results scattered in `prediction_results`. |
| `/api/assessments/{id}/report/generate`| POST| Generate report after analysis | Missing | **MISSING** | Currently `/api/profile/{id}/report` generates V2 report. |
| `/api/assessments/{id}/report`| GET | Get structured report JSON | Missing | **MISSING** | Currently `GET /report` (V1) or `GET /api/profile/{id}/report` (V2). |
| `/api/assessments/{id}/report/pdf`| GET | Retrieve/stream server PDF | Missing | **MISSING** | No server-side PDF generator exists. |
| `/api/reports` | GET | Admin list/search/filter reports | Missing | **MISSING** | No global report index API. |
| `/api/reports/{id}` | GET | Get report detail | `/report?report_id={id}` | **LEGACY EQUIVALENT** | Reads static JSON from `outputs/reports/` for V1 biometric scan. |
| `/api/counsellors/students`| GET | Assigned students for counsellor | Missing | **MISSING** | No counsellor assignment module. |
| `/api/assessments/{id}/assign-counsellor`| POST| Assign counsellor to assessment | Missing | **MISSING** | No assignment endpoint. |
| `/api/counsellors/{id}/students`| GET| Assigned students by counsellor ID | Missing | **MISSING** | No counsellor query endpoint. |
| `/api/assessments/{id}/counselling-notes`| POST| Add note to assessment | Missing | **MISSING** | No counselling notes module. |
| `/api/assessments/{id}/counselling-notes`| GET| Retrieve notes if authorized | Missing | **MISSING** | No notes retrieval endpoint. |
| `/api/assessments/{id}/follow-ups`| POST| Create follow-up task | Missing | **MISSING** | No follow-up module. |
| `/api/follow-ups/{id}` | PUT | Update follow-up status/date | Missing | **MISSING** | No follow-up update endpoint. |
| `/api/assessments/{id}/reviewed`| PATCH | Mark report reviewed | Missing | **MISSING** | No review status endpoint. |
| `/api/student/me` | GET | Student own profile | Missing | **MISSING** | Handled indirectly through `/api/auth/me`. |
| `/api/student/assessment`| GET | Student own current assessment | Missing | **MISSING** | No student current assessment API. |
| `/api/student/assessment/status`| GET| Student own scan/process status | Missing | **MISSING** | No student status API. |
| `/api/student/report` | GET | Student own report | Missing | **MISSING** | Student relies on `/api/profile/{id}/report`. |
| `/api/student/report/pdf`| GET | Student own PDF | Missing | **MISSING** | No PDF generation service. |
| `/api/admin/dashboard/summary`| GET | Admin dashboard aggregate metrics | `/dashboard` | **CONFLICTING** | Returns employee count and verification counts; no student/assessment metrics. |
| `/api/users` | GET | User administration list | Missing | **MISSING** | No user management API. |
| `/api/roles` | GET | Role definitions list | Missing | **MISSING** | No roles API. |
| `/api/admin/audit-logs` | GET | Admin audit trail query | Missing | **MISSING** | No audit log query API. |

---

## 4. Database Schema Audit

### 4.1 Schema Comparison Table
Target database: SQLite (`iris_database.db`).

| Required Logical Table | Current Database Entity | Audit Status | Key Discrepancies & Missing Columns |
|---|---|---|---|
| `users` | `app_users` | **PARTIAL** | Has `id, username, password_hash, role, full_name, email, created_at, is_active`. Lacks foreign key to `roles` table, last login timestamp, and student/counsellor reference links. |
| `roles` | *None* (hardcoded strings) | **MISSING** | Roles are hardcoded strings (`Admin`, `Counselor`, `Student`). Need explicit role table for permissions governance. |
| `students` | `student_profiles` | **LEGACY EQUIVALENT** | Primary key is `id`, unique identifier is `student_id`. Missing `created_by`, `status` column (`Active`, `Inactive`, `Archived`), and direct linkage to `app_users`. Retains legacy fields: `employee_code`, `location`, `school_college`. |
| `assessments` | *None* | **MISSING** | **CRITICAL GAP.** No table exists to track assessment lifecycles. Required fields: `id, assessment_id (UNIQUE), student_id, status, created_by, created_at, completed_at, updated_at`. |
| `eye_scans` | `scan_history` (historical verify log) | **MISSING** | `scan_history` records 1-to-N employee matching comparisons. It lacks: `scan_id, assessment_id, eye_side (LEFT/RIGHT), file_reference, status, result_reference, error_code, error_message, created_at, completed_at`. |
| `analysis_results` | `prediction_results` | **PARTIAL** | `prediction_results` stores individual subscale scores for students, but lacks `assessment_id` foreign key, JSON result payloads, and execution metadata. |
| `reports` | `report_versions` | **PARTIAL** | `report_versions` tracks `report_id, student_id, version_type, payload_json, created_on`. Lacks `assessment_id`, `status`, `pdf_reference`, `reviewed_by`, `reviewed_at`. |
| `report_sections` | *None* | **MISSING** | Not strictly required if structured JSON is stored in `reports.payload_json`, but missing if normalized table is chosen. |
| `counsellor_assignments`| *None* | **MISSING** | **CRITICAL SECURITY GAP.** No table binds a student/assessment to a specific counsellor. |
| `counselling_notes` | *None* | **MISSING** | No table exists to store notes (`id, assessment_id, counsellor_id, note_text, created_at`). |
| `follow_ups` | *None* | **MISSING** | No table exists for follow-ups (`id, assessment_id, counsellor_id, title, due_date, status, created_at`). |
| `audit_logs` | `dashboard_activity` | **MISSING** | `dashboard_activity` is a simple notification feed (`title, description, created_on`). Lacks `user_id, role, assessment_id, action, ip_address, status, timestamp, correlation_id`. |
| `processing_logs` | *None* | **MISSING** | Processing logs currently print to stdout. No table exists to persist asynchronous job progress or worker errors. |

### 4.2 Relationship & Constraint Violations
1. **Student 1 $\rightarrow$ Many Assessments:** Impossible in current schema because no parent `assessments` table exists.
2. **Assessment $\rightarrow$ LEFT + RIGHT Eye Scan:** Impossible in current schema; `scan_history` has no assessment foreign key and no constraint enforcing one left and one right scan per assessment.
3. **Assessment $\rightarrow$ Analysis Result:** No foreign key link.
4. **Counsellor Isolation:** In the absence of `counsellor_assignments`, counsellors cannot be restricted to assigned students.

---

## 5. Workflow & Assessment State Machine Audit

### 5.1 Required State Machine
```
[ REGISTERED ] ──(Initiate Scan)──> [ SCAN_PENDING ]
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
       [ LEFT_SCAN_COMPLETED ]                       [ RIGHT_SCAN_COMPLETED ]
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          ▼
                                  [ SCAN_COMPLETED ]
                                          │
                                   (Start Process)
                                          ▼
                                   [ PROCESSING ]
                                          │
                                          ▼
                               [ ANALYSIS_COMPLETED ]
                                          │
                                  (Generate Report)
                                          ▼
                               [ REPORT_GENERATING ]
                                          │
                                          ▼
                                   [ REPORT_READY ]

* Any state can transition to [ FAILED ] upon unrecoverable processing or validation error.
```

### 5.2 Current Workflow Comparison
1. **Existing Enrollment Flow:**
   User enters employee details $\rightarrow$ streams 40 webcam frames to `/register-frame` $\rightarrow$ `/enroll` computes average CNN embedding $\rightarrow$ inserts into `iris_users` and `iris_embeddings`.
2. **Existing Verification Flow:**
   User opens camera $\rightarrow$ captures frame $\rightarrow$ `/detect` runs YOLO crop $\rightarrow$ `/verify` compares against all enrolled employees in `iris_users` via cosine similarity $\rightarrow$ logs to `scan_history`.
3. **Existing Student Profiling Flow:**
   Admin creates student profile in `student_profiles` $\rightarrow$ enters marks and skills $\rightarrow$ answers psychometric questions on `assessments.html` $\rightarrow$ submits to `student_assessments` $\rightarrow$ calls `/analyze` $\rightarrow$ generates Report V2.

### 5.3 Verdict on Workflow Reuse
* **Cannot reuse existing user-facing enrollment flow:** Streaming 40 frames into `iris_users` contradicts the student assessment model.
* **Can reuse internal image algorithms:** The YOLO eye detector, pupil detector, iris segmentation, normalization, and feature extractors can be packaged cleanly into the `/scan/left` and `/scan/right` handlers.

---

## 6. Iris / AI Computer Vision Pipeline Reuse

The existing computer vision and machine learning assets are fully functional and must be preserved intact:

| Pipeline Component | Source File | Capability & Output | How to Wire into New Assessment Pipeline |
|---|---|---|---|
| **YOLO Eye Detector** | `utils/yolo_detector.py` | Detects eye bounding box, crops eye region with padding | Called upon `/scan/left` or `/scan/right` upload to crop the eye from full frame. |
| **Pupil Detection** | `utils/pupil_detection.py` | Circular Hough Transform & thresholding for pupil center and radius | Measures pupil boundary for geometric validation. |
| **Iris Segmentation** | `utils/iris_segmentation.py` | Detects outer limbus boundary and isolates iris collar | Generates segmented iris image for quality analysis. |
| **Normalization** | `utils/iris_normalization.py` | Daugman rubber sheet polar unwrapping ($64 \times 512$) | Produces standardized rectangular normalized iris strip. |
| **Feature Extraction (LBP)**| `utils/lbp_extractor.py` | Local Binary Patterns texture analysis | Extracts micro-texture patterns; generates LBP visualization. |
| **Feature Extraction (Gabor)**| `utils/gabor_extractor.py` | Multi-scale, multi-orientation 2D Gabor wavelets | Filters normalized iris into phase/frequency representation. |
| **Feature Extraction (GLCM)**| `utils/glcm_extractor.py` | Gray-Level Co-occurrence Matrix (contrast, energy, homogeneity) | Computes structural statistical features. |
| **CNN Embedding** | `utils/cnn_extractor.py` | Deep feature embedding via `models/iris_cnn.h5` | Produces 256-D normalized vector representation. |
| **Image Quality Analyzer**| `utils/iris_quality_analyzer.py` | Sharpness, blur, contrast, usable iris area, occlusion ratio | Automatically validates scan quality before confirming scan. |
| **Color Analysis** | `utils/color_analysis.py` | HSV color space clustering for iris pigmentation | Determines eye pigmentation metrics. |
| **Similarity Matcher** | `utils/similarity.py` | Cosine similarity between embeddings | Reused if cross-session verification or left/right consistency check is required. |

---

## 7. Report Requirements & PDF Audit

### 7.1 Data Contract Discrepancy
The required official report contract expects a structured JSON envelope:
```json
{
  "student": { "id": "STU-001", "name": "Aryan Sharma", ... },
  "assessment": { "assessment_id": "ASM-20260929-001", "date": "2026-09-29", "status": "REPORT_READY" },
  "eye_scan": {
    "left": { "status": "Completed", "quality_score": 88.5, "eye_color": "Brown", ... },
    "right": { "status": "Completed", "quality_score": 91.2, "eye_color": "Brown", ... }
  },
  "overall_result": { "combined_index": 82.4, "summary": "..." },
  "behaviour": { "categories": [...], "scores": [...], "descriptions": [...] },
  "personality": { "traits": [...], "scores": [...], "descriptions": [...] },
  "subjects_interest": { "preferences": [...], "categories": [...] },
  "recommendations": [...],
  "counselling": {
    "assigned_counsellor": "counselor1",
    "reviewed_status": true,
    "notes": [...],
    "follow_ups": [...]
  },
  "report_meta": { "report_id": "REP-20260929-001", "version": "1.0", "generated_date": "...", "pdf_reference": "..." }
}
```
* **Current Report V2 Payload (`services/report_v2_generator.py`):**
  Contains 32 sections heavily focused on psychometrics and school grades. It completely omits the dual eye scan details (`eye_scan.left` and `eye_scan.right`) and counselling notes/status (`counselling`).
* **PDF Generation Status:**
  Currently **MISSING** on backend. Frontend uses `html2pdf.js` in the browser, which creates formatting defects and cannot be downloaded programmatically by APIs. A server-side PDF generator (using ReportLab or WeasyPrint) is mandatory.

---

## 8. Security & Authorization Audit

### 8.1 Critical Vulnerabilities & Policy Conflicts
1. **Counselor Isolation Failure (CRITICAL CONFLICT):**
   In `security/auth.py` (lines 385–387):
   ```python
   role = current_user.get("role")
   if role in ("Admin", "Counselor"):
       return True
   ```
   This gives all counselors unrestricted institutional access to every student record in the database.
   * **Official Requirement:** *"Counsellor may access ONLY assigned/authorized students. No unrelated students unless explicitly permitted."*
2. **Student Scanning Access Blocked (CRITICAL CONFLICT):**
   In `static/camera.js` (lines 8–12), students are actively prohibited from loading the camera scanning interface. Under the new workflow, students must be allowed to perform left and right eye scans for their own assessment.
3. **Lack of Server-Side Session Revocation:**
   JWT tokens are stateless and expire after 60 minutes, but `/api/auth/logout` is missing, preventing immediate token invalidation on sign-out.
4. **Rate Limiting:**
   No rate limiter is mounted on `/api/auth/login` or scan upload endpoints, exposing the system to credential stuffing and denial of service.

---

## 9. Logging & Telemetry Audit

* **Current Implementation:** Pure `print()` statements and a legacy `dashboard_activity` table recording employee attendance events.
* **Required Audit Specification:** Every critical lifecycle event must be logged to an `audit_logs` table and structured log file:
  - Registration
  - Login outcome (success/failure, no passwords)
  - Scan submission (left/right)
  - Scan completion / failure
  - Analysis start and completion
  - Report generation
  - Counsellor assignment
  - Report review
  - Admin configuration changes
* **Required Log Schema:** `user_id`, `role`, `assessment_id`, `timestamp`, `action`, `status`, `ip_address`, `correlation_id`.

---

## 10. Protection of Existing Work

The following existing assets must be strictly preserved without regression during future implementation:
1. **Existing Tables:** `iris_users`, `iris_embeddings`, `scan_history`, `student_profiles`, `student_assessments`, `report_versions`.
2. **Existing Machine Learning Models & Weights:** `models/iris_cnn.h5`, `yolo11n.pt`, and all OpenCV/NumPy utility algorithms.
3. **Existing Security Hardening:** Password hashing (PBKDF2-100k), JWT verification, upload validation (magic bytes), media path validation, and security headers.
4. **Existing Profiling Intelligence:** Big Five personality scoring, cognitive domain calculators, subject gap analysis, and career catalog recommendation engines.

---
*End of Gap Analysis Document.*

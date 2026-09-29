# IRIS Project: Phase 1 Database Foundation Report

**Phase:** Phase 1 — Official IRIS Data Model & Student/Assessment Foundation  
**Specification References:**
- `IRIS_Backend_Detailed_Requirements.docx`
- `IRIS_Frontend_Detailed_Requirements.docx`  
**Execution Date:** September 2026  
**Status:** **PASS (100% Verified)**

---

## 1. Executive Summary

Phase 1 establishes the relational database backbone required by the official IRIS product specifications. All 12 required logical entities, primary/foreign keys, check constraints, and performance indexes have been provisioned in `iris_database.db` via safe, non-destructive SQL DDL in [database_official.py](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/database_official.py).

All historical biometric identities, embeddings, scan comparisons, student profiles, psychometric responses, and report versions remain 100% intact, with zero rows lost or altered.

---

## 2. Pre-Migration Baseline & Backup Integrity

Before executing any DDL or migration scripts, two full backups of `iris_database.db` were created and verified:
1. **Primary Workspace Backup:**  
   `/Users/dasarisaiteja/Desktop/syne it systems/iris peoject/iris-ai-code/iris_database.db.backup_pre_phase1_20260929` (Size: 17.5 MB)
2. **Scratch Backup Archive:**  
   `/Users/dasarisaiteja/Desktop/syne it systems/iris peoject/iris-ai-code/scratch/backups/iris_database_pre_phase1.db` (Size: 17.5 MB)

Detailed pre-migration audit logs are documented in:
[scratch/pre_phase1_database_snapshot.md](file:///Users/dasarisaiteja/Desktop/syne%20it%20systems/iris%20peoject/iris-ai-code/scratch/pre_phase1_database_snapshot.md).

---

## 3. Data Integrity & Non-Regression: Counts Before vs. After

| Table Name | Count Before Phase 1 | Count After Phase 1 | Net Change | Data Integrity Status |
|---|---|---|---|---|
| `academic_records` | **10** | **10** | 0 | **Preserved (100%)** |
| `activity_catalog` | **15** | **15** | 0 | **Preserved (100%)** |
| `app_users` | **3** | **3** | 0 | **Preserved (100%)** |
| `assessment_questions` | **21** | **21** | 0 | **Preserved (100%)** |
| `career_catalog` | **7** | **7** | 0 | **Preserved (100%)** |
| `dashboard_activity` | **57** | **57** | 0 | **Preserved (100%)** |
| `iris_embeddings` | **536** | **536** | 0 | **Preserved (100%)** |
| `iris_users` | **18** | **18** | 0 | **Preserved (100%)** |
| `prediction_results` | **293** | **293** | 0 | **Preserved (100%)** |
| `report_versions` | **199** | **199** | 0 | **Preserved (100%)** |
| `scan_history` | **57** | **57** | 0 | **Preserved (100%)** |
| `student_activities` | **2** | **2** | 0 | **Preserved (100%)** |
| `student_assessments` | **77** | **77** | 0 | **Preserved (100%)** |
| `student_interests` | **4** | **4** | 0 | **Preserved (100%)** |
| `student_profiles` | **4** | **4** | 0 | **Preserved (100%)** |
| `student_skills` | **5** | **5** | 0 | **Preserved (100%)** |
| **`roles` (New)** | *0* | **3** | +3 | **Provisioned & Seeded** |
| **`students` (New)** | *0* | **4** | +4 | **Provisioned & Synced** |
| **`assessments` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`eye_scans` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`analysis_results` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`reports` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`report_sections` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`counsellor_assignments` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`counselling_notes` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`follow_ups` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`audit_logs` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |
| **`processing_logs` (New)** | *0* | **0** | 0 | **Provisioned (Ready)** |

---

## 4. Tables Created & Relational Architecture

### 4.1 `roles`
* **Purpose:** Explicit, normalized role governance.
* **Columns:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `role_name TEXT UNIQUE NOT NULL`, `description TEXT`, `created_at TEXT NOT NULL`.
* **Seeded Roles:**
  1. `Admin` — System Administrator with full management access
  2. `Student` — Student with self-service assessment, scan, and report access
  3. `Counsellor` — Counsellor with assigned student guidance and report review access

### 4.2 `students`
* **Purpose:** Official student master record decoupled from legacy employee/customer models.
* **Columns:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `student_id TEXT UNIQUE NOT NULL`, `student_name TEXT NOT NULL`, `created_by TEXT DEFAULT 'system'`, `created_at TEXT NOT NULL`, `updated_at TEXT`, `status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED'))`.
* **Sync & Migration:** Existing records in `student_profiles` were automatically and non-destructively synced into `students`. Existing legacy columns in `student_profiles` were preserved.

### 4.3 `assessments`
* **Purpose:** Core assessment lifecycle and workflow state machine entity.
* **Columns:**
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `assessment_id TEXT UNIQUE NOT NULL`
  - `student_id TEXT NOT NULL`
  - `status TEXT NOT NULL`
  - `created_by TEXT DEFAULT 'system'`
  - `created_at TEXT NOT NULL`
  - `updated_at TEXT`
  - `completed_at TEXT`
* **State Machine CHECK Constraint:**
  Enforces exactly the 10 official workflow states:
  `CHECK(status IN ('REGISTERED', 'SCAN_PENDING', 'LEFT_SCAN_COMPLETED', 'RIGHT_SCAN_COMPLETED', 'SCAN_COMPLETED', 'PROCESSING', 'ANALYSIS_COMPLETED', 'REPORT_GENERATING', 'REPORT_READY', 'FAILED'))`.
* **Foreign Key:** `FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE RESTRICT`.

### 4.4 `eye_scans`
* **Purpose:** Mandatory separate captures for Left and Right eye side bound to the same assessment.
* **Columns:**
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `scan_id TEXT UNIQUE NOT NULL`
  - `assessment_id TEXT NOT NULL`
  - `eye_side TEXT NOT NULL CHECK(eye_side IN ('LEFT', 'RIGHT'))`
  - `file_reference TEXT NOT NULL` (secure token/URI, non-public path)
  - `status TEXT NOT NULL CHECK(status IN ('Pending', 'Processing', 'Completed', 'Failed'))`
  - `result_reference TEXT`
  - `error_code TEXT`
  - `error_message TEXT`
  - `attempt_number INTEGER DEFAULT 1`
  - `is_active INTEGER DEFAULT 1`
  - `created_at TEXT NOT NULL`
  - `completed_at TEXT`
* **Foreign Key:** `FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT`.
* **Concurrency / Duplicate Guard:**
  Partial unique index:
  `CREATE UNIQUE INDEX idx_eye_scans_unique_active_assessment_eye ON eye_scans(assessment_id, eye_side) WHERE is_active = 1;`  
  Guarantees that an assessment cannot have two active scans for the same eye side while cleanly permitting retries (`is_active = 0`).

### 4.5 `analysis_results`
* **Purpose:** Structured storage of combined AI analysis results.
* **Columns:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `assessment_id TEXT UNIQUE NOT NULL`, `results_json TEXT NOT NULL`, `model_version TEXT DEFAULT 'v1.0'`, `created_at TEXT NOT NULL`, `updated_at TEXT`.
* **Foreign Key:** `FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT`.

### 4.6 `reports` & `report_sections`
* **Purpose:** Versioned structured reports with review tracking and server PDF references.
* **`reports` Columns:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `report_id TEXT UNIQUE NOT NULL`, `assessment_id TEXT NOT NULL`, `version TEXT NOT NULL DEFAULT 'v1.0'`, `status TEXT NOT NULL CHECK(status IN ('REPORT_GENERATING', 'REPORT_READY', 'FAILED'))`, `generated_at TEXT`, `pdf_reference TEXT`, `reviewed_status INTEGER DEFAULT 0`, `reviewed_by TEXT`, `reviewed_at TEXT`, `created_at TEXT NOT NULL`, `updated_at TEXT`.
* **Duplicate Protection:** `UNIQUE(assessment_id, version)` prevents accidental duplicate generation.
* **`report_sections` Columns:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `report_id TEXT NOT NULL`, `section_key TEXT NOT NULL`, `title TEXT`, `content_json TEXT NOT NULL`, `order_num INTEGER DEFAULT 0`, `created_at TEXT NOT NULL`, `UNIQUE(report_id, section_key)`.

### 4.7 Counsellor Governance Tables
* **`counsellor_assignments`:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `assignment_id TEXT UNIQUE NOT NULL`, `assessment_id TEXT NOT NULL`, `student_id TEXT NOT NULL`, `counsellor_id TEXT NOT NULL`, `assigned_by TEXT NOT NULL`, `assigned_at TEXT NOT NULL`, `status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'COMPLETED', 'REVOKED'))`, `is_active INTEGER DEFAULT 1`.
* **`counselling_notes`:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `note_id TEXT UNIQUE NOT NULL`, `assessment_id TEXT NOT NULL`, `counsellor_id TEXT NOT NULL`, `note TEXT NOT NULL`, `created_at TEXT NOT NULL`, `updated_at TEXT`.
* **`follow_ups`:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `follow_up_id TEXT UNIQUE NOT NULL`, `assessment_id TEXT NOT NULL`, `counsellor_id TEXT NOT NULL`, `follow_up_date TEXT NOT NULL`, `status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Completed', 'Cancelled', 'Overdue'))`, `notes TEXT`, `created_at TEXT NOT NULL`, `updated_at TEXT`.

### 4.8 Telemetry & Audit Tables
* **`audit_logs`:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `audit_id TEXT UNIQUE NOT NULL`, `user_id TEXT`, `role TEXT`, `action TEXT NOT NULL`, `assessment_id TEXT`, `entity_type TEXT`, `entity_id TEXT`, `correlation_id TEXT`, `ip_address TEXT`, `status TEXT NOT NULL DEFAULT 'SUCCESS'`, `safe_metadata_json TEXT`, `timestamp TEXT NOT NULL`.
  * *Security Guarantee:* Passwords, bearer tokens, and raw biometric pixel arrays are strictly prohibited from log storage.
* **`processing_logs`:** `id INTEGER PRIMARY KEY AUTOINCREMENT`, `processing_id TEXT UNIQUE NOT NULL`, `assessment_id TEXT NOT NULL`, `operation TEXT NOT NULL`, `status TEXT NOT NULL`, `safe_error_code TEXT`, `safe_error_message TEXT`, `started_at TEXT NOT NULL`, `completed_at TEXT`, `duration_ms INTEGER`, `model_version TEXT`.

---

## 5. Indexes Provisioned

The following 12 mandatory performance indexes have been created:
1. `idx_students_student_id` on `students(student_id)`
2. `idx_assessments_assessment_id` on `assessments(assessment_id)`
3. `idx_assessments_student_id` on `assessments(student_id)`
4. `idx_assessments_status` on `assessments(status)`
5. `idx_eye_scans_assessment_id` on `eye_scans(assessment_id)`
6. `idx_eye_scans_eye_side` on `eye_scans(eye_side)`
7. `idx_reports_assessment_id` on `reports(assessment_id)`
8. `idx_counsellor_assignments_counsellor_id` on `counsellor_assignments(counsellor_id)`
9. `idx_counsellor_assignments_assessment_id` on `counsellor_assignments(assessment_id)`
10. `idx_audit_logs_user_id` on `audit_logs(user_id)`
11. `idx_audit_logs_assessment_id` on `audit_logs(assessment_id)`
12. `idx_processing_logs_assessment_id` on `processing_logs(assessment_id)`

---

## 6. Verification & Test Results

### 6.1 Phase 1 Verification Test Suite (`scratch/test_phase1_database_foundation.py`)
Execution Command: `./ai-env/bin/python scratch/test_phase1_database_foundation.py`

| # | Verification Assertion | Result |
|---|---|---|
| 1 | Database backup exists at both primary and scratch locations | **PASS** |
| 2 | All 12 official required tables exist in SQLite catalog | **PASS** |
| 3 | Required columns verified across all official tables | **PASS** |
| 4 | Official roles (`Admin`, `Student`, `Counsellor`) validated | **PASS** |
| 5 | Student ID uniqueness constraint enforced | **PASS** |
| 6 | Assessment ID uniqueness constraint enforced | **PASS** |
| 7 | Student 1 $\rightarrow$ Many Assessments relationship verified | **PASS** |
| 8 | Eye Scans $\rightarrow$ Assessment relationship verified | **PASS** |
| 9 | Duplicate active scan prevention on `(assessment_id, eye_side)` verified | **PASS** |
| 10 | Report $\rightarrow$ Assessment relationship and duplicate prevention verified | **PASS** |
| 11 | Counsellor assignment relationship verified | **PASS** |
| 12 | Foreign key integrity actively enforced (`PRAGMA foreign_keys = ON`) | **PASS** |
| 13 | All 12 required performance indexes verified | **PASS** |
| 14 | Invalid assessment state rejected by CHECK constraint | **PASS** |
| 15 | Invalid eye side rejected by CHECK constraint | **PASS** |
| 16 | Historical records across all 13 baseline tables preserved with zero data loss | **PASS** |
| 17 | Existing Iris biometric templates and user records completely intact | **PASS** |

**Summary: 17 / 17 Tests Passed (100% Success)**

---

## 7. Files Modified & Intentionally Untouched

### 7.1 Files Created or Modified
* **Created:** `database_official.py` (Official schema definition and initialization module)
* **Created:** `scratch/pre_phase1_database_snapshot.md` (Pre-migration baseline audit)
* **Created:** `scratch/test_phase1_database_foundation.py` (Automated 17-point verification suite)
* **Created:** `scratch/phase1_database_foundation_report.md` (This document)
* **Modified:** `main.py` (Imported and mounted `init_official_tables()` on startup)

### 7.2 Files Intentionally Untouched
* **Machine Learning & CV Pipeline:**
  `utils/yolo_detector.py`, `utils/pupil_detection.py`, `utils/iris_segmentation.py`, `utils/iris_normalization.py`, `utils/lbp_extractor.py`, `utils/gabor_extractor.py`, `utils/glcm_extractor.py`, `utils/cnn_extractor.py`, `utils/similarity.py`, `models/iris_cnn.h5`, `yolo11n.pt` — **100% UNTOUCHED**.
* **Frontend Templates & Scripts:**
  `static/register.html`, `static/register.js`, `static/camera.html`, `static/camera.js`, `static/login.html`, `static/dashboard.html`, `static/student_report.html` — **100% UNTOUCHED**.
* **Existing Profiling Logic:**
  `services/cognitive_engine.py`, `services/gap_analysis.py`, `services/career_engine.py`, `services/activity_sports.py`, `services/subject_analysis.py`, `services/report_v2_generator.py` — **100% UNTOUCHED**.

---
*End of Phase 1 Report. Ready for Phase 2 upon user instruction.*

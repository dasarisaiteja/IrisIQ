# IRIS Database Snapshot (Pre-Phase 1)

**Timestamp:** 2026-09-29 11:20:00 UTC  
**Database File:** `/Users/dasarisaiteja/Desktop/syne it systems/iris peoject/iris-ai-code/iris_database.db`  
**Database Technology:** SQLite 3  
**Backup Locations:**
1. `/Users/dasarisaiteja/Desktop/syne it systems/iris peoject/iris-ai-code/iris_database.db.backup_pre_phase1_20260929`
2. `/Users/dasarisaiteja/Desktop/syne it systems/iris peoject/iris-ai-code/scratch/backups/iris_database_pre_phase1.db`

---

## 1. Existing Tables & Row Counts

| # | Table Name | Existing Row Count | Main Responsibility |
|---|---|---|---|
| 1 | `academic_records` | **10** | Student academic subject scores and terms |
| 2 | `activity_catalog` | **15** | Curated catalog of co-curricular activities and sports |
| 3 | `app_users` | **3** | Authentication identities (`admin`, `counselor1`, `student1`) |
| 4 | `assessment_questions` | **21** | Validated psychometric assessment questionnaire items |
| 5 | `career_catalog` | **7** | Curated career profiles and qualification requirements |
| 6 | `dashboard_activity` | **57** | System activity notification entries |
| 7 | `iris_embeddings` | **536** | 256-D CNN normalized feature vectors for iris templates |
| 8 | `iris_users` | **18** | Enrolled biometric identity records (employees / legacy) |
| 9 | `prediction_results` | **293** | Historical intelligence and scoring indicators |
| 10 | `report_versions` | **199** | Stored V1 and V2 JSON report records |
| 11 | `scan_history` | **57** | Historical biometric verification match records |
| 12 | `student_activities` | **2** | Co-curricular student involvement records |
| 13 | `student_assessments` | **77** | Domain-specific questionnaire responses |
| 14 | `student_interests` | **4** | Vocational interest records |
| 15 | `student_profiles` | **4** | Student demographic profiles (`STU-001`, `STU-002`, etc.) |
| 16 | `student_skills` | **5** | Technical and soft skill records |

**Total Existing Tables:** 16  
**Total Existing Records:** 1,308

---

## 2. Existing Schema DDL & Relationships

### 2.1 Biometric & Verification Tables
* **`iris_users`**:
  Columns: `id, employee_code UNIQUE, user_name, department, designation, gender, age, dob, blood_group, mobile, email, address, photo_path, iris_code, embedding_count, created_on`.
* **`iris_embeddings`**:
  Columns: `id, employee_code, embedding, image_path, created_on`.
  Relationship: Linked by `employee_code` to `iris_users`.
* **`scan_history`**:
  Columns: `id, report_id, user_name, similarity, confidence, status, scan_date, scan_time, eye, image_path`.

### 2.2 Student Profiling Tables
* **`student_profiles`**:
  Columns: `id, student_id UNIQUE, employee_code, full_name, age, gender, email, mobile, school_college, course, year, stream, location, photo_path, created_on, updated_on`.
* **`academic_records`, `student_skills`, `student_interests`, `student_activities`, `student_assessments`, `prediction_results`, `report_versions`**:
  All linked to `student_profiles` via `student_id`.

### 2.3 Authentication Table
* **`app_users`**:
  Columns: `id, username UNIQUE, password_hash, role, full_name, email, created_at, is_active`.
  Users: `admin` (Role: Admin), `counselor1` (Role: Counselor), `student1` (Role: Student).

---

## 3. Existing Indexes (Auto-indexes)
* `sqlite_autoindex_activity_catalog_1` (activity_name)
* `sqlite_autoindex_app_users_1` (username)
* `sqlite_autoindex_career_catalog_1` (career_name)
* `sqlite_autoindex_iris_users_1` (employee_code)
* `sqlite_autoindex_report_versions_1` (report_id)
* `sqlite_autoindex_student_profiles_1` (student_id)

---

## 4. Phase 1 Migration Plan (Non-Destructive Relational Provisioning)

1. **Safety Constraints:**
   - No `DROP TABLE`, `ALTER TABLE ... DROP COLUMN`, or destructive migrations.
   - All existing 16 tables remain untouched.
   - Row counts for all 16 existing tables must be identical or greater after Phase 1.
2. **Entities to Create / Extend:**
   - `roles`: Explicit role dictionary (`Admin`, `Student`, `Counsellor`) with normalized identifiers.
   - `students`: Safely ensure `student_profiles` satisfies the minimum official requirements (`student_id`, `student_name` / `full_name`, `created_by`, `created_at`).
   - `assessments`: Workflow state machine table tracking `assessment_id`, `student_id`, and the 10 official workflow states with `CHECK(status IN (...))`.
   - `eye_scans`: Separate scan records tracking `scan_id`, `assessment_id`, `eye_side` (`CHECK(eye_side IN ('LEFT', 'RIGHT'))`), secure file references, and status.
   - `analysis_results`: Structured results linked to `assessment_id`.
   - `reports`: Official reports linked to `assessment_id` with `version` and review status.
   - `report_sections`: Normalized report section storage.
   - `counsellor_assignments`: Explicit assignment link between `assessment_id`, `student_id`, and `counsellor_id`.
   - `counselling_notes`: Notes recorded by counsellors on assessments.
   - `follow_ups`: Scheduled student follow-ups linked to assessments.
   - `audit_logs`: Security and lifecycle event tracking (without passwords/biometric secrets).
   - `processing_logs`: Asynchronous worker step and error telemetry.
3. **Execution Mechanism:**
   - Implement in a dedicated module `database_official.py` and invoke from `main.py` and `database.py`.
   - Idempotent execution (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).

---
*Snapshot created and verified before any schema alterations.*

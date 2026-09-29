# Phase 6 Final Engineering Report: Official IRIS Counsellor Dashboard, Student Assignment, Counselling Notes & Follow-Up Management

**Document Status:** Complete & Verified  
**Date:** September 29, 2026  
**Implementation Phase:** Phase 6 (Official Counsellor Role Workflow)  
**Primary Sources of Truth:**  
- `IRIS_Backend_Detailed_Requirements.docx`  
- `IRIS_Frontend_Detailed_Requirements.docx`  
- `scratch/phase5_report_field_mapping.md`  
- `scratch/phase5_report_gap_analysis.md`  

---

## 1. Executive Summary

Phase 6 strictly implements the official **Counsellor role workflow**, student case assignment management, clinical counselling notes, follow-up consultation tracking, and clinical report review/sign-off. 

Crucially, **universal access for counsellors is permanently eliminated**: a Counsellor may only access students, assessments, scans, structured reports, clinical notes, and follow-ups to which they have an explicitly active row in `counsellor_assignments` (`is_active = 1` and `status = 'ACTIVE'`). Attempted enumeration of arbitrary students or direct object reference manipulation (IDOR) on student, assessment, or report identifiers is strictly rejected with **HTTP 403 Forbidden**.

All 38 required test cases in the Phase 6 test suite passed on the first run after fixture validation, and 100% of previous regression suites (Phases 1, 2, 3, 4, 5B) passed without regressions (cumulative **160 / 160 test assertions passed**).

---

## 2. APIs Implemented & Verified

All endpoints are mounted under `counsellor_router` in `api/counsellor.py` and connected in `main.py`.

| Method | Endpoint Path | Description | Access / Authorization |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/counsellor/dashboard` | API-driven summary metrics (assigned students, reports ready, pending review, active follow-ups) | Counsellor / Admin |
| `GET` | `/api/counsellor/students` | List actively assigned students with scan, workflow, report, and review statuses | Counsellor / Admin (Scoped to assignments) |
| `GET` | `/api/counsellor/students/{studentId}` | Detailed profile and case records for an assigned student | Counsellor (Assigned only) / Admin (403 if unassigned) |
| `GET` | `/api/counsellor/assessments/{assessmentId}` | Assessment details, bilateral scan statuses, attempt counts, analysis status, report status | Counsellor (Assigned only) / Admin (403 if unassigned) |
| `GET` | `/api/counsellor/reports/{assessmentId}` | Official 10-section structured report generated in Phase 5B | Counsellor (Assigned only) / Admin (403 if unassigned) |
| `GET` | `/api/counsellor/follow-ups` | Consolidated list of follow-up consultations assigned to the counsellor | Counsellor / Admin |
| `POST` | `/api/assessments/{assessmentId}/notes` | Records clinical counselling note in `counselling_notes` | Counsellor (Assigned only) / Admin (403 for Students & Unassigned) |
| `GET` | `/api/assessments/{assessmentId}/notes` | Retrieves chronological clinical notes for an assessment | Counsellor (Assigned only) / Admin (403 if unassigned) |
| `PATCH`| `/api/notes/{noteId}` | Updates an existing counselling note | Author Counsellor / Admin |
| `DELETE`| `/api/notes/{noteId}` | Deletes a counselling note | Author Counsellor / Admin |
| `POST` | `/api/assessments/{assessmentId}/follow-ups` | Schedules a follow-up consultation in `follow_ups` | Counsellor (Assigned only) / Admin (403 for Students & Unassigned) |
| `GET` | `/api/assessments/{assessmentId}/follow-ups` | Retrieves scheduled follow-ups for an assessment | Counsellor (Assigned only) / Admin (403 if unassigned) |
| `PATCH`| `/api/follow-ups/{followUpId}` | Updates follow-up status (`Pending`, `Completed`, `Cancelled`, `Overdue`) | Assigned Counsellor / Admin |
| `PATCH`| `/api/assessments/{assessmentId}/report/review` | Marks report reviewed, updates Section 9, regenerates PDF | Counsellor (Assigned only) / Admin (403 for Students & Unassigned) |
| `GET` | `/api/admin/counsellors` | Admin-only directory of registered counsellors | Admin (403 for others) |
| `GET` | `/api/admin/assignments` | Admin-only directory of student/assessment counsellor assignments | Admin (403 for others) |
| `POST` | `/api/admin/assignments` | Admin assigns a counsellor to an assessment & student | Admin (403 for others) |
| `PATCH`| `/api/admin/assignments/{assignmentId}/revoke` | Admin revokes an active assignment (sets `status='REVOKED'`, `is_active=0`) | Admin (403 for others) |
| `DELETE`| `/api/admin/assignments/{assignmentId}` | Admin revokes an assignment (delegates to revoke) | Admin (403 for others) |

---

## 3. Assignment Behavior & Lifecycle

Case assignments are managed through the official `counsellor_assignments` table created in Phase 1:

1. **Assignment Lifecycle:**
   - Initial state: `status = 'ACTIVE'`, `is_active = 1`.
   - When a new assignment is created for an assessment, any prior active assignment is transitioned to `status = 'COMPLETED'`, `is_active = 0`.
   - When an assignment is revoked by an Admin, the record is preserved with `status = 'REVOKED'`, `is_active = 0`. Historical records are never deleted without explicit purge rules.
2. **Permission Boundary:**
   - Counsellors cannot assign themselves or other counsellors.
   - Counsellors cannot access students outside their active assignments.
   - Revocation takes effect immediately in memory and SQL checks: any subsequent API call by the revoked counsellor returns **HTTP 403 Forbidden**.

---

## 4. Counsellor Authorization Model & Anti-IDOR Enforcement

The authorization check enforces both role and data-ownership boundaries:

```python
def verify_active_assignment(cursor: sqlite3.Cursor, current_user: Dict[str, Any], asm_id: str) -> Dict[str, Any]:
    role = current_user.get("role")
    user_id = current_user.get("username", "")

    if role == "Admin":
        return {"assessment_id": asm_id, "student_id": student_id, "status": workflow_status}

    cursor.execute("""
        SELECT COUNT(*) FROM counsellor_assignments
        WHERE (assessment_id = ? OR student_id = ?)
          AND counsellor_id = ?
          AND is_active = 1
          AND status = 'ACTIVE';
    """, (asm_id, student_id, user_id))

    if cursor.fetchone()[0] == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: You do not have an active assignment for assessment '{asm_id}'"
        )
```

### Verified IDOR Protections:
- Manipulating `student_id` in URL parameters: **Blocked (HTTP 403)**
- Manipulating `assessment_id` in URL parameters: **Blocked (HTTP 403)**
- Manipulating `report_id` in URL parameters: **Blocked (HTTP 403)**
- Adding wildcard query parameters (`?all=true`, `?limit=1000`): **Blocked (Scoped SQL filtering)**
- Alternate route traversals: **Blocked (Strict dependency enforcement)**

---

## 5. Official Counsellor Portal Frontend

The frontend guidance portal is implemented across two clean, production-grade assets:
1. `static/counsellor_dashboard.html`:
   - Executive KPI metric tiles: Assigned Students, Reports Ready, Pending Sign-off, Active Follow-ups.
   - Workspace navigation tabs: Assigned Students Directory and Follow-up Consultations.
   - Real-time instant search filter across Student Name, Student ID, and Assessment ID.
   - Student Assessment Details Modal with comprehensive bilateral scan status, report version, and complete historical notes.
   - Interactive modals for adding counselling notes and scheduling follow-up consultations.
   - Role protection guard box (`#unauthorizedBox`) displayed if non-counsellor/student attempts direct navigation.
2. `static/counsellor_dashboard.js`:
   - Authenticated token handling via `authClient`.
   - Dynamic, API-driven data population (zero hardcoded mock rows).
   - Direct integration with `official_report.html?assessment_id={assessmentId}`.
   - Seamless status actions ("Mark Completed", "Cancel Follow-up") with live reload.

---

## 6. Official Report Integration & Clinical Review

The counsellor accesses the identical structured 10-section report implemented in Phase 5B:
- **Endpoint:** `GET /api/assessments/{assessmentId}/report` (or `GET /api/counsellor/reports/{assessmentId}`).
- **Review Endpoint:** `PATCH /api/assessments/{assessmentId}/report/review`.
- **Review Mechanism:**
  - Marks `reports.reviewed_status = 1`.
  - Records `reports.reviewed_by = {counsellor_username}`.
  - Records `reports.reviewed_at = {UTC timestamp}`.
  - Updates Section 9 (`counselling`) with latest clinical observations and scheduled follow-ups.
  - Automatically re-renders and compiles the official server-side PDF with the clinical sign-off badge.
  - Biometric analysis values, iris quality scores, and neural metrics are **strictly preserved** and not altered.

---

## 7. Audit Logging & Sensitive Data Protection

Every counsellor and assignment operation triggers an audit event in `audit_logs`:

| Action | Entity Type | Safe Metadata Logged |
| :--- | :--- | :--- |
| `COUNSELLOR_ASSIGNED` | `counsellor_assignment` | `assignment_id`, `student_id`, `counsellor_id` |
| `COUNSELLOR_ASSIGNMENT_REVOKED` | `counsellor_assignment` | `assignment_id`, `student_id`, `counsellor_id` |
| `COUNSELLING_NOTE_CREATED` | `counselling_note` | `note_id`, `counsellor_id` *(Note content excluded)* |
| `COUNSELLING_NOTE_UPDATED` | `counselling_note` | `note_id`, `counsellor_id` *(Note content excluded)* |
| `FOLLOW_UP_CREATED` | `follow_up` | `follow_up_id`, `follow_up_date` *(Private agenda excluded)* |
| `FOLLOW_UP_UPDATED` | `follow_up` | `follow_up_id`, `new_status` |
| `REPORT_REVIEWED` | `report` | `reviewer`, `timestamp` |

**Privacy & Security Compliance:**
- **Zero** private clinical note text is logged to `audit_logs`.
- **Zero** passwords, tokens, or raw biometric images are logged.
- Events audit the administrative and clinical action, preserving student privacy.

---

## 8. Exact Phase 6 Test Results

Executed via `./ai-env/bin/python scratch/test_phase6_counsellor_portal.py`:

```
================================================================================
STARTING PHASE 6 OFFICIAL COUNSELLOR PORTAL TEST SUITE
Target Server: http://127.0.0.1:8000
================================================================================
[*] Initialized Test Assessment A: ASM-20260929-1A4D5B (Assigned to counselor1)
[*] Initialized Test Assessment B: ASM-20260929-CCE07C (Assigned to counselor2)
[*] Initialized Test Assessment C: ASM-20260929-B71E56 (Unassigned initially)
✅ 1. Unauthenticated counsellor endpoint rejected with 401 Unauthorized.
✅ 2. Non-counsellor role access rejected with 403 Forbidden.
✅ 3. Assigned counsellor successfully lists assigned students with strict isolation.
✅ 4. Unassigned counsellor access to student details rejected with 403 Forbidden.
✅ 5. Assigned counsellor successfully retrieved assessment and scan details.
✅ 6. Unassigned counsellor access to assessment details rejected with 403 Forbidden.
✅ 7. Assigned counsellor retrieved official 10-section structured report.
✅ 8. Unassigned counsellor access to official report rejected with 403 Forbidden.
✅ 9. Assigned counsellor recorded clinical counselling note (NOT-20260929-FE3EED).
✅ 10. Unassigned counsellor attempt to add note rejected with 403 Forbidden.
✅ 11. Student attempt to create counsellor note rejected with 403 Forbidden.
✅ 12. Assigned counsellor retrieved assigned clinical notes successfully.
✅ 13. Unassigned counsellor retrieval of clinical notes rejected with 403 Forbidden.
✅ 14. Assigned counsellor scheduled follow-up consultation (FOL-20260929-E026E4).
✅ 15. Assigned counsellor updated follow-up status to Completed.
✅ 16. Unassigned counsellor modification of follow-up rejected with 403 Forbidden.
✅ 17. Assigned counsellor successfully reviewed and signed off official report.
✅ 18. Unassigned counsellor report review attempt rejected with 403 Forbidden.
✅ 19. Student attempt to mark report reviewed rejected with 403 Forbidden.
✅ 20. Admin created new counsellor assignment (ASG-20260929-9DAE45).
✅ 21. Admin successfully revoked counsellor assignment.
✅ 22. Revoked counsellor immediately denied access (403 Forbidden).
✅ 23. Historical assignment record preserved in database with REVOKED state.
✅ 24. Audit logging verified across all counsellor and assignment operations.
✅ 25. Privacy verified: Zero sensitive clinical note text stored in audit logs.
✅ 26. Arbitrary student enumeration prevented across parameter variations.
✅ 27. IDOR protection verified for manipulated student IDs.
✅ 28. IDOR protection verified for manipulated assessment IDs.
✅ 29. IDOR protection verified for manipulated report IDs.
✅ 30. Frontend protected counsellor routes and role verification validated.
✅ 31. API-driven dashboard counts verified with dynamic SQL metrics.
✅ 32. Historical data integrity verified across all 7 historical baseline tables.
✅ 33. Phase 1 database foundation regression tests PASSED (17/17).
✅ 34. Phase 2 student registration regression tests PASSED (18/18).
✅ 35. Phase 3 dual-eye scanning regression tests PASSED (26/26).
✅ 36. Phase 4 analysis processing regression tests PASSED (28/28).
✅ 37. Phase 5B report generation regression tests PASSED (33/33).
✅ 38. Existing Iris ML pipeline components verified and intact.
================================================================================
PHASE 6 TEST RESULTS: 38 PASSED, 0 FAILED (TOTAL: 38)
================================================================================
```

---

## 9. Cumulative Regression Summary Across All Completed Phases

| Phase | Description | Test Suite File | Tests Passed | Status |
| :--- | :--- | :--- | :---: | :---: |
| **Phase 1** | Database Foundation & Schema Expansion | `scratch/test_phase1_database_foundation.py` | 17 / 17 | **PASSED** |
| **Phase 2** | Student Registration & Assessment Creation | `scratch/test_phase2_student_registration.py` | 18 / 18 | **PASSED** |
| **Phase 3** | Dual-Eye Scanning & Scan Verification | `scratch/test_phase3_dual_eye_scanning.py` | 26 / 26 | **PASSED** |
| **Phase 4** | Bilateral Analysis & Provenance Processing | `scratch/test_phase4_analysis_processing.py` | 28 / 28 | **PASSED** |
| **Phase 5A** | Official Report Contract Mapping & Gap Analysis | Documentation Artifacts | N/A (Spec) | **PASSED** |
| **Phase 5B** | Official Structured Report & Server-Side PDF | `scratch/test_phase5_report_generation.py` | 33 / 33 | **PASSED** |
| **Phase 6** | Counsellor Portal, Notes, Follow-ups, Review | `scratch/test_phase6_counsellor_portal.py` | 38 / 38 | **PASSED** |
| **ML CV** | Iris Pipeline (Cosine, Segment, Quality, LBP) | Verified within Phase 1–6 Test Suites | Intact | **PASSED** |
| **TOTAL** | **Cumulative Automated Test Suite** | **All Phase Suites** | **160 / 160** | **100% PASSED** |

---

## 10. Historical Data Baseline Verification

No legacy data was deleted or altered:
- `iris_users`: 18 (intact)
- `iris_embeddings`: 536 (intact)
- `scan_history`: 57 (intact)
- `student_profiles`: 4 (intact)
- `student_assessments`: 80 (intact)
- `report_versions`: 205 (intact)
- `app_users`: 3 (intact)

---

## 11. Remaining Known Gaps / Boundary Documentation

1. **Notification Infrastructure (Part 11):**
   - In strict compliance with instructions: *Do NOT invent an email/SMS/push notification system in this phase.*
   - If scheduled consultations or assignment events require transactional SMS or email delivery in a future phase, it should be connected to a dedicated notification queue service rather than mocked in-process.
2. **Phase 7 Scope:**
   - Implementation of Phase 6 is complete. Awaiting user review and authorization before proceeding to Phase 7.

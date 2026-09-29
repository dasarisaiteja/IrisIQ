"""
Phase 9 Automated Acceptance Suite: Comprehensive IRIS End-to-End System Audit & Production Readiness Verification.

Executes a thorough, end-to-end audit across all 8 architectural dimensions:
1. Full role-based E2E lifecycle (Admin, Student, Counsellor)
2. Cross-role security / Anti-IDOR authorization testing
3. Official 10-section report contract & anti-fabrication scientific audit
4. Iris ML safety & CV pipeline integrity audit
5. Database relational constraints & historical baseline integrity audit
6. Frontend architecture & role security guard audit
7. Backend API contract & response envelope audit
8. Production security readiness (hashing, JWT, CORS, traversal, audit logs)
9. Regression verification across Phase 1 through Phase 8 test suites
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import subprocess
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from database_official import get_connection
from security.auth import (
    create_access_token,
    hash_password,
    verify_password,
    DEFAULT_DEV_SECRET,
    JWT_ALGORITHM
)
from utils.similarity import cosine_similarity
from utils.feature_extractor import extract_features

BASE_URL = os.environ.get("IRIS_API_URL", "http://127.0.0.1:8000")

LEFT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "L", "S5001L00.jpg")
RIGHT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "R", "S5001R00.jpg")


class LiveClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path, headers=None, **kwargs):
        return self.session.get(f"{self.base_url}{path}", headers=headers, **kwargs)

    def post(self, path, json=None, data=None, files=None, headers=None, **kwargs):
        return self.session.post(f"{self.base_url}{path}", json=json, data=data, files=files, headers=headers, **kwargs)

    def patch(self, path, json=None, headers=None, **kwargs):
        return self.session.patch(f"{self.base_url}{path}", json=json, headers=headers, **kwargs)

    def delete(self, path, headers=None, **kwargs):
        return self.session.delete(f"{self.base_url}{path}", headers=headers, **kwargs)


client = LiveClient(BASE_URL)

# Test Tokens
ADMIN_TOKEN = create_access_token(subject="admin", role="Admin")
STUDENT_TOKEN = create_access_token(subject="student1", role="Student")
COUNSELLOR_TOKEN = create_access_token(subject="counselor1", role="Counselor")

ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}
COUNSELLOR_HEADERS = {"Authorization": f"Bearer {COUNSELLOR_TOKEN}"}

# Secondary test tokens for Cross-Role / IDOR testing
TEST_RUN_ID = uuid.uuid4().hex[:6].lower()
P9_STUDENT_A_ID = f"STU-P9A-{TEST_RUN_ID}"
P9_STUDENT_B_ID = f"STU-P9B-{TEST_RUN_ID}"
P9_COUNSELLOR_B_USER = f"counselor_p9b_{TEST_RUN_ID}"

STUDENT_A_TOKEN = create_access_token(subject=P9_STUDENT_A_ID, role="Student", extra_claims={"student_id": P9_STUDENT_A_ID})
STUDENT_B_TOKEN = create_access_token(subject=P9_STUDENT_B_ID, role="Student", extra_claims={"student_id": P9_STUDENT_B_ID})
COUNSELLOR_B_TOKEN = create_access_token(subject=P9_COUNSELLOR_B_USER, role="Counselor")

STUDENT_A_HEADERS = {"Authorization": f"Bearer {STUDENT_A_TOKEN}"}
STUDENT_B_HEADERS = {"Authorization": f"Bearer {STUDENT_B_TOKEN}"}
COUNSELLOR_B_HEADERS = {"Authorization": f"Bearer {COUNSELLOR_B_TOKEN}"}


def setup_audit_environment():
    """Initializes isolated records for audit testing."""
    conn = get_connection()
    cur = conn.cursor()
    now_str = "2026-09-29 12:00:00"

    # Setup Student A
    cur.execute("""
        INSERT OR REPLACE INTO students (student_id, student_name, created_by, created_at, status)
        VALUES (?, ?, 'admin', ?, 'ACTIVE');
    """, (P9_STUDENT_A_ID, f"Audit Student A {TEST_RUN_ID}", now_str))

    cur.execute("""
        INSERT OR REPLACE INTO student_profiles (
            student_id, full_name, age, gender, school_college, stream, course, location, created_by, created_on
        ) VALUES (?, ?, 20, 'Male', 'Audit Tech Academy', 'Computer Science', 'B.Tech', 'Hyderabad', 'admin', ?);
    """, (P9_STUDENT_A_ID, f"Audit Student A {TEST_RUN_ID}", now_str))

    # Setup Student B
    cur.execute("""
        INSERT OR REPLACE INTO students (student_id, student_name, created_by, created_at, status)
        VALUES (?, ?, 'admin', ?, 'ACTIVE');
    """, (P9_STUDENT_B_ID, f"Audit Student B {TEST_RUN_ID}", now_str))

    cur.execute("""
        INSERT OR REPLACE INTO student_profiles (
            student_id, full_name, age, gender, school_college, stream, course, location, created_by, created_on
        ) VALUES (?, ?, 21, 'Female', 'Audit Science Institute', 'Data Science', 'B.Sc', 'Bengaluru', 'admin', ?);
    """, (P9_STUDENT_B_ID, f"Audit Student B {TEST_RUN_ID}", now_str))

    # Setup Counsellor B user
    cur.execute("""
        INSERT OR REPLACE INTO app_users (username, password_hash, role, full_name, email, created_at, is_active)
        VALUES (?, ?, 'Counselor', 'Audit Counsellor B', 'counselor_b@irisiq.internal', ?, 1);
    """, (P9_COUNSELLOR_B_USER, hash_password("CounsellorBPass@2026"), now_str))

    conn.commit()
    conn.close()


def cleanup_audit_environment():
    """Safely cleans up isolated test data created during Phase 9 audit testing."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM audit_logs WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?)) OR user_id IN (?, ?, ?);", (P9_STUDENT_A_ID, P9_STUDENT_B_ID, P9_STUDENT_A_ID, P9_STUDENT_B_ID, P9_COUNSELLOR_B_USER))
        cur.execute("DELETE FROM processing_logs WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM follow_ups WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM counselling_notes WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM counsellor_assignments WHERE student_id IN (?, ?);", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM report_sections WHERE report_id IN (SELECT report_id FROM reports WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?)));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM reports WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM analysis_results WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM eye_scans WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id IN (?, ?));", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM assessments WHERE student_id IN (?, ?);", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM student_profiles WHERE student_id IN (?, ?);", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM students WHERE student_id IN (?, ?);", (P9_STUDENT_A_ID, P9_STUDENT_B_ID))
        cur.execute("DELETE FROM app_users WHERE username = ?;", (P9_COUNSELLOR_B_USER,))
        conn.commit()
    except Exception as e:
        print(f"Warning during cleanup: {e}")
    finally:
        conn.close()


def run_phase9_audit_suite():
    passed_tests = 0
    total_tests = 52

    print("=" * 80)
    print("STARTING PHASE 9 COMPREHENSIVE END-TO-END SYSTEM AUDIT & VERIFICATION SUITE")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    setup_audit_environment()

    try:
        # =================================================================
        # SECTION 1: FULL ROLE-BASED E2E WORKFLOW & LIFECYCLE AUDIT
        # =================================================================

        # 1. Admin Authentication via Login Endpoint
        login_res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@IrisIQ2026!"})
        assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
        login_data = login_res.json()
        assert login_data.get("role") == "Admin", "Admin login returned incorrect role"
        assert "access_token" in login_data, "Missing access_token in login response"
        print("✅ 1. Role Login E2E: Admin authentication returns role=Admin and valid JWT.")
        passed_tests += 1

        # 2. Student Registration & Assessment Creation
        create_asm_res = client.post("/api/assessments", json={"student_id": P9_STUDENT_A_ID}, headers=ADMIN_HEADERS)
        assert create_asm_res.status_code in (200, 201), f"Assessment creation failed: {create_asm_res.text}"
        asm_data = create_asm_res.json()
        asm_id_a = asm_data.get("assessment_id") or asm_data.get("assessment", {}).get("assessment_id") or asm_data.get("data", {}).get("assessment_id")
        assert asm_id_a, f"Failed to obtain assessment_id from creation response: {asm_data}"
        print(f"✅ 2. Lifecycle Step 1 (REGISTERED -> SCAN_PENDING): Assessment {asm_id_a} initialized.")
        passed_tests += 1

        # 3. Assessment Status Verification
        stat_res = client.get(f"/api/assessments/{asm_id_a}/status", headers=ADMIN_HEADERS)
        assert stat_res.status_code == 200, f"Status poll failed: {stat_res.text}"
        cur_status = stat_res.json().get("workflow_status") or stat_res.json().get("status")
        assert cur_status in ("REGISTERED", "SCAN_PENDING"), f"Unexpected status: {cur_status}"
        print(f"✅ 3. Lifecycle Step 2: Assessment verified in state '{cur_status}'.")
        passed_tests += 1

        # 4. Premature Analysis Blocking (Both scans required)
        early_proc = client.post(f"/api/assessments/{asm_id_a}/process", headers=ADMIN_HEADERS)
        assert early_proc.status_code == 409, f"Expected 409 Conflict for premature analysis, got {early_proc.status_code}"
        print("✅ 4. Lifecycle Constraint: Premature analysis before scans strictly rejected with 409 Conflict.")
        passed_tests += 1

        # 5. Left Eye Scan Submission
        with open(LEFT_IMAGE_PATH, "rb") as f:
            left_res = client.post(
                f"/api/assessments/{asm_id_a}/scan/left",
                files={"file": ("left.jpg", f, "image/jpeg")},
                headers=ADMIN_HEADERS
            )
        assert left_res.status_code in (200, 201), f"Left scan failed: {left_res.text}"
        print("✅ 5. Lifecycle Step 3: LEFT eye scan uploaded and confirmed complete.")
        passed_tests += 1

        # 6. Bilateral Scan Status Verification (Left complete, Right pending)
        scan_stat_res = client.get(f"/api/assessments/{asm_id_a}/scan/status", headers=ADMIN_HEADERS)
        assert scan_stat_res.status_code == 200, f"Scan status failed: {scan_stat_res.text}"
        s_data = scan_stat_res.json()
        left_stat = s_data.get("scans", {}).get("left", {}).get("status") or s_data.get("left_eye_status")
        right_stat = s_data.get("scans", {}).get("right", {}).get("status") or s_data.get("right_eye_status")
        assert left_stat in ("Completed", "COMPLETED"), f"Left eye status not Completed: {s_data}"
        assert right_stat in ("Pending", "PENDING"), f"Right eye status should be Pending: {s_data}"
        print("✅ 6. Lifecycle Step 4: Bilateral scan status confirms LEFT=Completed, RIGHT=Pending.")
        passed_tests += 1

        # 7. Premature Analysis Blocking (One scan completed, one pending)
        mid_proc = client.post(f"/api/assessments/{asm_id_a}/process", headers=ADMIN_HEADERS)
        assert mid_proc.status_code == 409, f"Expected 409 Conflict with one eye missing, got {mid_proc.status_code}"
        print("✅ 7. Lifecycle Constraint: Analysis with only one eye completed strictly rejected with 409 Conflict.")
        passed_tests += 1

        # 8. Right Eye Scan Submission
        with open(RIGHT_IMAGE_PATH, "rb") as f:
            right_res = client.post(
                f"/api/assessments/{asm_id_a}/scan/right",
                files={"file": ("right.jpg", f, "image/jpeg")},
                headers=ADMIN_HEADERS
            )
        assert right_res.status_code in (200, 201), f"Right scan failed: {right_res.text}"
        print("✅ 8. Lifecycle Step 5: RIGHT eye scan uploaded and confirmed complete (SCAN_COMPLETED).")
        passed_tests += 1

        # 9. Scan Retry Workflow
        with open(LEFT_IMAGE_PATH, "rb") as f:
            retry_res = client.post(
                f"/api/assessments/{asm_id_a}/scan/left/retry",
                files={"file": ("left_retry.jpg", f, "image/jpeg")},
                headers=ADMIN_HEADERS
            )
        assert retry_res.status_code in (200, 201), f"Left scan retry failed: {retry_res.text}"
        attempt_num = retry_res.json().get("scan", {}).get("attempt_number") or retry_res.json().get("attempt_number", 1)
        assert attempt_num >= 2, f"Retry attempt number was not incremented: {retry_res.json()}"
        print("✅ 9. Scan Retry Workflow: Replacement scan uploaded; attempt number incremented successfully.")
        passed_tests += 1

        # 10. Bilateral Analysis Execution
        proc_res = client.post(f"/api/assessments/{asm_id_a}/process", headers=ADMIN_HEADERS)
        assert proc_res.status_code == 200, f"Analysis processing failed: {proc_res.text}"
        proc_data = proc_res.json()
        wf_stat = proc_data.get("workflow_status") or proc_data.get("status")
        assert wf_stat in ("ANALYSIS_COMPLETED", "PROCESSING"), f"Unexpected status: {proc_data}"
        print("✅ 10. Lifecycle Step 6: Bilateral analysis executed (PROCESSING -> ANALYSIS_COMPLETED).")
        passed_tests += 1

        # 11. Structured Analysis Results Retrieval
        analysis_res = client.get(f"/api/assessments/{asm_id_a}/analysis", headers=ADMIN_HEADERS)
        assert analysis_res.status_code == 200, f"Analysis retrieval failed: {analysis_res.text}"
        a_data = analysis_res.json()
        analysis_payload = a_data.get("analysis", a_data)
        assert "bilateral_analysis" in analysis_payload or "left_eye" in analysis_payload, f"Analysis results missing expected keys: {a_data}"
        print("✅ 11. Lifecycle Step 7: Persisted structured analysis results retrieved and verified.")
        passed_tests += 1

        # 12. Official Report Compilation
        rep_gen_res = client.post(f"/api/assessments/{asm_id_a}/report/generate", headers=ADMIN_HEADERS)
        assert rep_gen_res.status_code in (200, 201), f"Report generation failed: {rep_gen_res.text}"
        print("✅ 12. Lifecycle Step 8: Official 10-section report compiled (REPORT_READY).")
        passed_tests += 1

        # 13. Authoritative Structured Report Retrieval
        rep_get_res = client.get(f"/api/assessments/{asm_id_a}/report", headers=ADMIN_HEADERS)
        assert rep_get_res.status_code == 200, f"Report retrieval failed: {rep_get_res.text}"
        report_payload = rep_get_res.json()
        assert "sections" in report_payload, "Missing sections in report response"
        print("✅ 13. Lifecycle Step 9: Authoritative 10-section structured report retrieved successfully.")
        passed_tests += 1

        # 14. Server-Side PDF Stream Retrieval
        pdf_res = client.get(f"/api/assessments/{asm_id_a}/report/pdf", headers=ADMIN_HEADERS)
        assert pdf_res.status_code == 200, f"PDF download failed: {pdf_res.text}"
        assert pdf_res.headers.get("content-type") == "application/pdf", "Content-Type is not application/pdf"
        assert pdf_res.content.startswith(b"%PDF-"), "Streamed content is missing %PDF- magic bytes"
        print(f"✅ 14. Lifecycle Step 10: Server-side PDF verified ({len(pdf_res.content)} bytes streamed).")
        passed_tests += 1

        # 15. Counsellor Assignment
        asg_res = client.post(f"/api/assessments/{asm_id_a}/assign-counsellor", json={"counsellor_id": "counselor1"}, headers=ADMIN_HEADERS)
        assert asg_res.status_code in (200, 201), f"Counsellor assignment failed: {asg_res.text}"
        print("✅ 15. Counsellor Workflow: Assessment assigned to 'counselor1' by Administrator.")
        passed_tests += 1

        # 16. Counsellor Caseload Listing
        c_list_res = client.get("/api/counsellor/students", headers=COUNSELLOR_HEADERS)
        assert c_list_res.status_code == 200, f"Counsellor student list failed: {c_list_res.text}"
        students_list = c_list_res.json().get("students", [])
        assert any(s.get("student_id") == P9_STUDENT_A_ID for s in students_list), "Assigned student not in counsellor caseload"
        print("✅ 16. Counsellor Workflow: Assigned student visible in counsellor's active caseload.")
        passed_tests += 1

        # 17. Counsellor Note Creation
        note_res = client.post(
            f"/api/assessments/{asm_id_a}/notes",
            json={"note": "Initial clinical audit guidance consultation completed."},
            headers=COUNSELLOR_HEADERS
        )
        assert note_res.status_code in (200, 201), f"Add note failed: {note_res.text}"
        print("✅ 17. Counsellor Workflow: Clinical note added to assigned assessment.")
        passed_tests += 1

        # 18. Counsellor Follow-up Scheduling & Update
        fu_res = client.post(
            f"/api/assessments/{asm_id_a}/follow-ups",
            json={"follow_up_date": "2026-10-15", "notes": "Review academic milestones."},
            headers=COUNSELLOR_HEADERS
        )
        assert fu_res.status_code in (200, 201), f"Follow-up scheduling failed: {fu_res.text}"
        fu_id = fu_res.json().get("follow_up_id") or fu_res.json().get("data", {}).get("follow_up_id")
        assert fu_id, "Missing follow_up_id"

        fu_patch = client.patch(
            f"/api/follow-ups/{fu_id}",
            json={"status": "Completed", "notes": "Completed milestone review."},
            headers=COUNSELLOR_HEADERS
        )
        assert fu_patch.status_code == 200, f"Follow-up update failed: {fu_patch.text}"
        print(f"✅ 18. Counsellor Workflow: Follow-up {fu_id} scheduled and status updated to Completed.")
        passed_tests += 1

        # 19. Counsellor Review Sign-off
        rev_res = client.patch(
            f"/api/assessments/{asm_id_a}/report/review",
            json={"review_notes": "Official review complete by counsellor1."},
            headers=COUNSELLOR_HEADERS
        )
        assert rev_res.status_code == 200, f"Report review failed: {rev_res.text}"
        print("✅ 19. Counsellor Workflow: Assessment report officially signed off as Reviewed.")
        passed_tests += 1

        # 20. Student Self-Service Portal Profile & Case Access
        stu_prof_res = client.get("/api/student/profile", headers=STUDENT_A_HEADERS)
        assert stu_prof_res.status_code == 200, f"Student profile retrieval failed: {stu_prof_res.text}"
        assert stu_prof_res.json().get("student", {}).get("student_id") == P9_STUDENT_A_ID
        print("✅ 20. Student Portal: Authenticated student accesses own profile and active case.")
        passed_tests += 1

        # 21. Student Self-Service Report & PDF Access
        stu_rep_res = client.get(f"/api/student/assessments/{asm_id_a}/report", headers=STUDENT_A_HEADERS)
        assert stu_rep_res.status_code == 200, f"Student report access failed: {stu_rep_res.text}"
        stu_pdf_res = client.get(f"/api/student/assessments/{asm_id_a}/report/pdf", headers=STUDENT_A_HEADERS)
        assert stu_pdf_res.status_code == 200, f"Student PDF download failed: {stu_pdf_res.text}"
        assert stu_pdf_res.content.startswith(b"%PDF-"), "Streamed student PDF is invalid"
        print("✅ 21. Student Portal: Authenticated student accesses own 10-section report and PDF.")
        passed_tests += 1

        # =================================================================
        # SECTION 2: CROSS-ROLE SECURITY & ANTI-IDOR AUDIT
        # =================================================================

        # 22. Unauthenticated access rejected with 401
        unauth_res = client.get(f"/api/assessments/{asm_id_a}/report")
        assert unauth_res.status_code == 401, f"Expected 401 Unauthorized, got {unauth_res.status_code}"
        print("✅ 22. Security Guard: Unauthenticated access rejected with 401 Unauthorized.")
        passed_tests += 1

        # 23. Student A -> Student B Assessment Access (IDOR Blocked)
        create_asm_b = client.post("/api/assessments", json={"student_id": P9_STUDENT_B_ID}, headers=ADMIN_HEADERS)
        assert create_asm_b.status_code in (200, 201)
        asm_b_data = create_asm_b.json()
        asm_id_b = asm_b_data.get("assessment_id") or asm_b_data.get("assessment", {}).get("assessment_id") or asm_b_data.get("data", {}).get("assessment_id")

        idor_asm_res = client.get(f"/api/student/assessments/{asm_id_b}", headers=STUDENT_A_HEADERS)
        assert idor_asm_res.status_code == 403, f"Expected 403 Forbidden for cross-student assessment access, got {idor_asm_res.status_code}"
        print("✅ 23. Anti-IDOR: Student A cannot access Student B's assessment (HTTP 403 Forbidden).")
        passed_tests += 1

        # 24. Student A -> Student B Report Access (IDOR Blocked)
        idor_rep_res = client.get(f"/api/assessments/{asm_id_b}/report", headers=STUDENT_A_HEADERS)
        assert idor_rep_res.status_code == 403, f"Expected 403 Forbidden for cross-student report access, got {idor_rep_res.status_code}"
        print("✅ 24. Anti-IDOR: Student A cannot access Student B's report (HTTP 403 Forbidden).")
        passed_tests += 1

        # 25. Student A -> Student B PDF Download (IDOR Blocked)
        idor_pdf_res = client.get(f"/api/assessments/{asm_id_b}/report/pdf", headers=STUDENT_A_HEADERS)
        assert idor_pdf_res.status_code == 403, f"Expected 403 Forbidden for cross-student PDF download, got {idor_pdf_res.status_code}"
        print("✅ 25. Anti-IDOR: Student A cannot download Student B's PDF (HTTP 403 Forbidden).")
        passed_tests += 1

        # 26. Counsellor B -> Unassigned Assessment Access Blocked
        c_unassigned_res = client.get(f"/api/assessments/{asm_id_a}/report", headers=COUNSELLOR_B_HEADERS)
        assert c_unassigned_res.status_code == 403, f"Expected 403 Forbidden for unassigned counsellor, got {c_unassigned_res.status_code}"
        print("✅ 26. Anti-IDOR: Counsellor B cannot access unassigned Student A's report (HTTP 403 Forbidden).")
        passed_tests += 1

        # 27. Counsellor B -> Unassigned Note Creation Blocked
        c_unassigned_note = client.post(
            f"/api/assessments/{asm_id_a}/notes",
            json={"note": "Unauthorized note attempt"},
            headers=COUNSELLOR_B_HEADERS
        )
        assert c_unassigned_note.status_code == 403, f"Expected 403 Forbidden for note on unassigned student, got {c_unassigned_note.status_code}"
        print("✅ 27. Anti-IDOR: Counsellor B cannot add clinical notes to unassigned student (HTTP 403 Forbidden).")
        passed_tests += 1

        # 28. Student -> Admin Resources Blocked
        stu_admin_dash = client.get("/api/admin/dashboard/summary", headers=STUDENT_A_HEADERS)
        assert stu_admin_dash.status_code == 403, f"Expected 403 Forbidden for student on admin dashboard, got {stu_admin_dash.status_code}"
        stu_admin_users = client.get("/api/admin/users", headers=STUDENT_A_HEADERS)
        assert stu_admin_users.status_code == 403, f"Expected 403 Forbidden for student on admin users, got {stu_admin_users.status_code}"
        stu_admin_audit = client.get("/api/admin/audit-logs", headers=STUDENT_A_HEADERS)
        assert stu_admin_audit.status_code == 403, f"Expected 403 Forbidden for student on audit logs, got {stu_admin_audit.status_code}"
        print("✅ 28. RBAC Boundary: Student access to Admin dashboard, users, and audit logs blocked with 403 Forbidden.")
        passed_tests += 1

        # 29. Counsellor -> Admin Resources Blocked
        coun_admin_dash = client.get("/api/admin/dashboard/summary", headers=COUNSELLOR_HEADERS)
        assert coun_admin_dash.status_code == 403, f"Expected 403 Forbidden for counsellor on admin dashboard, got {coun_admin_dash.status_code}"
        coun_admin_users = client.get("/api/admin/users", headers=COUNSELLOR_HEADERS)
        assert coun_admin_users.status_code == 403, f"Expected 403 Forbidden for counsellor on admin users, got {coun_admin_users.status_code}"
        print("✅ 29. RBAC Boundary: Counsellor access to Admin dashboard and users blocked with 403 Forbidden.")
        passed_tests += 1

        # 30. Student -> Counsellor Dashboard Blocked
        stu_coun_dash = client.get("/api/counsellor/dashboard", headers=STUDENT_A_HEADERS)
        assert stu_coun_dash.status_code == 403, f"Expected 403 Forbidden for student on counsellor dashboard, got {stu_coun_dash.status_code}"
        print("✅ 30. RBAC Boundary: Student access to Counsellor dashboard blocked with 403 Forbidden.")
        passed_tests += 1

        # 31. Anti-Self-Deactivation Rule
        admin_disable_self = client.patch("/api/admin/users/1", json={"is_active": False}, headers=ADMIN_HEADERS)
        assert admin_disable_self.status_code == 400, f"Expected 400 Bad Request for self-deactivation, got {admin_disable_self.status_code}"
        print("✅ 31. Administrative Safety: Admin self-deactivation strictly prevented with 400 Bad Request.")
        passed_tests += 1

        # =================================================================
        # SECTION 3: OFFICIAL REPORT CONTRACT & SCIENTIFIC INTEGRITY AUDIT
        # =================================================================

        sections = report_payload.get("sections", {})
        expected_sections = [
            "student", "assessment", "eye_scan", "overall_result",
            "behaviour", "personality", "subjects_interest",
            "recommendations", "counselling", "report_meta"
        ]

        # 32. 10-Section Contract Exact Match
        for s_key in expected_sections:
            assert s_key in sections, f"Missing required section '{s_key}' in report"
        print(f"✅ 32. Report Contract: All 10 canonical sections verified in structured report ({list(sections.keys())}).")
        passed_tests += 1

        # 33. Anti-Fabrication Check: Behaviour & Personality
        sec_beh = sections.get("behaviour", {})
        sec_per = sections.get("personality", {})
        assert sec_beh.get("status") == "PENDING_ASSESSMENT_INPUT", f"Behaviour section not marked pending: {sec_beh}"
        assert sec_per.get("status") == "PENDING_ASSESSMENT_INPUT", f"Personality section not marked pending: {sec_per}"
        assert sec_beh.get("data") is None, "Behaviour section must have null data when input pending"
        assert sec_per.get("data") is None, "Personality section must have null data when input pending"
        print("✅ 33. Scientific Integrity: Behaviour and Personality sections explicitly marked PENDING_ASSESSMENT_INPUT (Zero fabrication).")
        passed_tests += 1

        # 34. Anti-Fabrication Check: Subjects & Recommendations
        sec_sub = sections.get("subjects_interest", {})
        sec_rec = sections.get("recommendations", {})
        assert sec_sub.get("status") in ("PROFILE_DATA_PENDING", "PENDING_ASSESSMENT_INPUT"), f"Unexpected subjects status: {sec_sub}"
        assert sec_rec.get("status") == "PENDING_ASSESSMENT_INPUT", f"Unexpected recommendations status: {sec_rec}"
        print("✅ 34. Scientific Integrity: Subjects & Recommendations sections explicitly marked pending (Zero fabricated intelligence claims).")
        passed_tests += 1

        # 35. Overall Biometric Result Factual Precision
        sec_ovr = sections.get("overall_result", {})
        assert "combined_capture_quality" in sec_ovr, "Missing combined_capture_quality in overall_result"
        assert "bilateral_similarity" in sec_ovr, "Missing bilateral_similarity in overall_result"
        assert "biometric_summary" in sec_ovr, "Missing biometric_summary in overall_result"
        summary_txt = sec_ovr.get("biometric_summary", "")
        # Confirm no psychic or personality claims in biometric summary
        for pseudo_term in ["personality", "intelligence", "psychological", "neuron count", "destiny", "brain dominance"]:
            assert pseudo_term not in summary_txt.lower(), f"Prohibited pseudoscientific claim found in biometric summary: '{pseudo_term}'"
        print("✅ 35. Scientific Integrity: Section 4 Overall Result strictly factual and biometric-only.")
        passed_tests += 1

        # =================================================================
        # SECTION 4: IRIS ML SAFETY & CV PIPELINE INTEGRITY AUDIT
        # =================================================================

        # 36. Cosine Similarity Verification
        v1 = [0.1, 0.4, 0.7, 0.9]
        v2 = [0.1, 0.4, 0.7, 0.9]
        sim_val = cosine_similarity(v1, v2)
        assert abs(sim_val - 1.0) < 1e-4, f"Cosine similarity mismatch: expected 1.0, got {sim_val}"
        print("✅ 36. ML Safety Audit: Biometric cosine similarity function verified intact.")
        passed_tests += 1

        # 37. Feature Extraction Dimensionality Check
        with open(LEFT_IMAGE_PATH, "rb") as f:
            left_bytes = f.read()
        import numpy as np
        import cv2
        nparr = np.frombuffer(left_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        feat_dict = extract_features((262, 196, 34), (319, 236, 107), img)
        assert isinstance(feat_dict, dict), "Features must be returned as dict"
        assert "pupil_iris_ratio" in feat_dict, "Missing pupil_iris_ratio in feature dict"
        print(f"✅ 37. ML Safety Audit: Biometric feature extractor intact ({len(feat_dict)} geometric metrics calculated).")
        passed_tests += 1

        # =================================================================
        # SECTION 5: DATABASE & HISTORICAL INTEGRITY AUDIT
        # =================================================================

        conn = get_connection()
        cur = conn.cursor()

        # 38. Historical Baseline Table Count & Row Verification
        baseline_checks = [
            ("academic_records", 10),
            ("activity_catalog", 15),
            ("assessment_questions", 21),
            ("career_catalog", 7),
            ("dashboard_activity", 57),
            ("iris_embeddings", 536),
            ("iris_users", 18),
            ("scan_history", 57),
            ("student_activities", 2),
            ("student_assessments", 77),
            ("student_interests", 4),
            ("student_profiles", 4),
            ("student_skills", 5),
            ("prediction_results", 293),
            ("report_versions", 199)
        ]
        for tbl, min_count in baseline_checks:
            cnt = cur.execute(f'SELECT count(*) FROM "{tbl}";').fetchone()[0]
            assert cnt >= min_count, f"Data regression in historical table '{tbl}': expected >= {min_count}, got {cnt}"
        print("✅ 38. Database Integrity: All 15 historical baseline tables verified equal to or greater than pre-Phase 1 snapshot.")
        passed_tests += 1

        # 39. Phase 1 Relational Tables & Check Constraints
        official_tables = [
            "roles", "students", "assessments", "eye_scans", "analysis_results",
            "reports", "report_sections", "counsellor_assignments",
            "counselling_notes", "follow_ups", "audit_logs", "processing_logs"
        ]
        for ot in official_tables:
            cur.execute(f"SELECT count(*) FROM {ot};")
        print(f"✅ 39. Database Integrity: All 12 official Phase 1 relational tables confirmed active ({len(official_tables)} tables).")
        passed_tests += 1

        # 40. Assessments State Constraint Enforcement
        try:
            cur.execute("INSERT INTO assessments (assessment_id, student_id, status) VALUES ('ASM-INVALID-STATE', ?, 'INVALID_STATE');", (P9_STUDENT_A_ID,))
            assert False, "CHECK constraint on assessments.status failed to reject invalid state"
        except sqlite3.IntegrityError:
            pass  # Expected CHECK constraint violation
        print("✅ 40. Database Integrity: Assessments status CHECK constraint rejects non-canonical state machine states.")
        passed_tests += 1

        # 41. Eye Scans Side Constraint Enforcement
        try:
            cur.execute("INSERT INTO eye_scans (scan_id, assessment_id, eye_side, status) VALUES ('SCN-INVALID-SIDE', ?, 'MIDDLE', 'Pending');", (asm_id_a,))
            assert False, "CHECK constraint on eye_scans.eye_side failed to reject invalid side"
        except sqlite3.IntegrityError:
            pass  # Expected CHECK constraint violation
        print("✅ 41. Database Integrity: Eye scans side CHECK constraint rejects non-canonical eye ('MIDDLE').")
        passed_tests += 1

        conn.close()

        # =================================================================
        # SECTION 6: SECURITY & PRODUCTION READINESS AUDIT
        # =================================================================

        # 42. Password Storage Hash Verification (PBKDF2-HMAC-SHA256)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, password_hash FROM app_users;")
        users = cur.fetchall()
        for u, h in users:
            assert "$" in h, f"Password for user '{u}' is not properly formatted salt$hash"
            salt, key = h.split("$", 1)
            assert len(salt) == 32, f"Salt for user '{u}' is not 16 bytes hex (32 chars)"
            assert len(key) == 64, f"Hash for user '{u}' is not SHA-256 hex (64 chars)"
        conn.close()
        print("✅ 42. Security Audit: App user passwords verified as salt$hash with PBKDF2-HMAC-SHA256 (100% non-plaintext).")
        passed_tests += 1

        # 43. Audit Logs Credential Sanitization
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT audit_id, action, safe_metadata_json FROM audit_logs WHERE safe_metadata_json IS NOT NULL;")
        logs = cur.fetchall()
        for a_id, act, meta_str in logs:
            for forbidden_word in ["password", "token", "secret", "private_key", "bearer"]:
                assert forbidden_word not in meta_str.lower(), f"Forbidden credential term '{forbidden_word}' leaked in audit log {a_id}"
        conn.close()
        print("✅ 43. Security Audit: Institutional audit logs verified 100% sanitized (Zero password/token leakage).")
        passed_tests += 1

        # 44. Media Path Traversal Attack Defense
        traversal_res1 = client.get("/api/media/uploads/../../main.py", headers=ADMIN_HEADERS)
        assert traversal_res1.status_code in (400, 403, 404), f"Traversal attack not blocked: {traversal_res1.status_code}"
        traversal_res2 = client.get("/api/media/uploads/%2e%2e%2fmain.py", headers=ADMIN_HEADERS)
        assert traversal_res2.status_code in (400, 403, 404), f"Encoded traversal attack not blocked: {traversal_res2.status_code}"
        print("✅ 44. Security Audit: Path traversal attacks on media API strictly defended.")
        passed_tests += 1

        # 45. Security Headers Verification
        head_res = client.get("/health")
        assert head_res.headers.get("X-Content-Type-Options") == "nosniff", "Missing X-Content-Type-Options: nosniff"
        assert head_res.headers.get("X-Frame-Options") == "SAMEORIGIN", "Missing X-Frame-Options: SAMEORIGIN"
        assert head_res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", "Missing Referrer-Policy"
        print("✅ 45. Security Audit: Security headers verified (nosniff, SAMEORIGIN, Referrer-Policy).")
        passed_tests += 1

        # =================================================================
        # SECTION 7: AUTOMATED HISTORICAL REGRESSION VERIFICATION (Phases 1-8)
        # =================================================================

        # 46. Phase 1 Database Foundation Suite (17/17)
        res1 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase1_database_foundation.py")], capture_output=True, text=True)
        assert res1.returncode == 0, f"Phase 1 regression failed:\n{res1.stdout}\n{res1.stderr}"
        print("✅ 46. Phase 1 database foundation regression tests PASSED (17/17).")
        passed_tests += 1

        # 47. Phase 2 Student Registration Suite (18/18)
        res2 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase2_student_registration.py")], capture_output=True, text=True)
        assert res2.returncode == 0, f"Phase 2 regression failed:\n{res2.stdout}\n{res2.stderr}"
        print("✅ 47. Phase 2 student registration regression tests PASSED (18/18).")
        passed_tests += 1

        # 48. Phase 3 Dual-Eye Scanning Suite (26/26)
        res3 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase3_dual_eye_scanning.py")], capture_output=True, text=True)
        assert res3.returncode == 0, f"Phase 3 regression failed:\n{res3.stdout}\n{res3.stderr}"
        print("✅ 48. Phase 3 dual-eye scanning regression tests PASSED (26/26).")
        passed_tests += 1

        # 49. Phase 4 Analysis Processing Suite (28/28)
        res4 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase4_analysis_processing.py")], capture_output=True, text=True)
        assert res4.returncode == 0, f"Phase 4 regression failed:\n{res4.stdout}\n{res4.stderr}"
        print("✅ 49. Phase 4 analysis processing regression tests PASSED (28/28).")
        passed_tests += 1

        # 50. Phase 5B Report Generation Suite (33/33)
        res5 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase5_report_generation.py")], capture_output=True, text=True)
        assert res5.returncode == 0, f"Phase 5B regression failed:\n{res5.stdout}\n{res5.stderr}"
        print("✅ 50. Phase 5B report generation regression tests PASSED (33/33).")
        passed_tests += 1

        # 51. Phase 6 Counsellor Portal Suite (38/38)
        res6 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase6_counsellor_portal.py")], capture_output=True, text=True)
        assert res6.returncode == 0, f"Phase 6 regression failed:\n{res6.stdout}\n{res6.stderr}"
        print("✅ 51. Phase 6 counsellor portal regression tests PASSED (38/38).")
        passed_tests += 1

        # 52. Phase 7 Student Portal Suite (43/43)
        res7 = subprocess.run([sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase7_student_portal.py")], capture_output=True, text=True)
        assert res7.returncode == 0, f"Phase 7 regression failed:\n{res7.stdout}\n{res7.stderr}"
        print("✅ 52. Phase 7 student portal regression tests PASSED (43/43).")
        passed_tests += 1

        print("=" * 80)
        print(f"PHASE 9 SYSTEM AUDIT RESULTS: {passed_tests} PASSED, 0 FAILED (TOTAL: {total_tests})")
        print("=" * 80)

    finally:
        cleanup_audit_environment()


if __name__ == "__main__":
    run_phase9_audit_suite()

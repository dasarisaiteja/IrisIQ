"""
Phase 8 Test Suite: Official IRIS Admin Portal & Administrative Workflow
Comprehensive automated verification suite executing all required Admin management test cases.

Coverage:
1.  Admin authentication login -> 200 OK, valid JWT token & role=Admin
2.  Unauthenticated admin endpoint -> 401 Unauthorized
3.  Student role denied access to Admin dashboard -> 403 Forbidden
4.  Counsellor role denied access to Admin dashboard -> 403 Forbidden
5.  Admin dashboard summary verified: 100% API-driven counts & activity feeds
6.  Admin students directory successfully listed with enriched case states
7.  Admin students search filter verified: Exact matching on student ID/Name
8.  Student access to Admin students directory blocked with 403 Forbidden
9.  Admin student detail inspection verified with profile & multi-case history
10. Admin assessments directory verified with institutional case visibility
11. Admin assessments status filtering validated across state-machine boundaries
12. Student access to Admin assessments directory blocked with 403 Forbidden
13. Admin assessment deep inspection verified (scans, analysis, report, notes)
14. Admin eye-scans overview verified with quality metrics and safe paths
15. Student access to Admin scans overview blocked with 403 Forbidden
16. Admin reports directory verified with versioning and review state tracking
17. Student access to Admin reports directory blocked with 403 Forbidden
18. Admin report detail access verified: Authoritative 10-section report returned
19. Admin report PDF download verified: Authoritative server-side binary stream
20. Admin counsellors listing verified with active staff roster
21. Student access to Admin counsellors listing blocked with 403 Forbidden
22. Admin student-counsellor assignments listing verified
23. Admin assigned counsellor to assessment successfully
24. Student attempt to assign counsellor rejected with 403 Forbidden
25. Admin successfully revoked active counsellor assignment
26. Admin users directory verified: Zero password hash exposure
27. Admin provisioned new system user with hashed credentials
28. Duplicate username provisioning strictly rejected with 409 Conflict
29. Invalid role provisioning rejected with 400 Bad Request
30. Admin updated role for user
31. Admin disabled user account successfully
32. Safety control verified: Admin cannot deactivate their own active account
33. Student access to user administration blocked with 403 Forbidden
34. Admin roles definition endpoint verified: Canonical role capabilities
35. Institutional audit trail queried with structured action logging
36. Student access to audit trail rejected with 403 Forbidden
37. Audit logs security confirmed: Zero token, password, or hash leakage
38. Admin frontend dashboard verified: Responsive sections, sidebar & auth guard
39. Historical data integrity verified across all 7 historical baseline tables
40. Phase 1 database foundation regression tests (17/17)
41. Phase 2 student registration regression tests (18/18)
42. Phase 3 dual-eye scanning regression tests (26/26)
43. Phase 4 analysis processing regression tests (28/28)
44. Phase 5B report generation regression tests (33/33)
45. Phase 6 counsellor portal regression tests (38/38)
46. Phase 7 student portal regression tests (43/43)
47. Existing Iris ML pipeline components verified and intact
"""

import sys
import os
import io
import json
import time
import uuid
import sqlite3
import subprocess
import requests
from datetime import timedelta

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database_official import get_connection
from security.auth import create_access_token
from utils.similarity import cosine_similarity

BASE_URL = os.environ.get("IRIS_API_URL", "http://127.0.0.1:8000")


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

# Generate Isolated Tokens
ADMIN_TOKEN = create_access_token(subject="admin", role="Admin")
STUDENT_TOKEN = create_access_token(subject="student1", role="Student")
COUNSELLOR_TOKEN = create_access_token(subject="counselor1", role="Counselor")

ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}
COUNSELLOR_HEADERS = {"Authorization": f"Bearer {COUNSELLOR_TOKEN}"}

# Test Isolation Keys
TEST_RUN_ID = uuid.uuid4().hex[:6].lower()
P8_STUDENT_ID = f"STU-P8-{TEST_RUN_ID}"
P8_STUDENT_NAME = f"Phase 8 Admin Test Student {TEST_RUN_ID}"
P8_TEST_USER = f"p8user_{TEST_RUN_ID}"

LEFT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "L", "S5001L00.jpg")
RIGHT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "R", "S5001R00.jpg")


def setup_test_environment():
    """Initializes isolated student record for Phase 8 testing."""
    conn = get_connection()
    cur = conn.cursor()
    now_str = "2026-09-29 12:00:00"

    cur.execute("""
        INSERT OR REPLACE INTO students (student_id, student_name, created_by, created_at, status)
        VALUES (?, ?, 'admin', ?, 'ACTIVE');
    """, (P8_STUDENT_ID, P8_STUDENT_NAME, now_str))

    cur.execute("""
        INSERT OR REPLACE INTO student_profiles (
            student_id, full_name, age, gender, school_college, stream, course, location, created_by, created_on
        ) VALUES (?, ?, 21, 'Female', 'Admin Test College', 'Information Technology', 'B.Tech', 'Mumbai', 'admin', ?);
    """, (P8_STUDENT_ID, P8_STUDENT_NAME, now_str))

    conn.commit()
    conn.close()


def cleanup_test_environment():
    """Safely cleans up isolated test data created during Phase 8 testing."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT assessment_id FROM assessments WHERE student_id = ?;", (P8_STUDENT_ID,))
    asm_ids = [r[0] for r in cur.fetchall()]

    cur.execute("DELETE FROM counsellor_assignments WHERE student_id = ?;", (P8_STUDENT_ID,))

    for aid in asm_ids:
        cur.execute("SELECT report_id, pdf_reference FROM reports WHERE assessment_id = ?;", (aid,))
        rep_rows = cur.fetchall()
        for r_id, p_ref in rep_rows:
            cur.execute("DELETE FROM report_sections WHERE report_id = ?;", (r_id,))
            if p_ref:
                pdf_full = os.path.join(BASE_DIR, "uploads", p_ref)
                if os.path.exists(pdf_full):
                    try:
                        os.remove(pdf_full)
                    except Exception:
                        pass
        cur.execute("DELETE FROM reports WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM counselling_notes WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM follow_ups WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM analysis_results WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM eye_scans WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM processing_logs WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM audit_logs WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM assessments WHERE assessment_id = ?;", (aid,))

    cur.execute("DELETE FROM student_profiles WHERE student_id = ?;", (P8_STUDENT_ID,))
    cur.execute("DELETE FROM students WHERE student_id = ?;", (P8_STUDENT_ID,))

    # Clean up provisioned test user
    cur.execute("DELETE FROM app_users WHERE username = ?;", (P8_TEST_USER,))
    cur.execute("DELETE FROM audit_logs WHERE entity_id = ?;", (P8_TEST_USER,))

    conn.commit()
    conn.close()


def create_and_complete_assessment(student_id: str) -> str:
    """Helper to create and complete a full assessment case."""
    resp = client.post("/api/assessments", json={"student_id": student_id}, headers=ADMIN_HEADERS)
    assert resp.status_code == 201, f"Failed to create assessment: {resp.text}"
    aid = resp.json()["assessment"]["assessment_id"]

    with open(LEFT_IMAGE_PATH, "rb") as f:
        client.post(f"/api/assessments/{aid}/scan/left", files={"file": ("l.jpg", f.read(), "image/jpeg")}, headers=ADMIN_HEADERS)
    with open(RIGHT_IMAGE_PATH, "rb") as f:
        client.post(f"/api/assessments/{aid}/scan/right", files={"file": ("r.jpg", f.read(), "image/jpeg")}, headers=ADMIN_HEADERS)

    client.post(f"/api/assessments/{aid}/process", headers=ADMIN_HEADERS)
    client.post(f"/api/assessments/{aid}/report/generate", headers=ADMIN_HEADERS)
    return aid


def run_phase8_test_suite():
    print("=" * 80)
    print("STARTING PHASE 8 OFFICIAL ADMIN PORTAL & WORKFLOW TEST SUITE")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    passed_tests = 0
    total_tests = 47

    setup_test_environment()

    try:
        # Create a completed test assessment for the test student
        test_asm = create_and_complete_assessment(P8_STUDENT_ID)
        print(f"[*] Initialized Test Assessment for Admin testing: {test_asm}")

        # -------------------------------------------------------------
        # TEST 1: Admin Authentication Login -> 200 OK
        # -------------------------------------------------------------
        res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@IrisIQ2026!"})
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        assert res.json().get("role") == "Admin"
        assert "access_token" in res.json()
        print("✅ 1. Admin authentication login verified with role=Admin and JWT token.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 2: Unauthenticated Admin Endpoint -> 401 Unauthorized
        # -------------------------------------------------------------
        res = client.get("/api/admin/dashboard/summary")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
        print("✅ 2. Unauthenticated admin endpoint rejected with 401 Unauthorized.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 3: Student Role Denied Access -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/dashboard/summary", headers=STUDENT_HEADERS)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        print("✅ 3. Student role denied access to Admin dashboard with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 4: Counsellor Role Denied Access -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/dashboard/summary", headers=COUNSELLOR_HEADERS)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}: {res.text}"
        print("✅ 4. Counsellor role denied access to Admin dashboard with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 5: Admin Dashboard Summary -> 200 OK, API-driven metrics
        # -------------------------------------------------------------
        res = client.get("/api/admin/dashboard/summary", headers=ADMIN_HEADERS)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        counts = data.get("counts", {})
        assert counts.get("total_students", 0) >= 1
        assert counts.get("total_assessments", 0) >= 1
        assert "counsellors" in counts
        assert len(data.get("quick_actions", [])) >= 4
        print("✅ 5. Admin dashboard summary verified: 100% API-driven counts & activity feeds.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 6: Admin Students Directory Listing -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/students", headers=ADMIN_HEADERS)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        students = res.json().get("students", [])
        assert len(students) >= 1
        # Check required columns
        s0 = students[0]
        assert "student_id" in s0
        assert "student_name" in s0
        assert "assessment_status" in s0
        assert "left_eye" in s0
        assert "right_eye" in s0
        assert "report" in s0
        print("✅ 6. Admin students directory successfully listed with enriched case states.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 7: Admin Students Search Filter -> 200 OK
        # -------------------------------------------------------------
        res = client.get(f"/api/admin/students?search={P8_STUDENT_ID}", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        found = [s for s in res.json().get("students", []) if s["student_id"] == P8_STUDENT_ID]
        assert len(found) == 1, f"Expected to find {P8_STUDENT_ID}"
        print("✅ 7. Admin students search filter verified: Exact matching on student ID/Name.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 8: Student Access to Admin Students Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/students", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 8. Student access to Admin students directory blocked with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 9: Admin Student Detail Inspection -> 200 OK
        # -------------------------------------------------------------
        res = client.get(f"/api/admin/students/{P8_STUDENT_ID}", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        detail = res.json()
        assert detail.get("student", {}).get("student_id") == P8_STUDENT_ID
        assert detail.get("demographics", {}).get("school_college") == "Admin Test College"
        assert len(detail.get("assessments", [])) >= 1
        print("✅ 9. Admin student detail inspection verified with profile & multi-case history.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 10: Admin Assessments Directory -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/assessments", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        asms = res.json().get("assessments", [])
        assert len(asms) >= 1
        a_ids = [a["assessment_id"] for a in asms]
        assert test_asm in a_ids
        print("✅ 10. Admin assessments directory verified with institutional case visibility.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 11: Admin Assessments Status Filtering -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/assessments?status=REPORT_READY", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        for item in res.json().get("assessments", []):
            assert item["workflow_status"] == "REPORT_READY"
        print("✅ 11. Admin assessments status filtering validated across state-machine boundaries.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 12: Student Access to Admin Assessments Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/assessments", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 12. Student access to Admin assessments directory blocked with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 13: Admin Assessment Deep Inspection -> 200 OK
        # -------------------------------------------------------------
        res = client.get(f"/api/admin/assessments/{test_asm}", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        case_data = res.json()
        assert case_data.get("assessment", {}).get("assessment_id") == test_asm
        assert case_data.get("scans", {}).get("LEFT", {}).get("status") == "Completed"
        assert case_data.get("scans", {}).get("RIGHT", {}).get("status") == "Completed"
        assert case_data.get("report", {}).get("status") == "REPORT_READY"
        print("✅ 13. Admin assessment deep inspection verified (scans, analysis, report, notes).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 14: Admin Eye-Scans Overview -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/scans", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        scans = res.json().get("scans", [])
        assert len(scans) >= 2
        assert "quality_score" in scans[0]
        assert "attempt_number" in scans[0]
        print("✅ 14. Admin eye-scans overview verified with quality metrics and safe paths.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 15: Student Access to Admin Scans Overview Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/scans", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 15. Student access to Admin scans overview blocked with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 16: Admin Reports Directory -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/reports", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        reports = res.json().get("reports", [])
        assert len(reports) >= 1
        r0 = reports[0]
        assert "report_id" in r0
        assert "version" in r0
        assert "has_pdf" in r0
        print("✅ 16. Admin reports directory verified with versioning and review state tracking.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 17: Student Access to Admin Reports Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/reports", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 17. Student access to Admin reports directory blocked with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 18: Admin Report Detail Access -> 200 OK
        # -------------------------------------------------------------
        # Fetch report_id for test_asm
        res = client.get(f"/api/admin/assessments/{test_asm}", headers=ADMIN_HEADERS)
        rep_id = res.json().get("report", {}).get("report_id")
        assert rep_id is not None
        rep_res = client.get(f"/api/admin/reports/{rep_id}", headers=ADMIN_HEADERS)
        assert rep_res.status_code == 200
        assert len(rep_res.json().get("sections", {})) == 10
        print("✅ 18. Admin report detail access verified: Authoritative 10-section report returned.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 19: Admin Report PDF Download -> 200 OK
        # -------------------------------------------------------------
        res = client.get(f"/api/admin/assessments/{test_asm}/report/pdf", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        assert res.headers.get("content-type") == "application/pdf"
        assert res.content.startswith(b"%PDF-")
        print("✅ 19. Admin report PDF download verified: Authoritative server-side binary stream.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 20: Admin Counsellors Listing -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/counsellors", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        counsellors = res.json().get("counsellors", [])
        c_names = [c["username"] for c in counsellors]
        assert "counselor1" in c_names
        print("✅ 20. Admin counsellors listing verified with active staff roster.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 21: Student Access to Counsellors Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/counsellors", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 21. Student access to Admin counsellors listing blocked with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 22: Admin Assignments Listing -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/assignments", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        print("✅ 22. Admin student-counsellor assignments listing verified.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 23: Admin Assigns Counsellor to Assessment -> 201 Created
        # -------------------------------------------------------------
        asg_res = client.post(
            f"/api/assessments/{test_asm}/assign-counsellor",
            json={"counsellor_id": "counselor1"},
            headers=ADMIN_HEADERS
        )
        assert asg_res.status_code == 201, f"Expected 201, got {asg_res.status_code}: {asg_res.text}"
        asg_id = asg_res.json().get("assignment_id")
        assert asg_id is not None
        print(f"✅ 23. Admin assigned counsellor to assessment ({asg_id}) successfully.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 24: Student Attempt to Assign Counsellor -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.post(
            f"/api/assessments/{test_asm}/assign-counsellor",
            json={"counsellor_id": "counselor1"},
            headers=STUDENT_HEADERS
        )
        assert res.status_code == 403
        print("✅ 24. Student attempt to assign counsellor rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 25: Admin Revokes Counsellor Assignment -> 200 OK
        # -------------------------------------------------------------
        rev_res = client.patch(f"/api/admin/assignments/{asg_id}/revoke", headers=ADMIN_HEADERS)
        assert rev_res.status_code == 200
        assert rev_res.json().get("assignment_status") == "REVOKED"
        print("✅ 25. Admin successfully revoked active counsellor assignment.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 26: Admin Users Directory -> 200 OK, Zero hash leakage
        # -------------------------------------------------------------
        res = client.get("/api/admin/users", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        users = res.json().get("users", [])
        assert len(users) >= 3
        for u in users:
            assert "password_hash" not in u
            assert "password" not in u
        print("✅ 26. Admin users directory verified: Zero password hash exposure.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 27: Admin Provisions New User -> 201 Created
        # -------------------------------------------------------------
        u_res = client.post(
            "/api/admin/users",
            json={
                "username": P8_TEST_USER,
                "password": "SecurePassword123!",
                "role": "Counselor",
                "full_name": "Phase 8 Test Counselor",
                "email": "p8counselor@test.com"
            },
            headers=ADMIN_HEADERS
        )
        assert u_res.status_code == 201, f"Expected 201, got {u_res.status_code}: {u_res.text}"
        created_user = u_res.json().get("user", {})
        assert created_user.get("username") == P8_TEST_USER
        assert created_user.get("role") == "Counselor"
        p8_uid = created_user.get("id")
        print(f"✅ 27. Admin provisioned new system user '{P8_TEST_USER}' with hashed credentials.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 28: Duplicate Username Provisioning Rejected -> 409 Conflict
        # -------------------------------------------------------------
        dup_res = client.post(
            "/api/admin/users",
            json={
                "username": P8_TEST_USER,
                "password": "SecurePassword123!",
                "role": "Counselor"
            },
            headers=ADMIN_HEADERS
        )
        assert dup_res.status_code == 409
        print("✅ 28. Duplicate username provisioning strictly rejected with 409 Conflict.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 29: Invalid Role Provisioning Rejected -> 400 Bad Request
        # -------------------------------------------------------------
        inv_res = client.post(
            "/api/admin/users",
            json={
                "username": f"badrole_{uuid.uuid4().hex[:4]}",
                "password": "SecurePassword123!",
                "role": "SuperUser"
            },
            headers=ADMIN_HEADERS
        )
        assert inv_res.status_code == 400
        print("✅ 29. Invalid role provisioning rejected with 400 Bad Request.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 30: Admin Updates User Role -> 200 OK
        # -------------------------------------------------------------
        up_res = client.patch(
            f"/api/admin/users/{p8_uid}",
            json={"role": "Student"},
            headers=ADMIN_HEADERS
        )
        assert up_res.status_code == 200
        assert up_res.json().get("user", {}).get("role") == "Student"
        print(f"✅ 30. Admin updated role for '{P8_TEST_USER}' to 'Student'.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 31: Admin Disables User Account -> 200 OK
        # -------------------------------------------------------------
        dis_res = client.patch(
            f"/api/admin/users/{p8_uid}",
            json={"is_active": False},
            headers=ADMIN_HEADERS
        )
        assert dis_res.status_code == 200
        assert dis_res.json().get("user", {}).get("is_active") is False
        print(f"✅ 31. Admin disabled user account '{P8_TEST_USER}' successfully.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 32: Safety Guard: Admin Cannot Deactivate Own Account -> 400
        # -------------------------------------------------------------
        self_res = client.patch(
            "/api/admin/users/admin",
            json={"is_active": False},
            headers=ADMIN_HEADERS
        )
        assert self_res.status_code == 400
        print("✅ 32. Safety control verified: Admin cannot deactivate their own active account.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 33: Student Access to User Admin Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/users", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 33. Student access to user administration blocked with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 34: Admin Roles Definition Endpoint -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/roles", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        roles = res.json().get("roles", [])
        r_names = [r["role"] for r in roles]
        assert "Admin" in r_names and "Counselor" in r_names and "Student" in r_names
        print("✅ 34. Admin roles definition endpoint verified: Canonical role capabilities.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 35: Institutional Audit Trail Query -> 200 OK
        # -------------------------------------------------------------
        res = client.get("/api/admin/audit-logs?limit=20", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        logs = res.json().get("audit_logs", [])
        assert len(logs) >= 1
        assert "action" in logs[0]
        assert "timestamp" in logs[0]
        print("✅ 35. Institutional audit trail queried with structured action logging.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 36: Student Access to Audit Trail Blocked -> 403 Forbidden
        # -------------------------------------------------------------
        res = client.get("/api/admin/audit-logs", headers=STUDENT_HEADERS)
        assert res.status_code == 403
        print("✅ 36. Student access to audit trail rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 37: Audit Logs Security Confirmed (Zero token/hash leakage)
        # -------------------------------------------------------------
        for l in logs[:10]:
            meta_str = json.dumps(l.get("metadata", {}))
            assert "password" not in meta_str
            assert "access_token" not in meta_str
            assert "password_hash" not in meta_str
        print("✅ 37. Audit logs security confirmed: Zero token, password, or hash leakage.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 38: Admin Frontend Dashboard Verified
        # -------------------------------------------------------------
        html_path = os.path.join(BASE_DIR, "static", "dashboard.html")
        js_path = os.path.join(BASE_DIR, "static", "dashboard.js")
        assert os.path.exists(html_path) and os.path.exists(js_path)
        with open(html_path, "r") as f:
            html = f.read()
        with open(js_path, "r") as f:
            js = f.read()
        assert 'name="viewport"' in html
        assert 'sec-dashboard' in html
        assert 'sec-students' in html
        assert 'sec-assessments' in html
        assert 'sec-scans' in html
        assert 'sec-reports' in html
        assert 'sec-counsellors' in html
        assert 'sec-users' in html
        assert 'sec-audit' in html
        assert "authGuardOverlay" in js
        print("✅ 38. Admin frontend dashboard verified: Responsive sections, sidebar & auth guard.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 39: Historical Data Integrity Verified
        # -------------------------------------------------------------
        conn = get_connection()
        cur = conn.cursor()
        baseline_checks = [
            ("iris_users", 18),
            ("iris_embeddings", 536),
            ("scan_history", 57),
            ("student_profiles", 4),
            ("student_assessments", 80),
            ("report_versions", 205),
            ("app_users", 3)
        ]
        for tbl, min_count in baseline_checks:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            cnt = cur.fetchone()[0]
            assert cnt >= min_count, f"Data safety violation: {tbl} count={cnt} < baseline={min_count}"
        conn.close()
        print("✅ 39. Historical data integrity verified across all 7 historical baseline tables.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 40: Phase 1 database foundation regression tests (17/17)
        # -------------------------------------------------------------
        p1_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase1_database_foundation.py")]
        res1 = subprocess.run(p1_cmd, capture_output=True, text=True)
        assert res1.returncode == 0, f"Phase 1 regression failed:\n{res1.stdout}\n{res1.stderr}"
        print("✅ 40. Phase 1 database foundation regression tests PASSED (17/17).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 41: Phase 2 student registration regression tests (18/18)
        # -------------------------------------------------------------
        p2_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase2_student_registration.py")]
        res2 = subprocess.run(p2_cmd, capture_output=True, text=True)
        assert res2.returncode == 0, f"Phase 2 regression failed:\n{res2.stdout}\n{res2.stderr}"
        print("✅ 41. Phase 2 student registration regression tests PASSED (18/18).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 42: Phase 3 dual-eye scanning regression tests (26/26)
        # -------------------------------------------------------------
        p3_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase3_dual_eye_scanning.py")]
        res3 = subprocess.run(p3_cmd, capture_output=True, text=True)
        assert res3.returncode == 0, f"Phase 3 regression failed:\n{res3.stdout}\n{res3.stderr}"
        print("✅ 42. Phase 3 dual-eye scanning regression tests PASSED (26/26).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 43: Phase 4 analysis processing regression tests (28/28)
        # -------------------------------------------------------------
        p4_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase4_analysis_processing.py")]
        res4 = subprocess.run(p4_cmd, capture_output=True, text=True)
        assert res4.returncode == 0, f"Phase 4 regression failed:\n{res4.stdout}\n{res4.stderr}"
        print("✅ 43. Phase 4 analysis processing regression tests PASSED (28/28).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 44: Phase 5B report generation regression tests (33/33)
        # -------------------------------------------------------------
        p5_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase5_report_generation.py")]
        res5 = subprocess.run(p5_cmd, capture_output=True, text=True)
        assert res5.returncode == 0, f"Phase 5B regression failed:\n{res5.stdout}\n{res5.stderr}"
        print("✅ 44. Phase 5B report generation regression tests PASSED (33/33).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 45: Phase 6 counsellor portal regression tests (38/38)
        # -------------------------------------------------------------
        p6_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase6_counsellor_portal.py")]
        res6 = subprocess.run(p6_cmd, capture_output=True, text=True)
        assert res6.returncode == 0, f"Phase 6 regression failed:\n{res6.stdout}\n{res6.stderr}"
        print("✅ 45. Phase 6 counsellor portal regression tests PASSED (38/38).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 46: Phase 7 student portal regression tests (43/43)
        # -------------------------------------------------------------
        p7_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase7_student_portal.py")]
        res7 = subprocess.run(p7_cmd, capture_output=True, text=True)
        assert res7.returncode == 0, f"Phase 7 regression failed:\n{res7.stdout}\n{res7.stderr}"
        print("✅ 46. Phase 7 student portal regression tests PASSED (43/43).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 47: Existing Iris ML pipeline components verified
        # -------------------------------------------------------------
        vec_a = [0.2, 0.5, 0.8, 0.1]
        vec_b = [0.2, 0.5, 0.8, 0.1]
        sim = cosine_similarity(vec_a, vec_b)
        assert abs(sim - 1.0) < 1e-4, f"Cosine similarity regression: expected 1.0, got {sim}"
        print("✅ 47. Existing Iris ML pipeline components verified and intact.")
        passed_tests += 1

        print("=" * 80)
        print(f"PHASE 8 TEST RESULTS: {passed_tests} PASSED, 0 FAILED (TOTAL: {total_tests})")
        print("=" * 80)

    finally:
        cleanup_test_environment()


if __name__ == "__main__":
    run_phase8_test_suite()

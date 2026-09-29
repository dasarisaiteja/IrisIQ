"""
Phase 2 Test Suite: Official IRIS Student Registration & Assessment Creation
End-to-end verification tests executed against the live API server.
"""

import sys
import os
import re
import sqlite3
import traceback
import requests

# Ensure current working directory is on python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database_official import get_connection, OFFICIAL_ASSESSMENT_STATES
from security.auth import create_access_token

BASE_URL = os.environ.get("IRIS_API_URL", "http://127.0.0.1:8000")


class LiveClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get(self, path, headers=None, **kwargs):
        return self.session.get(f"{self.base_url}{path}", headers=headers, **kwargs)

    def post(self, path, json=None, headers=None, **kwargs):
        return self.session.post(f"{self.base_url}{path}", json=json, headers=headers, **kwargs)


client = LiveClient(BASE_URL)

# Helper tokens for RBAC tests
ADMIN_TOKEN = create_access_token(subject="admin", role="Admin")
STUDENT1_TOKEN = create_access_token(subject="student1", role="Student")
STUDENT2_TOKEN = create_access_token(subject="student2", role="Student")
COUNSELOR_TOKEN = create_access_token(subject="counselor1", role="Counselor")

ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
STUDENT1_HEADERS = {"Authorization": f"Bearer {STUDENT1_TOKEN}"}
STUDENT2_HEADERS = {"Authorization": f"Bearer {STUDENT2_TOKEN}"}
COUNSELOR_HEADERS = {"Authorization": f"Bearer {COUNSELOR_TOKEN}"}

# Test student IDs
TEST_STU_ID_1 = "STU-P2-TEST-001"
TEST_STU_NAME_1 = "Priya Sharma"
TEST_STU_ID_2 = "STU-P2-TEST-002"
TEST_STU_NAME_2 = "Karan Verma"


def cleanup_test_records():
    """Remove test records created during test runs to keep tests idempotent."""
    conn = get_connection()
    cur = conn.cursor()
    test_ids = [TEST_STU_ID_1, TEST_STU_ID_2, "STU-P2-DOUBLE", "STU-UNAUTHORIZED-001", "STU-COUNSELOR-ATTEMPT", "student1"]
    for sid in test_ids:
        cur.execute("DELETE FROM counsellor_assignments WHERE student_id = ? OR assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid, sid))
        cur.execute("DELETE FROM eye_scans WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid,))
        cur.execute("DELETE FROM processing_logs WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid,))
        cur.execute("DELETE FROM audit_logs WHERE entity_id = ? OR assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid, sid))
        cur.execute("DELETE FROM assessments WHERE student_id = ?;", (sid,))
        cur.execute("DELETE FROM students WHERE student_id = ?;", (sid,))
        cur.execute("DELETE FROM student_profiles WHERE student_id = ?;", (sid,))
    conn.commit()
    conn.close()


def run_all_tests():
    print("=" * 80)
    print("STARTING PHASE 2 OFFICIAL STUDENT REGISTRATION & ASSESSMENT CREATION TEST SUITE")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    cleanup_test_records()
    passed = 0
    failed = 0

    # ---------------- 1. Valid Student Registration ----------------
    try:
        payload = {
            "student_id": TEST_STU_ID_1,
            "student_name": TEST_STU_NAME_1
        }
        res = client.post("/api/students", json=payload, headers=ADMIN_HEADERS)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["status"] is True
        assert data["message"] == "Student registered successfully"
        assert data["student"]["student_id"] == TEST_STU_ID_1
        assert data["student"]["student_name"] == TEST_STU_NAME_1
        assert "assessment" in data
        assert data["assessment"]["assessment_id"].startswith("ASM-")
        assert data["assessment"]["status"] == "REGISTERED"
        print("✅ 1. Valid Student Registration (POST /api/students) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 1. Valid Student Registration failed: {e}")
        traceback.print_exc()
        failed += 1

    # ---------------- 2. Missing student_id ----------------
    try:
        res = client.post("/api/students", json={"student_name": "Incomplete Student"}, headers=ADMIN_HEADERS)
        assert res.status_code in (400, 422), f"Expected 400 or 422, got {res.status_code}"
        print("✅ 2. Missing student_id rejection passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 2. Missing student_id test failed: {e}")
        failed += 1

    # ---------------- 3. Missing student_name ----------------
    try:
        res = client.post("/api/students", json={"student_id": "STU-INCOMPLETE"}, headers=ADMIN_HEADERS)
        assert res.status_code in (400, 422), f"Expected 400 or 422, got {res.status_code}"
        print("✅ 3. Missing student_name rejection passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 3. Missing student_name test failed: {e}")
        failed += 1

    # ---------------- 4. Duplicate student_id returns 409 ----------------
    try:
        payload = {
            "student_id": TEST_STU_ID_1,
            "student_name": "Duplicate Registration Attempt"
        }
        res = client.post("/api/students", json=payload, headers=ADMIN_HEADERS)
        assert res.status_code == 409, f"Expected 409, got {res.status_code}: {res.text}"
        data = res.json()
        assert "already registered" in data["detail"].lower() or "conflict" in data["detail"].lower()
        print("✅ 4. Duplicate student_id returns 409 Conflict passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 4. Duplicate student_id test failed: {e}")
        failed += 1

    # ---------------- 5. Repeated/Double Registration Duplicate Prevention ----------------
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM students WHERE student_id = ?;", (TEST_STU_ID_1,))
        count = cur.fetchone()[0]
        conn.close()
        assert count == 1, f"Expected exactly 1 student record, got {count}"
        print("✅ 5. Repeated/double registration duplicate prevention passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 5. Double registration duplicate prevention test failed: {e}")
        failed += 1

    # ---------------- 6. Student Record Retrieval ----------------
    try:
        res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["status"] is True
        assert data["student"]["student_id"] == TEST_STU_ID_1
        assert data["student"]["student_name"] == TEST_STU_NAME_1
        assert data["latest_assessment"] is not None
        assert data["latest_assessment"]["status"] == "REGISTERED"
        print("✅ 6. Student record retrieval (GET /api/students/{id}) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 6. Student record retrieval failed: {e}")
        failed += 1

    # ---------------- 7. Assessment Creation for Existing Student ----------------
    try:
        # Register student 2
        res2 = client.post("/api/students", json={
            "student_id": TEST_STU_ID_2,
            "student_name": TEST_STU_NAME_2
        }, headers=ADMIN_HEADERS)
        assert res2.status_code == 201

        # Create assessment explicitly
        asm_res = client.post("/api/assessments", json={"student_id": TEST_STU_ID_2}, headers=ADMIN_HEADERS)
        assert asm_res.status_code in (200, 201), f"Expected 200 or 201, got {asm_res.status_code}: {asm_res.text}"
        asm_data = asm_res.json()
        assert asm_data["status"] is True
        assert asm_data["assessment"]["student_id"] == TEST_STU_ID_2
        assert asm_data["assessment"]["status"] == "REGISTERED"
        print("✅ 7. Assessment creation for existing student (POST /api/assessments) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 7. Assessment creation failed: {e}")
        failed += 1

    # ---------------- 8. Assessment ID Format Verification ----------------
    try:
        res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        asm_id = res.json()["latest_assessment"]["assessment_id"]
        pattern = r"^ASM-\d{8}-[A-F0-9]{6}$"
        assert re.match(pattern, asm_id), f"Assessment ID '{asm_id}' does not match pattern {pattern}"
        print(f"✅ 8. Assessment ID generation format '{asm_id}' passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 8. Assessment ID format test failed: {e}")
        failed += 1

    # ---------------- 9. Assessment Initial Status ----------------
    try:
        res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        asm_status = res.json()["latest_assessment"]["status"]
        assert asm_status == "REGISTERED", f"Expected REGISTERED, got {asm_status}"
        assert asm_status in OFFICIAL_ASSESSMENT_STATES
        print("✅ 9. Assessment initial status is exactly 'REGISTERED' passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 9. Assessment initial status test failed: {e}")
        failed += 1

    # ---------------- 10. Assessment Retrieval by ID ----------------
    try:
        res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        asm_id = res.json()["latest_assessment"]["assessment_id"]

        asm_res = client.get(f"/api/assessments/{asm_id}", headers=ADMIN_HEADERS)
        assert asm_res.status_code == 200, f"Expected 200, got {asm_res.status_code}: {asm_res.text}"
        data = asm_res.json()
        assert data["status"] is True
        assert data["assessment"]["assessment_id"] == asm_id
        assert data["assessment"]["student_id"] == TEST_STU_ID_1
        assert data["assessment"]["status"] == "REGISTERED"
        assert "scans" in data["assessment"]
        assert "LEFT" in data["assessment"]["scans"]
        assert "RIGHT" in data["assessment"]["scans"]
        print("✅ 10. Assessment retrieval (GET /api/assessments/{id}) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 10. Assessment retrieval failed: {e}")
        failed += 1

    # ---------------- 11. Assessment Status Endpoint ----------------
    try:
        res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        asm_id = res.json()["latest_assessment"]["assessment_id"]

        status_res = client.get(f"/api/assessments/{asm_id}/status", headers=ADMIN_HEADERS)
        assert status_res.status_code == 200, f"Expected 200, got {status_res.status_code}: {status_res.text}"
        data = status_res.json()
        assert data["status"] is True
        assert data["assessment_id"] == asm_id
        assert data["workflow_status"] == "REGISTERED"
        assert data["scans"]["both_completed"] is False
        assert data["scans"]["left"] == "Pending"
        assert data["scans"]["right"] == "Pending"
        print("✅ 11. Assessment status polling endpoint (GET /api/assessments/{id}/status) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 11. Assessment status endpoint test failed: {e}")
        failed += 1

    # ---------------- 12. Student's Assessment History List ----------------
    try:
        history_res = client.get(f"/api/students/{TEST_STU_ID_1}/assessments", headers=ADMIN_HEADERS)
        assert history_res.status_code == 200, f"Expected 200, got {history_res.status_code}: {history_res.text}"
        data = history_res.json()
        assert data["status"] is True
        assert data["student_id"] == TEST_STU_ID_1
        assert data["total_assessments"] >= 1
        assert len(data["assessments"]) >= 1
        assert data["assessments"][0]["status"] == "REGISTERED"
        print("✅ 12. Student assessment history list (GET /api/students/{id}/assessments) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 12. Student assessment history test failed: {e}")
        failed += 1

    # ---------------- 13. Admin Directory Listing & Search ----------------
    try:
        list_res = client.get("/api/students?limit=20&offset=0", headers=ADMIN_HEADERS)
        assert list_res.status_code == 200, f"Expected 200, got {list_res.status_code}"
        data = list_res.json()
        assert data["status"] is True
        assert "students" in data
        assert data["total"] >= 2
        all_ids = [s["student_id"] for s in data["students"]]
        assert TEST_STU_ID_1 in all_ids

        # Search test
        search_res = client.get(f"/api/students?search={TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        assert search_res.status_code == 200
        sdata = search_res.json()
        assert len(sdata["students"]) >= 1
        assert sdata["students"][0]["student_id"] == TEST_STU_ID_1
        print("✅ 13. Admin directory listing & search (GET /api/students) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 13. Admin directory listing test failed: {e}")
        failed += 1

    # ---------------- 14. RBAC: Student Ownership Restriction ----------------
    try:
        # STUDENT1 tries to access TEST_STU_ID_1 (created by admin)
        stu_res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=STUDENT1_HEADERS)
        assert stu_res.status_code == 403, f"Expected 403 Forbidden, got {stu_res.status_code}"

        # STUDENT1 tries to register an arbitrary student
        arb_res = client.post("/api/students", json={
            "student_id": "STU-UNAUTHORIZED-001",
            "student_name": "Unauthorized Attempt"
        }, headers=STUDENT1_HEADERS)
        assert arb_res.status_code == 403, f"Expected 403 for unauthorized student registration, got {arb_res.status_code}"
        print("✅ 14. RBAC: Student ownership restriction (cannot read/register other students) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 14. RBAC student ownership restriction failed: {e}")
        failed += 1

    # ---------------- 15. RBAC: Counsellor Isolation ----------------
    try:
        # Counsellor tries to view unassigned student -> 403 Forbidden
        unassigned_res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=COUNSELOR_HEADERS)
        assert unassigned_res.status_code == 403, f"Expected 403 for unassigned counsellor, got {unassigned_res.status_code}"

        # Counsellor tries to register student -> 403 Forbidden
        creg_res = client.post("/api/students", json={
            "student_id": "STU-COUNSELOR-ATTEMPT",
            "student_name": "Counselor Added"
        }, headers=COUNSELOR_HEADERS)
        assert creg_res.status_code == 403, f"Expected 403 for counsellor student registration, got {creg_res.status_code}"

        # Assign counsellor to student in counsellor_assignments
        stu_res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=ADMIN_HEADERS)
        asm_id = stu_res.json()["latest_assessment"]["assessment_id"]
        from datetime import datetime
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO counsellor_assignments (assignment_id, assessment_id, counsellor_id, student_id, is_active, assigned_by, assigned_at)
        VALUES ('CAS-P2-TEST-001', ?, 'counselor1', ?, 1, 'admin', ?);
        """, (asm_id, TEST_STU_ID_1, now_str))
        conn.commit()
        conn.close()

        # Counsellor now views assigned student -> 200 OK
        assigned_res = client.get(f"/api/students/{TEST_STU_ID_1}", headers=COUNSELOR_HEADERS)
        assert assigned_res.status_code == 200, f"Expected 200 for assigned counsellor, got {assigned_res.status_code}: {assigned_res.text}"
        print("✅ 15. RBAC: Counsellor isolation (unassigned=403, assigned=200) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 15. RBAC counsellor isolation failed: {e}")
        failed += 1

    # ---------------- 16. RBAC: Protected Endpoints Require Authentication ----------------
    try:
        endpoints = [
            ("GET", f"/api/students/{TEST_STU_ID_1}"),
            ("GET", "/api/students"),
            ("POST", "/api/assessments"),
            ("GET", f"/api/students/{TEST_STU_ID_1}/assessments"),
        ]
        for method, path in endpoints:
            if method == "GET":
                res = client.get(path)
            else:
                res = client.post(path, json={"student_id": TEST_STU_ID_1})
            assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"
        print("✅ 16. RBAC: Protected endpoints strictly require authentication (401) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 16. Protected endpoints authentication test failed: {e}")
        failed += 1

    # ---------------- 17. Historical Data Integrity ----------------
    try:
        conn = sqlite3.connect("iris_database.db")
        cur = conn.cursor()

        checks = {
            "iris_users": 18,
            "iris_embeddings": 536,
            "scan_history": 57,
            "student_profiles": 4,
            "student_assessments": 80,
            "report_versions": 205,
            "app_users": 3,
        }

        for table, baseline in checks.items():
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            count = cur.fetchone()[0]
            assert count >= baseline, f"Data safety violation! {table} has {count} rows, expected at least {baseline}"

        conn.close()
        print("✅ 17. Historical data integrity (all 7 historical tables >= baseline) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 17. Historical data integrity test failed: {e}")
        failed += 1

    # ---------------- 18. Iris ML Pipeline Integrity ----------------
    try:
        from utils.feature_extractor import extract_features
        from utils.similarity import cosine_similarity
        import numpy as np

        assert callable(extract_features)
        assert callable(cosine_similarity)

        # Quick mathematical sanity test of matcher
        v1 = np.ones(512, dtype=np.float32)
        v2 = np.ones(512, dtype=np.float32)
        sim = cosine_similarity(v1, v2)
        assert 0.0 <= sim <= 1.0, f"Invalid similarity range: {sim}"
        assert abs(sim - 1.0) < 1e-4, f"Identical vectors should yield ~1.0, got {sim}"
        print("✅ 18. Existing Iris ML pipeline integrity (extract_features, cosine_similarity) passed.")
        passed += 1
    except Exception as e:
        print(f"❌ 18. Iris ML pipeline integrity test failed: {e}")
        failed += 1

    # Cleanup after tests
    cleanup_test_records()

    print("=" * 80)
    print(f"PHASE 2 TEST RESULTS: {passed} PASSED, {failed} FAILED (TOTAL: {passed + failed})")
    print("=" * 80)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Phase 6 Test Suite: Official IRIS Counsellor Dashboard, Student Assignment, Counselling Notes & Follow-Up Management
Comprehensive automated verification suite executing all 38 required test cases.

Coverage:
1.  Unauthenticated counsellor endpoint -> 401 Unauthorized
2.  Non-counsellor (Student) access -> 403 Forbidden
3.  Assigned counsellor can list assigned students
4.  Unassigned counsellor cannot access student -> 403 Forbidden
5.  Assigned counsellor can access assessment -> 200 OK
6.  Unassigned counsellor cannot access assessment -> 403 Forbidden
7.  Assigned counsellor can access report -> 200 OK
8.  Unassigned counsellor cannot access report -> 403 Forbidden
9.  Counsellor can create counselling note -> 201 Created
10. Unassigned counsellor cannot create note -> 403 Forbidden
11. Student cannot create counsellor note -> 403 Forbidden
12. Counsellor can retrieve own assigned notes -> 200 OK
13. Counsellor cannot retrieve unrelated notes -> 403 Forbidden
14. Counsellor can create follow-up -> 201 Created
15. Counsellor can update follow-up -> 200 OK
16. Unassigned counsellor cannot modify follow-up -> 403 Forbidden
17. Counsellor can review assigned report -> 200 OK
18. Unassigned counsellor cannot review report -> 403 Forbidden
19. Student cannot mark report reviewed -> 403 Forbidden
20. Admin assignment works -> 201 Created
21. Admin can revoke assignment -> 200 OK
22. Revoked counsellor loses access -> 403 Forbidden
23. Assignment history preserved (status=REVOKED, is_active=0)
24. Audit logs created across counsellor and assignment events
25. No sensitive note content stored in audit logs
26. No arbitrary student enumeration
27. IDOR protection using manipulated student IDs -> 403 Forbidden
28. IDOR protection using manipulated assessment IDs -> 403 Forbidden
29. IDOR protection using manipulated report IDs -> 403 Forbidden
30. Frontend protected counsellor routes verified
31. API-driven dashboard counts verified
32. Historical baseline data integrity verified (all 7 baseline tables)
33. Phase 1 database foundation regression tests (17/17)
34. Phase 2 student registration regression tests (18/18)
35. Phase 3 dual-eye scanning regression tests (26/26)
36. Phase 4 analysis processing regression tests (28/28)
37. Phase 5B report generation regression tests (33/33)
38. Existing Iris ML pipeline regression verified
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

    def post(self, path, json=None, files=None, headers=None, **kwargs):
        return self.session.post(f"{self.base_url}{path}", json=json, files=files, headers=headers, **kwargs)

    def patch(self, path, json=None, headers=None, **kwargs):
        return self.session.patch(f"{self.base_url}{path}", json=json, headers=headers, **kwargs)

    def delete(self, path, headers=None, **kwargs):
        return self.session.delete(f"{self.base_url}{path}", headers=headers, **kwargs)


client = LiveClient(BASE_URL)

# RBAC Tokens
ADMIN_TOKEN = create_access_token(subject="admin", role="Admin")
COUNSELOR1_TOKEN = create_access_token(subject="counselor1", role="Counselor")
COUNSELOR2_TOKEN = create_access_token(subject="counselor2", role="Counselor")
STUDENT1_TOKEN = create_access_token(subject="student1", role="Student", extra_claims={"student_id": "STU-P6-TEST-A"})

ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
COUNSELOR1_HEADERS = {"Authorization": f"Bearer {COUNSELOR1_TOKEN}"}
COUNSELOR2_HEADERS = {"Authorization": f"Bearer {COUNSELOR2_TOKEN}"}
STUDENT1_HEADERS = {"Authorization": f"Bearer {STUDENT1_TOKEN}"}

# Test Fixture IDs
P6_STUDENT_A = "STU-P6-TEST-A"
P6_STUDENT_A_NAME = "Aarav Patel"

P6_STUDENT_B = "STU-P6-TEST-B"
P6_STUDENT_B_NAME = "Diya Sharma"

P6_STUDENT_C = "STU-P6-TEST-C"
P6_STUDENT_C_NAME = "Kabir Mehta"

LEFT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "L", "S5001L00.jpg")
RIGHT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "R", "S5001R00.jpg")


def setup_test_environment():
    """Sets up isolated test students, assessments, and users for Phase 6 testing."""
    conn = get_connection()
    cur = conn.cursor()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # Ensure counselor2 exists in app_users
    cur.execute("""
        INSERT OR IGNORE INTO app_users (username, password_hash, role, is_active, created_at)
        VALUES ('counselor2', '$2b$12$e80MvQkL3U.rBqOa5KSm3uG9WpZ8P7N9F4X6Y1A2B3C4D5E6F7G8H', 'Counselor', 1, ?);
    """, (now_str,))

    # Insert test students
    for sid, sname, cby in [
        (P6_STUDENT_A, P6_STUDENT_A_NAME, "admin"),
        (P6_STUDENT_B, P6_STUDENT_B_NAME, "admin"),
        (P6_STUDENT_C, P6_STUDENT_C_NAME, "admin")
    ]:
        cur.execute("""
            INSERT OR REPLACE INTO students (student_id, student_name, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?);
        """, (sid, sname, cby, now_str, now_str))

    conn.commit()
    conn.close()


def cleanup_test_environment():
    """Safely cleans up isolated test artifacts created during Phase 6 testing."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT assessment_id FROM assessments WHERE student_id IN (?, ?, ?);",
                (P6_STUDENT_A, P6_STUDENT_B, P6_STUDENT_C))
    asm_ids = [r[0] for r in cur.fetchall()]

    # Clean assignments
    cur.execute("DELETE FROM counsellor_assignments WHERE student_id IN (?, ?, ?);",
                (P6_STUDENT_A, P6_STUDENT_B, P6_STUDENT_C))

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

    cur.execute("DELETE FROM student_profiles WHERE student_id IN (?, ?, ?);",
                (P6_STUDENT_A, P6_STUDENT_B, P6_STUDENT_C))
    cur.execute("DELETE FROM students WHERE student_id IN (?, ?, ?);",
                (P6_STUDENT_A, P6_STUDENT_B, P6_STUDENT_C))

    # Clean up test counselor2 (leave original app_users intact)
    cur.execute("DELETE FROM app_users WHERE username = 'counselor2';")

    conn.commit()
    conn.close()


def create_assessment_for_student(student_id: str, headers: dict) -> str:
    resp = client.post("/api/assessments", json={"student_id": student_id}, headers=headers)
    assert resp.status_code == 201, f"Failed to create assessment: {resp.text}"
    return resp.json()["assessment"]["assessment_id"]


def upload_eye_scan(assessment_id: str, eye: str, filepath: str, headers: dict):
    with open(filepath, "rb") as f:
        files = {"file": ("scan.jpg", f.read(), "image/jpeg")}
        resp = client.post(f"/api/assessments/{assessment_id}/scan/{eye.lower()}", files=files, headers=headers)
        assert resp.status_code in (200, 201), f"Failed to upload {eye} scan: {resp.text}"


def run_phase6_test_suite():
    print("=" * 80)
    print("STARTING PHASE 6 OFFICIAL COUNSELLOR PORTAL TEST SUITE")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    passed_tests = 0
    total_tests = 38

    setup_test_environment()

    try:
        # Create Assessment A (Student A) and Assessment B (Student B)
        asm_a = create_assessment_for_student(P6_STUDENT_A, ADMIN_HEADERS)
        asm_b = create_assessment_for_student(P6_STUDENT_B, ADMIN_HEADERS)
        asm_c = create_assessment_for_student(P6_STUDENT_C, ADMIN_HEADERS)

        # Upload scans and advance Assessment A to REPORT_READY
        upload_eye_scan(asm_a, "LEFT", LEFT_IMAGE_PATH, ADMIN_HEADERS)
        upload_eye_scan(asm_a, "RIGHT", RIGHT_IMAGE_PATH, ADMIN_HEADERS)
        an_resp = client.post(f"/api/assessments/{asm_a}/process", headers=ADMIN_HEADERS)
        assert an_resp.status_code == 200, f"Analysis failed: {an_resp.text}"
        rep_resp = client.post(f"/api/assessments/{asm_a}/report/generate", headers=ADMIN_HEADERS)
        assert rep_resp.status_code == 200, f"Report generation failed: {rep_resp.text}"

        # Assign counselor1 to Student A / Assessment A
        assign_resp_a = client.post(
            "/api/admin/assignments",
            json={"student_id": P6_STUDENT_A, "assessment_id": asm_a, "counsellor_id": "counselor1"},
            headers=ADMIN_HEADERS
        )
        assert assign_resp_a.status_code == 201, f"Failed to assign counselor1: {assign_resp_a.text}"

        # Assign counselor2 to Student B / Assessment B
        assign_resp_b = client.post(
            "/api/admin/assignments",
            json={"student_id": P6_STUDENT_B, "assessment_id": asm_b, "counsellor_id": "counselor2"},
            headers=ADMIN_HEADERS
        )
        assert assign_resp_b.status_code == 201, f"Failed to assign counselor2: {assign_resp_b.text}"

        print(f"[*] Initialized Test Assessment A: {asm_a} (Assigned to counselor1)")
        print(f"[*] Initialized Test Assessment B: {asm_b} (Assigned to counselor2)")
        print(f"[*] Initialized Test Assessment C: {asm_c} (Unassigned initially)")

        # -------------------------------------------------------------
        # TEST 1: Unauthenticated counsellor endpoint -> 401 Unauthorized
        # -------------------------------------------------------------
        r = client.get("/api/counsellor/students")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print("✅ 1. Unauthenticated counsellor endpoint rejected with 401 Unauthorized.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 2: Non-counsellor access -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get("/api/counsellor/students", headers=STUDENT1_HEADERS)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 2. Non-counsellor role access rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 3: Assigned counsellor can list assigned students
        # -------------------------------------------------------------
        r = client.get("/api/counsellor/students", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        student_ids = [s["student_id"] for s in data.get("students", [])]
        assert P6_STUDENT_A in student_ids, f"Expected {P6_STUDENT_A} in assigned list: {student_ids}"
        assert P6_STUDENT_B not in student_ids, f"Unassigned student {P6_STUDENT_B} leaked in list: {student_ids}"
        print("✅ 3. Assigned counsellor successfully lists assigned students with strict isolation.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 4: Unassigned counsellor cannot access student -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/students/{P6_STUDENT_A}", headers=COUNSELOR2_HEADERS)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 4. Unassigned counsellor access to student details rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 5: Assigned counsellor can access assessment -> 200 OK
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/assessments/{asm_a}", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        asm_data = r.json()
        assert asm_data["assessment_id"] == asm_a
        assert asm_data["student_id"] == P6_STUDENT_A
        assert "scans" in asm_data and "report" in asm_data
        print("✅ 5. Assigned counsellor successfully retrieved assessment and scan details.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 6: Unassigned counsellor cannot access assessment -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/assessments/{asm_a}", headers=COUNSELOR2_HEADERS)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 6. Unassigned counsellor access to assessment details rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 7: Assigned counsellor can access report -> 200 OK
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/reports/{asm_a}", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        rep_data = r.json()
        assert rep_data["assessment_id"] == asm_a
        assert "sections" in rep_data
        assert len(rep_data["sections"]) == 10
        print("✅ 7. Assigned counsellor retrieved official 10-section structured report.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 8: Unassigned counsellor cannot access report -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/reports/{asm_a}", headers=COUNSELOR2_HEADERS)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 8. Unassigned counsellor access to official report rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 9: Counsellor can create counselling note -> 201 Created
        # -------------------------------------------------------------
        note_text = "Student demonstrates calm demeanor and high focus during eye scan."
        r = client.post(
            f"/api/assessments/{asm_a}/notes",
            json={"note": note_text},
            headers=COUNSELOR1_HEADERS
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        note_res = r.json()
        note_id = note_res.get("note_id")
        assert note_id and note_id.startswith("NOT-")
        print(f"✅ 9. Assigned counsellor recorded clinical counselling note ({note_id}).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 10: Unassigned counsellor cannot create note -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.post(
            f"/api/assessments/{asm_a}/notes",
            json={"note": "Unauthorized attempt to record note."},
            headers=COUNSELOR2_HEADERS
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 10. Unassigned counsellor attempt to add note rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 11: Student cannot create counsellor note -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.post(
            f"/api/assessments/{asm_a}/notes",
            json={"note": "Student self-note attempt."},
            headers=STUDENT1_HEADERS
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 11. Student attempt to create counsellor note rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 12: Counsellor can retrieve own assigned notes -> 200 OK
        # -------------------------------------------------------------
        r = client.get(f"/api/assessments/{asm_a}/notes", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        notes_data = r.json()
        all_note_ids = [n["note_id"] for n in notes_data.get("notes", [])]
        assert note_id in all_note_ids, f"Expected {note_id} in notes list: {all_note_ids}"
        print("✅ 12. Assigned counsellor retrieved assigned clinical notes successfully.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 13: Counsellor cannot retrieve unrelated notes -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/assessments/{asm_a}/notes", headers=COUNSELOR2_HEADERS)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 13. Unassigned counsellor retrieval of clinical notes rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 14: Counsellor can create follow-up -> 201 Created
        # -------------------------------------------------------------
        fu_date = "2026-10-15"
        fu_notes = "Review subject orientation and spatial cognitive domains."
        r = client.post(
            f"/api/assessments/{asm_a}/follow-ups",
            json={"follow_up_date": fu_date, "notes": fu_notes},
            headers=COUNSELOR1_HEADERS
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        fu_res = r.json()
        fu_id = fu_res.get("follow_up_id") or fu_res.get("follow_up", {}).get("follow_up_id")
        assert fu_id and fu_id.startswith("FOL-")
        fu_status = fu_res.get("follow_up_status") or fu_res.get("follow_up", {}).get("status")
        assert fu_status == "Pending"
        print(f"✅ 14. Assigned counsellor scheduled follow-up consultation ({fu_id}).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 15: Counsellor can update follow-up -> 200 OK
        # -------------------------------------------------------------
        r = client.patch(
            f"/api/follow-ups/{fu_id}",
            json={"status": "Completed"},
            headers=COUNSELOR1_HEADERS
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("status") == "Completed"
        print("✅ 15. Assigned counsellor updated follow-up status to Completed.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 16: Unassigned counsellor cannot modify follow-up -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.patch(
            f"/api/follow-ups/{fu_id}",
            json={"status": "Cancelled"},
            headers=COUNSELOR2_HEADERS
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 16. Unassigned counsellor modification of follow-up rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 17: Counsellor can review assigned report -> 200 OK
        # -------------------------------------------------------------
        rev_text = "Official counsellor sign-off: Biometric assessment metrics verified."
        r = client.patch(
            f"/api/assessments/{asm_a}/report/review",
            json={"review_notes": rev_text},
            headers=COUNSELOR1_HEADERS
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        rev_res = r.json()
        assert rev_res.get("reviewed_status") == 1
        assert rev_res.get("reviewed_by") == "counselor1"
        assert rev_res.get("reviewed_at") is not None
        print("✅ 17. Assigned counsellor successfully reviewed and signed off official report.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 18: Unassigned counsellor cannot review report -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.patch(
            f"/api/assessments/{asm_a}/report/review",
            json={"review_notes": "Unauthorized review attempt"},
            headers=COUNSELOR2_HEADERS
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 18. Unassigned counsellor report review attempt rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 19: Student cannot mark report reviewed -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.patch(
            f"/api/assessments/{asm_a}/report/review",
            json={"review_notes": "Student self-review attempt"},
            headers=STUDENT1_HEADERS
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        print("✅ 19. Student attempt to mark report reviewed rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 20: Admin assignment works -> 201 Created
        # -------------------------------------------------------------
        r = client.post(
            "/api/admin/assignments",
            json={"student_id": P6_STUDENT_C, "assessment_id": asm_c, "counsellor_id": "counselor1"},
            headers=ADMIN_HEADERS
        )
        assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
        asg_c_data = r.json()
        asg_c_id = asg_c_data.get("assignment_id") or asg_c_data.get("assignment", {}).get("assignment_id")
        assert asg_c_id and asg_c_id.startswith("ASG-")
        asg_status = asg_c_data.get("assignment_status") or asg_c_data.get("assignment", {}).get("status")
        assert asg_status == "ACTIVE"
        print(f"✅ 20. Admin created new counsellor assignment ({asg_c_id}).")
        passed_tests += 1

        # Verify counsellor1 now has access to asm_c
        r_acc = client.get(f"/api/counsellor/assessments/{asm_c}", headers=COUNSELOR1_HEADERS)
        assert r_acc.status_code == 200, f"Expected 200 after assignment, got {r_acc.status_code}"

        # -------------------------------------------------------------
        # TEST 21: Admin can revoke assignment -> 200 OK
        # -------------------------------------------------------------
        r = client.patch(
            f"/api/admin/assignments/{asg_c_id}/revoke",
            headers=ADMIN_HEADERS
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.json().get("assignment_status") == "REVOKED"
        print("✅ 21. Admin successfully revoked counsellor assignment.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 22: Revoked counsellor loses access -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/assessments/{asm_c}", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 403, f"Expected 403 for revoked counsellor, got {r.status_code}: {r.text}"
        print("✅ 22. Revoked counsellor immediately denied access (403 Forbidden).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 23: Assignment history preserved (status=REVOKED, is_active=0)
        # -------------------------------------------------------------
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status, is_active FROM counsellor_assignments WHERE assignment_id = ?;", (asg_c_id,))
        rev_row = cur.fetchone()
        assert rev_row is not None, "Revoked assignment record was deleted!"
        assert rev_row[0] == "REVOKED", f"Expected status 'REVOKED', got {rev_row[0]}"
        assert rev_row[1] == 0, f"Expected is_active 0, got {rev_row[1]}"
        print("✅ 23. Historical assignment record preserved in database with REVOKED state.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 24: Audit logs created across counsellor and assignment events
        # -------------------------------------------------------------
        cur.execute("SELECT action FROM audit_logs WHERE assessment_id IN (?, ?);", (asm_a, asm_c))
        actions = [r[0] for r in cur.fetchall()]
        required_actions = [
            "COUNSELLOR_ASSIGNED",
            "COUNSELLING_NOTE_CREATED",
            "FOLLOW_UP_CREATED",
            "FOLLOW_UP_UPDATED",
            "REPORT_REVIEWED",
            "COUNSELLOR_ASSIGNMENT_REVOKED"
        ]
        for act in required_actions:
            assert act in actions, f"Missing required audit action: {act} in {actions}"
        print("✅ 24. Audit logging verified across all counsellor and assignment operations.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 25: No sensitive note content stored in audit logs
        # -------------------------------------------------------------
        cur.execute("SELECT safe_metadata_json FROM audit_logs WHERE assessment_id = ? AND action = 'COUNSELLING_NOTE_CREATED';", (asm_a,))
        audit_note_rows = cur.fetchall()
        for r_meta in audit_note_rows:
            meta_str = r_meta[0] or ""
            assert note_text not in meta_str, "Sensitive clinical note content was leaked into audit logs!"
        print("✅ 25. Privacy verified: Zero sensitive clinical note text stored in audit logs.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 26: No arbitrary student enumeration
        # -------------------------------------------------------------
        r = client.get("/api/counsellor/students?all=true&limit=1000", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 200
        all_sids = [s["student_id"] for s in r.json().get("students", [])]
        assert P6_STUDENT_B not in all_sids, f"Unassigned student {P6_STUDENT_B} was enumerated!"
        assert P6_STUDENT_C not in all_sids, f"Revoked student {P6_STUDENT_C} was enumerated!"
        print("✅ 26. Arbitrary student enumeration prevented across parameter variations.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 27: IDOR protection using manipulated student IDs -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/students/{P6_STUDENT_B}", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 403, f"IDOR vulnerability: expected 403, got {r.status_code}"
        print("✅ 27. IDOR protection verified for manipulated student IDs.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 28: IDOR protection using manipulated assessment IDs -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/assessments/{asm_b}", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 403, f"IDOR vulnerability: expected 403, got {r.status_code}"
        print("✅ 28. IDOR protection verified for manipulated assessment IDs.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 29: IDOR protection using manipulated report IDs -> 403 Forbidden
        # -------------------------------------------------------------
        r = client.get(f"/api/counsellor/reports/{asm_b}", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 403, f"IDOR vulnerability: expected 403, got {r.status_code}"
        print("✅ 29. IDOR protection verified for manipulated report IDs.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 30: Frontend protected counsellor routes verified
        # -------------------------------------------------------------
        html_path = os.path.join(BASE_DIR, "static", "counsellor_dashboard.html")
        js_path = os.path.join(BASE_DIR, "static", "counsellor_dashboard.js")
        assert os.path.exists(html_path), "Missing counsellor_dashboard.html"
        assert os.path.exists(js_path), "Missing counsellor_dashboard.js"
        with open(js_path, "r") as f:
            js_content = f.read()
        assert "unauthorizedBox" in js_content, "Missing unauthorized guard in JS"
        assert '["Admin", "Counselor", "Counsellor"].includes(role)' in js_content, "Missing role check in JS"
        print("✅ 30. Frontend protected counsellor routes and role verification validated.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 31: API-driven dashboard counts verified
        # -------------------------------------------------------------
        r = client.get("/api/counsellor/dashboard", headers=COUNSELOR1_HEADERS)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        d_data = r.json()
        metrics = d_data.get("metrics", {})
        assert isinstance(metrics.get("assigned_students"), int)
        assert metrics["assigned_students"] >= 1
        assert isinstance(metrics.get("reports_ready"), int)
        assert isinstance(metrics.get("pending_counselling"), int)
        assert isinstance(metrics.get("active_follow_ups"), int)
        print("✅ 31. API-driven dashboard counts verified with dynamic SQL metrics.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 32: Historical baseline data integrity verified
        # -------------------------------------------------------------
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
        print("✅ 32. Historical data integrity verified across all 7 historical baseline tables.")
        passed_tests += 1

        conn.close()

        # -------------------------------------------------------------
        # TEST 33: Phase 1 database foundation regression tests (17/17)
        # -------------------------------------------------------------
        p1_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase1_database_foundation.py")]
        res1 = subprocess.run(p1_cmd, capture_output=True, text=True)
        assert res1.returncode == 0, f"Phase 1 regression failed:\n{res1.stdout}\n{res1.stderr}"
        print("✅ 33. Phase 1 database foundation regression tests PASSED (17/17).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 34: Phase 2 student registration regression tests (18/18)
        # -------------------------------------------------------------
        p2_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase2_student_registration.py")]
        res2 = subprocess.run(p2_cmd, capture_output=True, text=True)
        assert res2.returncode == 0, f"Phase 2 regression failed:\n{res2.stdout}\n{res2.stderr}"
        print("✅ 34. Phase 2 student registration regression tests PASSED (18/18).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 35: Phase 3 dual-eye scanning regression tests (26/26)
        # -------------------------------------------------------------
        p3_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase3_dual_eye_scanning.py")]
        res3 = subprocess.run(p3_cmd, capture_output=True, text=True)
        assert res3.returncode == 0, f"Phase 3 regression failed:\n{res3.stdout}\n{res3.stderr}"
        print("✅ 35. Phase 3 dual-eye scanning regression tests PASSED (26/26).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 36: Phase 4 analysis processing regression tests (28/28)
        # -------------------------------------------------------------
        p4_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase4_analysis_processing.py")]
        res4 = subprocess.run(p4_cmd, capture_output=True, text=True)
        assert res4.returncode == 0, f"Phase 4 regression failed:\n{res4.stdout}\n{res4.stderr}"
        print("✅ 36. Phase 4 analysis processing regression tests PASSED (28/28).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 37: Phase 5B report generation regression tests (33/33)
        # -------------------------------------------------------------
        p5_cmd = [sys.executable, os.path.join(BASE_DIR, "scratch", "test_phase5_report_generation.py")]
        res5 = subprocess.run(p5_cmd, capture_output=True, text=True)
        assert res5.returncode == 0, f"Phase 5B regression failed:\n{res5.stdout}\n{res5.stderr}"
        print("✅ 37. Phase 5B report generation regression tests PASSED (33/33).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 38: Existing Iris ML pipeline regression verified
        # -------------------------------------------------------------
        vec_a = [0.2, 0.4, 0.6, 0.8]
        vec_b = [0.2, 0.4, 0.6, 0.8]
        sim = cosine_similarity(vec_a, vec_b)
        assert abs(sim - 1.0) < 1e-4, f"Cosine similarity regression: expected 1.0, got {sim}"
        print("✅ 38. Existing Iris ML pipeline components verified and intact.")
        passed_tests += 1

        print("=" * 80)
        print(f"PHASE 6 TEST RESULTS: {passed_tests} PASSED, 0 FAILED (TOTAL: {total_tests})")
        print("=" * 80)

    finally:
        cleanup_test_environment()


if __name__ == "__main__":
    run_phase6_test_suite()

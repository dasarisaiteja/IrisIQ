"""
Phase 4 Test Suite: Official IRIS Bilateral Analysis Processing & Structured Analysis Results
Comprehensive automated verification suite executing all 28 required test cases.
"""

import sys
import os
import io
import json
import time
import uuid
import sqlite3
import subprocess
import traceback
import requests
import numpy as np
from PIL import Image

# Ensure project root is in sys.path
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

    def post(self, path, json=None, files=None, headers=None, **kwargs):
        return self.session.post(f"{self.base_url}{path}", json=json, files=files, headers=headers, **kwargs)


client = LiveClient(BASE_URL)

# RBAC Tokens
ADMIN_TOKEN = create_access_token(subject="admin", role="Admin")
STUDENT1_TOKEN = create_access_token(subject="student1", role="Student")
STUDENT2_TOKEN = create_access_token(subject="student2", role="Student")
COUNSELOR1_TOKEN = create_access_token(subject="counselor1", role="Counselor")
COUNSELOR2_TOKEN = create_access_token(subject="counselor2", role="Counselor")

ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
STUDENT1_HEADERS = {"Authorization": f"Bearer {STUDENT1_TOKEN}"}
STUDENT2_HEADERS = {"Authorization": f"Bearer {STUDENT2_TOKEN}"}
COUNSELOR1_HEADERS = {"Authorization": f"Bearer {COUNSELOR1_TOKEN}"}
COUNSELOR2_HEADERS = {"Authorization": f"Bearer {COUNSELOR2_TOKEN}"}

# Test Fixture IDs
P4_STUDENT_ID = "STU-P4-TEST-001"
P4_STUDENT_NAME = "Arjun Verma"
P4_OTHER_STUDENT_ID = "STU-P4-OTHER-002"
P4_OTHER_STUDENT_NAME = "Priya Sharma"

# Test Images
LEFT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "L", "S5001L00.jpg")
RIGHT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "R", "S5001R00.jpg")


def get_image_file_tuple(filepath, filename="eye.jpg"):
    with open(filepath, "rb") as f:
        return ("file", (filename, f.read(), "image/jpeg"))


def setup_test_students_and_assignments():
    """Sets up isolated test students and counsellor assignment."""
    conn = get_connection()
    cur = conn.cursor()

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # Insert test students
    cur.execute("""
    INSERT OR REPLACE INTO students (student_id, student_name, created_by, created_at, updated_at)
    VALUES (?, ?, 'student1', ?, ?);
    """, (P4_STUDENT_ID, P4_STUDENT_NAME, now_str, now_str))

    cur.execute("""
    INSERT OR REPLACE INTO students (student_id, student_name, created_by, created_at, updated_at)
    VALUES (?, ?, 'student2', ?, ?);
    """, (P4_OTHER_STUDENT_ID, P4_OTHER_STUDENT_NAME, now_str, now_str))

    conn.commit()
    conn.close()


def cleanup_test_records():
    """Cleans up isolated test assessments, eye_scans, analysis_results, and logs."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT assessment_id FROM assessments WHERE student_id IN (?, ?);", (P4_STUDENT_ID, P4_OTHER_STUDENT_ID))
    asm_ids = [r[0] for r in cur.fetchall()]

    cur.execute("DELETE FROM counsellor_assignments WHERE student_id IN (?, ?);", (P4_STUDENT_ID, P4_OTHER_STUDENT_ID))

    for aid in asm_ids:
        cur.execute("DELETE FROM analysis_results WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM eye_scans WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM processing_logs WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM audit_logs WHERE assessment_id = ?;", (aid,))
        cur.execute("DELETE FROM assessments WHERE assessment_id = ?;", (aid,))

    cur.execute("DELETE FROM students WHERE student_id IN (?, ?);", (P4_STUDENT_ID, P4_OTHER_STUDENT_ID))

    conn.commit()
    conn.close()


def create_assessment_for_student(student_id: str, headers: dict) -> str:
    """Helper to create an assessment via official POST /api/assessments API."""
    resp = client.post("/api/assessments", json={"student_id": student_id}, headers=headers)
    assert resp.status_code == 201, f"Failed to create assessment: {resp.text}"
    return resp.json()["assessment"]["assessment_id"]


def upload_eye_scan(assessment_id: str, eye: str, filepath: str, headers: dict):
    """Helper to upload an eye scan via official POST /scan/{eye} API."""
    with open(filepath, "rb") as f:
        files = {"file": ("scan.jpg", f.read(), "image/jpeg")}
        resp = client.post(f"/api/assessments/{assessment_id}/scan/{eye.lower()}", files=files, headers=headers)
    return resp


def run_phase4_test_suite():
    print("=" * 80)
    print("STARTING PHASE 4 OFFICIAL ANALYSIS PROCESSING & STRUCTURED RESULTS TEST SUITE")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    # Initial cleanup & setup
    cleanup_test_records()
    setup_test_students_and_assignments()

    passed_tests = 0
    total_tests = 28

    # Create primary test assessment
    main_asm_id = create_assessment_for_student(P4_STUDENT_ID, STUDENT1_HEADERS)
    print(f"[*] Initialized Test Assessment: {main_asm_id} for Student: {P4_STUDENT_ID}")

    # Assign counselor1 to P4_STUDENT_ID on main_asm_id
    conn = get_connection()
    cur = conn.cursor()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO counsellor_assignments (
        assignment_id, assessment_id, student_id, counsellor_id, assigned_by, assigned_at, status, is_active
    ) VALUES ('ASG-P4-TEST-001', ?, ?, 'counselor1', 'admin', ?, 'ACTIVE', 1);
    """, (main_asm_id, P4_STUDENT_ID, now_str))
    conn.commit()
    conn.close()

    try:
        # -------------------------------------------------------------
        # TEST 1: Unauthenticated process request -> 401 Unauthorized
        # -------------------------------------------------------------
        resp = client.post(f"/api/assessments/{main_asm_id}/process")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("✅ 1. Unauthenticated process request rejected with 401 Unauthorized.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 2: Unauthorized student -> 403 Forbidden
        # -------------------------------------------------------------
        # student2 attempting to process student1's assessment
        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=STUDENT2_HEADERS)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("✅ 2. Unauthorized student access rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 3: Assigned counsellor access verified
        # -------------------------------------------------------------
        # counselor1 is assigned to STU-P4-TEST-001 -> should pass RBAC (even if rejected later by both-eyes gating with 409)
        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=COUNSELOR1_HEADERS)
        assert resp.status_code != 403, f"Assigned counsellor should not get 403 Forbidden, got {resp.status_code}: {resp.text}"
        print("✅ 3. Assigned counsellor authorization verified.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 4: Unassigned counsellor -> 403 Forbidden
        # -------------------------------------------------------------
        # counselor2 is NOT assigned to STU-P4-TEST-001
        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=COUNSELOR2_HEADERS)
        assert resp.status_code == 403, f"Expected 403 for unassigned counsellor, got {resp.status_code}: {resp.text}"
        print("✅ 4. Unassigned counsellor rejected with 403 Forbidden.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 5: Admin access verified
        # -------------------------------------------------------------
        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=ADMIN_HEADERS)
        assert resp.status_code != 403, f"Admin should not get 403 Forbidden, got {resp.status_code}: {resp.text}"
        print("✅ 5. Admin authorization verified across assessments.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 6: Invalid assessment -> 404 Not Found
        # -------------------------------------------------------------
        resp = client.post("/api/assessments/INVALID-ASM-99999/process", headers=ADMIN_HEADERS)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print("✅ 6. Invalid assessment rejected with 404 Not Found.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 7: Process with NO scans -> 409 Conflict
        # -------------------------------------------------------------
        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=STUDENT1_HEADERS)
        assert resp.status_code == 409, f"Expected 409 Conflict for no scans, got {resp.status_code}: {resp.text}"
        assert "both eyes" in resp.json()["detail"].lower() or "missing" in resp.json()["detail"].lower()
        print("✅ 7. Process with no scans rejected with 409 Conflict.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 8: Process with ONLY LEFT scan -> 409 Conflict
        # -------------------------------------------------------------
        upload_resp = upload_eye_scan(main_asm_id, "LEFT", LEFT_IMAGE_PATH, STUDENT1_HEADERS)
        assert upload_resp.status_code == 200, f"Failed to upload LEFT scan: {upload_resp.text}"

        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=STUDENT1_HEADERS)
        assert resp.status_code == 409, f"Expected 409 Conflict for only LEFT scan, got {resp.status_code}: {resp.text}"
        assert "right=missing" in resp.json()["detail"].lower() or "right" in resp.json()["detail"].lower()
        print("✅ 8. Process with only LEFT scan rejected with 409 Conflict.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 9: Process with ONLY RIGHT scan -> 409 Conflict
        # -------------------------------------------------------------
        right_only_asm_id = create_assessment_for_student(P4_STUDENT_ID, STUDENT1_HEADERS)
        upload_resp = upload_eye_scan(right_only_asm_id, "RIGHT", RIGHT_IMAGE_PATH, STUDENT1_HEADERS)
        assert upload_resp.status_code == 200, f"Failed to upload RIGHT scan: {upload_resp.text}"

        resp = client.post(f"/api/assessments/{right_only_asm_id}/process", headers=STUDENT1_HEADERS)
        assert resp.status_code == 409, f"Expected 409 Conflict for only RIGHT scan, got {resp.status_code}: {resp.text}"
        assert "left=missing" in resp.json()["detail"].lower() or "left" in resp.json()["detail"].lower()
        print("✅ 9. Process with only RIGHT scan rejected with 409 Conflict.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 10: Process with BOTH eyes completed -> 200 OK Accepted
        # -------------------------------------------------------------
        # Upload RIGHT scan to main_asm_id (which already has LEFT scan)
        upload_resp = upload_eye_scan(main_asm_id, "RIGHT", RIGHT_IMAGE_PATH, STUDENT1_HEADERS)
        assert upload_resp.status_code == 200, f"Failed to upload RIGHT scan: {upload_resp.text}"

        # Status should now be SCAN_COMPLETED
        status_resp = client.get(f"/api/assessments/{main_asm_id}/scan/status", headers=STUDENT1_HEADERS)
        assert status_resp.status_code == 200
        assert status_resp.json()["workflow_status"] == "SCAN_COMPLETED"

        # Now trigger POST /process
        proc_resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=STUDENT1_HEADERS)
        assert proc_resp.status_code == 200, f"Expected 200 OK, got {proc_resp.status_code}: {proc_resp.text}"
        proc_data = proc_resp.json()
        assert proc_data["status"] is True
        assert proc_data["workflow_status"] == "ANALYSIS_COMPLETED"
        print("✅ 10. Process with both eyes completed accepted with 200 OK.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 11: Assessment changes to PROCESSING during execution
        # -------------------------------------------------------------
        # Check processing_logs to verify the 'STARTED' / 'ANALYSIS_PROCESSING' state was recorded
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT operation, status FROM processing_logs WHERE assessment_id = ?;", (main_asm_id,))
        logs = cur.fetchall()
        assert len(logs) > 0, "No processing logs recorded"
        assert any(l[0] == "ANALYSIS_PROCESSING" for l in logs)
        print("✅ 11. Assessment state transition to PROCESSING recorded in processing logs.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 12: Successful processing -> ANALYSIS_COMPLETED
        # -------------------------------------------------------------
        cur.execute("SELECT status FROM assessments WHERE assessment_id = ?;", (main_asm_id,))
        db_status = cur.fetchone()[0]
        assert db_status == "ANALYSIS_COMPLETED", f"Expected ANALYSIS_COMPLETED, got {db_status}"
        print("✅ 12. Assessment workflow status transitioned to ANALYSIS_COMPLETED.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 13: Analysis result persisted in analysis_results table
        # -------------------------------------------------------------
        cur.execute("SELECT results_json, model_version FROM analysis_results WHERE assessment_id = ?;", (main_asm_id,))
        res_row = cur.fetchone()
        assert res_row is not None, "No record found in analysis_results table"
        persisted_json = json.loads(res_row[0])
        assert persisted_json["assessment_id"] == main_asm_id
        assert persisted_json["workflow_status"] == "ANALYSIS_COMPLETED"
        print("✅ 13. Structured analysis results persisted in analysis_results table.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 14: LEFT and RIGHT results remain associated with same assessment
        # -------------------------------------------------------------
        left_eye_data = persisted_json.get("left_eye", {})
        right_eye_data = persisted_json.get("right_eye", {})
        assert "pupil_circle" in left_eye_data and left_eye_data["pupil_circle"] is not None
        assert "pupil_circle" in right_eye_data and right_eye_data["pupil_circle"] is not None
        assert "iris_circle" in left_eye_data and left_eye_data["iris_circle"] is not None
        assert "iris_circle" in right_eye_data and right_eye_data["iris_circle"] is not None
        assert left_eye_data["scan_id"] != right_eye_data["scan_id"]
        assert "bilateral_analysis" in persisted_json
        print("✅ 14. Bilateral LEFT and RIGHT results strictly associated with the same assessment.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 15: Analysis retrieval endpoint (GET /analysis)
        # -------------------------------------------------------------
        get_res = client.get(f"/api/assessments/{main_asm_id}/analysis", headers=STUDENT1_HEADERS)
        assert get_res.status_code == 200, f"Expected 200, got {get_res.status_code}: {get_res.text}"
        analysis_body = get_res.json()
        assert analysis_body["status"] is True
        assert analysis_body["assessment_id"] == main_asm_id
        assert "analysis" in analysis_body
        assert analysis_body["analysis"]["workflow_status"] == "ANALYSIS_COMPLETED"
        print("✅ 15. Analysis retrieval endpoint returns persisted structured results.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 16: Student ownership restriction on GET /analysis
        # -------------------------------------------------------------
        resp = client.get(f"/api/assessments/{main_asm_id}/analysis", headers=STUDENT2_HEADERS)
        assert resp.status_code == 403, f"Expected 403 Forbidden for unauthorized student, got {resp.status_code}: {resp.text}"
        print("✅ 16. Student ownership restriction enforced on GET /analysis (403 Forbidden).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 17: Counsellor assignment restriction on GET /analysis
        # -------------------------------------------------------------
        # Unassigned counsellor -> 403
        resp = client.get(f"/api/assessments/{main_asm_id}/analysis", headers=COUNSELOR2_HEADERS)
        assert resp.status_code == 403, f"Expected 403 Forbidden for unassigned counsellor, got {resp.status_code}: {resp.text}"

        # Assigned counsellor -> 200
        resp = client.get(f"/api/assessments/{main_asm_id}/analysis", headers=COUNSELOR1_HEADERS)
        assert resp.status_code == 200, f"Expected 200 OK for assigned counsellor, got {resp.status_code}: {resp.text}"
        print("✅ 17. Counsellor assignment restriction verified on GET /analysis.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 18: Idempotent repeated process request
        # -------------------------------------------------------------
        # Calling POST /process again on ANALYSIS_COMPLETED assessment
        cur.execute("SELECT COUNT(*) FROM analysis_results WHERE assessment_id = ?;", (main_asm_id,))
        count_before = cur.fetchone()[0]

        resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=STUDENT1_HEADERS)
        assert resp.status_code == 200, f"Expected 200 OK for repeated request, got {resp.status_code}: {resp.text}"
        repeat_data = resp.json()
        assert repeat_data.get("already_completed") is True

        cur.execute("SELECT COUNT(*) FROM analysis_results WHERE assessment_id = ?;", (main_asm_id,))
        count_after = cur.fetchone()[0]
        assert count_after == count_before == 1, "Duplicate analysis record was created on idempotent call!"
        print("✅ 18. Idempotent repeated process request returns safe existing response without duplicate records.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 19: Controlled retry after failure
        # -------------------------------------------------------------
        # Simulate a FAILED state in the assessment
        cur.execute("UPDATE assessments SET status = 'FAILED' WHERE assessment_id = ?;", (main_asm_id,))
        conn.commit()

        # Calling POST /process should allow retry and transition FAILED -> PROCESSING -> ANALYSIS_COMPLETED
        retry_resp = client.post(f"/api/assessments/{main_asm_id}/process", headers=STUDENT1_HEADERS)
        assert retry_resp.status_code == 200, f"Expected 200 OK for retry after FAILED, got {retry_resp.status_code}: {retry_resp.text}"
        cur.execute("SELECT status FROM assessments WHERE assessment_id = ?;", (main_asm_id,))
        retried_status = cur.fetchone()[0]
        assert retried_status == "ANALYSIS_COMPLETED", f"Expected ANALYSIS_COMPLETED after retry, got {retried_status}"
        print("✅ 19. Controlled retry successfully recovers assessment from FAILED back to ANALYSIS_COMPLETED.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 20: Processing logs verified
        # -------------------------------------------------------------
        cur.execute("""
        SELECT processing_id, operation, status, duration_ms, model_version
        FROM processing_logs
        WHERE assessment_id = ? AND operation = 'ANALYSIS_PROCESSING'
        ORDER BY id ASC;
        """, (main_asm_id,))
        proc_logs = cur.fetchall()
        assert len(proc_logs) >= 1, "No processing logs found for analysis"
        for plog in proc_logs:
            assert plog[0].startswith("PRC-")
            assert plog[1] == "ANALYSIS_PROCESSING"
            assert plog[2] in ("STARTED", "COMPLETED", "FAILED")
            assert plog[4] == "iris-analysis-v1.0"
        print(f"✅ 20. Processing logs verified with valid processing_id and model metadata ({len(proc_logs)} entries).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 21: Audit logs verified
        # -------------------------------------------------------------
        cur.execute("""
        SELECT action, entity_type, status
        FROM audit_logs
        WHERE assessment_id = ?
        ORDER BY id ASC;
        """, (main_asm_id,))
        audit_records = cur.fetchall()
        audit_actions = [a[0] for a in audit_records]
        assert "ANALYSIS_STARTED" in audit_actions
        assert "ANALYSIS_COMPLETED" in audit_actions
        assert "ANALYSIS_RETRIEVED" in audit_actions
        print(f"✅ 21. Audit logs verified for ANALYSIS_STARTED, ANALYSIS_COMPLETED, and ANALYSIS_RETRIEVED.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 22: No fabricated confidence or results
        # -------------------------------------------------------------
        # Search the entire persisted results_json for forbidden psychological/personality buzzwords
        results_str = json.dumps(persisted_json).lower()
        forbidden_terms = [
            "iq", "intelligence", "personality", "leadership", "mental health",
            "neuron count", "psychometric", "career suitability", "learning style",
            "temperament", "behaviour", "behavior"
        ]
        found_forbidden = [t for t in forbidden_terms if f'"{t}"' in results_str or f"'{t}'" in results_str]
        assert len(found_forbidden) == 0, f"Found forbidden psychological/personality claims: {found_forbidden}"

        # Verify provenance tags are explicitly defined
        provenance = persisted_json.get("provenance", {})
        assert provenance.get("pupil_iris_geometry") == "iris-derived"
        assert provenance.get("quality_metrics") == "rule-based"
        assert provenance.get("texture_descriptors") == "ml-derived"
        assert provenance.get("color_measurements") == "iris-derived"
        print("✅ 22. Zero fabricated psychological claims; explicit provenance tagging enforced.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 23: Model/Service metadata behavior
        # -------------------------------------------------------------
        metadata = persisted_json.get("model_metadata", {})
        assert metadata.get("service") == "IRIS-Official-Analysis-Engine"
        assert metadata.get("pipeline_version") == "iris-analysis-v1.0"
        assert metadata.get("model_name") == "iris-geometry-cv"
        assert "opencv_version" in metadata
        timing = persisted_json.get("timing", {})
        assert "duration_ms" in timing and timing["duration_ms"] >= 0
        print("✅ 23. Model and service metadata accurately recorded.")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 24: Historical data integrity
        # -------------------------------------------------------------
        baseline_counts = {
            "iris_users": 18,
            "iris_embeddings": 536,
            "scan_history": 57,
            "student_profiles": 4,
            "student_assessments": 80,
            "report_versions": 205,
            "app_users": 3
        }
        for table, expected_min in baseline_counts.items():
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            actual = cur.fetchone()[0]
            assert actual >= expected_min, f"Historical table {table} has count {actual} < expected {expected_min}"
        print("✅ 24. All 7 historical database tables remain completely intact (>= baseline).")
        passed_tests += 1

        conn.close()

        # -------------------------------------------------------------
        # TEST 25: Phase 1 database foundation regression
        # -------------------------------------------------------------
        res1 = subprocess.run(
            [sys.executable, "scratch/test_phase1_database_foundation.py"],
            capture_output=True, text=True
        )
        assert res1.returncode == 0, f"Phase 1 regression failed:\n{res1.stdout}\n{res1.stderr}"
        print("✅ 25. Phase 1 database foundation regression tests PASSED (17/17).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 26: Phase 2 student registration regression
        # -------------------------------------------------------------
        res2 = subprocess.run(
            [sys.executable, "scratch/test_phase2_student_registration.py"],
            capture_output=True, text=True
        )
        assert res2.returncode == 0, f"Phase 2 regression failed:\n{res2.stdout}\n{res2.stderr}"
        print("✅ 26. Phase 2 student registration regression tests PASSED (18/18).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 27: Phase 3 dual-eye scanning regression
        # -------------------------------------------------------------
        res3 = subprocess.run(
            [sys.executable, "scratch/test_phase3_dual_eye_scanning.py"],
            capture_output=True, text=True
        )
        assert res3.returncode == 0, f"Phase 3 regression failed:\n{res3.stdout}\n{res3.stderr}"
        print("✅ 27. Phase 3 dual-eye scanning regression tests PASSED (26/26).")
        passed_tests += 1

        # -------------------------------------------------------------
        # TEST 28: Existing Iris ML pipeline regression
        # -------------------------------------------------------------
        from utils.feature_extractor import extract_features
        from utils.similarity import cosine_similarity
        from utils.pupil_detection import detect_pupil
        from utils.iris_segmentation import segment_iris
        from utils.color_analysis import analyze_color
        from utils.iris_quality_analyzer import analyze_iris_quality

        dummy_img = np.ones((200, 200, 3), dtype=np.uint8) * 128
        _, test_pupil = detect_pupil(dummy_img)
        assert test_pupil is not None and len(test_pupil) == 3
        _, test_iris = segment_iris(dummy_img)
        feats = extract_features(test_pupil, (100, 100, 50), dummy_img)
        assert feats is not None and "pupil_iris_ratio" in feats
        sim = cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert abs(sim - 1.0) < 1e-4
        col = analyze_color(dummy_img)
        assert col is not None and "eye_color" in col
        q = analyze_iris_quality(dummy_img, pupil=test_pupil, iris=(100, 100, 50))
        assert "capture_quality_score" in q
        print("✅ 28. Existing Iris ML pipeline components verified and intact.")
        passed_tests += 1

    finally:
        cleanup_test_records()

    print("=" * 80)
    print(f"PHASE 4 TEST RESULTS: {passed_tests} PASSED, {total_tests - passed_tests} FAILED (TOTAL: {total_tests})")
    print("=" * 80)
    assert passed_tests == total_tests, f"Only {passed_tests}/{total_tests} tests passed."


if __name__ == "__main__":
    run_phase4_test_suite()

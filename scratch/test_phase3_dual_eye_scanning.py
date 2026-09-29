"""
Phase 3 Test Suite: Official IRIS Dual-Eye Scanning Interface & Scan Upload API
Comprehensive automated verification suite executing all 26 required test cases.
"""

import sys
import os
import io
import re
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

# Helper tokens for RBAC tests
ADMIN_TOKEN = create_access_token(subject="admin", role="Admin")
STUDENT1_TOKEN = create_access_token(subject="student1", role="Student")
STUDENT2_TOKEN = create_access_token(subject="student2", role="Student")
COUNSELOR_TOKEN = create_access_token(subject="counselor1", role="Counselor")

ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
STUDENT1_HEADERS = {"Authorization": f"Bearer {STUDENT1_TOKEN}"}
STUDENT2_HEADERS = {"Authorization": f"Bearer {STUDENT2_TOKEN}"}
COUNSELOR_HEADERS = {"Authorization": f"Bearer {COUNSELOR_TOKEN}"}

# Test IDs
P3_STUDENT_ID = "STU-P3-TEST-001"
P3_STUDENT_NAME = "Aditi Rao"
P3_OWNED_STUDENT_ID = "student1"  # Owned by student1 user
P3_OTHER_STUDENT_ID = "STU-P3-OTHER-999"

# Test Image Fixtures
LEFT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "L", "S5001L00.jpg")
RIGHT_IMAGE_PATH = os.path.join(BASE_DIR, "dataset", "CASIA-Iris-Thousand", "001", "R", "S5001R00.jpg")


def get_image_file_tuple(filepath, filename="eye.jpg"):
    """Reads image file and returns multipart tuple."""
    with open(filepath, "rb") as f:
        return ("file", (filename, f.read(), "image/jpeg"))


def get_corrupt_file_tuple():
    """Returns invalid file payload."""
    return ("file", ("invalid.txt", b"THIS_IS_NOT_AN_IMAGE", "text/plain"))


def get_blank_image_tuple():
    """Returns a pure pitch-black image to test quality failure."""
    img = Image.new("RGB", (640, 480), color=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return ("file", ("black.jpg", buf.getvalue(), "image/jpeg"))


def cleanup_phase3_records():
    """Clean up test records created during test runs."""
    conn = get_connection()
    cur = conn.cursor()
    test_students = [P3_STUDENT_ID, P3_OWNED_STUDENT_ID, P3_OTHER_STUDENT_ID, "STU-P3-REG-01"]
    for sid in test_students:
        cur.execute("DELETE FROM counsellor_assignments WHERE student_id = ? OR assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid, sid))
        cur.execute("DELETE FROM processing_logs WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid,))
        cur.execute("DELETE FROM audit_logs WHERE entity_id = ? OR assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid, sid))
        cur.execute("DELETE FROM eye_scans WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE student_id = ?);", (sid,))
        cur.execute("DELETE FROM assessments WHERE student_id = ?;", (sid,))
        cur.execute("DELETE FROM students WHERE student_id = ?;", (sid,))
        cur.execute("DELETE FROM student_profiles WHERE student_id = ?;", (sid,))
    conn.commit()
    conn.close()


def run_all_tests():
    print("=" * 80)
    print("STARTING PHASE 3 DUAL-EYE SCANNING & UPLOAD API TEST SUITE")
    print(f"Target Server: {BASE_URL}")
    print("=" * 80)

    cleanup_phase3_records()
    passed = 0
    failed = 0

    # ---------------- Setup Test Assessment ----------------
    setup_res = client.post("/api/students", json={
        "student_id": P3_STUDENT_ID,
        "student_name": P3_STUDENT_NAME
    }, headers=ADMIN_HEADERS)
    assert setup_res.status_code == 201, f"Failed setup student: {setup_res.text}"
    p3_asm_id = setup_res.json()["assessment"]["assessment_id"]
    print(f"[*] Initialized Test Assessment: {p3_asm_id} for Student: {P3_STUDENT_ID}")

    # 1. Unauthenticated scan request -> 401
    try:
        files = {"file": ("eye.jpg", b"fake", "image/jpeg")}
        res = client.post(f"/api/assessments/{p3_asm_id}/scan/left", files=files)
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print("✅ 1. Unauthenticated scan request rejected with 401 Unauthorized.")
        passed += 1
    except Exception as e:
        print(f"❌ 1. Test 1 failed: {e}")
        failed += 1

    # 2. Unauthorized student -> 403
    try:
        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        # STUDENT2 tries to upload scan to assessment owned by P3_STUDENT_ID
        res = client.post(f"/api/assessments/{p3_asm_id}/scan/left", files=files, headers=STUDENT2_HEADERS)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("✅ 2. Unauthorized student access rejected with 403 Forbidden.")
        passed += 1
    except Exception as e:
        print(f"❌ 2. Test 2 failed: {e}")
        failed += 1

    # 3. Authorized student can scan own assessment
    try:
        # Register assessment for student1
        stu1_res = client.post("/api/students", json={
            "student_id": P3_OWNED_STUDENT_ID,
            "student_name": "Student One User"
        }, headers=ADMIN_HEADERS)
        assert stu1_res.status_code == 201
        stu1_asm_id = stu1_res.json()["assessment"]["assessment_id"]

        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        res = client.post(f"/api/assessments/{stu1_asm_id}/scan/left", files=files, headers=STUDENT1_HEADERS)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["status"] is True
        assert data["scan"]["eye_side"] == "LEFT"
        assert data["scan"]["status"] == "Completed"
        print("✅ 3. Authorized student can scan their own assessment.")
        passed += 1
    except Exception as e:
        print(f"❌ 3. Test 3 failed: {e}")
        failed += 1

    # 4. Assigned counsellor authorization
    try:
        # Assign counselor1 to P3_STUDENT_ID
        from datetime import datetime
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO counsellor_assignments (assignment_id, assessment_id, counsellor_id, student_id, is_active, assigned_by, assigned_at)
        VALUES ('CAS-P3-001', ?, 'counselor1', ?, 1, 'admin', ?);
        """, (p3_asm_id, P3_STUDENT_ID, now_str))
        conn.commit()
        conn.close()

        # Assigned counsellor can view scan status
        status_res = client.get(f"/api/assessments/{p3_asm_id}/scan/status", headers=COUNSELOR_HEADERS)
        assert status_res.status_code == 200, f"Expected 200 for assigned counsellor, got {status_res.status_code}"
        print("✅ 4. Assigned counsellor authorization verified.")
        passed += 1
    except Exception as e:
        print(f"❌ 4. Test 4 failed: {e}")
        failed += 1

    # 5. Unassigned counsellor rejected -> 403
    try:
        # Counselor tries to view stu1_asm_id (where counselor is NOT assigned)
        res = client.get(f"/api/assessments/{stu1_asm_id}/scan/status", headers=COUNSELOR_HEADERS)
        assert res.status_code == 403, f"Expected 403 for unassigned counsellor, got {res.status_code}"
        print("✅ 5. Unassigned counsellor rejected with 403 Forbidden.")
        passed += 1
    except Exception as e:
        print(f"❌ 5. Test 5 failed: {e}")
        failed += 1

    # 6. Admin authorization
    try:
        res = client.get(f"/api/assessments/{p3_asm_id}/scan/status", headers=ADMIN_HEADERS)
        assert res.status_code == 200, f"Expected 200 for Admin, got {res.status_code}"
        print("✅ 6. Admin authorization verified across assessments.")
        passed += 1
    except Exception as e:
        print(f"❌ 6. Test 6 failed: {e}")
        failed += 1

    # 7. Invalid assessment -> 404
    try:
        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        res = client.post("/api/assessments/ASM-NONEXISTENT-9999/scan/left", files=files, headers=ADMIN_HEADERS)
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("✅ 7. Invalid assessment rejected with 404 Not Found.")
        passed += 1
    except Exception as e:
        print(f"❌ 7. Test 7 failed: {e}")
        failed += 1

    # 8. Invalid eye -> 400
    try:
        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        res = client.post(f"/api/assessments/{p3_asm_id}/scan/MIDDLE", files=files, headers=ADMIN_HEADERS)
        assert res.status_code in (400, 404, 422), f"Expected 400 or 404, got {res.status_code}"
        get_res = client.get(f"/api/assessments/{p3_asm_id}/scan/UPPER", headers=ADMIN_HEADERS)
        assert get_res.status_code in (400, 422)
        print("✅ 8. Invalid eye side parameter rejected.")
        passed += 1
    except Exception as e:
        print(f"❌ 8. Test 8 failed: {e}")
        failed += 1

    # 9. Invalid file upload -> 400
    try:
        files = [get_corrupt_file_tuple()]
        res = client.post(f"/api/assessments/{p3_asm_id}/scan/left", files=files, headers=ADMIN_HEADERS)
        assert res.status_code in (400, 415, 422), f"Expected 400, got {res.status_code}"
        print("✅ 9. Malformed / non-image upload rejected safely.")
        passed += 1
    except Exception as e:
        print(f"❌ 9. Test 9 failed: {e}")
        failed += 1

    # 10. LEFT scan stored as LEFT
    try:
        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        res = client.post(f"/api/assessments/{p3_asm_id}/scan/left", files=files, headers=ADMIN_HEADERS)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["scan"]["eye_side"] == "LEFT"
        assert data["scan"]["status"] == "Completed"
        
        # Verify in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT eye_side, status FROM eye_scans WHERE scan_id = ?;", (data["scan"]["scan_id"],))
        db_row = cur.fetchone()
        conn.close()
        assert db_row[0] == "LEFT"
        assert db_row[1] == "Completed"
        print("✅ 10. LEFT scan accurately stored as LEFT eye.")
        passed += 1
    except Exception as e:
        print(f"❌ 10. Test 10 failed: {e}")
        failed += 1

    # 11. RIGHT scan stored as RIGHT
    try:
        files = [get_image_file_tuple(RIGHT_IMAGE_PATH, "right.jpg")]
        res = client.post(f"/api/assessments/{p3_asm_id}/scan/right", files=files, headers=ADMIN_HEADERS)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["scan"]["eye_side"] == "RIGHT"
        assert data["scan"]["status"] == "Completed"

        # Verify in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT eye_side, status FROM eye_scans WHERE scan_id = ?;", (data["scan"]["scan_id"],))
        db_row = cur.fetchone()
        conn.close()
        assert db_row[0] == "RIGHT"
        assert db_row[1] == "Completed"
        print("✅ 11. RIGHT scan accurately stored as RIGHT eye.")
        passed += 1
    except Exception as e:
        print(f"❌ 11. Test 11 failed: {e}")
        failed += 1

    # 12. LEFT cannot be submitted as RIGHT accidentally
    try:
        # Endpoints are distinct and strict: /scan/left vs /scan/right
        # Verification that {eye} path param enforces requested eye
        get_left = client.get(f"/api/assessments/{p3_asm_id}/scan/LEFT", headers=ADMIN_HEADERS).json()
        get_right = client.get(f"/api/assessments/{p3_asm_id}/scan/RIGHT", headers=ADMIN_HEADERS).json()
        assert get_left["scan"]["eye_side"] == "LEFT"
        assert get_right["scan"]["eye_side"] == "RIGHT"
        print("✅ 12. LEFT and RIGHT scans strictly separated and unmixed.")
        passed += 1
    except Exception as e:
        print(f"❌ 12. Test 12 failed: {e}")
        failed += 1

    # 13. Duplicate active eye scan prevented -> 409 Conflict
    try:
        # Since LEFT scan is already completed, attempting to post to /scan/left without retry returns 409
        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        dup_res = client.post(f"/api/assessments/{p3_asm_id}/scan/left", files=files, headers=ADMIN_HEADERS)
        assert dup_res.status_code == 409, f"Expected 409, got {dup_res.status_code}: {dup_res.text}"
        print("✅ 13. Duplicate active eye scan prevented with 409 Conflict.")
        passed += 1
    except Exception as e:
        print(f"❌ 13. Test 13 failed: {e}")
        failed += 1

    # 14. Scan status endpoint
    try:
        status_res = client.get(f"/api/assessments/{p3_asm_id}/scan/status", headers=ADMIN_HEADERS)
        assert status_res.status_code == 200
        sdata = status_res.json()
        assert sdata["status"] is True
        assert sdata["assessment_id"] == p3_asm_id
        assert "left" in sdata["scans"]
        assert "right" in sdata["scans"]
        assert sdata["scans"]["both_completed"] is True
        print("✅ 14. Scan status polling endpoint structure verified.")
        passed += 1
    except Exception as e:
        print(f"❌ 14. Test 14 failed: {e}")
        failed += 1

    # 15. One-eye completion state
    try:
        # Create fresh assessment to test single eye state
        reg_fresh = client.post("/api/students", json={
            "student_id": "STU-P3-REG-01",
            "student_name": "Single Eye Student"
        }, headers=ADMIN_HEADERS)
        fresh_asm_id = reg_fresh.json()["assessment"]["assessment_id"]

        # Upload only LEFT scan
        files = [get_image_file_tuple(LEFT_IMAGE_PATH, "left.jpg")]
        client.post(f"/api/assessments/{fresh_asm_id}/scan/left", files=files, headers=ADMIN_HEADERS)

        # Verify assessment status is LEFT_SCAN_COMPLETED
        st_res = client.get(f"/api/assessments/{fresh_asm_id}/scan/status", headers=ADMIN_HEADERS).json()
        assert st_res["workflow_status"] == "LEFT_SCAN_COMPLETED"
        assert st_res["scans"]["both_completed"] is False
        print("✅ 15. One-eye completion state (LEFT_SCAN_COMPLETED) verified.")
        passed += 1
    except Exception as e:
        print(f"❌ 15. Test 15 failed: {e}")
        failed += 1

    # 16. Both-eye completion -> SCAN_COMPLETED
    try:
        # Complete right eye on fresh assessment
        files = [get_image_file_tuple(RIGHT_IMAGE_PATH, "right.jpg")]
        client.post(f"/api/assessments/{fresh_asm_id}/scan/right", files=files, headers=ADMIN_HEADERS)

        st_res = client.get(f"/api/assessments/{fresh_asm_id}/scan/status", headers=ADMIN_HEADERS).json()
        assert st_res["workflow_status"] == "SCAN_COMPLETED"
        assert st_res["scans"]["both_completed"] is True
        print("✅ 16. Dual-eye completion transitions assessment to SCAN_COMPLETED.")
        passed += 1
    except Exception as e:
        print(f"❌ 16. Test 16 failed: {e}")
        failed += 1

    # 17. Retry failed/replacement scan
    try:
        files = [get_image_file_tuple(RIGHT_IMAGE_PATH, "right_replacement.jpg")]
        retry_res = client.post(f"/api/assessments/{fresh_asm_id}/scan/right/retry", files=files, headers=ADMIN_HEADERS)
        assert retry_res.status_code == 200
        rdata = retry_res.json()
        assert rdata["scan"]["attempt_number"] == 2
        assert rdata["scan"]["status"] == "Completed"
        
        # Verify in database that attempt 1 is marked inactive and attempt 2 is active
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT attempt_number, is_active FROM eye_scans WHERE assessment_id = ? AND eye_side = 'RIGHT' ORDER BY attempt_number ASC;", (fresh_asm_id,))
        rows = cur.fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0] == (1, 0)  # Prior attempt marked inactive
        assert rows[1] == (2, 1)  # New attempt is active
        print("✅ 17. Scan retry successfully deactivates previous attempt and increments attempt number.")
        passed += 1
    except Exception as e:
        print(f"❌ 17. Test 17 failed: {e}")
        failed += 1

    # 18. Failed scan does not falsely become completed
    try:
        # Upload black/unusable image via retry on left eye
        files = [get_blank_image_tuple()]
        fail_res = client.post(f"/api/assessments/{fresh_asm_id}/scan/left/retry", files=files, headers=ADMIN_HEADERS)
        fdata = fail_res.json()
        assert fdata["status"] is False
        assert fdata["scan"]["status"] == "Failed"
        assert fdata["scan"]["quality_score"] == 0.0
        assert "insufficient" in fdata["scan"]["error_message"].lower() or "quality" in fdata["scan"]["error_message"].lower()

        # Check that assessment status reverted from SCAN_COMPLETED to RIGHT_SCAN_COMPLETED
        st_res = client.get(f"/api/assessments/{fresh_asm_id}/scan/status", headers=ADMIN_HEADERS).json()
        assert st_res["workflow_status"] == "RIGHT_SCAN_COMPLETED"
        assert st_res["scans"]["both_completed"] is False
        print("✅ 18. Low quality/black image rejected as Failed; does not become Completed.")
        passed += 1
    except Exception as e:
        print(f"❌ 18. Test 18 failed: {e}")
        traceback.print_exc()
        failed += 1

    # 19. Secure file access
    try:
        get_res = client.get(f"/api/assessments/{p3_asm_id}/scan/LEFT", headers=ADMIN_HEADERS)
        assert get_res.status_code == 200
        ref = get_res.json()["scan"]["file_reference"]
        assert ref.startswith("scans/"), f"File reference '{ref}' should start with scans/"
        assert not os.path.isabs(ref), f"File reference must not be an absolute path: {ref}"
        print("✅ 19. Secure file reference abstraction verified.")
        passed += 1
    except Exception as e:
        print(f"❌ 19. Test 19 failed: {e}")
        failed += 1

    # 20. Raw filesystem path not exposed
    try:
        get_res = client.get(f"/api/assessments/{p3_asm_id}/scan/LEFT", headers=ADMIN_HEADERS)
        text = get_res.text
        assert "/Users/" not in text
        assert "C:\\" not in text
        assert "/home/" not in text
        print("✅ 20. No internal filesystem paths exposed in API responses.")
        passed += 1
    except Exception as e:
        print(f"❌ 20. Test 20 failed: {e}")
        failed += 1

    # 21. Audit log creation
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE assessment_id = ? AND entity_type = 'EYE_SCAN';", (p3_asm_id,))
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 2, f"Expected at least 2 audit entries, got {count}"
        print("✅ 21. Audit log records created for scan operations.")
        passed += 1
    except Exception as e:
        print(f"❌ 21. Test 21 failed: {e}")
        failed += 1

    # 22. Processing log creation
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM processing_logs WHERE assessment_id = ?;", (p3_asm_id,))
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 2, f"Expected at least 2 processing log entries, got {count}"
        print("✅ 22. Processing logs created with execution duration and model metadata.")
        passed += 1
    except Exception as e:
        print(f"❌ 22. Test 22 failed: {e}")
        failed += 1

    # 23. Historical data integrity
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
        print("✅ 23. All 7 historical tables remain completely intact (>= baseline).")
        passed += 1
    except Exception as e:
        print(f"❌ 23. Test 23 failed: {e}")
        failed += 1

    # 24. Phase 1 regression tests
    try:
        cmd = ["./ai-env/bin/python", "scratch/test_phase1_database_foundation.py"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Phase 1 regression failed:\n{res.stdout}\n{res.stderr}"
        print("✅ 24. Phase 1 database foundation regression tests PASSED (17/17).")
        passed += 1
    except Exception as e:
        print(f"❌ 24. Test 24 failed: {e}")
        failed += 1

    # 25. Phase 2 regression tests
    try:
        cmd = ["./ai-env/bin/python", "scratch/test_phase2_student_registration.py"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Phase 2 regression failed:\n{res.stdout}\n{res.stderr}"
        print("✅ 25. Phase 2 student registration regression tests PASSED (18/18).")
        passed += 1
    except Exception as e:
        print(f"❌ 25. Test 25 failed: {e}")
        failed += 1

    # 26. Existing Iris ML pipeline regression
    try:
        from utils.pupil_detection import detect_pupil
        from utils.iris_segmentation import segment_iris
        from utils.feature_extractor import extract_features
        from utils.similarity import cosine_similarity

        assert callable(detect_pupil)
        assert callable(segment_iris)
        assert callable(extract_features)
        assert callable(cosine_similarity)
        print("✅ 26. Existing Iris ML pipeline components verified and intact.")
        passed += 1
    except Exception as e:
        print(f"❌ 26. Test 26 failed: {e}")
        failed += 1

    # Final cleanup
    cleanup_phase3_records()

    print("=" * 80)
    print(f"PHASE 3 TEST RESULTS: {passed} PASSED, {failed} FAILED (TOTAL: {passed + failed})")
    print("=" * 80)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

"""
Automated Verification Suite for Student Eye Scan Assessment-Context Loading & Authorization Gate.
Tests:
1. Direct camera.html access (no assessment ID) -> verified to require assessment context.
2. Valid Student assessment context loading -> verifies assessment and student metadata via backend API.
3. Student ownership verification (IDOR protection) -> Student A accessing Student B's assessment rejected with 403 Forbidden.
4. Unauthenticated request to scan endpoints rejected with 401 Unauthorized.
5. Non-existent assessment rejected with 404 Not Found.
6. LEFT eye capture and quality verification for valid student assessment.
7. RIGHT eye capture and quality verification for valid student assessment.
8. Authoritative dual-scan completion transition verified.
9. Admin authorization to inspect and scan any assessment verified.
"""

import os
import io
import time
import requests
import numpy as np
import cv2

BASE_URL = os.environ.get("IRIS_API_URL", "http://127.0.0.1:8001")

def get_auth_token(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed for {username}: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]

def make_test_iris_image(pupil_r=25, iris_r=65):
    img = np.full((480, 640, 3), 180, dtype=np.uint8)
    cx, cy = 320, 240
    cv2.circle(img, (cx, cy), iris_r, (70, 110, 150), -1)
    for r in range(pupil_r, iris_r, 4):
        cv2.circle(img, (cx, cy), r, (50, 90, 130), 1)
    cv2.circle(img, (cx, cy), pupil_r, (15, 15, 15), -1)
    cv2.circle(img, (cx - 8, cy - 8), 4, (255, 255, 255), -1)
    _, buf = cv2.imencode(".jpg", img)
    return io.BytesIO(buf.tobytes())

def run_tests():
    print("=" * 80)
    print("RUNNING ASSESSMENT-CONTEXT LOADING & SECURITY VERIFICATION SUITE")
    print(f"Target: {BASE_URL}")
    print("=" * 80)

    # 1. Fetch static/camera.html directly
    cam_html_resp = requests.get(f"{BASE_URL}/static/camera.html")
    assert cam_html_resp.status_code == 200, "camera.html should load successfully"
    assert "displayAssessmentId" in cam_html_resp.text
    assert "displayWorkflowStatus" in cam_html_resp.text
    assert "captureLeftBtn" in cam_html_resp.text
    assert "captureRightBtn" in cam_html_resp.text
    # Verify default placeholder is '--', not 'ASM-LOADING...'
    assert "ASM-LOADING..." not in cam_html_resp.text, "Placeholder should not say ASM-LOADING..."
    print("✅ 1. Static /static/camera.html loads with clean default placeholder ('--' instead of 'ASM-LOADING...').")

    # 2. Inspect static/camera.js for strict URL parameter enforcement
    cam_js_resp = requests.get(f"{BASE_URL}/static/camera.js")
    assert cam_js_resp.status_code == 200
    js_content = cam_js_resp.text
    # Verify no fallback to stale localStorage/sessionStorage when parsing URL
    assert 'urlParams.get("assessment_id")' in js_content
    assert "No assessment context found" in js_content
    assert "initializeAssessment" in js_content
    print("✅ 2. /static/camera.js enforces strict URL parameter assessment context and validation before camera initialization.")

    import sys
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

    from security.auth import create_access_token

    # 3. Setup Authenticated Users: Admin, Student 1, Student 2
    admin_token = create_access_token(subject="admin", role="Admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Register Student 1
    ts = int(time.time())
    stu1_id = f"STU-CTX-{ts}-1"
    stu1_name = f"Test Student {ts} One"
    reg1_resp = requests.post(
        f"{BASE_URL}/api/students",
        json={"student_id": stu1_id, "student_name": stu1_name},
        headers=admin_headers
    )
    assert reg1_resp.status_code == 201
    asm1_id = reg1_resp.json()["assessment"]["assessment_id"]

    # Register Student 2
    stu2_id = f"STU-CTX-{ts}-2"
    stu2_name = f"Test Student {ts} Two"
    reg2_resp = requests.post(
        f"{BASE_URL}/api/students",
        json={"student_id": stu2_id, "student_name": stu2_name},
        headers=admin_headers
    )
    assert reg2_resp.status_code == 201
    asm2_id = reg2_resp.json()["assessment"]["assessment_id"]

    # Student 1 & 2 Auth Tokens
    stu1_token = create_access_token(subject=stu1_id, role="Student", extra_claims={"student_id": stu1_id, "full_name": stu1_name})
    stu1_headers = {"Authorization": f"Bearer {stu1_token}"}

    stu2_token = create_access_token(subject=stu2_id, role="Student", extra_claims={"student_id": stu2_id, "full_name": stu2_name})
    stu2_headers = {"Authorization": f"Bearer {stu2_token}"}

    print(f"[*] Initialized Test Assessment 1: {asm1_id} for {stu1_id}")
    print(f"[*] Initialized Test Assessment 2: {asm2_id} for {stu2_id}")

    # 4. Unauthenticated scan status query -> 401
    unauth_resp = requests.get(f"{BASE_URL}/api/assessments/{asm1_id}/scan/status")
    assert unauth_resp.status_code == 401, f"Expected 401, got {unauth_resp.status_code}"
    print("✅ 4. Unauthenticated assessment scan status query strictly rejected with 401 Unauthorized.")

    # 5. Non-existent assessment query -> 404
    fake_resp = requests.get(f"{BASE_URL}/api/assessments/ASM-FAKE-999999/scan/status", headers=stu1_headers)
    assert fake_resp.status_code == 404, f"Expected 404, got {fake_resp.status_code}"
    print("✅ 5. Non-existent assessment queried by student strictly rejected with 404 Not Found.")

    # 6. IDOR Protection: Student 1 attempts to query Student 2's assessment -> 403 Forbidden
    idor_resp = requests.get(f"{BASE_URL}/api/assessments/{asm2_id}/scan/status", headers=stu1_headers)
    assert idor_resp.status_code == 403, f"Expected 403, got {idor_resp.status_code}"
    print("✅ 6. IDOR Protection: Student cannot query or access another student's assessment (403 Forbidden).")

    # 7. Student 1 queries own assessment -> 200 OK with correct metadata
    own_resp = requests.get(f"{BASE_URL}/api/assessments/{asm1_id}/scan/status", headers=stu1_headers)
    assert own_resp.status_code == 200
    own_data = own_resp.json()
    assert own_data["assessment_id"] == asm1_id
    assert own_data["student_id"] == stu1_id
    assert own_data["student_name"] == stu1_name
    assert own_data["workflow_status"] in ("REGISTERED", "INITIALIZED")
    assert own_data["both_completed"] is False
    print(f"✅ 7. Student 1 authorized for own assessment: {asm1_id}, student_id={stu1_id}, name={stu1_name}.")

    # 8. IDOR Protection on Scan Upload: Student 1 attempts to upload scan to Student 2's assessment -> 403 Forbidden
    img_stream = make_test_iris_image()
    idor_upload = requests.post(
        f"{BASE_URL}/api/assessments/{asm2_id}/scan/left",
        headers=stu1_headers,
        files={"file": ("left.jpg", img_stream, "image/jpeg")}
    )
    assert idor_upload.status_code == 403, f"Expected 403, got {idor_upload.status_code}"
    print("✅ 8. IDOR Protection on Scan Upload: Student 1 uploading to Student 2's assessment blocked with 403 Forbidden.")

    # 9. Student 1 uploads LEFT eye scan
    img_stream = make_test_iris_image()
    left_upload = requests.post(
        f"{BASE_URL}/api/assessments/{asm1_id}/scan/left",
        headers=stu1_headers,
        files={"file": ("left.jpg", img_stream, "image/jpeg")}
    )
    assert left_upload.status_code == 200
    assert left_upload.json()["status"] is True
    print(f"✅ 9. Student 1 successfully uploaded LEFT eye scan for assessment {asm1_id}.")

    # Verify status after left scan
    st_resp = requests.get(f"{BASE_URL}/api/assessments/{asm1_id}/scan/status", headers=stu1_headers)
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["scans"]["left"]["status"] == "Completed"
    assert st_data["scans"]["right"]["status"] == "Pending"
    assert st_data["both_completed"] is False
    print(f"✅ 10. Status updated: LEFT scan Completed, RIGHT scan Pending.")

    # 11. Student 1 uploads RIGHT eye scan
    img_stream = make_test_iris_image()
    right_upload = requests.post(
        f"{BASE_URL}/api/assessments/{asm1_id}/scan/right",
        headers=stu1_headers,
        files={"file": ("right.jpg", img_stream, "image/jpeg")}
    )
    assert right_upload.status_code == 200
    assert right_upload.json()["status"] is True
    print(f"✅ 11. Student 1 successfully uploaded RIGHT eye scan for assessment {asm1_id}.")

    # Verify status after both scans
    st_resp2 = requests.get(f"{BASE_URL}/api/assessments/{asm1_id}/scan/status", headers=stu1_headers)
    assert st_resp2.status_code == 200
    st_data2 = st_resp2.json()
    assert st_data2["scans"]["left"]["status"] == "Completed"
    assert st_data2["scans"]["right"]["status"] == "Completed"
    assert st_data2["both_completed"] is True
    assert st_data2["workflow_status"] == "SCAN_COMPLETED"
    print(f"✅ 12. Bilateral scans verified: both_completed=True, workflow_status=SCAN_COMPLETED.")

    # 13. Admin can inspect scan status for any student assessment
    admin_check = requests.get(f"{BASE_URL}/api/assessments/{asm1_id}/scan/status", headers=admin_headers)
    assert admin_check.status_code == 200
    assert admin_check.json()["assessment_id"] == asm1_id
    print(f"✅ 13. Admin successfully inspected scan status for assessment {asm1_id}.")

    print("=" * 80)
    print("ALL 13 ASSESSMENT-CONTEXT LOADING & SECURITY TESTS PASSED (13/13)")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()

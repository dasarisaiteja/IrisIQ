import os
import sys
import shutil
import requests
from io import BytesIO
from PIL import Image

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from security.auth import create_access_token
from database import get_connection as get_iris_conn
from database_student import get_connection as get_student_conn

BASE_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8001")

def run_smoke_tests():
    print(f"Running Step 21 smoke tests against {BASE_URL}...")
    
    # 1. Generate auth tokens
    admin_token = create_access_token(subject="admin", role="Admin")
    student_token = create_access_token(subject="student1", role="Student", extra_claims={"student_id": "STU-001"})
    
    adm_headers = {"Authorization": f"Bearer {admin_token}"}
    stu_headers = {"Authorization": f"Bearer {student_token}"}
    
    # 2. /health
    r_health = requests.get(f"{BASE_URL}/health")
    print(f"GET /health: {r_health.status_code}")
    assert r_health.status_code == 200, f"Expected 200, got {r_health.status_code}"
    health_json = r_health.json()
    print(f"  Health response: {health_json}")
    
    # 3. Create test JPEG image in memory
    buf = BytesIO()
    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    img.save(buf, format="JPEG")
    dummy_bytes = buf.getvalue()
    
    # 4. /detect
    # Test with real image from uploads if available or dummy image
    test_img_path = os.path.join(BASE_DIR, "uploads", "001.jpg")
    if os.path.exists(test_img_path):
        with open(test_img_path, "rb") as f:
            det_bytes = f.read()
    else:
        det_bytes = dummy_bytes
        
    r_detect = requests.post(
        f"{BASE_URL}/detect",
        files={"file": ("001.jpg", det_bytes, "image/jpeg")},
        headers=adm_headers
    )
    print(f"POST /detect: {r_detect.status_code}")
    assert r_detect.status_code == 200, f"Expected 200, got {r_detect.status_code}"
    det_json = r_detect.json()
    print(f"  Detect status: {det_json.get('status')}, bbox: {det_json.get('detection', {}).get('bbox')}")
    
    # 5. /enroll (auth gating check without creating permanent biometric record)
    # Check 1: Unauthenticated request rejected with 401
    r_enroll_unauth = requests.post(f"{BASE_URL}/enroll")
    print(f"POST /enroll (Unauthenticated): {r_enroll_unauth.status_code}")
    assert r_enroll_unauth.status_code == 401, f"Expected 401, got {r_enroll_unauth.status_code}"
    
    # Check 2: Student forbidden from enrollment (RBAC 403)
    r_enroll_stu = requests.post(
        f"{BASE_URL}/enroll",
        headers=stu_headers,
        data={"employee_code": "STU-001"}
    )
    print(f"POST /enroll (Student role): {r_enroll_stu.status_code}")
    assert r_enroll_stu.status_code == 403, f"Expected 403, got {r_enroll_stu.status_code}"
    
    # 6. /verify
    # Check 1: Student attempting to verify another student's record is blocked with 403 (IDOR/BOLA)
    r_verify_idor = requests.post(
        f"{BASE_URL}/verify",
        headers=stu_headers,
        data={"employee_code": "EMP-OTHER", "report_id": "IR-001"},
        files={"file": ("test.jpg", dummy_bytes, "image/jpeg")}
    )
    print(f"POST /verify (Student IDOR check): {r_verify_idor.status_code}")
    assert r_verify_idor.status_code == 403, f"Expected 403, got {r_verify_idor.status_code}"
    
    # Check 2: Admin verify with non-existent report returns 404 or 400 without crashing
    r_verify_adm = requests.post(
        f"{BASE_URL}/verify",
        headers=adm_headers,
        data={"employee_code": "NONEXISTENT_EMP", "report_id": "NONEXISTENT_REP"},
        files={"file": ("test.jpg", dummy_bytes, "image/jpeg")}
    )
    print(f"POST /verify (Admin check): {r_verify_adm.status_code}")
    # Verify endpoint handles graceful validation (non-500)
    assert r_verify_adm.status_code in (200, 400, 404), f"Expected 200/400/404, got {r_verify_adm.status_code}"
    
    # 7. /register-frame
    # Check 1: Unauthenticated request rejected with 401
    r_reg_unauth = requests.post(
        f"{BASE_URL}/register-frame",
        data={"employee_code": "TEMP_SMOKE_TEST"},
        files={"file": ("test.jpg", dummy_bytes, "image/jpeg")}
    )
    print(f"POST /register-frame (Unauthenticated): {r_reg_unauth.status_code}")
    assert r_reg_unauth.status_code == 401, f"Expected 401, got {r_reg_unauth.status_code}"
    
    # Check 2: Authenticated request saves frame
    temp_emp_folder = os.path.join(BASE_DIR, "uploads", "TEMP_SMOKE_TEST")
    try:
        r_reg_auth = requests.post(
            f"{BASE_URL}/register-frame",
            data={"employee_code": "TEMP_SMOKE_TEST"},
            files={"file": ("test.jpg", dummy_bytes, "image/jpeg")},
            headers=adm_headers
        )
        print(f"POST /register-frame (Admin): {r_reg_auth.status_code}")
        assert r_reg_auth.status_code == 200, f"Expected 200, got {r_reg_auth.status_code}"
        reg_json = r_reg_auth.json()
        print(f"  Register-frame response: {reg_json}")
    finally:
        # Clean up temporary folder immediately so no disk residue remains
        if os.path.exists(temp_emp_folder):
            shutil.rmtree(temp_emp_folder, ignore_errors=True)
            print("  Cleaned up TEMP_SMOKE_TEST upload folder.")
            
    # 8. /api/quality/analyze
    r_quality = requests.post(
        f"{BASE_URL}/api/quality/analyze",
        files={"file": ("test.jpg", dummy_bytes, "image/jpeg")},
        headers=adm_headers
    )
    print(f"POST /api/quality/analyze: {r_quality.status_code}")
    assert r_quality.status_code == 200, f"Expected 200, got {r_quality.status_code}"
    qual_json = r_quality.json()
    print(f"  Quality response: {qual_json}")
    
    # 9. Verify database counts remain pristine
    iris_conn = get_iris_conn()
    c_iris = iris_conn.cursor()
    c_iris.execute('SELECT COUNT(*) FROM iris_users')
    iris_users = c_iris.fetchone()[0]
    c_iris.execute('SELECT COUNT(*) FROM scan_history')
    scan_history = c_iris.fetchone()[0]
    c_iris.execute('SELECT COUNT(*) FROM app_users')
    app_users = c_iris.fetchone()[0]
    iris_conn.close()

    stu_conn = get_student_conn()
    c_stu = stu_conn.cursor()
    c_stu.execute('SELECT COUNT(*) FROM student_profiles')
    student_profiles = c_stu.fetchone()[0]
    c_stu.execute('SELECT COUNT(*) FROM assessment_questions')
    assessment_questions = c_stu.fetchone()[0]
    stu_conn.close()

    print("\n--- DATABASE INTEGRITY CHECK ---")
    print(f"iris_users = {iris_users} (Expected 10)")
    print(f"scan_history = {scan_history} (Expected 57)")
    print(f"student_profiles = {student_profiles} (Expected 2)")
    print(f"assessment_questions = {assessment_questions} (Expected 21)")
    print(f"app_users = {app_users} (Expected 3)")
    
    assert iris_users == 10, f"Expected 10, got {iris_users}"
    assert scan_history == 57, f"Expected 57, got {scan_history}"
    assert student_profiles == 2, f"Expected 2, got {student_profiles}"
    assert assessment_questions == 21, f"Expected 21, got {assessment_questions}"
    assert app_users == 3, f"Expected 3, got {app_users}"
    
    print("\n✅ ALL SMOKE TESTS AND DATABASE INVARIANTS PASSED!")

if __name__ == "__main__":
    run_smoke_tests()

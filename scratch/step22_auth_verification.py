import os
import sys
import requests
from io import BytesIO
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from security.auth import create_access_token

BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")

def test_authorization():
    print(f"Testing Biometric Authorization Matrix against {BASE_URL}...")
    
    # 1. Generate Tokens
    admin_token = create_access_token(subject="admin", role="Admin")
    counselor_token = create_access_token(subject="counselor", role="Counselor")
    student_token = create_access_token(subject="student1", role="Student", extra_claims={"student_id": "STU-001"})
    invalid_token = "invalid.token.structure12345"
    
    headers_adm = {"Authorization": f"Bearer {admin_token}"}
    headers_cou = {"Authorization": f"Bearer {counselor_token}"}
    headers_stu = {"Authorization": f"Bearer {student_token}"}
    headers_inv = {"Authorization": f"Bearer {invalid_token}"}
    headers_none = {}
    
    # Valid iris test image
    test_img_path = os.path.join(PROJECT_ROOT, "uploads", "001.jpg")
    with open(test_img_path, "rb") as f:
        iris_bytes = f.read()
        
    print("\n--- 1. POST /detect AUTHORIZATION MATRIX ---")
    
    # A. No Authorization header
    r_no_auth = requests.post(f"{BASE_URL}/detect", files={"file": ("001.jpg", iris_bytes, "image/jpeg")}, headers=headers_none)
    print(f"A. No token:        HTTP {r_no_auth.status_code} (Expected 401)")
    assert r_no_auth.status_code == 401, f"Expected 401, got {r_no_auth.status_code}"
    
    # B. Invalid JWT
    r_inv_auth = requests.post(f"{BASE_URL}/detect", files={"file": ("001.jpg", iris_bytes, "image/jpeg")}, headers=headers_inv)
    print(f"B. Invalid JWT:     HTTP {r_inv_auth.status_code} (Expected 401)")
    assert r_inv_auth.status_code == 401, f"Expected 401, got {r_inv_auth.status_code}"
    
    # C. Student JWT
    r_stu_auth = requests.post(f"{BASE_URL}/detect", files={"file": ("001.jpg", iris_bytes, "image/jpeg")}, headers=headers_stu)
    print(f"C. Student JWT:     HTTP {r_stu_auth.status_code} (Expected 403)")
    assert r_stu_auth.status_code == 403, f"Expected 403, got {r_stu_auth.status_code}"
    
    # D. Counselor JWT
    r_cou_auth = requests.post(f"{BASE_URL}/detect", files={"file": ("001.jpg", iris_bytes, "image/jpeg")}, headers=headers_cou)
    print(f"D. Counselor JWT:   HTTP {r_cou_auth.status_code} (Expected 200)")
    assert r_cou_auth.status_code == 200, f"Expected 200, got {r_cou_auth.status_code}"
    cou_json = r_cou_auth.json()
    assert cou_json.get("status") is True, f"Detection failed: {cou_json}"
    assert "detection" in cou_json and cou_json["detection"].get("bbox") is not None
    print(f"   Counselor bbox: {cou_json['detection']['bbox']}, confidence: {cou_json['detection']['confidence']}")
    
    # E. Admin JWT
    r_adm_auth = requests.post(f"{BASE_URL}/detect", files={"file": ("001.jpg", iris_bytes, "image/jpeg")}, headers=headers_adm)
    print(f"E. Admin JWT:       HTTP {r_adm_auth.status_code} (Expected 200)")
    assert r_adm_auth.status_code == 200, f"Expected 200, got {r_adm_auth.status_code}"
    adm_json = r_adm_auth.json()
    assert adm_json.get("status") is True, f"Detection failed: {adm_json}"
    assert "detection" in adm_json and adm_json["detection"].get("bbox") is not None
    print(f"   Admin bbox: {adm_json['detection']['bbox']}, confidence: {adm_json['detection']['confidence']}")
    
    print("\n--- 2. OTHER BIOMETRIC AUTHORIZATION MATRIX ---")
    
    # 2.1 POST /enroll
    # Unauth -> 401
    r_enr_unauth = requests.post(f"{BASE_URL}/enroll")
    print(f"POST /enroll (Unauthenticated): HTTP {r_enr_unauth.status_code} (Expected 401)")
    assert r_enr_unauth.status_code == 401
    
    # Student -> 403
    r_enr_stu = requests.post(f"{BASE_URL}/enroll", headers=headers_stu, data={"employee_code": "STU-001"})
    print(f"POST /enroll (Student):         HTTP {r_enr_stu.status_code} (Expected 403)")
    assert r_enr_stu.status_code == 403
    
    # Counselor -> Allowed past auth (fails on missing form fields 422, not 401/403)
    r_enr_cou = requests.post(f"{BASE_URL}/enroll", headers=headers_cou)
    print(f"POST /enroll (Counselor auth):  HTTP {r_enr_cou.status_code} (Expected 422 Unprocessable Entity - past auth)")
    assert r_enr_cou.status_code == 422
    
    # Admin -> Allowed past auth (fails on missing form fields 422, not 401/403)
    r_enr_adm = requests.post(f"{BASE_URL}/enroll", headers=headers_adm)
    print(f"POST /enroll (Admin auth):      HTTP {r_enr_adm.status_code} (Expected 422 Unprocessable Entity - past auth)")
    assert r_enr_adm.status_code == 422
    
    # 2.2 POST /verify
    # Unauth -> 401
    r_ver_unauth = requests.post(f"{BASE_URL}/verify")
    print(f"POST /verify (Unauthenticated): HTTP {r_ver_unauth.status_code} (Expected 401)")
    assert r_ver_unauth.status_code == 401
    
    # Student -> 403 when trying other student's record (IDOR)
    r_ver_stu = requests.post(
        f"{BASE_URL}/verify",
        headers=headers_stu,
        data={"employee_code": "EMP-OTHER", "report_id": "IR-001"},
        files={"file": ("001.jpg", iris_bytes, "image/jpeg")}
    )
    print(f"POST /verify (Student cross):   HTTP {r_ver_stu.status_code} (Expected 403)")
    assert r_ver_stu.status_code == 403
    
    # Counselor -> Allowed past auth
    r_ver_cou = requests.post(
        f"{BASE_URL}/verify",
        headers=headers_cou,
        data={"employee_code": "TEST_EMP", "report_id": "NONEXISTENT"},
        files={"file": ("001.jpg", iris_bytes, "image/jpeg")}
    )
    print(f"POST /verify (Counselor):       HTTP {r_ver_cou.status_code} (Expected 200/400/404)")
    assert r_ver_cou.status_code in (200, 400, 404)
    
    # Admin -> Allowed past auth
    r_ver_adm = requests.post(
        f"{BASE_URL}/verify",
        headers=headers_adm,
        data={"employee_code": "TEST_EMP", "report_id": "NONEXISTENT"},
        files={"file": ("001.jpg", iris_bytes, "image/jpeg")}
    )
    print(f"POST /verify (Admin):           HTTP {r_ver_adm.status_code} (Expected 200/400/404)")
    assert r_ver_adm.status_code in (200, 400, 404)
    
    # 2.3 POST /register-frame
    # Unauth -> 401
    r_rf_unauth = requests.post(f"{BASE_URL}/register-frame", data={"employee_code": "EMP001"}, files={"file": ("001.jpg", iris_bytes, "image/jpeg")})
    print(f"POST /register-frame (Unauth):  HTTP {r_rf_unauth.status_code} (Expected 401)")
    assert r_rf_unauth.status_code == 401
    
    # 2.4 POST /api/quality/analyze
    # Unauth -> 401
    r_qa_unauth = requests.post(f"{BASE_URL}/api/quality/analyze", files={"file": ("001.jpg", iris_bytes, "image/jpeg")})
    print(f"POST /api/quality/analyze (No): HTTP {r_qa_unauth.status_code} (Expected 401)")
    assert r_qa_unauth.status_code == 401
    
    # Admin -> 200
    r_qa_adm = requests.post(f"{BASE_URL}/api/quality/analyze", files={"file": ("001.jpg", iris_bytes, "image/jpeg")}, headers=headers_adm)
    print(f"POST /api/quality/analyze (Adm): HTTP {r_qa_adm.status_code} (Expected 200)")
    assert r_qa_adm.status_code == 200
    
    print("\n✅ ALL BIOMETRIC AUTHORIZATION MATRIX CHECKS PASSED!")

if __name__ == "__main__":
    test_authorization()

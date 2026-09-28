#!/usr/bin/env python3
"""
Comprehensive Security & Authorization Test Suite for Iris Camera Scan Fix.
Verifies RBAC enforcement, credential hygiene, and frontend error formatting.
"""

import os
import sys
import json
import time
import requests
import jwt

BASE_URL = "http://127.0.0.1:8000"

def get_auth_token(username, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    raise RuntimeError(f"Login failed for {username}: {resp.status_code} {resp.text}")

def test_authorization_scenarios():
    print("======================================================================")
    print("TEST SUITE 1: AUTHORIZATION SCENARIOS ON POST /detect")
    print("======================================================================")

    img_path = "static/photos/camera.jpg"
    if not os.path.exists(img_path):
        img_path = "static/photos/emp001_20260801133451.jpg"
    
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    # Scenario A: Unauthenticated -> /detect = 401
    r_unauth = requests.post(f"{BASE_URL}/detect", files={"file": ("camera.jpg", img_bytes, "image/jpeg")})
    print(f"Scenario A (Unauthenticated): HTTP {r_unauth.status_code}")
    print(f"Response: {r_unauth.text}")
    assert r_unauth.status_code == 401, f"Expected 401, got {r_unauth.status_code}"
    unauth_data = r_unauth.json()
    assert "detail" in unauth_data, "Expected 'detail' field in 401 response"

    # Scenario B: Student -> /detect = 403
    student_token = get_auth_token("student1", "Student@IrisIQ2026!")
    r_student = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {student_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    print(f"\nScenario B (Student): HTTP {r_student.status_code}")
    print(f"Response: {r_student.text}")
    assert r_student.status_code == 403, f"Expected 403, got {r_student.status_code}"
    student_data = r_student.json()
    assert "detail" in student_data, "Expected 'detail' field in 403 response"
    assert "Insufficient permissions" in student_data["detail"]

    # Scenario C: Counselor -> /detect = 200
    counselor_token = get_auth_token("counselor1", "Counselor@IrisIQ2026!")
    r_counselor = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {counselor_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    print(f"\nScenario C (Counselor): HTTP {r_counselor.status_code}")
    assert r_counselor.status_code == 200, f"Expected 200, got {r_counselor.status_code}"
    counselor_data = r_counselor.json()
    assert counselor_data.get("status") is True
    assert "detection" in counselor_data
    assert "confidence" in counselor_data["detection"]
    assert "color_analysis" in counselor_data
    assert "eye_color" in counselor_data["color_analysis"]
    assert "features" in counselor_data
    assert "pupil_radius" in counselor_data["features"]
    assert "iris_radius" in counselor_data["features"]
    print(f"Confidence: {counselor_data['detection']['confidence']}")
    print(f"Eye Color: {counselor_data['color_analysis']['eye_color']}")
    print(f"Pupil Radius: {counselor_data['features']['pupil_radius']}")
    print(f"Iris Radius: {counselor_data['features']['iris_radius']}")

    # Scenario D: Admin -> /detect = 200
    admin_token = get_auth_token("admin", "Admin@IrisIQ2026!")
    r_admin = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    print(f"\nScenario D (Admin): HTTP {r_admin.status_code}")
    assert r_admin.status_code == 200, f"Expected 200, got {r_admin.status_code}"
    admin_data = r_admin.json()
    assert admin_data.get("status") is True
    assert "detection" in admin_data
    assert "confidence" in admin_data["detection"]
    assert "color_analysis" in admin_data
    assert "eye_color" in admin_data["color_analysis"]
    assert "features" in admin_data
    assert "pupil_radius" in admin_data["features"]
    assert "iris_radius" in admin_data["features"]
    print(f"Confidence: {admin_data['detection']['confidence']}")
    print(f"Eye Color: {admin_data['color_analysis']['eye_color']}")
    print(f"Pupil Radius: {admin_data['features']['pupil_radius']}")
    print(f"Iris Radius: {admin_data['features']['iris_radius']}")

    print("\n>>> ALL AUTHORIZATION SCENARIOS (A, B, C, D) PASSED SUCCESSFULLY! <<<\n")

def get_sample_image():
    img_path = "static/photos/emp001_20260801133451.jpg"
    with open(img_path, "rb") as f:
        return f.read()

def test_stale_and_invalid_tokens():
    print("======================================================================")
    print("TEST SUITE 2: STALE AND INVALID TOKEN HANDLING")
    print("======================================================================")

    img_bytes = get_sample_image()

    # Create an expired token manually
    expired_payload = {
        "sub": "admin",
        "role": "Admin",
        "exp": int(time.time()) - 3600  # Expired 1 hour ago
    }
    secret = "irisiq-enterprise-security-jwt-signing-secret-key-2026-production-ready-64b"
    expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

    r_exp = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {expired_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Expired Token: HTTP {r_exp.status_code}, Body: {r_exp.text}")
    assert r_exp.status_code == 401
    assert "Token has expired" in r_exp.json().get("detail", "")

    # Create an invalid signature token
    tampered_token = expired_token[:-5] + "XXXXX"
    r_inv = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {tampered_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Invalid Token: HTTP {r_inv.status_code}, Body: {r_inv.text}")
    assert r_inv.status_code == 401

    print("\n>>> STALE & INVALID TOKEN TESTS PASSED! <<<\n")

def test_registration_to_camera_workflows():
    print("======================================================================")
    print("TEST SUITE 3: REGISTRATION -> CAMERA WORKFLOWS (STAFF VS STUDENT)")
    print("======================================================================")

    img_bytes = get_sample_image()

    # 1. Admin registration -> Camera Scan Iris
    admin_token = get_auth_token("admin", "Admin@IrisIQ2026!")
    adm_code = f"adm_{int(time.time()) % 10000}"
    
    # Upload frame first via /register-frame
    r_adm_rf = requests.post(
        f"{BASE_URL}/register-frame",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"employee_code": adm_code},
        files={"file": ("frame1.jpg", img_bytes, "image/jpeg")}
    )
    assert r_adm_rf.status_code == 200, f"Register frame failed: {r_adm_rf.text}"

    form_adm = {
        "employee_code": adm_code,
        "user_name": f"Admin Registered {adm_code}",
        "department": "Engineering",
        "designation": "Staff",
        "gender": "Female",
        "age": "28",
        "dob": "1998-05-12",
        "blood_group": "O+",
        "mobile": "9876543210",
        "email": f"adm_{adm_code}@example.com",
        "address": "123 Tech Park"
    }
    r_adm_reg = requests.post(
        f"{BASE_URL}/enroll",
        headers={"Authorization": f"Bearer {admin_token}"},
        data=form_adm,
        files={"file": ("emp.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Admin Enrollment: HTTP {r_adm_reg.status_code}")
    assert r_adm_reg.status_code == 200, f"Expected 200, got {r_adm_reg.status_code}: {r_adm_reg.text}"
    res_adm = r_adm_reg.json()
    assert res_adm["status"] is True
    assert "scan_info" in res_adm
    print(f"Admin Enrollment Scan Info: {res_adm['scan_info']}")

    # Admin accesses camera and performs Scan Iris
    r_adm_scan = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    assert r_adm_scan.status_code == 200
    res_adm_scan = r_adm_scan.json()
    assert res_adm_scan["status"] is True
    assert "features" in res_adm_scan
    print(f"Admin Post-Registration Camera Scan Iris: SUCCESS (200 OK)")

    # 2. Counselor registration -> Camera Scan Iris
    counselor_token = get_auth_token("counselor1", "Counselor@IrisIQ2026!")
    cou_code = f"cou_{int(time.time()) % 10000}"

    r_cou_rf = requests.post(
        f"{BASE_URL}/register-frame",
        headers={"Authorization": f"Bearer {counselor_token}"},
        data={"employee_code": cou_code},
        files={"file": ("frame1.jpg", img_bytes, "image/jpeg")}
    )
    assert r_cou_rf.status_code == 200, f"Register frame failed: {r_cou_rf.text}"

    form_cou = {
        "employee_code": cou_code,
        "user_name": f"Counselor Registered {cou_code}",
        "department": "Counseling",
        "designation": "Advisor",
        "gender": "Male",
        "age": "32",
        "dob": "1994-08-20",
        "blood_group": "A+",
        "mobile": "9876543211",
        "email": f"cou_{cou_code}@example.com",
        "address": "456 College Way"
    }
    r_cou_reg = requests.post(
        f"{BASE_URL}/enroll",
        headers={"Authorization": f"Bearer {counselor_token}"},
        data=form_cou,
        files={"file": ("emp.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Counselor Enrollment: HTTP {r_cou_reg.status_code}")
    assert r_cou_reg.status_code == 200, f"Expected 200, got {r_cou_reg.status_code}: {r_cou_reg.text}"
    res_cou = r_cou_reg.json()
    assert res_cou["status"] is True
    assert "scan_info" in res_cou
    print(f"Counselor Enrollment Scan Info: {res_cou['scan_info']}")

    # Counselor accesses camera and performs Scan Iris
    r_cou_scan = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {counselor_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    assert r_cou_scan.status_code == 200
    res_cou_scan = r_cou_scan.json()
    assert res_cou_scan["status"] is True
    assert "features" in res_cou_scan
    print(f"Counselor Post-Registration Camera Scan Iris: SUCCESS (200 OK)")

    # 3. Student attempt to register and scan -> must be 403 Forbidden!
    student_token = get_auth_token("student1", "Student@IrisIQ2026!")
    stu_code = f"stu_{int(time.time()) % 10000}"
    form_stu = {
        "employee_code": stu_code,
        "user_name": f"Student Attempt {stu_code}",
        "department": "Students",
        "designation": "Student",
        "gender": "Female",
        "age": "20",
        "dob": "2006-01-15",
        "blood_group": "B+",
        "mobile": "9876543212",
        "email": f"stu_{stu_code}@example.com",
        "address": "789 Dorm Hall"
    }
    r_stu_reg = requests.post(
        f"{BASE_URL}/enroll",
        headers={"Authorization": f"Bearer {student_token}"},
        data=form_stu,
        files={"file": ("emp.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Student Enrollment Attempt: HTTP {r_stu_reg.status_code}, Body: {r_stu_reg.text}")
    assert r_stu_reg.status_code == 403, f"Student should be rejected with 403, got {r_stu_reg.status_code}"

    r_stu_scan = requests.post(
        f"{BASE_URL}/detect",
        headers={"Authorization": f"Bearer {student_token}"},
        files={"file": ("camera.jpg", img_bytes, "image/jpeg")}
    )
    print(f"Student Scan Iris Attempt: HTTP {r_stu_scan.status_code}, Body: {r_stu_scan.text}")
    assert r_stu_scan.status_code == 403, f"Student scan should be rejected with 403, got {r_stu_scan.status_code}"

    print("\n>>> REGISTRATION WORKFLOW TESTS PASSED! <<<\n")

def test_frontend_credential_hygiene():
    print("======================================================================")
    print("TEST SUITE 4: FRONTEND CREDENTIAL HYGIENE & LOGIC CHECK")
    print("======================================================================")

    # Check static/auth_client.js
    with open("static/auth_client.js", "r") as f:
        auth_client_src = f.read()

    assert "Admin@IrisIQ2026!" not in auth_client_src, "CRITICAL ERROR: Hardcoded admin password found in auth_client.js"
    assert '"admin"' not in auth_client_src, "CRITICAL ERROR: Hardcoded admin username found in auth_client.js"
    assert "loginPromise" not in auth_client_src, "Auto-login promise logic should be removed"

    # Check static/camera.js
    with open("static/camera.js", "r") as f:
        camera_src = f.read()

    assert "extractApiErrorMessage" in camera_src, "extractApiErrorMessage function missing from camera.js"
    assert 'currentRole === "Student"' in camera_src, "Student role restriction check missing from camera.js"

    # Test extractApiErrorMessage emulation in Python
    def extract_api_error_message(data, fallback):
        if data and isinstance(data, dict):
            if isinstance(data.get("message"), str) and data["message"].strip():
                return data["message"]
            if isinstance(data.get("detail"), str) and data["detail"].strip():
                return data["detail"]
            if isinstance(data.get("detail"), list) and len(data["detail"]) > 0:
                items = [d.get("msg") if isinstance(d, dict) else str(d) for d in data["detail"] if d]
                if items:
                    return "; ".join(items)
            if isinstance(data.get("detail"), dict):
                nested = data["detail"].get("message") or data["detail"].get("error") or data["detail"].get("msg")
                if isinstance(nested, str) and nested.strip():
                    return nested
        return fallback

    fallback = "YOLO detection failed. Please position your eye correctly and try again."

    # Test cases:
    # Case 1: FastAPI 401
    assert extract_api_error_message({"detail": "Authentication credentials were not provided"}, fallback) == "Authentication credentials were not provided"

    # Case 2: FastAPI 403
    assert extract_api_error_message({"detail": "Insufficient permissions: requires one of ['Admin', 'Counselor']"}, fallback) == "Insufficient permissions: requires one of ['Admin', 'Counselor']"

    # Case 3: FastAPI 422 validation array
    assert extract_api_error_message({"detail": [{"msg": "Field required"}]}, fallback) == "Field required"

    # Case 4: Real YOLO 'No Iris Detected'
    assert extract_api_error_message({"status": False, "message": "No Iris Detected"}, fallback) == "No Iris Detected"

    # Case 5: Real YOLO 'YOLO detection failed'
    assert extract_api_error_message({"status": False, "message": "YOLO detection failed"}, fallback) == "YOLO detection failed"

    # Case 6: Empty/None data fallback
    assert extract_api_error_message(None, fallback) == fallback
    assert extract_api_error_message({}, fallback) == fallback

    print("Error extraction emulation tests: ALL PASSED!")
    print("\n>>> FRONTEND CREDENTIAL HYGIENE & LOGIC TESTS PASSED! <<<\n")

if __name__ == "__main__":
    try:
        test_authorization_scenarios()
        test_stale_and_invalid_tokens()
        test_registration_to_camera_workflows()
        test_frontend_credential_hygiene()
        print("======================================================================")
        print("ALL SECURITY & REGRESSION TESTS COMPLETED SUCCESSFULLY!")
        print("======================================================================")
    except Exception as e:
        print(f"\nTEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

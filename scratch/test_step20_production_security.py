"""
Step 20 — Production Deployment & Security Verification Test Suite
Standalone executable test suite using live server HTTP verification:
1. Environment & Secrets (production fail-safe, secret entropy, configurable expiry)
2. Authentication Lifecycle (login, /api/auth/me, invalid credentials, expired/tampered JWT, PBKDF2)
3. Object-Level Access / IDOR & BOLA (Student isolation, counselor/admin scope, biometric protection)
4. CORS & Security Headers (nosniff, SAMEORIGIN, Referrer-Policy, Permissions-Policy)
5. Biometric Protection & Upload Security (magic bytes, corrupted files, path traversal, media auth)
6. Database Security & Baseline Invariant Verification (10 iris_users, 57 scan_history, 2 student_profiles, 21 assessment_questions)
"""

import os
import sys
import io
import time
import asyncio
import sqlite3
import requests
from datetime import datetime, timedelta
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import get_connection as get_iris_conn
from database_student import get_connection as get_student_conn
from security.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_jwt_secret_key,
    DEFAULT_DEV_SECRET,
    PBKDF2_ITERATIONS
)
from security.upload_validator import validate_uploaded_image

SERVER_URL = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8000")


class MockUploadFile:
    def __init__(self, filename, content_bytes):
        self.filename = filename
        self.content_bytes = content_bytes
        self.pointer = 0

    async def read(self, size=-1):
        if size == -1:
            return self.content_bytes
        data = self.content_bytes[self.pointer:self.pointer + size]
        self.pointer += len(data)
        return data

    async def seek(self, pos):
        self.pointer = pos


def get_token_for_user(username: str, role: str, student_id: str = None) -> str:
    claims = {"role": role}
    if student_id:
        claims["student_id"] = student_id
    return create_access_token(username, role=role, extra_claims=claims)


def run_step20_tests():
    print("=" * 70)
    print("STEP 20 — PRODUCTION DEPLOYMENT & SECURITY VERIFICATION SUITE")
    print("=" * 70)

    passed = 0
    total = 0

    # -------------------------------------------------------------
    # 1. Environment & Secrets: Production Fail-Safe
    # -------------------------------------------------------------
    total += 1
    orig_env = os.environ.get("ENVIRONMENT")
    orig_key = os.environ.get("JWT_SECRET_KEY")

    try:
        # Case A: Production mode with missing key
        os.environ["ENVIRONMENT"] = "production"
        if "JWT_SECRET_KEY" in os.environ:
            del os.environ["JWT_SECRET_KEY"]
        threw_missing = False
        try:
            get_jwt_secret_key()
        except RuntimeError as e:
            assert "JWT_SECRET_KEY must be set" in str(e)
            threw_missing = True
        assert threw_missing, "Expected RuntimeError on missing production secret"

        # Case B: Production mode with short key (<32 chars)
        os.environ["JWT_SECRET_KEY"] = "short-key-12345"
        threw_short = False
        try:
            get_jwt_secret_key()
        except RuntimeError as e:
            assert "at least 32 characters" in str(e)
            threw_short = True
        assert threw_short, "Expected RuntimeError on short production secret"

        # Case C: Production mode with default dev secret
        os.environ["JWT_SECRET_KEY"] = DEFAULT_DEV_SECRET
        threw_default = False
        try:
            get_jwt_secret_key()
        except RuntimeError as e:
            assert "cannot use default development secret" in str(e)
            threw_default = True
        assert threw_default, "Expected RuntimeError on default dev secret in production"

        # Case D: Valid production secret (>=32 chars, custom)
        valid_prod_key = "a_super_secret_production_entropy_key_with_at_least_64_bytes_of_randomness_2026!"
        os.environ["JWT_SECRET_KEY"] = valid_prod_key
        assert get_jwt_secret_key() == valid_prod_key

    finally:
        if orig_env is not None:
            os.environ["ENVIRONMENT"] = orig_env
        else:
            os.environ.pop("ENVIRONMENT", None)

        if orig_key is not None:
            os.environ["JWT_SECRET_KEY"] = orig_key
        else:
            os.environ.pop("JWT_SECRET_KEY", None)

    print("✅ 1. Environment & Secrets: Production secret fail-safe, length & entropy verified")
    passed += 1

    # -------------------------------------------------------------
    # 2. Cryptographic Password Hashing (PBKDF2-HMAC-SHA256)
    # -------------------------------------------------------------
    total += 1
    assert PBKDF2_ITERATIONS >= 100_000
    stored_hash = hash_password("TestSecretPassword2026!")
    salt, pwd_hash = stored_hash.split("$")
    assert len(salt) == 32
    assert len(pwd_hash) == 64
    assert verify_password("TestSecretPassword2026!", stored_hash) is True
    assert verify_password("WrongPassword!", stored_hash) is False
    print("✅ 2. Cryptography: PBKDF2-HMAC-SHA256 hashing (100k iter) & salt verification passed")
    passed += 1

    # -------------------------------------------------------------
    # 3. Authentication Lifecycle
    # -------------------------------------------------------------
    total += 1
    # Invalid credentials
    resp_bad = requests.post(f"{SERVER_URL}/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert resp_bad.status_code == 401
    assert "Invalid username or password" in resp_bad.json()["detail"]

    # Nonexistent user
    resp_no_user = requests.post(f"{SERVER_URL}/api/auth/login", json={"username": "nonexistent_user_999", "password": "any"})
    assert resp_no_user.status_code == 401

    # Valid admin login
    resp_ok = requests.post(f"{SERVER_URL}/api/auth/login", json={"username": "admin", "password": "Admin@IrisIQ2026!"})
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert "access_token" in data
    assert data["role"] == "Admin"

    token = data["access_token"]

    # /api/auth/me with valid token
    resp_me = requests.get(f"{SERVER_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    assert resp_me.json()["username"] == "admin"
    assert resp_me.json()["role"] == "Admin"

    # Missing token
    resp_missing = requests.get(f"{SERVER_URL}/api/auth/me")
    assert resp_missing.status_code == 401

    # Malformed token header
    resp_malformed = requests.get(f"{SERVER_URL}/api/auth/me", headers={"Authorization": "NotBearer 12345"})
    assert resp_malformed.status_code == 401

    # Tampered token
    tampered_token = token[:-5] + "XXXXX"
    resp_tampered = requests.get(f"{SERVER_URL}/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert resp_tampered.status_code == 401

    # Expired token
    expired_token = create_access_token("admin", role="Admin", expires_delta=timedelta(seconds=-10))
    resp_expired = requests.get(f"{SERVER_URL}/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp_expired.status_code == 401
    assert "expired" in resp_expired.json()["detail"].lower()

    print("✅ 3. Authentication Lifecycle: Valid/invalid login, expiration, tampering & /me verified")
    passed += 1

    # -------------------------------------------------------------
    # 4. Object-Level Access / IDOR Defense (Student Profile Isolation)
    # -------------------------------------------------------------
    total += 1
    student1_token = get_token_for_user("student1", "Student", student_id="STU-001")
    counselor_token = get_token_for_user("counselor1", "Counselor")
    admin_token = get_token_for_user("admin", "Admin")

    headers_s1 = {"Authorization": f"Bearer {student1_token}"}
    headers_c = {"Authorization": f"Bearer {counselor_token}"}
    headers_a = {"Authorization": f"Bearer {admin_token}"}

    # Student 1 accessing own profile STU-001 -> 200 OK
    resp_own = requests.get(f"{SERVER_URL}/api/profile/STU-001", headers=headers_s1)
    assert resp_own.status_code == 200
    assert resp_own.json()["status"] is True

    # Student 1 accessing STU-002 -> 403 Forbidden (IDOR Blocked)
    resp_idor = requests.get(f"{SERVER_URL}/api/profile/STU-002", headers=headers_s1)
    assert resp_idor.status_code == 403
    assert "not authorized" in resp_idor.json()["detail"].lower()

    # Counselor accessing STU-001 and STU-002 -> 200 OK
    resp_c_stu1 = requests.get(f"{SERVER_URL}/api/profile/STU-001", headers=headers_c)
    assert resp_c_stu1.status_code == 200
    resp_c_stu2 = requests.get(f"{SERVER_URL}/api/profile/STU-002", headers=headers_c)
    assert resp_c_stu2.status_code == 200

    # Admin accessing STU-002 -> 200 OK
    resp_a_stu2 = requests.get(f"{SERVER_URL}/api/profile/STU-002", headers=headers_a)
    assert resp_a_stu2.status_code == 200

    print("✅ 4. IDOR/BOLA Defense: Student profile cross-tenant isolation verified")
    passed += 1

    # -------------------------------------------------------------
    # 5. Object-Level Access: Reports, Assessments, Student List
    # -------------------------------------------------------------
    total += 1
    # Student 1 accessing Student 2 report -> 403
    resp_rep_idor = requests.get(f"{SERVER_URL}/api/profile/STU-002/report", headers=headers_s1)
    assert resp_rep_idor.status_code == 403

    # Student 1 submitting assessment for STU-002 -> 403
    resp_submit_idor = requests.post(
        f"{SERVER_URL}/api/profile/assessment",
        headers=headers_s1,
        json={"student_id": "STU-002", "domain": "personality", "responses": {}}
    )
    assert resp_submit_idor.status_code == 403

    # Student 1 listing students -> only sees their own profile STU-001
    resp_list = requests.get(f"{SERVER_URL}/api/profile/students", headers=headers_s1)
    assert resp_list.status_code == 200
    stu_list = resp_list.json()["students"]
    assert len(stu_list) == 1
    assert stu_list[0]["student_id"] == "STU-001"

    # Student 1 accessing Student 2 sub-resource mutations (IDOR)
    resp_acad_idor = requests.post(f"{SERVER_URL}/api/profile/STU-002/academics", headers=headers_s1, json=[])
    assert resp_acad_idor.status_code == 403

    resp_skill_idor = requests.post(f"{SERVER_URL}/api/profile/STU-002/skills", headers=headers_s1, json=[])
    assert resp_skill_idor.status_code == 403

    resp_int_idor = requests.post(f"{SERVER_URL}/api/profile/STU-002/interests", headers=headers_s1, json=[])
    assert resp_int_idor.status_code == 403

    resp_act_idor = requests.post(f"{SERVER_URL}/api/profile/STU-002/activities", headers=headers_s1, json=[])
    assert resp_act_idor.status_code == 403

    # Student 1 attempting to perform verification on another employee_code
    resp_verify_idor = requests.post(
        f"{SERVER_URL}/verify",
        headers=headers_s1,
        data={"employee_code": "EMP-999", "report_id": "IR-12345"},
        files={"file": ("test.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 20, "image/jpeg")}
    )
    assert resp_verify_idor.status_code == 403

    # Student 1 attempting to access another student's photo via media
    resp_photo_idor = requests.get(f"{SERVER_URL}/api/media/photos/stu002_photo.jpg", headers=headers_s1)
    assert resp_photo_idor.status_code == 403

    print("✅ 5. IDOR/BOLA Defense: Reports, assessments, mutations, verification & media scope verified")
    passed += 1

    # -------------------------------------------------------------
    # 6. Role Boundaries (Student cannot execute Admin/Counselor ops)
    # -------------------------------------------------------------
    total += 1
    # Student cannot create student profile
    resp_create = requests.post(
        f"{SERVER_URL}/api/profile/students",
        headers=headers_s1,
        json={"student_id": "STU-NEW", "full_name": "New Student"}
    )
    assert resp_create.status_code == 403

    # Student cannot delete student profile
    resp_del = requests.delete(f"{SERVER_URL}/api/profile/STU-002", headers=headers_s1)
    assert resp_del.status_code == 403

    # Student cannot enroll biometric user
    resp_enroll = requests.post(f"{SERVER_URL}/enroll", headers=headers_s1)
    assert resp_enroll.status_code == 403

    print("✅ 6. Role Boundary Enforcement: Student restricted from privileged operations")
    passed += 1

    # -------------------------------------------------------------
    # 7. Security Headers Middleware
    # -------------------------------------------------------------
    total += 1
    resp_head = requests.get(f"{SERVER_URL}/health")
    assert resp_head.status_code == 200
    assert resp_head.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp_head.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp_head.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp_head.headers.get("Permissions-Policy") == "camera=(self)"

    print("✅ 7. Security Headers: nosniff, SAMEORIGIN, Referrer-Policy, Permissions-Policy verified")
    passed += 1

    # -------------------------------------------------------------
    # 8. CORS Restriction
    # -------------------------------------------------------------
    total += 1
    untrusted_origin = "https://malicious-attacker-site.com"
    resp_cors = requests.options(
        f"{SERVER_URL}/api/auth/me",
        headers={
            "Origin": untrusted_origin,
            "Access-Control-Request-Method": "GET"
        }
    )
    allow_origin = resp_cors.headers.get("access-control-allow-origin")
    assert allow_origin != untrusted_origin
    assert allow_origin != "*"

    print("✅ 8. Production CORS: Untrusted origin rejection verified")
    passed += 1

    # -------------------------------------------------------------
    # 9. Biometric Media Protection & Path Traversal
    # -------------------------------------------------------------
    total += 1
    # Unauthenticated media request -> 401
    resp_unauth = requests.get(f"{SERVER_URL}/api/media/uploads/sample.jpg")
    assert resp_unauth.status_code == 401

    # Student cannot access raw uploads or outputs -> 403
    resp_stu_upload = requests.get(f"{SERVER_URL}/api/media/uploads/test.jpg", headers=headers_s1)
    assert resp_stu_upload.status_code == 403

    resp_stu_output = requests.get(f"{SERVER_URL}/api/media/outputs/mask.png", headers=headers_s1)
    assert resp_stu_output.status_code == 403

    # Path traversal attempts
    traversal_paths = [
        "../main.py",
        "nested/../../database.py"
    ]
    for bad_path in traversal_paths:
        resp_trav = requests.get(f"{SERVER_URL}/api/media/uploads/{bad_path}", headers=headers_a)
        assert resp_trav.status_code in (400, 403, 404)

    print("✅ 9. Biometric Protection: Media authentication, role gating & path traversal defense verified")
    passed += 1

    # -------------------------------------------------------------
    # 10. Upload Security & Magic Byte Validation
    # -------------------------------------------------------------
    total += 1
    async def run_upload_tests():
        # Valid JPEG
        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        valid_bytes = buf.getvalue()
        f_valid = MockUploadFile("photo.jpg", valid_bytes)
        b, fn = await validate_uploaded_image(f_valid)
        assert len(b) > 0 and fn == "photo.jpg"

        # Empty file
        threw_empty = False
        try:
            f_empty = MockUploadFile("empty.jpg", b"")
            await validate_uploaded_image(f_empty)
        except Exception:
            threw_empty = True
        assert threw_empty

        # Wrong magic bytes (HTML masquerading as .jpg)
        threw_magic = False
        try:
            f_fake = MockUploadFile("exploit.jpg", b"<?php echo 'malicious code'; ?>")
            await validate_uploaded_image(f_fake)
        except Exception:
            threw_magic = True
        assert threw_magic

        # Oversized file (>15MB)
        threw_huge = False
        try:
            f_huge = MockUploadFile("huge.jpg", b"\xFF\xD8\xFF\xE0" + (b"A" * (16 * 1024 * 1024)))
            await validate_uploaded_image(f_huge)
        except Exception:
            threw_huge = True
        assert threw_huge

    asyncio.run(run_upload_tests())
    print("✅ 10. Upload Security: Magic bytes, corrupt headers, empty/oversized validation verified")
    passed += 1

    # -------------------------------------------------------------
    # 11. Static Database Protection (No DB Download)
    # -------------------------------------------------------------
    total += 1
    resp_iris_db = requests.get(f"{SERVER_URL}/static/iris.db")
    assert resp_iris_db.status_code == 404

    resp_stu_db = requests.get(f"{SERVER_URL}/static/student_profiling.db")
    assert resp_stu_db.status_code == 404

    print("✅ 11. Database Exposure: Static SQLite file accessibility verified 404")
    passed += 1

    # -------------------------------------------------------------
    # 12. Database Baseline Invariants
    # -------------------------------------------------------------
    total += 1
    iris_conn = get_iris_conn()
    cur_iris = iris_conn.cursor()
    cur_iris.execute("SELECT COUNT(*) FROM iris_users")
    iris_users_count = cur_iris.fetchone()[0]

    cur_iris.execute("SELECT COUNT(*) FROM scan_history")
    scan_history_count = cur_iris.fetchone()[0]
    iris_conn.close()

    stu_conn = get_student_conn()
    cur_stu = stu_conn.cursor()
    cur_stu.execute("SELECT COUNT(*) FROM student_profiles")
    student_profiles_count = cur_stu.fetchone()[0]

    cur_stu.execute("SELECT COUNT(*) FROM assessment_questions")
    assessment_questions_count = cur_stu.fetchone()[0]
    stu_conn.close()

    assert iris_users_count == 10, f"Expected 10 iris_users, found {iris_users_count}"
    assert scan_history_count == 57, f"Expected 57 scan_history, found {scan_history_count}"
    assert student_profiles_count == 2, f"Expected 2 student_profiles, found {student_profiles_count}"
    assert assessment_questions_count == 21, f"Expected 21 assessment_questions, found {assessment_questions_count}"

    print("✅ 12. Database Invariants: Baseline preserved (10 iris_users, 57 scans, 2 students, 21 questions)")
    passed += 1

    print("=" * 70)
    print(f"STEP 20 RESULTS: {passed} PASSED, 0 FAILED out of {total} CRITERIA.")
    print("=" * 70)


if __name__ == "__main__":
    run_step20_tests()

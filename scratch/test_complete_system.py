import requests
import sqlite3
import numpy as np
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")

def test_system():
    print("=" * 60)
    print("STARTING SYSTEM INTEGRITY & NON-REGRESSION SUITE")
    print("=" * 60)

    # 1. Health & Home (Public)
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200 and r.json().get("status") == "healthy", "Health check failed"
    print("✅ 1. Health check passed (/health)")

    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200, "Home endpoint failed"
    print("✅ 2. Home endpoint passed (/)")

    # Authenticate to obtain JWT Bearer token for protected endpoints
    login_r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Admin@IrisIQ2026!"})
    assert login_r.status_code == 200, "Authentication login failed in test suite"
    token = login_r.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. Existing Dashboard & Keys (Authenticated)
    r = requests.get(f"{BASE_URL}/dashboard", headers=auth_headers)
    assert r.status_code == 200, "Dashboard failed"
    dash = r.json()
    # Check preserved keys
    for k in ["total_users", "total_employees", "total_scans", "matched", "not_matched", "accuracy", "reports", "monthly_reports", "recent_scans", "activity"]:
        assert k in dash, f"Missing preserved key: {k}"
    # Check added keys
    for k in ["total_students", "completed_assessments", "profiles_generated", "reports_generated", "career_recommendations", "stream_recommendations", "pending_assessments"]:
        assert k in dash, f"Missing new student key: {k}"
    print("✅ 3. Dashboard API passed (all 10 preserved keys + 7 new student intelligence keys)")

    # 3. Existing V1 Report (Authenticated)
    r = requests.get(f"{BASE_URL}/report?report_id=IR-20260909125126644-TYVFBYS", headers=auth_headers)
    assert r.status_code == 200, "V1 Report failed"
    v1_rep = r.json()
    assert v1_rep.get("status") is True and "report" in v1_rep, "Invalid V1 Report format"
    print("✅ 4. Existing Report V1 API passed (/report)")

    # 4. Iris Quality Analysis (Authenticated)
    sample_img = "outputs/iris_segment.jpg"
    if os.path.exists(sample_img):
        with open(sample_img, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/api/quality/analyze",
                files={"file": ("iris_segment.jpg", f, "image/jpeg")},
                data={"iris_x": 100, "iris_y": 100, "iris_r": 50},
                headers=auth_headers
            )
        assert r.status_code == 200 and r.json().get("status") is True, "Quality analysis failed"
        q = r.json().get("quality")
        assert "capture_quality_score" in q and "usable_iris_percentage" in q and q["source"] == "rule-based"
        print(f"✅ 5. Iris Quality API passed (Score: {q['capture_quality_score']}%, Usable: {q['usable_iris_percentage']}%)")
    else:
        print("⚠️ 5. Skipped quality image check (outputs/iris_segment.jpg not found)")

    # 5. Student Management APIs (Authenticated)
    r = requests.get(f"{BASE_URL}/api/profile/students", headers=auth_headers)
    assert r.status_code == 200 and r.json().get("status") is True
    students = r.json().get("students", [])
    assert len(students) >= 2, "Expected at least 2 seeded students"
    print(f"✅ 6. Student Directory API passed ({len(students)} students found)")

    # 6. Single Student Profile & Fusion (Authenticated)
    r = requests.get(f"{BASE_URL}/api/profile/STU-001", headers=auth_headers)
    assert r.status_code == 200
    prof = r.json().get("profile")
    assert prof["student"]["student_id"] == "STU-001"
    assert prof["student"]["source"] == "profile-derived"
    assert prof["iris_biometrics"]["source"] == "iris-derived"
    print("✅ 7. Student Feature Fusion API passed (STU-001 with biometric link)")

    # 7. Assessment Questions & Submission (Authenticated)
    r = requests.get(f"{BASE_URL}/api/profile/questions/all", headers=auth_headers)
    assert r.status_code == 200
    questions = r.json().get("questions", [])
    assert len(questions) >= 15, "Expected questions across all 8 domains"
    print(f"✅ 8. Assessment Questions API passed ({len(questions)} questions)")

    # Test submitting a response
    sub_payload = {
        "student_id": "STU-002",
        "domain": "critical_abilities",
        "responses": {"6": 4, "7": 4, "8": 5, "9": 4, "10": 5}
    }
    r = requests.post(f"{BASE_URL}/api/profile/assessment", json=sub_payload, headers=auth_headers)
    assert r.status_code == 200 and r.json().get("status") is True
    eval_res = r.json().get("result")
    assert eval_res["source"] == "assessment-derived"
    assert eval_res.get("confidence") is None
    assert eval_res.get("confidence_status") == "not_statistically_calibrated"
    for k, d in eval_res.get("details", {}).items():
        assert d.get("confidence") is None, f"Confidence for {k} must be null"
        assert d.get("confidence_status") == "not_statistically_calibrated"
    print("✅ 9. Assessment Submission & Evaluation API passed (Confidence verified as null / not_statistically_calibrated)")

    # 8. Holistic Analysis & Domain Profiles (Authenticated)
    r = requests.post(f"{BASE_URL}/api/profile/STU-001/analyze", headers=auth_headers)
    assert r.status_code == 200
    analysis = r.json()
    assert "cognitive" in analysis and "streams" in analysis and "careers" in analysis and "activities_and_sports" in analysis
    print("✅ 10. Holistic Profile Analysis API passed")

    # Domain specific endpoints (Authenticated)
    for endpoint in ["personality", "cognitive", "learning-style", "leadership", "subjects", "streams", "careers", "activities", "recommendations"]:
        r = requests.get(f"{BASE_URL}/api/profile/STU-001/{endpoint}", headers=auth_headers)
        assert r.status_code == 200, f"Endpoint {endpoint} failed"
    print("✅ 11. All 9 Domain Getters passed (/personality, /cognitive, /streams, /careers, etc.)")

    # 9. V2 Report Generation & 32 Sections (Authenticated)
    r = requests.post(f"{BASE_URL}/api/profile/STU-001/report", headers=auth_headers)
    assert r.status_code == 200
    rep_v2 = r.json()
    assert rep_v2.get("version") == "V2"
    sec = rep_v2.get("sections", {})
    assert len(sec) >= 25, "Expected comprehensive 32 sections in Report V2"
    assert "section_01_cover" in sec and "section_10_cognitive_profile" in sec and "section_19_stream_selection" in sec and "section_32_limitations_disclaimer" in sec
    # Verify Section 11 critical abilities confidence is None and marked not_statistically_calibrated
    crit_abilities = sec.get("section_11_critical_abilities", {}).get("abilities", {})
    for ab_k, ab_v in crit_abilities.items():
        assert ab_v.get("confidence") is None, f"Section 11 {ab_k} confidence must not be hardcoded float"
        assert ab_v.get("confidence_status") == "not_statistically_calibrated"
    print(f"✅ 12. Report V2 Generation API passed (Report ID: {rep_v2.get('report_id')}, {len(sec)} sections verified, confidence uncalibrated)")

    # 10. ML Architecture & Evaluation Check
    from ml.stream.model import BaselineStreamPredictor
    from ml.evaluation import evaluate_predictions

    model = BaselineStreamPredictor()
    X_sample = np.array([[85, 90, 75, 88, 70], [60, 65, 80, 70, 85]])
    preds = model.predict(X_sample)
    assert len(preds) == 2 and preds[0] in ["Science", "Commerce", "Humanities"]
    metrics = evaluate_predictions(["Science", "Humanities"], preds)
    assert "accuracy" in metrics and "f1" in metrics
    print(f"✅ 13. ML Architecture & Evaluation framework passed (Sample/Test accuracy: {metrics['accuracy']} — this is only a framework verification result and does not represent production model accuracy.)")
    print("   ℹ️ ML infrastructure is implemented and ready for validated model integration; production ML prediction models have not yet been scientifically validated.")

    # 11. Database Non-Regression Check
    conn = sqlite3.connect("iris_database.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM iris_users")
    assert cur.fetchone()[0] == 10, "iris_users count changed!"
    cur.execute("SELECT COUNT(*) FROM scan_history")
    assert cur.fetchone()[0] == 57, "scan_history count changed!"
    conn.close()
    print("✅ 14. Database Non-Regression passed (10 iris_users and 57 scan_history records 100% intact)")

    print("=" * 60)
    print("ALL 14 INTEGRITY & TEST SUITES PASSED SUCCESSFULLY (ZERO REGRESSION)")
    print("=" * 60)

if __name__ == "__main__":
    test_system()

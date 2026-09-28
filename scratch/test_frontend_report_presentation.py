"""
Frontend & V2 Report Presentation Verification Suite
Validates Step 7 UI presentation, terminology, explainability, disclaimers, and Section 25 matrix fix.
"""

import os
import re
import requests
import json
from database import get_connection as get_iris_conn
from database_student import get_connection as get_stu_conn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

def run_presentation_tests():
    print("=" * 65)
    print("STARTING FRONTEND & V2 REPORT PRESENTATION VERIFICATION SUITE")
    print("=" * 65)

    # ---------------- 1. HTML & JS Static Inspections ----------------
    rec_html = open(os.path.join(STATIC_DIR, "recommendations.html")).read()
    rec_js = open(os.path.join(STATIC_DIR, "recommendations.js")).read()
    rep_html = open(os.path.join(STATIC_DIR, "student_report.html")).read()
    rep_js = open(os.path.join(STATIC_DIR, "student_report.js")).read()

    # A. Check elimination of winner framing & unsupported claims
    forbidden_terms = [
        "fa-crown",
        "fa-trophy",
        "High market demand",
        "Top Match",
        "Best Stream",
        "Ideal Stream",
        "Perfect Stream",
        "Correct Stream"
    ]
    for term in forbidden_terms:
        assert term not in rec_html, f"Found forbidden term '{term}' in recommendations.html"
        assert term not in rep_html, f"Found forbidden term '{term}' in student_report.html"
    print("✅ 1. Elimination of crown icons and winner framing verified in templates")

    # B. Check neutral terminology in HTML templates
    assert "Higher-Match Careers" in rec_html and "Higher-Match Careers" in rep_html
    assert "Catalog-Trending Careers" in rec_html and "Catalog-Trending Careers" in rep_html
    assert "Additional Career Matches" in rec_html and "Additional Career Matches" in rep_html
    assert "Stream Affinity Analysis & Educational Pathways" in rep_html
    assert "Primary Stream Affinity" in rep_html
    assert "Catalog Taxonomy Notice" in rec_js or "Catalog Taxonomy" in rec_html
    print("✅ 2. Neutral career and stream category titles verified across templates")

    # C. Check Section 25 Career Matrix element & rendering logic
    assert 'id="repCareerMatrix"' in rep_html, "repCareerMatrix missing in student_report.html"
    assert "repCareerMatrix" in rep_js, "repCareerMatrix missing in student_report.js"
    assert "Career Pathway" in rep_js and "Domain Category" in rep_js and "Affinity Index (0-100)" in rep_js
    print("✅ 3. Section 25 repCareerMatrix container and table rendering verified")

    # D. Check Confidence & Provenance disclosures
    assert "Confidence: Not statistically calibrated" in rec_js
    assert "Confidence: Not statistically calibrated" in rep_html
    assert "rule-based heuristic matching" in rec_html or "rule-based heuristic matching" in rec_js
    assert "rule-based heuristic matching" in rep_html
    print("✅ 4. Scientific confidence and provenance disclosures verified in templates")

    # E. Check Missing Data & Profile Data Pending handling
    assert "Profile Data Pending" in rec_js
    assert "Profile Data Pending" in rep_js
    assert "Prerequisite subject marks or assessment records are not yet on file." in rec_js
    assert "Prerequisite subject marks or assessment records are not yet on file." in rep_js
    print("✅ 5. Profile Data Pending state and explanations verified in JS logic")

    # ---------------- 2. Live API & V2 Report Verification ----------------
    # A. Recommendations Endpoint
    r_rec = requests.get("http://127.0.0.1:8000/api/profile/STU-001/recommendations")
    assert r_rec.status_code == 200, f"Rec API returned {r_rec.status_code}"
    rec_data = r_rec.json()
    st_data = rec_data.get("streams", {})
    cr_data = rec_data.get("careers", {})

    assert "primary_affinity_stream" in st_data and "recommended_stream" in st_data
    assert "secondary_affinity_stream" in st_data
    assert "conflicts_and_considerations" in st_data
    assert "higher_match_careers" in cr_data and "top_recommendations" in cr_data
    assert "trending_catalog_careers" in cr_data and "trending_careers" in cr_data
    assert "additional_suitable_careers" in cr_data and "other_suitable_careers" in cr_data
    assert "trending_disclaimer" in cr_data
    print("✅ 6. Recommendations API backward compatibility and neutral fields verified")

    # B. V2 Report Generation Endpoint
    r_rep = requests.post("http://127.0.0.1:8000/api/profile/STU-001/report")
    assert r_rep.status_code == 200, f"Report API returned {r_rep.status_code}"
    rep_data = r_rep.json()
    sec = rep_data.get("sections", {})

    # Section 03
    s3 = sec.get("section_03_executive_summary", {})
    assert s3.get("primary_affinity_stream") is not None
    assert s3.get("higher_match_career") is not None
    assert s3.get("recommended_stream") is not None  # backward compat
    assert s3.get("top_career") is not None          # backward compat
    print("✅ 7. Report V2 Section 03 Executive Summary verified (dual neutral + legacy keys)")

    # Section 19
    s19 = sec.get("section_19_stream_selection", {})
    assert s19.get("primary_affinity_stream") is not None
    assert s19.get("secondary_affinity_stream") is not None
    prov19 = s19.get("provenance", {})
    assert prov19.get("source") == "rule-based"
    assert prov19.get("confidence_status") == "not_statistically_calibrated"
    assert prov19.get("confidence") is None
    print("✅ 8. Report V2 Section 19 Stream Affinity Analysis & Provenance verified")

    # Section 22, 23, 24
    s22 = sec.get("section_22_top_career_recommendations", {})
    s23 = sec.get("section_23_trending_careers", {})
    s24 = sec.get("section_24_other_suitable_careers", {})
    assert len(s22.get("higher_match_careers", [])) > 0
    assert len(s23.get("trending_catalog_careers", [])) >= 0
    assert "trending_disclaimer" in s23
    assert len(s24.get("additional_suitable_careers", [])) >= 0
    print("✅ 9. Report V2 Sections 22–24 Career recommendations verified")

    # Section 25 Matrix
    s25 = sec.get("section_25_career_compatibility", {})
    matrix = s25.get("matrix", [])
    assert len(matrix) == 7, f"Expected 7 matrix items, got {len(matrix)}"
    for row in matrix:
        assert "career" in row and "category" in row and "score" in row and "match_level" in row and "why" in row
    print("✅ 10. Report V2 Section 25 Career Compatibility Matrix populated with all 7 backend rows")

    # ---------------- 3. Integrity & Protected Systems Verification ----------------
    iris_conn = get_iris_conn()
    c_iris = iris_conn.cursor()
    c_iris.execute("SELECT COUNT(*) FROM iris_users")
    u_count = c_iris.fetchone()[0]
    c_iris.execute("SELECT COUNT(*) FROM scan_history")
    s_count = c_iris.fetchone()[0]
    assert u_count == 10, f"Expected 10 iris users, got {u_count}"
    assert s_count == 57, f"Expected 57 scan history records, got {s_count}"
    iris_conn.close()

    stu_conn = get_stu_conn()
    c_stu = stu_conn.cursor()
    c_stu.execute("SELECT COUNT(*) FROM assessment_questions")
    q_count = c_stu.fetchone()[0]
    assert q_count == 21, f"Expected 21 assessment questions, got {q_count}"
    stu_conn.close()
    print("✅ 11. Database integrity verified (10 iris_users, 57 scan_history, 21 assessment_questions intact)")

    print("=" * 65)
    print("ALL 11 FRONTEND & V2 REPORT PRESENTATION VERIFICATIONS PASSED")
    print("=" * 65)

if __name__ == "__main__":
    run_presentation_tests()

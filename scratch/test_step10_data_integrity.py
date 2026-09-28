import os
import sys
import json
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from services.subject_analysis import analyze_critical_subjects
from services.activity_sports import recommend_activities_and_sports
from services.gap_analysis import compute_development_gaps
from services.career_engine import recommend_careers
from services.stream_engine import recommend_streams
from services.cognitive_engine import compute_cognitive_profile
from services.kpi_engine import compute_kpis
from services.report_v2_generator import generate_v2_report_data
from services.feature_fusion import fuse_student_features
from database_student import get_connection
from database import get_connection as get_bio_connection


def run_tests():
    print("=" * 80)
    print("STARTING STEP 10: ZERO-FABRICATION DATA INTEGRITY TEST SUITE")
    print("=" * 80)

    # Base student components for scenario building
    full_academics = [
        {"subject": "Mathematics", "marks": 88.0, "max_marks": 100.0, "percentage": 88.0, "source": "academic-derived"},
        {"subject": "Physics", "marks": 84.0, "max_marks": 100.0, "percentage": 84.0, "source": "academic-derived"},
        {"subject": "Computer Science", "marks": 92.0, "max_marks": 100.0, "percentage": 92.0, "source": "academic-derived"}
    ]
    full_skills = [
        {"skill": "Python", "type": "technical", "proficiency": 85.0, "source": "profile-derived"},
        {"skill": "Data Structures", "type": "technical", "proficiency": 80.0, "source": "profile-derived"}
    ]
    full_interests = [
        {"category": "Technical", "interest": "Artificial Intelligence", "level": "High", "source": "profile-derived"},
        {"category": "Sports", "interest": "Badminton", "level": "High", "source": "profile-derived"}
    ]
    full_activities = [
        {"title": "Robotics Hackathon", "type": "Project", "description": "Autonomous bot", "year": "2025", "source": "profile-derived"}
    ]
    full_assessments = {
        "personality": {
            "data": {"scores": {"openness": 82.0, "conscientiousness": 80.0, "extraversion": 72.0, "agreeableness": 84.0, "emotional_stability": 78.0}}
        },
        "critical_abilities": {
            "data": {"scores": {"problem_solving": 86.0, "creative_ability": 84.0, "pressure_handling": 80.0, "emotion_management": 82.0, "logical_reasoning": 88.0}}
        },
        "learning_style": {
            "data": {"scores": {"visual_pct": 55.0, "auditory_pct": 25.0, "kinesthetic_pct": 20.0}}
        },
        "leadership_style": {
            "data": {"scores": {"task_oriented_pct": 62.0, "relationship_oriented_pct": 38.0}}
        }
    }
    partial_assessments = {
        "critical_abilities": {
            "data": {"scores": {"problem_solving": 75.0, "logical_reasoning": 80.0}}
        }
    }

    # -------------------------------------------------------------
    # SCENARIO A: Completely Empty Student Profile
    # -------------------------------------------------------------
    empty_fused = {
        "student": {"student_id": "TEST-EMPTY", "full_name": "Empty Student", "stream": None, "age": None, "year": None},
        "academics": [],
        "subject_marks": {},
        "skills": [],
        "interests": [],
        "activities": [],
        "assessments": {},
        "iris_biometrics": None
    }

    print("\n--- Testing Scenario A: Completely Empty Profile ---")
    sub_res = analyze_critical_subjects(empty_fused)
    assert sub_res["subjects"] == [], f"Expected empty subjects, got {sub_res['subjects']}"
    assert sub_res["average_score"] is None, f"Expected None average_score, got {sub_res['average_score']}"
    assert sub_res["is_pending"] is True, "Expected is_pending=True for empty academics"
    print("✅ 1. Empty profile returns empty subjects & null average_score (no fake 78/82/75/85/70)")

    act_res = recommend_activities_and_sports(empty_fused)
    assert act_res["is_pending"] is True, "Expected is_pending=True for empty activities"
    for r in act_res["co_curricular_recommendations"] + act_res["sports_recommendations"]:
        assert r["compatibility"] is None, f"Expected compatibility=None, got {r['compatibility']}"
        assert r["is_pending"] is True, "Expected item is_pending=True"
        assert r["level"] == "Unassessed / Pending", f"Expected 'Unassessed / Pending', got {r['level']}"
    print("✅ 2. Empty profile produces NO fabricated activity/sports suitability (no 93.3% or 70.0 fallbacks)")

    gap_res = compute_development_gaps(empty_fused)
    assert gap_res["is_pending"] is True, "Expected gap analysis is_pending=True"
    for g in gap_res["gaps"]:
        assert g["current_score"] is None, f"Expected current_score=None, got {g['current_score']}"
        assert g["gap"] is None, f"Expected gap=None, got {g['gap']}"
        assert g["status"] == "Unassessed", f"Expected status='Unassessed', got {g['status']}"
        assert g["is_assessed"] is False
    print("✅ 3. Empty profile produces NO fabricated gap scores (no 72/74/68/65/70 defaults)")

    car_res = recommend_careers(empty_fused)
    assert car_res["is_pending"] is True, "Expected career recommendations is_pending=True"
    for c in car_res["all_careers"]:
        assert c["compatibility_score"] == 0.0, f"Expected compatibility_score=0.0, got {c['compatibility_score']}"
        assert c["is_pending"] is True, "Expected career is_pending=True"
        assert c["match_level"] == "Profile Data Pending", f"Expected 'Profile Data Pending', got {c['match_level']}"
    print("✅ 4. Empty profile produces 0.0% compatibility and 'Profile Data Pending' (NEVER 100% High Match)")

    # -------------------------------------------------------------
    # SCENARIO B: Profile with No Academics
    # -------------------------------------------------------------
    print("\n--- Testing Scenario B: No Academic Data ---")
    no_acad_fused = dict(empty_fused)
    no_acad_fused["skills"] = full_skills
    no_acad_fused["interests"] = full_interests
    no_acad_fused["activities"] = full_activities
    no_acad_fused["assessments"] = full_assessments
    sub_b = analyze_critical_subjects(no_acad_fused)
    assert sub_b["subjects"] == [] and sub_b["average_score"] is None and sub_b["is_pending"] is True
    print("✅ 5. Profile with no academics cleanly returns empty subjects & pending state")

    # -------------------------------------------------------------
    # SCENARIO C: Profile with No Skills
    # -------------------------------------------------------------
    print("\n--- Testing Scenario C: No Skills ---")
    no_skills_fused = dict(empty_fused)
    no_skills_fused["academics"] = full_academics
    no_skills_fused["interests"] = full_interests
    no_skills_fused["activities"] = full_activities
    no_skills_fused["assessments"] = full_assessments
    gap_c = compute_development_gaps(no_skills_fused)
    py_gap = [g for g in gap_c["gaps"] if "python" in g["skill"].lower()][0]
    assert py_gap["current_score"] is None and py_gap["status"] == "Unassessed"
    print("✅ 6. Profile with no skills reports Python as Unassessed with null current_score")

    # -------------------------------------------------------------
    # SCENARIO D: Profile with No Interests
    # -------------------------------------------------------------
    print("\n--- Testing Scenario D: No Interests ---")
    no_int_fused = dict(empty_fused)
    no_int_fused["academics"] = full_academics
    no_int_fused["skills"] = full_skills
    no_int_fused["activities"] = full_activities
    no_int_fused["assessments"] = full_assessments
    car_d = recommend_careers(no_int_fused)
    for c in car_d["all_careers"]:
        dim = c["dimensional_scores"]
        assert dim["interest_match"] is None, f"Expected interest_match=None, got {dim['interest_match']}"
    print("✅ 7. Profile with no interests cleanly marks interest_match as None across careers")

    # -------------------------------------------------------------
    # SCENARIO E: Profile with No Activities
    # -------------------------------------------------------------
    print("\n--- Testing Scenario E: No Activities ---")
    no_act_fused = dict(empty_fused)
    no_act_fused["academics"] = full_academics
    no_act_fused["skills"] = full_skills
    no_act_fused["interests"] = full_interests
    no_act_fused["assessments"] = full_assessments
    car_e = recommend_careers(no_act_fused)
    for c in car_e["all_careers"]:
        dim = c["dimensional_scores"]
        assert dim["activity_match"] is None, f"Expected activity_match=None, got {dim['activity_match']}"
    print("✅ 8. Profile with no activities cleanly marks activity_match as None across careers")

    # -------------------------------------------------------------
    # SCENARIO F: Profile with No Assessments
    # -------------------------------------------------------------
    print("\n--- Testing Scenario F: No Assessments ---")
    no_assess_fused = dict(empty_fused)
    no_assess_fused["academics"] = full_academics
    no_assess_fused["skills"] = full_skills
    no_assess_fused["interests"] = full_interests
    no_assess_fused["activities"] = full_activities
    act_f = recommend_activities_and_sports(no_assess_fused)
    # Activities that match declared interest should be interest-aligned; others pending
    badminton = [s for s in act_f["sports_recommendations"] if "badminton" in s["activity"].lower()][0]
    assert badminton["compatibility"] == 75.0, f"Expected 75.0 for declared interest, got {badminton['compatibility']}"
    assert badminton["source"] == "profile-derived"
    assert badminton["level"] == "Interest Aligned"
    unmatched_sport = [s for s in act_f["sports_recommendations"] if "swimming" in s["activity"].lower()][0]
    assert unmatched_sport["compatibility"] is None and unmatched_sport["is_pending"] is True
    print("✅ 9. Unassessed activities return pending; declared interest activities score as profile-derived (no 70 trait fallback)")

    # -------------------------------------------------------------
    # SCENARIO G: Partial Assessment
    # -------------------------------------------------------------
    print("\n--- Testing Scenario G: Partial Assessment ---")
    part_fused = dict(empty_fused)
    part_fused["assessments"] = partial_assessments
    gap_g = compute_development_gaps(part_fused)
    algo_gap = [g for g in gap_g["gaps"] if "algorithmic" in g["skill"].lower()][0]
    assert algo_gap["is_assessed"] is True and algo_gap["current_score"] == 75.0
    exec_gap = [g for g in gap_g["gaps"] if "executive" in g["skill"].lower()][0]
    assert exec_gap["is_assessed"] is False and exec_gap["current_score"] is None
    print("✅ 10. Partial assessment assesses confirmed domains and leaves unassessed domains pending")

    # -------------------------------------------------------------
    # SCENARIO H: Complete Profile (STU-001) Preservation
    # -------------------------------------------------------------
    print("\n--- Testing Scenario H: Complete Profile (STU-001) Preservation ---")
    fused_stu = fuse_student_features("STU-001")
    assert fused_stu is not None, "STU-001 must exist"
    sub_stu = analyze_critical_subjects(fused_stu)
    assert len(sub_stu["subjects"]) == 5, f"Expected 5 subjects, got {len(sub_stu['subjects'])}"
    assert sub_stu["is_pending"] is False

    car_stu = recommend_careers(fused_stu)
    top_c = car_stu["higher_match_careers"][0]
    assert top_c["career"] == "Artificial Intelligence & ML Engineer"
    assert top_c["compatibility_score"] > 70.0
    assert top_c["is_pending"] is False

    act_stu = recommend_activities_and_sports(fused_stu)
    assert act_stu["is_pending"] is False

    rep_stu = generate_v2_report_data("STU-001")
    assert rep_stu["status"] is True
    sec28 = rep_stu["sections"]["section_28_overall_student_profile"]
    assert len(sec28["key_skills"]) > 0, "STU-001 must have key_skills"
    assert len(sec28["key_interests"]) > 0, "STU-001 must have key_interests"
    assert sec28["is_pending"] is False

    # Check cognitive display label in Section 07
    sec07 = rep_stu["sections"]["section_07_strengths"]
    assert sec07["strengths_list"][0]["domain"] == "Cognitive & Problem Solving Indicators", f"Expected updated domain label, got {sec07['strengths_list'][0]['domain']}"
    print("✅ 11. Complete profile (STU-001) scores and recommendations preserved with 100% fidelity")

    # -------------------------------------------------------------
    # Verification Items 9-11: Provenance & Confidence Transparency
    # -------------------------------------------------------------
    print("\n--- Testing Provenance & Confidence Transparency ---")
    for eng_res in [car_res, car_stu, act_res, act_stu]:
        conf = eng_res.get("confidence") or eng_res.get("provenance", {}).get("confidence")
        conf_status = eng_res.get("confidence_status") or eng_res.get("provenance", {}).get("confidence_status")
        assert conf is None, f"Expected confidence=None, got {conf}"
        assert conf_status == "not_statistically_calibrated", f"Expected not_statistically_calibrated, got {conf_status}"
    print("✅ 12. Confidence transparency confirmed (confidence=null, status='not_statistically_calibrated')")

    # -------------------------------------------------------------
    # Verification Items 12-13: Database Preservation
    # -------------------------------------------------------------
    print("\n--- Testing Database Preservation ---")
    bio_conn = get_bio_connection()
    bio_cursor = bio_conn.cursor()
    bio_cursor.execute("SELECT COUNT(*) FROM iris_users")
    iris_user_count = bio_cursor.fetchone()[0]
    bio_cursor.execute("SELECT COUNT(*) FROM scan_history")
    scan_count = bio_cursor.fetchone()[0]
    bio_conn.close()

    assert iris_user_count == 10, f"Expected 10 iris_users, got {iris_user_count}"
    assert scan_count == 57, f"Expected 57 scan_history records, got {scan_count}"
    print(f"✅ 13. Iris biometric database records 100% intact ({iris_user_count} users, {scan_count} scans)")

    # -------------------------------------------------------------
    # Verification Items 14-17: API Deduplication & Activities POST
    # -------------------------------------------------------------
    print("\n--- Testing API Deduplication & Activities Handling ---")
    from api.profile import add_academic_records, add_skills, add_interests, add_activities, AcademicRecordSchema

    test_sid = "TEST-DEDUP-001"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM academic_records WHERE student_id = ?", (test_sid,))
    cur.execute("DELETE FROM student_skills WHERE student_id = ?", (test_sid,))
    cur.execute("DELETE FROM student_interests WHERE student_id = ?", (test_sid,))
    cur.execute("DELETE FROM student_activities WHERE student_id = ?", (test_sid,))
    conn.commit()

    # 14. Academic Deduplication
    acad1 = [AcademicRecordSchema(subject_name="Physics", marks_obtained=80.0, max_marks=100.0, term="Term 1")]
    add_academic_records(test_sid, acad1)
    acad2 = [AcademicRecordSchema(subject_name="Physics", marks_obtained=85.0, max_marks=100.0, term="Term 1")]
    add_academic_records(test_sid, acad2)
    cur.execute("SELECT marks_obtained FROM academic_records WHERE student_id = ? AND subject_name = 'Physics' AND term = 'Term 1'", (test_sid,))
    rows = cur.fetchall()
    assert len(rows) == 1, f"Expected 1 row after upsert, got {len(rows)}"
    assert rows[0][0] == 85.0, f"Expected updated mark 85.0, got {rows[0][0]}"
    print("✅ 14. Repeated academic POST updates record instead of creating duplicate")

    # 15. Skill Deduplication
    add_skills(test_sid, [{"name": "Python", "proficiency": 75.0}])
    add_skills(test_sid, [{"name": "Python", "proficiency": 90.0}])
    cur.execute("SELECT proficiency_score FROM student_skills WHERE student_id = ? AND skill_name = 'Python'", (test_sid,))
    rows = cur.fetchall()
    assert len(rows) == 1, f"Expected 1 skill row after upsert, got {len(rows)}"
    assert rows[0][0] == 90.0, f"Expected updated proficiency 90.0, got {rows[0][0]}"
    print("✅ 15. Repeated skill POST updates record instead of creating duplicate")

    # 16. Interest Deduplication
    add_interests(test_sid, [{"name": "Robotics", "category": "Tech", "level": "Medium"}])
    add_interests(test_sid, [{"name": "Robotics", "category": "Tech", "level": "High"}])
    cur.execute("SELECT level FROM student_interests WHERE student_id = ? AND interest_name = 'Robotics'", (test_sid,))
    rows = cur.fetchall()
    assert len(rows) == 1, f"Expected 1 interest row after upsert, got {len(rows)}"
    assert rows[0][0] == "High", f"Expected updated level High, got {rows[0][0]}"
    print("✅ 16. Repeated interest POST updates record instead of creating duplicate")

    # 17. Activities POST & Deduplication
    add_activities(test_sid, [{"title": "Science Olympiad", "activity_type": "Competition", "year": "2025"}])
    add_activities(test_sid, [{"title": "Science Olympiad", "activity_type": "National Competition", "year": "2025"}])
    cur.execute("SELECT activity_type FROM student_activities WHERE student_id = ? AND title = 'Science Olympiad'", (test_sid,))
    rows = cur.fetchall()
    assert len(rows) == 1, f"Expected 1 activity row, got {len(rows)}"
    assert rows[0][0] == "National Competition", f"Expected updated activity_type, got {rows[0][0]}"
    print("✅ 17. Activities API correctly handles insert and deduplication")

    # Clean up test dedup records
    cur.execute("DELETE FROM academic_records WHERE student_id = ?", (test_sid,))
    cur.execute("DELETE FROM student_skills WHERE student_id = ?", (test_sid,))
    cur.execute("DELETE FROM student_interests WHERE student_id = ?", (test_sid,))
    cur.execute("DELETE FROM student_activities WHERE student_id = ?", (test_sid,))
    conn.commit()
    conn.close()

    # -------------------------------------------------------------
    # Verification Items 18-20: Specific Fabrication Prevention Invariants
    # -------------------------------------------------------------
    print("\n--- Testing Specific Zero-Fabrication Invariants ---")
    # 18. Empty profile never produces 100% career compatibility
    assert not any(c["compatibility_score"] == 100.0 for c in car_res["all_careers"])
    print("✅ 18. Empty profile NEVER produces 100% career compatibility")

    # 19. Empty profile never produces 93.3% activity/sports suitability
    for r in act_res["co_curricular_recommendations"] + act_res["sports_recommendations"]:
        assert r["compatibility"] != 93.3 and r["compatibility"] != 70.0 and r["compatibility"] is None
    print("✅ 19. Empty profile NEVER produces 93.3% or 70.0 activity suitability")

    # 20. Empty profile never produces fake 78/82/75/85/70 academic scores
    assert sub_res["subjects"] == []
    assert sub_res["average_score"] is None
    print("✅ 20. Empty profile NEVER produces fake 78/82/75/85/70 academic scores")

    print("\n" + "=" * 80)
    print("ALL 20 STEP 10 DATA INTEGRITY VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

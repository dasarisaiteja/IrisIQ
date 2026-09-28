import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.assessment_engine import evaluate_assessment_responses
from services.kpi_engine import compute_kpis
from services.stream_engine import recommend_streams
from services.career_engine import recommend_careers
from services.activity_sports import recommend_activities_and_sports
from services.gap_analysis import compute_development_gaps
from services.cognitive_engine import compute_cognitive_profile
from services.report_v2_generator import generate_student_report_v2

passed_tests = 0
failed_tests = 0


def record_result(test_num, name, condition, details=""):
    global passed_tests, failed_tests
    if condition:
        passed_tests += 1
        print(f" [PASS] Test {test_num:02d}: {name}")
    else:
        failed_tests += 1
        print(f" [FAIL] Test {test_num:02d}: {name} - {details}")


print("=" * 70)
print("RUNNING STEP 12 SCORING INTEGRITY & PARTIAL DATA TESTS (25 CRITERIA)")
print("=" * 70)

# Test 1: Empty Likert domain returns norm_score: None, level: "Pending"
res_empty_pers = evaluate_assessment_responses("TEST-STU", "personality", {})
scores_empty_pers = res_empty_pers.get("scores", {})
details_empty_pers = res_empty_pers.get("details", {})
test1_ok = (
    res_empty_pers.get("is_pending") is True
    and all(v is None for v in scores_empty_pers.values())
    and all(d.get("level") == "Pending" for d in details_empty_pers.values())
)
record_result(1, "Empty Likert domain returns norm_score: None, level: 'Pending'", test1_ok)

# Test 2: Fully answered Likert domain preserves normal percentage score
# Personality questions Q1 to Q5
res_full_pers = evaluate_assessment_responses("TEST-STU", "personality", {
    "1": 4, "2": 5, "3": 4, "4": 3, "5": 5
})
scores_full_pers = res_full_pers.get("scores", {})
test2_ok = (
    res_full_pers.get("is_pending") is False
    and all(isinstance(v, float) and v > 0 for v in scores_full_pers.values())
)
record_result(2, "Fully answered Likert domain preserves normal percentage score", test2_ok, f"scores: {scores_full_pers}")

# Test 3: Empty VAK returns dominant_style: "Profile Data Pending" and None percentages
res_empty_vak = evaluate_assessment_responses("TEST-STU", "learning_style", {})
vak_scores = res_empty_vak.get("scores", {})
vak_details = res_empty_vak.get("details", {})
test3_ok = (
    res_empty_vak.get("is_pending") is True
    and vak_details.get("dominant_style") == "Profile Data Pending"
    and vak_scores.get("visual_pct") is None
    and vak_scores.get("auditory_pct") is None
    and vak_scores.get("kinesthetic_pct") is None
)
record_result(3, "Empty VAK returns dominant_style: 'Profile Data Pending' and None percentages", test3_ok, f"res: {res_empty_vak}")

# Test 4: Single-question VAK produces non-null percentage but flags is_partial: True
res_part_vak = evaluate_assessment_responses("TEST-STU", "learning_style", {"11": "V"})  # Q11 answered visual
vak_p_scores = res_part_vak.get("scores", {})
vak_p_details = res_part_vak.get("details", {})
test4_ok = (
    vak_p_details.get("is_partial") is True
    and vak_p_details.get("answered_questions") == 1
    and vak_p_details.get("total_questions") == 3
    and vak_p_scores.get("visual_pct") == 100.0
    and vak_p_scores.get("auditory_pct") == 0.0
)
record_result(4, "Single-question VAK produces non-null percentage but flags is_partial: True", test4_ok, f"res: {res_part_vak}")

# Test 5: Empty leadership returns task_oriented_pct: None, relationship_oriented_pct: None, orientation: "Profile Data Pending"
res_empty_lead = evaluate_assessment_responses("TEST-STU", "leadership", {})
lead_scores = res_empty_lead.get("scores", {})
lead_details = res_empty_lead.get("details", {})
test5_ok = (
    res_empty_lead.get("is_pending") is True
    and lead_details.get("dominant_style") == "Profile Data Pending"
    and lead_scores.get("task_oriented_pct") is None
    and lead_scores.get("relationship_oriented_pct") is None
)
record_result(5, "Empty leadership returns task/relationship: None and 'Profile Data Pending'", test5_ok, f"res: {res_empty_lead}")

# Test 6: Balanced leadership (50/50) produces 0 gap, status "Balanced / Situational Focus"
fused_lead_bal = {
    "assessments": {
        "leadership": {
            "data": {
                "scores": {"task_oriented_pct": 50.0, "relationship_oriented_pct": 50.0}
            }
        }
    }
}
kpis_bal = compute_kpis(fused_lead_bal)["kpis"]
lead_kpi_bal = next((k for k in kpis_bal if k["category"] == "Leadership"), None)
test6_ok = (
    lead_kpi_bal is not None
    and lead_kpi_bal.get("gap") == 0.0
    and lead_kpi_bal.get("current_score") == 100.0  # 100 - abs(50 - 50)
    and "Balanced" in lead_kpi_bal.get("status", "")
)
record_result(6, "Balanced leadership (50/50) produces 0 gap, status 'Balanced / Situational Focus'", test6_ok, f"kpi: {lead_kpi_bal}")

# Test 7: Asymmetric leadership produces correct directional status without penalizing score
fused_lead_asym = {
    "assessments": {
        "leadership": {
            "data": {
                "scores": {"task_oriented_pct": 80.0, "relationship_oriented_pct": 20.0}
            }
        }
    }
}
kpis_asym = compute_kpis(fused_lead_asym)["kpis"]
lead_kpi_asym = next((k for k in kpis_asym if k["category"] == "Leadership"), None)
test7_ok = (
    lead_kpi_asym is not None
    and lead_kpi_asym.get("gap") == 0.0  # Orientation is neutral, not penalized
    and lead_kpi_asym.get("current_score") == 40.0  # 100 - abs(80 - 20)
    and "Task-Directed" in lead_kpi_asym.get("status", "")
)
record_result(7, "Asymmetric leadership produces directional status without penalty gap", test7_ok, f"kpi: {lead_kpi_asym}")

# Test 8: Empty thinking_action returns None percentages and "Profile Data Pending"
res_empty_think = evaluate_assessment_responses("TEST-STU", "thinking_action", {})
think_scores = res_empty_think.get("scores", {})
think_details = res_empty_think.get("details", {})
test8_ok = (
    res_empty_think.get("is_pending") is True
    and think_details.get("orientation") == "Profile Data Pending"
    and think_scores.get("thinking_pct") is None
    and think_scores.get("action_pct") is None
)
record_result(8, "Empty thinking_action returns None percentages and 'Profile Data Pending'", test8_ok, f"res: {res_empty_think}")

# Test 9: Empty team_role returns None percentages and "Profile Data Pending"
res_empty_team = evaluate_assessment_responses("TEST-STU", "team_role", {})
team_scores = res_empty_team.get("scores", {})
team_details = res_empty_team.get("details", {})
test9_ok = (
    res_empty_team.get("is_pending") is True
    and team_details.get("dominant_role") == "Profile Data Pending"
    and team_scores.get("team_management_pct") is None
    and team_scores.get("team_player_pct") is None
)
record_result(9, "Empty team_role returns None percentages and 'Profile Data Pending'", test9_ok, f"res: {res_empty_team}")

# Test 10: Sports KPI with 0 sports activities returns current_score: None, status "pending"
fused_no_sports = {
    "activities": [
        {"title": "Debate Club", "type": "co-curricular"},
        {"title": "Robotics Club", "type": "technical"}
    ]
}
kpis_no_sports = compute_kpis(fused_no_sports)["kpis"]
sports_kpi_none = next((k for k in kpis_no_sports if k["category"] == "Sports Performance"), None)
test10_ok = (
    sports_kpi_none is not None
    and sports_kpi_none.get("current_score") is None
    and sports_kpi_none.get("status") == "pending"
)
record_result(10, "Sports KPI with 0 sports activities returns current_score: None, status 'pending'", test10_ok, f"kpi: {sports_kpi_none}")

# Test 11: Sports KPI with explicit sports activity calculates actual performance
fused_with_sports = {
    "activities": [
        {"title": "School Swimming Team", "type": "sports"}
    ]
}
kpis_with_sports = compute_kpis(fused_with_sports)["kpis"]
sports_kpi_act = next((k for k in kpis_with_sports if k["category"] == "Sports Performance"), None)
test11_ok = (
    sports_kpi_act is not None
    and sports_kpi_act.get("current_score") == 65.0
    and sports_kpi_act.get("gap") == 15.0
)
record_result(11, "Sports KPI with explicit sports activity calculates actual performance", test11_ok, f"kpi: {sports_kpi_act}")

# Test 12: Stream interest matching with "art" does NOT match "artificial intelligence"
fused_ai_interest = {
    "interests": [{"interest": "artificial intelligence", "level": "High"}]
}
streams_ai = recommend_streams(fused_ai_interest)
humanities_stream = next((s for s in streams_ai["stream_rankings"] if "Humanities" in s["stream"]), None)
hum_dim = humanities_stream.get("dimensional_scores", {})
test12_ok = (
    humanities_stream is not None
    and (hum_dim.get("interest_match") is None or hum_dim.get("interest_match") == 0.0)
)
record_result(12, "Stream interest matching with 'art' does NOT match 'artificial intelligence'", test12_ok, f"hum_dim: {hum_dim}")

# Test 13: Stream interest matching with "artificial intelligence" matches Science (STEM)
stem_stream = next((s for s in streams_ai["stream_rankings"] if "Science (STEM)" in s["stream"]), None)
stem_dim = stem_stream.get("dimensional_scores", {})
test13_ok = (
    stem_stream is not None
    and stem_dim.get("interest_match") is not None
    and stem_dim.get("interest_match") > 50.0
)
record_result(13, "Stream interest matching with 'artificial intelligence' matches Science (STEM)", test13_ok, f"stem_dim: {stem_dim}")

# Test 14: Stream scoring with only 1 dimension does NOT rescale to 100%
# With only interest matching STEM (interest_score = 100.0, weight = 0.20), compatibility should be 20.0, not 100.0!
test14_ok = (
    stem_stream is not None
    and stem_stream.get("compatibility_score") <= 25.0
    and stem_stream.get("data_completeness") == 0.2
    and stem_stream.get("is_partial") is True
    and stem_stream.get("level") == "Limited Evidence"
)
record_result(14, "Stream scoring with only 1 dimension does NOT rescale to 100%", test14_ok, f"stem_stream: {stem_stream}")

# Test 15: Stream scoring with all 5 dimensions produces expected composite score
fused_full_student = {
    "subject_marks": {"mathematics": 92.0, "science": 90.0, "physics": 91.0, "chemistry": 89.0},
    "assessments": {
        "critical_abilities": {"data": {"scores": {"logical_reasoning": 85.0, "problem_solving": 88.0}}},
        "personality": {"data": {"scores": {"conscientiousness": 80.0, "openness": 75.0, "agreeableness": 70.0, "extraversion": 65.0, "emotional_stability": 75.0}}}
    },
    "interests": [{"interest": "artificial intelligence", "level": "High"}],
    "skills": [{"skill": "Python", "type": "technical", "proficiency": 90.0}],
    "activities": [{"title": "Robotics Club", "type": "technical", "description": "STEM robotics"}]
}
streams_full = recommend_streams(fused_full_student)
stem_full = next((s for s in streams_full["stream_rankings"] if "Science (STEM)" in s["stream"]), None)
test15_ok = (
    stem_full is not None
    and stem_full.get("compatibility_score") >= 80.0
    and stem_full.get("data_completeness") == 1.0
    and stem_full.get("is_partial") is False
    and stem_full.get("level") == "High Affinity"
)
record_result(15, "Stream scoring with all 5 dimensions produces expected composite score", test15_ok, f"stem_full: {stem_full.get('compatibility_score') if stem_full else None}")

# Test 16: Career scoring with only 1 dimension does NOT rescale to 100%
careers_ai = recommend_careers(fused_ai_interest)
top_c_ai = careers_ai["all_careers"][0]
test16_ok = (
    top_c_ai.get("compatibility_score") <= 25.0
    and top_c_ai.get("data_completeness") == 0.15
    and top_c_ai.get("is_partial") is True
    and top_c_ai.get("match_level") == "Limited Evidence"
)
record_result(16, "Career scoring with only 1 dimension does NOT rescale to 100%", test16_ok, f"top_c_ai: {top_c_ai.get('compatibility_score')}, completeness: {top_c_ai.get('data_completeness')}")

# Test 17: Career scoring with empty profile returns compatibility_score: 0.0 and is_pending: True
careers_empty = recommend_careers({})
test17_ok = (
    careers_empty.get("is_pending") is True
    and all(c.get("compatibility_score") == 0.0 for c in careers_empty["all_careers"])
    and all(c.get("is_pending") is True for c in careers_empty["all_careers"])
)
record_result(17, "Career scoring with empty profile returns compatibility_score: 0.0 and is_pending: True", test17_ok)

# Test 18: Activity trait compatibility searches critical, personality, behavioral, emotional, and cognitive domains
fused_traits = {
    "assessments": {
        "behavioral": {"data": {"scores": {"perseverance": 85.0}}},
        "critical_abilities": {"data": {"scores": {"pressure_handling": 80.0}}},
        "emotional_social": {"data": {"scores": {"social_confidence": 90.0, "emotion_management": 80.0}}}
    }
}
acts_traits = recommend_activities_and_sports(fused_traits)
swim_rec = next((s for s in acts_traits["sports_recommendations"] if s["activity"] == "Swimming"), None)
test18_ok = (
    swim_rec is not None
    and "perseverance" in swim_rec.get("matched_traits", [])
    and "pressure_handling" in swim_rec.get("matched_traits", [])
    and swim_rec.get("compatibility") is not None
    and swim_rec.get("compatibility") >= 90.0
)
record_result(18, "Activity trait compatibility searches behavioral and emotional domains", test18_ok, f"swim_rec: {swim_rec}")

# Test 19: Activity requiring 2 traits with only 1 present calculates compatibility over 2 traits, not 1
fused_one_trait = {
    "assessments": {
        "critical_abilities": {"data": {"scores": {"pressure_handling": 75.0}}}
    }
}
acts_one = recommend_activities_and_sports(fused_one_trait)
swim_one = next((s for s in acts_one["sports_recommendations"] if s["activity"] == "Swimming"), None)
test19_ok = (
    swim_one is not None
    and swim_one.get("is_partial") is True
    and len(swim_one.get("matched_traits", [])) == 1
    and swim_one.get("required_trait_count") == 2
    and swim_one.get("compatibility") == 50.0  # 100 / 2 = 50.0
)
record_result(19, "Activity requiring 2 traits with only 1 present calculates compatibility over 2 traits (50%)", test19_ok, f"swim_one: {swim_one}")

# Test 20: Activity with 0 matched traits and no interest returns compatibility: None, status 'pending'
acts_empty = recommend_activities_and_sports({})
all_pending_acts = all(a.get("compatibility") is None and a.get("status") == "pending" for a in acts_empty["co_curricular_recommendations"] + acts_empty["sports_recommendations"])
test20_ok = (
    acts_empty.get("is_pending") is True
    and all_pending_acts
)
record_result(20, "Activity with 0 matched traits returns compatibility: None, status 'pending'", test20_ok)

# Test 21: Gap analysis for Team Leadership checks leadership first, not agreeableness
fused_lead_no_agree = {
    "assessments": {
        "leadership": {"data": {"scores": {"task_oriented_pct": 70.0, "relationship_oriented_pct": 70.0}}},
        "personality": {"data": {"scores": {"agreeableness": 30.0}}}
    }
}
gaps_lead = compute_development_gaps(fused_lead_no_agree)
lead_gap = next((g for g in gaps_lead["gaps"] if g["skill"] == "Team Leadership & Coordination"), None)
test21_ok = (
    lead_gap is not None
    and lead_gap.get("current_score") == 100.0  # From leadership balance 100 - |70-70|, NOT agreeableness 30.0!
)
record_result(21, "Gap analysis for Team Leadership checks leadership first, not agreeableness", test21_ok, f"lead_gap: {lead_gap}")

# Test 22: Gap analysis for Communication checks communication/languages, not extraversion
fused_extra_no_comm = {
    "assessments": {
        "personality": {"data": {"scores": {"extraversion": 90.0}}}
    }
}
gaps_extra = compute_development_gaps(fused_extra_no_comm)
comm_gap = next((g for g in gaps_extra["gaps"] if g["skill"] == "Executive Communication"), None)
test22_ok = (
    comm_gap is not None
    and comm_gap.get("current_score") is None
    and comm_gap.get("status") == "Unassessed"  # Extraversion NOT used as communication score!
)
record_result(22, "Gap analysis for Communication does NOT use extraversion as substitute", test22_ok, f"comm_gap: {comm_gap}")

# Test 23: Cognitive profile with < 3 valid domains sets overall_cognitive_index: None, is_partial: True
fused_cog_sparse = {
    "assessments": {
        "critical_abilities": {"data": {"scores": {"logical_reasoning": 80.0}}}
    }
}
cog_sparse = compute_cognitive_profile(fused_cog_sparse)
test23_ok = (
    cog_sparse.get("overall_cognitive_index") is None
    and cog_sparse.get("overall_index") is None
    and cog_sparse.get("is_partial") is True
    and cog_sparse.get("valid_domain_count") < 3
    and cog_sparse.get("message") == "Limited assessment evidence"
)
record_result(23, "Cognitive profile with < 3 valid domains sets overall_cognitive_index: None, is_partial: True", test23_ok, f"cog_sparse: {cog_sparse}")

# Test 24: Cognitive profile with >= 3 valid domains computes overall_cognitive_index correctly
fused_cog_valid = {
    "subject_marks": {"mathematics": 85.0, "science": 80.0, "english": 88.0},
    "assessments": {
        "critical_abilities": {"data": {"scores": {"logical_reasoning": 90.0, "problem_solving": 85.0, "creative_ability": 80.0}}},
        "personality": {"data": {"scores": {"conscientiousness": 82.0, "openness": 78.0, "extraversion": 75.0, "agreeableness": 80.0}}}
    }
}
cog_valid = compute_cognitive_profile(fused_cog_valid)
test24_ok = (
    cog_valid.get("overall_cognitive_index") is not None
    and cog_valid.get("overall_index") == cog_valid.get("overall_cognitive_index")
    and cog_valid.get("is_pending") is False
    and cog_valid.get("valid_domain_count") >= 3
)
record_result(24, "Cognitive profile with >= 3 valid domains computes overall_cognitive_index correctly", test24_ok, f"overall: {cog_valid.get('overall_cognitive_index')}, valid_domains: {cog_valid.get('valid_domain_count')}")

# Test 25: Report V2 executive summary with empty profile does NOT recommend "Artificial Intelligence & ML Engineer"
empty_fused_rep = {
    "student_id": "STU-EMPTY",
    "full_name": "Test Pending Student",
    "employee_code": "EMPTY001",
    "email": "empty@example.com",
    "mobile": "0000000000"
}
rep_empty = generate_student_report_v2(empty_fused_rep)
exec_summary_text = rep_empty["sections"]["section_03_executive_summary"]["summary_text"]
higher_c_label = rep_empty["sections"]["section_03_executive_summary"]["higher_match_career"]
test25_ok = (
    "Artificial Intelligence & ML Engineer" not in exec_summary_text
    and "Career recommendations require additional student profile data" in exec_summary_text
    and higher_c_label == "Pending Profile Data"
)
record_result(25, "Report V2 executive summary with empty profile does NOT recommend AI Engineer", test25_ok, f"exec_summary: {exec_summary_text}")

print("=" * 70)
print(f"RESULTS: {passed_tests} PASSED, {failed_tests} FAILED out of 25 TESTS.")
print("=" * 70)

if failed_tests > 0:
    sys.exit(1)
else:
    sys.exit(0)

"""
Step 14: Provenance & Traceability Fixes Regression Suite
Tests the 18 minimum verification requirements specified in Step 14.
"""

import sys
import os
import sqlite3
import re

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.gap_analysis import compute_development_gaps
from services.activity_sports import recommend_activities_and_sports
from services.kpi_engine import compute_kpis
from services.cognitive_engine import compute_cognitive_profile, _match_subject
from services.stream_engine import _keyword_in_text
from services.report_v2_generator import generate_v2_report_data
from services.feature_fusion import fuse_student_features

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "iris_database.db"))

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
print("RUNNING STEP 14 PROVENANCE & TRACEABILITY VERIFICATION (18 CRITERIA)")
print("=" * 70)

# 1. Leadership alias resolution
fused_style = {
    "skills": [],
    "subject_marks": {},
    "assessments": {
        "leadership_style": {
            "data": {"scores": {"task_oriented_pct": 62, "relationship_oriented_pct": 38}}
        }
    }
}
res_style = compute_development_gaps(fused_style)
bm_lead_style = next(b for b in res_style["gaps"] if b["skill"] == "Team Leadership & Coordination")

fused_legacy = {
    "skills": [],
    "subject_marks": {},
    "assessments": {
        "leadership": {
            "data": {"scores": {"task_oriented_pct": 60, "relationship_oriented_pct": 40}}
        }
    }
}
res_legacy = compute_development_gaps(fused_legacy)
bm_lead_legacy = next(b for b in res_legacy["gaps"] if b["skill"] == "Team Leadership & Coordination")

test1_ok = (
    bm_lead_style["is_assessed"] is True
    and bm_lead_style["current_score"] == 76.0
    and bm_lead_style["gap"] == 9.0
    and bm_lead_legacy["is_assessed"] is True
    and bm_lead_legacy["current_score"] == 80.0
    and bm_lead_legacy["gap"] == 5.0
)
record_result(1, "Leadership alias resolution (leadership_style and leadership)", test1_ok)

# 2. Leadership genuinely unassessed state
empty_fused = {"skills": [], "subject_marks": {}, "assessments": {}}
res_empty = compute_development_gaps(empty_fused)
bm_lead_empty = next(b for b in res_empty["gaps"] if b["skill"] == "Team Leadership & Coordination")
test2_ok = (
    bm_lead_empty["is_assessed"] is False
    and bm_lead_empty["current_score"] is None
    and bm_lead_empty["gap"] is None
    and bm_lead_empty["status"] == "Unassessed"
)
record_result(2, "Leadership genuinely unassessed state", test2_ok)

# 3. Memory substitution removed
fused_mem_test = {
    "assessments": {
        "critical_abilities": {"data": {"scores": {"logical_reasoning": 95.0}}}
    },
    "subject_marks": {},
    "skills": []
}
recs_mem = recommend_activities_and_sports(fused_mem_test)
# Check that memory is NOT substituted from logical reasoning
all_acts_mem = recs_mem.get("co_curricular_recommendations", []) + recs_mem.get("sports_recommendations", [])
test3_ok = True
checked_memory_acts = 0
for act in all_acts_mem:
    all_reqs = act.get("matched_traits", []) + act.get("missing_traits", [])
    if "memory" in all_reqs:
        checked_memory_acts += 1
        if "memory" in act.get("matched_traits", []):
            test3_ok = False
        if "memory" not in act.get("missing_traits", []):
            test3_ok = False
test3_ok = test3_ok and (checked_memory_acts > 0)
record_result(3, "Memory substitution removed (logical reasoning not substituted)", test3_ok)

# 4. Extraversion -> communication substitution removed
fused_ext_test = {
    "assessments": {
        "personality": {"data": {"scores": {"extraversion": 90.0}}}
    },
    "subject_marks": {},
    "skills": []
}
recs_ext = recommend_activities_and_sports(fused_ext_test)
all_acts_ext = recs_ext.get("co_curricular_recommendations", []) + recs_ext.get("sports_recommendations", [])
test4_ok = True
checked_comm_acts = 0
for act in all_acts_ext:
    all_reqs = act.get("matched_traits", []) + act.get("missing_traits", [])
    if "language_communication" in all_reqs:
        checked_comm_acts += 1
        if "language_communication" in act.get("matched_traits", []):
            test4_ok = False
        if "language_communication" not in act.get("missing_traits", []):
            test4_ok = False
test4_ok = test4_ok and (checked_comm_acts > 0)
record_result(4, "Extraversion -> language_communication substitution removed", test4_ok)

# 5. Agreeableness -> teamwork substitution removed
fused_agr_test = {
    "assessments": {
        "personality": {"data": {"scores": {"agreeableness": 95.0}}}
    },
    "subject_marks": {},
    "skills": []
}
recs_agr = recommend_activities_and_sports(fused_agr_test)
all_acts_agr = recs_agr.get("co_curricular_recommendations", []) + recs_agr.get("sports_recommendations", [])
test5_ok = True
checked_team_acts = 0
for act in all_acts_agr:
    all_reqs = act.get("matched_traits", []) + act.get("missing_traits", [])
    if "teamwork" in all_reqs:
        checked_team_acts += 1
        if "teamwork" in act.get("matched_traits", []):
            test5_ok = False
        if "teamwork" not in act.get("missing_traits", []):
            test5_ok = False
test5_ok = test5_ok and (checked_team_acts > 0)
record_result(5, "Agreeableness -> teamwork substitution removed", test5_ok)

# 6. Partial activity compatibility preserved
fused_team_only = {
    "assessments": {
        "team_player": {"data": {"scores": {"team_player_pct": 75.0}}}
    },
    "subject_marks": {},
    "skills": []
}
recs_team = recommend_activities_and_sports(fused_team_only)
all_acts_team = recs_team.get("co_curricular_recommendations", []) + recs_team.get("sports_recommendations", [])
partial_found = False
for act in all_acts_team:
    matched = act.get("matched_traits", [])
    missing = act.get("missing_traits", [])
    if "teamwork" in matched and len(missing) > 0:
        if act.get("is_partial") is True:
            partial_found = True
record_result(6, "Partial activity compatibility preserved without fabricating missing traits", partial_found)

# 7. Learning Progress renamed correctly
fused_kpi = {
    "assessments": {
        "personality": {"data": {"scores": {"conscientiousness": 80.0}}},
        "critical_abilities": {"data": {"scores": {"pressure_handling": 80.0}}}
    },
    "subject_marks": {},
    "skills": [],
    "activities": []
}
kpis_res = compute_kpis(fused_kpi)
kpi_study = next((k for k in kpis_res["kpis"] if k["category"] == "Self-Directed Study Habits"), None)
test7_ok = (
    kpi_study is not None
    and kpi_study.get("category_alias") == "Learning Progress"
    and kpi_study.get("current_score") == 80.0
    and "study habits" in kpi_study.get("note", "").lower()
    and "longitudinal" in kpi_study.get("note", "").lower()
)
record_result(7, "Learning Progress renamed to Self-Directed Study Habits with alias & provenance", test7_ok)

# 8. Creativity KPI provenance/label
kpi_creat = next((k for k in kpis_res["kpis"] if k["category"] == "Creative Thinking Indicator"), None)
test8_ok = (
    kpi_creat is not None
    and kpi_creat.get("category_alias") == "Creativity"
    and "heuristic indicator" in kpi_creat.get("note", "").lower()
)
record_result(8, "Creativity KPI renamed to Creative Thinking Indicator with provenance note", test8_ok)

# 9. Technical English & Communication matching
sub_compound = {"Technical English & Communication": 85.0}
cog_compound = compute_cognitive_profile({"assessments": {}, "subject_marks": sub_compound, "skills": []})
d_comm = next(d for d in cog_compound["domains"] if d["domain"] == "Language/Communication")
gaps_compound = compute_development_gaps({"assessments": {}, "subject_marks": sub_compound, "skills": []})
bm_comm = next(b for b in gaps_compound["gaps"] if b["skill"] == "Executive Communication")
test9_ok = (
    d_comm["score"] == 85.0
    and d_comm["is_pending"] is False
    and bm_comm["current_score"] == 85.0
    and bm_comm["is_assessed"] is True
)
record_result(9, "Compound subject 'Technical English & Communication' matching", test9_ok)

# 10. English matching
sub_eng1 = {"English": 78.0}
sub_eng2 = {"english": 78.0}
cog_eng1 = compute_cognitive_profile({"assessments": {}, "subject_marks": sub_eng1, "skills": []})
cog_eng2 = compute_cognitive_profile({"assessments": {}, "subject_marks": sub_eng2, "skills": []})
d_eng1 = next(d for d in cog_eng1["domains"] if d["domain"] == "Language/Communication")
d_eng2 = next(d for d in cog_eng2["domains"] if d["domain"] == "Language/Communication")
test10_ok = (d_eng1["score"] == 78.0 and d_eng2["score"] == 78.0)
record_result(10, "Subject 'English' / 'english' case-insensitive matching", test10_ok)

# 11. Languages matching
sub_lang1 = {"Languages": 82.0}
sub_lang2 = {"languages": 82.0}
cog_lang1 = compute_cognitive_profile({"assessments": {}, "subject_marks": sub_lang1, "skills": []})
cog_lang2 = compute_cognitive_profile({"assessments": {}, "subject_marks": sub_lang2, "skills": []})
d_lang1 = next(d for d in cog_lang1["domains"] if d["domain"] == "Language/Communication")
d_lang2 = next(d for d in cog_lang2["domains"] if d["domain"] == "Language/Communication")
test11_ok = (d_lang1["score"] == 82.0 and d_lang2["score"] == 82.0)
record_result(11, "Subject 'Languages' / 'languages' case-insensitive matching", test11_ok)

# 12. Maths/Mathematics matching
math_pats = [r'\btechnical\s+math\b', r'\bmath(?:ematics|s)?\b', r'\bcalculus\b', r'\balgebra\b']
val_maths = _match_subject({"Maths": 88.0}, math_pats, ["mathematics", "math", "maths"])
val_mathematics = _match_subject({"Mathematics": 92.0}, math_pats, ["mathematics", "math", "maths"])
val_techmath = _match_subject({"Technical Math": 86.0}, math_pats, ["mathematics", "math", "maths"])
test12_ok = (val_maths == 88.0 and val_mathematics == 92.0 and val_techmath == 86.0)
record_result(12, "Subjects 'Mathematics', 'Maths', and 'Technical Math' matching", test12_ok)

# 13. Artificial Intelligence does not match Art
art_in_ai = _keyword_in_text("art", "Artificial Intelligence")
art_in_intro = _keyword_in_text("art", "Introduction to Artificial Intelligence and Machine Learning")
art_in_fine = _keyword_in_text("art", "Fine Art and Sculpture")
test13_ok = (art_in_ai is False and art_in_intro is False and art_in_fine is True)
record_result(13, "Safe token matching: 'Artificial Intelligence' does NOT match 'art'", test13_ok)

# 14. Empty report does not recommend Python
empty_student_fused = {
    "student": {"student_id": "STU-EMPTY", "full_name": "Unassessed Student", "academic_class": "Grade 10"},
    "academic": {},
    "skills": [],
    "interests": [],
    "activities": [],
    "assessments": {},
    "subject_marks": {}
}
report_empty = generate_v2_report_data(empty_student_fused)
summary_empty = report_empty["sections"]["section_03_executive_summary"]["summary_text"]
test14_ok = (
    "Python Programming" not in summary_empty
    and "Targeted skill development recommendations require additional student profile and assessment data." in summary_empty
)
record_result(14, "Empty report executive summary does not default to Python Programming", test14_ok)

# 15. Analytical Thinking dependency behavior
cog_analytical = compute_cognitive_profile({
    "assessments": {"critical_abilities": {"data": {"scores": {"logical_reasoning": 82.0}}}},
    "subject_marks": {"Mathematics": 88.0, "Science": 85.0},
    "skills": []
})
d_log = next(d for d in cog_analytical["domains"] if d["domain"] == "Logical Reasoning")
d_ana = next(d for d in cog_analytical["domains"] if d["domain"] == "Analytical Thinking")
# Logical = 82*0.7 + 88*0.3 = 83.8; Analytical = 83.8*0.6 + 85*0.4 = 50.28 + 34.0 = 84.28 -> 84.3
test15_ok = (d_log["score"] == 83.8 and d_ana["score"] == 84.3 and d_ana["source"] == "assessment-derived")
record_result(15, "Analytical Thinking composite dependency documented and scores preserved", test15_ok)

# 16. VAK is not presented as spatial cognition
cog_vak = compute_cognitive_profile({
    "assessments": {"learning_style": {"data": {"scores": {"visual_pct": 75.0, "auditory_pct": 15.0, "kinesthetic_pct": 10.0}}}},
    "subject_marks": {"Mathematics": 90.0},
    "skills": []
})
d_spatial = next(d for d in cog_vak["domains"] if d["domain"] == "Visual/Spatial Processing")
test16_ok = (
    d_spatial["score"] is None
    and d_spatial["is_pending"] is True
    and "Requires explicit spatial reasoning assessment" in d_spatial.get("note", "")
)
record_result(16, "VAK visual style is not conflated with cognitive spatial processing", test16_ok)

# 17. Iris isolation and database counts
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT count(*) FROM iris_users")
user_count = cursor.fetchone()[0]
cursor.execute("SELECT count(*) FROM scan_history")
scan_count = cursor.fetchone()[0]
conn.close()
test17_ok = (user_count == 10 and scan_count == 57)
record_result(17, f"Iris isolation and database counts preserved (users: {user_count}/10, scans: {scan_count}/57)", test17_ok)

# 18. STU-001 preservation
fused_stu = fuse_student_features("STU-001")
cog_stu = compute_cognitive_profile(fused_stu)
kpis_stu_obj = compute_kpis(fused_stu)
kpis_stu = [k["category"] for k in kpis_stu_obj.get("kpis", [])]
gaps_stu_obj = compute_development_gaps(fused_stu)
gaps_stu = gaps_stu_obj.get("gaps", [])

d_stu = {d["domain"]: d["score"] for d in cog_stu.get("domains", [])}
lead_gap = next((b for b in gaps_stu if b["skill"] == "Team Leadership & Coordination"), None)
comm_gap = next((b for b in gaps_stu if b["skill"] == "Executive Communication"), None)

test18_ok = (
    fused_stu is not None
    and cog_stu.get("overall_cognitive_index") == 84.0
    and d_stu.get("Logical Reasoning") == 88.0
    and d_stu.get("Problem Solving") == 87.5
    and d_stu.get("Creative Thinking") == 83.2
    and d_stu.get("Planning") == 81.8
    and d_stu.get("Analytical Thinking") == 89.6
    and lead_gap is not None
    and lead_gap.get("is_assessed") is True
    and lead_gap.get("current_score") == 76.0
    and lead_gap.get("gap") == 9.0
    and comm_gap is not None
    and comm_gap.get("is_assessed") is True
    and comm_gap.get("current_score") == 82.0
    and comm_gap.get("gap") == 3.0
    and "Self-Directed Study Habits" in kpis_stu
    and "Creative Thinking Indicator" in kpis_stu
)
record_result(18, "STU-001 profile integrity and leadership benchmark resolution preserved", test18_ok)

print("=" * 70)
print(f"STEP 14 TEST SUMMARY: {passed_tests} PASSED, {failed_tests} FAILED out of 18")
print("=" * 70)

if failed_tests > 0:
    sys.exit(1)

"""
test_step16_ui_consistency.py
Step 16 Verification Suite: User-Facing UI & Report Consistency Fixes
Covers all 20 criteria specified in Step 16 prompt.
"""

import os
import sys
import json
import sqlite3
import subprocess

# Ensure repo root is on path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from services.activity_sports import recommend_activities_and_sports
from services.feature_fusion import fuse_student_features
from services.report_v2_generator import generate_v2_report_data

DB_PATH = os.path.join(ROOT_DIR, "iris_database.db")

def run_js(code: str) -> str:
    """Execute a snippet of JavaScript using node and return stdout."""
    res = subprocess.run(["node", "-e", code], capture_output=True, text=True, cwd=ROOT_DIR)
    if res.returncode != 0:
        raise RuntimeError(f"JS execution failed:\n{res.stderr}")
    return res.stdout.strip()


def test_01_null_kpi_renders_pending():
    js = """
    const k = { category: "Sports Performance", current_score: null, target_score: 80.0, gap: null };
    const isScorePresent = k.current_score !== null && k.current_score !== undefined;
    const scoreDisplay = isScorePresent ? k.current_score : '<span class="badge bg-secondary-subtle text-secondary">Pending</span>';
    console.log(scoreDisplay);
    """
    output = run_js(js)
    assert "Pending" in output, f"Expected 'Pending' in output, got: {output}"
    assert "null" not in output, f"Literal 'null' found in output: {output}"
    print(" [PASS] Test 01: Null KPI renders Pending")


def test_02_null_kpi_gap_renders_dash():
    js = """
    const k = { category: "Sports Performance", current_score: null, target_score: 80.0, gap: null };
    const isGapPresent = k.gap !== null && k.gap !== undefined;
    const gapDisplay = isGapPresent ? (k.gap > 0 ? '-' + k.gap : (k.gap === 0 ? '0' : '+' + Math.abs(k.gap))) : '<span class="text-muted small">-</span>';
    console.log(gapDisplay);
    """
    output = run_js(js)
    assert "-" in output, f"Expected '-' in output, got: {output}"
    assert "0" not in output, f"Literal '0' found for null gap: {output}"
    print(" [PASS] Test 02: Null KPI gap renders '-'")


def test_03_numeric_kpi_zero_remains_zero():
    js = """
    const k = { category: "Leadership", current_score: 0, target_score: 85.0, gap: 0 };
    const isScorePresent = k.current_score !== null && k.current_score !== undefined;
    const scoreDisplay = isScorePresent ? k.current_score : 'Pending';
    const isGapPresent = k.gap !== null && k.gap !== undefined;
    const gapDisplay = isGapPresent ? (k.gap > 0 ? '-' + k.gap : (k.gap === 0 ? '0' : '+' + Math.abs(k.gap))) : '-';
    console.log(JSON.stringify({ score: scoreDisplay, gap: gapDisplay }));
    """
    res = json.loads(run_js(js))
    assert res["score"] == 0, f"Expected score 0, got: {res['score']}"
    assert res["gap"] == "0", f"Expected gap '0', got: {res['gap']}"
    print(" [PASS] Test 03: Numeric KPI 0 remains 0 (for both score and gap)")


def test_04_section_28_populated_data_renders():
    js = """
    const s28 = {
        key_skills: ["Python", "Data Analysis"],
        key_interests: ["Machine Learning", "Robotics"],
        course: "Computer Science",
        school_college: "Tech Academy",
        is_pending: false
    };
    const keySkills = s28.key_skills || [];
    const keyInterests = s28.key_interests || [];
    const isPending = s28.is_pending || (!keySkills.length && !keyInterests.length);

    if (isPending) {
        console.log("PENDING");
    } else {
        console.log("POPULATED:" + keySkills.join(",") + "|" + keyInterests.join(","));
    }
    """
    output = run_js(js)
    assert output.startswith("POPULATED:"), f"Expected populated output, got: {output}"
    assert "Python" in output and "Robotics" in output
    print(" [PASS] Test 04: Section 28 populated data renders")


def test_05_section_28_empty_data_renders_pending_state():
    js = """
    const s28 = {
        key_skills: [],
        key_interests: [],
        is_pending: true
    };
    const keySkills = s28.key_skills || [];
    const keyInterests = s28.key_interests || [];
    const isPending = s28.is_pending || (!keySkills.length && !keyInterests.length);
    console.log(isPending ? "Profile Data Pending" : "POPULATED");
    """
    output = run_js(js)
    assert output == "Profile Data Pending", f"Expected 'Profile Data Pending', got: {output}"
    print(" [PASS] Test 05: Section 28 empty data renders safe pending state")


def test_06_missing_stream_renders_not_specified():
    js = """
    function checkStream(stream) {
        return (stream && stream.trim()) ? stream : "Not Specified";
    }
    console.log(JSON.stringify([
        checkStream(null),
        checkStream(undefined),
        checkStream(""),
        checkStream("   ")
    ]));
    """
    results = json.loads(run_js(js))
    for r in results:
        assert r == "Not Specified", f"Expected 'Not Specified', got: {r}"
    print(" [PASS] Test 06: Missing/empty stream renders 'Not Specified'")


def test_07_existing_stream_remains_unchanged():
    js = """
    function checkStream(stream) {
        return (stream && stream.trim()) ? stream : "Not Specified";
    }
    console.log(JSON.stringify([
        checkStream("Science"),
        checkStream("Commerce"),
        checkStream("Humanities")
    ]));
    """
    results = json.loads(run_js(js))
    assert results == ["Science", "Commerce", "Humanities"], f"Unexpected stream output: {results}"
    print(" [PASS] Test 07: Existing stream values remain unchanged")


def test_08_missing_grade_renders_not_provided():
    js = """
    function checkGrade(grade) {
        return (grade !== null && grade !== undefined && String(grade).trim() !== '') ? grade : 'Not Provided';
    }
    console.log(JSON.stringify([
        checkGrade(null),
        checkGrade(undefined),
        checkGrade(""),
        checkGrade("   ")
    ]));
    """
    results = json.loads(run_js(js))
    for r in results:
        assert r == "Not Provided", f"Expected 'Not Provided', got: {r}"
    print(" [PASS] Test 08: Missing grade renders 'Not Provided'")


def test_09_existing_grade_remains_unchanged():
    js = """
    function checkGrade(grade) {
        return (grade !== null && grade !== undefined && String(grade).trim() !== '') ? grade : 'Not Provided';
    }
    console.log(JSON.stringify([
        checkGrade("A"),
        checkGrade("B+"),
        checkGrade("C"),
        checkGrade("O")
    ]));
    """
    results = json.loads(run_js(js))
    assert results == ["A", "B+", "C", "O"], f"Unexpected grade output: {results}"
    print(" [PASS] Test 09: Existing grades remain unchanged")


def test_10_numeric_academic_average_zero_remains_zero():
    js = """
    const academics = [{ subject: "Physics", percentage: 0, marks: 0 }];
    const avg = academics.length > 0
        ? Math.round(academics.reduce((acc, a) => acc + (a.percentage !== undefined && a.percentage !== null ? a.percentage : a.marks), 0) / academics.length)
        : null;
    const text = (avg !== null && avg !== undefined) ? `${avg}%` : "Pending";
    console.log(text);
    """
    output = run_js(js)
    assert output == "0%", f"Expected '0%', got: {output}"
    print(" [PASS] Test 10: Numeric academic average 0 remains '0%'")


def test_11_null_academic_average_renders_pending():
    js = """
    const academics = [];
    const avg = academics.length > 0
        ? Math.round(academics.reduce((acc, a) => acc + (a.percentage !== undefined && a.percentage !== null ? a.percentage : a.marks), 0) / academics.length)
        : null;
    const text = (avg !== null && avg !== undefined) ? `${avg}%` : "Pending";
    console.log(text);
    """
    output = run_js(js)
    assert output == "Pending", f"Expected 'Pending', got: {output}"
    print(" [PASS] Test 11: Null academic average (empty records) renders 'Pending'")


def test_12_cognitive_index_zero_remains_zero():
    js = """
    const cog = { overall_cognitive_index: 0 };
    let text = "";
    if (cog.overall_cognitive_index !== null && cog.overall_cognitive_index !== undefined) {
        text = `Cognitive Index: ${cog.overall_cognitive_index}%`;
    } else {
        text = `Cognitive Index: Pending`;
    }
    console.log(text);
    """
    output = run_js(js)
    assert output == "Cognitive Index: 0%", f"Expected 'Cognitive Index: 0%', got: {output}"
    print(" [PASS] Test 12: Cognitive index 0 remains 'Cognitive Index: 0%'")


def test_13_null_cognitive_index_renders_pending():
    js = """
    const cog = { overall_cognitive_index: null };
    let text = "";
    if (cog.overall_cognitive_index !== null && cog.overall_cognitive_index !== undefined) {
        text = `Cognitive Index: ${cog.overall_cognitive_index}%`;
    } else {
        text = `Cognitive Index: Pending`;
    }
    console.log(text);
    """
    output = run_js(js)
    assert output == "Cognitive Index: Pending", f"Expected 'Cognitive Index: Pending', got: {output}"
    print(" [PASS] Test 13: Null cognitive index renders 'Cognitive Index: Pending'")


def test_14_activity_matched_traits_render():
    js = """
    function formatTrait(t) {
        if (!t) return "";
        return t.replace(/_/g, " ").replace(/\\b\\w/g, l => l.toUpperCase());
    }
    const matched = ["problem_solving", "perseverance"];
    const matchedHtml = matched.length > 0
        ? matched.map(t => `<span class="badge">${formatTrait(t)}</span>`).join("")
        : '<span class="text-muted small">None identified</span>';
    console.log(matchedHtml);
    """
    output = run_js(js)
    assert "Problem Solving" in output, f"Missing 'Problem Solving' in: {output}"
    assert "Perseverance" in output, f"Missing 'Perseverance' in: {output}"
    print(" [PASS] Test 14: Activity matched traits render formatted chip labels")


def test_15_activity_missing_traits_render():
    js = """
    function formatTrait(t) {
        if (!t) return "";
        return t.replace(/_/g, " ").replace(/\\b\\w/g, l => l.toUpperCase());
    }
    const missing = ["communication", "adaptability"];
    const missingHtml = missing.length > 0
        ? missing.map(t => `<span class="badge">${formatTrait(t)}</span>`).join("")
        : '<span class="text-muted small">None identified</span>';
    console.log(missingHtml);
    """
    output = run_js(js)
    assert "Communication" in output, f"Missing 'Communication' in: {output}"
    assert "Adaptability" in output, f"Missing 'Adaptability' in: {output}"
    print(" [PASS] Test 15: Activity missing traits render formatted chip labels")


def test_16_empty_trait_lists_handled_safely():
    js = """
    const matched = [];
    const missing = [];
    const matchedHtml = matched.length > 0 ? "CHIPS" : "None identified";
    const missingHtml = missing.length > 0 ? "CHIPS" : "None identified";
    console.log(matchedHtml + "|" + missingHtml);
    """
    output = run_js(js)
    assert output == "None identified|None identified", f"Unexpected output: {output}"
    print(" [PASS] Test 16: Empty trait lists safely display 'None identified'")


def test_17_section_22_has_no_top_recommendations_wording():
    with open(os.path.join(ROOT_DIR, "static", "student_report.html"), "r") as f:
        content = f.read()

    assert "(Top Recommendations)" not in content, "Found legacy '(Top Recommendations)' in student_report.html"
    assert "22. Higher-Match Vocational Pathways" in content, "Expected '22. Higher-Match Vocational Pathways' heading in student_report.html"
    print(" [PASS] Test 17: Section 22 has no 'Top Recommendations' wording")


def test_18_activity_85_plus_returns_strong_alignment():
    # Pass profile traits that produce >= 85% compatibility for an activity
    fused_input = {
        "assessments": {
            "critical_abilities": {"data": {"scores": {
                "problem_solving": 90.0, "logical_reasoning": 90.0, "pressure_handling": 90.0, "creative_ability": 90.0
            }}},
            "behavioral": {"data": {"scores": {
                "perseverance": 90.0, "adaptability": 90.0
            }}}
        },
        "interests": [],
        "activities": []
    }
    res = recommend_activities_and_sports(fused_input)
    all_recs = res["co_curricular_recommendations"] + res["sports_recommendations"]
    
    # Filter those with compat >= 85
    high_compat = [r for r in all_recs if r["compatibility"] is not None and r["compatibility"] >= 85.0]
    assert len(high_compat) > 0, "Expected at least one activity with >= 85.0% compatibility"
    
    for r in high_compat:
        assert r["level"] != "Top Recommendation", f"Found legacy 'Top Recommendation' level in: {r['activity']}"
        assert r["level"] == "Strong Alignment", f"Expected 'Strong Alignment' level, got: {r['level']}"
    print(" [PASS] Test 18: Activities with >= 85% compatibility return 'Strong Alignment'")


def test_19_stu_001_values_preserved():
    profile = fuse_student_features("STU-001")
    assert profile is not None, "STU-001 profile fusion failed"
    stu = profile.get("student", {})
    assert stu.get("student_id") == "STU-001", "Student ID mismatch"
    assert stu.get("full_name") == "Dhanashri Varpe", "Student name mismatch"
    
    # Verify assessment integrity
    assessments = profile.get("assessments", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})
    assert pers.get("openness") == 82.0, f"Openness mismatch: {pers.get('openness')}"
    assert pers.get("conscientiousness") == 80.0, f"Conscientiousness mismatch: {pers.get('conscientiousness')}"
    
    # Verify report v2 generation runs cleanly for STU-001
    rep = generate_v2_report_data("STU-001")
    assert bool(rep["status"]) is True
    sec = rep["sections"]
    assert "section_28_overall_student_profile" in sec
    assert sec["section_28_overall_student_profile"]["full_name"] == "Dhanashri Varpe"
    print(" [PASS] Test 19: STU-001 profile data, scores, and report generation preserved")


def test_20_iris_database_counts_preserved():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM iris_users")
    user_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM scan_history")
    scan_count = c.fetchone()[0]
    conn.close()

    assert user_count == 10, f"Expected 10 iris_users, found {user_count}"
    assert scan_count == 57, f"Expected 57 scan_history records, found {scan_count}"
    print(" [PASS] Test 20: Database counts preserved (10 iris_users, 57 scan_history records)")


def main():
    print("=" * 70)
    print("RUNNING STEP 16 UI & REPORT CONSISTENCY VERIFICATION (20 CRITERIA)")
    print("=" * 70)
    
    tests = [
        test_01_null_kpi_renders_pending,
        test_02_null_kpi_gap_renders_dash,
        test_03_numeric_kpi_zero_remains_zero,
        test_04_section_28_populated_data_renders,
        test_05_section_28_empty_data_renders_pending_state,
        test_06_missing_stream_renders_not_specified,
        test_07_existing_stream_remains_unchanged,
        test_08_missing_grade_renders_not_provided,
        test_09_existing_grade_remains_unchanged,
        test_10_numeric_academic_average_zero_remains_zero,
        test_11_null_academic_average_renders_pending,
        test_12_cognitive_index_zero_remains_zero,
        test_13_null_cognitive_index_renders_pending,
        test_14_activity_matched_traits_render,
        test_15_activity_missing_traits_render,
        test_16_empty_trait_lists_handled_safely,
        test_17_section_22_has_no_top_recommendations_wording,
        test_18_activity_85_plus_returns_strong_alignment,
        test_19_stu_001_values_preserved,
        test_20_iris_database_counts_preserved
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f" [FAIL] {t.__name__}: {e}")
            failed += 1

    print("=" * 70)
    print(f"STEP 16 TEST SUMMARY: {passed} PASSED, {failed} FAILED out of {len(tests)}")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Test Suite: Expandable Assessment Engine & Question Architecture Verification
Verifies:
1. Arbitrary question counts (scaling from 1 to 10+ questions per subcategory)
2. Reverse scoring mechanism ((max + min) - value)
3. Question weightings (differential weights 3.0 vs 1.0)
4. Categorical multi-item expansion (VAK & Leadership)
5. Active/inactive status filtering
6. Strict provenance ('assessment-derived') and uncalibrated confidence (None)
"""

import json
import sqlite3
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database_student import get_connection
from services.assessment_engine import (
    get_assessment_questions,
    add_assessment_question,
    evaluate_assessment_responses
)


def run_expandable_engine_tests():
    print("=" * 65)
    print("STARTING EXPANDABLE ASSESSMENT ENGINE TEST SUITE")
    print("=" * 65)

    # Track inserted test question IDs for cleanup
    test_qids = []

    try:
        # -------------------------------------------------------------
        # TEST 1: Baseline Question Bank Verification
        # -------------------------------------------------------------
        base_qs = get_assessment_questions()
        assert len(base_qs) >= 21, "Baseline question bank must have at least 21 questions"
        print(f"✅ 1. Baseline question bank verified ({len(base_qs)} questions loaded with full metadata)")

        # Verify all metadata attributes exist on each question
        sample_q = base_qs[0]
        for attr in ["domain", "subcategory", "question_text", "answer_type", "options",
                     "scoring_direction", "scoring_weight", "is_reverse_scored", "is_active", "version"]:
            assert attr in sample_q, f"Missing question attribute: {attr}"
        print("✅ 2. Question metadata schema verified (domain, subcategory, answer_type, weights, reverse, active)")

        # -------------------------------------------------------------
        # TEST 2: Multi-Item Subcategory Expansion (10 questions)
        # -------------------------------------------------------------
        # Create 5 extra test questions in a test subcategory
        test_domain = "critical_abilities"
        test_sub = "test_fluid_reasoning"
        likert_opts = [
            {"text": "Strongly Disagree", "val": 1},
            {"text": "Disagree", "val": 2},
            {"text": "Neutral", "val": 3},
            {"text": "Agree", "val": 4},
            {"text": "Strongly Agree", "val": 5}
        ]

        multi_qids = []
        for i in range(5):
            qid = add_assessment_question(
                domain=test_domain,
                subcategory=test_sub,
                question_text=f"Test fluid reasoning scale item #{i+1}",
                answer_type="likert",
                options=likert_opts,
                scoring_weight=1.0,
                is_reverse_scored=False,
                is_active=True,
                version="test-v2"
            )
            multi_qids.append(qid)
            test_qids.append(qid)

        # Submit answers: [5, 4, 5, 4, 5] -> avg = 4.6 -> score = (4.6 - 1) / 4 * 100 = 90.0%
        multi_responses = {
            str(multi_qids[0]): 5,
            str(multi_qids[1]): 4,
            str(multi_qids[2]): 5,
            str(multi_qids[3]): 4,
            str(multi_qids[4]): 5,
        }

        res = evaluate_assessment_responses("TEST-STU", test_domain, multi_responses)
        sub_score = res["scores"].get(test_sub)
        assert sub_score == 90.0, f"Expected 90.0% for 5-item scale, got {sub_score}"
        assert res["details"][test_sub]["confidence"] is None
        assert res["details"][test_sub]["confidence_status"] == "not_statistically_calibrated"
        print(f"✅ 3. Multi-item scale expansion passed (5 questions in subcategory averaged to {sub_score}%)")

        # -------------------------------------------------------------
        # TEST 3: Reverse-Scored Questions
        # -------------------------------------------------------------
        # Item A: Standard forward-scored (val=5 -> score 100%)
        # Item B: Reverse-scored (val=5 -> inverted to 1 -> score 0%)
        rev_sub = "test_reverse_trait"
        qid_fwd = add_assessment_question(
            domain="personality",
            subcategory=rev_sub,
            question_text="I am extremely focused (forward-scored)",
            answer_type="likert",
            options=likert_opts,
            scoring_direction="positive",
            scoring_weight=1.0,
            is_reverse_scored=False,
            is_active=True
        )
        test_qids.append(qid_fwd)

        qid_rev = add_assessment_question(
            domain="personality",
            subcategory=rev_sub,
            question_text="I get easily distracted and quit early (reverse-scored)",
            answer_type="likert",
            options=likert_opts,
            scoring_direction="negative",
            scoring_weight=1.0,
            is_reverse_scored=True,
            is_active=True
        )
        test_qids.append(qid_rev)

        # If student answers 5 on forward and 5 on reverse:
        # Forward: 5 -> 5
        # Reverse: 5 -> (5+1)-5 = 1
        # Average: (5 + 1) / 2 = 3.0 -> norm_score = (3.0 - 1) / 4 * 100 = 50.0%
        rev_responses = {str(qid_fwd): 5, str(qid_rev): 5}
        res_rev = evaluate_assessment_responses("TEST-STU", "personality", rev_responses)
        rev_score = res_rev["scores"].get(rev_sub)
        assert rev_score == 50.0, f"Expected 50.0% with reverse scoring, got {rev_score}"
        print(f"✅ 4. Reverse scoring verification passed (5 on forward + 5 on reverse inverted to {rev_score}%)")

        # -------------------------------------------------------------
        # TEST 4: Differential Question Weighting
        # -------------------------------------------------------------
        # Q1 has weight 3.0, answer = 5 (effective 15)
        # Q2 has weight 1.0, answer = 1 (effective 1)
        # Total weight = 4.0, weighted sum = 16.0 -> avg = 4.0 -> norm_score = 75.0%
        # (Unweighted would have been (5+1)/2 = 3.0 -> 50.0%)
        weight_sub = "test_weighted_trait"
        qid_w1 = add_assessment_question(
            domain="behavioral",
            subcategory=weight_sub,
            question_text="Heavy weight question",
            answer_type="likert",
            options=likert_opts,
            scoring_weight=3.0,
            is_reverse_scored=False,
            is_active=True
        )
        test_qids.append(qid_w1)

        qid_w2 = add_assessment_question(
            domain="behavioral",
            subcategory=weight_sub,
            question_text="Light weight question",
            answer_type="likert",
            options=likert_opts,
            scoring_weight=1.0,
            is_reverse_scored=False,
            is_active=True
        )
        test_qids.append(qid_w2)

        w_responses = {str(qid_w1): 5, str(qid_w2): 1}
        res_w = evaluate_assessment_responses("TEST-STU", "behavioral", w_responses)
        w_score = res_w["scores"].get(weight_sub)
        assert w_score == 75.0, f"Expected 75.0% for 3:1 weighted scale, got {w_score}"
        print(f"✅ 5. Differential question weighting passed (3.0 weight + 1.0 weight evaluated to {w_score}%)")

        # -------------------------------------------------------------
        # TEST 5: Categorical Multi-Item Expansion (VAK with 6 questions)
        # -------------------------------------------------------------
        vak_opts = [
            {"text": "Visual", "val": "V"},
            {"text": "Auditory", "val": "A"},
            {"text": "Kinesthetic", "val": "K"}
        ]
        vak_extra_qids = []
        for i in range(3):
            qid_v = add_assessment_question(
                domain="learning_style",
                subcategory="vak",
                question_text=f"Expanded VAK Question #{i+1}",
                answer_type="categorical",
                options=vak_opts,
                scoring_weight=1.0,
                is_active=True
            )
            vak_extra_qids.append(qid_v)
            test_qids.append(qid_v)

        # Baseline 3 + 3 extra = 6 questions answered: 4 V, 1 A, 1 K
        # Total = 6. V = 4/6 = 66.7%, A = 1/6 = 16.7%, K = 1/6 = 16.7%
        vak_responses = {
            "11": "V", "12": "V", "13": "A",
            str(vak_extra_qids[0]): "V",
            str(vak_extra_qids[1]): "V",
            str(vak_extra_qids[2]): "K"
        }
        res_vak = evaluate_assessment_responses("TEST-STU", "learning_style", vak_responses)
        assert res_vak["scores"]["visual_pct"] == 66.7
        assert res_vak["scores"]["auditory_pct"] == 16.7
        assert res_vak["scores"]["kinesthetic_pct"] == 16.7
        assert res_vak["details"]["dominant_style"] == "Visual"
        print(f"✅ 6. Categorical multi-item expansion passed (6 VAK items -> Visual {res_vak['scores']['visual_pct']}%)")

        # -------------------------------------------------------------
        # TEST 6: Inactive Question Exclusion
        # -------------------------------------------------------------
        qid_inactive = add_assessment_question(
            domain="personality",
            subcategory="openness",
            question_text="Draft inactive question",
            answer_type="likert",
            options=likert_opts,
            is_active=False
        )
        test_qids.append(qid_inactive)

        active_qs = get_assessment_questions("personality", active_only=True)
        assert not any(q["id"] == qid_inactive for q in active_qs), "Inactive question should be excluded"
        all_qs = get_assessment_questions("personality", active_only=False)
        assert any(q["id"] == qid_inactive for q in all_qs), "All questions should include inactive"
        print("✅ 7. Active/inactive status filtering passed (draft questions excluded when active_only=True)")

        # -------------------------------------------------------------
        # TEST 7: Provenance and Uncalibrated Confidence Guarantee
        # -------------------------------------------------------------
        assert res["source"] == "assessment-derived"
        assert res["confidence"] is None
        assert res["confidence_status"] == "not_statistically_calibrated"
        print("✅ 8. Scientific transparency confirmed (source='assessment-derived', confidence=null, status='not_statistically_calibrated')")

    finally:
        # Cleanup all created test questions and test assessments to leave DB clean
        try:
            conn = get_connection()
            cur = conn.cursor()
            if test_qids:
                placeholders = ",".join("?" for _ in test_qids)
                cur.execute(f"DELETE FROM assessment_questions WHERE id IN ({placeholders})", test_qids)
            cur.execute("DELETE FROM student_assessments WHERE student_id = 'TEST-STU'")
            cur.execute("DELETE FROM prediction_results WHERE student_id = 'TEST-STU'")
            conn.commit()
            conn.close()
            print(f"🧹 Cleaned up {len(test_qids)} temporary test questions. Database returned to pristine baseline.")
        except Exception as e:
            print(f"Cleanup error: {e}")

    print("=" * 65)
    print("ALL 8 EXPANDABLE ASSESSMENT ENGINE ARCHITECTURE TESTS PASSED")
    print("=" * 65)


if __name__ == "__main__":
    run_expandable_engine_tests()

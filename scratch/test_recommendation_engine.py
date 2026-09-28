"""
Test Suite: Data-Driven, Configurable Stream Selection & Career Recommendation Engine
Verifies:
1. Stream scoring logic (Science, Commerce, Humanities)
2. Career multi-factor scoring with full dimensional breakdown
3. Missing data resilience (NO fabricated 75/70/40 defaults)
4. Conflict and contradiction detection (High marks + 0 interest; High interest + missing prereq; Tied streams)
5. Prerequisite failure handling
6. Configurable heuristic weights override
7. Neutral terminology & tiering (primary/secondary affinity, higher match, trending catalog)
8. Explainable evidence (strictly data-derived matched factors and gaps)
9. Scientific transparency (confidence=null, status='not_statistically_calibrated', source='rule-based')
10. Trending metadata transparency (curated catalog source with disclaimer)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.stream_engine import recommend_streams, DEFAULT_STREAM_WEIGHTS
from services.career_engine import recommend_careers, DEFAULT_CAREER_WEIGHTS


def run_recommendation_tests():
    print("=" * 65)
    print("STARTING RECOMMENDATION ENGINE TEST SUITE (STREAM & CAREER)")
    print("=" * 65)

    # -----------------------------------------------------------------
    # Test Data 1: Complete Student Profile (STEM High Achiever)
    # -----------------------------------------------------------------
    complete_student = {
        "student": {"student_id": "STU-FULL", "stream": "Science", "course": "Computer Science"},
        "subject_marks": {
            "mathematics": 92.0,
            "science": 88.0,
            "computer science": 95.0,
            "languages": 78.0,
            "english": 80.0
        },
        "skills": [
            {"skill": "Python", "proficiency": 90.0},
            {"skill": "Machine Learning", "proficiency": 80.0},
            {"skill": "Data Structures", "proficiency": 85.0}
        ],
        "interests": [
            {"interest": "Artificial Intelligence", "level": "High"},
            {"interest": "Robotics", "level": "High"}
        ],
        "activities": [
            {"title": "Robotics Club Hackathon", "description": "Built automated bot"}
        ],
        "assessments": {
            "critical_abilities": {"data": {"scores": {"logical_reasoning": 85.0, "problem_solving": 88.0}}},
            "personality": {"data": {"scores": {"conscientiousness": 75.0, "openness": 80.0}}}
        }
    }

    # -----------------------------------------------------------------
    # TEST 1: Stream Scoring & Neutral Terminology
    # -----------------------------------------------------------------
    streams_res = recommend_streams(complete_student)
    assert streams_res["primary_affinity_stream"] == "Science (STEM)"
    assert streams_res["recommended_stream"] == "Science (STEM)"  # backward compatibility
    assert len(streams_res["stream_rankings"]) == 3
    sci_rank = next(s for s in streams_res["stream_rankings"] if s["stream"] == "Science (STEM)")
    assert sci_rank["compatibility_score"] >= 80.0
    assert sci_rank["dimensional_scores"]["academic_match"] == 91.7
    assert sci_rank["dimensional_scores"]["assessment_match"] == 86.5
    print("✅ 1. Stream scoring verified with neutral terminology (primary_affinity_stream='Science (STEM)')")

    # -----------------------------------------------------------------
    # TEST 2: Career Multi-Factor Scoring & Dimensional Breakdown
    # -----------------------------------------------------------------
    careers_res = recommend_careers(complete_student)
    assert "higher_match_careers" in careers_res
    assert "trending_catalog_careers" in careers_res
    assert "additional_suitable_careers" in careers_res
    # Backward compatibility check
    assert careers_res["top_recommendations"] == careers_res["higher_match_careers"]
    assert careers_res["trending_careers"] == careers_res["trending_catalog_careers"]

    top_c = careers_res["higher_match_careers"][0]
    dim = top_c["dimensional_scores"]
    for dim_key in ["academic_match", "skill_match", "assessment_match", "interest_match", "stream_eligibility"]:
        assert dim_key in dim, f"Missing dimensional score key: {dim_key}"
    assert top_c["career"] == "Artificial Intelligence & ML Engineer"
    assert top_c["compatibility_score"] >= 80.0
    print(f"✅ 2. Career multi-factor scoring verified (Top: {top_c['career']} with {top_c['compatibility_score']}%)")

    # -----------------------------------------------------------------
    # TEST 3: Missing Data Resilience (NO Fabricated Defaults)
    # -----------------------------------------------------------------
    # Student with NO marks, NO skills, NO assessments
    blank_student = {
        "student": {"student_id": "STU-BLANK", "stream": "Science"},
        "subject_marks": {},
        "skills": [],
        "interests": [],
        "activities": [],
        "assessments": {}
    }
    blank_streams = recommend_streams(blank_student)
    # Must NOT fabricate 75.0% or 40.0%
    for s in blank_streams["stream_rankings"]:
        assert s["compatibility_score"] == 0.0, f"Expected 0.0 for blank profile, got {s['compatibility_score']}"
        assert s["dimensional_scores"]["academic_match"] is None
        assert s["dimensional_scores"]["assessment_match"] is None
        assert len(s["missing_prerequisites"]) > 0
    print("✅ 3. Missing data resilience verified (zero score for blank profile, no fabricated defaults)")

    # -----------------------------------------------------------------
    # TEST 4: Conflict Detection - High Academic Performance vs Low Interest
    # -----------------------------------------------------------------
    # High Math/Science marks, but interests only in Arts/Literature
    conflict_student_1 = {
        "student": {"student_id": "STU-CONF-1", "stream": "Science"},
        "subject_marks": {"mathematics": 95.0, "science": 92.0},
        "skills": [],
        "interests": [{"interest": "Classical Literature", "level": "High"}],
        "activities": [],
        "assessments": {}
    }
    conf1_res = recommend_streams(conflict_student_1)
    found_conflict = any("Contradiction in Science" in c or "low expressed student interest" in c for c in conf1_res["conflicts_and_considerations"])
    assert found_conflict, f"Expected academic vs interest contradiction to be flagged. Conflicts: {conf1_res['conflicts_and_considerations']}"
    print("✅ 4. Conflict detection verified: High Academic vs Low Interest flagged")

    # -----------------------------------------------------------------
    # TEST 5: Conflict Detection - High Interest vs Missing Prerequisite
    # -----------------------------------------------------------------
    conflict_student_2 = {
        "student": {"student_id": "STU-CONF-2", "stream": "Humanities"},
        "subject_marks": {"languages": 85.0, "history": 82.0},  # No Math, No Science
        "skills": [],
        "interests": [{"interest": "Artificial Intelligence", "level": "High"}],
        "activities": [],
        "assessments": {}
    }
    conf2_res = recommend_streams(conflict_student_2)
    found_prereq_gap = any("Prerequisite Gap in Science" in c or "missing or below proficiency" in c for c in conf2_res["conflicts_and_considerations"])
    assert found_prereq_gap, f"Expected prerequisite gap conflict to be flagged. Conflicts: {conf2_res['conflicts_and_considerations']}"
    print("✅ 5. Conflict detection verified: High Interest vs Missing Prerequisite flagged")

    # -----------------------------------------------------------------
    # TEST 6: Marginal Differentiation / Tied Streams Consideration
    # -----------------------------------------------------------------
    tied_student = {
        "student": {"student_id": "STU-TIED"},
        "subject_marks": {"mathematics": 80.0, "science": 80.0, "commerce": 80.0, "economics": 80.0},
        "skills": [],
        "interests": [{"interest": "technology", "level": "High"}, {"interest": "business", "level": "High"}],
        "activities": [],
        "assessments": {"critical_abilities": {"data": {"scores": {"logical_reasoning": 75.0}}}}
    }
    tied_res = recommend_streams(tied_student)
    found_tie_note = any("Close Suitability Balance" in c or "Marginal differentiation" in c for c in tied_res["conflicts_and_considerations"])
    assert found_tie_note, f"Expected marginal differentiation note. Conflicts: {tied_res['conflicts_and_considerations']}"
    print("✅ 6. Marginal differentiation / tied streams consideration verified")

    # -----------------------------------------------------------------
    # TEST 7: Configurable Heuristic Weights Override
    # -----------------------------------------------------------------
    # Compare heavy-academic weight vs heavy-interest weight on complete_student
    heavy_academic = recommend_streams(complete_student, custom_weights={"academic_weight": 0.80, "interest_weight": 0.05})
    heavy_interest = recommend_streams(complete_student, custom_weights={"academic_weight": 0.05, "interest_weight": 0.80})
    sci_heavy_acad = next(s for s in heavy_academic["stream_rankings"] if s["stream"] == "Science (STEM)")
    sci_heavy_int = next(s for s in heavy_interest["stream_rankings"] if s["stream"] == "Science (STEM)")
    assert sci_heavy_acad["compatibility_score"] != sci_heavy_int["compatibility_score"]
    assert heavy_academic["provenance"]["weights_used"]["academic_weight"] == 0.80
    print("✅ 7. Configurable weights override verified (weights shift scores dynamically)")

    # -----------------------------------------------------------------
    # TEST 8: Explainable Evidence Strictly Data-Derived
    # -----------------------------------------------------------------
    top_career_item = careers_res["higher_match_careers"][0]
    assert len(top_career_item["matched_factors"]) > 0
    # Must mention actual records (e.g. Python, Math, AI)
    factors_str = " ".join(top_career_item["matched_factors"])
    assert "Mathematics" in factors_str or "Python" in factors_str or "Artificial Intelligence" in factors_str
    print("✅ 8. Explainable evidence verified (strictly data-derived without fabricated claims)")

    # -----------------------------------------------------------------
    # TEST 9: Trending Data Transparency & Static Taxonomy Disclaimer
    # -----------------------------------------------------------------
    assert careers_res["trending_disclaimer"] is not None
    assert "static catalog taxonomy" in careers_res["trending_disclaimer"]
    for c in careers_res["trending_catalog_careers"]:
        assert c["trending_source"] == "curated_catalog"
    print("✅ 9. Trending data transparency verified (curated catalog source with disclaimer)")

    # -----------------------------------------------------------------
    # TEST 10: Provenance & Uncalibrated Confidence Guarantee
    # -----------------------------------------------------------------
    for res in [streams_res, careers_res]:
        prov = res["provenance"]
        assert prov["source"] == "rule-based"
        assert prov["confidence"] is None
        assert prov["confidence_status"] == "not_statistically_calibrated"
        assert "not predictive scientific guarantees" in prov["disclaimer"]
    print("✅ 10. Scientific transparency confirmed (source='rule-based', confidence=null, status='not_statistically_calibrated')")

    print("=" * 65)
    print("ALL 10 RECOMMENDATION ENGINE TESTS PASSED")
    print("=" * 65)


if __name__ == "__main__":
    run_recommendation_tests()

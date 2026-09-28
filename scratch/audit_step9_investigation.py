import os
import sys
import json
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from services.cognitive_engine import compute_cognitive_profile
from services.subject_analysis import analyze_critical_subjects
from services.kpi_engine import compute_kpis
from services.stream_engine import recommend_streams
from services.career_engine import recommend_careers
from services.activity_sports import recommend_activities_and_sports
from services.gap_analysis import compute_development_gaps
from services.feature_fusion import fuse_student_features
from services.report_v2_generator import generate_v2_report_data
from database_student import get_connection


def run_scenarios_audit():
    print("=" * 80)
    print("STEP 9 DETAILED AUDIT: DATA COMPLETENESS ACROSS SCENARIOS A-G")
    print("=" * 80)

    # Standard full components for mix & match
    full_academics = [
        {"subject": "Mathematics", "marks": 88, "max_marks": 100, "percentage": 88.0, "source": "academic-derived"},
        {"subject": "Physics", "marks": 84, "max_marks": 100, "percentage": 84.0, "source": "academic-derived"},
        {"subject": "Computer Science", "marks": 92, "max_marks": 100, "percentage": 92.0, "source": "academic-derived"}
    ]
    full_subject_marks = {"mathematics": 88.0, "physics": 84.0, "computer science": 92.0}
    full_skills = [
        {"skill": "Python", "type": "technical", "proficiency": 85.0, "source": "profile-derived"},
        {"skill": "Data Structures", "type": "technical", "proficiency": 80.0, "source": "profile-derived"}
    ]
    full_interests = [
        {"category": "Technical", "interest": "Artificial Intelligence", "level": "High", "source": "profile-derived"},
        {"category": "Technical", "interest": "Robotics", "level": "High", "source": "profile-derived"}
    ]
    full_activities = [
        {"title": "Robotics Hackathon", "type": "projects", "description": "Built an autonomous robot", "year": "2025", "source": "profile-derived"}
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
        },
        "thinking_action": {
            "data": {"scores": {"thinking_pct": 65.0, "action_pct": 35.0}}
        },
        "team_player": {
            "data": {"scores": {"team_management_pct": 55.0, "team_player_pct": 45.0}}
        },
        "behavioral": {
            "data": {"scores": {"adaptability": 78.0, "perseverance": 82.0}}
        },
        "emotional_social": {
            "data": {"scores": {"empathy": 80.0, "social_confidence": 75.0}}
        }
    }

    partial_assessments = {
        "critical_abilities": {
            "data": {"scores": {"problem_solving": 75.0, "logical_reasoning": 80.0}}
        }
    }

    scenarios = [
        ("A. No Academic Data", {"academics": [], "subject_marks": {}, "skills": full_skills, "interests": full_interests, "activities": full_activities, "assessments": full_assessments}),
        ("B. No Skills", {"academics": full_academics, "subject_marks": full_subject_marks, "skills": [], "interests": full_interests, "activities": full_activities, "assessments": full_assessments}),
        ("C. No Interests", {"academics": full_academics, "subject_marks": full_subject_marks, "skills": full_skills, "interests": [], "activities": full_activities, "assessments": full_assessments}),
        ("D. No Activities", {"academics": full_academics, "subject_marks": full_subject_marks, "skills": full_skills, "interests": full_interests, "activities": [], "assessments": full_assessments}),
        ("E. No Assessment", {"academics": full_academics, "subject_marks": full_subject_marks, "skills": full_skills, "interests": full_interests, "activities": full_activities, "assessments": {}}),
        ("F. Partial Assessment", {"academics": full_academics, "subject_marks": full_subject_marks, "skills": full_skills, "interests": full_interests, "activities": full_activities, "assessments": partial_assessments}),
        ("G. Complete Assessment & Profile", {"academics": full_academics, "subject_marks": full_subject_marks, "skills": full_skills, "interests": full_interests, "activities": full_activities, "assessments": full_assessments}),
        ("H. Zero Data (Completely Empty Profile)", {"academics": [], "subject_marks": {}, "skills": [], "interests": [], "activities": [], "assessments": {}})
    ]

    for label, sc_data in scenarios:
        print(f"\n>>> SCENARIO {label}")
        fused = {
            "student": {"student_id": "AUDIT-STU", "full_name": "Audit Student", "stream": "Science"},
            "academics": sc_data["academics"],
            "subject_marks": sc_data["subject_marks"],
            "skills": sc_data["skills"],
            "interests": sc_data["interests"],
            "activities": sc_data["activities"],
            "assessments": sc_data["assessments"],
            "iris_biometrics": None
        }

        # 1. Cognitive Engine
        cog = compute_cognitive_profile(fused)
        valid_cog = [d for d in cog.get("domains", []) if d.get("score") is not None]
        print(f"  [Cognitive] is_pending={cog.get('is_pending')}, valid_domains={len(valid_cog)}/10, overall_index={cog.get('overall_cognitive_index')}")

        # 2. Subject Analysis
        sub = analyze_critical_subjects(fused)
        has_fallback_subs = not sc_data["academics"] and len(sub.get("subjects", [])) > 0
        print(f"  [Subjects] subjects_count={len(sub.get('subjects', []))}, avg={sub.get('average_score')} (FALLBACK DETECTED: {has_fallback_subs})")

        # 3. Stream Engine
        stream = recommend_streams(fused)
        top_stream = stream.get("recommended_stream")
        top_stream_score = stream["stream_rankings"][0]["compatibility_score"] if stream.get("stream_rankings") else None
        print(f"  [Streams] recommended={top_stream}, top_score={top_stream_score}")

        # 4. Career Engine
        career = recommend_careers(fused)
        top_car = career["top_recommendations"][0]["career"] if career.get("top_recommendations") else None
        top_car_score = career["top_recommendations"][0]["compatibility_score"] if career.get("top_recommendations") else None
        print(f"  [Careers] top_career={top_car}, top_score={top_car_score}")

        # 5. Activity & Sports
        acts = recommend_activities_and_sports(fused)
        top_cocurr = acts["co_curricular_recommendations"][0]["activity"]
        top_cocurr_score = acts["co_curricular_recommendations"][0]["compatibility"]
        top_sport = acts["sports_recommendations"][0]["activity"]
        top_sport_score = acts["sports_recommendations"][0]["compatibility"]
        print(f"  [Activities] top_co_curricular={top_cocurr} ({top_cocurr_score}%), top_sport={top_sport} ({top_sport_score}%)")

        # 6. KPI Engine
        kpi = compute_kpis(fused)
        pending_kpis = [k["category"] for k in kpi["kpis"] if k.get("is_pending")]
        scored_kpis = [k["category"] for k in kpi["kpis"] if not k.get("is_pending")]
        print(f"  [KPIs] scored={len(scored_kpis)}/9, pending={len(pending_kpis)}/9, overall_avg={kpi.get('overall_kpi_average')}")

        # 7. Gap Analysis
        gap = compute_development_gaps(fused)
        print(f"  [Gaps] total_tracked={gap.get('total_tracked_skills')}")


if __name__ == "__main__":
    run_scenarios_audit()

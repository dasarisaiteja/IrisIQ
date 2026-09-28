"""
Career Recommendation Engine
Provides transparent, data-driven, configurable, and explainable career affinity evaluations
strictly independent of raw iris biometric features.

Scientific Transparency Note:
The weights, matching logic, and suitability scores herein are configurable decision-support heuristics,
NOT psychometrically validated predictive models or clinical guarantees.
"""

import json
from typing import Dict, Any, Optional, List
from database_student import get_connection


DEFAULT_CAREER_WEIGHTS = {
    "academic_weight": 0.30,
    "skill_weight": 0.25,
    "assessment_weight": 0.20,
    "interest_weight": 0.15,
    "activity_weight": 0.05,
    "stream_eligibility_weight": 0.05
}


def recommend_careers(fused_data: Dict[str, Any], custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Evaluates career compatibility across the configurable career database using
    student academic marks, skills, interests, assessments, and activities.
    Strictly independent of raw iris biometric features.
    """
    active_weights = dict(DEFAULT_CAREER_WEIGHTS)
    if custom_weights:
        active_weights.update(custom_weights)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, career_name, category, required_skills_json, required_subjects_json,
               interest_areas_json, aptitude_requirements_json, relevant_assessment_domains_json,
               work_style, education_pathway, required_certifications, future_opportunities,
               is_trending, eligible_streams_json, development_requirements_json, version, trending_source
        FROM career_catalog
        WHERE is_active = 1
    """)
    rows = cursor.fetchall()
    conn.close()

    subject_marks = fused_data.get("subject_marks", {})
    assessments = fused_data.get("assessments", {})
    student_skills = {
        str(s.get("skill", "")).lower(): float(s.get("proficiency", 70.0))
        for s in fused_data.get("skills", [])
    }
    student_interests = [str(i.get("interest", "")).lower() for i in fused_data.get("interests", [])]
    student_activities = fused_data.get("activities", [])
    student_stream = str(fused_data.get("student", {}).get("stream", "")).lower()

    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})

    evidence_sources = set(["rule-based"])
    if subject_marks:
        evidence_sources.add("academic-derived")
    if student_skills:
        evidence_sources.add("skill-derived")
    if student_interests:
        evidence_sources.add("interest-derived")
    if crit or pers:
        evidence_sources.add("assessment-derived")
    if student_activities:
        evidence_sources.add("activity-derived")

    all_evaluated = []

    for r in rows:
        c_id = r[0]
        c_name = r[1]
        c_cat = r[2]
        req_skills = json.loads(r[3]) if r[3] else []
        req_subs = json.loads(r[4]) if r[4] else []
        interest_areas = json.loads(r[5]) if r[5] else []
        apt_reqs = json.loads(r[6]) if r[6] else {}
        work_style = r[8] or "Professional Practice"
        edu_path = r[9] or "Relevant degree or professional qualification"
        certs = r[10] or "Industry recognized credentials"
        future_opps = r[11] or "Active market opportunities"
        is_trending = bool(r[12])
        eligible_streams = json.loads(r[13]) if r[13] else ["Science (STEM)", "Commerce & Business Studies", "Humanities & Social Sciences"]
        dev_reqs = json.loads(r[14]) if r[14] else []
        c_version = r[15] or "v1"
        trending_source = r[16] or "curated_catalog"

        matched_factors = []
        gaps = []
        conflicts = []

        # -------------------------------------------------------------
        # 1. Academic Prerequisite Alignment
        # -------------------------------------------------------------
        matched_subs = {}
        missing_subs = []
        for s in req_subs:
            s_low = s.lower()
            found_val = next((float(v) for k, v in subject_marks.items() if s_low in k or k in s_low), None)
            if found_val is not None:
                matched_subs[s] = found_val
            else:
                missing_subs.append(s)

        if req_subs:
            if matched_subs:
                sub_score = round(sum(matched_subs.values()) / len(matched_subs), 1)
                subs_str = ", ".join(f"{k} ({v}%)" for k, v in matched_subs.items())
                matched_factors.append(f"Prerequisite subject readiness: {subs_str}")
            else:
                sub_score = None
                gaps.append(f"Required prerequisite subjects not recorded: {', '.join(missing_subs)}")
        else:
            sub_score = 75.0  # If career has no specific academic prerequisites

        # -------------------------------------------------------------
        # 2. Skill Alignment & Gaps
        # -------------------------------------------------------------
        matched_skills = []
        skill_gaps = []
        skill_scores = []
        for sk in req_skills:
            sk_low = sk.lower()
            matching_key = next((k for k in student_skills.keys() if sk_low in k or k in sk_low), None)
            if matching_key:
                prof = student_skills[matching_key]
                skill_scores.append(prof)
                if prof >= 75.0:
                    matched_skills.append(f"{sk} ({prof}%)")
                else:
                    skill_gaps.append({
                        "skill": sk,
                        "current": prof,
                        "required": 80.0,
                        "gap": round(80.0 - prof, 1),
                        "status": "developing"
                    })
            else:
                skill_gaps.append({
                    "skill": sk,
                    "current": None,
                    "required": 80.0,
                    "gap": 80.0,
                    "status": "missing"
                })

        if req_skills:
            if student_skills:
                # Weighted by fraction of skills present
                acquired_ratio = len(skill_scores) / len(req_skills)
                avg_prof = (sum(skill_scores) / len(skill_scores)) if skill_scores else 0.0
                skill_score = round(avg_prof * (0.6 + 0.4 * acquired_ratio), 1)
                if matched_skills:
                    matched_factors.append(f"Demonstrated domain skills: {', '.join(matched_skills)}")
            else:
                skill_score = None
                gaps.append(f"Student has not recorded technical/domain skills for {c_name}")
        else:
            skill_score = 70.0

        if skill_gaps:
            gaps.extend([f"Skill gap in {g['skill']} (Target: 80.0%)" for g in skill_gaps[:2]])

        # -------------------------------------------------------------
        # 3. Interest Alignment
        # -------------------------------------------------------------
        matched_interests = []
        for ia in interest_areas:
            ia_low = ia.lower()
            if any(ia_low in si or si in ia_low for si in student_interests):
                matched_interests.append(ia)

        if student_interests:
            if matched_interests:
                interest_score = min(100.0, round((len(matched_interests) / max(1, len(interest_areas))) * 80.0 + 20.0, 1))
                matched_factors.append(f"Direct vocational interest alignment: {', '.join(matched_interests)}")
            else:
                interest_score = 15.0
                gaps.append("Low declared interest in this specific career domain")
        else:
            interest_score = None

        # -------------------------------------------------------------
        # 4. Assessment / Aptitude Alignment
        # -------------------------------------------------------------
        apt_scores = []
        for apt, req_val in apt_reqs.items():
            curr_val = crit.get(apt, pers.get(apt))
            if curr_val is not None:
                fulfillment = min(100.0, (float(curr_val) / max(1.0, float(req_val))) * 100.0)
                apt_scores.append(fulfillment)

        if apt_scores:
            apt_score = round(sum(apt_scores) / len(apt_scores), 1)
            matched_factors.append(f"Assessment trait suitability index: {apt_score}% across required cognitive domains")
        else:
            apt_score = None

        # -------------------------------------------------------------
        # 5. Activity Alignment
        # -------------------------------------------------------------
        act_matches = []
        for act in student_activities:
            t = str(act.get("title", "")).lower()
            d = str(act.get("description", "")).lower()
            if any(sk.lower() in t or sk.lower() in d for sk in req_skills[:3]):
                act_matches.append(act.get("title", t))

        if student_activities:
            activity_score = 85.0 if act_matches else 40.0
            if act_matches:
                matched_factors.append(f"Relevant project/co-curricular activity: {', '.join(act_matches[:2])}")
        else:
            activity_score = None

        # -------------------------------------------------------------
        # 6. Stream Eligibility
        # -------------------------------------------------------------
        if student_stream:
            is_stream_eligible = any(student_stream in es.lower() or es.lower() in student_stream for es in eligible_streams)
            stream_score = 100.0 if is_stream_eligible else 55.0
            if not is_stream_eligible:
                gaps.append(f"Career typically aligns with {', '.join(eligible_streams)}; current stream is {student_stream.title()}")
        else:
            stream_score = None
            gaps.append("Current stream not declared; confirm educational pathway prerequisites.")

        # -------------------------------------------------------------
        # Conflict Detection per career
        # -------------------------------------------------------------
        if sub_score is not None and sub_score >= 80.0 and (interest_score is not None and interest_score <= 20.0):
            conflicts.append(f"Academic readiness is high ({sub_score}%), but student has not indicated interest in {c_name}.")
        if interest_score is not None and interest_score >= 70.0 and missing_subs:
            conflicts.append(f"Strong student interest expressed, but missing academic grades for prerequisite subjects: {', '.join(missing_subs)}.")
        if sub_score is not None and sub_score >= 75.0 and not matched_skills:
            conflicts.append(f"Strong academic prerequisites, but practical applied skills ({', '.join(req_skills[:2])}) are not yet demonstrated.")

        # -------------------------------------------------------------
        # Composite Match Score Calculation (Missing-Data Resilient)
        # -------------------------------------------------------------
        dim_scores = {
            "academic_match": sub_score,
            "skill_match": skill_score,
            "assessment_match": apt_score,
            "interest_match": interest_score,
            "activity_match": activity_score,
            "stream_eligibility": stream_score
        }

        weights_map = {
            "academic_match": active_weights["academic_weight"],
            "skill_match": active_weights["skill_weight"],
            "assessment_match": active_weights["assessment_weight"],
            "interest_match": active_weights["interest_weight"],
            "activity_match": active_weights["activity_weight"],
            "stream_eligibility": active_weights["stream_eligibility_weight"]
        }

        # Check if ANY student-specific evidence exists (academics, skills, assessments, interests, activities)
        student_evidence = [sub_score, skill_score, apt_score, interest_score, activity_score]
        has_student_evidence = any(v is not None for v in student_evidence)

        available_dims = [k for k, v in dim_scores.items() if v is not None]
        missing_dims = [k for k, v in dim_scores.items() if v is None]

        if not has_student_evidence:
            compat_score = 0.0
            evidence_score = 0.0
            data_completeness = 0.0
            is_partial = False
            is_pending = True
            match_level = "Profile Data Pending"
            matched_factors = ["Awaiting academic records, structured assessments, or declared skills/interests"]
        else:
            is_pending = False
            weighted_sum = 0.0
            total_weight_used = 0.0
            for dim_k, dim_v in dim_scores.items():
                if dim_v is not None:
                    w = weights_map[dim_k]
                    weighted_sum += dim_v * w
                    total_weight_used += w

            compat_score = round(weighted_sum, 1)
            evidence_score = compat_score
            data_completeness = round(total_weight_used, 2)
            is_partial = total_weight_used < 0.95

            if total_weight_used < 0.5:
                match_level = "Limited Evidence"
            elif compat_score >= 80.0:
                match_level = "High Match"
            elif compat_score >= 65.0:
                match_level = "Moderate Match"
            else:
                match_level = "Developing Potential"

        all_evaluated.append({
            "career": c_name,
            "category": c_cat,
            "compatibility_score": compat_score,
            "evidence_score": evidence_score,
            "data_completeness": data_completeness,
            "is_partial": is_partial,
            "match_level": match_level,
            "is_pending": is_pending,
            "available_dimensions": available_dims,
            "missing_dimensions": missing_dims,
            "is_trending": is_trending,
            "trending_source": trending_source,
            "dimensional_scores": dim_scores,
            "matched_factors": matched_factors if matched_factors else ["Baseline exploratory alignment"],
            "why_it_matches": matched_factors if matched_factors else ["Baseline exploratory alignment"],  # backward compatible
            "gaps_and_development_areas": gaps,
            "conflicts_and_considerations": conflicts,
            "relevant_strengths": matched_skills if matched_skills else ["Foundational quantitative and reasoning aptitude"],
            "skill_gaps": skill_gaps[:3],
            "missing_prerequisite_subjects": missing_subs,
            "required_education": edu_path,
            "recommended_skills": req_skills[:4],
            "required_certifications": certs,
            "development_requirements": dev_reqs,
            "future_opportunities": future_opps,
            "work_style": work_style,
            "eligible_streams": eligible_streams,
            "version": c_version,
            "next_steps": f"Enroll in foundational coursework for {req_skills[0] if req_skills else 'core domain'}, build portfolio projects, and pursue {certs.split(',')[0] if certs else 'industry credentials'}.",
            "source": "rule-based"
        })

    # Sort descending by compatibility
    all_sorted = sorted(all_evaluated, key=lambda x: x["compatibility_score"], reverse=True)

    higher_match = all_sorted[:3]
    trending_matches = [c for c in all_sorted if c["is_trending"] and c not in higher_match][:3]
    additional_suitable = [c for c in all_sorted if c not in higher_match and c not in trending_matches][:3]
    all_pending = all(c.get("is_pending") for c in all_evaluated) if all_evaluated else True

    return {
        "is_pending": all_pending,
        "status": "pending" if all_pending else "completed",
        "message": "Profile Data Pending" if all_pending else "Completed",

        # Neutral Tiering
        "higher_match_careers": higher_match,
        "trending_catalog_careers": trending_matches,
        "additional_suitable_careers": additional_suitable,

        # Backward Compatibility Keys
        "top_recommendations": higher_match,
        "trending_careers": trending_matches,
        "other_suitable_careers": additional_suitable,

        "all_careers": all_sorted,
        "evidence_sources": sorted(list(evidence_sources)),
        "source": "rule-based",
        "methodology": "Multi-dimensional weighted factor matching using academic grades, assessments, skills, and student interest profiles.",
        "trending_disclaimer": "Trending indicators reflect static catalog taxonomy and do not represent real-time macroeconomic labor-market statistics.",
        "provenance": {
            "source": "rule-based",
            "method": "configurable_multi_factor_matching",
            "weights_used": active_weights,
            "confidence": None,
            "confidence_status": "not_statistically_calibrated",
            "disclaimer": "Career suitability scores are heuristic exploratory aids and not predictive scientific guarantees."
        }
    }

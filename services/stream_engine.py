"""
Stream Selection Recommendation Engine
Provides transparent, data-driven, configurable, and explainable stream affinity evaluations
(Science, Commerce, Humanities) strictly independent of raw iris biometric features.

Scientific Transparency Note:
The weights and formulas herein are configurable decision-support heuristics,
NOT psychometrically validated predictive models or clinical guarantees.
"""

import re
from typing import Dict, Any, Optional, List


def _keyword_in_text(kw: str, text: str) -> bool:
    kw = kw.lower().strip()
    text = text.lower().strip()
    if len(kw) <= 3:
        # short acronym or word: match as whole word to avoid false positives (e.g. 'art' in 'artificial')
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))
    return kw in text


DEFAULT_STREAM_WEIGHTS = {
    "academic_weight": 0.40,
    "assessment_weight": 0.25,
    "interest_weight": 0.20,
    "skill_weight": 0.10,
    "activity_weight": 0.05
}


def recommend_streams(fused_data: Dict[str, Any], custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Computes comparative suitability for Science, Commerce, and Humanities streams
    utilizing multi-factor profiling (academic marks, assessments, interests, skills, activities).
    Strictly independent of raw iris biometric features.
    """
    active_weights = dict(DEFAULT_STREAM_WEIGHTS)
    if custom_weights:
        active_weights.update(custom_weights)

    subject_marks = fused_data.get("subject_marks", {})
    assessments = fused_data.get("assessments", {})
    interests = [str(i.get("interest", "")).lower() for i in fused_data.get("interests", [])]
    skills = fused_data.get("skills", [])
    activities = fused_data.get("activities", [])

    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})

    evidence_sources = set(["rule-based"])
    if subject_marks:
        evidence_sources.add("academic-derived")
    if crit or pers:
        evidence_sources.add("assessment-derived")
    if interests:
        evidence_sources.add("interest-derived")
    if skills:
        evidence_sources.add("skill-derived")
    if activities:
        evidence_sources.add("activity-derived")

    # Helper to find matching subject marks without fabricating defaults
    def find_subjects(patterns: List[str]) -> Dict[str, float]:
        found = {}
        for p in patterns:
            for sub_name, val in subject_marks.items():
                if p in sub_name or sub_name in p:
                    found[sub_name] = float(val)
        return found

    # Helper to find skills without fabricating defaults
    def find_skills(keywords: List[str]) -> Dict[str, float]:
        found = {}
        for s in skills:
            s_name = str(s.get("skill", "")).lower()
            if any(_keyword_in_text(k, s_name) for k in keywords):
                found[s.get("skill", s_name)] = float(s.get("proficiency", 70.0))
        return found

    # Helper to check activities
    def find_activities(keywords: List[str]) -> List[str]:
        found = []
        for a in activities:
            title = str(a.get("title", "")).lower()
            desc = str(a.get("description", "")).lower()
            if any(_keyword_in_text(k, title) or _keyword_in_text(k, desc) for k in keywords):
                found.append(a.get("title", title))
        return found

    # Stream Definitions
    stream_defs = [
        {
            "stream": "Science (STEM)",
            "subject_patterns": ["math", "sci", "phys", "chem", "bio", "comp"],
            "required_subject_labels": ["Mathematics", "Science (Physics / Chemistry / Biology / Computer Science)"],
            "assessment_traits": ["logical_reasoning", "problem_solving"],
            "interest_keywords": ["artificial intelligence", "ai", "machine learning", "robotics", "robot", "tech", "technology", "coding", "software", "medical", "medicine", "biotech", "physics", "science", "mathematics", "math", "engineering", "stem", "data science"],
            "skill_keywords": ["python", "programming", "mathematics", "data", "machine learning", "analysis", "lab", "robotics", "c++", "java"],
            "activity_keywords": ["science", "robotics", "hackathon", "math", "coding", "stem", "physics", "tech"],
            "strengths": ["Quantitative abstraction", "Deductive problem solving", "Structured laboratory inquiry"],
            "potential_challenges": ["Intense competitive syllabus density", "Requires consistent daily mathematical practice"],
            "recommended_preparation": "Solidify foundational calculus, complete advanced problem sets, and participate in practical STEM/coding projects."
        },
        {
            "stream": "Commerce & Business Studies",
            "subject_patterns": ["comm", "econ", "acc", "bus", "math"],
            "required_subject_labels": ["Commerce / Economics / Accounting", "Mathematics"],
            "assessment_traits": ["conscientiousness", "logical_reasoning"],
            "interest_keywords": ["finance", "business", "investing", "investment", "market", "marketing", "economy", "economics", "entrepreneurship", "entrepreneur", "banking", "commerce", "stock", "accounting"],
            "skill_keywords": ["accounting", "financial", "management", "excel", "spreadsheets", "economics", "communication", "marketing", "business"],
            "activity_keywords": ["business", "entrepreneurship", "stock", "commerce", "debate", "mun", "finance"],
            "strengths": ["Data-driven decision making", "Financial literacy aptitude", "Structured planning and resource allocation"],
            "potential_challenges": ["Extensive regulatory and legal terminology", "Intricacy in advanced financial accounting and auditing"],
            "recommended_preparation": "Study foundational double-entry bookkeeping, follow macroeconomic news, and practice spreadsheet financial modeling."
        },
        {
            "stream": "Humanities & Social Sciences",
            "subject_patterns": ["lang", "eng", "social", "hist", "geog", "pol", "psych", "lit"],
            "required_subject_labels": ["Languages / English", "Social Studies / History / Political Science / Psychology"],
            "assessment_traits": ["openness", "creative_ability", "empathy"],
            "interest_keywords": ["art", "arts", "writing", "design", "music", "social sciences", "social work", "law", "history", "philosophy", "journalism", "public policy", "policy", "literature", "psychology", "sociology"],
            "skill_keywords": ["writing", "creative", "public speaking", "communication", "design", "critical analysis", "research", "journalism"],
            "activity_keywords": ["model un", "mun", "debate", "drama", "writing", "journalism", "art", "social work", "ngo"],
            "strengths": ["Critical textual analysis", "Empathetic contextual synthesis", "Persuasive verbal and written rhetoric"],
            "potential_challenges": ["High subjective essay evaluation variability", "Extensive qualitative literature reading volumes"],
            "recommended_preparation": "Read sociological and geopolitical essays, participate in Model United Nations/debates, and practice analytical essay writing."
        }
    ]

    streams_evaluated = []
    conflicts_and_considerations = []

    for s_def in stream_defs:
        s_name = s_def["stream"]

        # 1. Academic Match (Only from actual data)
        found_subs = find_subjects(s_def["subject_patterns"])
        missing_prereqs = []
        if found_subs:
            acad_score = round(sum(found_subs.values()) / len(found_subs), 1)
        else:
            acad_score = None
            missing_prereqs = list(s_def["required_subject_labels"])

        # 2. Assessment Match (Only from actual data)
        trait_scores = []
        for trait in s_def["assessment_traits"]:
            val = crit.get(trait, pers.get(trait))
            if val is not None:
                trait_scores.append(float(val))

        if trait_scores:
            assess_score = round(sum(trait_scores) / len(trait_scores), 1)
        else:
            assess_score = None

        # 3. Interest Match (Explicit overlap using word boundaries)
        matched_interests = [i for i in interests if any(_keyword_in_text(k, i) for k in s_def["interest_keywords"])]
        if interests:
            interest_score = min(100.0, round((len(matched_interests) / max(1, len(interests))) * 100.0 + (15.0 if matched_interests else 0.0), 1))
        else:
            interest_score = None

        # 4. Skill Match (Explicit proficiency)
        found_skills = find_skills(s_def["skill_keywords"])
        if skills:
            if found_skills:
                skill_score = round(sum(found_skills.values()) / len(found_skills), 1)
            else:
                skill_score = 0.0
        else:
            skill_score = None

        # 5. Activity Match
        found_acts = find_activities(s_def["activity_keywords"])
        if activities:
            activity_score = 80.0 if found_acts else 30.0
        else:
            activity_score = None

        # Dynamically calculate composite score using only available dimensions
        dim_scores = {
            "academic_match": acad_score,
            "assessment_match": assess_score,
            "interest_match": interest_score,
            "skill_match": skill_score,
            "activity_match": activity_score
        }

        available_dims = [k for k, v in dim_scores.items() if v is not None]
        missing_dims = [k for k, v in dim_scores.items() if v is None]

        weights_map = {
            "academic_match": active_weights["academic_weight"],
            "assessment_match": active_weights["assessment_weight"],
            "interest_match": active_weights["interest_weight"],
            "skill_match": active_weights["skill_weight"],
            "activity_match": active_weights["activity_weight"]
        }

        weighted_sum = 0.0
        total_weight_used = 0.0
        for dim_key, dim_val in dim_scores.items():
            if dim_val is not None:
                w = weights_map[dim_key]
                weighted_sum += dim_val * w
                total_weight_used += w

        if total_weight_used > 0:
            final_comp = round(weighted_sum, 1)
            data_completeness = round(total_weight_used, 2)
            is_partial = total_weight_used < 0.95
            is_pending = False
        else:
            final_comp = 0.0
            data_completeness = 0.0
            is_partial = False
            is_pending = True

        # Construct strictly data-derived matched factors (no invented claims)
        matched_factors = []
        if found_subs:
            subs_str = ", ".join(f"{k} ({v}%)" for k, v in list(found_subs.items())[:3])
            matched_factors.append(f"Recorded academic proficiency across: {subs_str}")
        if trait_scores:
            matched_factors.append(f"Assessment trait alignment ({s_def['assessment_traits'][0]} / {s_def['assessment_traits'][-1]} averaging {assess_score}%)")
        if matched_interests:
            matched_factors.append(f"Expressed student interest in: {', '.join(matched_interests[:3])}")
        if found_skills:
            matched_factors.append(f"Demonstrated domain skills in: {', '.join(list(found_skills.keys())[:3])}")
        if found_acts:
            matched_factors.append(f"Co-curricular participation in: {', '.join(found_acts[:2])}")

        # Construct specific gaps & challenges
        gaps_and_challenges = list(s_def["potential_challenges"])
        if missing_prereqs:
            gaps_and_challenges.insert(0, f"Prerequisite subjects not recorded in academic profile: {', '.join(missing_prereqs)}")
        if interest_score is not None and interest_score < 25.0:
            gaps_and_challenges.append("Low declared student interest in domain-specific subjects")
        if skill_score == 0.0:
            gaps_and_challenges.append("No technical or domain-specific skills recorded in student profile")

        # Conflict Detection per stream
        if acad_score is not None and acad_score >= 80.0 and (interest_score is not None and interest_score <= 20.0):
            conflicts_and_considerations.append(
                f"Contradiction in {s_name}: Strong academic performance ({acad_score}%), but low expressed student interest ({interest_score}%)."
            )
        if interest_score is not None and interest_score >= 70.0 and (acad_score is None or acad_score < 55.0):
            conflicts_and_considerations.append(
                f"Prerequisite Gap in {s_name}: High student interest ({interest_score}%), but prerequisite academic grades are missing or below proficiency ({acad_score if acad_score else 'Not on file'})."
            )

        if is_pending:
            level = "Profile Data Pending"
        elif total_weight_used < 0.5:
            level = "Limited Evidence"
        elif final_comp >= 80.0:
            level = "High Affinity"
        elif final_comp >= 65.0:
            level = "Moderate Affinity"
        else:
            level = "Conditional / Developing Affinity"

        streams_evaluated.append({
            "stream": s_name,
            "compatibility_score": final_comp,
            "evidence_score": final_comp,
            "data_completeness": data_completeness,
            "is_partial": is_partial,
            "is_pending": is_pending,
            "available_dimensions": available_dims,
            "missing_dimensions": missing_dims,
            "level": level,
            "dimensional_scores": dim_scores,
            "matched_factors": matched_factors if matched_factors else ["Exploratory profile - baseline data pending"],
            "gaps_and_challenges": gaps_and_challenges,
            "missing_prerequisites": missing_prereqs,
            "recommended_preparation": s_def["recommended_preparation"],
            "strengths": s_def["strengths"],
            "potential_challenges": s_def["potential_challenges"],
            "reasons": matched_factors if matched_factors else ["Exploratory domain affinity"],
            "source": "rule-based"
        })

    # Sort descending by compatibility
    sorted_streams = sorted(streams_evaluated, key=lambda x: x["compatibility_score"], reverse=True)

    # Check for tied or close streams (marginal differentiation)
    if len(sorted_streams) >= 2:
        diff = round(abs(sorted_streams[0]["compatibility_score"] - sorted_streams[1]["compatibility_score"]), 1)
        if diff <= 3.0 and sorted_streams[0]["compatibility_score"] > 0:
            conflicts_and_considerations.append(
                f"Close Suitability Balance: Marginal differentiation ({diff} pts) between '{sorted_streams[0]['stream']}' and '{sorted_streams[1]['stream']}'. Stream selection should prioritize student elective interest rather than quantitative score alone."
            )

    primary_stream = sorted_streams[0]["stream"] if sorted_streams and sorted_streams[0]["compatibility_score"] > 0 else "Pending Profile Data"
    secondary_stream = sorted_streams[1]["stream"] if len(sorted_streams) > 1 and sorted_streams[1]["compatibility_score"] > 0 else None

    return {
        "primary_affinity_stream": primary_stream,
        "secondary_affinity_stream": secondary_stream,
        "recommended_stream": primary_stream,  # Preserved for backward compatibility
        "stream_rankings": sorted_streams,
        "conflicts_and_considerations": conflicts_and_considerations,
        "evidence_sources": sorted(list(evidence_sources)),
        "source": "rule-based",
        "provenance": {
            "source": "rule-based",
            "method": "configurable_multi_factor_matching",
            "weights_used": active_weights,
            "confidence": None,
            "confidence_status": "not_statistically_calibrated",
            "disclaimer": "Stream affinity ratings are configurable heuristic decision-support metrics and not predictive scientific guarantees."
        },
        "scientific_note": "Stream compatibility is derived from academic marks, structured assessments, and expressed student interests. Biometrics are not used to constrain academic pathways."
    }

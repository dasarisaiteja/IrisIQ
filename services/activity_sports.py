import json
from database_student import get_connection


def recommend_activities_and_sports(fused_data):
    """
    Generates tailored recommendations for co-curricular activities and sports.
    Strictly avoids inferring medical or physical capabilities from iris images.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT activity_name, activity_type, benefits, skills_developed_json, aptitude_alignment_json
        FROM activity_catalog
    """)
    rows = cursor.fetchall()
    conn.close()

    assessments = fused_data.get("assessments", {})
    interests = [i.get("interest", "").lower() for i in fused_data.get("interests", [])]
    existing_activities = [a.get("title", "").lower() for a in fused_data.get("activities", [])]

    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})
    vak = assessments.get("learning_style", {}).get("data", {}).get("scores", {})
    behav = assessments.get("behavioral", {}).get("data", {}).get("scores", {})
    emot = assessments.get("emotional_social", {}).get("data", {}).get("scores", {})
    team = assessments.get("team_role", assessments.get("team_player", {})).get("data", {}).get("scores", {})
    think = assessments.get("thinking_action", {}).get("data", {}).get("scores", {})

    # Build comprehensive confirmed trait lookup strictly without unvalidated semantic substitutions
    profile_traits = {}
    for k, v in crit.items():
        if v is not None:
            profile_traits[k] = float(v)
    for k, v in pers.items():
        if v is not None:
            profile_traits[k] = float(v)
    for k, v in behav.items():
        if v is not None:
            profile_traits[k] = float(v)
    for k, v in emot.items():
        if v is not None:
            profile_traits[k] = float(v)

    # 1. Teamwork: explicit Team Player assessment or teamwork skill (Do NOT substitute agreeableness)
    student_skills = {str(s.get("skill", "")).lower(): float(s.get("proficiency", 70.0)) for s in fused_data.get("skills", [])}
    if team.get("team_player_pct") is not None:
        profile_traits["teamwork"] = float(team["team_player_pct"])
    else:
        team_skill = student_skills.get("teamwork", student_skills.get("team collaboration", student_skills.get("team player")))
        if team_skill is not None:
            profile_traits["teamwork"] = float(team_skill)

    # 2. Thinking vs Action
    if think.get("action_pct") is not None:
        profile_traits["thinking_action"] = float(think["action_pct"])

    # 3. Planning
    if pers.get("conscientiousness") is not None:
        profile_traits["planning"] = float(pers["conscientiousness"])

    # 4. Language / Communication: explicit communication skill or confirmed language curriculum mark (Do NOT substitute extraversion)
    comm_skill = student_skills.get("communication", student_skills.get("executive communication", student_skills.get("public speaking")))
    if comm_skill is not None:
        profile_traits["language_communication"] = float(comm_skill)
    else:
        subject_marks = fused_data.get("subject_marks", {})
        import re
        lang_pats = [r'\btechnical\s+english\b', r'\benglish\b', r'\blanguages?\b', r'\blanguage\s*&\s*communication\b']
        for sub_name, val in subject_marks.items():
            if any(re.search(pat, sub_name.lower().strip()) for pat in lang_pats):
                profile_traits["language_communication"] = float(val)
                break
    # (Note: memory must NOT be substituted with logical_reasoning; visual_spatial must NOT be substituted with VAK visual preference)

    # Incorporate cognitive engine domain indicators if already fused
    cog = fused_data.get("cognitive", {})
    for d in cog.get("domains", []):
        d_name = d.get("domain", "").lower().replace(" ", "_").replace("/", "_")
        d_score = d.get("score")
        if d_score is not None:
            if "attention" in d_name:
                profile_traits["attention_focus"] = float(d_score)
            elif "memory" in d_name:
                profile_traits["memory"] = float(d_score)
            elif "planning" in d_name:
                profile_traits["planning"] = float(d_score)
            elif "visual" in d_name or "spatial" in d_name:
                profile_traits["visual_spatial"] = float(d_score)
            elif "language" in d_name or "communication" in d_name:
                profile_traits["language_communication"] = float(d_score)

    co_curricular_recs = []
    sports_recs = []

    for r in rows:
        name = r[0]
        act_type = r[1]
        benefits = r[2]
        skills_dev = json.loads(r[3]) if r[3] else []
        apt_align = json.loads(r[4]) if r[4] else {}

        # Evaluate trait alignment strictly from confirmed assessment data
        matched_traits = []
        missing_traits = []
        apt_scores = []
        total_req = len(apt_align)
        for trait, req in apt_align.items():
            curr = profile_traits.get(trait)
            if curr is not None:
                matched_traits.append(trait)
                apt_scores.append(min(100.0, (float(curr) / max(1.0, float(req))) * 100.0))
            else:
                missing_traits.append(trait)

        # Check explicit interest or existing activity match
        name_low = name.lower()
        has_interest = any(w in name_low for w in interests) if interests else False
        has_activity = any(name_low in ea for ea in existing_activities) if existing_activities else False

        if apt_scores:
            base_score = sum(apt_scores) / max(1, total_req)
            if has_interest or has_activity:
                base_score = min(98.0, base_score + 15.0)
            compat = round(base_score, 1)
            is_pending = False
            status = "completed"
            is_partial = len(matched_traits) < total_req
            if is_partial:
                level = "Partial Alignment" if compat < 75.0 else "Recommended"
                reason = f"Partial alignment ({len(matched_traits)}/{total_req} traits) in {', '.join(matched_traits[:2])}"
            elif compat >= 85.0:
                level = "Strong Alignment"
                reason = f"Strong alignment across required traits in {', '.join(matched_traits[:2])}"
            elif compat >= 70.0:
                level = "Recommended"
                reason = f"Good alignment across profile indicators in {', '.join(matched_traits[:2])}"
            else:
                level = "Exploratory"
                reason = f"Foundational alignment in {', '.join(matched_traits[:2])}"

            source = "multi-source" if (has_interest or has_activity) else "assessment-derived"
        elif has_interest or has_activity:
            compat = 75.0
            is_pending = False
            status = "completed"
            is_partial = False
            level = "Interest Aligned"
            reason = f"Directly aligns with student's declared interest or co-curricular participation in {name}"
            source = "profile-derived"
        else:
            compat = None
            is_pending = True
            status = "pending"
            is_partial = False
            level = "Unassessed / Pending"
            reason = "Assessment traits and declared interests are pending for this activity."
            source = "rule-based"

        rec_item = {
            "activity": name,
            "type": act_type,
            "compatibility": compat,
            "is_pending": is_pending,
            "is_partial": is_partial,
            "matched_traits": matched_traits,
            "missing_traits": missing_traits,
            "available_trait_count": len(matched_traits),
            "required_trait_count": total_req,
            "status": status,
            "level": level,
            "reason": reason,
            "benefits": benefits,
            "skills_developed": skills_dev,
            "source": source,
            "confidence": None,
            "confidence_status": "not_statistically_calibrated"
        }

        if act_type == "co-curricular":
            co_curricular_recs.append(rec_item)
        else:
            sports_recs.append(rec_item)

    # Sort so assessed items with highest compatibility appear first, pending at the end
    co_curricular_sorted = sorted(co_curricular_recs, key=lambda x: (x["compatibility"] is not None, x["compatibility"] or 0), reverse=True)
    sports_sorted = sorted(sports_recs, key=lambda x: (x["compatibility"] is not None, x["compatibility"] or 0), reverse=True)

    all_recs = co_curricular_recs + sports_recs
    all_pending = all(r.get("is_pending") for r in all_recs) if all_recs else True

    return {
        "co_curricular_recommendations": co_curricular_sorted,
        "sports_recommendations": sports_sorted,
        "is_pending": all_pending,
        "status": "pending" if all_pending else "completed",
        "message": "Profile Data Pending" if all_pending else "Completed",
        "source": "rule-based",
        "confidence": None,
        "confidence_status": "not_statistically_calibrated",
        "scientific_disclaimer": "Sports recommendations are guided solely by declared interests, activity history, and structured assessment coordination preferences. No physical or medical attributes are inferred from iris imagery."
    }

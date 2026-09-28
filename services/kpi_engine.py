def compute_kpis(fused_data):
    """
    Computes 9 standard student Key Performance Indicators (KPIs) with target benchmarks,
    measured gaps, and actionable recommendations.
    Strictly avoids fabricating defaults when assessment or academic data is absent.
    Confidence is uncalibrated (null / not_statistically_calibrated).
    """
    subject_marks = fused_data.get("subject_marks", {})
    assessments = fused_data.get("assessments", {})
    skills = fused_data.get("skills", [])
    activities = fused_data.get("activities", [])

    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})
    lead_entry = assessments.get("leadership_style") or assessments.get("leadership") or {}
    lead = lead_entry.get("data", {}).get("scores", {})
    team_entry = assessments.get("team_player") or assessments.get("team_role") or {}
    team = team_entry.get("data", {}).get("scores", {})
    soc = assessments.get("emotional_social", {}).get("data", {}).get("scores", {})

    # 1. Academic Performance
    if subject_marks:
        acad_avg = sum(subject_marks.values()) / max(1, len(subject_marks))
    else:
        acad_avg = None

    # 2. Sports Performance (Only evaluate if explicit sports activities are recorded)
    if activities:
        sports_activities = [a for a in activities if str(a.get("type", "")).lower() in ["sports", "athletics", "swimming"]]
        if sports_activities:
            sports_score = min(95.0, 50.0 + len(sports_activities) * 15.0)
        else:
            sports_score = None
    else:
        sports_score = None

    # 3. Communication
    pers_ext = pers.get("extraversion")
    soc_conf = soc.get("social_confidence")
    if pers_ext is not None and soc_conf is not None:
        comm_score = round(pers_ext * 0.4 + soc_conf * 0.6, 1)
    elif pers_ext is not None:
        comm_score = round(pers_ext, 1)
    elif soc_conf is not None:
        comm_score = round(soc_conf, 1)
    else:
        comm_score = None

    # 4. Problem Solving
    prob_val = crit.get("problem_solving")
    prob_score = round(prob_val, 1) if prob_val is not None else None

    # 5. Creativity
    crit_creat = crit.get("creative_ability")
    pers_open = pers.get("openness")
    if crit_creat is not None and pers_open is not None:
        creat_score = round(crit_creat * 0.6 + pers_open * 0.4, 1)
    elif crit_creat is not None:
        creat_score = round(crit_creat, 1)
    elif pers_open is not None:
        creat_score = round(pers_open, 1)
    else:
        creat_score = None

    # 6. Leadership (Neutral exploratory orientation indicator; does not penalize balanced orientation)
    task_pct = lead.get("task_oriented_pct")
    rel_pct = lead.get("relationship_oriented_pct")
    if task_pct is not None and rel_pct is not None:
        orientation_balance = round(100.0 - abs(float(task_pct) - float(rel_pct)), 1)
        if abs(float(task_pct) - float(rel_pct)) <= 15.0:
            lead_status = "Balanced Leadership Orientation"
        elif float(task_pct) > float(rel_pct):
            lead_status = "Task-Directed Orientation"
        else:
            lead_status = "Relational Leadership Orientation"
        lead_score = orientation_balance
        lead_extra = {
            "task_orientation_pct": float(task_pct),
            "relationship_orientation_pct": float(rel_pct),
            "orientation_balance": orientation_balance,
            "leadership_indicator_status": lead_status
        }
    elif task_pct is not None:
        lead_score = round(float(task_pct), 1)
        lead_status = "Task-Directed Orientation"
        lead_extra = {
            "task_orientation_pct": float(task_pct),
            "relationship_orientation_pct": None,
            "orientation_balance": None,
            "leadership_indicator_status": lead_status
        }
    elif rel_pct is not None:
        lead_score = round(float(rel_pct), 1)
        lead_status = "Relational Leadership Orientation"
        lead_extra = {
            "task_orientation_pct": None,
            "relationship_orientation_pct": float(rel_pct),
            "orientation_balance": None,
            "leadership_indicator_status": lead_status
        }
    else:
        lead_score = None
        lead_status = "pending"
        lead_extra = {
            "task_orientation_pct": None,
            "relationship_orientation_pct": None,
            "orientation_balance": None,
            "leadership_indicator_status": "pending"
        }

    # 7. Technical Skills
    tech_skills = [s.get("proficiency") for s in skills if s.get("type") == "technical" and s.get("proficiency") is not None]
    tech_score = round(sum(tech_skills) / len(tech_skills), 1) if tech_skills else None

    # 8. Teamwork
    team_pl = team.get("team_player_pct")
    pers_agr = pers.get("agreeableness")
    if team_pl is not None and pers_agr is not None:
        team_score = round(team_pl * 0.6 + pers_agr * 0.4, 1)
    elif team_pl is not None:
        team_score = round(team_pl, 1)
    elif pers_agr is not None:
        team_score = round(pers_agr, 1)
    else:
        team_score = None

    # 9. Learning Progress
    pers_con = pers.get("conscientiousness")
    crit_pre = crit.get("pressure_handling")
    if pers_con is not None and crit_pre is not None:
        learn_score = round(pers_con * 0.5 + crit_pre * 0.5, 1)
    elif pers_con is not None:
        learn_score = round(pers_con, 1)
    elif crit_pre is not None:
        learn_score = round(crit_pre, 1)
    else:
        learn_score = None

    kpis_def = [
        {"category": "Academic Performance", "current": round(acad_avg, 1) if acad_avg is not None else None, "target": 90.0, "rec": "Focus on high-weightage topics and spaced retrieval practice to close the examination gap.", "source": "academic-derived"},
        {"category": "Sports Performance", "current": round(sports_score, 1) if sports_score is not None else None, "target": 80.0, "rec": "Maintain consistent weekly aerobic and agility training routines.", "source": "profile-derived"},
        {"category": "Communication", "current": comm_score, "target": 85.0, "rec": "Engage in public speaking, elocution debates, and multi-disciplinary seminar presentations.", "source": "assessment-derived"},
        {"category": "Problem Solving", "current": prob_score, "target": 90.0, "rec": "Solve advanced algorithmic challenges and unstructured real-world problem sets.", "source": "assessment-derived"},
        {"category": "Creative Thinking Indicator", "category_alias": "Creativity", "current": creat_score, "target": 85.0, "rec": "Participate in design-thinking hackathons and multidisciplinary arts/media workshops.", "source": "assessment-derived", "note": "Assessment-derived heuristic indicator; shares underlying questionnaire inputs with Cognitive Creative Thinking."},
        {"category": "Leadership", "current": lead_score, "target": 85.0, "rec": "Take active ownership of team initiatives and practice empathetic milestone delegation.", "source": "assessment-derived", "note": "Exploratory orientation indicator; balance does not imply deficiency.", "extra": lead_extra},
        {"category": "Technical Skills", "current": tech_score, "target": 88.0, "rec": "Undertake end-to-end technical capstone implementations and obtain industry certifications.", "source": "profile-derived"},
        {"category": "Teamwork", "current": team_score, "target": 90.0, "rec": "Actively mediate cross-functional consensus and support struggling peers during group assignments.", "source": "assessment-derived"},
        {"category": "Self-Directed Study Habits", "category_alias": "Learning Progress", "current": learn_score, "target": 88.0, "rec": "Track weekly curriculum progress with milestone checklists and self-audit retrospectives.", "source": "assessment-derived", "note": "Assessment-derived study habits indicator based on conscientiousness and pressure handling; not a longitudinal grade progression measure."}
    ]

    results = []
    for k in kpis_def:
        if k["current"] is not None:
            if k["category"] == "Leadership":
                gap = 0.0
                status_str = k.get("extra", {}).get("leadership_indicator_status", "Orientation Recorded")
            else:
                gap = round(max(0.0, k["target"] - k["current"]), 1)
                status_str = "Target Met" if gap == 0 else ("Minor Gap" if gap <= 10 else "Development Priority")

            kpi_entry = {
                "category": k["category"],
                "category_alias": k.get("category_alias"),
                "current_score": k["current"],
                "target_score": k["target"],
                "gap": gap,
                "status": status_str,
                "recommendation": k["rec"],
                "source": k.get("source", "assessment-derived"),
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "is_pending": False,
                "note": k.get("note")
            }
            if "extra" in k:
                kpi_entry.update(k["extra"])
            results.append(kpi_entry)
        else:
            kpi_entry = {
                "category": k["category"],
                "category_alias": k.get("category_alias"),
                "current_score": None,
                "target_score": k["target"],
                "gap": None,
                "status": "pending",
                "recommendation": f"Assessment/data required to evaluate {k['category']}.",
                "source": k.get("source", "assessment-derived"),
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "is_pending": True,
                "message": "Profile Data Pending",
                "note": k.get("note")
            }
            if "extra" in k:
                kpi_entry.update(k["extra"])
            results.append(kpi_entry)

    valid_scores = [r["current_score"] for r in results if r["current_score"] is not None]
    return {
        "kpis": results,
        "overall_kpi_average": round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None,
        "source": "rule-based",
        "confidence": None,
        "confidence_status": "not_statistically_calibrated"
    }

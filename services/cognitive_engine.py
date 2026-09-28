import re


def _match_subject(subject_marks, target_patterns, exact_keys=None):
    if not subject_marks:
        return None
    # Normalize subject_marks keys to lowercase stripped strings for robust matching
    norm_marks = {str(k).lower().strip(): v for k, v in subject_marks.items()}
    if exact_keys:
        for ek in exact_keys:
            ek_l = ek.lower().strip()
            if ek_l in norm_marks:
                return float(norm_marks[ek_l])
    for pattern in target_patterns:
        for sub_name, val in norm_marks.items():
            if re.search(pattern, sub_name):
                return float(val)
    return None


def compute_cognitive_profile(fused_data):
    """
    Computes a safe 10-domain cognitive indicator profile derived from structured
    assessment indicators and confirmed curriculum marks.
    Strictly avoids claiming that iris scans or questionnaires measure physical neurons,
    brain structure, or clinical IQ/EQ.
    """
    assessments = fused_data.get("assessments", {})
    subject_marks = fused_data.get("subject_marks", {})
    skills = fused_data.get("skills", {})

    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})
    vak = assessments.get("learning_style", {}).get("data", {}).get("scores", {})
    team = assessments.get("team_player", {}).get("data", {}).get("scores", {})
    soc = assessments.get("emotional_social", {}).get("data", {}).get("scores", {})

    has_assessments = any(
        bool(assessments.get(dom, {}).get("data", {}).get("scores", {}))
        for dom in ["critical_abilities", "personality", "learning_style", "team_player", "emotional_social"]
    )
    has_academics = bool(subject_marks)

    # If both assessment and academic records are unavailable, return an explicit pending state
    if not has_assessments and not has_academics:
        return {
            "status": "pending",
            "is_pending": True,
            "is_partial": False,
            "valid_domain_count": 0,
            "total_domain_count": 10,
            "message": "Profile Data Pending",
            "domains": [],
            "overall_cognitive_index": None,
            "overall_index": None,
            "legacy_neuron_reference": {
                "is_legacy_reference": True,
                "disclaimer": "Historical demonstration metric only. Scientific disclaimer: Static iris biometrics do not measure physical human neuron distribution or intracranial activity.",
                "metrics": {
                    "demonstration_composite_strength": None,
                    "demonstration_neuro_strength": None,  # legacy alias
                    "demonstration_consistency": None,
                    "demonstration_stability": None
                }
            },
            "confidence": None,
            "confidence_status": "not_statistically_calibrated",
            "source": "assessment-derived",
            "methodology": "Linear composite indexing combining structured assessment indicators and curriculum marks"
        }

    # Extract confirmed subject marks using safe case-insensitive token/pattern matching
    math_score = _match_subject(
        subject_marks,
        [r'\btechnical\s+math\b', r'\bmath(?:ematics|s)?\b', r'\bcalculus\b', r'\balgebra\b'],
        exact_keys=["mathematics", "math", "maths"]
    )
    lang_score = _match_subject(
        subject_marks,
        [r'\btechnical\s+english\b', r'\benglish\b', r'\blanguages?\b', r'\blanguage\s*&\s*communication\b'],
        exact_keys=["languages", "english", "technical english & communication", "technical english", "english communication", "language & communication"]
    )
    sci_score = _match_subject(
        subject_marks,
        [r'\bcomputer\s+science\b', r'\bphysics\b', r'\bscience\b', r'\bchemistry\b', r'\bbiology\b'],
        exact_keys=["science", "physics", "computer science", "computer science & ai", "physics & electronics"]
    )

    # 1. Logical Reasoning (Critical ability + Math)
    crit_log = crit.get("logical_reasoning")
    if crit_log is not None and math_score is not None:
        logical = round(crit_log * 0.7 + math_score * 0.3, 1)
    elif crit_log is not None:
        logical = round(crit_log, 1)
    elif math_score is not None:
        logical = round(math_score, 1)
    else:
        logical = None

    # 2. Problem Solving (Critical ability + Science)
    crit_prob = crit.get("problem_solving")
    if crit_prob is not None and sci_score is not None:
        problem_solving = round(crit_prob * 0.75 + sci_score * 0.25, 1)
    elif crit_prob is not None:
        problem_solving = round(crit_prob, 1)
    elif sci_score is not None:
        problem_solving = round(sci_score, 1)
    else:
        problem_solving = None

    # 3. Creative Thinking (Personality Openness + Creative ability)
    crit_creat = crit.get("creative_ability")
    pers_open = pers.get("openness")
    if crit_creat is not None and pers_open is not None:
        creative = round(crit_creat * 0.6 + pers_open * 0.4, 1)
    elif crit_creat is not None:
        creative = round(crit_creat, 1)
    elif pers_open is not None:
        creative = round(pers_open, 1)
    else:
        creative = None

    # 4. Planning (Personality Conscientiousness + Problem Solving)
    pers_consc = pers.get("conscientiousness")
    if pers_consc is not None and crit_prob is not None:
        planning = round(pers_consc * 0.7 + crit_prob * 0.3, 1)
    elif pers_consc is not None:
        planning = round(pers_consc, 1)
    elif crit_prob is not None:
        planning = round(crit_prob, 1)
    else:
        planning = None

    # 5. Language / Communication (Languages + Extraversion)
    pers_extra = pers.get("extraversion")
    if lang_score is not None and pers_extra is not None:
        communication = round(lang_score * 0.6 + pers_extra * 0.4, 1)
    elif lang_score is not None:
        communication = round(lang_score, 1)
    elif pers_extra is not None:
        communication = round(pers_extra, 1)
    else:
        communication = None

    # 6. Visual / Spatial Processing (Explicit Spatial Ability Assessment)
    # Provenance Note (Step 14 Fix 8): Self-reported VAK visual preference indicates study/learning
    # presentation preference, NOT measured spatial cognition. To prevent conflation, Visual/Spatial
    # Processing is derived only when an explicit spatial assessment is present (e.g. crit.visual_spatial).
    # If unassessed, it remains Profile Data Pending rather than fabricating a score from VAK.
    crit_spatial = crit.get("visual_spatial") or crit.get("spatial_reasoning") or crit.get("spatial")
    if crit_spatial is not None:
        visual_spatial = round(float(crit_spatial), 1)
    else:
        visual_spatial = None

    # 7. Attention / Focus (Conscientiousness + Pressure handling)
    crit_press = crit.get("pressure_handling")
    if pers_consc is not None and crit_press is not None:
        attention_focus = round(pers_consc * 0.5 + crit_press * 0.5, 1)
    elif pers_consc is not None:
        attention_focus = round(pers_consc, 1)
    elif crit_press is not None:
        attention_focus = round(crit_press, 1)
    else:
        attention_focus = None

    # 8. Memory (Academic average + Conscientiousness)
    acad_avg = (sum(subject_marks.values()) / len(subject_marks)) if subject_marks else None
    if acad_avg is not None and pers_consc is not None:
        memory = round(acad_avg * 0.6 + pers_consc * 0.4, 1)
    elif acad_avg is not None:
        memory = round(acad_avg, 1)
    elif pers_consc is not None:
        memory = round(pers_consc, 1)
    else:
        memory = None

    # 9. Analytical Thinking (Logical reasoning + Science)
    # Provenance Note (Step 14 Fix 6): Analytical Thinking is derived from Logical Reasoning (60%)
    # and Science academic performance (40%). Logical Reasoning itself is a composite of Critical
    # Abilities logical reasoning (70%) and Mathematics (30%). This preserves calibrated composite
    # scoring while maintaining full traceability back to primitive assessments and curriculum marks.
    if logical is not None and sci_score is not None:
        analytical = round(logical * 0.6 + sci_score * 0.4, 1)
    elif logical is not None:
        analytical = round(logical, 1)
    elif sci_score is not None:
        analytical = round(sci_score, 1)
    else:
        analytical = None

    # 10. Social / Collaborative Skills (Agreeableness + Team player + Empathy)
    pers_agree = pers.get("agreeableness")
    team_pl = team.get("team_player_pct")
    soc_emp = soc.get("empathy")
    soc_comps = [(c, w) for c, w in [(pers_agree, 0.4), (team_pl, 0.3), (soc_emp, 0.3)] if c is not None]
    if soc_comps:
        tot_w = sum(w for _, w in soc_comps)
        social_collab = round(sum(c * w for c, w in soc_comps) / tot_w, 1)
    else:
        social_collab = None

    domain_raw = [
        ("Logical Reasoning", logical),
        ("Problem Solving", problem_solving),
        ("Creative Thinking", creative),
        ("Planning", planning),
        ("Language/Communication", communication),
        ("Visual/Spatial Processing", visual_spatial),
        ("Attention/Focus", attention_focus),
        ("Memory", memory),
        ("Analytical Thinking", analytical),
        ("Social/Collaborative Skills", social_collab)
    ]

    domains = []
    for d_name, d_score in domain_raw:
        if d_name == "Visual/Spatial Processing":
            if d_score is not None:
                note_str = "Derived from explicit spatial ability assessment. Non-clinical decision-support indicator."
            else:
                note_str = "Requires explicit spatial reasoning assessment. Self-reported VAK visual preference represents study style and is not conflated with cognitive spatial ability."
        else:
            note_str = None
        if d_score is not None:
            domains.append({
                "domain": d_name,
                "score": d_score,
                "category": _cat(d_score),
                "is_pending": False,
                "note": note_str,
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            })
        else:
            domains.append({
                "domain": d_name,
                "score": None,
                "category": "Profile Data Pending",
                "is_pending": True,
                "note": note_str,
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            })

    valid_scores = [d["score"] for d in domains if d["score"] is not None]
    valid_count = len(valid_scores)

    if valid_count < 3:
        overall_index = None
        is_partial = True if valid_count > 0 else False
        is_pending = True
        cog_message = "Limited assessment evidence" if valid_count > 0 else "Profile Data Pending"
    else:
        overall_index = round(sum(valid_scores) / valid_count, 1)
        is_partial = valid_count < len(domains)
        is_pending = False
        cog_message = "Completed"

    # Legacy Reference Section (Non-clinical demonstration)
    if logical is not None and problem_solving is not None:
        demo_strength = round((logical + problem_solving) / 2.0, 1)
    elif logical is not None:
        demo_strength = round(logical, 1)
    elif problem_solving is not None:
        demo_strength = round(problem_solving, 1)
    else:
        demo_strength = None

    legacy_neuron_reference = {
        "is_legacy_reference": True,
        "disclaimer": "Historical demonstration metric only. Scientific disclaimer: Static iris biometrics do not measure physical human neuron distribution or intracranial activity.",
        "metrics": {
            "demonstration_composite_strength": demo_strength,
            "demonstration_neuro_strength": demo_strength,  # legacy alias
            "demonstration_consistency": round(planning, 1) if planning is not None else None,
            "demonstration_stability": round(attention_focus, 1) if attention_focus is not None else None
        }
    }

    return {
        "domains": domains,
        "legacy_neuron_reference": legacy_neuron_reference,
        "overall_cognitive_index": overall_index,
        "overall_index": overall_index,
        "is_pending": is_pending,
        "is_partial": is_partial,
        "valid_domain_count": valid_count,
        "total_domain_count": len(domains),
        "status": "pending" if is_pending else "completed",
        "message": cog_message,
        "confidence": None,
        "confidence_status": "not_statistically_calibrated",
        "source": "assessment-derived",
        "methodology": "Linear composite indexing combining structured assessment indicators and curriculum marks"
    }


def _cat(score):
    if score is None:
        return "Profile Data Pending"
    if score >= 80.0:
        return "Advanced / Exceptional"
    elif score >= 65.0:
        return "Proficient / Strong"
    elif score >= 50.0:
        return "Moderate / Capable"
    return "Emerging / Needs Focus"

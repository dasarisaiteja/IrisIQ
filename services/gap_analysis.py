import re

def compute_development_gaps(fused_data, target_career=None):
    """
    Computes tangible skill and ability development gaps, providing actionable learning paths.
    """
    skills = {s.get("skill", "").lower(): float(s.get("proficiency", 60.0)) for s in fused_data.get("skills", [])}
    subject_marks = fused_data.get("subject_marks", {})
    assessments = fused_data.get("assessments", {})
    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})
    pers = assessments.get("personality", {}).get("data", {}).get("scores", {})
    lead_entry = (
        assessments.get("leadership_style")
        or assessments.get("leadership")
        or {}
    )
    lead = lead_entry.get("data", {}).get("scores", {})
    team = assessments.get("team_role", assessments.get("team_player", {})).get("data", {}).get("scores", {})

    # Leadership source priority (Leadership assessment -> Team management role -> None. Do not use agreeableness)
    lead_task = lead.get("task_oriented_pct")
    lead_rel = lead.get("relationship_oriented_pct")
    team_mgmt = team.get("team_management_pct")
    if lead_task is not None and lead_rel is not None:
        lead_current = round(100.0 - abs(float(lead_task) - float(lead_rel)), 1)
    elif lead_task is not None:
        lead_current = float(lead_task)
    elif team_mgmt is not None:
        lead_current = float(team_mgmt)
    else:
        lead_current = None

    # Communication source priority (Communication skill -> Language subject mark -> None. Do not use extraversion)
    comm_skill = skills.get("communication", skills.get("executive communication", skills.get("public speaking")))
    
    # Safe token/pattern matching for Language / English subjects (case-insensitive)
    lang_grade = None
    exact_lang_keys = ["languages", "english", "technical english & communication", "technical english", "english communication", "language & communication"]
    norm_subject_marks = {str(k).lower().strip(): v for k, v in subject_marks.items()}
    for ek in exact_lang_keys:
        if ek in norm_subject_marks:
            lang_grade = float(norm_subject_marks[ek])
            break
    if lang_grade is None:
        lang_pats = [r'\btechnical\s+english\b', r'\benglish\b', r'\blanguages?\b', r'\blanguage\s*&\s*communication\b']
        for sub_name, val in norm_subject_marks.items():
            if any(re.search(pat, sub_name) for pat in lang_pats):
                lang_grade = float(val)
                break

    if comm_skill is not None:
        comm_current = comm_skill
    elif lang_grade is not None:
        comm_current = lang_grade
    else:
        comm_current = None

    benchmarks = [
        {
            "skill": "Python Programming",
            "category": "Technical",
            "current": skills.get("python", skills.get("python programming")),
            "required": 90.0,
            "recom": "Advanced Python idioms, asynchronous workflows, and building production web/data APIs"
        },
        {
            "skill": "Algorithmic Problem Solving",
            "category": "Cognitive",
            "current": crit.get("problem_solving"),
            "required": 88.0,
            "recom": "Practice dynamic programming, tree traversals, and graph problems on competitive coding platforms"
        },
        {
            "skill": "Executive Communication",
            "category": "Soft Skill",
            "current": comm_current,
            "required": 85.0,
            "recom": "Engage in structured debate societies, elocution presentations, and technical manuscript writing"
        },
        {
            "skill": "Data & Statistical Analysis",
            "category": "Analytical",
            "current": skills.get("data analysis", skills.get("data & statistical analysis")),
            "required": 85.0,
            "recom": "Complete exploratory data analysis projects with Pandas, NumPy, and statistical hypothesis testing"
        },
        {
            "skill": "Team Leadership & Coordination",
            "category": "Leadership",
            "current": lead_current,
            "required": 85.0,
            "recom": "Lead academic team sprints, practice milestone decomposition, and mentor junior study cohorts"
        }
    ]

    gap_items = []
    for b in benchmarks:
        curr = b["current"]
        if curr is not None:
            curr_score = round(float(curr), 1)
            gap = round(max(0.0, b["required"] - curr_score), 1)
            status = "Proficient" if gap == 0 else ("Minor Gap" if gap <= 10 else "Significant Gap")
            is_assessed = True
            recom = b["recom"]
            src = "skill-derived" if b["category"] in ["Technical", "Analytical"] else "assessment-derived"
        else:
            curr_score = None
            gap = None
            status = "Unassessed"
            is_assessed = False
            recom = f"Complete foundational assessment or submit coursework records for {b['skill']}."
            src = "unassessed"

        gap_items.append({
            "skill": b["skill"],
            "category": b["category"],
            "current_score": curr_score,
            "required_score": round(b["required"], 1),
            "gap": gap,
            "status": status,
            "is_assessed": is_assessed,
            "recommendation": recom,
            "learning_roadmap": [
                f"Phase 1 (Weeks 1-4): Complete foundational exercises in {b['skill']}",
                f"Phase 2 (Weeks 5-8): Build a self-directed applied project addressing key gaps",
                f"Phase 3 (Weeks 9-12): Undergo peer assessment and portfolio code review"
            ],
            "source": src
        })

    all_unassessed = all(not g.get("is_assessed") for g in gap_items)

    return {
        "gaps": gap_items,
        "total_tracked_skills": len(gap_items),
        "is_pending": all_unassessed,
        "status": "pending" if all_unassessed else "completed",
        "message": "Profile Data Pending" if all_unassessed else "Completed",
        "source": "rule-based"
    }

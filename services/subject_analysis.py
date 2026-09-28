def analyze_critical_subjects(fused_data):
    """
    Evaluates academic subjects and determines strength level, compatibility,
    development areas, and actionable improvement recommendations.
    """
    academics = fused_data.get("academics", [])
    assessments = fused_data.get("assessments", {})
    crit = assessments.get("critical_abilities", {}).get("data", {}).get("scores", {})

    if not academics:
        return {
            "subjects": [],
            "average_score": None,
            "is_pending": True,
            "status": "pending",
            "message": "Profile Data Pending",
            "source": "academic-derived"
        }

    results = []
    for item in academics:
        sub_name = item.get("subject", "General Subject")
        score = item.get("percentage", item.get("marks", 75.0))

        # Strength level
        if score >= 85.0:
            strength = "Mastery / High Strength"
            compat = "High Affinity"
        elif score >= 70.0:
            strength = "Proficient / Solid"
            compat = "Moderate Affinity"
        elif score >= 55.0:
            strength = "Developing / Average"
            compat = "Conditional Affinity"
        else:
            strength = "Critical Focus Needed"
            compat = "Low Affinity"

        # Domain specific development area and recommendations
        sub_lower = sub_name.lower()
        if "math" in sub_lower:
            dev_area = "Abstract formulation and speed problem solving under exam conditions"
            recom = "Practice advanced algebraic proofs, timed Olympiad problems, and applied statistical modeling."
        elif "sci" in sub_lower or "phys" in sub_lower or "chem" in sub_lower or "bio" in sub_lower:
            dev_area = "Hypothesis experimentation, conceptual physics derivations, and biological systems recall"
            recom = "Incorporate visual virtual lab simulations, schematic flowcharts, and formula flashcard reviews."
        elif "lang" in sub_lower or "eng" in sub_lower:
            dev_area = "Critical reading analysis, vocabulary nuance, and formal persuasive essay composition"
            recom = "Engage in editorial reading, analytical essay writing with peer review, and verbal presentation exercises."
        elif "comp" in sub_lower or "info" in sub_lower or "code" in sub_lower:
            dev_area = "Algorithmic optimization, time complexity reduction, and full-stack software architecture"
            recom = "Participate in competitive coding platforms, build open-source portfolio projects, and study system design."
        elif "comm" in sub_lower or "econ" in sub_lower or "acc" in sub_lower or "bus" in sub_lower:
            dev_area = "Financial statement analysis, market equilibrium dynamics, and business case evaluations"
            recom = "Analyze real-world corporate balance sheets, follow economic policy trends, and simulate investment portfolios."
        else:
            dev_area = "Conceptual mastery, continuous spaced revision, and active practice testing"
            recom = "Structured weekly review schedule, self-testing with past papers, and synthesized mind maps."

        results.append({
            "subject": sub_name,
            "current_score": round(score, 1),
            "strength_level": strength,
            "compatibility": compat,
            "development_area": dev_area,
            "recommended_improvement": recom,
            "source": item.get("source", "academic-derived")
        })

    return {
        "subjects": results,
        "average_score": round(sum(s["current_score"] for s in results) / max(1, len(results)), 1),
        "is_pending": False,
        "status": "completed",
        "message": "Completed",
        "source": "academic-derived"
    }

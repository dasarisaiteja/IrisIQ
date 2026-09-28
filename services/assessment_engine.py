import json
import sqlite3
from datetime import datetime
from database_student import get_connection


def get_assessment_questions(domain=None, active_only=True):
    """
    Retrieves questions filtered by domain or all domains.
    Fully configurable: reads subcategory, answer_type, scoring_weights,
    scoring_direction, scoring_weight, is_reverse_scored, and is_active.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Query with column inspection for robust backward compatibility
    cursor.execute("PRAGMA table_info(assessment_questions)")
    col_names = [col[1] for col in cursor.fetchall()]

    has_new_cols = "answer_type" in col_names and "scoring_weight" in col_names

    if has_new_cols:
        query_cols = (
            "id, domain, subcategory, question_text, answer_type, options_json, "
            "scoring_weights_json, scoring_direction, scoring_weight, is_reverse_scored, "
            "is_active, version"
        )
    else:
        query_cols = "id, domain, subcategory, question_text, options_json, scoring_weights_json, version"

    where_clauses = []
    params = []

    if active_only and has_new_cols:
        where_clauses.append("is_active = 1")

    if domain:
        if domain in ["leadership", "leadership_style"]:
            where_clauses.append("(domain = 'leadership' OR domain = 'leadership_style')")
        elif domain in ["team_role", "team_player"]:
            where_clauses.append("(domain = 'team_role' OR domain = 'team_player')")
        else:
            where_clauses.append("domain = ?")
            params.append(domain)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"SELECT {query_cols} FROM assessment_questions {where_sql} ORDER BY domain, id"

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    questions = []
    for r in rows:
        if has_new_cols:
            opts = json.loads(r[5]) if r[5] else []
            weights = json.loads(r[6]) if r[6] else {}
            weight_val = float(r[8]) if r[8] is not None else float(weights.get("weight", 1.0))
            is_rev = bool(r[9]) if r[9] is not None else bool(weights.get("is_reverse_scored", False))
            is_act = bool(r[10]) if r[10] is not None else True
            direction = r[7] or ("negative" if is_rev else "positive")
            ans_type = r[4] or "likert"
            ver = r[11] or "v1"
        else:
            opts = json.loads(r[4]) if r[4] else []
            weights = json.loads(r[5]) if r[5] else {}
            weight_val = float(weights.get("weight", 1.0))
            is_rev = bool(weights.get("is_reverse_scored", False))
            is_act = True
            direction = "negative" if is_rev else "positive"
            ans_type = "likert"
            ver = r[6] or "v1"

        questions.append({
            "id": r[0],
            "domain": r[1],
            "subcategory": r[2],
            "question_text": r[3],
            "answer_type": ans_type,
            "options": opts,
            "scoring_weights": weights,
            "scoring_direction": direction,
            "scoring_weight": weight_val,
            "is_reverse_scored": is_rev,
            "is_active": is_act,
            "version": ver
        })
    return questions


def add_assessment_question(domain, subcategory, question_text, answer_type="likert",
                            options=None, scoring_weights=None, scoring_direction="positive",
                            scoring_weight=1.0, is_reverse_scored=False, is_active=True, version="v1"):
    """
    Programmatic interface for expanding the question bank with custom/larger surveys.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(assessment_questions)")
    col_names = [col[1] for col in cursor.fetchall()]

    opts_json = json.dumps(options or [])
    weights_json = json.dumps(scoring_weights or {})

    if "answer_type" in col_names:
        cursor.execute("""
            INSERT INTO assessment_questions (
                domain, subcategory, question_text, answer_type, options_json,
                scoring_weights_json, scoring_direction, scoring_weight,
                is_reverse_scored, is_active, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            domain, subcategory, question_text, answer_type, opts_json,
            weights_json, scoring_direction, float(scoring_weight),
            1 if is_reverse_scored else 0, 1 if is_active else 0, version
        ))
    else:
        cursor.execute("""
            INSERT INTO assessment_questions (
                domain, subcategory, question_text, options_json, scoring_weights_json, version
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (domain, subcategory, question_text, opts_json, weights_json, version))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


def _parse_val_and_bounds(q, raw_val):
    """
    Extracts numeric bounds from question options and applies reverse scoring
    and weighting dynamically based on question metadata.
    """
    options = q.get("options", [])
    numeric_opts = []
    for opt in options:
        v = opt.get("val")
        if v is not None and str(v).replace(".", "", 1).replace("-", "", 1).isdigit():
            numeric_opts.append(float(v))

    min_val = min(numeric_opts) if numeric_opts else 1.0
    max_val = max(numeric_opts) if numeric_opts else 5.0

    try:
        val_float = float(raw_val)
    except (ValueError, TypeError):
        val_float = (min_val + max_val) / 2.0

    # Apply reverse scoring if specified
    is_rev = q.get("is_reverse_scored", False) or q.get("scoring_direction") == "negative"
    if is_rev:
        v_adj = (max_val + min_val) - val_float
    else:
        v_adj = val_float

    weight = float(q.get("scoring_weight", 1.0))
    if weight <= 0:
        weight = 1.0

    return v_adj, weight, min_val, max_val


def _get_level_for_sub(domain, sub, score):
    """
    Helper providing consistent diagnostic levels for subcategories.
    """
    if score is None:
        return "Pending"
    if domain == "personality":
        return "High" if score >= 70.0 else ("Moderate" if score >= 45.0 else "Developing")
    elif domain == "critical_abilities":
        return "Exceptional" if score >= 85.0 else ("Strong" if score >= 75.0 else ("Proficient" if score >= 50.0 else "Needs Development"))
    else:
        return "Strong" if score >= 75.0 else ("Proficient" if score >= 50.0 else "Developing")


def evaluate_assessment_responses(student_id, domain, raw_responses):
    """
    Evaluates raw responses for any domain dynamically driven by question metadata.
    
    Supports:
    - Arbitrary question counts per domain / subcategory
    - Likert, multiple-choice, and categorical answer types
    - Question-specific weights (scoring_weight)
    - Forward and reverse scoring (is_reverse_scored / scoring_direction)
    - Dynamic scale range detection from question options
    
    Maintains:
    - source = "assessment-derived"
    - confidence = None
    - confidence_status = "not_statistically_calibrated"
    """
    questions = get_assessment_questions(domain, active_only=True)
    q_map = {q["id"]: q for q in questions}

    scores = {}
    details = {}

    if domain == "learning_style":
        counts = {"V": 0.0, "A": 0.0, "K": 0.0}
        total_weight = 0.0
        answered_q_ids = set()

        for q in questions:
            qid_str = str(q["id"])
            if qid_str in raw_responses or q["id"] in raw_responses:
                val = str(raw_responses.get(qid_str, raw_responses.get(q["id"]))).upper()
                w = float(q.get("scoring_weight", 1.0))
                if val in counts:
                    counts[val] += w
                    total_weight += w
                    answered_q_ids.add(q["id"])

        answered_count = len(answered_q_ids)
        total_questions = len(questions)

        if answered_count == 0 or total_weight == 0:
            scores = {"visual_pct": None, "auditory_pct": None, "kinesthetic_pct": None}
            details = {
                "dominant_style": "Profile Data Pending",
                "primary_learning_preference": "Profile Data Pending",
                "secondary_style": None,
                "visual_pct": None,
                "auditory_pct": None,
                "kinesthetic_pct": None,
                "is_pending": True,
                "is_partial": False,
                "answered_questions": 0,
                "total_questions": total_questions,
                "study_recommendations": "Complete the learning preference assessment to generate personalized multi-sensory study practices.",
                "scientific_disclaimer": "Self-reported study preference indicator; does not measure fixed cognitive learning capability.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }
        else:
            total = total_weight
            v_pct = round((counts["V"] / total) * 100.0, 1)
            a_pct = round((counts["A"] / total) * 100.0, 1)
            k_pct = round((counts["K"] / total) * 100.0, 1)

            scores = {"visual_pct": v_pct, "auditory_pct": a_pct, "kinesthetic_pct": k_pct}
            sorted_styles = sorted([("Visual", v_pct), ("Auditory", a_pct), ("Kinesthetic", k_pct)], key=lambda x: x[1], reverse=True)
            diff_top_two = round(sorted_styles[0][1] - sorted_styles[1][1], 1)

            if diff_top_two <= 5.0 and sorted_styles[0][1] > 0:
                dominant = "Balanced Multi-Sensory Preference"
                primary_label = "Balanced Multi-Sensory Preference"
            else:
                dominant = sorted_styles[0][0]
                primary_label = f"{sorted_styles[0][0]} Learning Preference"

            secondary = sorted_styles[1][0]

            study_recs = {
                "Visual": "Utilize mind-maps, diagrams, color-coded summaries, and structured visual organizers.",
                "Auditory": "Participate in study discussion groups, listen to educational podcasts, and explain concepts aloud.",
                "Kinesthetic": "Build hands-on prototypes, apply tactile case studies, and take active movement study breaks.",
                "Balanced Multi-Sensory Preference": "Integrate visual summaries, verbal peer discussions, and tactile project exercises flexibly across subjects."
            }

            details = {
                "dominant_style": dominant,
                "primary_learning_preference": primary_label,
                "secondary_style": secondary,
                "visual_pct": v_pct,
                "auditory_pct": a_pct,
                "kinesthetic_pct": k_pct,
                "is_balanced": diff_top_two <= 5.0,
                "is_pending": False,
                "is_partial": answered_count < total_questions,
                "answered_questions": answered_count,
                "total_questions": total_questions,
                "study_recommendations": study_recs.get(dominant, "Incorporate multi-sensory study practices flexibly."),
                "scientific_disclaimer": "Self-reported study preference indicator; does not measure fixed cognitive learning capability.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }

    elif domain in ["leadership_style", "leadership"]:
        task_count = 0.0
        rel_count = 0.0
        answered_q_ids = set()

        for q in questions:
            qid_str = str(q["id"])
            if qid_str in raw_responses or q["id"] in raw_responses:
                val = str(raw_responses.get(qid_str, raw_responses.get(q["id"]))).upper()
                w = float(q.get("scoring_weight", 1.0))
                if val == "T":
                    task_count += 1.0 * w
                    answered_q_ids.add(q["id"])
                elif val == "R":
                    rel_count += 1.0 * w
                    answered_q_ids.add(q["id"])
                elif val == "B":
                    task_count += 0.5 * w
                    rel_count += 0.5 * w
                    answered_q_ids.add(q["id"])

        answered_count = len(answered_q_ids)
        total_questions = len(questions)

        if answered_count == 0 or (task_count + rel_count) == 0:
            scores = {"task_oriented_pct": None, "relationship_oriented_pct": None}
            details = {
                "dominant_style": "Profile Data Pending",
                "leadership_orientation": "Profile Data Pending",
                "task_pct": None,
                "relationship_pct": None,
                "orientation_type": "Pending",
                "is_pending": True,
                "is_partial": False,
                "answered_questions": 0,
                "total_questions": total_questions,
                "characteristics": "Leadership preference responses pending completion.",
                "strengths": "Pending structured assessment responses.",
                "development_areas": "Pending structured assessment responses.",
                "scientific_note": "Exploratory leadership orientation indicator derived from structured questionnaire; not a validated leadership diagnosis.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }
        else:
            total = task_count + rel_count
            t_pct = round((task_count / total) * 100.0, 1)
            r_pct = round((rel_count / total) * 100.0, 1)

            scores = {"task_oriented_pct": t_pct, "relationship_oriented_pct": r_pct}
            if t_pct > r_pct:
                dominant = "Predominant Leadership Orientation (Task-Directed)"
                orientation_type = "Task-Directed"
            elif r_pct > t_pct:
                dominant = "Relational Leadership Orientation"
                orientation_type = "Relational"
            else:
                dominant = "Balanced Leadership Orientation"
                orientation_type = "Balanced"

            details = {
                "dominant_style": dominant,
                "leadership_orientation": dominant,
                "task_pct": t_pct,
                "relationship_pct": r_pct,
                "orientation_type": orientation_type,
                "is_pending": False,
                "is_partial": answered_count < total_questions,
                "answered_questions": answered_count,
                "total_questions": total_questions,
                "characteristics": "Goal-focused, systematic, and milestone-driven" if orientation_type == "Task-Directed" else ("Empathetic, consensus-seeking, and team-morale oriented" if orientation_type == "Relational" else "Integrates milestone discipline with interpersonal team empathy"),
                "strengths": "Punctual execution, rigorous quality control, structured direction" if orientation_type == "Task-Directed" else ("High team psychological safety, active conflict mediation, strong retention" if orientation_type == "Relational" else "Adaptive leadership balance between schedule control and team support"),
                "development_areas": "Incorporate active empathy and team pacing" if orientation_type == "Task-Directed" else ("Enforce tighter deadlines and objective performance thresholds" if orientation_type == "Relational" else "Maintain consistent delegation boundaries"),
                "scientific_note": "Exploratory leadership orientation indicator derived from structured questionnaire; not a validated leadership diagnosis.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }

    elif domain == "thinking_action":
        weighted_sum = 0.0
        total_weight = 0.0
        min_v, max_v = 1.0, 5.0
        answered_q_ids = set()

        for q in questions:
            qid_str = str(q["id"])
            if qid_str in raw_responses or q["id"] in raw_responses:
                val = raw_responses.get(qid_str, raw_responses.get(q["id"]))
                v_adj, w, q_min, q_max = _parse_val_and_bounds(q, val)
                weighted_sum += v_adj * w
                total_weight += w
                min_v, max_v = q_min, q_max
                answered_q_ids.add(q["id"])

        if not answered_q_ids or total_weight == 0:
            scores = {"thinking_pct": None, "action_pct": None}
            details = {
                "orientation": "Profile Data Pending",
                "thinking_action_preference": "Profile Data Pending",
                "thinking_pct": None,
                "action_pct": None,
                "is_pending": True,
                "scientific_note": "Self-reported execution preference indicator; not a cognitive archetype diagnosis.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }
        else:
            avg = weighted_sum / total_weight
            span = (max_v - min_v) or 1.0
            action_pct = round(((avg - min_v) / span) * 100.0, 1)
            thinking_pct = round(100.0 - action_pct, 1)

            scores = {"thinking_pct": thinking_pct, "action_pct": action_pct}
            if thinking_pct > 60:
                orientation = "Planning-Oriented Preference"
            elif action_pct > 60:
                orientation = "Action-Oriented Preference"
            else:
                orientation = "Balanced Preference"

            details = {
                "orientation": orientation,
                "thinking_action_preference": orientation,
                "thinking_pct": thinking_pct,
                "action_pct": action_pct,
                "is_pending": False,
                "scientific_note": "Self-reported execution preference indicator; not a cognitive archetype diagnosis.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }

    elif domain in ["team_player", "team_role"]:
        m_count = 0.0
        p_count = 0.0
        answered_q_ids = set()

        for q in questions:
            qid_str = str(q["id"])
            if qid_str in raw_responses or q["id"] in raw_responses:
                val = str(raw_responses.get(qid_str, raw_responses.get(q["id"]))).upper()
                w = float(q.get("scoring_weight", 1.0))
                if val == "M":
                    m_count += 1.0 * w
                    answered_q_ids.add(q["id"])
                elif val == "P":
                    p_count += 1.0 * w
                    answered_q_ids.add(q["id"])
                elif val == "B":
                    m_count += 0.5 * w
                    p_count += 0.5 * w
                    answered_q_ids.add(q["id"])
                else:
                    m_count += 0.5 * w
                    p_count += 0.5 * w
                    answered_q_ids.add(q["id"])

        if not answered_q_ids or (m_count + p_count) == 0:
            scores = {"team_management_pct": None, "team_player_pct": None}
            details = {
                "dominant_role": "Profile Data Pending",
                "preferred_collaboration_mode": "Profile Data Pending",
                "team_management_pct": None,
                "team_player_pct": None,
                "is_pending": True,
                "scientific_note": "Self-reported collaboration preference indicator; not a fixed managerial assessment.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }
        else:
            total = m_count + p_count
            mgr_pct = round((m_count / total) * 100.0, 1)
            player_pct = round((p_count / total) * 100.0, 1)

            scores = {"team_management_pct": mgr_pct, "team_player_pct": player_pct}
            if mgr_pct > player_pct:
                dominant_role = "Management-Oriented Preference"
            elif player_pct > mgr_pct:
                dominant_role = "Team Participation Preference"
            else:
                dominant_role = "Balanced Collaboration Preference"

            details = {
                "dominant_role": dominant_role,
                "preferred_collaboration_mode": dominant_role,
                "team_management_pct": mgr_pct,
                "team_player_pct": player_pct,
                "is_pending": False,
                "scientific_note": "Self-reported collaboration preference indicator; not a fixed managerial assessment.",
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }

    else:
        # Standard subcategory-driven domains: personality, critical_abilities, behavioral, emotional_social
        sub_questions = {}
        for q in questions:
            sub = q.get("subcategory") or "general"
            sub_questions.setdefault(sub, []).append(q)

        for sub, qlist in sub_questions.items():
            sub_weighted_sum = 0.0
            sub_weight_total = 0.0
            min_v, max_v = 1.0, 5.0
            sub_answered = False

            for q in qlist:
                qid_str = str(q["id"])
                if qid_str in raw_responses or q["id"] in raw_responses:
                    raw_val = raw_responses.get(qid_str, raw_responses.get(q["id"]))
                    v_adj, weight, q_min, q_max = _parse_val_and_bounds(q, raw_val)
                    sub_weighted_sum += v_adj * weight
                    sub_weight_total += weight
                    min_v, max_v = q_min, q_max
                    sub_answered = True

            if sub_answered and sub_weight_total > 0:
                avg = sub_weighted_sum / sub_weight_total
                span = (max_v - min_v) or 1.0
                norm_score = round(min(100.0, max(0.0, ((avg - min_v) / span) * 100.0)), 1)
                level_str = _get_level_for_sub(domain, sub, norm_score)
                is_sub_pending = False
            else:
                norm_score = None
                level_str = "Pending"
                is_sub_pending = True

            scores[sub] = norm_score
            details[sub] = {
                "score": norm_score,
                "level": level_str,
                "is_pending": is_sub_pending,
                "confidence": None,
                "confidence_status": "not_statistically_calibrated",
                "source": "assessment-derived"
            }

    # Persist in student_assessments
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO student_assessments (
            student_id, domain, version, completed_on, raw_responses_json, scores_json
        ) VALUES (?, ?, 'v1', ?, ?, ?)
    """, (
        student_id, domain, now_str,
        json.dumps(raw_responses), json.dumps({"scores": scores, "details": details})
    ))

    # Also record into prediction_results for source provenance (skip unassessed/nulls)
    for key, val in scores.items():
        if val is None:
            continue
        item_detail = details.get(key)
        if isinstance(item_detail, dict):
            label_val = str(item_detail.get("level", ""))
        else:
            label_val = str(details.get("dominant_style") or details.get("orientation") or details.get("dominant_role") or "")

        cursor.execute("""
            INSERT INTO prediction_results (
                student_id, category, sub_category, score, label, confidence, source, model_version, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, 'assessment-derived', 'rule-based-eval-v1', ?)
        """, (
            student_id, domain, key, val, label_val, None, now_str
        ))

    conn.commit()
    conn.close()

    if domain in ["learning_style", "leadership_style", "leadership", "thinking_action", "team_player", "team_role"]:
        all_pending = details.get("is_pending", False)
    else:
        all_pending = all(d.get("is_pending", False) for d in details.values()) if details else True

    return {
        "student_id": student_id,
        "domain": domain,
        "scores": scores,
        "details": details,
        "is_pending": all_pending,
        "confidence": None,
        "confidence_status": "not_statistically_calibrated",
        "completed_on": now_str,
        "source": "assessment-derived"
    }


def get_student_assessment_history(student_id):
    """
    Returns all completed assessments for a student.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT domain, version, completed_on, scores_json
        FROM student_assessments
        WHERE student_id = ?
        ORDER BY id DESC
    """, (student_id,))

    rows = cursor.fetchall()
    conn.close()

    history = {}
    for r in rows:
        domain = r[0]
        if domain not in history:
            history[domain] = {
                "domain": domain,
                "version": r[1],
                "completed_on": r[2],
                "results": json.loads(r[3]) if r[3] else {}
            }
    return history

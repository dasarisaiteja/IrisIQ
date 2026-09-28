import json
from database_student import get_connection
from database import get_user, get_embeddings


def fuse_student_features(student_id):
    """
    Fuses multi-source profile data into an integrated feature structure.
    Strictly tags every component with its authoritative source:
      - iris-derived
      - assessment-derived
      - academic-derived
      - profile-derived
      - rule-based
      - ML-derived
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Base Student Profile
    cursor.execute("""
        SELECT student_id, employee_code, full_name, age, gender, email, mobile,
               school_college, course, year, stream, location, photo_path, created_on
        FROM student_profiles
        WHERE student_id = ?
    """, (student_id,))
    prof_row = cursor.fetchone()

    if not prof_row:
        conn.close()
        return None

    student = {
        "student_id": prof_row[0],
        "employee_code": prof_row[1],
        "full_name": prof_row[2],
        "age": prof_row[3],
        "gender": prof_row[4],
        "email": prof_row[5],
        "mobile": prof_row[6],
        "school_college": prof_row[7],
        "course": prof_row[8],
        "year": prof_row[9],
        "stream": prof_row[10],
        "location": prof_row[11],
        "photo_path": prof_row[12],
        "created_on": prof_row[13],
        "source": "profile-derived"
    }

    # 2. Academic Records
    cursor.execute("""
        SELECT subject_name, marks_obtained, max_marks, grade, term
        FROM academic_records
        WHERE student_id = ?
    """, (student_id,))
    acad_rows = cursor.fetchall()

    academics = []
    subject_marks = {}
    for r in acad_rows:
        pct = round((r[1] / max(1.0, r[2])) * 100.0, 1)
        academics.append({
            "subject": r[0],
            "marks": r[1],
            "max_marks": r[2],
            "percentage": pct,
            "grade": r[3],
            "term": r[4],
            "source": "academic-derived"
        })
        subject_marks[r[0].lower()] = pct

    # 3. Skills
    cursor.execute("""
        SELECT skill_name, skill_type, proficiency_score
        FROM student_skills
        WHERE student_id = ?
    """, (student_id,))
    skill_rows = cursor.fetchall()
    skills = []
    for r in skill_rows:
        skills.append({
            "skill": r[0],
            "type": r[1] or "technical",
            "proficiency": r[2],
            "source": "profile-derived"
        })

    # 4. Interests
    cursor.execute("""
        SELECT category, interest_name, level
        FROM student_interests
        WHERE student_id = ?
    """, (student_id,))
    interest_rows = cursor.fetchall()
    interests = []
    for r in interest_rows:
        interests.append({
            "category": r[0],
            "interest": r[1],
            "level": r[2] or "High",
            "source": "profile-derived"
        })

    # 5. Activities
    cursor.execute("""
        SELECT title, activity_type, description, year
        FROM student_activities
        WHERE student_id = ?
    """, (student_id,))
    activity_rows = cursor.fetchall()
    activities = []
    for r in activity_rows:
        activities.append({
            "title": r[0],
            "type": r[1],
            "description": r[2],
            "year": r[3],
            "source": "profile-derived"
        })

    # 6. Assessments
    cursor.execute("""
        SELECT domain, version, completed_on, scores_json
        FROM student_assessments
        WHERE student_id = ?
        ORDER BY id DESC
    """, (student_id,))
    assessment_rows = cursor.fetchall()
    assessments = {}
    for r in assessment_rows:
        dom = r[0]
        if dom not in assessments:
            assessments[dom] = {
                "version": r[1],
                "completed_on": r[2],
                "data": json.loads(r[3]) if r[3] else {},
                "source": "assessment-derived"
            }

    # 7. Iris-Derived Biometric Link
    iris_data = None
    if student["employee_code"]:
        # Check if matching user exists in iris_users
        cursor.execute("""
            SELECT employee_code, photo_path, embedding_count, created_on
            FROM iris_users
            WHERE employee_code = ?
        """, (student["employee_code"],))
        user_row = cursor.fetchone()
        if user_row:
            # Check for latest scan in scan_history
            cursor.execute("""
                SELECT report_id, similarity, confidence, status, scan_date, scan_time, eye, image_path
                FROM scan_history
                WHERE LOWER(TRIM(user_name)) = LOWER(TRIM(?)) OR report_id LIKE ?
                ORDER BY id DESC LIMIT 1
            """, (student["full_name"], f"%{student['employee_code']}%"))
            scan_row = cursor.fetchone()

            iris_data = {
                "is_enrolled": True,
                "employee_code": user_row[0],
                "enrolled_photo": user_row[1],
                "embedding_count": user_row[2],
                "source": "iris-derived",
                "notes": "Verified against enrolled biometric database. Used for identity verification and biometric quality analysis only."
            }
            if scan_row:
                iris_data["latest_scan"] = {
                    "report_id": scan_row[0],
                    "similarity": scan_row[1],
                    "confidence": scan_row[2],
                    "status": scan_row[3],
                    "date": scan_row[4],
                    "time": scan_row[5],
                    "eye": scan_row[6],
                    "source": "iris-derived"
                }

    conn.close()

    fused_payload = {
        "student": student,
        "academics": academics,
        "subject_marks": subject_marks,
        "skills": skills,
        "interests": interests,
        "activities": activities,
        "assessments": assessments,
        "iris_biometrics": iris_data,
        "fusion_metadata": {
            "version": "1.0",
            "source_provenance_enforced": True
        }
    }

    return fused_payload

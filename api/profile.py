from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from database_student import get_connection
from services.assessment_engine import get_assessment_questions, evaluate_assessment_responses, get_student_assessment_history
from services.feature_fusion import fuse_student_features
from services.cognitive_engine import compute_cognitive_profile
from services.subject_analysis import analyze_critical_subjects
from services.kpi_engine import compute_kpis
from services.stream_engine import recommend_streams
from services.career_engine import recommend_careers
from services.activity_sports import recommend_activities_and_sports
from services.gap_analysis import compute_development_gaps
from services.report_v2_generator import generate_v2_report_data

from security.auth import (
    require_authenticated,
    require_counselor_or_admin,
    require_admin,
    get_current_user,
    check_student_access,
)

router = APIRouter(
    prefix="/api/profile",
    tags=["Student Profile & Intelligence"],
    dependencies=[Depends(require_authenticated)]
)


# Pydantic Schemas
class StudentCreateSchema(BaseModel):
    student_id: Optional[str] = None
    employee_code: Optional[str] = None
    full_name: str
    age: Optional[int] = None
    gender: Optional[str] = "Not Specified"
    email: Optional[str] = ""
    mobile: Optional[str] = ""
    school_college: Optional[str] = ""
    course: Optional[str] = ""
    year: Optional[str] = None
    stream: Optional[str] = None
    location: Optional[str] = ""
    photo_path: Optional[str] = ""


class AcademicRecordSchema(BaseModel):
    subject_name: str
    marks_obtained: float
    max_marks: float = 100.0
    grade: Optional[str] = ""
    term: Optional[str] = "Current"


class StudentActivitySchema(BaseModel):
    title: str
    activity_type: Optional[str] = "Co-Curricular"
    description: Optional[str] = ""
    year: Optional[str] = ""


class AssessmentSubmissionSchema(BaseModel):
    student_id: str
    domain: str
    responses: Dict[str, Any]


# ---------------- Student CRUD ----------------

@router.post("/students", dependencies=[Depends(require_counselor_or_admin)])
def create_or_update_student(student: StudentCreateSchema):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sid = student.student_id or f"STU-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    cursor.execute("""
        INSERT INTO student_profiles (
            student_id, employee_code, full_name, age, gender, email, mobile,
            school_college, course, year, stream, location, photo_path, created_on, updated_on
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            employee_code = excluded.employee_code,
            full_name = excluded.full_name,
            age = excluded.age,
            gender = excluded.gender,
            email = excluded.email,
            mobile = excluded.mobile,
            school_college = excluded.school_college,
            course = excluded.course,
            year = excluded.year,
            stream = excluded.stream,
            location = excluded.location,
            photo_path = CASE WHEN excluded.photo_path != '' THEN excluded.photo_path ELSE student_profiles.photo_path END,
            updated_on = excluded.updated_on
    """, (
        sid, student.employee_code, student.full_name, student.age, student.gender,
        student.email, student.mobile, student.school_college, student.course,
        student.year, student.stream, student.location, student.photo_path, now_str, now_str
    ))

    conn.commit()
    conn.close()

    return {"status": True, "message": "Student profile saved successfully", "student_id": sid}


@router.get("/students")
def list_students(current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT student_id, employee_code, full_name, age, gender, email, mobile,
               school_college, course, year, stream, location, photo_path, created_on
        FROM student_profiles
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    students = []
    for r in rows:
        students.append({
            "student_id": r[0],
            "employee_code": r[1],
            "full_name": r[2],
            "age": r[3],
            "gender": r[4],
            "email": r[5],
            "mobile": r[6],
            "school_college": r[7],
            "course": r[8],
            "year": r[9],
            "stream": r[10],
            "location": r[11],
            "photo_path": r[12],
            "created_on": r[13]
        })

    if isinstance(current_user, dict) and current_user.get("role") == "Student":
        username = current_user.get("username", "")
        token_sid = current_user.get("claims", {}).get("student_id") or username
        students = [
            s for s in students
            if s["student_id"].lower() in (username.lower(), token_sid.lower())
            or (username.lower() == "student1" and s["student_id"].upper() == "STU-001")
        ]

    return {"status": True, "total": len(students), "students": students}


@router.get("/{student_id}")
def get_student_profile(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": True, "profile": fused}


@router.delete("/{student_id}", dependencies=[Depends(require_admin)])
def delete_student_profile(student_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM student_profiles WHERE student_id = ?", (student_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found")

    # Application-level cascade delete for child records
    cursor.execute("DELETE FROM academic_records WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM student_skills WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM student_interests WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM student_activities WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM student_assessments WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM prediction_results WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM report_versions WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM student_profiles WHERE student_id = ?", (student_id,))

    conn.commit()
    conn.close()
    return {"status": True, "message": f"Student {student_id} and associated records successfully deleted"}


# ---------------- Academics, Skills, Interests & Activities ----------------

@router.post("/{student_id}/academics")
def add_academic_records(student_id: str, records: List[AcademicRecordSchema], current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    for r in records:
        term_val = r.term or "Current"
        cursor.execute("""
            SELECT id FROM academic_records
            WHERE student_id = ? AND LOWER(TRIM(subject_name)) = LOWER(TRIM(?)) AND term = ?
            ORDER BY id DESC LIMIT 1
        """, (student_id, r.subject_name, term_val))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE academic_records
                SET marks_obtained = ?, max_marks = ?, grade = ?, created_on = ?
                WHERE id = ?
            """, (r.marks_obtained, r.max_marks, r.grade, now_str, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO academic_records (student_id, subject_name, marks_obtained, max_marks, grade, term, created_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, r.subject_name, r.marks_obtained, r.max_marks, r.grade, term_val, now_str))
        saved_count += 1

    conn.commit()
    conn.close()
    return {"status": True, "message": f"Saved {saved_count} academic record(s)"}


@router.post("/{student_id}/skills")
def add_skills(student_id: str, skills: List[Dict[str, Any]], current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    for s in skills:
        s_name = s.get("name") or s.get("skill") or ""
        s_type = s.get("type") or "technical"
        s_prof = float(s.get("proficiency", 70.0))
        if not s_name:
            continue

        cursor.execute("""
            SELECT id FROM student_skills
            WHERE student_id = ? AND LOWER(TRIM(skill_name)) = LOWER(TRIM(?))
            ORDER BY id DESC LIMIT 1
        """, (student_id, s_name))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE student_skills
                SET skill_type = ?, proficiency_score = ?, created_on = ?
                WHERE id = ?
            """, (s_type, s_prof, now_str, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO student_skills (student_id, skill_name, skill_type, proficiency_score, created_on)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, s_name, s_type, s_prof, now_str))
        saved_count += 1

    conn.commit()
    conn.close()
    return {"status": True, "message": f"Saved {saved_count} skill(s)"}


@router.post("/{student_id}/interests")
def add_interests(student_id: str, interests: List[Dict[str, Any]], current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    for i in interests:
        i_name = i.get("name") or i.get("interest") or ""
        i_cat = i.get("category", "General")
        i_level = i.get("level", "High")
        if not i_name:
            continue

        cursor.execute("""
            SELECT id FROM student_interests
            WHERE student_id = ? AND LOWER(TRIM(interest_name)) = LOWER(TRIM(?))
            ORDER BY id DESC LIMIT 1
        """, (student_id, i_name))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE student_interests
                SET category = ?, level = ?, created_on = ?
                WHERE id = ?
            """, (i_cat, i_level, now_str, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO student_interests (student_id, category, interest_name, level, created_on)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, i_cat, i_name, i_level, now_str))
        saved_count += 1

    conn.commit()
    conn.close()
    return {"status": True, "message": f"Saved {saved_count} interest(s)"}


@router.post("/{student_id}/activities")
def add_activities(student_id: str, activities: List[Dict[str, Any]], current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    saved_count = 0
    for a in activities:
        a_title = a.get("title", "")
        a_type = a.get("activity_type") or a.get("type", "Co-Curricular")
        a_desc = a.get("description", "")
        a_year = a.get("year", "")
        if not a_title:
            continue

        cursor.execute("""
            SELECT id FROM student_activities
            WHERE student_id = ? AND LOWER(TRIM(title)) = LOWER(TRIM(?))
            ORDER BY id DESC LIMIT 1
        """, (student_id, a_title))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE student_activities
                SET activity_type = ?, description = ?, year = ?, created_on = ?
                WHERE id = ?
            """, (a_type, a_desc, a_year, now_str, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO student_activities (student_id, title, activity_type, description, year, created_on)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, a_title, a_type, a_desc, a_year, now_str))
        saved_count += 1

    conn.commit()
    conn.close()
    return {"status": True, "message": f"Saved {saved_count} activity/activities"}


# ---------------- Assessments ----------------

@router.get("/questions/all")
def get_all_questions(domain: Optional[str] = Query(None), active_only: bool = Query(True)):
    return {"status": True, "questions": get_assessment_questions(domain, active_only=active_only)}


@router.post("/assessment")
def submit_assessment(payload: AssessmentSubmissionSchema, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, payload.student_id)
    result = evaluate_assessment_responses(payload.student_id, payload.domain, payload.responses)
    return {"status": True, "result": result}


@router.get("/{student_id}/assessments")
def get_student_assessments(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    history = get_student_assessment_history(student_id)
    return {"status": True, "history": history}


# ---------------- Holistic Analysis & Profiles ----------------

@router.post("/{student_id}/analyze")
def analyze_student(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")

    cognitive = compute_cognitive_profile(fused)
    subjects = analyze_critical_subjects(fused)
    kpis = compute_kpis(fused)
    streams = recommend_streams(fused)
    careers = recommend_careers(fused)
    act_sports = recommend_activities_and_sports(fused)
    gaps = compute_development_gaps(fused)

    return {
        "status": True,
        "student_id": student_id,
        "cognitive": cognitive,
        "subjects": subjects,
        "kpis": kpis,
        "streams": streams,
        "careers": careers,
        "activities_and_sports": act_sports,
        "gaps": gaps
    }


@router.get("/{student_id}/personality")
def get_personality(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    pers = fused.get("assessments", {}).get("personality", {}).get("data", {})
    return {"status": True, "personality": pers, "source": "assessment-derived"}


@router.get("/{student_id}/cognitive")
def get_cognitive(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": True, "cognitive": compute_cognitive_profile(fused)}


@router.get("/{student_id}/learning-style")
def get_learning_style(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    vak = fused.get("assessments", {}).get("learning_style", {}).get("data", {})
    return {"status": True, "learning_style": vak, "source": "assessment-derived"}


@router.get("/{student_id}/leadership")
def get_leadership(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    lead = fused.get("assessments", {}).get("leadership_style", {}).get("data", {})
    return {"status": True, "leadership_style": lead, "source": "assessment-derived"}


@router.get("/{student_id}/subjects")
def get_subjects(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": True, "subjects": analyze_critical_subjects(fused)}


@router.get("/{student_id}/streams")
def get_streams(
    student_id: str,
    academic_weight: Optional[float] = Query(None),
    assessment_weight: Optional[float] = Query(None),
    interest_weight: Optional[float] = Query(None),
    skill_weight: Optional[float] = Query(None),
    activity_weight: Optional[float] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")

    custom_w = None
    w_inputs = {
        "academic_weight": academic_weight,
        "assessment_weight": assessment_weight,
        "interest_weight": interest_weight,
        "skill_weight": skill_weight,
        "activity_weight": activity_weight
    }
    filtered_w = {k: v for k, v in w_inputs.items() if v is not None}
    if filtered_w:
        custom_w = filtered_w

    return {"status": True, "streams": recommend_streams(fused, custom_weights=custom_w)}


@router.get("/{student_id}/careers")
def get_careers(
    student_id: str,
    academic_weight: Optional[float] = Query(None),
    skill_weight: Optional[float] = Query(None),
    assessment_weight: Optional[float] = Query(None),
    interest_weight: Optional[float] = Query(None),
    activity_weight: Optional[float] = Query(None),
    stream_eligibility_weight: Optional[float] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")

    custom_w = None
    w_inputs = {
        "academic_weight": academic_weight,
        "skill_weight": skill_weight,
        "assessment_weight": assessment_weight,
        "interest_weight": interest_weight,
        "activity_weight": activity_weight,
        "stream_eligibility_weight": stream_eligibility_weight
    }
    filtered_w = {k: v for k, v in w_inputs.items() if v is not None}
    if filtered_w:
        custom_w = filtered_w

    return {"status": True, "careers": recommend_careers(fused, custom_weights=custom_w)}


@router.get("/{student_id}/activities")
def get_activities(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"status": True, "activities": recommend_activities_and_sports(fused)}


@router.get("/{student_id}/recommendations")
def get_all_recommendations(student_id: str, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    fused = fuse_student_features(student_id)
    if not fused:
        raise HTTPException(status_code=404, detail="Student not found")
    return {
        "status": True,
        "streams": recommend_streams(fused),
        "careers": recommend_careers(fused),
        "activities_and_sports": recommend_activities_and_sports(fused),
        "development_gaps": compute_development_gaps(fused)
    }


# ---------------- Report V2 Endpoints ----------------

@router.post("/{student_id}/report")
def create_v2_report(student_id: str, report_id: Optional[str] = None, current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    report_data = generate_v2_report_data(student_id, report_id=report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return report_data


@router.get("/{student_id}/report")
def get_v2_report(student_id: str, report_id: Optional[str] = Query(None), current_user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    check_student_access(current_user, student_id)
    conn = get_connection()
    cursor = conn.cursor()

    if report_id:
        cursor.execute("""
            SELECT payload_json FROM report_versions
            WHERE report_id = ? AND version_type = 'V2'
        """, (report_id,))
    else:
        cursor.execute("""
            SELECT payload_json FROM report_versions
            WHERE student_id = ? AND version_type = 'V2'
            ORDER BY id DESC LIMIT 1
        """, (student_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])

    # If no report generated yet, generate one on the fly
    report_data = generate_v2_report_data(student_id, report_id=report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Student not found")
    return report_data

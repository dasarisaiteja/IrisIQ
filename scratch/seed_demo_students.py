import sqlite3
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "iris_database.db")

def seed():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Check if STU-001 exists
    cur.execute("SELECT id FROM student_profiles WHERE student_id = 'STU-001'")
    if not cur.fetchone():
        # Insert STU-001 linked to emp004
        cur.execute("""
            INSERT INTO student_profiles (
                student_id, employee_code, full_name, age, gender, email, mobile,
                school_college, course, year, stream, location, photo_path, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "STU-001", "emp004", "Dhanashri Varpe", 25, "Female", "dhanashrisatpute163@gmail.com",
            "+91 9876543210", "Institute of Technology & Science", "B.Tech Computer Science",
            "Final Year", "Science", "Pune, Maharashtra", "static/photos/emp004/20260807184818.jpg",
            now, now
        ))

        # Add Academics
        academics = [
            ("STU-001", "Mathematics", 88.0, 100.0, "A+", "Semester 7"),
            ("STU-001", "Physics & Electronics", 84.0, 100.0, "A", "Semester 7"),
            ("STU-001", "Computer Science & AI", 92.0, 100.0, "O", "Semester 7"),
            ("STU-001", "Technical English & Communication", 82.0, 100.0, "A", "Semester 7"),
            ("STU-001", "Data Structures & Algorithms", 90.0, 100.0, "O", "Semester 7")
        ]
        cur.executemany("""
            INSERT INTO academic_records (student_id, subject_name, marks_obtained, max_marks, grade, term, created_on)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, academics)

        # Add Skills
        skills = [
            ("STU-001", "Python", "technical", 85.0),
            ("STU-001", "Web Design & UI/UX", "technical", 90.0),
            ("STU-001", "Machine Learning Fundamentals", "technical", 75.0),
            ("STU-001", "Analytical Problem Solving", "problem_solving", 88.0),
            ("STU-001", "Team Collaboration", "soft", 85.0)
        ]
        cur.executemany("""
            INSERT INTO student_skills (student_id, skill_name, skill_type, proficiency_score, created_on)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, skills)

        # Add Interests
        interests = [
            ("STU-001", "technical", "Artificial Intelligence", "High"),
            ("STU-001", "creative", "Digital Product Design", "High"),
            ("STU-001", "sports", "Badminton", "Moderate"),
            ("STU-001", "hobbies", "Photography", "High")
        ]
        cur.executemany("""
            INSERT INTO student_interests (student_id, category, interest_name, level, created_on)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, interests)

        # Add Activities
        activities = [
            ("STU-001", "National Web Design Hackathon", "projects", "Won 2nd Runner Up for Accessible UI Design", "2025"),
            ("STU-001", "College Technical Symposium", "leadership", "Coordinated volunteer logistics and student coding challenge", "2026")
        ]
        cur.executemany("""
            INSERT INTO student_activities (student_id, title, activity_type, description, year, created_on)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, activities)

        # Complete Personality Assessment
        pers_scores = {"openness": 82.0, "conscientiousness": 80.0, "extraversion": 72.0, "agreeableness": 84.0, "emotional_stability": 78.0}
        pers_details = {
            "openness": {"score": 82.0, "level": "High", "source": "assessment-derived"},
            "conscientiousness": {"score": 80.0, "level": "High", "source": "assessment-derived"},
            "extraversion": {"score": 72.0, "level": "Moderate", "source": "assessment-derived"},
            "agreeableness": {"score": 84.0, "level": "High", "source": "assessment-derived"},
            "emotional_stability": {"score": 78.0, "level": "High", "source": "assessment-derived"}
        }
        cur.execute("""
            INSERT INTO student_assessments (student_id, domain, version, completed_on, raw_responses_json, scores_json)
            VALUES ('STU-001', 'personality', 'v1', ?, '{}', ?)
        """, (now, json.dumps({"scores": pers_scores, "details": pers_details})))

        # Complete Critical Abilities Assessment
        crit_scores = {"problem_solving": 86.0, "creative_ability": 84.0, "pressure_handling": 80.0, "emotion_management": 82.0, "logical_reasoning": 88.0}
        crit_details = {k: {"score": v, "level": "Strong", "confidence": None, "confidence_status": "not_statistically_calibrated", "source": "assessment-derived"} for k, v in crit_scores.items()}
        cur.execute("""
            INSERT INTO student_assessments (student_id, domain, version, completed_on, raw_responses_json, scores_json)
            VALUES ('STU-001', 'critical_abilities', 'v1', ?, '{}', ?)
        """, (now, json.dumps({"scores": crit_scores, "details": crit_details})))

        # Complete VAK Assessment
        vak_scores = {"visual_pct": 55.0, "auditory_pct": 25.0, "kinesthetic_pct": 20.0}
        vak_details = {
            "dominant_style": "Visual", "secondary_style": "Auditory",
            "visual_pct": 55.0, "auditory_pct": 25.0, "kinesthetic_pct": 20.0,
            "study_recommendations": "Utilize mind-maps, diagrams, color-coded summaries, and structured visual organizers."
        }
        cur.execute("""
            INSERT INTO student_assessments (student_id, domain, version, completed_on, raw_responses_json, scores_json)
            VALUES ('STU-001', 'learning_style', 'v1', ?, '{}', ?)
        """, (now, json.dumps({"scores": vak_scores, "details": vak_details})))

        # Complete Leadership Assessment
        lead_scores = {"task_oriented_pct": 62.0, "relationship_oriented_pct": 38.0}
        lead_details = {
            "dominant_style": "Task Oriented", "task_pct": 62.0, "relationship_pct": 38.0,
            "characteristics": "Goal-focused, systematic, and milestone-driven",
            "strengths": "Punctual execution, rigorous quality control, structured direction",
            "development_areas": "Incorporate active empathy and team pacing"
        }
        cur.execute("""
            INSERT INTO student_assessments (student_id, domain, version, completed_on, raw_responses_json, scores_json)
            VALUES ('STU-001', 'leadership_style', 'v1', ?, '{}', ?)
        """, (now, json.dumps({"scores": lead_scores, "details": lead_details})))

    # 2. Check if STU-002 (Standalone student) exists
    cur.execute("SELECT id FROM student_profiles WHERE student_id = 'STU-002'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO student_profiles (
                student_id, employee_code, full_name, age, gender, email, mobile,
                school_college, course, year, stream, location, photo_path, created_on, updated_on
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "STU-002", "Aryan Sharma", 18, "Male", "aryan.sharma@example.com",
            "+91 9123456780", "Delhi Public School", "Higher Secondary", "12th Grade",
            "Science", "New Delhi", "", now, now
        ))

        academics_2 = [
            ("STU-002", "Mathematics", 82.0, 100.0, "A", "Midterm"),
            ("STU-002", "Physics", 80.0, 100.0, "A", "Midterm"),
            ("STU-002", "Chemistry", 76.0, 100.0, "B+", "Midterm"),
            ("STU-002", "Computer Science", 88.0, 100.0, "A+", "Midterm"),
            ("STU-002", "English", 78.0, 100.0, "A", "Midterm")
        ]
        cur.executemany("""
            INSERT INTO academic_records (student_id, subject_name, marks_obtained, max_marks, grade, term, created_on)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, academics_2)

    conn.commit()
    conn.close()
    print("Seed students populated successfully.")

if __name__ == "__main__":
    seed()

"""
Phase 1 Database Foundation Verification Test Suite.
Validates all 17 acceptance criteria required by the official requirements:
1. Database backup exists.
2. Required tables exist.
3. Required columns exist.
4. Roles are valid.
5. Student ID uniqueness.
6. Assessment ID uniqueness.
7. Assessment -> Student relationship.
8. Eye scan -> Assessment relationship.
9. LEFT/RIGHT eye constraints.
10. Report -> Assessment relationship.
11. Counsellor assignment relationships.
12. Foreign key integrity.
13. Required indexes.
14. Invalid assessment state rejected.
15. Invalid eye side rejected.
16. Existing historical records preserved.
17. Existing Iris tables/data unchanged.
"""

import os
import sys
import sqlite3
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database_official import (
    get_connection,
    init_official_tables,
    OFFICIAL_ASSESSMENT_STATES,
    OFFICIAL_EYE_SIDES,
)


def run_tests():
    print("=" * 70)
    print("STARTING PHASE 1 DATABASE FOUNDATION VERIFICATION TEST SUITE")
    print("=" * 70)

    # 1. Database backup exists
    backup_path = os.path.join(BASE_DIR, "iris_database.db.backup_pre_phase1_20260929")
    backup_scratch = os.path.join(BASE_DIR, "scratch", "backups", "iris_database_pre_phase1.db")
    assert os.path.exists(backup_path) and os.path.getsize(backup_path) > 1000000, "Backup file missing or too small!"
    assert os.path.exists(backup_scratch) and os.path.getsize(backup_scratch) > 1000000, "Scratch backup file missing!"
    print("✅ 1. Database backup verified at both target locations.")

    conn = get_connection()
    cursor = conn.cursor()

    # 2. Required tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = set(r[0] for r in cursor.fetchall())
    required_tables = [
        "roles",
        "students",
        "assessments",
        "eye_scans",
        "analysis_results",
        "reports",
        "report_sections",
        "counsellor_assignments",
        "counselling_notes",
        "follow_ups",
        "audit_logs",
        "processing_logs",
    ]
    for tbl in required_tables:
        assert tbl in existing_tables, f"Required table '{tbl}' is missing from database!"
    print(f"✅ 2. All {len(required_tables)} official required tables exist.")

    # 3. Required columns exist
    def get_columns(table_name):
        cursor.execute(f"PRAGMA table_info({table_name});")
        return {r[1]: r[2] for r in cursor.fetchall()}

    # students columns
    stu_cols = get_columns("students")
    for col in ["student_id", "student_name", "created_by", "created_at"]:
        assert col in stu_cols, f"Column '{col}' missing from students table!"

    # assessments columns
    asm_cols = get_columns("assessments")
    for col in ["assessment_id", "student_id", "status", "created_by", "created_at", "updated_at"]:
        assert col in asm_cols, f"Column '{col}' missing from assessments table!"

    # eye_scans columns
    scan_cols = get_columns("eye_scans")
    for col in ["scan_id", "assessment_id", "eye_side", "file_reference", "status", "error_code", "created_at"]:
        assert col in scan_cols, f"Column '{col}' missing from eye_scans table!"

    # reports columns
    rep_cols = get_columns("reports")
    for col in ["report_id", "assessment_id", "version", "status", "pdf_reference", "created_at"]:
        assert col in rep_cols, f"Column '{col}' missing from reports table!"

    # counsellor_assignments columns
    ca_cols = get_columns("counsellor_assignments")
    for col in ["assignment_id", "assessment_id", "student_id", "counsellor_id", "assigned_by", "assigned_at", "status"]:
        assert col in ca_cols, f"Column '{col}' missing from counsellor_assignments table!"

    # counselling_notes columns
    cn_cols = get_columns("counselling_notes")
    for col in ["note_id", "assessment_id", "counsellor_id", "note", "created_at"]:
        assert col in cn_cols, f"Column '{col}' missing from counselling_notes table!"

    # follow_ups columns
    fu_cols = get_columns("follow_ups")
    for col in ["follow_up_id", "assessment_id", "counsellor_id", "follow_up_date", "status", "notes"]:
        assert col in fu_cols, f"Column '{col}' missing from follow_ups table!"

    # audit_logs columns
    al_cols = get_columns("audit_logs")
    for col in ["audit_id", "user_id", "role", "action", "timestamp"]:
        assert col in al_cols, f"Column '{col}' missing from audit_logs table!"

    # processing_logs columns
    pl_cols = get_columns("processing_logs")
    for col in ["processing_id", "assessment_id", "operation", "status", "started_at"]:
        assert col in pl_cols, f"Column '{col}' missing from processing_logs table!"

    print("✅ 3. Required columns verified across all official tables.")

    # 4. Roles are valid
    cursor.execute("SELECT role_name FROM roles ORDER BY role_name;")
    roles = [r[0] for r in cursor.fetchall()]
    assert "Admin" in roles and "Student" in roles and "Counsellor" in roles, f"Roles incomplete: {roles}"
    print(f"✅ 4. Official roles validated: {roles}")

    # 5. Student ID uniqueness
    test_stu_id = f"TEST-STU-{uuid.uuid4().hex[:6].upper()}"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO students (student_id, student_name, created_by, created_at)
    VALUES (?, ?, ?, ?);
    """, (test_stu_id, "Test Student 1", "test_runner", now_str))
    conn.commit()

    duplicate_caught = False
    try:
        cursor.execute("""
        INSERT INTO students (student_id, student_name, created_by, created_at)
        VALUES (?, ?, ?, ?);
        """, (test_stu_id, "Duplicate Student", "test_runner", now_str))
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_caught = True
        conn.rollback()

    assert duplicate_caught, "Failed to enforce student_id uniqueness!"
    print("✅ 5. Student ID uniqueness constraint enforced.")

    # 6. Assessment ID uniqueness
    test_asm_id = f"TEST-ASM-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
    VALUES (?, ?, 'REGISTERED', 'test_runner', ?);
    """, (test_asm_id, test_stu_id, now_str))
    conn.commit()

    duplicate_asm_caught = False
    try:
        cursor.execute("""
        INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
        VALUES (?, ?, 'REGISTERED', 'test_runner', ?);
        """, (test_asm_id, test_stu_id, now_str))
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_asm_caught = True
        conn.rollback()

    assert duplicate_asm_caught, "Failed to enforce assessment_id uniqueness!"
    print("✅ 6. Assessment ID uniqueness constraint enforced.")

    # 7. Assessment -> Student relationship
    test_asm_id2 = f"TEST-ASM-MULTI-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
    VALUES (?, ?, 'SCAN_PENDING', 'test_runner', ?);
    """, (test_asm_id2, test_stu_id, now_str))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM assessments WHERE student_id = ?;", (test_stu_id,))
    assert cursor.fetchone()[0] == 2, "Student should support multiple assessments over time!"
    print("✅ 7. Student 1 -> Many Assessments relationship verified.")

    # 8. Eye scan -> Assessment relationship
    scan_left_id = f"SCAN-L-{uuid.uuid4().hex[:6].upper()}"
    scan_right_id = f"SCAN-R-{uuid.uuid4().hex[:6].upper()}"

    cursor.execute("""
    INSERT INTO eye_scans (scan_id, assessment_id, eye_side, file_reference, status, created_at)
    VALUES (?, ?, 'LEFT', 'secure://uploads/test_left.jpg', 'Completed', ?);
    """, (scan_left_id, test_asm_id, now_str))

    cursor.execute("""
    INSERT INTO eye_scans (scan_id, assessment_id, eye_side, file_reference, status, created_at)
    VALUES (?, ?, 'RIGHT', 'secure://uploads/test_right.jpg', 'Completed', ?);
    """, (scan_right_id, test_asm_id, now_str))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM eye_scans WHERE assessment_id = ?;", (test_asm_id,))
    assert cursor.fetchone()[0] == 2, "Assessment should contain exactly both scans!"
    print("✅ 8. Eye Scans -> Assessment relationship verified.")

    # 9. LEFT/RIGHT eye constraints & duplicate active scan prevention
    duplicate_active_scan_caught = False
    try:
        cursor.execute("""
        INSERT INTO eye_scans (scan_id, assessment_id, eye_side, file_reference, status, created_at, is_active)
        VALUES (?, ?, 'LEFT', 'secure://uploads/test_left_dup.jpg', 'Completed', ?, 1);
        """, (f"SCAN-L-DUP-{uuid.uuid4().hex[:4]}", test_asm_id, now_str))
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_active_scan_caught = True
        conn.rollback()

    assert duplicate_active_scan_caught, "Failed to prevent duplicate active scan for same assessment + eye side!"
    print("✅ 9. Duplicate active scan prevention on (assessment_id, eye_side) verified.")

    # 10. Report -> Assessment relationship & duplicate prevention
    test_rep_id = f"REP-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO reports (report_id, assessment_id, version, status, created_at)
    VALUES (?, ?, 'v1.0', 'REPORT_READY', ?);
    """, (test_rep_id, test_asm_id, now_str))
    conn.commit()

    duplicate_report_caught = False
    try:
        cursor.execute("""
        INSERT INTO reports (report_id, assessment_id, version, status, created_at)
        VALUES (?, ?, 'v1.0', 'REPORT_READY', ?);
        """, (f"REP-DUP-{uuid.uuid4().hex[:4]}", test_asm_id, now_str))
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_report_caught = True
        conn.rollback()

    assert duplicate_report_caught, "Failed to prevent duplicate report for same assessment + version!"
    print("✅ 10. Report -> Assessment relationship and duplicate prevention verified.")

    # 11. Counsellor assignment relationships
    test_assign_id = f"ASSIGN-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO counsellor_assignments (assignment_id, assessment_id, student_id, counsellor_id, assigned_by, assigned_at)
    VALUES (?, ?, ?, 'counselor1', 'admin', ?);
    """, (test_assign_id, test_asm_id, test_stu_id, now_str))
    conn.commit()

    cursor.execute("SELECT counsellor_id FROM counsellor_assignments WHERE assessment_id = ?;", (test_asm_id,))
    assert cursor.fetchone()[0] == "counselor1"
    print("✅ 11. Counsellor assignment relationship verified.")

    # 12. Foreign key integrity
    invalid_fk_caught = False
    try:
        cursor.execute("""
        INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
        VALUES ('ASM-ORPHAN-TEST', 'NON-EXISTENT-STUDENT', 'REGISTERED', 'test', datetime('now'));
        """)
        conn.commit()
    except sqlite3.IntegrityError:
        invalid_fk_caught = True
        conn.rollback()

    assert invalid_fk_caught, "Foreign key constraint failed to block orphan assessment!"
    print("✅ 12. Foreign key integrity constraint actively enforced.")

    # 13. Required indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    all_indexes = set(r[0] for r in cursor.fetchall())
    required_indexes = [
        "idx_students_student_id",
        "idx_assessments_assessment_id",
        "idx_assessments_student_id",
        "idx_assessments_status",
        "idx_eye_scans_assessment_id",
        "idx_eye_scans_eye_side",
        "idx_reports_assessment_id",
        "idx_counsellor_assignments_counsellor_id",
        "idx_counsellor_assignments_assessment_id",
        "idx_audit_logs_user_id",
        "idx_audit_logs_assessment_id",
        "idx_processing_logs_assessment_id",
    ]
    for idx in required_indexes:
        assert idx in all_indexes, f"Index '{idx}' missing from database!"
    print(f"✅ 13. All {len(required_indexes)} required performance indexes verified.")

    # 14. Invalid assessment state rejected
    invalid_state_caught = False
    try:
        cursor.execute("""
        INSERT INTO assessments (assessment_id, student_id, status, created_by, created_at)
        VALUES ('ASM-INVALID-STATE', ?, 'INVALID_JUNK_STATE', 'test', datetime('now'));
        """, (test_stu_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        invalid_state_caught = True
        conn.rollback()

    assert invalid_state_caught, "Failed to reject invalid assessment state via CHECK constraint!"
    print("✅ 14. Invalid assessment state properly rejected by CHECK constraint.")

    # 15. Invalid eye side rejected
    invalid_eye_caught = False
    try:
        cursor.execute("""
        INSERT INTO eye_scans (scan_id, assessment_id, eye_side, file_reference, status, created_at)
        VALUES ('SCAN-INVALID-EYE', ?, 'MIDDLE_EYE', 'file://test.jpg', 'Completed', datetime('now'));
        """, (test_asm_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        invalid_eye_caught = True
        conn.rollback()

    assert invalid_eye_caught, "Failed to reject invalid eye side via CHECK constraint!"
    print("✅ 15. Invalid eye side properly rejected by CHECK constraint.")

    # Clean up test rows
    cursor.execute("DELETE FROM counsellor_assignments WHERE assignment_id = ?;", (test_assign_id,))
    cursor.execute("DELETE FROM reports WHERE report_id = ?;", (test_rep_id,))
    cursor.execute("DELETE FROM eye_scans WHERE assessment_id IN (?, ?);", (test_asm_id, test_asm_id2))
    cursor.execute("DELETE FROM assessments WHERE student_id = ?;", (test_stu_id,))
    cursor.execute("DELETE FROM students WHERE student_id = ?;", (test_stu_id,))
    conn.commit()

    # 16. Existing historical records preserved
    baseline_expectations = {
        "academic_records": 10,
        "activity_catalog": 15,
        "app_users": 3,
        "assessment_questions": 21,
        "career_catalog": 7,
        "dashboard_activity": 57,
        "iris_embeddings": 536,
        "iris_users": 18,
        "scan_history": 57,
        "student_activities": 2,
        "student_interests": 4,
        "student_profiles": 4,
        "student_skills": 5,
    }

    for tbl, expected_min in baseline_expectations.items():
        cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
        actual_count = cursor.fetchone()[0]
        assert actual_count >= expected_min, f"Table '{tbl}' lost rows! Expected at least {expected_min}, got {actual_count}"

    print("✅ 16. Historical records across all 13 baseline tables preserved with zero data loss.")

    # 17. Existing Iris tables/data unchanged
    cursor.execute("SELECT id, employee_code, user_name FROM iris_users LIMIT 1;")
    first_user = cursor.fetchone()
    assert first_user is not None and len(first_user) == 3, "iris_users record damaged!"
    cursor.execute("SELECT COUNT(*) FROM iris_embeddings WHERE employee_code IS NOT NULL;")
    assert cursor.fetchone()[0] == 536, "iris_embeddings count altered!"

    print("✅ 17. Existing Iris biometric templates and user records completely intact.")

    conn.close()
    print("=" * 70)
    print("ALL 17 PHASE 1 DATABASE VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

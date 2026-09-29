"""
Official IRIS Database Foundation & Relational Schema Module (Phase 1).
Implements non-destructive DDL and relational schema required by:
- IRIS_Backend_Detailed_Requirements.docx
- IRIS_Frontend_Detailed_Requirements.docx

Preserves 100% of existing tables, ML models, and historical biometric/profiling records.
"""

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "iris_database.db")

OFFICIAL_ASSESSMENT_STATES = (
    "REGISTERED",
    "SCAN_PENDING",
    "LEFT_SCAN_COMPLETED",
    "RIGHT_SCAN_COMPLETED",
    "SCAN_COMPLETED",
    "PROCESSING",
    "ANALYSIS_COMPLETED",
    "REPORT_GENERATING",
    "REPORT_READY",
    "FAILED",
)

OFFICIAL_EYE_SIDES = ("LEFT", "RIGHT")
OFFICIAL_SCAN_STATUSES = ("Pending", "Processing", "Completed", "Failed")
OFFICIAL_REPORT_STATUSES = ("REPORT_GENERATING", "REPORT_READY", "FAILED")


def get_connection():
    """Returns a thread-safe connection with foreign key constraints enabled."""
    conn = sqlite3.connect(DB_NAME, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_official_tables():
    """
    Idempotent, non-destructive provisioning of official relational tables,
    indexes, and constraints.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # -------------------------------------------------------------
    # 1. ROLES
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Seed baseline roles if empty
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    official_roles = [
        ("Admin", "System Administrator with full management access", now_str),
        ("Student", "Student with self-service assessment, scan, and report access", now_str),
        ("Counsellor", "Counsellor with assigned student guidance and report review access", now_str),
    ]
    for r_name, r_desc, r_time in official_roles:
        cursor.execute("""
        INSERT OR IGNORE INTO roles (role_name, description, created_at)
        VALUES (?, ?, ?);
        """, (r_name, r_desc, r_time))

    # -------------------------------------------------------------
    # 2. STUDENTS (Official Master Entity)
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        student_name TEXT NOT NULL,
        created_by TEXT DEFAULT 'system',
        created_at TEXT NOT NULL,
        updated_at TEXT,
        status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'INACTIVE', 'ARCHIVED'))
    );
    """)

    # Non-destructive extension of existing student_profiles table if needed
    cursor.execute("PRAGMA table_info(student_profiles);")
    prof_cols = [c[1] for c in cursor.fetchall()]
    if "created_by" not in prof_cols:
        cursor.execute("ALTER TABLE student_profiles ADD COLUMN created_by TEXT DEFAULT 'system';")
    if "student_name" not in prof_cols:
        cursor.execute("ALTER TABLE student_profiles ADD COLUMN student_name TEXT;")

    # Populate students from existing student_profiles non-destructively
    cursor.execute("""
    INSERT OR IGNORE INTO students (student_id, student_name, created_by, created_at, updated_at)
    SELECT 
        student_id, 
        full_name, 
        COALESCE(created_by, 'system'), 
        COALESCE(created_on, datetime('now')), 
        COALESCE(updated_on, datetime('now'))
    FROM student_profiles;
    """)

    # -------------------------------------------------------------
    # 3. ASSESSMENTS (Workflow State Machine)
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id TEXT UNIQUE NOT NULL,
        student_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN (
            'REGISTERED',
            'SCAN_PENDING',
            'LEFT_SCAN_COMPLETED',
            'RIGHT_SCAN_COMPLETED',
            'SCAN_COMPLETED',
            'PROCESSING',
            'ANALYSIS_COMPLETED',
            'REPORT_GENERATING',
            'REPORT_READY',
            'FAILED'
        )),
        created_by TEXT DEFAULT 'system',
        created_at TEXT NOT NULL,
        updated_at TEXT,
        completed_at TEXT,
        FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE RESTRICT
    );
    """)

    # -------------------------------------------------------------
    # 4. EYE_SCANS (Mandatory Dual Scan Records)
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eye_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT UNIQUE NOT NULL,
        assessment_id TEXT NOT NULL,
        eye_side TEXT NOT NULL CHECK(eye_side IN ('LEFT', 'RIGHT')),
        file_reference TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Pending', 'Processing', 'Completed', 'Failed')),
        result_reference TEXT,
        error_code TEXT,
        error_message TEXT,
        attempt_number INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT
    );
    """)

    # Partial unique index to enforce single active scan per eye side per assessment
    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_eye_scans_unique_active_assessment_eye 
    ON eye_scans(assessment_id, eye_side) 
    WHERE is_active = 1;
    """)

    # -------------------------------------------------------------
    # 5. ANALYSIS_RESULTS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analysis_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id TEXT UNIQUE NOT NULL,
        results_json TEXT NOT NULL,
        model_version TEXT DEFAULT 'v1.0',
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT
    );
    """)

    # -------------------------------------------------------------
    # 6. REPORTS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id TEXT UNIQUE NOT NULL,
        assessment_id TEXT NOT NULL,
        version TEXT NOT NULL DEFAULT 'v1.0',
        status TEXT NOT NULL CHECK(status IN ('REPORT_GENERATING', 'REPORT_READY', 'FAILED')),
        generated_at TEXT,
        pdf_reference TEXT,
        reviewed_status INTEGER DEFAULT 0,
        reviewed_by TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT,
        UNIQUE(assessment_id, version)
    );
    """)

    # -------------------------------------------------------------
    # 7. REPORT_SECTIONS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id TEXT NOT NULL,
        section_key TEXT NOT NULL,
        title TEXT,
        content_json TEXT NOT NULL,
        order_num INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(report_id) REFERENCES reports(report_id) ON DELETE RESTRICT,
        UNIQUE(report_id, section_key)
    );
    """)

    # -------------------------------------------------------------
    # 8. COUNSELLOR_ASSIGNMENTS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS counsellor_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id TEXT UNIQUE NOT NULL,
        assessment_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        counsellor_id TEXT NOT NULL,
        assigned_by TEXT NOT NULL,
        assigned_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'COMPLETED', 'REVOKED')),
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT,
        FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE RESTRICT
    );
    """)

    # -------------------------------------------------------------
    # 9. COUNSELLING_NOTES
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS counselling_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        note_id TEXT UNIQUE NOT NULL,
        assessment_id TEXT NOT NULL,
        counsellor_id TEXT NOT NULL,
        note TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT
    );
    """)

    # -------------------------------------------------------------
    # 10. FOLLOW_UPS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS follow_ups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follow_up_id TEXT UNIQUE NOT NULL,
        assessment_id TEXT NOT NULL,
        counsellor_id TEXT NOT NULL,
        follow_up_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Completed', 'Cancelled', 'Overdue')),
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT
    );
    """)

    # -------------------------------------------------------------
    # 11. AUDIT_LOGS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_id TEXT UNIQUE NOT NULL,
        user_id TEXT,
        role TEXT,
        action TEXT NOT NULL,
        assessment_id TEXT,
        entity_type TEXT,
        entity_id TEXT,
        correlation_id TEXT,
        ip_address TEXT,
        status TEXT NOT NULL DEFAULT 'SUCCESS',
        safe_metadata_json TEXT,
        timestamp TEXT NOT NULL
    );
    """)

    # -------------------------------------------------------------
    # 12. PROCESSING_LOGS
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processing_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        processing_id TEXT UNIQUE NOT NULL,
        assessment_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        status TEXT NOT NULL,
        safe_error_code TEXT,
        safe_error_message TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        duration_ms INTEGER,
        model_version TEXT,
        FOREIGN KEY(assessment_id) REFERENCES assessments(assessment_id) ON DELETE RESTRICT
    );
    """)

    # -------------------------------------------------------------
    # 13. REVOKED_TOKENS (Server-Side Token Revocation / Blacklist)
    # -------------------------------------------------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS revoked_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT UNIQUE NOT NULL,
        revoked_at TEXT NOT NULL,
        expires_at INTEGER NOT NULL
    );
    """)

    # -------------------------------------------------------------
    # 14. INDEXES
    # -------------------------------------------------------------
    indexes = [
        # revoked_tokens
        ("idx_revoked_tokens_hash", "revoked_tokens", "token_hash"),
        # students
        ("idx_students_student_id", "students", "student_id"),
        # assessments
        ("idx_assessments_assessment_id", "assessments", "assessment_id"),
        ("idx_assessments_student_id", "assessments", "student_id"),
        ("idx_assessments_status", "assessments", "status"),
        ("idx_assessments_created_at", "assessments", "created_at"),
        # eye_scans
        ("idx_eye_scans_scan_id", "eye_scans", "scan_id"),
        ("idx_eye_scans_assessment_id", "eye_scans", "assessment_id"),
        ("idx_eye_scans_eye_side", "eye_scans", "eye_side"),
        ("idx_eye_scans_status", "eye_scans", "status"),
        # reports
        ("idx_reports_report_id", "reports", "report_id"),
        ("idx_reports_assessment_id", "reports", "assessment_id"),
        ("idx_reports_status", "reports", "status"),
        # counsellor_assignments
        ("idx_counsellor_assignments_counsellor_id", "counsellor_assignments", "counsellor_id"),
        ("idx_counsellor_assignments_assessment_id", "counsellor_assignments", "assessment_id"),
        ("idx_counsellor_assignments_student_id", "counsellor_assignments", "student_id"),
        # counselling_notes
        ("idx_counselling_notes_assessment_id", "counselling_notes", "assessment_id"),
        ("idx_counselling_notes_counsellor_id", "counselling_notes", "counsellor_id"),
        # follow_ups
        ("idx_follow_ups_assessment_id", "follow_ups", "assessment_id"),
        ("idx_follow_ups_counsellor_id", "follow_ups", "counsellor_id"),
        ("idx_follow_ups_status", "follow_ups", "status"),
        # audit_logs
        ("idx_audit_logs_user_id", "audit_logs", "user_id"),
        ("idx_audit_logs_assessment_id", "audit_logs", "assessment_id"),
        ("idx_audit_logs_action", "audit_logs", "action"),
        ("idx_audit_logs_timestamp", "audit_logs", "timestamp"),
        # processing_logs
        ("idx_processing_logs_assessment_id", "processing_logs", "assessment_id"),
        ("idx_processing_logs_operation", "processing_logs", "operation"),
    ]

    for idx_name, table_name, col_name in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({col_name});")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_official_tables()
    print("Official IRIS relational tables initialized successfully.")

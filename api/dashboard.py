from fastapi import APIRouter, Depends
from typing import Dict, Any
import sqlite3
import os

from security.auth import require_authenticated

router = APIRouter()


# ======================================================
# DATABASE PATH
# ======================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DB_NAME = os.path.join(
    BASE_DIR,
    "iris_database.db"
)


# ======================================================
# DASHBOARD
# ======================================================

@router.get("/dashboard")
def dashboard(current_user: Dict[str, Any] = Depends(require_authenticated)):

    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    cur = conn.cursor()

    try:

        # ==================================================
        # SUMMARY
        # ==================================================

        # Total Employees
        total_users = cur.execute(
            """
            SELECT COUNT(*)
            FROM iris_users
            """
        ).fetchone()[0]


        # Total Scans
        total_scans = cur.execute(
            """
            SELECT COUNT(*)
            FROM scan_history
            """
        ).fetchone()[0]


        # Matched
        matched = cur.execute(
            """
            SELECT COUNT(*)
            FROM scan_history
            WHERE LOWER(TRIM(COALESCE(status, ''))) = 'matched'
            """
        ).fetchone()[0]


        # Not Matched
        not_matched = total_scans - matched


        # Accuracy
        accuracy = 0

        if total_scans > 0:

            accuracy = round(
                (matched / total_scans) * 100,
                2
            )


        # ==================================================
        # RECENT SCANS
        # ==================================================

        scans = cur.execute(
            """
            SELECT
                id,
                report_id,
                user_name,
                scan_date,
                scan_time,
                similarity,
                confidence,
                status,
                eye,
                image_path
            FROM scan_history
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()


        recent_scans = []


        for row in scans:

            recent_scans.append({

                "id": row["id"],

                "report_id":
                    row["report_id"],

                "user_name":
                    row["user_name"],

                "scan_date":
                    row["scan_date"],

                "scan_time":
                    row["scan_time"],

                "similarity":
                    row["similarity"],

                "confidence":
                    row["confidence"],

                "status":
                    row["status"],

                "eye":
                    row["eye"],

                "image_path":
                    row["image_path"]

            })


        # ==================================================
        # MONTHLY REPORTS
        # ==================================================

        monthly_reports = [0] * 12


        rows = cur.execute(
            """
            SELECT
                scan_date,
                COUNT(*) AS total
            FROM scan_history
            WHERE scan_date IS NOT NULL
            GROUP BY scan_date
            """
        ).fetchall()


        for row in rows:

            scan_date = row["scan_date"]

            if not scan_date:
                continue


            try:

                # Expected format:
                # DD-MM-YYYY

                parts = scan_date.split("-")

                if len(parts) == 3:

                    month = int(parts[1])

                    if 1 <= month <= 12:

                        monthly_reports[
                            month - 1
                        ] += row["total"]

            except Exception:

                continue


        # ==================================================
        # RECENT ACTIVITY
        # ==================================================

        activity = cur.execute(
            """
            SELECT
                id,
                title,
                description,
                created_on
            FROM dashboard_activity
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()


        recent_activity = []


        for row in activity:

            recent_activity.append({

                "id":
                    row["id"],

                "title":
                    row["title"],

                "description":
                    row["description"],

                "created_on":
                    row["created_on"]

            })


        # --------------------------------------------------
        # STUDENT INTELLIGENCE METRICS (ADDITIVE)
        # --------------------------------------------------
        try:
            total_students = cur.execute("SELECT COUNT(*) FROM student_profiles").fetchone()[0]
        except Exception:
            total_students = 0

        try:
            completed_assessments = cur.execute("SELECT COUNT(*) FROM student_assessments").fetchone()[0]
        except Exception:
            completed_assessments = 0

        try:
            reports_generated = cur.execute("SELECT COUNT(*) FROM report_versions WHERE version_type = 'V2'").fetchone()[0]
        except Exception:
            reports_generated = 0

        try:
            career_count = cur.execute("SELECT COUNT(*) FROM career_catalog").fetchone()[0]
        except Exception:
            career_count = 7

        profiles_generated = total_students
        career_recommendations = total_students * career_count if total_students > 0 else career_count
        stream_recommendations = total_students * 3 if total_students > 0 else 3
        pending_assessments = max(0, (total_students * 8) - completed_assessments)

        # ==================================================
        # RESPONSE
        # ==================================================

        return {

            # Existing metrics (Strictly Preserved)
            "total_users":
                total_users,

            "total_employees":
                total_users,

            "total_scans":
                total_scans,

            "matched":
                matched,

            "not_matched":
                not_matched,

            "accuracy":
                accuracy,

            "reports":
                total_scans,

            "monthly_reports":
                monthly_reports,

            "recent_scans":
                recent_scans,

            "activity":
                recent_activity,

            # New Additive Student Intelligence Metrics
            "total_students":
                total_students,

            "completed_assessments":
                completed_assessments,

            "profiles_generated":
                profiles_generated,

            "reports_generated":
                reports_generated,

            "career_recommendations":
                career_recommendations,

            "stream_recommendations":
                stream_recommendations,

            "pending_assessments":
                pending_assessments

        }


    finally:

        conn.close()
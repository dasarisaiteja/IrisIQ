import os
import sqlite3
import json
from datetime import datetime
import time


# ======================================================
# DATABASE PATH
# ======================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(
    BASE_DIR,
    "iris_database.db"
)


# ======================================================
# DATABASE CONNECTION
# ======================================================

def get_connection():

    return sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )


# ======================================================
# CREATE DATABASE
# ======================================================

def create_database():

    conn = get_connection()
    cursor = conn.cursor()

    # ---------------- USERS ----------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS iris_users (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        employee_code TEXT UNIQUE NOT NULL,

        user_name TEXT NOT NULL,

        department TEXT,

        designation TEXT,

        gender TEXT,

        age INTEGER,

        dob TEXT,

        blood_group TEXT,

        mobile TEXT,

        email TEXT,

        address TEXT,

        photo_path TEXT,

        iris_code TEXT NOT NULL,

        embedding_count INTEGER DEFAULT 1,

        created_on TEXT

    )
    """)

    # ---------------- EMBEDDINGS ----------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS iris_embeddings (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        employee_code TEXT NOT NULL,

        embedding TEXT NOT NULL,

        image_path TEXT,

        created_on TEXT

    )
    """)

    # ---------------- SCAN HISTORY ----------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_history (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        report_id TEXT,

        user_name TEXT,

        similarity REAL,

        confidence REAL,

        status TEXT,

        scan_date TEXT,

        scan_time TEXT,

        eye TEXT,

        image_path TEXT

    )
    """)

    # ---------------- DASHBOARD ACTIVITY ----------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dashboard_activity (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        title TEXT,

        description TEXT,

        created_on TEXT

    )
    """)

    conn.commit()
    conn.close()


# ======================================================
# ENROLL USER
# ======================================================

def enroll_user(
    employee_code,
    user_name,
    department,
    designation,
    gender,
    age,
    dob,
    blood_group,
    mobile,
    email,
    address,
    photo_path,
    embedding
):

    conn = get_connection()
    cursor = conn.cursor()

    embedding_json = json.dumps(embedding)

    cursor.execute(
        """
        SELECT id
        FROM iris_users
        WHERE employee_code = ?
        """,
        (employee_code,)
    )

    exists = cursor.fetchone()

    if exists:

        cursor.execute(
            """
            UPDATE iris_users
            SET
                photo_path = ?,
                iris_code = ?,
                embedding_count = embedding_count + 1
            WHERE employee_code = ?
            """,
            (
                photo_path,
                embedding_json,
                employee_code
            )
        )

    else:

        cursor.execute(
            """
            INSERT INTO iris_users
            (
                employee_code,
                user_name,
                department,
                designation,
                gender,
                age,
                dob,
                blood_group,
                mobile,
                email,
                address,
                photo_path,
                iris_code,
                embedding_count,
                created_on
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee_code,
                user_name,
                department,
                designation,
                gender,
                age,
                dob,
                blood_group,
                mobile,
                email,
                address,
                photo_path,
                embedding_json,
                1,
                datetime.now().strftime(
                    "%d-%m-%Y %H:%M:%S"
                )
            )
        )

    conn.commit()
    conn.close()


# ======================================================
# SAVE SINGLE EMBEDDING
# ======================================================

def save_embedding(
    employee_code,
    embedding,
    image_path
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO iris_embeddings
        (
            employee_code,
            embedding,
            image_path,
            created_on
        )
        VALUES
        (?, ?, ?, ?)
        """,
        (
            employee_code,
            json.dumps(embedding),
            image_path,
            datetime.now().strftime(
                "%d-%m-%Y %H:%M:%S"
            )
        )
    )

    conn.commit()
    conn.close()


# ======================================================
# SAVE EMBEDDINGS BULK
# ======================================================

def save_embeddings_bulk(
    employee_code,
    embeddings
):

    for retry in range(5):

        conn = None

        try:

            conn = sqlite3.connect(
                DB_NAME,
                timeout=30,
                check_same_thread=False
            )

            cursor = conn.cursor()

            # Remove old embeddings
            cursor.execute(
                """
                DELETE FROM iris_embeddings
                WHERE employee_code = ?
                """,
                (employee_code,)
            )

            rows = []

            for embedding, image_path in embeddings:

                rows.append(
                    (
                        employee_code,
                        json.dumps(embedding),
                        image_path,
                        datetime.now().strftime(
                            "%d-%m-%Y %H:%M:%S"
                        )
                    )
                )

            if rows:

                cursor.executemany(
                    """
                    INSERT INTO iris_embeddings
                    (
                        employee_code,
                        embedding,
                        image_path,
                        created_on
                    )
                    VALUES
                    (?, ?, ?, ?)
                    """,
                    rows
                )

            conn.commit()
            conn.close()

            return

        except sqlite3.OperationalError:

            if conn:

                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass

            time.sleep(1)

    raise Exception(
        "Unable to save embeddings"
    )


# ======================================================
# GET ALL USERS
# ======================================================

def get_all_users():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        id,
        employee_code,
        user_name,
        department,
        designation,
        gender,
        age,
        dob,
        blood_group,
        mobile,
        email,
        address,
        photo_path,
        iris_code,
        created_on
    FROM iris_users
    ORDER BY user_name
    """)

    rows = cursor.fetchall()

    conn.close()

    users = []

    for row in rows:

        try:
            embedding = json.loads(row[13])
        except Exception:
            embedding = []

        users.append({

            "id": row[0],

            "employee_code": row[1],

            "user_name": row[2],

            "department": row[3],

            "designation": row[4],

            "gender": row[5],

            "age": row[6],

            "dob": row[7],

            "blood_group": row[8],

            "mobile": row[9],

            "email": row[10],

            "address": row[11],

            "photo_path": row[12],

            "embedding": embedding,

            "created_on": row[14]

        })

    return users


# ======================================================
# GET EMBEDDINGS
# ======================================================

def get_embeddings(employee_code):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT embedding
        FROM iris_embeddings
        WHERE employee_code = ?
        """,
        (employee_code,)
    )

    rows = cursor.fetchall()

    conn.close()

    embeddings = []

    for row in rows:

        try:
            embeddings.append(
                json.loads(row[0])
            )
        except Exception:
            continue

    return embeddings


# ======================================================
# GET SINGLE USER
# ======================================================

def get_user(employee_code):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            employee_code,
            user_name,
            department,
            designation,
            gender,
            age,
            dob,
            blood_group,
            mobile,
            email,
            address,
            photo_path,
            iris_code,
            created_on
        FROM iris_users
        WHERE employee_code = ?
    """, (employee_code,))

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    try:
        embedding = json.loads(row[13])
    except Exception:
        embedding = []

    return {

        "id": row[0],

        "employee_code": row[1],

        "user_name": row[2],

        "department": row[3],

        "designation": row[4],

        "gender": row[5],

        "age": row[6],

        "dob": row[7],

        "blood_group": row[8],

        "mobile": row[9],

        "email": row[10],

        "address": row[11],

        "photo_path": row[12],

        "embedding": embedding,

        "created_on": row[14]

    }


# ======================================================
# GET EMPLOYEE IMAGES
# ======================================================

def get_employee_images(employee_code):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT image_path
        FROM iris_embeddings
        WHERE employee_code = ?
        ORDER BY id
        """,
        (employee_code,)
    )

    rows = cursor.fetchall()

    conn.close()

    return [
        row[0]
        for row in rows
        if row[0]
    ]


# ======================================================
# USER COUNT
# ======================================================

def get_user_count(user_name):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM iris_users
        WHERE user_name = ?
        """,
        (user_name,)
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count


# ======================================================
# SAVE SCAN HISTORY
# ======================================================

def save_scan_history(
    report_id,
    user_name,
    similarity,
    confidence,
    status,
    scan_date,
    scan_time,
    eye,
    image_path
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO scan_history
        (
            report_id,
            user_name,
            similarity,
            confidence,
            status,
            scan_date,
            scan_time,
            eye,
            image_path
        )
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_id,
            user_name,
            similarity,
            confidence,
            status,
            scan_date,
            scan_time,
            eye,
            image_path
        )
    )

    conn.commit()
    conn.close()


# ======================================================
# GET RECENT SCANS
# ======================================================

def get_recent_scans(limit=10):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            report_id,
            user_name,
            similarity,
            confidence,
            status,
            scan_date,
            scan_time,
            eye,
            image_path
        FROM scan_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    conn.close()

    scans = []

    for row in rows:

        scans.append({

            "id": row[0],

            "report_id": row[1],

            "user_name": row[2],

            "similarity": row[3],

            "confidence": row[4],

            "status": row[5],

            "scan_date": row[6],

            "scan_time": row[7],

            "eye": row[8],

            "image_path": row[9]

        })

    return scans


# ======================================================
# DASHBOARD ACTIVITY
# ======================================================

def add_dashboard_activity(
    title,
    description
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO dashboard_activity
        (
            title,
            description,
            created_on
        )
        VALUES
        (?, ?, ?)
        """,
        (
            title,
            description,
            datetime.now().strftime(
                "%d-%m-%Y %H:%M:%S"
            )
        )
    )

    conn.commit()
    conn.close()


# ======================================================
# GET RECENT DASHBOARD ACTIVITY
# ======================================================

def get_recent_activity(limit=10):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            description,
            created_on
        FROM dashboard_activity
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    conn.close()

    activities = []

    for row in rows:

        activities.append({

            "id": row[0],

            "title": row[1],

            "description": row[2],

            "created_on": row[3]

        })

    return activities


# ======================================================
# DASHBOARD SUMMARY
# ======================================================

def get_dashboard_summary():

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------
    # TOTAL EMPLOYEES
    # --------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM iris_users
    """)

    total_users = cursor.fetchone()[0]

    # --------------------------------------------------
    # TOTAL SCANS
    # --------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM scan_history
    """)

    total_scans = cursor.fetchone()[0]

    # --------------------------------------------------
    # MATCHED
    # --------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM scan_history
        WHERE LOWER(TRIM(COALESCE(status, ''))) = 'matched'
    """)

    matched = cursor.fetchone()[0]

    # --------------------------------------------------
    # NOT MATCHED
    # --------------------------------------------------

    not_matched = total_scans - matched

    # --------------------------------------------------
    # ACCURACY
    # --------------------------------------------------

    accuracy = 0

    if total_scans > 0:

        accuracy = round(
            (matched / total_scans) * 100,
            2
        )

    # --------------------------------------------------
    # REPORTS
    # --------------------------------------------------

    reports = total_scans

    conn.close()

    return {

        "total_users": total_users,

        "total_employees": total_users,

        "total_scans": total_scans,

        "matched": matched,

        "not_matched": not_matched,

        "accuracy": accuracy,

        "reports": reports

    }


# ======================================================
# INITIALIZE DATABASE
# ======================================================

create_database()
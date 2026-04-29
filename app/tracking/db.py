import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/jobs.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            title           TEXT NOT NULL,
            company         TEXT NOT NULL,
            location        TEXT,
            remote_type     TEXT,
            salary_range    TEXT,
            apply_method    TEXT,
            apply_url       TEXT,
            jd_url          TEXT,
            jd_text         TEXT,
            jd_hash         TEXT UNIQUE,
            skill_score     INTEGER,
            hire_score      INTEGER,
            status          TEXT DEFAULT 'new',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS applications (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id              INTEGER NOT NULL REFERENCES jobs(id),
            cv_path             TEXT,
            cover_letter_path   TEXT,
            ats_score           INTEGER,
            submitted_at        TEXT,
            submission_method   TEXT,
            status              TEXT DEFAULT 'applied',
            follow_up_21_at     TEXT,
            follow_up_30_at     TEXT,
            ghosted_at          TEXT,
            notes               TEXT
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            body        TEXT NOT NULL,
            read        INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()
    print("Database initialised at", DB_PATH)


# ── JOBS ──────────────────────────────────────────────

def insert_job(source, title, company, location=None, remote_type=None,
               salary_range=None, apply_method=None, apply_url=None,
               jd_url=None, jd_text=None, jd_hash=None):
    """Insert a new job. Returns the new row id, or None if duplicate."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (source, title, company, location, remote_type,
                              salary_range, apply_method, apply_url,
                              jd_url, jd_text, jd_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (source, title, company, location, remote_type,
              salary_range, apply_method, apply_url,
              jd_url, jd_text, jd_hash))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # jd_hash already exists — duplicate job
        return None
    finally:
        conn.close()


def get_unscored_jobs():
    """Return jobs that have not been scored yet."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE skill_score IS NULL AND status = 'new'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_job_scores(job_id, skill_score, hire_score):
    """Save AI scores and update status to qualified or skipped."""
    from app.config import settings
    status = (
        "qualified"
        if skill_score >= settings.skill_score_threshold
        and hire_score >= settings.hire_score_threshold
        else "skipped"
    )
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET skill_score=?, hire_score=?, status=? WHERE id=?",
        (skill_score, hire_score, status, job_id)
    )
    conn.commit()
    conn.close()


def get_qualified_jobs():
    """Return jobs that passed scoring and have not been applied to yet."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status = 'qualified'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── APPLICATIONS ───────────────────────────────────────

def insert_application(job_id, cv_path, cover_letter_path,
                        ats_score, submission_method):
    """Record a submitted application."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO applications
            (job_id, cv_path, cover_letter_path, ats_score,
             submitted_at, submission_method, status)
        VALUES (?, ?, ?, ?, ?, ?, 'applied')
    """, (job_id, cv_path, cover_letter_path, ats_score,
          datetime.utcnow().isoformat(), submission_method))
    conn.execute(
        "UPDATE jobs SET status='applied' WHERE id=?", (job_id,)
    )
    conn.commit()
    app_id = cursor.lastrowid
    conn.close()
    return app_id


def get_applications_due_followup(day: int):
    """Return applications due for a follow-up at day 21 or 30."""
    column = "follow_up_21_at" if day == 21 else "follow_up_30_at"
    conn = get_connection()
    rows = conn.execute(f"""
        SELECT a.*, j.title, j.company, j.apply_url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.status = 'applied'
          AND a.{column} IS NULL
          AND julianday('now') - julianday(a.submitted_at) >= ?
    """, (day,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_application_status(app_id, status):
    """Update the status of an application."""
    conn = get_connection()
    conn.execute(
        "UPDATE applications SET status=? WHERE id=?", (status, app_id)
    )
    conn.commit()
    conn.close()


def count_applications_today():
    """Return how many applications were submitted today."""
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) as cnt FROM applications
        WHERE date(submitted_at) = date('now')
    """).fetchone()
    conn.close()
    return row["cnt"]


def get_pipeline_stats():
    """Return a summary count of applications by status."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM applications
        GROUP BY status
    """).fetchall()
    conn.close()
    return {r["status"]: r["count"] for r in rows}


# ── NOTIFICATIONS ───────────────────────────────────────

def add_notification(title: str, body: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO notifications (title, body) VALUES (?, ?)", (title, body)
    )
    conn.commit()
    conn.close()


def get_notifications(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_unread_notifications() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as c FROM notifications WHERE read=0").fetchone()
    conn.close()
    return row["c"]


def mark_notifications_read():
    conn = get_connection()
    conn.execute("UPDATE notifications SET read=1")
    conn.commit()
    conn.close()

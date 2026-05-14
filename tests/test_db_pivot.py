import importlib
import pytest
import sys
from pathlib import Path


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Isolated DB for each test."""
    db_file = tmp_path / "test.db"

    # Clear module cache
    if "app.tracking.db" in sys.modules:
        del sys.modules["app.tracking.db"]
    if "app.tracking" in sys.modules:
        del sys.modules["app.tracking"]

    # Patch the DB_PATH before the module is imported
    monkeypatch.setattr("pathlib.Path", lambda p="data/jobs.db": Path(db_file) if p == "data/jobs.db" else Path(p))

    # Now import the module
    import app.tracking.db as dbmod

    # Directly set DB_PATH in the loaded module to ensure it's correct
    dbmod.DB_PATH = db_file

    # Initialize DB
    dbmod.init_db()
    yield dbmod


def test_dismiss_job(db):
    job_id = db.insert_job(
        source="test", title="Dev", company="Acme",
        jd_hash="hash1"
    )
    db.dismiss_job(job_id)
    conn = db.get_connection()
    row = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    assert row["status"] == "dismissed"


def test_qualified_jobs_excludes_dismissed(db):
    db.insert_job(source="test", title="Dev A", company="Acme", jd_hash="h1")
    id2 = db.insert_job(source="test", title="Dev B", company="Beta", jd_hash="h2")
    conn = db.get_connection()
    conn.execute("UPDATE jobs SET skill_score=70, hire_score=65, status='qualified' WHERE jd_hash IN ('h1','h2')")
    conn.commit()
    conn.close()
    db.dismiss_job(id2)
    jobs = db.get_qualified_jobs()
    titles = [j["title"] for j in jobs]
    assert "Dev A" in titles
    assert "Dev B" not in titles


def test_create_manual_application(db):
    job_id = db.insert_job(
        source="test", title="Dev", company="Acme", jd_hash="hash3"
    )
    app_id = db.create_manual_application(job_id)
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    conn.close()
    assert row["job_id"] == job_id
    assert row["status"] == "applied"


def test_update_application_status(db):
    job_id = db.insert_job(
        source="test", title="Dev", company="Acme", jd_hash="hash4"
    )
    app_id = db.create_manual_application(job_id)
    db.update_application_status(app_id, "replied")
    conn = db.get_connection()
    row = conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
    conn.close()
    assert row["status"] == "replied"


def test_applied_job_removed_from_queue(db):
    job_id = db.insert_job(source="test", title="Dev C", company="Corp", jd_hash="h3")
    conn = db.get_connection()
    conn.execute("UPDATE jobs SET skill_score=70, status='qualified' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
    db.create_manual_application(job_id)
    jobs = db.get_qualified_jobs()
    titles = [j["title"] for j in jobs]
    assert "Dev C" not in titles

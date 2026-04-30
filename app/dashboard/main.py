"""FastAPI dashboard — serves the UI. Scheduler is managed by app/scheduler.py."""
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.scheduler import build_scheduler
from app.tracking.db import (
    get_connection, count_applications_today,
    get_notifications, count_unread_notifications, mark_notifications_read,
)

app = FastAPI(title="Job Automation Dashboard")

_scheduler = build_scheduler()


@app.on_event("startup")
def startup():
    _scheduler.start()


@app.on_event("shutdown")
def shutdown():
    _scheduler.shutdown()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/apply/{job_id}")
def re_trigger(job_id: int):
    """Re-trigger Playwright for a needs_review job."""
    conn = get_connection()
    job = conn.execute(
        "SELECT * FROM jobs WHERE id=? AND status='needs_review'", (job_id,)
    ).fetchone()
    conn.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not in needs_review state")

    job = dict(job)
    from app.cv.engine import tailor, extract_keywords
    from app.cv.renderer import render
    from app.submission import cover_letter as cl_gen
    from app.submission.form_filler import submit

    tailored = tailor(
        job_id=job["id"],
        title=job["title"],
        company=job["company"],
        jd_text=job.get("jd_text", ""),
    )
    paths = render(tailored)
    cl_text = cl_gen.generate(
        job_id=job["id"],
        title=job["title"],
        company=job["company"],
        keywords=tailored["keywords"],
    )
    job_with_kw = {**job, "keywords": tailored["keywords"]}
    result = submit(job=job_with_kw, cv_path=paths["pdf"], cover_letter_text=cl_text)
    return JSONResponse(result)


@app.get("/api/notifications")
def api_notifications():
    notes = get_notifications(limit=20)
    unread = count_unread_notifications()
    mark_notifications_read()
    return JSONResponse({"notifications": notes, "unread": unread})


@app.get("/api/unread-count")
def api_unread_count():
    return JSONResponse({"unread": count_unread_notifications()})


@app.get("/api/stats")
def api_stats():
    conn = get_connection()
    total_jobs   = conn.execute("SELECT COUNT(*) as c FROM jobs").fetchone()["c"]
    qualified    = conn.execute("SELECT COUNT(*) as c FROM jobs WHERE status='qualified'").fetchone()["c"]
    needs_review = conn.execute("SELECT COUNT(*) as c FROM jobs WHERE status='needs_review'").fetchone()["c"]
    total_applied = conn.execute("SELECT COUNT(*) as c FROM applications WHERE status='applied'").fetchone()["c"]
    replied      = conn.execute("SELECT COUNT(*) as c FROM applications WHERE status='replied'").fetchone()["c"]
    conn.close()
    return {
        "total_jobs": total_jobs,
        "qualified": qualified,
        "applied_today": count_applications_today(),
        "max_per_day": settings.max_applications_per_day,
        "total_applied": total_applied,
        "needs_review": needs_review,
        "replied": replied,
        "dry_run": settings.dry_run,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@app.get("/api/applications")
def api_applications():
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.id, a.submitted_at, a.submission_method as apply_method,
               a.status, a.ats_score,
               j.title, j.company, j.apply_method as job_apply_method
        FROM applications a JOIN jobs j ON j.id = a.job_id
        ORDER BY a.submitted_at DESC LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/queue")
def api_queue():
    conn = get_connection()
    rows = conn.execute("""
        SELECT j.id, j.title, j.company, j.apply_url, j.skill_score, j.hire_score,
               a.notes
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id AND a.status = 'needs_review'
        WHERE j.status = 'needs_review'
        ORDER BY j.skill_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/history")
def api_history(status: str = "", method: str = ""):
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.id, a.submitted_at, a.submission_method as apply_method,
               a.status, a.ats_score, a.cv_path, a.notes,
               a.follow_up_21_at, a.follow_up_30_at,
               j.title, j.company, j.skill_score
        FROM applications a JOIN jobs j ON j.id = a.job_id
        ORDER BY a.submitted_at DESC
    """).fetchall()
    conn.close()
    apps = [dict(r) for r in rows]
    if status:
        apps = [a for a in apps if a["status"] == status]
    if method:
        apps = [a for a in apps if (a["apply_method"] or "").lower() == method.lower()]
    return apps


@app.post("/mark-applied/{job_id}")
def mark_applied(job_id: int):
    """Mark a needs_review job as applied after manual submission."""
    conn = get_connection()
    conn.execute("UPDATE jobs SET status='applied' WHERE id=?", (job_id,))
    conn.execute(
        "UPDATE applications SET status='applied', submitted_at=? WHERE job_id=? AND status='needs_review'",
        (datetime.utcnow().isoformat(), job_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/run-now")
def run_now():
    """Manually trigger the full pipeline immediately."""
    import threading
    from app.scheduler import job_scrape, job_score, job_generate_cvs, job_submit

    def _run_all():
        from app.scheduler import _run
        _run("Scraper", job_scrape)
        _run("Scorer", job_score)
        _run("CV Generator", job_generate_cvs)
        _run("Submitter", job_submit)

    t = threading.Thread(target=_run_all, daemon=True)
    t.start()
    return {"ok": True, "message": "Full pipeline triggered"}


@app.post("/api/run-now")
def api_run_now():
    return run_now()


@app.post("/api/apply/{job_id}")
def api_re_trigger(job_id: int):
    return re_trigger(job_id)


@app.post("/api/mark-applied/{job_id}")
def api_mark_applied(job_id: int):
    return mark_applied(job_id)


# Must be registered last — serves frontend/dist/ at "/" after all /api/* routes
from fastapi.staticfiles import StaticFiles as _StaticFiles
_dist = Path("frontend/dist")
if _dist.exists():
    app.mount("/", _StaticFiles(directory=_dist, html=True), name="frontend")

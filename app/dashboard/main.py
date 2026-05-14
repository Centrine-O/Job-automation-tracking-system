"""FastAPI dashboard — serves the UI. Scheduler is managed by app/scheduler.py."""
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.scheduler import build_scheduler
from app.tracking.db import (
    get_connection, count_applications_today,
    get_notifications, count_unread_notifications, mark_notifications_read,
)
from app import state

# Pydantic request models
class UpdateStatusPayload(BaseModel):
    status: str

class UpdateNotesPayload(BaseModel):
    notes: str

app = FastAPI(title="Job Automation Dashboard")

_scheduler = build_scheduler()


# ── Health check ───────────────────────────────────────────────────────────────

def _check_health() -> dict:
    """Probe each service and return a status dict. Never raises."""
    services = {}

    # SQLite
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        services["sqlite"] = {"status": "ok", "label": "SQLite Database"}
    except Exception as exc:
        services["sqlite"] = {"status": "error", "label": "SQLite Database", "detail": str(exc)[:80]}

    # APScheduler
    services["scheduler"] = {
        "status": "ok" if _scheduler.running else "error",
        "label": "APScheduler",
        "detail": None if _scheduler.running else "Scheduler not running",
    }


    # Playwright / Chromium
    try:
        import playwright  # noqa: F401
        pw_cache = Path.home() / ".cache" / "ms-playwright"
        chromium_ok = pw_cache.exists() and any(pw_cache.glob("chromium-*"))
        if chromium_ok:
            services["playwright"] = {"status": "ok", "label": "Playwright / Chromium"}
        else:
            services["playwright"] = {"status": "warn", "label": "Playwright / Chromium", "detail": "Chromium not installed — run: playwright install chromium"}
    except ImportError:
        services["playwright"] = {"status": "error", "label": "Playwright / Chromium", "detail": "Package not installed"}

    # API keys (presence check only — live calls would burn credits)
    api_keys = [
        ("gemini",      settings.gemini_api_key,      "Gemini API"),
        ("groq",        settings.groq_api_key,         "Groq API"),
        ("cohere",      settings.cohere_api_key,        "Cohere API"),
        ("openrouter",  settings.openrouter_api_key,    "OpenRouter API"),
        ("serpapi",     settings.serpapi_key,           "SerpAPI"),
    ]
    for key, val, label in api_keys:
        services[key] = {
            "status": "ok" if val else "warn",
            "label": label,
            "detail": None if val else "No API key configured",
        }

    return services


def _refresh_health():
    """Update the shared health cache. Called on a background schedule."""
    try:
        services = _check_health()
        state.health_cache.update({
            "checked_at": datetime.utcnow().isoformat(),
            "services": services,
        })
    except Exception:
        pass


@app.on_event("startup")
def startup():
    _scheduler.start()
    # Health-check job: every 60 s, fire immediately on startup
    from apscheduler.triggers.interval import IntervalTrigger
    _scheduler.add_job(
        _refresh_health,
        IntervalTrigger(seconds=60),
        id="health_check",
        replace_existing=True,
    )
    threading.Thread(target=_refresh_health, daemon=True).start()


@app.on_event("shutdown")
def shutdown():
    _scheduler.shutdown()


# ── Routes ─────────────────────────────────────────────────────────────────────

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
    try:
        total_jobs     = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        qualified      = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='qualified'").fetchone()[0]
        dismissed      = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='dismissed'").fetchone()[0]
        total_applied  = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        replied        = conn.execute("SELECT COUNT(*) FROM applications WHERE status='replied'").fetchone()[0]
        offers         = conn.execute("SELECT COUNT(*) FROM applications WHERE status='offer'").fetchone()[0]
    finally:
        conn.close()
    return {
        "total_jobs": total_jobs,
        "qualified": qualified,
        "dismissed": dismissed,
        "total_applied": total_applied,
        "replied": replied,
        "offers": offers,
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


@app.post("/api/jobs/{job_id}/dismiss")
def api_dismiss_job(job_id: int):
    from app.tracking.db import dismiss_job
    dismiss_job(job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/apply")
def api_apply_job(job_id: int):
    from app.tracking.db import create_manual_application
    app_id = create_manual_application(job_id)
    return {"ok": True, "application_id": app_id}


@app.patch("/api/applications/{app_id}/status")
def api_update_status(app_id: int, payload: UpdateStatusPayload):
    from app.tracking.db import update_application_status
    status = payload.status
    allowed = {"applied", "replied", "offer", "rejected", "ghosted"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {allowed}")
    update_application_status(app_id, status)
    return {"ok": True}


@app.patch("/api/applications/{app_id}/notes")
def api_update_notes(app_id: int, payload: UpdateNotesPayload):
    from app.tracking.db import get_connection
    notes = payload.notes
    conn = get_connection()
    try:
        conn.execute("UPDATE applications SET notes=? WHERE id=?", (notes, app_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/api/history")
def api_history(status: str = "", method: str = ""):
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.id, a.job_id, a.status, a.submitted_at, a.notes,
               j.title, j.company, j.apply_url, j.source, j.skill_score
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        ORDER BY a.submitted_at DESC
    """).fetchall()
    conn.close()
    apps = [dict(r) for r in rows]
    if status:
        apps = [a for a in apps if a["status"] == status]
    return apps


@app.post("/run-now")
def run_now():
    """Manually trigger the pipeline immediately."""
    import threading
    from app.scheduler import job_scrape, job_score

    def _run_all():
        from app.scheduler import _run
        _run("Scraper", job_scrape)
        _run("Scorer", job_score)

    t = threading.Thread(target=_run_all, daemon=True)
    t.start()
    return {"ok": True, "message": "Pipeline triggered"}


@app.post("/api/run-now")
def api_run_now():
    return run_now()


@app.get("/api/system/status")
def api_system_status():
    scheduled = {}
    job_labels = {
        "scrape":         "Scraper",
        "score":          "Scorer",
        "generate_cvs":   "CV Generator",
        "submit":         "Submitter",
        "detect_replies": "Reply Detector",
        "followups":      "Follow-up Checker",
        "daily_digest":   "Daily Digest",
    }
    for job_id, label in job_labels.items():
        job = _scheduler.get_job(job_id)
        if job and job.next_run_time:
            scheduled[job_id] = {
                "label": label,
                "next_run": job.next_run_time.isoformat(),
            }
    return {
        "pipeline": state.snapshot(),
        "scheduled": scheduled,
        "now": datetime.utcnow().isoformat(),
    }


@app.get("/api/system/health")
def api_system_health():
    return {
        "checked_at": state.health_cache.get("checked_at"),
        "services": state.health_cache.get("services", {}),
    }


# Must be registered last — serves frontend/dist/ at "/" after all /api/* routes
from fastapi.staticfiles import StaticFiles as _StaticFiles
_dist = Path("frontend/dist")
if _dist.exists():
    app.mount("/", _StaticFiles(directory=_dist, html=True), name="frontend")

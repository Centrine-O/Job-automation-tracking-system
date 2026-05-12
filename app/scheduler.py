"""Production scheduler — all cron jobs for the job automation pipeline.

Schedule (EAT = UTC+3):
  07:00  → Scrape all job boards
  08:00  → Score all new jobs
  09:00  → Generate CVs for newly qualified jobs
  09:30  → Submit applications (respects daily cap + dry_run)
  Every 6h → Detect Gmail replies, update application statuses
  Every 6h → Check follow-up due dates (21-day / 30-day)
  00:00  → Send daily digest email
"""
import logging
import traceback
from datetime import datetime, date
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

# ── Logging setup ──────────────────────────────────────────────────────────────

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "engine.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("scheduler")


_STAGE_KEYS = {
    "Scraper": "scraping",
    "Scorer": "scoring",
    "CV Generator": "generating_cvs",
    "Submitter": "submitting",
    "Reply Detector": "detecting_replies",
    "Follow-up Checker": "checking_followups",
    "Daily Digest": "sending_digest",
}

_INTERVIEW_KEYWORDS = {"interview", "schedule", "call", "meet", "availability", "discuss"}


def _run(label: str, fn):
    """Run a pipeline step, catch and log all exceptions."""
    from app import state
    from app.notifications import telegram
    stage = _STAGE_KEYS.get(label, label.lower().replace(" ", "_"))
    state.set_stage(stage, datetime.utcnow().isoformat())
    state.set_error(None)
    log.info(f"▶ {label} starting")
    try:
        fn()
        log.info(f"✓ {label} complete")
        state.complete_stage(stage, datetime.utcnow().isoformat())
    except Exception:
        err = traceback.format_exc()
        log.error(f"✗ {label} FAILED:\n{err}")
        last_line = err.strip().splitlines()[-1]
        state.set_error(f"{label} failed: {last_line}")
        state.set_stage("idle")
        telegram.alert(f"{label} failed: {last_line}")


# ── Pipeline steps ─────────────────────────────────────────────────────────────

def job_scrape():
    from app.scrapers.run_all import run_all_scrapers
    new = run_all_scrapers()
    log.info(f"  Scraped: {new} new jobs found")


def job_score():
    from app.ai.scorer import score_all
    score_all()


def job_generate_cvs():
    """Pre-generate CVs for all newly qualified jobs that don't have one yet."""
    import sqlite3
    from app.cv.engine import tailor
    from app.cv.renderer import render

    conn = sqlite3.connect("data/jobs.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, company, jd_text FROM jobs
        WHERE status = 'qualified'
          AND jd_text IS NOT NULL AND jd_text != ''
          AND id NOT IN (SELECT job_id FROM applications)
        ORDER BY skill_score DESC
    """).fetchall()
    conn.close()

    log.info(f"  CV generation: {len(rows)} jobs need CVs")
    for row in rows:
        try:
            tailored = tailor(
                job_id=row["id"],
                title=row["title"],
                company=row["company"],
                jd_text=row["jd_text"],
            )
            render(tailored)
            log.info(f"  CV generated for [{row['id']}] {row['title']} @ {row['company']} (ATS {tailored['ats_score']}%)")
        except Exception:
            log.error(f"  CV failed for [{row['id']}] {row['title']}:\n{traceback.format_exc()}")


def job_submit():
    from app.submission.coordinator import run_batch
    result = run_batch()
    log.info(
        f"  Submissions: {result['submitted']} sent, "
        f"{result['skipped']} skipped, "
        f"{result['needs_review']} needs review"
    )


def job_detect_replies():
    """Scan Gmail for replies to sent applications and update DB status."""
    import sqlite3
    from app.notifications import telegram

    conn = sqlite3.connect("data/jobs.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, notes FROM applications
        WHERE submission_method = 'email' AND status = 'applied'
          AND notes LIKE 'gmail_message_id:%'
    """).fetchall()
    conn.close()

    if not rows:
        return

    from app.submission.email_sender import detect_replies

    msg_ids = []
    app_map = {}
    for row in rows:
        msg_id = row["notes"].replace("gmail_message_id:", "").strip()
        msg_ids.append(msg_id)
        app_map[msg_id] = row["id"]

    replies = detect_replies(msg_ids)
    for reply in replies:
        app_id = app_map.get(reply["original_message_id"])
        if not app_id:
            continue

        snippet = reply["snippet"]
        conn = sqlite3.connect("data/jobs.db")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "UPDATE applications SET status='replied', notes=? WHERE id=?",
            (f"Reply: {snippet[:200]}", app_id)
        )
        conn.commit()

        job_row = conn.execute("""
            SELECT j.title, j.company FROM applications a
            JOIN jobs j ON j.id = a.job_id WHERE a.id = ?
        """, (app_id,)).fetchone()
        conn.close()

        log.info(f"  Reply detected for application {app_id}: {snippet[:60]}")

        if any(kw in snippet.lower() for kw in _INTERVIEW_KEYWORDS):
            title   = job_row["title"]   if job_row else "Unknown role"
            company = job_row["company"] if job_row else "Unknown company"
            telegram.alert(
                f"Interview invite — {company} · {title}\n"
                f'"{snippet[:150]}"'
            )
            log.info(f"  Interview keyword detected — Telegram alert sent")


def job_check_followups():
    """Send follow-up emails at Day 21 and Day 30 for email-method applications."""
    from app.tracking.db import get_applications_due_followup, get_connection
    from app.notifications import telegram

    _SUBJECTS = {
        21: "Follow-up: {title} Application — Centrine Ong'aria",
        30: "Second Follow-up: {title} Application — Centrine Ong'aria",
    }
    _BODIES = {
        21: (
            "Dear Hiring Team,\n\n"
            "I hope this message finds you well. I wanted to follow up on my application "
            "for the {title} position at {company}, submitted on {date}.\n\n"
            "I remain very interested in this opportunity and am confident my skills in "
            "software engineering, data analysis, and automation align well with your team's needs.\n\n"
            "Please don't hesitate to reach out if you need additional information.\n\n"
            "Best regards,\nCentrine Ong'aria\ncentyanita@gmail.com | +254 712 382 443"
        ),
        30: (
            "Dear Hiring Team,\n\n"
            "I'm reaching out once more regarding my application for the {title} role "
            "at {company}, submitted on {date}.\n\n"
            "I understand you're reviewing many candidates and appreciate your time. "
            "I remain enthusiastic about this position and believe my background would be a strong fit.\n\n"
            "Best regards,\nCentrine Ong'aria\ncentyanita@gmail.com | +254 712 382 443"
        ),
    }

    for day in (21, 30):
        due = get_applications_due_followup(day)
        if not due:
            continue
        col = "follow_up_21_at" if day == 21 else "follow_up_30_at"
        conn = get_connection()

        for app in due:
            title   = app.get("title", "the role")
            company = app.get("company", "your company")
            date    = (app.get("submitted_at") or "")[:10]
            method  = app.get("submission_method", "")
            apply_url = app.get("apply_url") or ""

            if method == "email" and apply_url:
                to_email = apply_url.replace("mailto:", "").strip()
                if "@" not in to_email:
                    log.info(f"  Follow-up ({day}d): unparseable email for [{app['id']}] — marking done")
                    conn.execute(f"UPDATE applications SET {col}=? WHERE id=?",
                                 (datetime.utcnow().isoformat(), app["id"]))
                    continue

                subject = _SUBJECTS[day].format(title=title)
                body    = _BODIES[day].format(title=title, company=company, date=date)

                try:
                    from app.submission.email_sender import _get_service, _build_message
                    service = _get_service()
                    message = _build_message(to_email, subject, body, [])
                    service.users().messages().send(userId="me", body=message).execute()
                    conn.execute(f"UPDATE applications SET {col}=? WHERE id=?",
                                 (datetime.utcnow().isoformat(), app["id"]))
                    log.info(f"  Follow-up email sent ({day}d): [{app['id']}] {title} @ {company}")
                    telegram.send(f"📧 Day-{day} follow-up sent → {company} · {title}")
                except Exception:
                    log.error(f"  Follow-up email FAILED ({day}d): [{app['id']}]\n{traceback.format_exc()}")
                    # Do NOT set the timestamp — next run will retry
            else:
                # Form submission — no email to send, just mark as checked
                conn.execute(f"UPDATE applications SET {col}=? WHERE id=?",
                             (datetime.utcnow().isoformat(), app["id"]))
                log.info(f"  Follow-up ({day}d, form/skip): [{app['id']}] {title} @ {company}")

        conn.commit()
        conn.close()


def job_daily_digest():
    """Send a daily summary email with today's application stats."""
    import sqlite3
    from app.submission.email_sender import _get_service, _build_message
    import base64

    today = date.today().isoformat()
    conn = sqlite3.connect("data/jobs.db")
    conn.row_factory = sqlite3.Row

    applied_today = conn.execute(
        "SELECT COUNT(*) as c FROM applications WHERE date(submitted_at)=?", (today,)
    ).fetchone()["c"]

    replied = conn.execute(
        "SELECT COUNT(*) as c FROM applications WHERE status='replied'"
    ).fetchone()["c"]

    needs_review = conn.execute(
        "SELECT COUNT(*) as c FROM jobs WHERE status='needs_review'"
    ).fetchone()["c"]

    total_qualified = conn.execute(
        "SELECT COUNT(*) as c FROM jobs WHERE status='qualified'"
    ).fetchone()["c"]

    recent_apps = conn.execute("""
        SELECT j.title, j.company, a.submission_method, a.ats_score
        FROM applications a JOIN jobs j ON j.id = a.job_id
        WHERE date(a.submitted_at) = ?
        ORDER BY a.submitted_at DESC
    """, (today,)).fetchall()
    conn.close()

    if applied_today == 0 and not recent_apps:
        log.info("  Daily digest: nothing to report today, skipping")
        return

    lines = [
        f"Daily Job Automation Report — {today}",
        "",
        f"Applied today:    {applied_today}",
        f"Total replies:    {replied}",
        f"Needs review:     {needs_review}",
        f"Still qualified:  {total_qualified}",
        "",
    ]

    if recent_apps:
        lines.append("Today's applications:")
        for a in recent_apps:
            lines.append(f"  • {a['title']} @ {a['company']} ({a['submission_method']}, ATS {a['ats_score']}%)")

    body = "\n".join(lines)

    # Save to dashboard notifications
    from app.tracking.db import add_notification
    add_notification(title=f"Daily Report — {today}", body=body)

    # Also send via email
    try:
        service = _get_service()
        msg_bytes = (
            f"To: centyanita@gmail.com\n"
            f"From: centyanita@gmail.com\n"
            f"Subject: Job Automation Report — {today}\n\n"
            f"{body}"
        ).encode()
        raw = base64.urlsafe_b64encode(msg_bytes).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        log.info(f"  Daily digest sent: {applied_today} applications today")
    except Exception:
        log.error(f"  Daily digest email failed:\n{traceback.format_exc()}")

    from app.notifications import telegram
    telegram.send(
        f"📊 Daily Report — {today}\n"
        f"Applied today: {applied_today}\n"
        f"Total replies: {replied}\n"
        f"Needs review: {needs_review}\n"
        f"Still qualified: {total_qualified}"
    )


# ── Scheduler factory ──────────────────────────────────────────────────────────

def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Africa/Nairobi")

    # Scrape at 7am daily
    scheduler.add_job(
        lambda: _run("Scraper", job_scrape),
        CronTrigger(hour=7, minute=0),
        id="scrape", replace_existing=True,
    )
    # Score at 8am daily
    scheduler.add_job(
        lambda: _run("Scorer", job_score),
        CronTrigger(hour=8, minute=0),
        id="score", replace_existing=True,
    )
    # Generate CVs at 9am daily
    scheduler.add_job(
        lambda: _run("CV Generator", job_generate_cvs),
        CronTrigger(hour=9, minute=0),
        id="generate_cvs", replace_existing=True,
    )
    # Submit applications at 9:30am daily
    scheduler.add_job(
        lambda: _run("Submitter", job_submit),
        CronTrigger(hour=9, minute=30),
        id="submit", replace_existing=True,
    )
    # Detect Gmail replies every 6 hours
    scheduler.add_job(
        lambda: _run("Reply Detector", job_detect_replies),
        CronTrigger(hour="0,6,12,18", minute=0),
        id="detect_replies", replace_existing=True,
    )
    # Check follow-ups every 6 hours
    scheduler.add_job(
        lambda: _run("Follow-up Checker", job_check_followups),
        CronTrigger(hour="0,6,12,18", minute=15),
        id="followups", replace_existing=True,
    )
    # Daily digest at midnight
    scheduler.add_job(
        lambda: _run("Daily Digest", job_daily_digest),
        CronTrigger(hour=0, minute=0),
        id="daily_digest", replace_existing=True,
    )

    return scheduler

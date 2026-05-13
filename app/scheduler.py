"""Production scheduler — scrape 3× daily, score 30 min after each run.

Schedule (EAT = UTC+3):
  07:00 / 13:00 / 20:00  → Scrape all job boards
  07:30 / 13:30 / 20:30  → Score all new jobs
  On any failure         → Telegram alert
"""
import logging
import re
import traceback
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

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
    "Scorer":  "scoring",
}

_INTERVIEW_RE = re.compile(
    r'\b(interview|schedule|call|meet|availability|discuss)\b', re.IGNORECASE
)


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


def job_scrape():
    from app.scrapers.run_all import run_all_scrapers
    new = run_all_scrapers()
    log.info(f"  Scraped: {new} new jobs found")


def job_score():
    from app.ai.scorer import score_all
    score_all()


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Africa/Nairobi")

    # Scrape at 7am, 1pm, 8pm daily
    scheduler.add_job(
        lambda: _run("Scraper", job_scrape),
        CronTrigger(hour="7,13,20", minute=0),
        id="scrape", replace_existing=True,
    )
    # Score 30 min after each scrape
    scheduler.add_job(
        lambda: _run("Scorer", job_score),
        CronTrigger(hour="7,13,20", minute=30),
        id="score", replace_existing=True,
    )

    return scheduler

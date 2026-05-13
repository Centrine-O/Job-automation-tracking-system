# Manual Apply Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot from auto-submission to a job discovery + manual tracking system: scrape → score → show on dashboard → user applies manually → user tracks status.

**Architecture:** Remove cv/ and submission/ modules entirely. Simplify the scheduler to scrape 3×/day and score after each run. Add dismiss/apply/status-update API endpoints. Redesign the Queue page with a detail panel and the History page with clickable status pills. Add two new scrapers (MyJobMag Kenya, LinkedIn via SerpAPI).

**Tech Stack:** Python/FastAPI (backend), SQLite (DB), React/Vite/Tailwind (frontend), SerpAPI (LinkedIn), BeautifulSoup (MyJobMag).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/cv/` | **Delete** | CV generation (no longer needed) |
| `app/submission/` | **Delete** | Email/form submission (no longer needed) |
| `data/gmail_credentials.json` | **Delete if exists** | Gmail OAuth (no longer needed) |
| `data/gmail_token.json` | **Delete if exists** | Gmail OAuth (no longer needed) |
| `app/scheduler.py` | Modify | 3×/day scrape+score, remove 6 dead jobs |
| `app/tracking/db.py` | Modify | Add `dismiss_job()`, `create_manual_application()`, update `get_qualified_jobs()` |
| `app/dashboard/main.py` | Modify | Add 3 new endpoints, remove old submission endpoints, update `/api/stats` |
| `app/scrapers/myjobmag.py` | **Create** | MyJobMag Kenya HTML scraper |
| `app/scrapers/linkedin.py` | **Create** | LinkedIn Jobs via SerpAPI |
| `app/scrapers/run_all.py` | Modify | Register 2 new scrapers |
| `frontend/src/lib/api.js` | Modify | Add dismissJob, applyJob, updateStatus, updateNotes; remove old endpoints |
| `frontend/src/pages/Queue.jsx` | Rewrite | Job list + detail panel, Open/Apply/Dismiss actions |
| `frontend/src/pages/History.jsx` | Rewrite | Status pills + notes per application |
| `frontend/src/pages/Overview.jsx` | Modify | Update stats (remove submission stats, add dismissed) |
| `frontend/src/pages/System.jsx` | Modify | Remove submission pipeline stages |
| `tests/test_myjobmag.py` | **Create** | Unit tests for MyJobMag scraper |
| `tests/test_linkedin_scraper.py` | **Create** | Unit tests for LinkedIn scraper |

---

## Task 1: Remove dead modules and simplify scheduler

**Files:**
- Delete: `app/cv/` (entire directory)
- Delete: `app/submission/` (entire directory)
- Delete: `data/gmail_credentials.json` (if exists)
- Delete: `data/gmail_token.json` (if exists)
- Modify: `app/scheduler.py`

- [ ] **Step 1: Delete dead code**

```bash
rm -rf app/cv app/submission
rm -f data/gmail_credentials.json data/gmail_token.json
```

- [ ] **Step 2: Replace `app/scheduler.py` entirely**

```python
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
```

- [ ] **Step 3: Verify scheduler starts cleanly**

```bash
python -c "
from app.scheduler import build_scheduler
s = build_scheduler()
s.start()
for j in s.get_jobs():
    print(f'  {j.id}: {j.next_run_time}')
s.shutdown()
print('OK')
"
```

Expected: prints `scrape` and `score` jobs with next run times, then `OK`.

- [ ] **Step 4: Verify app still imports cleanly**

```bash
python -c "from app.dashboard.main import app; print('OK')"
```

Expected: `OK` (no ImportError from removed modules).

- [ ] **Step 5: Commit**

```bash
git add app/scheduler.py
git rm -r --cached app/cv app/submission 2>/dev/null || true
git add -A
git commit -m "feat: remove cv/submission modules, simplify scheduler to 3x/day scrape+score"
```

---

## Task 2: DB — add dismiss and manual apply functions

**Files:**
- Modify: `app/tracking/db.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db_pivot.py`:

```python
import sqlite3
import pytest
from unittest.mock import patch
from pathlib import Path


@pytest.fixture
def db(tmp_path, monkeypatch):
    """In-memory DB with schema."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("app.tracking.db.DB_PATH", db_file)
    from app.tracking import db as dbmod
    importlib.reload(dbmod)
    dbmod.init_db()
    return dbmod


import importlib


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
    # Manually set scores so they qualify
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_db_pivot.py -v
```

Expected: `ImportError` or `AttributeError` — `dismiss_job` and `create_manual_application` don't exist yet.

- [ ] **Step 3: Add functions to `app/tracking/db.py`**

Add after the existing `update_application_status` function:

```python
def dismiss_job(job_id: int) -> None:
    """Mark a job as dismissed — removes it from the Queue."""
    conn = get_connection()
    conn.execute("UPDATE jobs SET status='dismissed' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()


def create_manual_application(job_id: int) -> int:
    """Record that the user manually applied to a job. Returns the new application id."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO applications (job_id, submitted_at, status) VALUES (?, ?, 'applied')",
        (job_id, datetime.utcnow().isoformat()),
    )
    app_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return app_id
```

Also update `get_qualified_jobs()` to exclude dismissed. Find the function and replace its WHERE clause:

```python
def get_qualified_jobs():
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM jobs
        WHERE status = 'qualified'
        ORDER BY skill_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

(The `dismissed` status change already excludes them since dismissed jobs have `status='dismissed'`, not `'qualified'`.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_db_pivot.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tracking/db.py tests/test_db_pivot.py
git commit -m "feat: add dismiss_job and create_manual_application DB functions"
```

---

## Task 3: Backend API — new endpoints, remove old ones, update stats

**Files:**
- Modify: `app/dashboard/main.py`

- [ ] **Step 1: Add new API endpoints to `app/dashboard/main.py`**

Add these three endpoints after the existing `GET /api/queue` endpoint:

```python
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
def api_update_status(app_id: int, payload: dict):
    from app.tracking.db import update_application_status
    status = payload.get("status", "")
    allowed = {"applied", "replied", "offer", "rejected", "ghosted"}
    if status not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"status must be one of {allowed}")
    update_application_status(app_id, status)
    return {"ok": True}


@app.patch("/api/applications/{app_id}/notes")
def api_update_notes(app_id: int, payload: dict):
    import sqlite3
    notes = payload.get("notes", "")
    conn = sqlite3.connect("data/jobs.db")
    conn.execute("UPDATE applications SET notes=? WHERE id=?", (notes, app_id))
    conn.commit()
    conn.close()
    return {"ok": True}
```

- [ ] **Step 2: Update `/api/stats` to reflect the new model**

Replace the `api_stats` function body with:

```python
@app.get("/api/stats")
def api_stats():
    import sqlite3
    conn = sqlite3.connect("data/jobs.db")
    conn.row_factory = sqlite3.Row

    total_jobs     = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    qualified      = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='qualified'").fetchone()[0]
    dismissed      = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='dismissed'").fetchone()[0]
    total_applied  = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    replied        = conn.execute("SELECT COUNT(*) FROM applications WHERE status='replied'").fetchone()[0]
    offers         = conn.execute("SELECT COUNT(*) FROM applications WHERE status='offer'").fetchone()[0]
    conn.close()

    return {
        "total_jobs":    total_jobs,
        "qualified":     qualified,
        "dismissed":     dismissed,
        "total_applied": total_applied,
        "replied":       replied,
        "offers":        offers,
    }
```

- [ ] **Step 3: Update `/api/history` — remove old method filter, add notes**

Replace `api_history` with:

```python
@app.get("/api/history")
def api_history(status: str = ""):
    import sqlite3
    conn = sqlite3.connect("data/jobs.db")
    conn.row_factory = sqlite3.Row
    query = """
        SELECT a.id, a.job_id, a.status, a.submitted_at, a.notes,
               j.title, j.company, j.apply_url, j.source, j.skill_score
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        {}
        ORDER BY a.submitted_at DESC
    """
    if status:
        rows = conn.execute(
            query.format("WHERE a.status = ?"), (status,)
        ).fetchall()
    else:
        rows = conn.execute(query.format("")).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Remove old submission endpoints**

Delete these functions from `app/dashboard/main.py`:
- `re_trigger` (`@app.post("/apply/{job_id}")`)
- `mark_applied` (`@app.post("/mark-applied/{job_id}")`)
- `api_re_trigger` (`@app.post("/api/apply/{job_id}")`)
- `api_mark_applied` (`@app.post("/api/mark-applied/{job_id}")`)

- [ ] **Step 5: Verify API starts cleanly**

```bash
python -c "from app.dashboard.main import app; print('routes:', [r.path for r in app.routes])"
```

Expected: shows `/api/jobs/{job_id}/dismiss`, `/api/jobs/{job_id}/apply`, `/api/applications/{app_id}/status` in the list.

- [ ] **Step 6: Commit**

```bash
git add app/dashboard/main.py
git commit -m "feat: add dismiss/apply/status API endpoints, update stats and history"
```

---

## Task 4: MyJobMag Kenya scraper

**Files:**
- Create: `app/scrapers/myjobmag.py`
- Create: `tests/test_myjobmag.py`
- Modify: `app/scrapers/run_all.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_myjobmag.py`:

```python
from unittest.mock import patch, MagicMock
import pytest


SAMPLE_HTML = """
<html><body>
<div class="job-list-item">
  <h2 class="title"><a href="/job/123">Senior Python Developer</a></h2>
  <span class="company">Safaricom</span>
  <span class="location">Nairobi</span>
  <a class="apply-btn" href="https://myjobmag.co.ke/apply/123">Apply</a>
</div>
<div class="job-list-item">
  <h2 class="title"><a href="/job/456">Marketing Executive</a></h2>
  <span class="company">ACME</span>
  <span class="location">Mombasa</span>
  <a class="apply-btn" href="https://myjobmag.co.ke/apply/456">Apply</a>
</div>
</body></html>
"""


def test_run_returns_count():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("app.scrapers.myjobmag.requests.get", return_value=mock_resp), \
         patch("app.scrapers.myjobmag.insert_job", return_value=1) as mock_insert:
        from app.scrapers import myjobmag
        count = myjobmag.run()
        assert count >= 0
        assert mock_insert.called


def test_irrelevant_jobs_skipped():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("app.scrapers.myjobmag.requests.get", return_value=mock_resp), \
         patch("app.scrapers.myjobmag.insert_job", return_value=1) as mock_insert:
        from app.scrapers import myjobmag
        myjobmag.run()
        # "Marketing Executive" should NOT be inserted
        calls = [str(c) for c in mock_insert.call_args_list]
        assert not any("Marketing" in c for c in calls)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_myjobmag.py -v
```

Expected: `ImportError: No module named 'app.scrapers.myjobmag'`

- [ ] **Step 3: Create `app/scrapers/myjobmag.py`**

```python
import hashlib
import requests
from bs4 import BeautifulSoup
from app.tracking.db import insert_job

BASE_URL = "https://www.myjobmag.co.ke"
LISTINGS_URL = f"{BASE_URL}/jobs-in-kenya"

RELEVANT_KEYWORDS = [
    "python", "data analyst", "data engineer", "software engineer",
    "software developer", "automation", "ai", "machine learning",
    "backend", "full stack", "fullstack", "api", "sql", "developer",
]

PAGES = 3


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title):
    return any(kw in title.lower() for kw in RELEVANT_KEYWORDS)


def run():
    """Scrape MyJobMag Kenya and save relevant jobs to DB."""
    print("Starting MyJobMag scraper...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for page in range(1, PAGES + 1):
        url = f"{LISTINGS_URL}?page={page}"
        print(f"  Fetching page {page}: {url}")
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
        except Exception as e:
            print(f"  Error fetching page {page}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".job-list-item, .job_listing, article.job_listing")

        if not items:
            # fallback: try generic job link pattern
            items = soup.find_all("li", class_=lambda c: c and "job" in c.lower())

        print(f"  Found {len(items)} listings")

        for item in items:
            title_tag = item.find(["h2", "h3", "h4"]) or item.find(class_=lambda c: c and "title" in str(c).lower())
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)

            if not is_relevant(title):
                total_skipped += 1
                continue

            company_tag = item.find(class_=lambda c: c and "company" in str(c).lower())
            company = company_tag.get_text(strip=True) if company_tag else "Unknown"

            location_tag = item.find(class_=lambda c: c and "location" in str(c).lower())
            location = location_tag.get_text(strip=True) if location_tag else "Kenya"

            link_tag = title_tag.find("a") or item.find("a", href=True)
            if not link_tag:
                continue
            href = link_tag.get("href", "")
            job_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            jd_hash = make_hash(title, company, job_url)

            job_id = insert_job(
                source="myjobmag",
                title=title,
                company=company,
                location=location,
                remote_type="onsite",
                apply_method="form",
                apply_url=job_url,
                jd_url=job_url,
                jd_text="",
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {title} @ {company}")
                total_new += 1
            else:
                total_dupes += 1

    print(f"\nMyJobMag done: {total_new} new, {total_dupes} dupes, {total_skipped} irrelevant")
    return total_new


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_myjobmag.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Register in `run_all.py`**

Open `app/scrapers/run_all.py` and add the import and call:

```python
from app.scrapers import myjobmag
```

And inside `run_all_scrapers()`, add:

```python
    try:
        total += myjobmag.run()
    except Exception:
        import traceback
        log.error(f"MyJobMag scraper failed:\n{traceback.format_exc()}")
```

- [ ] **Step 6: Commit**

```bash
git add app/scrapers/myjobmag.py app/scrapers/run_all.py tests/test_myjobmag.py
git commit -m "feat: add MyJobMag Kenya scraper"
```

---

## Task 5: LinkedIn Jobs scraper via SerpAPI

**Files:**
- Create: `app/scrapers/linkedin.py`
- Create: `tests/test_linkedin_scraper.py`
- Modify: `app/scrapers/run_all.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_linkedin_scraper.py`:

```python
from unittest.mock import patch, MagicMock
import pytest


SAMPLE_RESPONSE = {
    "jobs_results": [
        {
            "title": "Senior Data Engineer",
            "company_name": "Safaricom",
            "location": "Nairobi, Kenya",
            "description": "We need a Python data engineer with 5+ years experience...",
            "apply_options": [{"link": "https://linkedin.com/jobs/view/123"}],
            "job_id": "linkedin_123",
        },
        {
            "title": "Sales Manager",
            "company_name": "ACME",
            "location": "Nairobi",
            "description": "Looking for a sales manager...",
            "apply_options": [{"link": "https://linkedin.com/jobs/view/456"}],
            "job_id": "linkedin_456",
        },
    ]
}


def test_run_returns_count():
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    mock_settings = MagicMock()
    mock_settings.serpapi_key = "TESTKEY"

    with patch("app.scrapers.linkedin.requests.get", return_value=mock_resp), \
         patch("app.scrapers.linkedin.settings", mock_settings), \
         patch("app.scrapers.linkedin.insert_job", return_value=1) as mock_insert:
        from app.scrapers import linkedin
        count = linkedin.run()
        assert count >= 0
        assert mock_insert.called


def test_irrelevant_jobs_skipped():
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    mock_settings = MagicMock()
    mock_settings.serpapi_key = "TESTKEY"

    with patch("app.scrapers.linkedin.requests.get", return_value=mock_resp), \
         patch("app.scrapers.linkedin.settings", mock_settings), \
         patch("app.scrapers.linkedin.insert_job", return_value=1) as mock_insert:
        from app.scrapers import linkedin
        linkedin.run()
        calls = [str(c) for c in mock_insert.call_args_list]
        assert not any("Sales Manager" in c for c in calls)


def test_skips_when_no_key():
    mock_settings = MagicMock()
    mock_settings.serpapi_key = ""

    with patch("app.scrapers.linkedin.settings", mock_settings), \
         patch("app.scrapers.linkedin.requests.get") as mock_get:
        from app.scrapers import linkedin
        count = linkedin.run()
        assert count == 0
        assert not mock_get.called
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
venv/bin/python -m pytest tests/test_linkedin_scraper.py -v
```

Expected: `ImportError: No module named 'app.scrapers.linkedin'`

- [ ] **Step 3: Create `app/scrapers/linkedin.py`**

```python
import hashlib
import requests
from app.tracking.db import insert_job
from app.config import settings

SERPAPI_URL = "https://serpapi.com/search"

SEARCH_QUERIES = [
    "software engineer Kenya",
    "data analyst Nairobi",
    "python developer Kenya",
    "data engineer remote Kenya",
    "backend engineer Kenya",
    "full stack developer Nairobi",
]

RELEVANT_KEYWORDS = [
    "python", "data analyst", "data engineer", "software engineer",
    "software developer", "automation", "ai", "machine learning",
    "backend", "full stack", "fullstack", "api", "sql",
]


def make_hash(title, company, url):
    raw = f"{title.lower().strip()}{company.lower().strip()}{url.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_relevant(title, description):
    searchable = (title + " " + description).lower()
    return any(kw in searchable for kw in RELEVANT_KEYWORDS)


def run():
    """Fetch LinkedIn jobs via SerpAPI and save to DB."""
    if not settings.serpapi_key:
        print("SerpAPI key not set — skipping LinkedIn scraper.")
        return 0

    print("Starting LinkedIn scraper (SerpAPI)...")
    total_new = 0
    total_dupes = 0
    total_skipped = 0

    for query in SEARCH_QUERIES:
        print(f"  Searching: {query}")
        try:
            resp = requests.get(
                SERPAPI_URL,
                params={
                    "engine": "linkedin_jobs",
                    "q": query,
                    "api_key": settings.serpapi_key,
                    "num": 10,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs_raw = data.get("jobs_results", [])
            print(f"  Found {len(jobs_raw)} results")
        except Exception as e:
            print(f"  Error fetching '{query}': {e}")
            continue

        for job in jobs_raw:
            title = (job.get("title") or "").strip()
            company = (job.get("company_name") or "").strip()
            location = (job.get("location") or "Kenya").strip()
            description = (job.get("description") or "").strip()

            apply_options = job.get("apply_options", [])
            apply_link = apply_options[0].get("link") if apply_options else None
            job_url = apply_link or f"https://www.linkedin.com/jobs/search?q={job.get('job_id','')}"

            if not is_relevant(title, description):
                total_skipped += 1
                continue

            jd_hash = make_hash(title, company, job_url)

            job_id = insert_job(
                source="linkedin",
                title=title,
                company=company,
                location=location,
                remote_type="remote" if "remote" in location.lower() else "onsite",
                apply_method="form",
                apply_url=job_url,
                jd_url=job_url,
                jd_text=description,
                jd_hash=jd_hash,
            )

            if job_id:
                print(f"    + Saved: {title} @ {company}")
                total_new += 1
            else:
                total_dupes += 1

    print(f"\nLinkedIn done: {total_new} new, {total_dupes} dupes, {total_skipped} irrelevant")
    return total_new


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
venv/bin/python -m pytest tests/test_linkedin_scraper.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Register in `run_all.py`**

Add to `app/scrapers/run_all.py`:

```python
from app.scrapers import linkedin
```

And in `run_all_scrapers()`:

```python
    try:
        total += linkedin.run()
    except Exception:
        import traceback
        log.error(f"LinkedIn scraper failed:\n{traceback.format_exc()}")
```

- [ ] **Step 6: Commit**

```bash
git add app/scrapers/linkedin.py app/scrapers/run_all.py tests/test_linkedin_scraper.py
git commit -m "feat: add LinkedIn Jobs scraper via SerpAPI"
```

---

## Task 6: Frontend — update api.js and Queue page

**Files:**
- Modify: `frontend/src/lib/api.js`
- Rewrite: `frontend/src/pages/Queue.jsx`

- [ ] **Step 1: Replace `frontend/src/lib/api.js`**

```js
export const getStats        = () => fetch('/api/stats').then(r => r.json())
export const getQueue        = () => fetch('/api/queue').then(r => r.json())
export const getHistory      = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return fetch(`/api/history${qs ? '?' + qs : ''}`).then(r => r.json())
}
export const getApplications = () => fetch('/api/applications').then(r => r.json())
export const getNotifications = () => fetch('/api/notifications').then(r => r.json())
export const getUnreadCount  = () => fetch('/api/unread-count').then(r => r.json())
export const runNow          = () => fetch('/api/run-now', { method: 'POST' }).then(r => r.json())
export const getSystemStatus = () => fetch('/api/system/status').then(r => r.json())
export const getSystemHealth = () => fetch('/api/system/health').then(r => r.json())

export const dismissJob      = (id) =>
  fetch(`/api/jobs/${id}/dismiss`, { method: 'POST' }).then(r => r.json())

export const applyJob        = (id) =>
  fetch(`/api/jobs/${id}/apply`, { method: 'POST' }).then(r => r.json())

export const updateStatus    = (appId, status) =>
  fetch(`/api/applications/${appId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }).then(r => r.json())

export const updateNotes     = (appId, notes) =>
  fetch(`/api/applications/${appId}/notes`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  }).then(r => r.json())
```

- [ ] **Step 2: Rewrite `frontend/src/pages/Queue.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { getQueue, dismissJob, applyJob } from '@/lib/api'

export default function Queue() {
  const [jobs, setJobs]         = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getQueue()
      .then(data => { setJobs(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  function removeJob(id) {
    setJobs(prev => prev.filter(j => j.id !== id))
    if (selected?.id === id) setSelected(null)
  }

  async function handleDismiss(job) {
    await dismissJob(job.id)
    removeJob(job.id)
  }

  async function handleApply(job) {
    await applyJob(job.id)
    removeJob(job.id)
  }

  if (loading) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>
  if (error)   return <p className="font-serif text-red-600">{error}</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-3xl font-bold text-onyx">Review Queue</h1>
        <span className="font-mono text-xs text-onyx-dim">{jobs.length} qualified</span>
      </div>

      {jobs.length === 0 ? (
        <div className="bg-white rounded-lg border border-bone-2 p-12 text-center">
          <p className="font-serif text-xl text-onyx-dim">Queue is clear.</p>
          <p className="font-mono text-xs text-onyx-dim/60 mt-2">Check back after the next scrape.</p>
        </div>
      ) : (
        <div className="flex gap-4 h-[calc(100vh-160px)]">

          {/* Job list */}
          <div className="w-80 flex-shrink-0 overflow-y-auto space-y-2 pr-1">
            {jobs.map(job => (
              <button
                key={job.id}
                onClick={() => setSelected(job)}
                className={`w-full text-left rounded-lg border px-4 py-3 transition-colors ${
                  selected?.id === job.id
                    ? 'border-olive bg-olive/5'
                    : 'border-bone-2 bg-white hover:border-bone-3'
                }`}
              >
                <p className="font-serif text-sm font-semibold text-onyx leading-tight truncate">{job.title}</p>
                <p className="font-mono text-xs text-onyx-dim mt-0.5 truncate">{job.company}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="font-mono text-[10px] bg-olive/10 text-olive px-1.5 py-0.5 rounded">
                    {job.skill_score}%
                  </span>
                  {job.remote_type && (
                    <span className="font-mono text-[10px] text-onyx-dim/60">{job.remote_type}</span>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Detail panel */}
          <div className="flex-1 overflow-y-auto">
            {selected ? (
              <div className="bg-white rounded-lg border border-bone-2 p-6 space-y-5">
                <div>
                  <h2 className="font-serif text-2xl font-bold text-onyx">{selected.title}</h2>
                  <p className="font-mono text-sm text-onyx-dim mt-1">
                    {selected.company}
                    {selected.location ? ` · ${selected.location}` : ''}
                    {selected.salary_range ? ` · ${selected.salary_range}` : ''}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="font-mono text-xs bg-olive/10 text-olive border border-olive/20 px-2 py-0.5 rounded">
                      Score {selected.skill_score}%
                    </span>
                    <span className="font-mono text-xs text-onyx-dim/60 uppercase tracking-wide">
                      {selected.source}
                    </span>
                  </div>
                </div>

                {selected.jd_text && (
                  <div>
                    <p className="font-mono text-[10px] text-onyx-dim/60 uppercase tracking-widest mb-2">Description</p>
                    <p className="font-mono text-xs text-onyx-dim leading-relaxed line-clamp-6">
                      {selected.jd_text.slice(0, 400)}{selected.jd_text.length > 400 ? '…' : ''}
                    </p>
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  {selected.apply_url && (
                    <a
                      href={selected.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs bg-olive text-bone px-4 py-2 rounded border border-olive hover:bg-olive/90 transition-colors"
                    >
                      Open Job ↗
                    </a>
                  )}
                  <button
                    onClick={() => handleApply(selected)}
                    className="font-mono text-xs bg-onyx text-bone px-4 py-2 rounded border border-onyx hover:bg-onyx/90 transition-colors"
                  >
                    Mark Applied ✓
                  </button>
                  <button
                    onClick={() => handleDismiss(selected)}
                    className="font-mono text-xs text-onyx-dim px-4 py-2 rounded border border-bone-2 hover:border-onyx-dim hover:text-onyx transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-bone-2 p-12 text-center h-full flex items-center justify-center">
                <p className="font-mono text-xs text-onyx-dim/60">Select a job to review</p>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Build frontend and verify no errors**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in ...s` with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.js frontend/src/pages/Queue.jsx
git add -f frontend/dist/
git commit -m "feat: redesign Queue page with detail panel, Open/Apply/Dismiss actions"
```

---

## Task 7: Frontend — History page with status pills and notes

**Files:**
- Rewrite: `frontend/src/pages/History.jsx`

- [ ] **Step 1: Rewrite `frontend/src/pages/History.jsx`**

```jsx
import { useState, useEffect, useCallback } from 'react'
import { getHistory, updateStatus, updateNotes } from '@/lib/api'

const STATUSES = ['applied', 'replied', 'offer', 'rejected', 'ghosted']

const STATUS_STYLES = {
  applied:  'bg-bone-1 text-onyx-dim border-bone-2',
  replied:  'bg-amber-50 text-amber-700 border-amber-200',
  offer:    'bg-olive/10 text-olive border-olive/30',
  rejected: 'bg-red-50 text-red-600 border-red-200',
  ghosted:  'bg-gray-50 text-gray-400 border-gray-200',
}

function StatusPills({ appId, current, onChange }) {
  const [saving, setSaving] = useState(false)

  async function handleClick(status) {
    if (status === current || saving) return
    setSaving(true)
    await updateStatus(appId, status)
    onChange(appId, status)
    setSaving(false)
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {STATUSES.map(s => (
        <button
          key={s}
          onClick={() => handleClick(s)}
          disabled={saving}
          className={`font-mono text-[10px] px-2 py-1 rounded border transition-colors capitalize ${
            s === current
              ? STATUS_STYLES[s] + ' font-semibold'
              : 'bg-white text-onyx-dim/40 border-bone-1 hover:border-bone-3 hover:text-onyx-dim'
          }`}
        >
          {s}
        </button>
      ))}
    </div>
  )
}

function NotesField({ appId, initial }) {
  const [notes, setNotes] = useState(initial || '')
  const [saved, setSaved] = useState(false)

  async function handleBlur() {
    await updateNotes(appId, notes)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={notes}
        onChange={e => setNotes(e.target.value)}
        onBlur={handleBlur}
        placeholder="Add notes…"
        className="w-full font-mono text-xs text-onyx-dim bg-transparent border-b border-bone-1 focus:border-onyx-dim outline-none py-0.5 placeholder:text-onyx-dim/30"
      />
      {saved && <span className="absolute right-0 top-0 font-mono text-[9px] text-olive">saved</span>}
    </div>
  )
}

export default function History() {
  const [rows, setRows]     = useState([])
  const [statusF, setStatusF] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    getHistory()
      .then(data => { setRows(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const handleStatusChange = useCallback((appId, newStatus) => {
    setRows(prev => prev.map(r => r.id === appId ? { ...r, status: newStatus } : r))
  }, [])

  const filtered = statusF === 'all' ? rows : rows.filter(r => r.status === statusF)

  const btnBase   = 'font-mono text-xs px-3 py-1.5 rounded border transition-colors'
  const btnActive = `${btnBase} bg-onyx text-bone border-onyx`
  const btnIdle   = `${btnBase} border-bone-2 text-onyx-dim hover:border-onyx hover:text-onyx`

  if (loading) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>
  if (error)   return <p className="font-serif text-red-600">{error}</p>

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-3xl font-bold text-onyx">History</h1>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setStatusF('all')} className={statusF === 'all' ? btnActive : btnIdle}>All</button>
        {STATUSES.map(s => (
          <button key={s} onClick={() => setStatusF(statusF === s ? 'all' : s)}
            className={statusF === s ? btnActive : btnIdle}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      <p className="font-mono text-xs text-onyx-dim">
        {filtered.length} record{filtered.length !== 1 ? 's' : ''}
        {statusF !== 'all' ? ' (filtered)' : ''}
      </p>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-lg border border-bone-2 p-12 text-center">
          <p className="font-serif text-xl text-onyx-dim">No applications yet.</p>
          <p className="font-mono text-xs text-onyx-dim/60 mt-2">Mark jobs as applied from the Queue.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(row => (
            <div key={row.id} className="bg-white rounded-lg border border-bone-2 px-5 py-4 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-serif text-base font-semibold text-onyx">{row.title}</p>
                  <p className="font-mono text-xs text-onyx-dim mt-0.5">
                    {row.company}
                    {row.submitted_at ? ` · applied ${row.submitted_at.slice(0, 10)}` : ''}
                  </p>
                </div>
                {row.apply_url && (
                  <a
                    href={row.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-[10px] text-onyx-dim/50 hover:text-olive transition-colors flex-shrink-0"
                  >
                    Open ↗
                  </a>
                )}
              </div>
              <StatusPills appId={row.id} current={row.status} onChange={handleStatusChange} />
              <NotesField appId={row.id} initial={row.notes} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Build frontend**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in ...s`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/History.jsx
git add -f frontend/dist/
git commit -m "feat: rewrite History page with status pills and inline notes"
```

---

## Task 8: Frontend — Overview and System page cleanup

**Files:**
- Modify: `frontend/src/pages/Overview.jsx`
- Modify: `frontend/src/pages/System.jsx`

- [ ] **Step 1: Update `frontend/src/pages/Overview.jsx`**

Replace the full file:

```jsx
import { useState, useEffect } from 'react'
import StatCard from '@/components/StatCard'
import { getStats, getHistory } from '@/lib/api'

export default function Overview() {
  const [stats, setStats] = useState(null)
  const [apps, setApps]   = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getStats(), getHistory()])
      .then(([s, a]) => { setStats(s); setApps(a) })
      .catch(e => setError(e.message))
  }, [])

  if (error)  return <p className="font-serif text-red-600">{error}</p>
  if (!stats) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>

  const recent = apps.slice(0, 5)

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-3xl font-bold text-onyx">Overview</h1>

      <div className="grid grid-cols-6 gap-3">
        <StatCard label="Scraped"   value={stats.total_jobs}    index={0} />
        <StatCard label="Qualified" value={stats.qualified}     index={1} accent />
        <StatCard label="Applied"   value={stats.total_applied} index={2} />
        <StatCard label="Replied"   value={stats.replied}       index={3} />
        <StatCard label="Offers"    value={stats.offers}        index={4} />
        <StatCard label="Dismissed" value={stats.dismissed}     index={5} />
      </div>

      {recent.length > 0 && (
        <div>
          <h2 className="font-serif text-xl font-semibold text-onyx mb-3">Recent Applications</h2>
          <div className="space-y-2">
            {recent.map(row => (
              <div key={row.id} className="bg-white rounded-lg border border-bone-2 px-4 py-3 flex items-center justify-between">
                <div>
                  <p className="font-serif text-sm font-semibold text-onyx">{row.title}</p>
                  <p className="font-mono text-xs text-onyx-dim">{row.company}</p>
                </div>
                <span className={`font-mono text-[10px] px-2 py-1 rounded border capitalize
                  ${row.status === 'replied' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                    row.status === 'offer'   ? 'bg-olive/10 text-olive border-olive/30' :
                    'bg-bone-1 text-onyx-dim border-bone-2'}`}>
                  {row.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Update `STAGE_LABELS` and `PIPELINE_STEPS` in `frontend/src/pages/System.jsx`**

Replace the two constants at the top of the file:

```js
const STAGE_LABELS = {
  idle:     'Idle',
  scraping: 'Scraping Jobs',
  scoring:  'Scoring Jobs',
}

const PIPELINE_STEPS = [
  { key: 'scraping', label: 'Scrape' },
  { key: 'scoring',  label: 'Score' },
]
```

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: `✓ built in ...s`

- [ ] **Step 4: Run full test suite**

```bash
venv/bin/python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests PASS.

- [ ] **Step 5: Final commit**

```bash
git add frontend/src/pages/Overview.jsx frontend/src/pages/System.jsx
git add -f frontend/dist/
git commit -m "feat: update Overview stats and simplify System pipeline to scrape+score"
```

---

## Self-Review

**Spec coverage:**
- ✅ Remove cv/, submission/, Gmail — Task 1
- ✅ Scheduler 3×/day scrape+score — Task 1
- ✅ Telegram error alerts only — Task 1 (`_run()` kept unchanged)
- ✅ `dismiss_job()` DB function — Task 2
- ✅ `create_manual_application()` DB function — Task 2
- ✅ `dismissed` excludes from qualified queue — Task 2
- ✅ `POST /api/jobs/{id}/dismiss` — Task 3
- ✅ `POST /api/jobs/{id}/apply` — Task 3
- ✅ `PATCH /api/applications/{id}/status` — Task 3
- ✅ `PATCH /api/applications/{id}/notes` — Task 3
- ✅ Updated `/api/stats` — Task 3
- ✅ Updated `/api/history` (with notes) — Task 3
- ✅ Removed old submission endpoints — Task 3
- ✅ MyJobMag Kenya scraper — Task 4
- ✅ LinkedIn via SerpAPI — Task 5
- ✅ Queue page: job list + detail panel — Task 6
- ✅ Queue page: Open Job ↗ button — Task 6
- ✅ Queue page: Mark Applied button — Task 6
- ✅ Queue page: Dismiss button — Task 6
- ✅ History page: status pills (applied/replied/offer/rejected/ghosted) — Task 7
- ✅ History page: inline notes — Task 7
- ✅ Overview stats updated — Task 8
- ✅ System page simplified pipeline — Task 8

**Type consistency:** `updateStatus(appId, status)` in api.js matches `PATCH /api/applications/{app_id}/status` in backend. `applyJob(id)` → `POST /api/jobs/{id}/apply`. All consistent.

**Notes column:** Already exists in DB schema from Phase 8 — no migration needed.

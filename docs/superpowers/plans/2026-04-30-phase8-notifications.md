# Phase 8 — Notifications & Follow-up Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Telegram alerts for pipeline errors, interview replies, and daily digests; add automated Day-21/30 follow-up emails and Day-45 ghosted detection — all in pure Python, no new services.

**Architecture:** A new `app/notifications/telegram.py` module wraps the Telegram Bot API using only `urllib`. It is imported by `app/scheduler.py` which gains one new function (`job_mark_ghosted`) and five modified functions. Config gets two new fields read from `.env`.

**Tech Stack:** Python stdlib (`urllib.request`), existing Gmail API (`app/submission/email_sender.py`), APScheduler (already running), SQLite (already running).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/notifications/__init__.py` | Create | Package marker |
| `app/notifications/telegram.py` | Create | `send(text)` and `alert(text)` — sole point of contact with Telegram Bot API |
| `app/config.py` | Modify | Add `telegram_bot_token` and `telegram_chat_id` fields |
| `app/scheduler.py` | Modify | Wire Telegram into `_run()`, `job_detect_replies()`, `job_daily_digest()`, `job_check_followups()`; add `job_mark_ghosted()`; register new cron job |

---

## Task 1: Telegram notifier module

**Files:**
- Create: `app/notifications/__init__.py`
- Create: `app/notifications/telegram.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Create the package and write the failing test**

```bash
mkdir -p app/notifications tests
touch app/notifications/__init__.py
```

Create `tests/test_telegram.py`:

```python
from unittest.mock import patch, MagicMock
import pytest


def test_send_calls_telegram_api():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TOKEN"
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen") as mock_open, \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.send("hello")
        assert mock_open.called
        req = mock_open.call_args[0][0]
        assert "TOKEN" in req.full_url
        assert b"hello" in req.data


def test_send_silent_on_error():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TOKEN"
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen", side_effect=Exception("network error")), \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.send("hello")  # must not raise


def test_send_skips_when_no_token():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = ""
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen") as mock_open, \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.send("hello")
        assert not mock_open.called


def test_alert_prepends_emoji():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TOKEN"
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen") as mock_open, \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.alert("pipeline down")
        req = mock_open.call_args[0][0]
        assert "🚨" in req.data.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_telegram.py -v
```

Expected: `ImportError: No module named 'app.notifications.telegram'`

- [ ] **Step 3: Write `app/notifications/telegram.py`**

```python
"""Telegram Bot API notifications. Uses urllib only — no extra dependencies."""
import logging
import urllib.parse
import urllib.request

from app.config import settings

log = logging.getLogger("telegram")


def send(text: str) -> None:
    """Send a message to the configured Telegram chat. Silently fails on error."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        log.debug("Telegram not configured — skipping notification")
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        log.warning(f"Telegram send failed: {exc}")


def alert(text: str) -> None:
    """Send an urgent alert — prepends 🚨."""
    send(f"🚨 {text}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_telegram.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Smoke-test against real Telegram**

```bash
python -c "
from app.notifications import telegram
telegram.send('✅ Phase 8 test — notifications module loaded correctly')
"
```

Expected: Message arrives in the Telegram bot chat within a few seconds.

- [ ] **Step 6: Commit**

```bash
git add app/notifications/__init__.py app/notifications/telegram.py tests/test_telegram.py
git commit -m "feat: add Telegram notifier module (app/notifications/telegram.py)"
```

---

## Task 2: Add Telegram credentials to config

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Open `app/config.py` and add two fields**

Current file ends with:
```python
    # Mode
    dry_run: bool = True


settings = Settings()
```

Add the two new fields inside the `Settings` class, before `dry_run`:

```python
    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Mode
    dry_run: bool = True
```

- [ ] **Step 2: Verify config loads both values from `.env`**

```bash
python -c "
from app.config import settings
print('token:', settings.telegram_bot_token[:10], '...')
print('chat_id:', settings.telegram_chat_id)
"
```

Expected: Prints the first 10 chars of the token and the numeric chat ID.

- [ ] **Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat: add telegram_bot_token and telegram_chat_id to config"
```

---

## Task 3: Pipeline error alerts — wire into `_run()`

**Files:**
- Modify: `app/scheduler.py` (the `_run` function, lines 39–58)

- [ ] **Step 1: Update `_run()` in `app/scheduler.py`**

Replace the current `_run` function:

```python
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
```

- [ ] **Step 2: Verify by triggering a deliberate failure**

```bash
python -c "
from app.scheduler import _run
_run('Test Stage', lambda: (_ for _ in ()).throw(RuntimeError('deliberate test error')))
"
```

Expected: Error logged to console AND a 🚨 Telegram message arrives: `🚨 Test Stage failed: RuntimeError: deliberate test error`

- [ ] **Step 3: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: Telegram alert on pipeline stage failure"
```

---

## Task 4: Daily digest Telegram summary

**Files:**
- Modify: `app/scheduler.py` (the `job_daily_digest` function)

- [ ] **Step 1: Find `job_daily_digest()` in `app/scheduler.py`**

The function ends with a try/except that sends the email. After the `except Exception` block, add the Telegram send. The full updated function:

```python
def job_daily_digest():
    """Send a daily summary email with today's application stats."""
    import sqlite3
    from app.submission.email_sender import _get_service, _build_message
    from app.notifications import telegram
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

    from app.tracking.db import add_notification
    add_notification(title=f"Daily Report — {today}", body=body)

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

    telegram.send(
        f"📊 Daily Report — {today}\n"
        f"Applied today: {applied_today}\n"
        f"Total replies: {replied}\n"
        f"Needs review: {needs_review}\n"
        f"Still qualified: {total_qualified}"
    )
```

- [ ] **Step 2: Test the digest fires a Telegram message**

```bash
python -c "
from app.scheduler import job_daily_digest
job_daily_digest()
"
```

Expected: Telegram message arrives with today's counts. (If `applied_today == 0` it returns early — that's correct.)

- [ ] **Step 3: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: send daily digest summary to Telegram"
```

---

## Task 5: Interview keyword alert in reply detection

**Files:**
- Modify: `app/scheduler.py` (the `job_detect_replies` function)

- [ ] **Step 1: Add `INTERVIEW_KEYWORDS` constant near the top of `app/scheduler.py`**

Add this after the `_STAGE_KEYS` dict (around line 55):

```python
_INTERVIEW_KEYWORDS = {"interview", "schedule", "call", "meet", "availability", "discuss"}
```

- [ ] **Step 2: Update `job_detect_replies()` to alert on interview replies**

Replace the current `job_detect_replies` function:

```python
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
```

- [ ] **Step 3: Verify the keyword set covers the main cases**

```bash
python -c "
from app.scheduler import _INTERVIEW_KEYWORDS
test_snippets = [
    'We would like to schedule an interview with you',
    'Can we set up a call to discuss your application?',
    'Please let us know your availability for a meeting',
    'Thank you for applying — we will review your CV',
]
for s in test_snippets:
    hit = any(kw in s.lower() for kw in _INTERVIEW_KEYWORDS)
    print(f'  [{\"HIT\" if hit else \"miss\"}] {s[:50]}')
"
```

Expected:
```
  [HIT] We would like to schedule an interview with you
  [HIT] Can we set up a call to discuss your applicati
  [HIT] Please let us know your availability for a mee
  [miss] Thank you for applying — we will review your C
```

- [ ] **Step 4: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: Telegram alert on interview keyword detected in Gmail reply"
```

---

## Task 6: Follow-up emails at Day 21 and Day 30

**Files:**
- Modify: `app/scheduler.py` (the `job_check_followups` function)

- [ ] **Step 1: Replace `job_check_followups()` in `app/scheduler.py`**

```python
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
```

- [ ] **Step 2: Verify the function loads without error**

```bash
python -c "from app.scheduler import job_check_followups; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Check which applications would be affected right now**

```bash
python -c "
from app.tracking.db import get_applications_due_followup
for day in (21, 30):
    due = get_applications_due_followup(day)
    print(f'Day {day}: {len(due)} due')
    for a in due:
        print(f'  [{a[\"id\"]}] {a.get(\"title\")} @ {a.get(\"company\")} — method: {a.get(\"submission_method\")}')
"
```

Expected: Lists any applications past their follow-up window. Currently likely 0 since the system just went live.

- [ ] **Step 4: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: send Day-21 and Day-30 follow-up emails with Telegram confirmation"
```

---

## Task 7: Ghosted detection at Day 45

**Files:**
- Modify: `app/scheduler.py` (add `job_mark_ghosted` function; update `_STAGE_KEYS` and `build_scheduler`)

- [ ] **Step 1: Add `"Ghosted Detector"` to `_STAGE_KEYS`**

Find `_STAGE_KEYS` in `app/scheduler.py` and add one entry:

```python
_STAGE_KEYS = {
    "Scraper":          "scraping",
    "Scorer":           "scoring",
    "CV Generator":     "generating_cvs",
    "Submitter":        "submitting",
    "Reply Detector":   "detecting_replies",
    "Follow-up Checker":"checking_followups",
    "Daily Digest":     "sending_digest",
    "Ghosted Detector": "marking_ghosted",       # ← add this line
}
```

- [ ] **Step 2: Add `job_mark_ghosted()` function to `app/scheduler.py`**

Add this function after `job_check_followups()`:

```python
def job_mark_ghosted():
    """Mark applications with no reply after 45 days as ghosted."""
    from app.tracking.db import get_connection
    from app.notifications import telegram

    conn = get_connection()
    rows = conn.execute("""
        SELECT a.id, j.title, j.company
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.status = 'applied'
          AND julianday('now') - julianday(a.submitted_at) >= 45
    """).fetchall()

    count = 0
    for row in rows:
        conn.execute(
            "UPDATE applications SET status='ghosted', ghosted_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), row["id"])
        )
        log.info(f"  Ghosted: [{row['id']}] {row['title']} @ {row['company']}")
        telegram.send(f"👻 Ghosted — {row['company']} · {row['title']} (45 days, no reply)")
        count += 1

    conn.commit()
    conn.close()
    if count:
        log.info(f"  Ghosted {count} application(s)")
```

- [ ] **Step 3: Register `job_mark_ghosted` in `build_scheduler()`**

Find `build_scheduler()` and add a new `scheduler.add_job` call before the `return scheduler` line:

```python
    # Mark ghosted at Day 45 — runs every 6h at :30
    scheduler.add_job(
        lambda: _run("Ghosted Detector", job_mark_ghosted),
        CronTrigger(hour="0,6,12,18", minute=30),
        id="mark_ghosted", replace_existing=True,
    )
```

- [ ] **Step 4: Verify the scheduler starts cleanly with the new job**

```bash
python -c "
from app.scheduler import build_scheduler
s = build_scheduler()
s.start()
jobs = {j.id: j.next_run_time for j in s.get_jobs()}
for jid, t in jobs.items():
    print(f'  {jid}: {t}')
s.shutdown()
"
```

Expected: `mark_ghosted` appears in the list with a next run time.

- [ ] **Step 5: Verify the ghosted query logic**

```bash
python -c "
from app.tracking.db import get_connection
conn = get_connection()
rows = conn.execute('''
    SELECT a.id, j.title, j.company,
           julianday(\"now\") - julianday(a.submitted_at) as days_elapsed
    FROM applications a JOIN jobs j ON j.id = a.job_id
    WHERE a.status = \"applied\"
    ORDER BY days_elapsed DESC
''').fetchall()
conn.close()
for r in rows:
    print(f'  [{r[\"id\"]}] {r[\"company\"]} — {r[\"days_elapsed\"]:.0f} days elapsed')
"
```

Expected: Lists all active applications with their age in days. Any at 45+ would be ghosted on next run.

- [ ] **Step 6: Commit**

```bash
git add app/scheduler.py
git commit -m "feat: Day-45 ghosted detection with Telegram alert (job_mark_ghosted)"
```

---

## Task 8: Update System page health check label

**Files:**
- Modify: `app/dashboard/main.py`

The health check already shows "APScheduler" — the new job `mark_ghosted` registers automatically. But the `app/state.py` pipeline stage label needs the new key so the System page displays it correctly.

- [ ] **Step 1: Verify `app/state.py` already handles unknown stage keys gracefully**

```bash
python -c "
from app import state
state.set_stage('marking_ghosted', '2026-01-01T00:00:00')
print(state.snapshot())
"
```

Expected: `{'stage': 'marking_ghosted', ...}` — the System page's `STAGE_LABELS` dict falls back to the raw key if not found, which is fine.

- [ ] **Step 2: Add `marking_ghosted` to `System.jsx` STAGE_LABELS**

In `frontend/src/pages/System.jsx`, find `STAGE_LABELS` and add:

```js
const STAGE_LABELS = {
  idle:               'Idle',
  scraping:           'Scraping Jobs',
  scoring:            'Scoring Jobs',
  generating_cvs:     'Generating CVs',
  submitting:         'Submitting',
  detecting_replies:  'Detecting Replies',
  checking_followups: 'Checking Follow-ups',
  sending_digest:     'Daily Digest',
  marking_ghosted:    'Marking Ghosted',    // ← add this line
}
```

Also add to `PIPELINE_STEPS`:

```js
const PIPELINE_STEPS = [
  { key: 'scraping',           label: 'Scrape' },
  { key: 'scoring',            label: 'Score' },
  { key: 'generating_cvs',     label: 'Gen CVs' },
  { key: 'submitting',         label: 'Submit' },
  { key: 'detecting_replies',  label: 'Replies' },
  { key: 'checking_followups', label: 'Follow-up' },
  { key: 'marking_ghosted',    label: 'Ghosted' },   // ← add this line
  { key: 'sending_digest',     label: 'Digest' },
]
```

- [ ] **Step 3: Build frontend**

```bash
cd frontend && npm run build && cd ..
```

Expected: `✓ built in ~2s`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/System.jsx
git add -f frontend/dist/
git commit -m "feat: add marking_ghosted stage to System page pipeline display"
```

---

## Task 9: End-to-end smoke test

- [ ] **Step 1: Restart the server and verify all jobs are registered**

Stop and restart with `python main.py`. Check the log output shows:

```
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← scrape
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← score
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← generate_cvs
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← submit
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← detect_replies
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← followups
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← daily_digest
[INFO] Added job "build_scheduler.<locals>.<lambda>" to job store "default"  ← mark_ghosted
[INFO] Added job "_refresh_health" to job store "default"
[INFO] Scheduler started
```

- [ ] **Step 2: Trigger Run Now from the dashboard and watch the System page**

Open the dashboard, click **Run Now**, and watch the System page. The pipeline stage indicator should move through Scraping → Scoring → Generating CVs → Submitting.

- [ ] **Step 3: Verify the health check includes all 9 services**

Open the System page and confirm the Services Health panel shows all services including APScheduler as green.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Phase 8 complete — Telegram notifications, follow-ups, ghosted detection"
```

---

## Self-Review

**Spec coverage:**
- ✅ `telegram.send()` / `telegram.alert()` — Task 1
- ✅ Config fields — Task 2
- ✅ Pipeline error alert in `_run()` — Task 3
- ✅ Daily digest Telegram — Task 4
- ✅ Interview keyword Telegram alert — Task 5
- ✅ Day-21 / Day-30 follow-up emails — Task 6
- ✅ Day-45 ghosted detection — Task 7
- ✅ System page stage label — Task 8

**Follow-up email retry logic:** timestamp is written only after successful send — a Gmail failure leaves the timestamp null so the next scheduler run retries. ✅

**Form applications:** marked as checked without sending an email (no address). ✅

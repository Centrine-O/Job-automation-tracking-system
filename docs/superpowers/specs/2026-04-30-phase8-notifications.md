# Phase 8 — Notifications & Follow-up Automation Design Spec

**Date:** 2026-04-30
**Status:** Approved

---

## Goal

Replace the planned n8n integration with a Python-native implementation that delivers the same outcomes: follow-up emails at Day 21 and Day 30, ghosted detection at Day 45, instant Telegram alerts for interview replies and pipeline errors, and Telegram in the daily digest. No additional services or Docker containers required.

---

## Architecture

### New file

**`app/notifications/telegram.py`**
Single responsibility: send messages to the Telegram bot. No state, no side effects beyond the HTTP call. Two public functions:
- `send(text: str)` — sends a regular message. Silently swallows exceptions so a Telegram outage never crashes the pipeline.
- `alert(text: str)` — prepends 🚨 and calls `send()`. Used for errors and urgent events.

Uses `urllib.request` only — no new dependencies.

### Config additions (`app/config.py`)

```
telegram_bot_token: str = ""
telegram_chat_id: str = ""
```

Both read from `.env`. If either is empty, `telegram.send()` logs a warning and returns without crashing.

### Scheduler changes (`app/scheduler.py`)

Five modifications to existing functions, plus one new function:

| Function | Change |
|---|---|
| `_run()` | On exception: call `telegram.alert()` with stage name + last line of traceback |
| `job_check_followups()` | Send follow-up email via Gmail first, then mark timestamp. Failed sends leave timestamp null so the next run retries. Sends Telegram confirmation on success. |
| `job_detect_replies()` | After updating status to `replied`: check reply snippet for interview keywords → `telegram.alert()` |
| `job_daily_digest()` | After email: send condensed Telegram summary (applied today, total replies, needs review count) |
| `build_scheduler()` | Add `job_mark_ghosted` to cron at every 6h (hour "0,6,12,18", minute 30) |

**New function: `job_mark_ghosted()`**
- Finds applications where `status='applied'` AND `submitted_at` is 45+ days ago
- Updates their status to `'ghosted'`
- Sends one Telegram alert per ghosted application: company name + role

---

## Follow-up Email Behaviour

- **Email-method applications only** (`submission_method = 'email'`). The hiring address comes from `jobs.apply_url` (stored as `mailto:...` or plain email).
- **Day 21 email tone:** professional first follow-up, references original application date, expresses continued interest.
- **Day 30 email tone:** more concise, acknowledges prior follow-up, brief reiteration of fit.
- **Form-method applications:** no follow-up email sent (no address available). They still hit the Day 45 ghosted check.
- Timestamp (`follow_up_21_at` / `follow_up_30_at`) is written **only after** a successful email send. If Gmail throws, the timestamp stays null and the next scheduler run retries the send.

---

## Interview Keyword Detection

When `job_detect_replies()` finds a Gmail reply, the snippet is checked for these keywords (case-insensitive): `interview`, `schedule`, `call`, `meet`, `availability`, `discuss`.

If any match: `telegram.alert()` fires immediately with:
```
🚨 Interview invite — [Company] · [Role]
"[first 150 chars of reply snippet]"
```

---

## Ghosted Detection

Runs every 6 hours. Query:
```sql
SELECT a.id, j.title, j.company
FROM applications a JOIN jobs j ON j.id = a.job_id
WHERE a.status = 'applied'
  AND a.submitted_at <= datetime('now', '-45 days')
```

For each result: update `applications.status = 'ghosted'`, send Telegram:
```
👻 Ghosted — [Company] · [Role] (45 days, no reply)
```

---

## Daily Digest Telegram Format

Sent at 00:00 EAT alongside the existing email:
```
📊 Daily Report — [date]
Applied today: N
Total replies: N
Needs review: N
Still qualified: N
```

---

## Pipeline Error Alerts

`_run()` already catches all exceptions. Addition: before logging the error, call:
```
telegram.alert(f"{label} failed: {last_line_of_traceback}")
```

This means any stage failure (scraper down, Gmail API broken, CV generation crash) immediately pings your phone.

---

## Files Modified

| File | Change |
|---|---|
| `app/config.py` | Add `telegram_bot_token`, `telegram_chat_id` |
| `app/scheduler.py` | Update `_run`, `job_check_followups`, `job_detect_replies`, `job_daily_digest`, `build_scheduler`; add `job_mark_ghosted` |

## Files Created

| File | Purpose |
|---|---|
| `app/notifications/telegram.py` | Telegram Bot API wrapper |
| `app/notifications/__init__.py` | Package marker |

---

## Done When

- A pipeline failure sends a Telegram alert within seconds
- Daily digest arrives on Telegram at midnight EAT
- Gmail reply with "interview" triggers an immediate Telegram ping
- Applications 45+ days old with no reply are marked `ghosted` automatically
- Follow-up emails send on Day 21 and Day 30 for email-method applications

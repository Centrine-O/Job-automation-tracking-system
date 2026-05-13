# Manual Apply Pivot — Design Spec

**Date:** 2026-05-13
**Status:** Approved

## Overview

Pivot the job automation system from fully automated application submission to a job discovery + manual tracking system. The system scrapes job boards, scores jobs with AI, and surfaces qualified jobs on the dashboard. The user reviews jobs, opens the URL to apply manually, and tracks application status in the dashboard.

---

## What Gets Removed

| Module | Action |
|---|---|
| `app/cv/` | Delete entirely |
| `app/submission/` | Delete entirely |
| `app/notifications/` | Keep `telegram.py` only (error alerts); remove all other notification logic |
| `data/gmail_credentials.json` | Delete |
| `google-auth`, `google-api-python-client` | Remove from dependencies |

**Scheduler jobs removed:**
- `job_generate_cvs`
- `job_submit`
- `job_detect_replies`
- `job_check_followups`
- `job_mark_ghosted`
- `job_daily_digest`
- All Phase 8 Telegram wiring except `_run()` error alert

**Scheduler after pivot:**
- Scrape at 7:00am, 1:00pm, 8:00pm (EAT)
- Score 30 minutes after each scrape (7:30am, 1:30pm, 8:30pm)
- `_run()` sends `telegram.alert()` on any pipeline failure — unchanged

---

## New Scrapers

Two scrapers to add alongside the existing four:

| Scraper | Source | Method |
|---|---|---|
| `myjobmag.py` | https://www.myjobmag.co.ke/ | Direct HTML scrape (BeautifulSoup) |
| `linkedin.py` | LinkedIn Jobs | SerpAPI LinkedIn Jobs endpoint (existing key) |

Both follow the same pattern as existing scrapers: fetch listings, normalise fields, call `insert_job()`. Deduplicate on `(title, company)` as existing scrapers do.

---

## Database Changes

**`jobs` table — new valid status value:** `'dismissed'`

Dismissed jobs are excluded from the Queue and do not re-appear. No schema migration needed — `status` is already a `TEXT` column.

**`applications` table — add column:**
```sql
ALTER TABLE applications ADD COLUMN notes TEXT;
```

Existing submission-specific columns (`cv_path`, `cover_letter_path`, `ats_score`, `submission_method`, `follow_up_21_at`, `follow_up_30_at`, `ghosted_at`) are kept but no longer written to. New application records only use: `id`, `job_id`, `submitted_at`, `status`, `notes`.

---

## Backend API

### New endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/jobs/{id}/dismiss` | Set job `status = 'dismissed'` |
| `POST` | `/api/jobs/{id}/apply` | Create application record with `status = 'applied'` |
| `PATCH` | `/api/applications/{id}/status` | Update status: `applied / replied / offer / rejected / ghosted` |

### Changed endpoints

- `GET /api/queue` — returns `status = 'qualified'` jobs only (excludes dismissed), ordered by `skill_score DESC`. Each job includes: `id`, `title`, `company`, `location`, `remote_type`, `salary`, `skill_score`, `hire_score`, `apply_url`, `jd_text` (first 400 chars), `source`.
- `GET /api/history` — returns all applications joined with job info, ordered by `submitted_at DESC`. Includes `status` and `notes`.
- `GET /api/stats` — update counts: `qualified`, `applied`, `replied`, `offers`, `dismissed`.

### Removed endpoints

- `POST /apply/{job_id}` — old auto-submit trigger
- `POST /api/apply/{job_id}` — old auto-submit trigger
- `POST /mark-applied/{job_id}` — old endpoint
- `POST /api/mark-applied/{job_id}` — old endpoint

---

## Dashboard

### Queue page

**Layout:** Two-column. Left: scrollable job list. Right: detail panel (opens when you click a job, empty state by default).

**Job list item:** Title, company, score badge, remote/location tag. Active item highlighted.

**Detail panel contents:**
- Title, company, salary, source, score
- JD snippet (first 400 chars, expandable)
- Three action buttons:
  - **Open Job ↗** — opens `apply_url` in new tab
  - **Mark Applied** — calls `POST /api/jobs/{id}/apply`, moves job to History, removes from Queue
  - **Dismiss** — calls `POST /api/jobs/{id}/dismiss`, removes from Queue immediately

### History page

**Layout:** Table/card list of manually applied jobs.

**Each entry shows:** Title, company, applied date, current status.

**Status pills:** `Applied` / `Replied` / `Offer` / `Rejected` / `Ghosted` — click to update via `PATCH /api/applications/{id}/status`. Active status is highlighted.

**Notes:** Inline editable text field per application.

### Overview page

Stats updated:
- **Qualified** — jobs ready to apply to
- **Applied** — manually applied
- **Replied** — companies that responded
- **Dismissed** — jobs skipped

Remove: applications sent today, ATS score stats, submission method breakdown.

### System page

Pipeline steps updated to: `Scrape → Score` (remove CV Gen, Submit, Replies, Follow-up, Ghosted, Digest stages).

---

## Spec Self-Review

- No TBDs or placeholders
- LinkedIn via SerpAPI is consistent with existing `google_jobs.py` pattern
- `notes` column addition requires a one-time migration on startup (run in `init_db()`)
- Dismissed status is non-destructive — jobs can be un-dismissed in future if needed (not in scope now)
- Existing 13 applied + 18 application records in DB are unaffected

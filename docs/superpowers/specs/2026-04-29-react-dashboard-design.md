# React Dashboard — Design Spec
**Date:** 2026-04-29
**Status:** Approved

---

## Overview

Replace the current Jinja2 HTML dashboard (three server-rendered templates) with a React + Vite single-page application that communicates with the FastAPI backend through a JSON REST API. The backend serves the compiled React app in production.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend framework | React 18 + Vite |
| Styling | Tailwind CSS v3 |
| Component library | shadcn/ui |
| Routing | React Router v6 |
| Data fetching | Native `fetch` via thin `api.js` module |
| Fonts | Crimson Text (400/600/700) + IBM Plex Mono (400/500/600) via Google Fonts |

---

## Architecture

### Development

```
Terminal 1: python main.py          → FastAPI on localhost:8000
Terminal 2: cd frontend && npm run dev  → Vite on localhost:5173
```

Vite proxies all `/api/*` requests to `localhost:8000` during development. The frontend developer experience is fully hot-reloaded.

### Production

```
cd frontend && npm run build        → outputs to frontend/dist/
python main.py                      → FastAPI on :8000, serves frontend/dist/ at /
```

FastAPI mounts `frontend/dist/` as a StaticFiles directory at `/` (registered last so it never shadows `/api/*` routes). One process, one port, no CORS needed.

---

## Directory Structure

```
Job-automation-tracking-system/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Overview.jsx        # stats + recent applications
│   │   │   ├── Queue.jsx           # needs_review exception jobs
│   │   │   └── History.jsx         # full application log with filters
│   │   ├── components/
│   │   │   ├── Layout.jsx          # sidebar + topbar shell (wraps all pages)
│   │   │   ├── StatCard.jsx        # single metric card
│   │   │   ├── AppTable.jsx        # reusable applications table
│   │   │   ├── JobCard.jsx         # queue card with action buttons
│   │   │   └── NotifPanel.jsx      # notification bell dropdown
│   │   ├── lib/
│   │   │   └── api.js              # all fetch calls, named exports
│   │   ├── globals.css             # shadcn/ui CSS variables + Tailwind directives
│   │   └── main.jsx
│   ├── index.html                  # Google Fonts links here
│   ├── vite.config.js              # /api/* proxy to :8000
│   ├── tailwind.config.js          # custom palette
│   ├── components.json             # shadcn/ui config
│   └── package.json
│
└── app/dashboard/main.py           # gains /api/* JSON routes + StaticFiles mount
```

---

## Backend API Changes

New JSON endpoints added to `app/dashboard/main.py`. Existing HTML routes (`/`, `/queue`, `/history`) remain until the frontend is stable, then are removed.

### New endpoints

```
GET  /api/stats
     Response: {
       total_jobs, qualified, applied_today, max_per_day,
       total_applied, needs_review, replied, dry_run, now
     }

GET  /api/applications
     Response: [ { id, title, company, apply_method, ats_score,
                   status, submitted_at } ]
     (last 10, for Overview page)

GET  /api/queue
     Response: [ { id, title, company, apply_url,
                   skill_score, hire_score, notes } ]

GET  /api/history
     Query params: ?status=&method=   (optional filters)
     Response: [ { id, title, company, apply_method, ats_score,
                   skill_score, status, submitted_at, notes,
                   cv_path, follow_up_21_at, follow_up_30_at } ]
```

### Endpoints that need an `/api/` prefix alias added

These routes exist in the backend but without the `/api/` prefix. Add aliased routes so the frontend can call them uniformly:

```
GET  /api/notifications      → already has /api/ prefix ✓
GET  /api/unread-count       → already has /api/ prefix ✓
POST /api/run-now            → alias for existing POST /run-now
POST /api/apply/{job_id}     → alias for existing POST /apply/{job_id}
POST /api/mark-applied/{id}  → alias for existing POST /mark-applied/{id}
```

Production static file mount (added last in `main.py`):

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

---

## Frontend Pages

### Overview (`/`)
- 6 `StatCard` components in a grid: Scraped, Qualified, Today (with cap), Total Applied, Review, Replies
- `AppTable` showing the last 10 applications
- Data from `GET /api/stats` + `GET /api/applications`

### Queue (`/queue`)
- Alert banner showing job count when queue is non-empty
- One `JobCard` per job showing: title, company, skill/hire scores, block reason, apply URL
- Each card has **Retry Auto-Submit** and **Mark as Applied** buttons
- Empty state shown when queue is clear
- Data from `GET /api/queue`

### History (`/history`)
- Filter bar: All / Applied / Replied / Review / Email / Form (client-side filtering)
- Full `AppTable` with columns: #, Role/Company, Method, ATS, Skill, Status, Submitted, Notes, CV
- Follow-up flags (21d / 30d) shown inline in Status column
- Data from `GET /api/history`

---

## Shared Layout

`Layout.jsx` wraps all three pages and renders:

**Sidebar (220px, ONYX `#13140e` background):**
- Logo mark (`FIELD OPS V1` in IBM Plex Mono) + `Job.Auto` wordmark
- Navigation links: Overview, Review Queue (with red badge if count > 0), History
- Active link: left olive border + olive text
- Footer: animated pipeline status dot

**Top bar (bone-1 background, full width):**
- Left: current timestamp + EAT label (IBM Plex Mono)
- Right: DRY RUN pill (when enabled), notification bell with unread badge, Run Now button

---

## Styling

### Tailwind custom colors (`tailwind.config.js`)

```js
colors: {
  onyx:  { DEFAULT: '#13140e', dim: '#474a38' },
  olive: { DEFAULT: '#838236', bright: '#9a9a3f' },
  bone:  { DEFAULT: '#dedacf', 1: '#d4d0c5', 2: '#c8c4b9', 3: '#b8b4a9' },
}
```

### shadcn/ui CSS variable mapping (`globals.css`)

| shadcn variable | Value |
|---|---|
| `--background` | `#dedacf` (bone) |
| `--foreground` | `#13140e` (onyx) |
| `--primary` | `#838236` (olive) |
| `--card` | `#ffffff` |
| `--border` | `#c8c4b9` (bone-2) |
| `--destructive` | `#c44040` |
| `--muted-foreground` | `#474a38` (onyx-dim) |

### Typography

- **Crimson Text** — headings, stat values, body text, role names (serif)
- **IBM Plex Mono** — all labels, timestamps, badges, tags (monospace)
- Fonts loaded in `index.html` via Google Fonts CDN

---

## api.js — Data Layer

All API calls live in `src/lib/api.js`. Pages import named functions, never raw URLs.

```js
export const getStats         = () => fetch('/api/stats').then(r => r.json())
export const getApplications  = () => fetch('/api/applications').then(r => r.json())
export const getQueue         = () => fetch('/api/queue').then(r => r.json())
export const getHistory       = () => fetch('/api/history').then(r => r.json())
export const getNotifications = () => fetch('/api/notifications').then(r => r.json())
export const getUnreadCount   = () => fetch('/api/unread-count').then(r => r.json())
export const runNow           = () => fetch('/api/run-now', { method: 'POST' }).then(r => r.json())
export const retryApply       = (id) => fetch(`/api/apply/${id}`, { method: 'POST' }).then(r => r.json())
export const markApplied      = (id) => fetch(`/api/mark-applied/${id}`, { method: 'POST' }).then(r => r.json())
```

---

## What Gets Removed

Once the React frontend is working and verified against live data:
- `app/dashboard/templates/dashboard.html`
- `app/dashboard/templates/queue.html`
- `app/dashboard/templates/history.html`
- Jinja2 `TemplateResponse` routes in `main.py` (`GET /`, `GET /queue`, `GET /history`)
- `jinja2` and `python-multipart` dependencies (if no longer needed)

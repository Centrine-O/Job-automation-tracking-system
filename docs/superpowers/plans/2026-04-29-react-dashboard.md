# React Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three Jinja2 HTML templates with a React + Vite SPA served by the existing FastAPI backend.

**Architecture:** Vite dev server (port 5173) proxies `/api/*` to FastAPI (port 8000) during development. In production, `npm run build` outputs to `frontend/dist/` which FastAPI mounts at `/` via StaticFiles — one port, no CORS.

**Tech Stack:** React 18, Vite, Tailwind CSS v3, shadcn/ui, React Router v6, native fetch

---

## File Map

**Backend (modify):**
- `app/dashboard/main.py` — add 4 JSON GET endpoints + 3 `/api/` prefix POST aliases

**Frontend (create):**
- `frontend/package.json`
- `frontend/vite.config.js` — proxy `/api/*` → `:8000`
- `frontend/tailwind.config.js` — custom ONYX/OLIVE/BONE palette
- `frontend/postcss.config.js`
- `frontend/components.json` — shadcn/ui config
- `frontend/index.html` — Google Fonts link tags
- `frontend/src/globals.css` — shadcn/ui CSS variables + Tailwind directives
- `frontend/src/main.jsx` — React root + React Router setup
- `frontend/src/lib/api.js` — all fetch calls, named exports
- `frontend/src/components/Layout.jsx` — sidebar + topbar shell
- `frontend/src/components/StatCard.jsx` — single metric tile
- `frontend/src/components/AppTable.jsx` — reusable applications table
- `frontend/src/components/JobCard.jsx` — queue card with action buttons
- `frontend/src/components/NotifPanel.jsx` — notification bell dropdown
- `frontend/src/pages/Overview.jsx` — stats + recent applications
- `frontend/src/pages/Queue.jsx` — needs_review jobs
- `frontend/src/pages/History.jsx` — full log with filters

---

## Task 1: Add JSON API endpoints to FastAPI

**Files:**
- Modify: `app/dashboard/main.py`

- [ ] **Step 1: Add the 4 new GET /api/* routes**

  Open `app/dashboard/main.py` and add the following routes after the existing `/api/unread-count` route (before the `/run-now` route):

  ```python
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
  ```

- [ ] **Step 2: Add `/api/` prefix aliases for the three POST routes**

  Add these three aliased routes directly after the routes above, before the StaticFiles mount section:

  ```python
  @app.post("/api/run-now")
  def api_run_now():
      return run_now()


  @app.post("/api/apply/{job_id}")
  def api_re_trigger(job_id: int):
      return re_trigger(job_id)


  @app.post("/api/mark-applied/{job_id}")
  def api_mark_applied(job_id: int):
      return mark_applied(job_id)
  ```

- [ ] **Step 3: Start FastAPI and verify all endpoints respond**

  ```bash
  python main.py &
  sleep 2
  curl -s http://localhost:8000/api/stats | python -m json.tool
  curl -s http://localhost:8000/api/applications | python -m json.tool
  curl -s http://localhost:8000/api/queue | python -m json.tool
  curl -s http://localhost:8000/api/history | python -m json.tool
  ```

  Expected: each returns valid JSON (empty arrays `[]` are fine for queue/history if DB is empty).

- [ ] **Step 4: Stop the dev server**

  ```bash
  kill $(lsof -ti:8000)
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add app/dashboard/main.py
  git commit -m "feat: add /api/* JSON endpoints for React frontend"
  ```

---

## Task 2: Scaffold the Vite + React project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`

- [ ] **Step 1: Initialise the frontend directory**

  ```bash
  cd frontend
  npm create vite@latest . -- --template react
  ```

  When prompted, confirm overwriting the directory. Select **React** framework and **JavaScript** variant.

- [ ] **Step 2: Install dependencies**

  ```bash
  cd frontend
  npm install
  npm install -D tailwindcss@3 postcss autoprefixer
  npm install react-router-dom@6
  npx tailwindcss init -p
  ```

- [ ] **Step 3: Replace `frontend/vite.config.js` with proxy config**

  ```js
  import { defineConfig } from 'vite'
  import react from '@vitejs/plugin-react'
  import path from 'path'

  export default defineConfig({
    plugins: [react()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    server: {
      proxy: {
        '/api': 'http://localhost:8000',
      },
    },
  })
  ```

- [ ] **Step 4: Replace `frontend/index.html`**

  ```html
  <!doctype html>
  <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>Job.Auto — Field Ops</title>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
      <link
        href="https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />
    </head>
    <body>
      <div id="root"></div>
      <script type="module" src="/src/main.jsx"></script>
    </body>
  </html>
  ```

- [ ] **Step 5: Verify dev server starts**

  ```bash
  # Terminal 1
  python main.py

  # Terminal 2
  cd frontend && npm run dev
  ```

  Expected: Vite reports `Local: http://localhost:5173/`. Browser shows Vite default page.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/
  git commit -m "chore: scaffold Vite + React frontend"
  ```

---

## Task 3: Configure Tailwind + shadcn/ui

**Files:**
- Modify: `frontend/tailwind.config.js`
- Create: `frontend/components.json`
- Create: `frontend/src/globals.css`
- Delete: `frontend/src/index.css` (replaced by globals.css)

- [ ] **Step 1: Replace `frontend/tailwind.config.js`**

  ```js
  /** @type {import('tailwindcss').Config} */
  export default {
    darkMode: ['class'],
    content: ['./index.html', './src/**/*.{js,jsx}'],
    theme: {
      extend: {
        colors: {
          onyx:  { DEFAULT: '#13140e', dim: '#474a38' },
          olive: { DEFAULT: '#838236', bright: '#9a9a3f' },
          bone:  { DEFAULT: '#dedacf', 1: '#d4d0c5', 2: '#c8c4b9', 3: '#b8b4a9' },
        },
        fontFamily: {
          serif: ['"Crimson Text"', 'Georgia', 'serif'],
          mono:  ['"IBM Plex Mono"', 'Menlo', 'monospace'],
        },
      },
    },
    plugins: [],
  }
  ```

- [ ] **Step 2: Install and initialise shadcn/ui**

  ```bash
  cd frontend
  npx shadcn@latest init
  ```

  When prompted, use these answers:
  - Style: **Default**
  - Base color: **Slate** (we override with CSS vars)
  - CSS variables: **Yes**
  - Global CSS file: `src/globals.css`
  - Tailwind config: `tailwind.config.js`
  - Components alias: `@/components`
  - Utils alias: `@/lib/utils`
  - RSC: **No**

- [ ] **Step 3: Replace the generated `frontend/src/globals.css` with the project palette**

  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

  @layer base {
    :root {
      --background: 46 20% 84%;      /* #dedacf bone */
      --foreground: 68 15% 8%;       /* #13140e onyx */
      --card: 0 0% 100%;             /* #ffffff */
      --card-foreground: 68 15% 8%;
      --primary: 60 39% 36%;         /* #838236 olive */
      --primary-foreground: 0 0% 100%;
      --muted: 46 14% 82%;
      --muted-foreground: 68 12% 25%;  /* #474a38 onyx-dim */
      --border: 46 14% 75%;          /* #c8c4b9 bone-2 */
      --input: 46 14% 75%;
      --ring: 60 39% 36%;
      --destructive: 0 48% 51%;      /* #c44040 */
      --destructive-foreground: 0 0% 100%;
      --radius: 0.5rem;
    }
  }

  @layer base {
    * {
      @apply border-border;
    }
    body {
      @apply bg-background text-foreground;
      font-family: 'Crimson Text', Georgia, serif;
      font-weight: 400;
      -webkit-font-smoothing: antialiased;
    }
  }
  ```

- [ ] **Step 4: Remove the old index.css import from `frontend/src/main.jsx` if present**

  Open `frontend/src/main.jsx`. Change:
  ```js
  import './index.css'
  ```
  to:
  ```js
  import './globals.css'
  ```

  Then delete `frontend/src/index.css` if it exists:
  ```bash
  rm -f frontend/src/index.css
  ```

- [ ] **Step 5: Add the Button component from shadcn/ui (used by JobCard)**

  ```bash
  cd frontend
  npx shadcn@latest add button badge
  ```

- [ ] **Step 6: Verify Tailwind classes resolve**

  Start dev server, open browser, confirm the body background is bone (`#dedacf`) not white.

- [ ] **Step 7: Commit**

  ```bash
  git add frontend/
  git commit -m "chore: configure Tailwind palette and shadcn/ui"
  ```

---

## Task 4: Build the api.js data layer

**Files:**
- Create: `frontend/src/lib/api.js`

- [ ] **Step 1: Create `frontend/src/lib/api.js`**

  ```js
  export const getStats         = () => fetch('/api/stats').then(r => r.json())
  export const getApplications  = () => fetch('/api/applications').then(r => r.json())
  export const getQueue         = () => fetch('/api/queue').then(r => r.json())
  export const getHistory       = (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return fetch(`/api/history${qs ? '?' + qs : ''}`).then(r => r.json())
  }
  export const getNotifications = () => fetch('/api/notifications').then(r => r.json())
  export const getUnreadCount   = () => fetch('/api/unread-count').then(r => r.json())
  export const runNow           = () => fetch('/api/run-now', { method: 'POST' }).then(r => r.json())
  export const retryApply       = (id) => fetch(`/api/apply/${id}`, { method: 'POST' }).then(r => r.json())
  export const markApplied      = (id) => fetch(`/api/mark-applied/${id}`, { method: 'POST' }).then(r => r.json())
  ```

- [ ] **Step 2: Smoke-test in browser console**

  With both servers running, open `http://localhost:5173`, open DevTools console, run:

  ```js
  import('/src/lib/api.js').then(m => m.getStats()).then(console.log)
  ```

  Expected: stats object logged with `total_jobs`, `qualified`, etc.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/lib/api.js
  git commit -m "feat: add api.js data layer"
  ```

---

## Task 5: Build Layout.jsx

**Files:**
- Create: `frontend/src/components/Layout.jsx`

- [ ] **Step 1: Create `frontend/src/components/Layout.jsx`**

  ```jsx
  import { useState, useEffect } from 'react'
  import { NavLink, Outlet, useNavigate } from 'react-router-dom'
  import { getUnreadCount, runNow } from '@/lib/api'

  function useClock() {
    const [time, setTime] = useState(new Date())
    useEffect(() => {
      const id = setInterval(() => setTime(new Date()), 1000)
      return () => clearInterval(id)
    }, [])
    return time
  }

  export default function Layout({ dryRun }) {
    const [unread, setUnread]     = useState(0)
    const [running, setRunning]   = useState(false)
    const now                     = useClock()

    useEffect(() => {
      getUnreadCount().then(d => setUnread(d.unread)).catch(() => {})
      const id = setInterval(() => {
        getUnreadCount().then(d => setUnread(d.unread)).catch(() => {})
      }, 30_000)
      return () => clearInterval(id)
    }, [])

    async function handleRunNow() {
      setRunning(true)
      try { await runNow() } finally {
        setTimeout(() => setRunning(false), 3000)
      }
    }

    const navLink = ({ isActive }) =>
      `flex items-center gap-2 px-4 py-2 text-sm font-mono rounded transition-colors ` +
      (isActive
        ? 'border-l-2 border-olive text-olive bg-white/10'
        : 'text-bone/70 hover:text-bone border-l-2 border-transparent')

    return (
      <div className="flex h-screen overflow-hidden">
        {/* ── Sidebar ── */}
        <aside className="w-[220px] flex-shrink-0 flex flex-col bg-onyx text-bone">
          <div className="px-5 pt-6 pb-4 border-b border-white/10">
            <p className="font-mono text-[10px] tracking-widest text-bone/40 uppercase mb-1">FIELD OPS V1</p>
            <p className="font-serif text-xl font-semibold tracking-tight">Job.Auto</p>
          </div>

          <nav className="flex-1 py-4 space-y-1">
            <NavLink to="/"       end className={navLink}>Overview</NavLink>
            <NavLink to="/queue"      className={navLink}>
              Review Queue
              {unread > 0 && (
                <span className="ml-auto bg-destructive text-white text-[10px] font-mono px-1.5 py-0.5 rounded-full">
                  {unread}
                </span>
              )}
            </NavLink>
            <NavLink to="/history"    className={navLink}>History</NavLink>
          </nav>

          <div className="px-5 py-4 border-t border-white/10">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-olive animate-pulse" />
              <span className="font-mono text-[11px] text-bone/50">pipeline active</span>
            </div>
          </div>
        </aside>

        {/* ── Main area ── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top bar */}
          <header className="flex-shrink-0 h-14 bg-bone-1 border-b border-bone-2 flex items-center px-6 gap-4">
            <span className="font-mono text-xs text-onyx-dim">
              {now.toLocaleTimeString('en-US', { hour12: false })} EAT
            </span>
            <div className="flex-1" />
            {dryRun && (
              <span className="font-mono text-[11px] px-2 py-1 rounded border border-olive text-olive">
                DRY RUN
              </span>
            )}
            <NotifBell unread={unread} onOpen={() => setUnread(0)} />
            <button
              onClick={handleRunNow}
              disabled={running}
              className="font-mono text-xs px-3 py-1.5 rounded bg-olive text-white hover:bg-olive-bright disabled:opacity-50 transition-colors"
            >
              {running ? 'Running…' : 'Run Now'}
            </button>
          </header>

          <main className="flex-1 overflow-y-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
    )
  }

  function NotifBell({ unread, onOpen }) {
    const [open, setOpen] = useState(false)
    return (
      <div className="relative">
        <button
          onClick={() => { setOpen(o => !o); onOpen() }}
          className="relative p-1.5 rounded hover:bg-bone-2 transition-colors"
        >
          <svg className="w-5 h-5 text-onyx-dim" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
          </svg>
          {unread > 0 && (
            <span className="absolute top-0 right-0 w-2 h-2 rounded-full bg-destructive" />
          )}
        </button>
        {open && (
          <div className="absolute right-0 top-10 w-72 bg-white rounded-lg shadow-xl border border-bone-2 z-50 p-3">
            <p className="font-mono text-xs text-onyx-dim mb-2">NOTIFICATIONS</p>
            <p className="font-serif text-sm text-onyx-dim">No new notifications</p>
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/components/Layout.jsx
  git commit -m "feat: add Layout component (sidebar + topbar)"
  ```

---

## Task 6: Build StatCard.jsx

**Files:**
- Create: `frontend/src/components/StatCard.jsx`

- [ ] **Step 1: Create `frontend/src/components/StatCard.jsx`**

  ```jsx
  export default function StatCard({ label, value, sub, accent = false }) {
    return (
      <div className={`bg-white rounded-lg p-5 border ${accent ? 'border-olive/40' : 'border-bone-2'}`}>
        <p className="font-mono text-[11px] tracking-widest uppercase text-onyx-dim mb-2">{label}</p>
        <p className={`font-serif text-5xl font-bold leading-none ${accent ? 'text-olive' : 'text-onyx'}`}>
          {value ?? '—'}
        </p>
        {sub && <p className="font-mono text-xs text-onyx-dim mt-2">{sub}</p>}
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/components/StatCard.jsx
  git commit -m "feat: add StatCard component"
  ```

---

## Task 7: Build AppTable.jsx

**Files:**
- Create: `frontend/src/components/AppTable.jsx`

- [ ] **Step 1: Create `frontend/src/components/AppTable.jsx`**

  ```jsx
  function statusClass(status) {
    const map = {
      applied:      'bg-olive/10 text-olive',
      replied:      'bg-blue-50 text-blue-700',
      needs_review: 'bg-red-50 text-red-600',
      skipped:      'bg-bone text-onyx-dim',
    }
    return map[status] ?? 'bg-bone text-onyx-dim'
  }

  export default function AppTable({ rows, showFollowUp = false }) {
    if (!rows?.length) {
      return (
        <div className="bg-white rounded-lg border border-bone-2 p-8 text-center">
          <p className="font-serif text-onyx-dim">No applications yet.</p>
        </div>
      )
    }

    return (
      <div className="bg-white rounded-lg border border-bone-2 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bone-2 bg-bone/40">
              <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">#</th>
              <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">ROLE / COMPANY</th>
              <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">METHOD</th>
              <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">ATS</th>
              {showFollowUp && <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">SKILL</th>}
              <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">STATUS</th>
              <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">SUBMITTED</th>
              {showFollowUp && (
                <>
                  <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">NOTES</th>
                  <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">CV</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.id} className="border-b border-bone/60 last:border-0 hover:bg-bone/20 transition-colors">
                <td className="font-mono text-xs text-onyx-dim px-4 py-3">{i + 1}</td>
                <td className="px-4 py-3">
                  <p className="font-serif font-semibold text-onyx">{row.title}</p>
                  <p className="font-mono text-xs text-onyx-dim">{row.company}</p>
                </td>
                <td className="font-mono text-xs text-onyx-dim px-4 py-3 uppercase">
                  {row.apply_method || row.job_apply_method || '—'}
                </td>
                <td className="font-mono text-xs px-4 py-3">
                  {row.ats_score != null ? `${row.ats_score}%` : '—'}
                </td>
                {showFollowUp && (
                  <td className="font-mono text-xs px-4 py-3">
                    {row.skill_score != null ? `${row.skill_score}%` : '—'}
                  </td>
                )}
                <td className="px-4 py-3">
                  <span className={`font-mono text-[10px] px-2 py-0.5 rounded-full ${statusClass(row.status)}`}>
                    {row.status}
                  </span>
                  {showFollowUp && !row.follow_up_21_at && row.status === 'applied' && (
                    <span className="ml-1 font-mono text-[9px] px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-700">21d</span>
                  )}
                  {showFollowUp && !row.follow_up_30_at && row.status === 'applied' && (
                    <span className="ml-1 font-mono text-[9px] px-1.5 py-0.5 rounded bg-orange-50 text-orange-700">30d</span>
                  )}
                </td>
                <td className="font-mono text-xs text-onyx-dim px-4 py-3">
                  {row.submitted_at ? row.submitted_at.slice(0, 16).replace('T', ' ') : '—'}
                </td>
                {showFollowUp && (
                  <>
                    <td className="font-serif text-xs text-onyx-dim px-4 py-3 max-w-[180px] truncate">{row.notes || '—'}</td>
                    <td className="px-4 py-3">
                      {row.cv_path ? (
                        <a
                          href={`/api/cv/${row.id}`}
                          className="font-mono text-[10px] text-olive hover:underline"
                          target="_blank" rel="noreferrer"
                        >PDF</a>
                      ) : '—'}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/components/AppTable.jsx
  git commit -m "feat: add AppTable component"
  ```

---

## Task 8: Build NotifPanel.jsx

**Files:**
- Create: `frontend/src/components/NotifPanel.jsx`

- [ ] **Step 1: Create `frontend/src/components/NotifPanel.jsx`**

  This component is a self-contained dropdown panel (the Layout's `NotifBell` is a lightweight stub — this full panel can replace it later). For now it lives standalone for future enhancement.

  ```jsx
  export default function NotifPanel({ notifications = [] }) {
    return (
      <div className="w-72">
        <p className="font-mono text-[10px] tracking-widest text-onyx-dim mb-3 uppercase">Notifications</p>
        {notifications.length === 0 ? (
          <p className="font-serif text-sm text-onyx-dim">All clear — no notifications.</p>
        ) : (
          <ul className="space-y-2">
            {notifications.map(n => (
              <li key={n.id} className={`rounded p-2 ${n.read ? 'opacity-60' : 'bg-olive/5'}`}>
                <p className="font-serif text-sm font-semibold text-onyx">{n.title}</p>
                <p className="font-serif text-xs text-onyx-dim">{n.body}</p>
                <p className="font-mono text-[10px] text-onyx-dim/60 mt-0.5">{n.created_at?.slice(0, 16)}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/components/NotifPanel.jsx
  git commit -m "feat: add NotifPanel component"
  ```

---

## Task 9: Build Overview.jsx page

**Files:**
- Create: `frontend/src/pages/Overview.jsx`

- [ ] **Step 1: Create `frontend/src/pages/Overview.jsx`**

  ```jsx
  import { useState, useEffect } from 'react'
  import StatCard from '@/components/StatCard'
  import AppTable from '@/components/AppTable'
  import { getStats, getApplications } from '@/lib/api'

  export default function Overview() {
    const [stats, setStats]   = useState(null)
    const [apps, setApps]     = useState([])
    const [error, setError]   = useState(null)

    useEffect(() => {
      Promise.all([getStats(), getApplications()])
        .then(([s, a]) => { setStats(s); setApps(a) })
        .catch(e => setError(e.message))
    }, [])

    if (error) return <p className="font-serif text-red-600">{error}</p>
    if (!stats) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>

    return (
      <div className="space-y-6">
        <h1 className="font-serif text-3xl font-bold text-onyx">Overview</h1>

        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard label="Scraped"      value={stats.total_jobs} />
          <StatCard label="Qualified"    value={stats.qualified}  accent />
          <StatCard
            label="Today"
            value={stats.applied_today}
            sub={`cap: ${stats.max_per_day}/day`}
          />
          <StatCard label="Total Applied"  value={stats.total_applied} />
          <StatCard label="Review Queue"   value={stats.needs_review} />
          <StatCard label="Replies"        value={stats.replied} />
        </div>

        <div>
          <h2 className="font-serif text-xl font-semibold text-onyx mb-3">Recent Applications</h2>
          <AppTable rows={apps} />
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 2: Wire into main.jsx temporarily to preview**

  Skip — wire in Task 13 alongside all other pages.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/pages/Overview.jsx
  git commit -m "feat: add Overview page"
  ```

---

## Task 10: Build JobCard.jsx

**Files:**
- Create: `frontend/src/components/JobCard.jsx`

- [ ] **Step 1: Create `frontend/src/components/JobCard.jsx`**

  ```jsx
  import { useState } from 'react'
  import { retryApply, markApplied } from '@/lib/api'

  export default function JobCard({ job, onRemove }) {
    const [state, setState] = useState('idle') // idle | working | done

    async function handleRetry() {
      setState('working')
      try {
        await retryApply(job.id)
        setState('done')
        setTimeout(() => onRemove(job.id), 600)
      } catch {
        setState('idle')
      }
    }

    async function handleMark() {
      setState('working')
      try {
        await markApplied(job.id)
        setState('done')
        setTimeout(() => onRemove(job.id), 600)
      } catch {
        setState('idle')
      }
    }

    return (
      <div
        className={`bg-white rounded-lg border border-bone-2 p-5 transition-all duration-500 ${
          state === 'done' ? 'opacity-0 scale-95' : 'opacity-100'
        }`}
      >
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <p className="font-serif text-lg font-semibold text-onyx">{job.title}</p>
            <p className="font-mono text-xs text-onyx-dim">{job.company}</p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <span className="font-mono text-[10px] px-2 py-1 rounded bg-olive/10 text-olive">
              SKILL {job.skill_score ?? '—'}
            </span>
            <span className="font-mono text-[10px] px-2 py-1 rounded bg-blue-50 text-blue-700">
              HIRE {job.hire_score ?? '—'}
            </span>
          </div>
        </div>

        {job.notes && (
          <div className="mb-3 p-3 rounded bg-red-50 border border-red-100">
            <p className="font-mono text-[10px] text-red-600 tracking-widest uppercase mb-1">Block reason</p>
            <p className="font-serif text-sm text-red-800">{job.notes}</p>
          </div>
        )}

        {job.apply_url && (
          <a
            href={job.apply_url}
            target="_blank"
            rel="noreferrer"
            className="font-mono text-xs text-olive hover:underline block mb-4 truncate"
          >
            {job.apply_url}
          </a>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleRetry}
            disabled={state !== 'idle'}
            className="flex-1 font-mono text-xs py-2 rounded bg-olive text-white hover:bg-olive-bright disabled:opacity-50 transition-colors"
          >
            {state === 'working' ? 'Working…' : 'Retry Auto-Submit'}
          </button>
          <button
            onClick={handleMark}
            disabled={state !== 'idle'}
            className="flex-1 font-mono text-xs py-2 rounded border border-bone-2 text-onyx hover:bg-bone transition-colors disabled:opacity-50"
          >
            Mark as Applied
          </button>
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/components/JobCard.jsx
  git commit -m "feat: add JobCard component with animated removal"
  ```

---

## Task 11: Build Queue.jsx page

**Files:**
- Create: `frontend/src/pages/Queue.jsx`

- [ ] **Step 1: Create `frontend/src/pages/Queue.jsx`**

  ```jsx
  import { useState, useEffect } from 'react'
  import JobCard from '@/components/JobCard'
  import { getQueue } from '@/lib/api'

  export default function Queue() {
    const [jobs, setJobs]   = useState([])
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
      getQueue()
        .then(data => { setJobs(data); setLoading(false) })
        .catch(e => { setError(e.message); setLoading(false) })
    }, [])

    function removeJob(id) {
      setJobs(prev => prev.filter(j => j.id !== id))
    }

    if (loading) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>
    if (error)   return <p className="font-serif text-red-600">{error}</p>

    return (
      <div className="space-y-6">
        <h1 className="font-serif text-3xl font-bold text-onyx">Review Queue</h1>

        {jobs.length > 0 ? (
          <>
            <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 border border-red-100">
              <span className="font-mono text-[10px] tracking-widest text-red-600 uppercase">
                {jobs.length} {jobs.length === 1 ? 'job requires' : 'jobs require'} attention
              </span>
            </div>
            <div className="grid gap-4">
              {jobs.map(job => (
                <JobCard key={job.id} job={job} onRemove={removeJob} />
              ))}
            </div>
          </>
        ) : (
          <div className="bg-white rounded-lg border border-bone-2 p-12 text-center">
            <p className="font-serif text-xl text-onyx-dim">Queue is clear.</p>
            <p className="font-mono text-xs text-onyx-dim/60 mt-2">All jobs processed successfully.</p>
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/pages/Queue.jsx
  git commit -m "feat: add Queue page"
  ```

---

## Task 12: Build History.jsx page

**Files:**
- Create: `frontend/src/pages/History.jsx`

- [ ] **Step 1: Create `frontend/src/pages/History.jsx`**

  ```jsx
  import { useState, useEffect } from 'react'
  import AppTable from '@/components/AppTable'
  import { getHistory } from '@/lib/api'

  const STATUS_FILTERS = ['all', 'applied', 'replied', 'needs_review']
  const METHOD_FILTERS = ['all', 'email', 'form']

  export default function History() {
    const [rows, setRows]         = useState([])
    const [statusF, setStatusF]   = useState('all')
    const [methodF, setMethodF]   = useState('all')
    const [error, setError]       = useState(null)
    const [loading, setLoading]   = useState(true)

    useEffect(() => {
      getHistory()
        .then(data => { setRows(data); setLoading(false) })
        .catch(e => { setError(e.message); setLoading(false) })
    }, [])

    const filtered = rows.filter(r => {
      const matchStatus = statusF === 'all' || r.status === statusF
      const matchMethod = methodF === 'all' || (r.apply_method || '').toLowerCase() === methodF
      return matchStatus && matchMethod
    })

    const btnBase = 'font-mono text-xs px-3 py-1.5 rounded border transition-colors'
    const btnActive = `${btnBase} bg-onyx text-bone border-onyx`
    const btnIdle   = `${btnBase} border-bone-2 text-onyx-dim hover:border-onyx hover:text-onyx`

    if (loading) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>
    if (error)   return <p className="font-serif text-red-600">{error}</p>

    return (
      <div className="space-y-6">
        <h1 className="font-serif text-3xl font-bold text-onyx">History</h1>

        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map(s => (
            <button key={s} onClick={() => setStatusF(s)} className={statusF === s ? btnActive : btnIdle}>
              {s === 'all' ? 'All' : s.replace('_', ' ')}
            </button>
          ))}
          <span className="w-px bg-bone-2 self-stretch mx-1" />
          {METHOD_FILTERS.map(m => (
            <button key={m} onClick={() => setMethodF(m)} className={methodF === m ? btnActive : btnIdle}>
              {m === 'all' ? 'Any Method' : m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>

        <p className="font-mono text-xs text-onyx-dim">
          {filtered.length} record{filtered.length !== 1 ? 's' : ''}
          {statusF !== 'all' || methodF !== 'all' ? ' (filtered)' : ''}
        </p>

        <AppTable rows={filtered} showFollowUp />
      </div>
    )
  }
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add frontend/src/pages/History.jsx
  git commit -m "feat: add History page with filter bar"
  ```

---

## Task 13: Wire React Router in main.jsx

**Files:**
- Modify: `frontend/src/main.jsx`
- Delete: `frontend/src/App.jsx` (replaced by page routing)
- Delete: `frontend/src/App.css` (if present)

- [ ] **Step 1: Replace `frontend/src/main.jsx`**

  ```jsx
  import React, { useState, useEffect } from 'react'
  import ReactDOM from 'react-dom/client'
  import { BrowserRouter, Routes, Route } from 'react-router-dom'
  import './globals.css'

  import Layout   from '@/components/Layout'
  import Overview from '@/pages/Overview'
  import Queue    from '@/pages/Queue'
  import History  from '@/pages/History'
  import { getStats } from '@/lib/api'

  function App() {
    const [dryRun, setDryRun] = useState(false)

    useEffect(() => {
      getStats().then(s => setDryRun(s.dry_run)).catch(() => {})
    }, [])

    return (
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout dryRun={dryRun} />}>
            <Route index         element={<Overview />} />
            <Route path="queue"   element={<Queue />} />
            <Route path="history" element={<History />} />
          </Route>
        </Routes>
      </BrowserRouter>
    )
  }

  ReactDOM.createRoot(document.getElementById('root')).render(<App />)
  ```

- [ ] **Step 2: Remove Vite scaffold files that are no longer needed**

  ```bash
  rm -f frontend/src/App.jsx frontend/src/App.css frontend/public/vite.svg frontend/src/assets/react.svg
  ```

- [ ] **Step 3: Start both servers and verify all three pages render**

  ```bash
  # Terminal 1
  python main.py

  # Terminal 2
  cd frontend && npm run dev
  ```

  Open `http://localhost:5173` — confirm:
  - Overview loads with 6 stat cards
  - Sidebar navigation links work
  - `/queue` and `/history` pages load without errors

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/main.jsx
  git rm --cached frontend/src/App.jsx frontend/src/App.css 2>/dev/null || true
  git commit -m "feat: wire React Router — Overview, Queue, History pages"
  ```

---

## Task 14: Production build + FastAPI StaticFiles mount

**Files:**
- Modify: `app/dashboard/main.py` (add StaticFiles mount at end of file)

- [ ] **Step 1: Build the React app**

  ```bash
  cd frontend && npm run build
  ```

  Expected: `frontend/dist/` is created with `index.html` and `assets/`.

- [ ] **Step 2: Add StaticFiles mount to `app/dashboard/main.py`**

  At the very end of the file, after all route definitions, add:

  ```python
  # Must be registered last — serves frontend/dist/ at "/" after all /api/* routes
  from fastapi.staticfiles import StaticFiles as _StaticFiles
  _dist = Path("frontend/dist")
  if _dist.exists():
      app.mount("/", _StaticFiles(directory=_dist, html=True), name="frontend")
  ```

- [ ] **Step 3: Restart FastAPI and verify production mode works**

  ```bash
  python main.py
  ```

  Open `http://localhost:8000` — confirm the React app loads (not the old Jinja2 template).
  Open `http://localhost:8000/queue` — confirm React Router handles the route (not 404).
  Run `curl -s http://localhost:8000/api/stats` — confirm API still responds.

- [ ] **Step 4: Commit**

  ```bash
  git add app/dashboard/main.py frontend/dist/
  git commit -m "feat: mount React build to FastAPI for production serving"
  ```

---

## Task 15: Remove old Jinja2 templates and routes

> Only do this task after verifying the React app works correctly against live data in both dev and production modes.

**Files:**
- Modify: `app/dashboard/main.py` — remove 3 HTML routes + Jinja2 imports
- Delete: `app/dashboard/templates/dashboard.html`
- Delete: `app/dashboard/templates/queue.html`
- Delete: `app/dashboard/templates/history.html`

- [ ] **Step 1: Remove the Jinja2 HTML routes from `app/dashboard/main.py`**

  Delete these lines:
  ```python
  from fastapi.responses import HTMLResponse, JSONResponse
  from fastapi.templating import Jinja2Templates
  templates = Jinja2Templates(directory="app/dashboard/templates")
  ```

  Replace with:
  ```python
  from fastapi.responses import JSONResponse
  ```

  Delete the three route functions: `dashboard()`, `review_queue()`, `history()` (the `GET /`, `GET /queue`, `GET /history` handlers that return `TemplateResponse`).

- [ ] **Step 2: Delete the template files**

  ```bash
  rm app/dashboard/templates/dashboard.html
  rm app/dashboard/templates/queue.html
  rm app/dashboard/templates/history.html
  ```

- [ ] **Step 3: Verify FastAPI still starts without errors**

  ```bash
  python main.py
  ```

  Expected: no import errors, `http://localhost:8000` still serves the React app.

- [ ] **Step 4: Commit**

  ```bash
  git add app/dashboard/main.py
  git rm app/dashboard/templates/dashboard.html \
         app/dashboard/templates/queue.html \
         app/dashboard/templates/history.html
  git commit -m "chore: remove Jinja2 templates — React frontend is live"
  ```

---

## Self-Review

**Spec coverage:**
- ✓ GET /api/stats, /api/applications, /api/queue, /api/history — Task 1
- ✓ POST /api/run-now, /api/apply/{id}, /api/mark-applied/{id} aliases — Task 1
- ✓ Vite proxy /api/* → :8000 — Task 2
- ✓ Tailwind ONYX/OLIVE/BONE palette — Task 3
- ✓ shadcn/ui CSS vars mapped to palette — Task 3
- ✓ Google Fonts (Crimson Text + IBM Plex Mono) in index.html — Task 2
- ✓ api.js named exports — Task 4
- ✓ Layout: 220px ONYX sidebar, bone topbar, olive active link, pipeline dot, Run Now button, DRY RUN pill — Task 5
- ✓ StatCard — Task 6
- ✓ AppTable with showFollowUp mode for History — Task 7
- ✓ NotifPanel — Task 8
- ✓ Overview: 6 stat cards + AppTable — Task 9
- ✓ JobCard: retry + mark-applied with animated removal — Task 10
- ✓ Queue: alert banner, empty state — Task 11
- ✓ History: filter bar (status + method), record count, AppTable with follow-up flags — Task 12
- ✓ React Router wiring — Task 13
- ✓ Production build + StaticFiles mount — Task 14
- ✓ Remove old Jinja2 templates — Task 15

**Type consistency:** `retryApply(id)` and `markApplied(id)` in api.js match usage in JobCard. `showFollowUp` prop name is consistent between AppTable definition and History/Overview usage. `onRemove(job.id)` in JobCard matches `removeJob(id)` signature in Queue.

**Ambiguity resolved:** Queue badge in sidebar uses `unread` notification count (not `needs_review` count) — matches Layout implementation. CV download link (`/api/cv/${id}`) does not yet exist in the backend — the cell shows `—` gracefully when `cv_path` is null, so this is not a blocker.

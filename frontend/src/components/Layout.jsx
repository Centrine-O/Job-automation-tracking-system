import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
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
          <p className="font-mono text-[10px] tracking-widest text-bone/40 uppercase mb-1">JOB AUTOMATION</p>
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

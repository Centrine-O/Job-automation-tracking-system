import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { getSystemStatus, getSystemHealth } from '@/lib/api'

const STAGE_LABELS = {
  idle:              'Idle',
  scraping:          'Scraping Jobs',
  scoring:           'Scoring Jobs',
  generating_cvs:    'Generating CVs',
  submitting:        'Submitting Applications',
  detecting_replies: 'Detecting Replies',
  checking_followups:'Checking Follow-ups',
  sending_digest:    'Sending Digest',
}

const STATUS_RING = {
  ok:    'border-emerald-300 bg-emerald-50',
  warn:  'border-amber-300  bg-amber-50',
  error: 'border-red-300    bg-red-50',
}
const STATUS_DOT = {
  ok:    'bg-emerald-500',
  warn:  'bg-amber-400',
  error: 'bg-red-500',
}
const STATUS_TEXT = {
  ok:    'text-emerald-700',
  warn:  'text-amber-700',
  error: 'text-red-700',
}

function fmt(isoUtc) {
  if (!isoUtc) return '—'
  const d = new Date(isoUtc.endsWith('Z') ? isoUtc : isoUtc + 'Z')
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtTime(isoUtc) {
  if (!isoUtc) return '—'
  const d = new Date(isoUtc.endsWith('Z') ? isoUtc : isoUtc + 'Z')
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function System() {
  const [status,  setStatus]  = useState(null)
  const [health,  setHealth]  = useState(null)
  const [error,   setError]   = useState(null)
  const [tick,    setTick]    = useState(0)

  const fetchAll = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([getSystemStatus(), getSystemHealth()])
      setStatus(s)
      setHealth(h)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(() => { fetchAll(); setTick(t => t + 1) }, 5000)
    return () => clearInterval(id)
  }, [fetchAll])

  if (error && !status) return <p className="font-serif text-red-600">{error}</p>
  if (!status) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>

  const { pipeline, scheduled } = status
  const isActive = pipeline.stage !== 'idle'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-3xl font-bold text-onyx">System</h1>
        <span className="font-mono text-[10px] text-onyx-dim">
          auto-refresh every 5s
        </span>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* ── Pipeline Monitor ── */}
        <div className="bg-white rounded-lg border border-bone-2 p-5 flex flex-col gap-5">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] tracking-widest uppercase text-onyx-dim">Pipeline Monitor</p>
            <span className={`w-2 h-2 rounded-full transition-colors ${isActive ? 'bg-olive animate-pulse' : 'bg-bone-2'}`} />
          </div>

          {/* Current stage */}
          <div>
            <p className="font-mono text-[9px] tracking-widest uppercase text-onyx-dim mb-1">Current Stage</p>
            <motion.p
              key={pipeline.stage}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`font-serif text-2xl font-bold leading-tight ${isActive ? 'text-olive' : 'text-onyx-dim'}`}
            >
              {STAGE_LABELS[pipeline.stage] ?? pipeline.stage}
            </motion.p>
            {isActive && pipeline.stage_started_at && (
              <p className="font-mono text-[10px] text-onyx-dim mt-0.5">
                started {fmtTime(pipeline.stage_started_at)}
              </p>
            )}
          </div>

          {/* Last completed */}
          <div>
            <p className="font-mono text-[9px] tracking-widest uppercase text-onyx-dim mb-1">Last Completed</p>
            <p className="font-mono text-xs text-onyx">
              {pipeline.last_stage ? `${STAGE_LABELS[pipeline.last_stage] ?? pipeline.last_stage} — ` : ''}{fmt(pipeline.last_run_at)}
            </p>
          </div>

          {/* Error banner */}
          {pipeline.error && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2">
              <p className="font-mono text-[10px] text-red-600 break-all">{pipeline.error}</p>
            </div>
          )}

          {/* Scheduled jobs */}
          <div className="flex-1">
            <p className="font-mono text-[9px] tracking-widest uppercase text-onyx-dim mb-2">Scheduled Jobs</p>
            <div className="divide-y divide-bone-1">
              {Object.entries(scheduled).map(([id, job]) => (
                <div key={id} className="flex items-center justify-between py-1.5">
                  <span className="font-mono text-[11px] text-onyx">{job.label}</span>
                  <span className="font-mono text-[10px] text-onyx-dim tabular-nums">
                    {fmtTime(job.next_run)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Services Health ── */}
        <div className="bg-white rounded-lg border border-bone-2 p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] tracking-widest uppercase text-onyx-dim">Services Health</p>
            {health?.checked_at && (
              <p className="font-mono text-[9px] text-onyx-dim">
                checked {fmtTime(health.checked_at)}
              </p>
            )}
          </div>

          {health?.services && Object.keys(health.services).length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(health.services).map(([key, svc], i) => (
                <motion.div
                  key={key}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.04 }}
                  className={`flex items-start gap-2.5 px-3 py-2.5 rounded border ${STATUS_RING[svc.status] ?? STATUS_RING.warn}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-[3px] ${STATUS_DOT[svc.status] ?? STATUS_DOT.warn}`} />
                  <div className="min-w-0">
                    <p className={`font-mono text-[10px] font-semibold leading-tight ${STATUS_TEXT[svc.status] ?? STATUS_TEXT.warn}`}>
                      {svc.label}
                    </p>
                    {svc.detail && (
                      <p className="font-mono text-[9px] text-onyx-dim mt-0.5 leading-tight">
                        {svc.detail}
                      </p>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="font-mono text-xs text-onyx-dim animate-pulse">Running health checks…</p>
          )}

          <p className="font-mono text-[9px] text-onyx-dim mt-auto">
            Health checks run every 60 s in the background
          </p>
        </div>
      </div>
    </div>
  )
}

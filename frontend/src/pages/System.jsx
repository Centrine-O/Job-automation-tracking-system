import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { getSystemStatus, getSystemHealth } from '@/lib/api'

const STAGE_LABELS = {
  idle:               'Idle',
  scraping:           'Scraping Jobs',
  scoring:            'Scoring Jobs',
  generating_cvs:     'Generating CVs',
  submitting:         'Submitting',
  detecting_replies:  'Detecting Replies',
  checking_followups: 'Checking Follow-ups',
  sending_digest:     'Sending Digest',
}

const PIPELINE_STEPS = [
  { key: 'scraping',           short: 'Scrape' },
  { key: 'scoring',            short: 'Score' },
  { key: 'generating_cvs',     short: 'CVs' },
  { key: 'submitting',         short: 'Submit' },
  { key: 'detecting_replies',  short: 'Replies' },
  { key: 'checking_followups', short: 'Follow-up' },
  { key: 'sending_digest',     short: 'Digest' },
]

const SVC_STATUS = {
  ok:    { dot: 'bg-emerald-400', badge: 'text-emerald-500', label: 'OK' },
  warn:  { dot: 'bg-amber-400',   badge: 'text-amber-500',   label: 'WARN' },
  error: { dot: 'bg-red-400',     badge: 'text-red-500',     label: 'ERR' },
}

function parseDate(iso) {
  if (!iso) return null
  const d = new Date(iso)
  return isNaN(d.getTime()) ? null : d
}

function clockTime(iso) {
  const d = parseDate(iso)
  return d ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'
}

function relTime(iso) {
  const d = parseDate(iso)
  if (!d) return ''
  const ms = d - Date.now()
  const abs = Math.abs(ms)
  if (abs < 60000) return 'now'
  const h = Math.floor(abs / 3600000)
  const m = Math.floor((abs % 3600000) / 60000)
  const str = h > 0 ? `${h}h ${m}m` : `${m}m`
  return ms > 0 ? `in ${str}` : `${str} ago`
}

export default function System() {
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [error,  setError]  = useState(null)

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
    const id = setInterval(fetchAll, 5000)
    return () => clearInterval(id)
  }, [fetchAll])

  if (error && !status) return <p className="font-serif text-red-600">{error}</p>
  if (!status) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>

  const { pipeline, scheduled } = status
  const isActive = pipeline.stage !== 'idle'

  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between">
        <h1 className="font-serif text-3xl font-bold text-onyx">System</h1>
        <span className="font-mono text-[10px] text-onyx-dim tabular-nums">↻ 5s</span>
      </div>

      {/* ── Pipeline — dark card ── */}
      <div className="bg-onyx rounded-lg overflow-hidden">
        {/* Header row */}
        <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-white/5">
          <p className="font-mono text-[9px] tracking-[0.18em] uppercase text-bone/40">Pipeline Monitor</p>
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-olive animate-pulse' : 'bg-white/15'}`} />
            <span className="font-mono text-[10px] text-bone/40">{isActive ? 'running' : 'idle'}</span>
          </div>
        </div>

        {/* Stage flow */}
        <div className="px-5 py-4 flex items-center gap-px">
          {PIPELINE_STEPS.map((step, i) => {
            const active = pipeline.stage === step.key
            return (
              <div key={step.key} className="flex items-center gap-px flex-1 min-w-0">
                <motion.div
                  animate={active ? { opacity: [1, 0.55, 1] } : {}}
                  transition={active ? { repeat: Infinity, duration: 1.4, ease: 'easeInOut' } : {}}
                  className={`flex-1 py-2 text-center rounded-sm transition-all duration-300 ${
                    active ? 'bg-olive' : 'bg-white/[0.04]'
                  } ${i === 0 ? 'rounded-l' : ''} ${i === PIPELINE_STEPS.length - 1 ? 'rounded-r' : ''}`}
                >
                  <p className={`font-mono text-[9px] tracking-wide truncate px-1 ${
                    active ? 'text-white font-semibold' : 'text-bone/25'
                  }`}>
                    {step.short}
                  </p>
                </motion.div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <span className="text-white/8 font-mono text-[8px] select-none">│</span>
                )}
              </div>
            )
          })}
        </div>

        {/* Stage detail + last run */}
        <div className="px-5 pb-4 flex items-end justify-between">
          <div>
            <p className="font-mono text-[9px] tracking-[0.15em] uppercase text-bone/30 mb-0.5">Current stage</p>
            <motion.p
              key={pipeline.stage}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className={`font-serif text-2xl font-bold leading-none ${isActive ? 'text-olive' : 'text-bone/25'}`}
            >
              {STAGE_LABELS[pipeline.stage] ?? pipeline.stage}
            </motion.p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[9px] tracking-[0.15em] uppercase text-bone/30 mb-0.5">Last completed</p>
            <p className="font-mono text-xs text-bone/50">
              {pipeline.last_stage
                ? `${STAGE_LABELS[pipeline.last_stage] ?? pipeline.last_stage} · ${clockTime(pipeline.last_run_at)}`
                : '—'}
            </p>
          </div>
        </div>

        {pipeline.error && (
          <div className="mx-5 mb-4 rounded border border-red-500/25 bg-red-500/8 px-3 py-2">
            <p className="font-mono text-[10px] text-red-400 break-all">{pipeline.error}</p>
          </div>
        )}
      </div>

      {/* ── Bottom row ── */}
      <div className="grid grid-cols-2 gap-5">

        {/* Scheduled Jobs */}
        <div className="bg-white rounded-lg border border-bone-2 p-4">
          <p className="font-mono text-[9px] tracking-[0.18em] uppercase text-onyx-dim mb-3">Scheduled Jobs</p>
          <div className="space-y-0">
            {Object.entries(scheduled).map(([id, job], i) => (
              <motion.div
                key={id}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center justify-between py-2 border-b border-bone-1 last:border-0"
              >
                <span className="font-mono text-[11px] text-onyx">{job.label}</span>
                <div className="text-right">
                  <p className="font-mono text-[11px] text-onyx tabular-nums">{clockTime(job.next_run)}</p>
                  <p className="font-mono text-[9px] text-onyx-dim">{relTime(job.next_run)}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Services Health */}
        <div className="bg-white rounded-lg border border-bone-2 p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="font-mono text-[9px] tracking-[0.18em] uppercase text-onyx-dim">Services</p>
            {health?.checked_at && (
              <p className="font-mono text-[9px] text-onyx-dim">
                checked {clockTime(health.checked_at)}
              </p>
            )}
          </div>
          {health?.services && Object.keys(health.services).length > 0 ? (
            <div className="space-y-1">
              {Object.entries(health.services).map(([key, svc], i) => {
                const c = SVC_STATUS[svc.status] ?? SVC_STATUS.warn
                return (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, x: 6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="flex items-center gap-2.5 px-2.5 py-1.5 rounded bg-bone-1 group"
                  >
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${c.dot}`} />
                    <span className="font-mono text-[10px] text-onyx flex-1">{svc.label}</span>
                    {svc.detail ? (
                      <span className="font-mono text-[8px] text-onyx-dim truncate max-w-[100px]">{svc.detail}</span>
                    ) : (
                      <span className={`font-mono text-[8px] tracking-widest font-bold ${c.badge}`}>{c.label}</span>
                    )}
                  </motion.div>
                )
              })}
            </div>
          ) : (
            <p className="font-mono text-xs text-onyx-dim animate-pulse">Running checks…</p>
          )}
          <p className="font-mono text-[8px] text-onyx-dim/50 mt-3">refreshes every 60 s</p>
        </div>
      </div>
    </div>
  )
}

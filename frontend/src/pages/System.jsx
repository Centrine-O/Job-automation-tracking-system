import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { getSystemStatus, getSystemHealth } from '@/lib/api'

const STAGE_LABELS = {
  idle:     'Idle',
  scraping: 'Scraping Jobs',
  scoring:  'Scoring Jobs',
}

const PIPELINE_STEPS = [
  { key: 'scraping', label: 'Scrape' },
  { key: 'scoring',  label: 'Score' },
]

const SVC = {
  ok:    { dot: 'bg-olive',       card: 'bg-white   border-bone-2',         name: 'text-onyx'        },
  warn:  { dot: 'bg-onyx-dim',    card: 'bg-bone-1  border-bone-3',         name: 'text-onyx-dim'    },
  error: { dot: 'bg-destructive', card: 'bg-bone-1  border-destructive',    name: 'text-destructive' },
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
      setStatus(s); setHealth(h); setError(null)
    } catch (e) { setError(e.message) }
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
        <span className="font-mono text-[10px] text-onyx-dim">↻ 5s</span>
      </div>

      {/* ── Pipeline Monitor ── */}
      <div className="bg-white rounded-lg border border-bone-2 p-5">
        <div className="flex items-center justify-between mb-5">
          <p className="font-mono text-[9px] tracking-[0.18em] uppercase text-onyx-dim">Pipeline Monitor</p>
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isActive ? 'bg-olive animate-pulse' : 'bg-bone-2'}`} />
            <span className="font-mono text-[10px] text-onyx-dim">{isActive ? 'running' : 'idle'}</span>
          </div>
        </div>

        <div className="flex gap-8">
          {/* Stage name */}
          <div className="w-48 flex-shrink-0">
            <p className="font-mono text-[9px] tracking-[0.15em] uppercase text-onyx-dim mb-1">Current Stage</p>
            <motion.p
              key={pipeline.stage}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              className={`font-serif text-2xl font-bold leading-tight ${isActive ? 'text-olive' : 'text-onyx-dim'}`}
            >
              {STAGE_LABELS[pipeline.stage] ?? pipeline.stage}
            </motion.p>
            {pipeline.last_run_at && (
              <p className="font-mono text-[10px] text-onyx-dim mt-2">
                Last run {clockTime(pipeline.last_run_at)}
              </p>
            )}
          </div>

          {/* Stage pills */}
          <div className="flex-1 flex items-center flex-wrap gap-2">
            {PIPELINE_STEPS.map((step, i) => {
              const active = pipeline.stage === step.key
              return (
                <motion.div
                  key={step.key}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <motion.span
                    animate={active ? { opacity: [1, 0.55, 1] } : {}}
                    transition={active ? { repeat: Infinity, duration: 1.4, ease: 'easeInOut' } : {}}
                    className={`inline-flex items-center gap-1.5 font-mono text-[10px] px-3 py-1.5 rounded-full border transition-all duration-300 ${
                      active
                        ? 'bg-olive text-white border-olive shadow-sm'
                        : 'bg-transparent text-onyx-dim border-bone-2 hover:border-onyx-dim'
                    }`}
                  >
                    {active && <span className="w-1 h-1 rounded-full bg-white/70 flex-shrink-0" />}
                    {step.label}
                  </motion.span>
                </motion.div>
              )
            })}
          </div>
        </div>

        {pipeline.error && (
          <div className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2">
            <p className="font-mono text-[10px] text-red-600">{pipeline.error}</p>
          </div>
        )}
      </div>

      {/* ── Bottom row ── */}
      <div className="grid grid-cols-2 gap-5">

        {/* Scheduled Jobs */}
        <div className="bg-white rounded-lg border border-bone-2 p-4">
          <p className="font-mono text-[9px] tracking-[0.18em] uppercase text-onyx-dim mb-3">Scheduled Jobs</p>
          <div>
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
              <p className="font-mono text-[9px] text-onyx-dim">checked {clockTime(health.checked_at)}</p>
            )}
          </div>
          {health?.services && Object.keys(health.services).length > 0 ? (
            <div className="grid grid-cols-2 gap-1.5">
              {Object.entries(health.services).map(([key, svc], i) => {
                const c = SVC[svc.status] ?? SVC.warn
                return (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.04 }}
                    className={`flex items-start gap-2 px-3 py-2 rounded border ${c.card}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-[3px] ${c.dot}`} />
                    <div className="min-w-0">
                      <p className={`font-mono text-[10px] font-semibold leading-tight ${c.name}`}>{svc.label}</p>
                      {svc.detail && (
                        <p className="font-mono text-[8px] text-onyx-dim mt-0.5 leading-tight">{svc.detail}</p>
                      )}
                    </div>
                  </motion.div>
                )
              })}
            </div>
          ) : (
            <p className="font-mono text-xs text-onyx-dim animate-pulse">Running checks…</p>
          )}
          <p className="font-mono text-[8px] text-onyx-dim/60 mt-3">refreshes every 60 s</p>
        </div>
      </div>
    </div>
  )
}

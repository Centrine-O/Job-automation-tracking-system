import { useState, useEffect } from 'react'
import { getQueue, dismissJob, applyJob } from '@/lib/api'

export default function Queue() {
  const [jobs, setJobs]             = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [pending, setPending]       = useState(false)
  const [actionError, setActionError] = useState(null)

  const selected = jobs.find(j => j.id === selectedId) ?? null

  useEffect(() => {
    getQueue()
      .then(data => { setJobs(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  function removeJob(id) {
    setJobs(prev => prev.filter(j => j.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  async function handleDismiss(job) {
    if (pending) return
    setPending(true)
    setActionError(null)
    try {
      await dismissJob(job.id)
      removeJob(job.id)
    } catch (e) {
      setActionError('Failed to dismiss job. Please try again.')
    } finally {
      setPending(false)
    }
  }

  async function handleApply(job) {
    if (pending) return
    setPending(true)
    setActionError(null)
    try {
      await applyJob(job.id)
      removeJob(job.id)
    } catch (e) {
      setActionError('Failed to record application. Please try again.')
    } finally {
      setPending(false)
    }
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
                onClick={() => setSelectedId(job.id)}
                className={`w-full text-left rounded-lg border px-4 py-3 transition-colors ${
                  selectedId === job.id
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
                    <p className="font-mono text-xs text-onyx-dim leading-relaxed">
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
                      className="font-mono text-xs bg-olive text-bone px-4 py-2 rounded border border-olive hover:bg-olive/90 transition-colors disabled:opacity-50 disabled:pointer-events-none"
                      aria-disabled={pending}
                      tabIndex={pending ? -1 : undefined}
                    >
                      Open Job ↗
                    </a>
                  )}
                  <button
                    onClick={() => handleApply(selected)}
                    disabled={pending}
                    className="font-mono text-xs bg-onyx text-bone px-4 py-2 rounded border border-onyx hover:bg-onyx/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Mark Applied ✓
                  </button>
                  <button
                    onClick={() => handleDismiss(selected)}
                    disabled={pending}
                    className="font-mono text-xs text-onyx-dim px-4 py-2 rounded border border-bone-2 hover:border-onyx-dim hover:text-onyx transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Dismiss
                  </button>
                </div>

                {actionError && (
                  <p className="font-mono text-xs text-red-600">{actionError}</p>
                )}
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

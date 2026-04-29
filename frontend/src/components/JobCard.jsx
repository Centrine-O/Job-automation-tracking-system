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

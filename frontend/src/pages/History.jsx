import { useState, useEffect, useCallback, useRef } from 'react'
import { getHistory, updateStatus, updateNotes } from '@/lib/api'

const STATUSES = ['applied', 'replied', 'offer', 'rejected', 'ghosted']

const STATUS_STYLES = {
  applied:  'bg-bone-1 text-onyx-dim border-bone-2',
  replied:  'bg-amber-50 text-amber-700 border-amber-200',
  offer:    'bg-olive/10 text-olive border-olive/30',
  rejected: 'bg-red-50 text-red-600 border-red-200',
  ghosted:  'bg-gray-50 text-gray-400 border-gray-200',
}

function StatusPills({ appId, current, onChange }) {
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState(null)

  async function handleClick(status) {
    if (status === current || saving) return
    setSaving(true)
    setError(null)
    try {
      await updateStatus(appId, status)
      onChange(appId, status)
    } catch {
      setError('Failed to update status')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => handleClick(s)}
            disabled={saving}
            className={`font-mono text-[10px] px-2 py-1 rounded border transition-colors capitalize ${
              s === current
                ? STATUS_STYLES[s] + ' font-semibold'
                : 'bg-white text-onyx-dim/40 border-bone-1 hover:border-bone-3 hover:text-onyx-dim'
            }`}
          >
            {s}
          </button>
        ))}
      </div>
      {error && <p className="font-mono text-[9px] text-red-500 mt-1">{error}</p>}
    </div>
  )
}

function NotesField({ appId, initial }) {
  const [notes, setNotes] = useState(initial || '')
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const savedRef = useRef(initial || '')

  useEffect(() => {
    setNotes(initial || '')
    savedRef.current = initial || ''
  }, [appId])

  async function handleBlur() {
    if (notes === savedRef.current) return
    setError(null)
    try {
      await updateNotes(appId, notes)
      savedRef.current = notes
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
    } catch {
      setError('Failed to save notes')
    }
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={notes}
        onChange={e => setNotes(e.target.value)}
        onBlur={handleBlur}
        placeholder="Add notes…"
        className="w-full font-mono text-xs text-onyx-dim bg-transparent border-b border-bone-1 focus:border-onyx-dim outline-none py-0.5 placeholder:text-onyx-dim/30"
      />
      {saved && <span className="absolute right-0 top-0 font-mono text-[9px] text-olive">saved</span>}
      {error && <span className="absolute right-0 top-0 font-mono text-[9px] text-red-500">{error}</span>}
    </div>
  )
}

export default function History() {
  const [rows, setRows]         = useState([])
  const [statusF, setStatusF]   = useState('all')
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getHistory()
      .then(data => { setRows(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const handleStatusChange = useCallback((appId, newStatus) => {
    setRows(prev => prev.map(r => r.id === appId ? { ...r, status: newStatus } : r))
  }, [])

  const filtered = statusF === 'all' ? rows : rows.filter(r => r.status === statusF)

  const btnBase   = 'font-mono text-xs px-3 py-1.5 rounded border transition-colors'
  const btnActive = `${btnBase} bg-onyx text-bone border-onyx`
  const btnIdle   = `${btnBase} border-bone-2 text-onyx-dim hover:border-onyx hover:text-onyx`

  if (loading) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>
  if (error)   return <p className="font-serif text-red-600">{error}</p>

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-3xl font-bold text-onyx">History</h1>

      <div className="flex flex-wrap gap-2">
        <button onClick={() => setStatusF('all')} className={statusF === 'all' ? btnActive : btnIdle}>All</button>
        {STATUSES.map(s => (
          <button key={s} onClick={() => setStatusF(statusF === s ? 'all' : s)}
            className={statusF === s ? btnActive : btnIdle}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      <p className="font-mono text-xs text-onyx-dim">
        {filtered.length} record{filtered.length !== 1 ? 's' : ''}
        {statusF !== 'all' ? ' (filtered)' : ''}
      </p>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-lg border border-bone-2 p-12 text-center">
          <p className="font-serif text-xl text-onyx-dim">No applications yet.</p>
          <p className="font-mono text-xs text-onyx-dim/60 mt-2">Mark jobs as applied from the Queue.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(row => (
            <div key={row.id} className="bg-white rounded-lg border border-bone-2 px-5 py-4 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-serif text-base font-semibold text-onyx">{row.title}</p>
                  <p className="font-mono text-xs text-onyx-dim mt-0.5">
                    {row.company}
                    {row.submitted_at ? ` · applied ${row.submitted_at.slice(0, 10)}` : ''}
                  </p>
                </div>
                {row.apply_url && (
                  <a
                    href={row.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-[10px] text-onyx-dim/50 hover:text-olive transition-colors flex-shrink-0"
                  >
                    Open ↗
                  </a>
                )}
              </div>
              <StatusPills appId={row.id} current={row.status} onChange={handleStatusChange} />
              <NotesField appId={row.id} initial={row.notes} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

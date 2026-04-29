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

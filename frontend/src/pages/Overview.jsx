import { useState, useEffect } from 'react'
import StatCard from '@/components/StatCard'
import { getStats, getHistory } from '@/lib/api'

export default function Overview() {
  const [stats, setStats] = useState(null)
  const [apps, setApps]   = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getStats(), getHistory()])
      .then(([s, a]) => { setStats(s); setApps(a) })
      .catch(e => setError(e.message))
  }, [])

  if (error)  return <p className="font-serif text-red-600">{error}</p>
  if (!stats) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>

  const recent = apps.slice(0, 5)

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-3xl font-bold text-onyx">Overview</h1>

      <div className="grid grid-cols-6 gap-3">
        <StatCard label="Scraped"   value={stats.total_jobs}    index={0} />
        <StatCard label="Qualified" value={stats.qualified}     index={1} accent />
        <StatCard label="Applied"   value={stats.total_applied} index={2} />
        <StatCard label="Replied"   value={stats.replied}       index={3} />
        <StatCard label="Offers"    value={stats.offers}        index={4} />
        <StatCard label="Dismissed" value={stats.dismissed}     index={5} />
      </div>

      {recent.length > 0 && (
        <div>
          <h2 className="font-serif text-xl font-semibold text-onyx mb-3">Recent Applications</h2>
          <div className="space-y-2">
            {recent.map(row => (
              <div key={row.id} className="bg-white rounded-lg border border-bone-2 px-4 py-3 flex items-center justify-between">
                <div>
                  <p className="font-serif text-sm font-semibold text-onyx">{row.title}</p>
                  <p className="font-mono text-xs text-onyx-dim">{row.company}</p>
                </div>
                <span className={`font-mono text-[10px] px-2 py-1 rounded border capitalize
                  ${row.status === 'replied' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                    row.status === 'offer'   ? 'bg-olive/10 text-olive border-olive/30' :
                    'bg-bone-1 text-onyx-dim border-bone-2'}`}>
                  {row.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

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

      <div className="grid grid-cols-6 gap-3">
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

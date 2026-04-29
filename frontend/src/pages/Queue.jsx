import { useState, useEffect } from 'react'
import JobCard from '@/components/JobCard'
import { getQueue } from '@/lib/api'

export default function Queue() {
  const [jobs, setJobs]   = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getQueue()
      .then(data => { setJobs(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  function removeJob(id) {
    setJobs(prev => prev.filter(j => j.id !== id))
  }

  if (loading) return <p className="font-mono text-onyx-dim text-sm animate-pulse">Loading…</p>
  if (error)   return <p className="font-serif text-red-600">{error}</p>

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-3xl font-bold text-onyx">Review Queue</h1>

      {jobs.length > 0 ? (
        <>
          <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 border border-red-100">
            <span className="font-mono text-[10px] tracking-widest text-red-600 uppercase">
              {jobs.length} {jobs.length === 1 ? 'job requires' : 'jobs require'} attention
            </span>
          </div>
          <div className="grid gap-4">
            {jobs.map(job => (
              <JobCard key={job.id} job={job} onRemove={removeJob} />
            ))}
          </div>
        </>
      ) : (
        <div className="bg-white rounded-lg border border-bone-2 p-12 text-center">
          <p className="font-serif text-xl text-onyx-dim">Queue is clear.</p>
          <p className="font-mono text-xs text-onyx-dim/60 mt-2">All jobs processed successfully.</p>
        </div>
      )}
    </div>
  )
}

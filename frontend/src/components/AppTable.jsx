function statusClass(status) {
  const map = {
    applied:      'bg-olive/10 text-olive',
    replied:      'bg-blue-50 text-blue-700',
    needs_review: 'bg-red-50 text-red-600',
    skipped:      'bg-bone text-onyx-dim',
  }
  return map[status] ?? 'bg-bone text-onyx-dim'
}

export default function AppTable({ rows, showFollowUp = false }) {
  if (!rows?.length) {
    return (
      <div className="bg-white rounded-lg border border-bone-2 p-8 text-center">
        <p className="font-serif text-onyx-dim">No applications yet.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-bone-2 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-bone-2 bg-bone/40">
            <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">#</th>
            <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">ROLE / COMPANY</th>
            <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">METHOD</th>
            <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">ATS</th>
            {showFollowUp && <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">SKILL</th>}
            <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">STATUS</th>
            <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">SUBMITTED</th>
            {showFollowUp && (
              <>
                <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">NOTES</th>
                <th className="font-mono text-[10px] tracking-widest text-onyx-dim px-4 py-2 text-left">CV</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id} className="border-b border-bone/60 last:border-0 hover:bg-bone/20 transition-colors">
              <td className="font-mono text-xs text-onyx-dim px-4 py-3">{i + 1}</td>
              <td className="px-4 py-3">
                <p className="font-serif font-semibold text-onyx">{row.title}</p>
                <p className="font-mono text-xs text-onyx-dim">{row.company}</p>
              </td>
              <td className="font-mono text-xs text-onyx-dim px-4 py-3 uppercase">
                {row.apply_method || row.job_apply_method || '—'}
              </td>
              <td className="font-mono text-xs px-4 py-3">
                {row.ats_score != null ? `${row.ats_score}%` : '—'}
              </td>
              {showFollowUp && (
                <td className="font-mono text-xs px-4 py-3">
                  {row.skill_score != null ? `${row.skill_score}%` : '—'}
                </td>
              )}
              <td className="px-4 py-3">
                <span className={`font-mono text-[10px] px-2 py-0.5 rounded-full ${statusClass(row.status)}`}>
                  {row.status}
                </span>
                {showFollowUp && !row.follow_up_21_at && row.status === 'applied' && (
                  <span className="ml-1 font-mono text-[9px] px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-700">21d</span>
                )}
                {showFollowUp && !row.follow_up_30_at && row.status === 'applied' && (
                  <span className="ml-1 font-mono text-[9px] px-1.5 py-0.5 rounded bg-orange-50 text-orange-700">30d</span>
                )}
              </td>
              <td className="font-mono text-xs text-onyx-dim px-4 py-3">
                {row.submitted_at ? row.submitted_at.slice(0, 16).replace('T', ' ') : '—'}
              </td>
              {showFollowUp && (
                <>
                  <td className="font-serif text-xs text-onyx-dim px-4 py-3 max-w-[180px] truncate">{row.notes || '—'}</td>
                  <td className="px-4 py-3">
                    {row.cv_path ? (
                      <a
                        href={`/api/cv/${row.id}`}
                        className="font-mono text-[10px] text-olive hover:underline"
                        target="_blank" rel="noreferrer"
                      >PDF</a>
                    ) : '—'}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

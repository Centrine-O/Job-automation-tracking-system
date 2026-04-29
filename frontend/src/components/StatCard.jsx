export default function StatCard({ label, value, sub, accent = false }) {
  return (
    <div className={`bg-white rounded-lg p-5 border ${accent ? 'border-olive/40' : 'border-bone-2'}`}>
      <p className="font-mono text-[10px] tracking-widest uppercase text-onyx-dim mb-2">{label}</p>
      <p className={`font-serif text-5xl font-bold leading-none ${accent ? 'text-olive' : 'text-onyx'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="font-mono text-xs text-onyx-dim mt-2">{sub}</p>}
    </div>
  )
}

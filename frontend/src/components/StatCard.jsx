export default function StatCard({ label, value, sub, accent = false }) {
  return (
    <div className={`bg-white rounded-lg p-4 border ${accent ? 'border-olive/40' : 'border-bone-2'}`}>
      <p className="font-mono text-[9px] tracking-widest uppercase text-onyx-dim mb-1.5">{label}</p>
      <p className={`font-serif text-3xl font-bold leading-none ${accent ? 'text-olive' : 'text-onyx'}`}>
        {value ?? '—'}
      </p>
      {sub && <p className="font-mono text-[10px] text-onyx-dim mt-1.5">{sub}</p>}
    </div>
  )
}

export default function NotifPanel({ notifications = [] }) {
  return (
    <div className="w-72">
      <p className="font-mono text-[10px] tracking-widest text-onyx-dim mb-3 uppercase">Notifications</p>
      {notifications.length === 0 ? (
        <p className="font-serif text-sm text-onyx-dim">All clear — no notifications.</p>
      ) : (
        <ul className="space-y-2">
          {notifications.map(n => (
            <li key={n.id} className={`rounded p-2 ${n.read ? 'opacity-60' : 'bg-olive/5'}`}>
              <p className="font-serif text-sm font-semibold text-onyx">{n.title}</p>
              <p className="font-serif text-xs text-onyx-dim">{n.body}</p>
              <p className="font-mono text-[10px] text-onyx-dim/60 mt-0.5">{n.created_at?.slice(0, 16)}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

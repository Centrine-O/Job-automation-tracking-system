const checked = r => { if (!r.ok) throw new Error(`API error ${r.status}`); return r.json() }

export const getStats        = () => fetch('/api/stats').then(checked)
export const getQueue        = () => fetch('/api/queue').then(checked)
export const getHistory      = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return fetch(`/api/history${qs ? '?' + qs : ''}`).then(checked)
}
export const getApplications = () => fetch('/api/applications').then(checked)
export const getNotifications = () => fetch('/api/notifications').then(checked)
export const getUnreadCount  = () => fetch('/api/unread-count').then(checked)
export const runNow          = () => fetch('/api/run-now', { method: 'POST' }).then(checked)
export const getSystemStatus = () => fetch('/api/system/status').then(checked)
export const getSystemHealth = () => fetch('/api/system/health').then(checked)

export const dismissJob      = (id) =>
  fetch(`/api/jobs/${id}/dismiss`, { method: 'POST' }).then(checked)

export const applyJob        = (id) =>
  fetch(`/api/jobs/${id}/apply`, { method: 'POST' }).then(checked)

export const updateStatus    = (appId, status) =>
  fetch(`/api/applications/${appId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }).then(checked)

export const updateNotes     = (appId, notes) =>
  fetch(`/api/applications/${appId}/notes`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  }).then(checked)

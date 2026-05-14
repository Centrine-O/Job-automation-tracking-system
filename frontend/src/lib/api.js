export const getStats        = () => fetch('/api/stats').then(r => r.json())
export const getQueue        = () => fetch('/api/queue').then(r => r.json())
export const getHistory      = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return fetch(`/api/history${qs ? '?' + qs : ''}`).then(r => r.json())
}
export const getApplications = () => fetch('/api/applications').then(r => r.json())
export const getNotifications = () => fetch('/api/notifications').then(r => r.json())
export const getUnreadCount  = () => fetch('/api/unread-count').then(r => r.json())
export const runNow          = () => fetch('/api/run-now', { method: 'POST' }).then(r => r.json())
export const getSystemStatus = () => fetch('/api/system/status').then(r => r.json())
export const getSystemHealth = () => fetch('/api/system/health').then(r => r.json())

export const dismissJob      = (id) =>
  fetch(`/api/jobs/${id}/dismiss`, { method: 'POST' }).then(r => r.json())

export const applyJob        = (id) =>
  fetch(`/api/jobs/${id}/apply`, { method: 'POST' }).then(r => r.json())

export const updateStatus    = (appId, status) =>
  fetch(`/api/applications/${appId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  }).then(r => r.json())

export const updateNotes     = (appId, notes) =>
  fetch(`/api/applications/${appId}/notes`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  }).then(r => r.json())

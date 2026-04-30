export const getStats         = () => fetch('/api/stats').then(r => r.json())
export const getApplications  = () => fetch('/api/applications').then(r => r.json())
export const getQueue         = () => fetch('/api/queue').then(r => r.json())
export const getHistory       = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return fetch(`/api/history${qs ? '?' + qs : ''}`).then(r => r.json())
}
export const getNotifications = () => fetch('/api/notifications').then(r => r.json())
export const getUnreadCount   = () => fetch('/api/unread-count').then(r => r.json())
export const runNow           = () => fetch('/api/run-now', { method: 'POST' }).then(r => r.json())
export const retryApply       = (id) => fetch(`/api/apply/${id}`, { method: 'POST' }).then(r => r.json())
export const markApplied      = (id) => fetch(`/api/mark-applied/${id}`, { method: 'POST' }).then(r => r.json())
export const getSystemStatus  = () => fetch('/api/system/status').then(r => r.json())
export const getSystemHealth  = () => fetch('/api/system/health').then(r => r.json())

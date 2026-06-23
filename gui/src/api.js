// Kingdom API client
// Token is injected by Vite proxy server-side from /home/kingdom-os/.env
// Browser never sees KINGDOM_API_TOKEN
// Access control: VS Code tunnel + 127.0.0.1 binding

const BASE = '/api'

async function req(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' }
  }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

// Tasks
export const getTasks = (status) =>
  req('GET', status ? `/tasks?status=${status}` : '/tasks')
export const createTask = (title, description, task_type) =>
  req('POST', '/tasks', { title, description, task_type })
export const getTask = (id) => req('GET', `/tasks/${id}`)
export const completeTask = (id, actor = 'kingdom') =>
  req('POST', `/tasks/${id}/complete`, { actor })

// Runs
export const runTask = (id) => req('POST', `/tasks/${id}/run`)
export const getRuns = (taskId) => req('GET', `/tasks/${taskId}/runs`)
export const getRun = (id) => req('GET', `/runs/${id}`)
export const approveRun = (id, actor = 'kingdom', note = '') =>
  req('POST', `/runs/${id}/approve`, { actor, note })
export const rejectRun = (id, actor = 'kingdom', reason) =>
  req('POST', `/runs/${id}/reject`, { actor, reason })

// Daemon
export const getDaemonStatus = () => req('GET', '/daemon/status')
export const pauseDaemon = () => req('POST', '/daemon/pause')
export const resumeDaemon = () => req('POST', '/daemon/resume')

// Knowledge
export const getKnowledgeStatus = () => req('GET', '/knowledge/status')
export const ingestFile = (file_path) =>
  req('POST', '/knowledge/ingest/file', { file_path })
export const ingestDirectory = (dir_path, extensions = null) =>
  req('POST', '/knowledge/ingest/directory', { dir_path, extensions })
export const searchKnowledge = (query, n_results = 5) =>
  req('POST', '/knowledge/search', { query, n_results })

// Audit
export const getAuditLog = (limit = 50) => req('GET', `/audit?limit=${limit}`)

// Health
export const getHealth = () => req('GET', '/health')

import { useState, useEffect, useCallback } from 'react'
import { getHealth } from './api'
import TaskInput from './panels/TaskInput'
import TaskBoard from './panels/TaskBoard'
import ApprovalCentre from './panels/ApprovalCentre'
import DaemonControls from './panels/DaemonControls'
import KnowledgePanel from './panels/KnowledgePanel'
import AuditLog from './panels/AuditLog'

const PANELS = ['Tasks', 'Board', 'Approvals', 'Daemon', 'Knowledge', 'Audit']

const s = {
  app: { fontFamily: 'monospace', background: '#0d0d0d', minHeight: '100vh', color: '#e2e8f0' },
  header: { background: '#111', borderBottom: '1px solid #222', padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 16 },
  title: { fontSize: 16, fontWeight: 700, letterSpacing: 1, margin: 0 },
  dot: { width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block', marginRight: 8 },
  dotErr: { width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block', marginRight: 8 },
  nav: { display: 'flex', gap: 4, padding: '8px 20px', background: '#111', borderBottom: '1px solid #1a1a1a' },
  navBtn: { padding: '4px 12px', border: '1px solid #222', borderRadius: 4, background: 'none', color: '#64748b', cursor: 'pointer', fontSize: 12 },
  navBtnActive: { padding: '4px 12px', border: '1px solid #7c3aed', borderRadius: 4, background: '#7c3aed22', color: '#a78bfa', cursor: 'pointer', fontSize: 12 },
  content: { padding: 20, maxWidth: 1100, margin: '0 auto' },
  err: { textAlign: 'center', marginTop: 80, color: '#ef4444', fontSize: 14 },
}

export default function App() {
  const [panel, setPanel] = useState('Board')
  const [healthy, setHealthy] = useState(null)

  const checkHealth = useCallback(async () => {
    try { await getHealth(); setHealthy(true) }
    catch { setHealthy(false) }
  }, [])

  useEffect(() => {
    checkHealth()
    const t = setInterval(checkHealth, 10000)
    return () => clearInterval(t)
  }, [checkHealth])

  if (healthy === false) return (
    <div style={s.app}>
      <div style={s.err}>
        Cannot reach Kingdom API.<br />
        Check kingdom-core is running: sudo systemctl status kingdom-core
      </div>
    </div>
  )

  return (
    <div style={s.app}>
      <div style={s.header}>
        <span style={healthy ? s.dot : s.dotErr} />
        <span style={s.title}>Kingdom</span>
      </div>
      <div style={s.nav}>
        {PANELS.map(p => (
          <button key={p} style={panel === p ? s.navBtnActive : s.navBtn} onClick={() => setPanel(p)}>{p}</button>
        ))}
      </div>
      <div style={s.content}>
        {panel === 'Tasks'     && <TaskInput />}
        {panel === 'Board'     && <TaskBoard />}
        {panel === 'Approvals' && <ApprovalCentre />}
        {panel === 'Daemon'    && <DaemonControls />}
        {panel === 'Knowledge' && <KnowledgePanel />}
        {panel === 'Audit'     && <AuditLog />}
      </div>
    </div>
  )
}

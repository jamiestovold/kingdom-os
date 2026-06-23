import { useState, useEffect } from 'react'
import { getTasks } from '../api'

const STATUSES = ['queued','running','waiting_approval','approved','completed','failed']
const STATUS_COLOR = {
  queued:'#64748b', running:'#f59e0b', waiting_approval:'#3b82f6',
  approved:'#10b981', completed:'#6366f1', failed:'#ef4444'
}

const s = {
  grid: { display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12 },
  col: { background:'#111', border:'1px solid #1e1e2e', borderRadius:8, padding:12 },
  colHead: { fontSize:11, fontWeight:700, textTransform:'uppercase', letterSpacing:1, marginBottom:10, paddingBottom:6, borderBottom:'1px solid #1e1e2e' },
  task: { background:'#0d0d0d', border:'1px solid #222', borderRadius:4, padding:'8px 10px', marginBottom:6, fontSize:12 },
  taskId: { color:'#333', fontSize:10 },
  taskTitle: { color:'#e2e8f0', marginTop:2 },
  taskAgent: { color:'#64748b', fontSize:10, marginTop:2 },
  refresh: { fontSize:11, color:'#333', marginBottom:12, display:'flex', justifyContent:'space-between', alignItems:'center' },
  btn: { background:'#1a1a2e', color:'#a78bfa', border:'1px solid #333', borderRadius:4, padding:'3px 10px', cursor:'pointer', fontSize:11, fontFamily:'monospace' },
}

export default function TaskBoard() {
  const [tasks, setTasks] = useState([])
  const [lastPoll, setLastPoll] = useState(null)

  const poll = async () => {
    try {
      const data = await getTasks()
      setTasks(data.tasks || [])
      setLastPoll(new Date().toLocaleTimeString())
    } catch {}
  }

  useEffect(() => { poll(); const t = setInterval(poll, 10000); return () => clearInterval(t) }, [])

  const byStatus = (status) => tasks.filter(t => t.status === status)

  return (
    <div>
      <div style={s.refresh}>
        <span>Last polled: {lastPoll || '...'}</span>
        <button style={s.btn} onClick={poll}>↻ Refresh</button>
      </div>
      <div style={s.grid}>
        {STATUSES.map(status => (
          <div key={status} style={s.col}>
            <div style={{ ...s.colHead, color: STATUS_COLOR[status] }}>
              {status.replace('_',' ')} ({byStatus(status).length})
            </div>
            {byStatus(status).map(task => (
              <div key={task.id} style={s.task}>
                <div style={s.taskId}>{task.id.slice(0,8)}...</div>
                <div style={s.taskTitle}>{task.title}</div>
                <div style={s.taskAgent}>{task.agent} · {task.task_type}</div>
              </div>
            ))}
            {byStatus(status).length === 0 && (
              <div style={{ color:'#333', fontSize:11 }}>empty</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

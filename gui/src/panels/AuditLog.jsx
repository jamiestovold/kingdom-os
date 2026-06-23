import { useState, useEffect } from 'react'
import { getAuditLog } from '../api'

const ACTION_COLOR = {
  task_created: '#3b82f6', task_updated: '#f59e0b', run_started: '#6366f1',
  run_approved: '#10b981', run_rejected: '#ef4444', run_completed: '#10b981',
  run_failed: '#ef4444', daemon_paused: '#f59e0b', daemon_resumed: '#10b981',
  knowledge_ingested: '#a78bfa',
}

const s = {
  h2: { fontSize:13, fontWeight:700, color:'#a78bfa', marginBottom:12, textTransform:'uppercase', letterSpacing:1 },
  refresh: { fontSize:11, color:'#333', marginBottom:12, display:'flex', justifyContent:'space-between', alignItems:'center' },
  btn: { background:'#1a1a2e', color:'#a78bfa', border:'1px solid #333', borderRadius:4, padding:'3px 10px', cursor:'pointer', fontSize:11, fontFamily:'monospace' },
  table: { width:'100%', borderCollapse:'collapse' },
  th: { textAlign:'left', fontSize:10, color:'#64748b', textTransform:'uppercase', padding:'4px 8px', borderBottom:'1px solid #1e1e2e' },
  td: { fontSize:11, padding:'5px 8px', borderBottom:'1px solid #0d0d0d', verticalAlign:'top', color:'#94a3b8' },
  badge: (action) => ({
    display:'inline-block', padding:'1px 6px', borderRadius:3, fontSize:10,
    background: ACTION_COLOR[action] ? ACTION_COLOR[action] + '22' : '#33333322',
    color: ACTION_COLOR[action] || '#64748b',
    border: `1px solid ${ACTION_COLOR[action] || '#333'}44`,
  }),
  details: { maxWidth:400, wordBreak:'break-all' },
  limitRow: { display:'flex', gap:8, marginBottom:12, alignItems:'center' },
  select: { background:'#0d0d0d', border:'1px solid #333', borderRadius:4, padding:'3px 8px', color:'#e2e8f0', fontFamily:'monospace', fontSize:12 },
}

export default function AuditLog() {
  const [logs, setLogs] = useState([])
  const [limit, setLimit] = useState(50)
  const [lastPoll, setLastPoll] = useState(null)

  const poll = async (lim = limit) => {
    try {
      const data = await getAuditLog(lim)
      setLogs(data.logs || [])
      setLastPoll(new Date().toLocaleTimeString())
    } catch {}
  }

  useEffect(() => { poll() }, [])
  useEffect(() => { poll(limit) }, [limit])

  return (
    <div>
      <div style={s.h2}>Audit Log</div>
      <div style={s.refresh}>
        <div style={s.limitRow}>
          <span style={{ fontSize:11, color:'#64748b' }}>Show:</span>
          <select style={s.select} value={limit} onChange={e => setLimit(+e.target.value)}>
            {[25,50,100,200].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
          <span style={{ fontSize:11, color:'#333' }}>Last: {lastPoll || '...'}</span>
        </div>
        <button style={s.btn} onClick={() => poll(limit)}>↻ Refresh</button>
      </div>
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>Time</th>
            <th style={s.th}>Action</th>
            <th style={s.th}>Resource</th>
            <th style={s.th}>Details</th>
          </tr>
        </thead>
        <tbody>
          {logs.map(log => (
            <tr key={log.id}>
              <td style={s.td}>{log.timestamp?.slice(0,19)?.replace('T',' ')}</td>
              <td style={s.td}><span style={s.badge(log.action)}>{log.action}</span></td>
              <td style={s.td}>{log.resource?.slice(0,12)}</td>
              <td style={{ ...s.td, ...s.details }}>
                {typeof log.details === 'object'
                  ? JSON.stringify(log.details).slice(0,120)
                  : String(log.details || '').slice(0,120)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {logs.length === 0 && <div style={{ color:'#333', fontSize:12, textAlign:'center', marginTop:20 }}>No audit entries.</div>}
    </div>
  )
}

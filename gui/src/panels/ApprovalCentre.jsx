import { useState, useEffect } from 'react'
import { getTasks, getRuns, approveRun, rejectRun } from '../api'

const s = {
  h2: { fontSize:13, fontWeight:700, color:'#a78bfa', marginBottom:16, textTransform:'uppercase', letterSpacing:1 },
  card: { background:'#111', border:'1px solid #1e1e2e', borderRadius:8, padding:16, marginBottom:12 },
  row: { display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:16 },
  info: { flex:1 },
  title: { fontSize:13, color:'#e2e8f0', marginBottom:2 },
  meta: { fontSize:11, color:'#64748b' },
  output: { marginTop:10, background:'#0d0d0d', border:'1px solid #222', borderRadius:4, padding:10, fontSize:11, color:'#94a3b8', maxHeight:120, overflowY:'auto', whiteSpace:'pre-wrap', fontFamily:'monospace' },
  btns: { display:'flex', gap:8, marginTop:12 },
  approveBtn: { background:'#065f46', color:'#10b981', border:'1px solid #10b981', borderRadius:4, padding:'5px 14px', cursor:'pointer', fontSize:12, fontFamily:'monospace' },
  rejectBtn: { background:'#450a0a', color:'#ef4444', border:'1px solid #ef4444', borderRadius:4, padding:'5px 14px', cursor:'pointer', fontSize:12, fontFamily:'monospace' },
  noteInput: { background:'#0d0d0d', border:'1px solid #333', borderRadius:4, padding:'4px 8px', color:'#e2e8f0', fontFamily:'monospace', fontSize:12, flex:1 },
  empty: { color:'#333', fontSize:13, textAlign:'center', marginTop:40 },
  flash: { fontSize:11, marginTop:8 },
  refresh: { fontSize:11, color:'#333', marginBottom:12, display:'flex', justifyContent:'space-between', alignItems:'center' },
  btn: { background:'#1a1a2e', color:'#a78bfa', border:'1px solid #333', borderRadius:4, padding:'3px 10px', cursor:'pointer', fontSize:11, fontFamily:'monospace' },
}

function ApprovalCard({ run, task, onAction }) {
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState('')

  const act = async (fn, ...args) => {
    setLoading(true)
    try {
      await fn(run.id, 'kingdom', ...args)
      setFlash('Done')
      onAction()
    } catch(e) { setFlash('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={s.card}>
      <div style={s.row}>
        <div style={s.info}>
          <div style={s.title}>{task?.title || run.task_id.slice(0,8)}</div>
          <div style={s.meta}>agent: {run.agent} · run: {run.id.slice(0,8)} · {run.started_at?.slice(0,16)}</div>
        </div>
      </div>
      {run.output && <div style={s.output}>{run.output}</div>}
      <div style={s.btns}>
        <input style={s.noteInput} value={note} onChange={e => setNote(e.target.value)} placeholder="Approval note (optional)" />
        <button style={s.approveBtn} disabled={loading} onClick={() => act(approveRun, note)}>
          {loading ? '...' : 'Approve'}
        </button>
      </div>
      <div style={s.btns}>
        <input style={s.noteInput} value={reason} onChange={e => setReason(e.target.value)} placeholder="Rejection reason (required)" />
        <button style={s.rejectBtn} disabled={loading || !reason.trim()} onClick={() => act(rejectRun, reason)}>
          {loading ? '...' : 'Reject'}
        </button>
      </div>
      {flash && <div style={{ ...s.flash, color: flash.startsWith('Error') ? '#ef4444' : '#10b981' }}>{flash}</div>}
    </div>
  )
}

export default function ApprovalCentre() {
  const [pending, setPending] = useState([])
  const [taskMap, setTaskMap] = useState({})
  const [lastPoll, setLastPoll] = useState(null)

  const poll = async () => {
    try {
      const { tasks } = await getTasks('waiting_approval')
      const runs = []
      for (const task of (tasks || [])) {
        const r = await getRuns(task.id)
        const waiting = (r.runs || []).filter(x => x.status === 'waiting_approval')
        runs.push(...waiting)
        waiting.forEach(w => setTaskMap(m => ({ ...m, [w.task_id]: task })))
      }
      setPending(runs)
      setLastPoll(new Date().toLocaleTimeString())
    } catch {}
  }

  useEffect(() => { poll(); const t = setInterval(poll, 8000); return () => clearInterval(t) }, [])

  return (
    <div>
      <div style={s.h2}>Approval Centre</div>
      <div style={s.refresh}>
        <span>Last polled: {lastPoll || '...'}</span>
        <button style={s.btn} onClick={poll}>↻ Refresh</button>
      </div>
      {pending.length === 0
        ? <div style={s.empty}>No runs awaiting approval.</div>
        : pending.map(run => (
            <ApprovalCard key={run.id} run={run} task={taskMap[run.task_id]} onAction={poll} />
          ))
      }
    </div>
  )
}

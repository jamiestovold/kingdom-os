import { useState, useEffect } from 'react'
import { getDaemonStatus, pauseDaemon, resumeDaemon } from '../api'

const s = {
  h2: { fontSize:13, fontWeight:700, color:'#a78bfa', marginBottom:16, textTransform:'uppercase', letterSpacing:1 },
  card: { background:'#111', border:'1px solid #1e1e2e', borderRadius:8, padding:20, marginBottom:12 },
  grid: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginBottom:16 },
  stat: { background:'#0d0d0d', border:'1px solid #222', borderRadius:4, padding:'10px 14px' },
  statLabel: { fontSize:10, color:'#64748b', textTransform:'uppercase', letterSpacing:1 },
  statValue: { fontSize:18, fontWeight:700, marginTop:4 },
  btns: { display:'flex', gap:10 },
  pauseBtn: { background:'#451a03', color:'#f59e0b', border:'1px solid #f59e0b', borderRadius:4, padding:'7px 20px', cursor:'pointer', fontSize:13, fontFamily:'monospace' },
  resumeBtn: { background:'#052e16', color:'#10b981', border:'1px solid #10b981', borderRadius:4, padding:'7px 20px', cursor:'pointer', fontSize:13, fontFamily:'monospace' },
  flash: { fontSize:12, marginTop:10 },
  ts: { fontSize:11, color:'#333', marginTop:12 },
}

function Stat({ label, value, color }) {
  return (
    <div style={s.stat}>
      <div style={s.statLabel}>{label}</div>
      <div style={{ ...s.statValue, color: color || '#e2e8f0' }}>{value ?? '—'}</div>
    </div>
  )
}

export default function DaemonControls() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState('')

  const fetch = async () => {
    try { setData(await getDaemonStatus()) } catch {}
  }

  useEffect(() => { fetch(); const t = setInterval(fetch, 5000); return () => clearInterval(t) }, [])

  const act = async (fn, label) => {
    setLoading(true); setFlash('')
    try { await fn(); await fetch(); setFlash(`${label} sent.`) }
    catch(e) { setFlash('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  const d = data?.daemon || {}
  const c = data?.config || {}
  const paused = d.paused

  return (
    <div>
      <div style={s.h2}>Daemon Controls</div>
      <div style={s.card}>
        <div style={s.grid}>
          <Stat label="Status" value={paused ? 'PAUSED' : 'RUNNING'} color={paused ? '#f59e0b' : '#10b981'} />
          <Stat label="Tasks this hour" value={`${d.tasks_run_this_hour ?? 0} / ${c.max_tasks_per_hour ?? '?'}`} />
          <Stat label="Poll interval" value={`${c.poll_interval_seconds ?? '?'}s`} />
          <Stat label="Worker count" value={c.worker_count ?? '?'} />
        </div>
        <div style={s.btns}>
          <button style={s.pauseBtn} disabled={loading || paused} onClick={() => act(pauseDaemon, 'Pause')}>
            Pause Daemon
          </button>
          <button style={s.resumeBtn} disabled={loading || !paused} onClick={() => act(resumeDaemon, 'Resume')}>
            Resume Daemon
          </button>
        </div>
        {flash && <div style={{ ...s.flash, color: flash.startsWith('Error') ? '#ef4444' : '#10b981' }}>{flash}</div>}
        {d.last_poll && <div style={s.ts}>Last poll: {d.last_poll}</div>}
        {d.started_at && <div style={s.ts}>Started: {d.started_at}</div>}
      </div>
    </div>
  )
}

import { useState } from 'react'
import { createTask } from '../api'

const TASK_TYPES = ['general','architecture','review','research','analysis','build','test','document','infra']
const ROUTING = { architecture:'claude', review:'codex', research:'claude', analysis:'claude',
  build:'local_llm', test:'codex', document:'local_llm', infra:'script', general:'claude' }

const s = {
  card: { background:'#111', border:'1px solid #1e1e2e', borderRadius:8, padding:20, marginBottom:16 },
  h2: { fontSize:13, fontWeight:700, color:'#a78bfa', marginBottom:16, textTransform:'uppercase', letterSpacing:1 },
  label: { fontSize:11, color:'#64748b', marginBottom:4, display:'block' },
  input: { width:'100%', background:'#0d0d0d', border:'1px solid #333', borderRadius:4, padding:'6px 10px', color:'#e2e8f0', fontFamily:'monospace', fontSize:13, boxSizing:'border-box', marginBottom:12 },
  textarea: { width:'100%', background:'#0d0d0d', border:'1px solid #333', borderRadius:4, padding:'6px 10px', color:'#e2e8f0', fontFamily:'monospace', fontSize:13, boxSizing:'border-box', marginBottom:12, resize:'vertical', minHeight:80 },
  select: { width:'100%', background:'#0d0d0d', border:'1px solid #333', borderRadius:4, padding:'6px 10px', color:'#e2e8f0', fontFamily:'monospace', fontSize:13, marginBottom:12 },
  btn: { background:'#7c3aed', color:'#fff', border:'none', borderRadius:4, padding:'7px 20px', cursor:'pointer', fontSize:13, fontFamily:'monospace' },
  routing: { fontSize:12, color:'#10b981', marginTop:8 },
  err: { color:'#ef4444', fontSize:12, marginTop:8 },
  success: { color:'#10b981', fontSize:12, marginTop:8 },
}

export default function TaskInput() {
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [type, setType] = useState('general')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [err, setErr] = useState('')

  const submit = async () => {
    if (!title.trim()) { setErr('Title is required'); return }
    setLoading(true); setErr(''); setResult(null)
    try {
      const task = await createTask(title.trim(), desc.trim(), type)
      setResult(task)
      setTitle(''); setDesc(''); setType('general')
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={s.card}>
      <div style={s.h2}>New Task</div>
      <label style={s.label}>Title</label>
      <input style={s.input} value={title} onChange={e => setTitle(e.target.value)}
        placeholder="Task title" onKeyDown={e => e.key === 'Enter' && submit()} />
      <label style={s.label}>Description</label>
      <textarea style={s.textarea} value={desc} onChange={e => setDesc(e.target.value)}
        placeholder="What should Kingdom do?" />
      <label style={s.label}>Task Type</label>
      <select style={s.select} value={type} onChange={e => setType(e.target.value)}>
        {TASK_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
      </select>
      <div style={s.routing}>→ routes to: {ROUTING[type] || 'claude'}</div>
      {err && <div style={s.err}>{err}</div>}
      {result && <div style={s.success}>✓ Task created — ID: {result.id?.slice(0,8)}... agent: {result.agent}</div>}
      <button style={{ ...s.btn, marginTop:12 }} onClick={submit} disabled={loading}>
        {loading ? 'Creating...' : 'Create Task'}
      </button>
    </div>
  )
}

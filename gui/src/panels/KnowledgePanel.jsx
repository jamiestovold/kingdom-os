import { useState, useEffect } from 'react'
import { getKnowledgeStatus, ingestFile, ingestDirectory, searchKnowledge } from '../api'

const s = {
  h2: { fontSize:13, fontWeight:700, color:'#a78bfa', marginBottom:16, textTransform:'uppercase', letterSpacing:1 },
  card: { background:'#111', border:'1px solid #1e1e2e', borderRadius:8, padding:16, marginBottom:12 },
  statRow: { display:'flex', gap:16, marginBottom:12 },
  stat: { background:'#0d0d0d', border:'1px solid #222', borderRadius:4, padding:'8px 14px', textAlign:'center' },
  statLabel: { fontSize:10, color:'#64748b', textTransform:'uppercase' },
  statVal: { fontSize:20, fontWeight:700, color:'#a78bfa', marginTop:2 },
  label: { fontSize:11, color:'#64748b', marginBottom:4, display:'block' },
  input: { width:'100%', background:'#0d0d0d', border:'1px solid #333', borderRadius:4, padding:'6px 10px', color:'#e2e8f0', fontFamily:'monospace', fontSize:12, boxSizing:'border-box', marginBottom:8 },
  btn: { background:'#7c3aed', color:'#fff', border:'none', borderRadius:4, padding:'6px 14px', cursor:'pointer', fontSize:12, fontFamily:'monospace' },
  secBtn: { background:'#1a1a2e', color:'#a78bfa', border:'1px solid #7c3aed', borderRadius:4, padding:'6px 14px', cursor:'pointer', fontSize:12, fontFamily:'monospace' },
  result: { background:'#0d0d0d', border:'1px solid #222', borderRadius:4, padding:10, marginBottom:8, fontSize:12 },
  resultSource: { color:'#64748b', fontSize:10, marginBottom:4 },
  resultText: { color:'#94a3b8', whiteSpace:'pre-wrap' },
  flash: { fontSize:12, marginTop:6 },
  row: { display:'flex', gap:8, alignItems:'flex-end' },
  docList: { marginTop:8 },
  docItem: { fontSize:11, color:'#64748b', padding:'3px 0', borderBottom:'1px solid #1a1a1a' },
}

function IngestSection({ onDone }) {
  const [file, setFile] = useState('')
  const [dir, setDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState('')

  const doFile = async () => {
    if (!file.trim()) return
    setLoading(true); setFlash('')
    try {
      const r = await ingestFile(file.trim())
      setFlash(`✓ ${r.message || 'Ingested'}`)
      setFile(''); onDone()
    } catch(e) { setFlash('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  const doDir = async () => {
    if (!dir.trim()) return
    setLoading(true); setFlash('')
    try {
      const r = await ingestDirectory(dir.trim())
      setFlash(`✓ ${r.message || `${r.files_processed || 0} files processed`}`)
      setDir(''); onDone()
    } catch(e) { setFlash('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={s.card}>
      <div style={s.h2}>Ingest</div>
      <label style={s.label}>File path</label>
      <div style={s.row}>
        <input style={{ ...s.input, marginBottom:0, flex:1 }} value={file} onChange={e => setFile(e.target.value)}
          placeholder="/home/kingdom-os/kingdom-philosophy.md" />
        <button style={s.btn} disabled={loading || !file.trim()} onClick={doFile}>Ingest File</button>
      </div>
      <label style={{ ...s.label, marginTop:10 }}>Directory path</label>
      <div style={s.row}>
        <input style={{ ...s.input, marginBottom:0, flex:1 }} value={dir} onChange={e => setDir(e.target.value)}
          placeholder="/home/kingdom-os/docs" />
        <button style={s.secBtn} disabled={loading || !dir.trim()} onClick={doDir}>Ingest Dir</button>
      </div>
      {flash && <div style={{ ...s.flash, color: flash.startsWith('Error') ? '#ef4444' : '#10b981' }}>{flash}</div>}
    </div>
  )
}

function SearchSection() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const r = await searchKnowledge(query.trim(), 5)
      setResults(r.results || [])
      setSearched(true)
    } catch {}
    finally { setLoading(false) }
  }

  return (
    <div style={s.card}>
      <div style={s.h2}>Search Knowledge</div>
      <div style={s.row}>
        <input style={{ ...s.input, marginBottom:0, flex:1 }} value={query}
          onChange={e => setQuery(e.target.value)} placeholder="Search query..."
          onKeyDown={e => e.key === 'Enter' && search()} />
        <button style={s.btn} disabled={loading || !query.trim()} onClick={search}>Search</button>
      </div>
      {searched && results.length === 0 && <div style={{ color:'#333', fontSize:12, marginTop:10 }}>No results.</div>}
      {results.map((r, i) => (
        <div key={i} style={{ ...s.result, marginTop:10 }}>
          <div style={s.resultSource}>{r.source_path} · chunk {r.chunk_index} · dist {r.distance?.toFixed(4)}</div>
          <div style={s.resultText}>{r.text.slice(0, 300)}{r.text.length > 300 ? '…' : ''}</div>
        </div>
      ))}
    </div>
  )
}

export default function KnowledgePanel() {
  const [status, setStatus] = useState(null)

  const fetchStatus = async () => {
    try { setStatus(await getKnowledgeStatus()) } catch {}
  }

  useEffect(() => { fetchStatus() }, [])

  const docs = status?.recent_documents || []

  return (
    <div>
      <div style={s.h2}>Knowledge Base</div>
      {status && (
        <div style={s.card}>
          <div style={s.statRow}>
            <div style={s.stat}><div style={s.statLabel}>Docs</div><div style={s.statVal}>{status.documents_indexed}</div></div>
            <div style={s.stat}><div style={s.statLabel}>Chunks</div><div style={s.statVal}>{status.chunks_indexed}</div></div>
            <div style={s.stat}><div style={s.statLabel}>Vectors</div><div style={s.statVal}>{status.chroma_vectors}</div></div>
          </div>
          {docs.length > 0 && (
            <div style={s.docList}>
              {docs.map((d, i) => <div key={i} style={s.docItem}>{d.file_path} ({d.chunks} chunks)</div>)}
            </div>
          )}
        </div>
      )}
      <IngestSection onDone={fetchStatus} />
      <SearchSection />
    </div>
  )
}

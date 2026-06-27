import { useState, useRef, useCallback, useEffect } from 'react'
import axios from 'axios'

const API = 'http://localhost:8080'

const COLORS = {
  defect: '#f85149',
  normal: '#3fb950',
  warning: '#d29922',
  accent: '#58a6ff',
  muted: '#8b949e',
  dim: '#484f58',
  border: '#30363d',
  card: '#21262d',
  surface: '#161b22',
  bg: '#0d1117',
  text: '#e6edf3',
}

function timeAgo(date) {
  const s = Math.floor((Date.now() - new Date(date)) / 1000)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function Badge({ isAnomaly, size = 'md' }) {
  const pad = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-4 py-2 text-sm'
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-lg border font-mono font-bold tracking-wide ${pad}`}
      style={{
        color: isAnomaly ? COLORS.defect : COLORS.normal,
        background: isAnomaly ? 'rgba(248,81,73,0.12)' : 'rgba(63,185,80,0.12)',
        borderColor: isAnomaly ? 'rgba(248,81,73,0.35)' : 'rgba(63,185,80,0.35)',
      }}
    >
      <span
        className="rounded-full"
        style={{
          width: 8, height: 8, display: 'inline-block',
          background: isAnomaly ? COLORS.defect : COLORS.normal,
          animation: isAnomaly ? 'pulse 1s ease infinite' : 'none',
        }}
      />
      {isAnomaly ? '⚠ DEFECT' : '✓ NORMAL'}
    </span>
  )
}

function ScoreGauge({ score, threshold }) {
  const ARC = 157.08
  const isAnomaly = score > threshold
  const color = isAnomaly ? COLORS.defect : score > threshold * 0.85 ? COLORS.warning : COLORS.normal
  const dash = `${(score * ARC).toFixed(2)} 314.16`
  const ta = Math.PI * threshold
  const tmX1 = (60 - 43 * Math.cos(ta)).toFixed(1)
  const tmY1 = (64 - 43 * Math.sin(ta)).toFixed(1)
  const tmX2 = (60 - 55 * Math.cos(ta)).toFixed(1)
  const tmY2 = (64 - 55 * Math.sin(ta)).toFixed(1)
  return (
    <svg viewBox="0 0 120 72" width={150} height={90} overflow="visible">
      <path d="M 10,64 A 50,50 0 0,1 110,64" fill="none" stroke="#1e2530" strokeWidth={9} strokeLinecap="round" />
      <path d="M 10,64 A 50,50 0 0,1 110,64" fill="none" stroke={COLORS.border} strokeWidth={8} strokeLinecap="round" />
      <path d="M 10,64 A 50,50 0 0,1 110,64" fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
        strokeDasharray={dash} strokeDashoffset={0} />
      <line x1={tmX1} y1={tmY1} x2={tmX2} y2={tmY2} stroke={COLORS.warning} strokeWidth={2.5} strokeLinecap="round" />
      <text x="60" y="53" textAnchor="middle" fill={color} fontSize={19} fontWeight={700} fontFamily="JetBrains Mono, monospace">
        {score.toFixed(3)}
      </text>
      <text x="10" y="72" textAnchor="middle" fill={COLORS.dim} fontSize={7.5}>0.0</text>
      <text x="110" y="72" textAnchor="middle" fill={COLORS.dim} fontSize={7.5}>1.0</text>
    </svg>
  )
}

function Sidebar({ nav, setNav, stats, threshold }) {
  const items = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'history', label: 'History', count: stats.total },
    { id: 'config', label: 'Configuration' },
    { id: 'model', label: 'Model Info' },
  ]
  return (
    <aside className="flex flex-col flex-shrink-0" style={{ width: 200, background: COLORS.surface, borderRight: `1px solid ${COLORS.border}` }}>
      <nav className="flex-1 overflow-y-auto p-2 pt-3">
        <div className="px-2 mb-1.5 text-xs font-semibold tracking-widest" style={{ color: COLORS.dim }}>NAVIGATION</div>
        {items.map(item => (
          <button key={item.id} onClick={() => setNav(item.id)}
            className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md mb-0.5 text-left text-xs font-medium transition-colors"
            style={{
              background: nav === item.id ? 'rgba(88,166,255,0.1)' : 'transparent',
              color: nav === item.id ? COLORS.accent : COLORS.muted,
            }}>
            <span className="flex-1">{item.label}</span>
            {item.count !== undefined && (
              <span className="rounded-full px-1.5 py-0 text-xs font-mono" style={{ background: 'rgba(88,166,255,0.12)', color: COLORS.accent }}>
                {item.count}
              </span>
            )}
          </button>
        ))}
      </nav>
      <div className="p-3.5" style={{ borderTop: `1px solid ${COLORS.border}` }}>
        <div className="mb-2 text-xs font-semibold tracking-widest" style={{ color: COLORS.dim }}>SESSION</div>
        {[
          ['Defects', stats.defects, COLORS.defect],
          ['Normal rate', `${stats.normalRate}%`, COLORS.normal],
          ['Threshold', threshold.toFixed(2), COLORS.accent],
        ].map(([label, val, color]) => (
          <div key={label} className="flex justify-between mb-1.5">
            <span className="text-xs" style={{ color: COLORS.muted }}>{label}</span>
            <span className="text-xs font-semibold font-mono" style={{ color }}>{val}</span>
          </div>
        ))}
      </div>
    </aside>
  )
}

function DropZone({ onFile, isDragging, setIsDragging }) {
  const onDragOver = (e) => { e.preventDefault(); setIsDragging(true) }
  const onDragLeave = (e) => { e.preventDefault(); setIsDragging(false) }
  const onDrop = (e) => {
    e.preventDefault(); setIsDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }
  const ref = useRef(null)
  return (
    <div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
      onClick={() => ref.current?.click()}
      className="flex flex-col items-center justify-center cursor-pointer rounded-xl gap-3.5 transition-all"
      style={{
        border: `2px dashed ${isDragging ? COLORS.accent : COLORS.border}`,
        background: isDragging ? 'rgba(88,166,255,0.05)' : 'transparent',
        minHeight: 280, padding: '56px 32px',
      }}>
      <input ref={ref} type="file" accept="image/*,.bmp" className="hidden" onChange={e => { const f = e.target.files[0]; if (f) onFile(f); e.target.value = '' }} />
      <div className="flex items-center justify-center rounded-xl" style={{ width: 60, height: 60, background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke={COLORS.accent} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <div className="text-center">
        <div className="font-semibold mb-1" style={{ fontSize: 15, color: COLORS.text }}>Drop an image to inspect</div>
        <div className="text-xs" style={{ color: COLORS.muted }}>Accepts JPG · PNG · BMP · Drag &amp; drop or click to browse</div>
      </div>
      <div className="text-xs font-mono rounded-md px-3 py-1" style={{ color: COLORS.dim, background: COLORS.surface, border: `1px solid ${COLORS.border}` }}>
        PaDiM · ONNX · FastAPI @ localhost:8080
      </div>
    </div>
  )
}

function StatCard({ label, value, color, sub }) {
  return (
    <div className="rounded-lg p-3" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
      <div className="text-xs mb-0.5" style={{ color: COLORS.muted }}>{label}</div>
      <div className="font-bold font-mono leading-tight" style={{ fontSize: 24, color: color || COLORS.text }}>{value}</div>
      {sub && <div className="text-xs mt-0.5" style={{ color: COLORS.dim }}>{sub}</div>}
    </div>
  )
}

export default function App() {
  const [nav, setNav] = useState('dashboard')
  const [image, setImage] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isInferring, setIsInferring] = useState(false)
  const [result, setResult] = useState(null)
  const [threshold, setThreshold] = useState(0.5)
  const [history, setHistory] = useState([])
  const [backendStatus, setBackendStatus] = useState('offline')
  const fileRef = useRef(null)

  useEffect(() => { pingBackend() }, [])

  function pingBackend() {
    setBackendStatus('checking')
    axios.get(`${API}/health`, { timeout: 2000 })
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'))
  }

  async function handleFile(file) {
    const url = await new Promise(res => {
      const r = new FileReader()
      r.onload = e => res(e.target.result)
      r.readAsDataURL(file)
    })
    setImage({ url, name: file.name })
    setResult(null)
    setIsInferring(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const { data } = await axios.post(`${API}/api/v1/predict`, fd, { timeout: 15000 })
      const heatmapUrl = data.heatmap_base64
        ? `data:image/png;base64,${data.heatmap_base64}` : url
      const r = { score: data.score, heatmapUrl, ms: data.inference_time_ms, isAnomaly: data.is_anomaly }
      setResult(r)
      setHistory(h => [{ id: Date.now(), name: file.name, score: data.score, ts: new Date(), thumb: url }, ...h].slice(0, 20))
    } catch (err) {
      console.error('Inference failed:', err)
      setResult(null)
    } finally {
      setIsInferring(false)
    }
  }

  const stats = {
    total: history.length,
    defects: history.filter(h => h.score > threshold).length,
    get normalRate() { return this.total > 0 ? (((this.total - this.defects) / this.total) * 100).toFixed(1) : '0.0' },
    get avgScore() { return this.total > 0 ? (history.reduce((a, b) => a + b.score, 0) / this.total).toFixed(3) : '0.000' },
  }

  const statusColor = { online: COLORS.normal, checking: COLORS.warning, offline: COLORS.defect }[backendStatus]
  const statusLabel = { online: 'API Online', checking: 'Connecting…', offline: 'Demo Mode' }[backendStatus]

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: COLORS.bg, color: COLORS.text, fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Header */}
      <header className="flex items-center gap-2.5 px-4 flex-shrink-0" style={{ height: 52, background: COLORS.surface, borderBottom: `1px solid ${COLORS.border}` }}>
        <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
          <rect width="26" height="26" rx="6" fill="rgba(88,166,255,.12)"/>
          <polygon points="13,3 21,8 21,18 13,23 5,18 5,8" stroke="#58a6ff" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
          <circle cx="13" cy="13" r="2.5" fill="#58a6ff"/>
        </svg>
        <div>
          <div className="font-bold text-sm leading-tight">DefectSense</div>
          <div className="text-xs tracking-widest font-mono" style={{ color: COLORS.muted, fontSize: 9 }}>INDUSTRIAL ANOMALY DETECTION</div>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, color: COLORS.dim }}>v2.1.0</span>
        <div className="flex-1" />
        <div className="flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-md" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
          <span className="font-mono" style={{ color: COLORS.dim, fontSize: 10 }}>MODEL</span>
          <span className="font-semibold">PaDiM · WideResNet50</span>
          <span style={{ width: 1, height: 11, background: COLORS.border, display: 'inline-block' }} />
          <span className="font-mono" style={{ color: COLORS.normal, fontSize: 10 }}>AUROC 0.956</span>
        </div>
        <div className="flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-md" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
          <span className="rounded-full" style={{ width: 7, height: 7, background: statusColor, display: 'inline-block', animation: backendStatus !== 'offline' ? 'pulse 1.8s ease infinite' : 'none' }} />
          <span style={{ color: COLORS.muted }}>{statusLabel}</span>
        </div>
        <div className="text-xs font-mono px-2.5 py-1.5 rounded-md" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
          <span style={{ color: COLORS.accent, fontWeight: 600 }}>{stats.total}</span>
          <span style={{ color: COLORS.dim }}> images</span>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        <Sidebar nav={nav} setNav={setNav} stats={stats} threshold={threshold} />

        {/* Center */}
        <main className="flex-1 overflow-y-auto min-w-0" style={{ background: COLORS.bg }}>
          {nav === 'dashboard' && (
            <div className="p-4 flex flex-col gap-3.5">
              {!image ? (
                <DropZone onFile={handleFile} isDragging={isDragging} setIsDragging={setIsDragging} />
              ) : (
                <div>
                  {/* File bar */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-mono" style={{ color: COLORS.muted }}>{image.name}</span>
                    <div className="flex gap-1.5">
                      <button onClick={() => fileRef.current?.click()} className="text-xs px-2.5 py-1 rounded-md border transition-colors" style={{ color: COLORS.accent, background: 'rgba(88,166,255,0.06)', borderColor: 'rgba(88,166,255,0.3)' }}>New Image</button>
                      <button onClick={() => { setImage(null); setResult(null) }} className="text-xs px-2.5 py-1 rounded-md border" style={{ color: COLORS.muted, background: COLORS.card, borderColor: COLORS.border }}>Clear</button>
                      <input ref={fileRef} type="file" accept="image/*,.bmp" className="hidden" onChange={e => { const f = e.target.files[0]; if (f) handleFile(f); e.target.value = '' }} />
                    </div>
                  </div>

                  {/* Image comparison */}
                  <div className="grid grid-cols-2 gap-2.5 mb-3">
                    {[
                      { label: 'ORIGINAL', dotColor: COLORS.normal, content: <img src={image.url} alt="Original" className="max-w-full max-h-64 object-contain rounded block" /> },
                      { label: 'ANOMALY MAP', dotColor: COLORS.defect, content: isInferring
                          ? <div className="w-full h-64 rounded" style={{ background: 'linear-gradient(90deg,#21262d 25%,#2a3142 50%,#21262d 75%)', backgroundSize: '600px 100%', animation: 'shimmer 1.4s ease infinite' }} />
                          : result ? <img src={result.heatmapUrl} alt="Heatmap" className="max-w-full max-h-64 object-contain rounded block" style={{ animation: 'fadeUp .4s ease' }} /> : null
                      },
                    ].map(({ label, dotColor, content }) => (
                      <div key={label} className="rounded-lg overflow-hidden" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                        <div className="flex items-center gap-1.5 px-3 py-1.5" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                          <span className="rounded-full" style={{ width: 6, height: 6, background: dotColor, display: 'inline-block' }} />
                          <span className="text-xs font-bold font-mono tracking-widest" style={{ color: COLORS.muted }}>{label}</span>
                        </div>
                        <div className="p-2 flex items-center justify-center" style={{ minHeight: 192, background: '#1a1f26' }}>{content}</div>
                      </div>
                    ))}
                  </div>

                  {/* Loading */}
                  {isInferring && (
                    <div className="flex items-center gap-3.5 p-3.5 rounded-lg mb-3" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                      <div className="relative flex-shrink-0" style={{ width: 34, height: 34 }}>
                        <svg width="34" height="34" viewBox="0 0 34 34" style={{ position: 'absolute', animation: 'spin 1s linear infinite' }}>
                          <circle cx="17" cy="17" r="13" fill="none" stroke={COLORS.accent} strokeWidth="2" strokeDasharray="40 42" />
                        </svg>
                      </div>
                      <div className="flex-1">
                        <div className="font-semibold text-sm mb-0.5">Running PaDiM inference…</div>
                        <div className="text-xs" style={{ color: COLORS.muted }}>Extracting features · Computing Mahalanobis distance · Generating heatmap</div>
                      </div>
                    </div>
                  )}

                  {/* Score section */}
                  {result && !isInferring && (
                    <div className="grid gap-2.5 mb-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                      <div className="flex flex-col items-center p-3.5 rounded-lg" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, minWidth: 178 }}>
                        <div className="text-xs font-bold tracking-widest mb-1" style={{ color: COLORS.dim }}>ANOMALY SCORE</div>
                        <ScoreGauge score={result.score} threshold={threshold} />
                        <div className="text-xs font-mono mt-1" style={{ color: COLORS.dim, marginTop: -6 }}>threshold {threshold.toFixed(2)}</div>
                      </div>
                      <div className="flex flex-col justify-center gap-2.5 p-3.5 rounded-lg" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                        <div className="flex items-center gap-3">
                          <Badge isAnomaly={result.isAnomaly} />
                          <div>
                            <div className="text-xs mb-0.5" style={{ color: COLORS.muted }}>Confidence</div>
                            <div className="text-lg font-bold font-mono">{Math.min(99, Math.round(Math.abs(result.score - threshold) / Math.max(threshold, 1 - threshold) * 100))}%</div>
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          {[
                            ['SCORE', result.score.toFixed(3), result.isAnomaly ? COLORS.defect : COLORS.normal],
                            ['THRESHOLD', threshold.toFixed(2), COLORS.muted],
                            ['LATENCY', `${result.ms}ms`, COLORS.muted],
                          ].map(([label, val, color]) => (
                            <div key={label} className="rounded-md p-2" style={{ background: COLORS.surface }}>
                              <div className="text-xs mb-0.5 tracking-widest" style={{ color: COLORS.dim, fontSize: 9 }}>{label}</div>
                              <div className="font-bold font-mono text-sm" style={{ color }}>{val}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="flex flex-col items-center justify-center p-3.5 rounded-lg gap-1" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`, minWidth: 88 }}>
                        <div className="text-xs font-bold tracking-widest" style={{ color: COLORS.dim }}>FPS</div>
                        <div className="font-bold font-mono" style={{ fontSize: 28, color: COLORS.accent, lineHeight: 1 }}>{(1000 / result.ms).toFixed(1)}</div>
                        <div className="text-xs" style={{ color: COLORS.muted }}>frames/sec</div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Threshold slider */}
              <div className="rounded-lg p-3.5" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                <div className="flex items-center justify-between mb-2.5">
                  <div>
                    <div className="font-semibold text-xs mb-0.5">Detection Threshold</div>
                    <div className="text-xs" style={{ color: COLORS.muted }}>
                      Score ≥ threshold → <span style={{ color: COLORS.defect }}>DEFECT</span> &nbsp; Score &lt; threshold → <span style={{ color: COLORS.normal }}>NORMAL</span>
                    </div>
                  </div>
                  <div className="font-bold font-mono text-xl" style={{ color: COLORS.accent }}>{threshold.toFixed(2)}</div>
                </div>
                <input type="range" min="0.05" max="0.95" step="0.01" value={threshold}
                  onChange={e => setThreshold(parseFloat(e.target.value))}
                  className="w-full accent-blue-400" />
                <div className="flex justify-between mt-1.5">
                  <span className="text-xs font-mono" style={{ color: COLORS.dim }}>0.05 · sensitive</span>
                  <span className="text-xs font-mono" style={{ color: COLORS.dim }}>strict · 0.95</span>
                </div>
              </div>
            </div>
          )}

          {nav === 'history' && (
            <div className="p-4">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="font-bold mb-1" style={{ fontSize: 17 }}>Inference History</h2>
                  <p className="text-xs" style={{ color: COLORS.muted }}>{history.length} records · threshold {threshold.toFixed(2)}</p>
                </div>
                <div className="flex gap-1.5">
                  {[['defects', stats.defects, COLORS.defect], ['normal', stats.total - stats.defects, COLORS.normal]].map(([label, val, color]) => (
                    <div key={label} className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                      <span className="rounded-full" style={{ width: 6, height: 6, background: color, display: 'inline-block' }} />
                      <span className="font-bold font-mono" style={{ color }}>{val}</span>
                      <span style={{ color: COLORS.muted }}>{label}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-lg overflow-hidden" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                <div className="grid px-3.5 py-2 text-xs font-bold tracking-widest" style={{ gridTemplateColumns: '38px 1fr 100px 96px 100px', background: COLORS.surface, borderBottom: `1px solid ${COLORS.border}`, color: COLORS.dim }}>
                  {['#', 'FILE', 'SCORE', 'RESULT', 'TIME'].map(h => <div key={h}>{h}</div>)}
                </div>
                {history.length === 0 && (
                  <div className="py-12 text-center text-xs" style={{ color: COLORS.dim }}>No inferences yet — upload an image from the Dashboard</div>
                )}
                {history.map((item, i) => {
                  const anom = item.score > threshold
                  return (
                    <div key={item.id} className="grid px-3.5 py-2 items-center text-xs" style={{ gridTemplateColumns: '38px 1fr 100px 96px 100px', borderBottom: `1px solid rgba(48,54,61,0.5)` }}>
                      <span className="font-mono" style={{ color: COLORS.dim }}>{i + 1}</span>
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="flex-shrink-0 rounded overflow-hidden flex items-center justify-center" style={{ width: 28, height: 28, background: COLORS.surface, border: `1px solid ${COLORS.border}` }}>
                          {item.thumb ? <img src={item.thumb} className="w-full h-full object-cover" alt="" /> : <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#484f58" strokeWidth="1.2" strokeLinecap="round"><rect x="1" y="1" width="10" height="10" rx="1.5"/><path d="M1 9l3-3 2 2 2.5-3L11 9"/></svg>}
                        </div>
                        <span className="font-mono truncate" style={{ color: COLORS.text }}>{item.name}</span>
                      </div>
                      <div>
                        <div className="font-bold font-mono mb-0.5" style={{ color: anom ? COLORS.defect : COLORS.normal }}>{item.score.toFixed(3)}</div>
                        <div className="h-0.5 rounded overflow-hidden" style={{ width: 64, background: COLORS.border }}>
                          <div style={{ height: '100%', width: `${(item.score * 100).toFixed(0)}%`, background: anom ? COLORS.defect : COLORS.normal, borderRadius: 2 }} />
                        </div>
                      </div>
                      <Badge isAnomaly={anom} size="sm" />
                      <span className="font-mono" style={{ color: COLORS.muted }}>{timeAgo(item.ts)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {nav === 'config' && (
            <div className="p-4" style={{ maxWidth: 640 }}>
              <h2 className="font-bold mb-1" style={{ fontSize: 17 }}>Configuration</h2>
              <p className="text-xs mb-5" style={{ color: COLORS.muted }}>Adjust detection parameters and backend connection</p>
              <div className="rounded-lg p-4 mb-3" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                <div className="font-semibold text-sm mb-1">Detection Threshold</div>
                <div className="text-xs mb-3" style={{ color: COLORS.muted }}>Samples with anomaly score ≥ threshold are classified as defects.</div>
                <div className="flex items-center gap-3 mb-2.5">
                  <input type="range" min="0.05" max="0.95" step="0.01" value={threshold} onChange={e => setThreshold(parseFloat(e.target.value))} className="flex-1" />
                  <span className="font-bold font-mono text-2xl min-w-12 text-right" style={{ color: COLORS.accent }}>{threshold.toFixed(2)}</span>
                </div>
                <div className="flex gap-1.5 flex-wrap">
                  {[[0.30, 'sensitive'], [0.50, 'default'], [0.70, 'strict'], [0.80, 'very strict']].map(([val, label]) => (
                    <button key={val} onClick={() => setThreshold(val)} className="text-xs font-mono px-3 py-1 rounded-md transition-colors" style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, color: COLORS.muted }}>
                      {val.toFixed(2)} · {label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="rounded-lg p-4" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                <div className="font-semibold text-sm mb-1">API Connection</div>
                <div className="text-xs mb-3" style={{ color: COLORS.muted }}>FastAPI backend serving the PaDiM ONNX model.</div>
                <div className="flex gap-2 mb-2.5">
                  <div className="flex-1 text-xs font-mono px-3 py-2 rounded-md" style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}` }}>http://localhost:8080</div>
                  <button onClick={pingBackend} className="text-xs px-3 py-2 rounded-md transition-colors" style={{ background: 'rgba(88,166,255,0.08)', border: '1px solid rgba(88,166,255,0.25)', color: COLORS.accent }}>Test Connection</button>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full" style={{ width: 7, height: 7, background: statusColor, display: 'inline-block' }} />
                  <span className="text-xs" style={{ color: COLORS.muted }}>{statusLabel}</span>
                </div>
              </div>
            </div>
          )}

          {nav === 'model' && (
            <div className="p-4" style={{ maxWidth: 720 }}>
              <h2 className="font-bold mb-1" style={{ fontSize: 17 }}>Model Information</h2>
              <p className="text-xs mb-5" style={{ color: COLORS.muted }}>PaDiM — Patch Distribution Modeling for Anomaly Detection</p>
              <div className="grid grid-cols-2 gap-3 mb-3">
                {[
                  { title: 'ARCHITECTURE', rows: [['Model','PaDiM'],['Backbone','WideResNet50'],['Format','ONNX'],['Input size','256 × 256'],['Dataset','MVTec AD'],['Layers','layer1, 2, 3']] },
                  { title: 'PERFORMANCE', rows: [['AUROC','0.956',COLORS.normal],['F1 Score','0.921',COLORS.normal],['Precision','0.934'],['Recall','0.908'],['Avg latency','~52 ms'],['Max FPS','~19.2']] },
                ].map(({ title, rows }) => (
                  <div key={title} className="rounded-lg p-4" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                    <div className="text-xs font-bold tracking-widest mb-3" style={{ color: COLORS.dim }}>{title}</div>
                    {rows.map(([label, val, color]) => (
                      <div key={label} className="flex justify-between items-center mb-2">
                        <span className="text-xs" style={{ color: COLORS.muted }}>{label}</span>
                        <span className="text-xs font-semibold font-mono" style={{ color: color || COLORS.text }}>{val}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
              <div className="rounded-lg p-4" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                <div className="text-xs font-bold tracking-widest mb-3" style={{ color: COLORS.dim }}>API ENDPOINTS</div>
                {[
                  { method: 'POST', path: '/api/v1/predict', desc: 'multipart/form-data · score, is_anomaly, heatmap_base64, inference_time_ms', methodColor: COLORS.normal, methodBg: 'rgba(63,185,80,0.12)' },
                  { method: 'GET',  path: '/api/v1/stats',   desc: 'total_processed · defect_count · avg_score · model_info', methodColor: COLORS.accent, methodBg: 'rgba(88,166,255,0.12)' },
                  { method: 'GET',  path: '/health',         desc: '200 OK', methodColor: COLORS.accent, methodBg: 'rgba(88,166,255,0.12)' },
                ].map(({ method, path, desc, methodColor, methodBg }) => (
                  <div key={path} className="flex items-center gap-2.5 px-3 py-2.5 rounded-md mb-2 flex-wrap" style={{ background: COLORS.surface }}>
                    <span className="text-xs font-bold font-mono px-2 py-0.5 rounded flex-shrink-0" style={{ color: methodColor, background: methodBg }}>{method}</span>
                    <span className="text-xs font-mono" style={{ color: COLORS.accent }}>{path}</span>
                    <span className="text-xs ml-auto" style={{ color: COLORS.muted }}>{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Right stats panel */}
        <aside className="flex flex-col flex-shrink-0 overflow-y-auto" style={{ width: 268, background: COLORS.surface, borderLeft: `1px solid ${COLORS.border}` }}>
          <div className="p-3.5" style={{ borderBottom: `1px solid ${COLORS.border}` }}>
            <div className="text-xs font-bold tracking-widest mb-3" style={{ color: COLORS.dim }}>STATISTICS</div>
            <StatCard label="Total Processed" value={stats.total} />
            <div className="grid grid-cols-2 gap-2 my-2">
              <StatCard label="Defects" value={stats.defects} color={COLORS.defect} />
              <StatCard label="Normal %" value={stats.normalRate} color={COLORS.normal} />
            </div>
            <div className="rounded-lg p-3 mb-2" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs" style={{ color: COLORS.muted }}>Avg Anomaly Score</span>
                <span className="font-bold font-mono text-sm" style={{ color: COLORS.warning }}>{stats.avgScore}</span>
              </div>
              <div className="h-1 rounded overflow-hidden" style={{ background: COLORS.border }}>
                <div style={{ height: '100%', width: `${(parseFloat(stats.avgScore) * 100).toFixed(0)}%`, background: 'linear-gradient(90deg,#3fb950,#d29922,#f85149)', borderRadius: 2, transition: 'width .5s' }} />
              </div>
            </div>
            <div className="flex items-center justify-between rounded-lg p-3" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
              <div>
                <div className="text-xs mb-0.5" style={{ color: COLORS.muted }}>Model AUROC</div>
                <div className="text-xs" style={{ color: COLORS.dim }}>PaDiM · WideResNet50</div>
              </div>
              <div className="font-bold font-mono text-lg" style={{ color: COLORS.normal }}>0.956</div>
            </div>
          </div>

          <div className="p-3.5 flex-1">
            <div className="text-xs font-bold tracking-widest mb-2.5" style={{ color: COLORS.dim }}>RECENT INFERENCES</div>
            <div className="flex flex-col gap-1.5">
              {history.slice(0, 7).map(item => {
                const anom = item.score > threshold
                return (
                  <div key={item.id} className="flex items-center gap-2 p-2 rounded-md" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                    <div className="flex-shrink-0 rounded overflow-hidden flex items-center justify-center" style={{ width: 32, height: 32, background: COLORS.surface, border: `1px solid ${COLORS.border}` }}>
                      {item.thumb ? <img src={item.thumb} className="w-full h-full object-cover" alt="" /> : <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#484f58" strokeWidth="1.3" strokeLinecap="round"><rect x="1" y="1" width="12" height="12" rx="2"/><path d="M1 11l4-4 2.5 2.5 2.5-3 4 4.5"/></svg>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-mono truncate" style={{ color: COLORS.text }}>{item.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: COLORS.muted }}>{timeAgo(item.ts)}</div>
                    </div>
                    <div className="flex flex-col items-end gap-0.5 flex-shrink-0">
                      <Badge isAnomaly={anom} size="sm" />
                      <span className="text-xs font-mono" style={{ color: anom ? COLORS.defect : COLORS.normal }}>{item.score.toFixed(3)}</span>
                    </div>
                  </div>
                )
              })}
              {history.length === 0 && <div className="text-xs text-center py-6" style={{ color: COLORS.dim }}>No inferences yet</div>}
            </div>
            {history.length > 0 && (
              <button onClick={() => setNav('history')} className="w-full mt-3 py-1.5 text-xs rounded-md transition-colors" style={{ border: `1px dashed ${COLORS.border}`, color: COLORS.accent }}>
                View all {history.length} inferences →
              </button>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

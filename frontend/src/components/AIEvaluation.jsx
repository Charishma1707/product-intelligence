import { useState, useEffect } from 'react'
import { API } from '../apiConfig'

// ---------------------------------------------------------------------------
// Radar / Pentagon chart drawn on a canvas element
// ---------------------------------------------------------------------------
function RadarChart({ scores, labels, size = 220 }) {
  const center = size / 2
  const radius = size * 0.38
  const n = labels.length
  const angleStep = (2 * Math.PI) / n

  const toXY = (idx, r) => {
    const angle = idx * angleStep - Math.PI / 2
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    }
  }

  // Grid rings
  const rings = [0.25, 0.5, 0.75, 1.0]
  const gridPaths = rings.map(frac => {
    const pts = Array.from({ length: n }, (_, i) => toXY(i, radius * frac))
    return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z'
  })

  // Spokes
  const spokes = Array.from({ length: n }, (_, i) => {
    const outer = toXY(i, radius)
    return { x1: center, y1: center, x2: outer.x, y2: outer.y }
  })

  // Data polygon
  const dataPoints = scores.map((s, i) => toXY(i, radius * Math.min(s, 1)))
  const dataPath = dataPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z'

  // Label positions (slightly outside the radar)
  const labelPositions = Array.from({ length: n }, (_, i) => {
    const pos = toXY(i, radius + 32)
    return { ...pos, label: labels[i], score: scores[i] }
  })

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Grid rings */}
      {gridPaths.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="rgba(99,102,241,0.2)" strokeWidth={1} />
      ))}
      {/* Spokes */}
      {spokes.map((s, i) => (
        <line key={i} {...s} stroke="rgba(99,102,241,0.15)" strokeWidth={1} />
      ))}
      {/* Data polygon */}
      <path d={dataPath} fill="rgba(99,102,241,0.25)" stroke="#818cf8" strokeWidth={2} />
      {/* Data points */}
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={4} fill="#818cf8" />
      ))}
      {/* Labels */}
      {labelPositions.map((lp, i) => (
        <g key={i}>
          <text
            x={lp.x}
            y={lp.y - 4}
            textAnchor="middle"
            fill="#9ca3af"
            fontSize={9}
            fontFamily="Inter, sans-serif"
            fontWeight="600"
          >
            {lp.label.toUpperCase()}
          </text>
          <text
            x={lp.x}
            y={lp.y + 9}
            textAnchor="middle"
            fill="#e5e7eb"
            fontSize={10}
            fontFamily="Inter, sans-serif"
            fontWeight="700"
          >
            {(lp.score * 100).toFixed(0)}%
          </text>
        </g>
      ))}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Grade badge
// ---------------------------------------------------------------------------
function GradeBadge({ grade }) {
  const colors = {
    A: { bg: 'rgba(34,197,94,0.15)', border: '#22c55e', text: '#22c55e' },
    B: { bg: 'rgba(96,165,250,0.15)', border: '#60a5fa', text: '#60a5fa' },
    C: { bg: 'rgba(251,191,36,0.15)', border: '#fbbf24', text: '#fbbf24' },
    D: { bg: 'rgba(251,146,60,0.15)', border: '#fb923c', text: '#fb923c' },
    F: { bg: 'rgba(239,68,68,0.15)', border: '#ef4444', text: '#ef4444' },
  }
  const c = colors[grade] || colors['F']
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: 64,
      height: 64,
      borderRadius: 12,
      background: c.bg,
      border: `2px solid ${c.border}`,
      fontSize: 28,
      fontWeight: 900,
      color: c.text,
      letterSpacing: -1,
    }}>
      {grade}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Score bar row
// ---------------------------------------------------------------------------
function ScoreRow({ label, score, reasoning, issues, flaggedFields, feedback, missingFields, uncitedFields, weight }) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.round(score * 100)
  const color = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444'
  const extra = issues || flaggedFields || feedback || missingFields || uncitedFields

  return (
    <div style={{
      padding: '14px 16px',
      background: 'rgba(255,255,255,0.03)',
      borderRadius: 10,
      border: '1px solid rgba(255,255,255,0.07)',
      marginBottom: 8,
    }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: extra ? 'pointer' : 'default' }}
        onClick={() => extra && setExpanded(e => !e)}
      >
        {/* Score circle */}
        <div style={{
          width: 44,
          height: 44,
          borderRadius: '50%',
          background: `conic-gradient(${color} ${pct * 3.6}deg, rgba(255,255,255,0.08) 0deg)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          position: 'relative',
        }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: '#111827',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 10,
            fontWeight: 800,
            color,
          }}>
            {pct}%
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, color: '#f3f4f6', fontSize: 14 }}>{label}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#6b7280' }}>Weight: {Math.round(weight * 100)}%</span>
              {extra && (
                <span style={{ fontSize: 11, color: '#6b7280' }}>{expanded ? '▲' : '▼'}</span>
              )}
            </div>
          </div>
          {/* Progress bar */}
          <div style={{ height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.08)', marginTop: 6 }}>
            <div style={{
              height: '100%',
              width: `${pct}%`,
              borderRadius: 4,
              background: color,
              transition: 'width 0.8s ease',
            }} />
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>{reasoning}</div>
        </div>
      </div>

      {/* Expandable detail */}
      {expanded && extra && (
        <div style={{
          marginTop: 12,
          paddingTop: 12,
          borderTop: '1px solid rgba(255,255,255,0.07)',
          fontSize: 12,
          color: '#9ca3af',
        }}>
          {(missingFields?.length > 0) && (
            <div><strong style={{ color: '#d1d5db' }}>Missing fields:</strong> {missingFields.join(', ')}</div>
          )}
          {(uncitedFields?.length > 0) && (
            <div style={{ marginTop: 4 }}><strong style={{ color: '#d1d5db' }}>Uncited fields:</strong> {uncitedFields.join(', ')}</div>
          )}
          {(issues?.length > 0) && (
            <div style={{ marginTop: 4 }}>
              <strong style={{ color: '#d1d5db' }}>Issues:</strong>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                {issues.map((issue, i) => <li key={i}>{issue}</li>)}
              </ul>
            </div>
          )}
          {(flaggedFields?.length > 0) && (
            <div style={{ marginTop: 4 }}>
              <strong style={{ color: '#fbbf24' }}>⚠ Possibly hallucinated:</strong>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                {flaggedFields.map((f, i) => (
                  <li key={i}><strong style={{ color: '#e5e7eb' }}>{f.field}</strong>: "{f.value}" — {f.reason}</li>
                ))}
              </ul>
            </div>
          )}
          {(feedback?.length > 0) && (
            <div style={{ marginTop: 4 }}>
              <strong style={{ color: '#d1d5db' }}>Feedback:</strong>
              <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                {feedback.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main AIEvaluation component
// ---------------------------------------------------------------------------
export default function AIEvaluation() {
  const [jobs, setJobs] = useState([])
  const [selectedJobId, setSelectedJobId] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [animating, setAnimating] = useState(false)

  // Fetch completed jobs for the selector
  useEffect(() => {
    const loadJobs = async () => {
      try {
        const res = await fetch(`${API}/jobs?status=complete&limit=50`)
        if (res.ok) {
          const data = await res.json()
          const jobList = data.jobs || []
          setJobs(jobList)
          if (jobList.length > 0) setSelectedJobId(jobList[0].job_id)
        }
      } catch {
        // Use demo fallback
        const demoJobs = [
          { job_id: 'demo-fluke-117', brand: 'Fluke', mpn: 'FLUKE-117' },
          { job_id: 'demo-milwaukee-drill', brand: 'Milwaukee', mpn: '2804-20' },
        ]
        setJobs(demoJobs)
        setSelectedJobId(demoJobs[0].job_id)
      }
    }
    loadJobs()
  }, [])

  const runEvaluation = async () => {
    if (!selectedJobId) return
    setLoading(true)
    setError(null)
    setReport(null)
    try {
      const res = await fetch(`${API}/evaluate/${selectedJobId}`, { method: 'POST' })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      setReport(data)
      setAnimating(true)
      setTimeout(() => setAnimating(false), 800)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const dimensionConfig = [
    { key: 'completeness',       label: 'Completeness',      icon: '📋' },
    { key: 'citation_quality',   label: 'Citation Quality',  icon: '📎' },
    { key: 'hallucination_risk', label: 'Accuracy',          icon: '🎯' },
    { key: 'consistency',        label: 'Consistency',       icon: '⚖️' },
    { key: 'description_quality',label: 'Descriptions',     icon: '✍️' },
  ]

  const radarScores = report
    ? dimensionConfig.map(d => report.dimensions?.[d.key]?.score ?? 0)
    : []

  const radarLabels = dimensionConfig.map(d => d.label)

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Hero */}
      <div className="hero" style={{ paddingBottom: 'var(--space-md)' }}>
        <div className="hero-badge">LLM-as-Judge Scoring</div>
        <h1>AI Quality Evaluation</h1>
        <p style={{ maxWidth: 620, margin: '12px auto 0' }}>
          Run automated quality evaluation on enriched products across <strong>5 dimensions</strong>:
          completeness, citation quality, hallucination risk, cross-field consistency, and description quality.
        </p>
      </div>

      {/* Job selector */}
      <div className="card" style={{ maxWidth: 700, margin: '0 auto var(--space-lg)' }}>
        <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#9ca3af', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>
              Select Completed Job
            </label>
            <select
              value={selectedJobId}
              onChange={e => { setSelectedJobId(e.target.value); setReport(null) }}
              style={{
                width: '100%',
                background: '#1f2937',
                border: '1px solid rgba(255,255,255,0.12)',
                color: '#f3f4f6',
                padding: '10px 12px',
                borderRadius: 8,
                fontSize: 14,
              }}
            >
              {jobs.length === 0 && <option value="">No completed jobs</option>}
              {jobs.map(j => (
                <option key={j.job_id} value={j.job_id}>
                  {j.brand} — {j.mpn} ({j.job_id.slice(0, 8)}…)
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-primary"
            onClick={runEvaluation}
            disabled={loading || !selectedJobId}
            style={{ flexShrink: 0, minWidth: 160 }}
          >
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                Evaluating…
              </span>
            ) : '🔍 Run Evaluation'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ textAlign: 'center', color: '#f87171', marginBottom: 24 }}>
          ⚠ Error: {error}
        </div>
      )}

      {/* Results */}
      {report && (
        <div style={{ opacity: animating ? 0 : 1, transition: 'opacity 0.6s ease', display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 20, alignItems: 'start' }}>

          {/* Left: Radar + Grade */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Overall grade card */}
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '24px 20px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
                  Overall Quality Grade
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
                  <GradeBadge grade={report.grade} />
                </div>
                <div style={{ fontSize: 28, fontWeight: 900, color: '#f3f4f6', lineHeight: 1 }}>
                  {(report.overall_score * 100).toFixed(1)}%
                </div>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                  Weighted Quality Score
                </div>
                <div style={{ marginTop: 10, fontSize: 12, color: '#9ca3af' }}>
                  <strong style={{ color: '#d1d5db' }}>{report.brand}</strong> — {report.mpn}
                </div>
              </div>
            </div>

            {/* Radar chart */}
            <div className="card">
              <div className="card-body" style={{ display: 'flex', justifyContent: 'center', padding: '20px 16px' }}>
                <RadarChart scores={radarScores} labels={radarLabels} size={240} />
              </div>
            </div>

            {/* Recommendations */}
            {report.recommendations?.length > 0 && (
              <div className="card">
                <div className="card-body" style={{ padding: '16px' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>
                    💡 Recommendations
                  </div>
                  <ul style={{ margin: 0, padding: '0 0 0 18px', fontSize: 13, color: '#d1d5db', lineHeight: 1.8 }}>
                    {report.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Right: Dimension breakdown */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">📊 Dimension Breakdown</h2>
              <span style={{ fontSize: 12, color: '#6b7280' }}>Click any row to expand details</span>
            </div>
            <div className="card-body">
              {dimensionConfig.map(d => {
                const dim = report.dimensions?.[d.key]
                if (!dim) return null
                return (
                  <ScoreRow
                    key={d.key}
                    label={`${d.icon} ${d.label}`}
                    score={dim.score ?? 0}
                    reasoning={dim.reasoning ?? ''}
                    weight={report.weights?.[d.key] ?? 0}
                    issues={dim.issues}
                    flaggedFields={dim.flagged_fields}
                    feedback={dim.feedback}
                    missingFields={dim.missing_fields}
                    uncitedFields={dim.uncited_fields}
                  />
                )
              })}

              {/* Hallucination risk level pill */}
              {report.dimensions?.hallucination_risk && (
                <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#9ca3af' }}>
                  Hallucination Risk Level:
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: 20,
                    fontWeight: 700,
                    fontSize: 11,
                    background: report.dimensions.hallucination_risk.risk_level === 'low'
                      ? 'rgba(34,197,94,0.15)' : report.dimensions.hallucination_risk.risk_level === 'medium'
                      ? 'rgba(251,191,36,0.15)' : 'rgba(239,68,68,0.15)',
                    color: report.dimensions.hallucination_risk.risk_level === 'low'
                      ? '#22c55e' : report.dimensions.hallucination_risk.risk_level === 'medium'
                      ? '#fbbf24' : '#ef4444',
                    border: `1px solid ${report.dimensions.hallucination_risk.risk_level === 'low'
                      ? '#22c55e44' : report.dimensions.hallucination_risk.risk_level === 'medium'
                      ? '#fbbf2444' : '#ef444444'}`,
                    textTransform: 'uppercase',
                  }}>
                    {report.dimensions.hallucination_risk.risk_level?.toUpperCase() ?? 'UNKNOWN'}
                  </span>
                </div>
              )}

              <div style={{ marginTop: 16, padding: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 8, fontSize: 11, color: '#6b7280', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                Evaluated at {new Date(report.evaluated_at).toLocaleString()} · Weights: Completeness 30%, Hallucination Risk 25%, Citation Quality 20%, Consistency 15%, Descriptions 10%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!report && !loading && (
        <div style={{
          textAlign: 'center',
          padding: '60px 20px',
          color: '#4b5563',
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔬</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>
            Select a completed job and click "Run Evaluation"
          </div>
          <div style={{ fontSize: 13, color: '#4b5563' }}>
            The AI evaluator will score your enriched product data across 5 quality dimensions
          </div>
        </div>
      )}
    </div>
  )
}

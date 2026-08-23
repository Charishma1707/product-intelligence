/* ---------- PipelineStages — Enterprise 5-stage progress panel ---------- */

const STAGES = [
  {
    id: 'interpreting',
    step: '01',
    label: 'Taxonomy & Identity',
    desc: 'UNSPSC classification, brand resolution, OEM detection',
  },
  {
    id: 'searching',
    step: '02',
    label: 'Exact-MPN Sourcing',
    desc: 'Multi-pass discovery: Manufacturer site and datasheet PDFs',
  },
  {
    id: 'extracting',
    step: '03',
    label: 'RAG Extraction',
    desc: 'ChromaDB semantic retrieval and series knowledge reuse',
  },
  {
    id: 'validating',
    step: '04',
    label: 'Validation & Confidence',
    desc: '5-tier provenance scoring and snippet validation',
  },
  {
    id: 'copywriting',
    step: '05',
    label: 'Commercial Copywriting',
    desc: 'Invoice description ≤40 chars, long description, UNSPSC',
  },
]

function getStatus(stageId, activeStage) {
  if (!activeStage || activeStage === 'idle') return 'idle'
  if (activeStage === 'done') return 'done'
  const ai = STAGES.findIndex(s => s.id === activeStage)
  const ti = STAGES.findIndex(s => s.id === stageId)
  if (ti < ai)  return 'done'
  if (ti === ai) return 'active'
  return 'idle'
}

export default function PipelineStages({ activeStage }) {
  if (!activeStage || activeStage === 'idle') return null

  const activeIdx     = STAGES.findIndex(s => s.id === activeStage)
  const progressPct   = activeStage === 'done' ? 100 : Math.max(8, Math.round(((activeIdx + 1) / STAGES.length) * 100))
  const isDone        = activeStage === 'done'

  return (
    <div style={{
      background: 'linear-gradient(160deg, rgba(0,128,255,0.05) 0%, rgba(14,20,32,0.9) 40%)',
      border: '1px solid var(--border-blue)',
      borderRadius: 'var(--radius-lg)',
      padding: '24px',
      margin: '24px auto',
      maxWidth: '960px',
      boxShadow: '0 0 40px rgba(0,128,255,0.08)',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {isDone ? (
            <span style={{ width: 22, height: 22, background: 'var(--green-500)', borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 13, fontWeight: 800 }}>✓</span>
          ) : (
            <span className="spinner spinner-sm" style={{ borderTopColor: 'var(--blue-400)' }} />
          )}
          <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
            {isDone ? 'Pipeline Complete' : 'Execution Pipeline Active'}
          </span>
        </div>
        <span className={`metric-chip ${isDone ? 'green' : 'blue'}`} style={{ fontSize: 11 }}>
          {isDone ? '100% Complete' : `${progressPct}% Executing`}
        </span>
      </div>

      {/* Progress bar */}
      <div className="stage-progress-bar">
        <div className="stage-progress-fill" style={{ width: `${progressPct}%` }} />
      </div>

      {/* Stages grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        {STAGES.map(stage => {
          const status   = getStatus(stage.id, activeStage)
          const isActive = status === 'active'
          const done     = status === 'done' || isDone

          return (
            <div
              key={stage.id}
              id={`stage-${stage.id}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '14px 8px',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
                background: isActive
                  ? 'rgba(0,128,255,0.12)'
                  : done
                  ? 'rgba(16,185,129,0.07)'
                  : 'rgba(255,255,255,0.02)',
                border: `1px solid ${isActive ? 'rgba(0,128,255,0.5)' : done ? 'rgba(16,185,129,0.3)' : 'var(--border-subtle)'}`,
                transition: 'all 0.35s ease',
                transform: isActive ? 'scale(1.03)' : 'scale(1)',
                boxShadow: isActive ? '0 0 18px rgba(0,128,255,0.22)' : 'none',
              }}
            >
              {/* Step indicator circle */}
              <div style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: done ? 15 : 13,
                marginBottom: 8,
                background: done
                  ? 'var(--green-500)'
                  : isActive
                  ? 'var(--blue-500)'
                  : 'rgba(255,255,255,0.06)',
                color: '#fff',
                fontWeight: 800,
                boxShadow: isActive ? '0 0 12px rgba(0,128,255,0.5)' : done ? '0 0 10px rgba(16,185,129,0.4)' : 'none',
                transition: 'all 0.35s ease',
              }}>
                {isActive ? (
                  <span className="spinner spinner-sm" style={{ borderTopColor: '#fff' }} />
                ) : done ? (
                  '✓'
                ) : (
                  stage.step
                )}
              </div>

              {/* Label */}
              <div style={{
                fontSize: 11,
                fontWeight: isActive || done ? 700 : 500,
                color: done ? 'var(--green-400)' : isActive ? '#fff' : 'var(--text-muted)',
                lineHeight: 1.35,
                marginBottom: 4,
              }}>
                {stage.label}
              </div>

              {/* Description */}
              <div style={{ fontSize: 9.5, color: isActive ? 'var(--blue-300)' : 'var(--text-muted)', lineHeight: 1.3 }}>
                {stage.desc}
              </div>
            </div>
          )
        })}
      </div>

      {/* Done banner */}
      {isDone && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          background: 'var(--green-100)',
          border: '1px solid var(--border-green)',
          borderRadius: 'var(--radius-full)',
          padding: '8px 24px',
          color: 'var(--green-400)',
          fontSize: 13,
          fontWeight: 700,
          marginTop: 20,
        }}>
          All 5 Verification Stages Complete — Review enriched data below
        </div>
      )}
    </div>
  )
}

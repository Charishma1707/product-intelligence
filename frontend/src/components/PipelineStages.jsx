const STAGES = [
  { id: 'interpreting', label: 'Interpreting',  icon: '🔍', desc: 'Classifying product category & fields' },
  { id: 'searching',    label: 'Searching',     icon: '🌐', desc: 'Fetching datasheets & documentation' },
  { id: 'extracting',   label: 'Extracting',    icon: '🤖', desc: 'AI extraction of spec values' },
  { id: 'validating',   label: 'Validating',    icon: '✓',  desc: 'Confidence scoring & sanity checks' },
  { id: 'copywriting',  label: 'Copywriting',   icon: '✍️',  desc: 'Generating commerce-ready copy' },
]

function getStageStatus(stageId, activeStage) {
  if (activeStage === 'idle' || activeStage === null) return 'idle'
  if (activeStage === 'done') return 'done'

  const activeIdx = STAGES.findIndex(s => s.id === activeStage)
  const thisIdx   = STAGES.findIndex(s => s.id === stageId)

  if (thisIdx < activeIdx) return 'done'
  if (thisIdx === activeIdx) return 'active'
  return 'idle'
}

export default function PipelineStages({ activeStage }) {
  if (!activeStage || activeStage === 'idle') return null

  return (
    <div style={{ textAlign: 'center', padding: 'var(--space-lg) 0' }}>
      <p style={{ fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 'var(--space-md)' }}>
        Pipeline Progress
      </p>
      <div className="pipeline-stages">
        {STAGES.map((stage) => {
          const status = getStageStatus(stage.id, activeStage)
          return (
            <div key={stage.id} className={`stage-item ${status}`} id={`stage-${stage.id}`}>
              <div className="stage-icon">
                {status === 'done' ? '✓' : stage.icon}
              </div>
              <div className="stage-label">{stage.label}</div>
              {status === 'active' && (
                <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', marginTop: 2, maxWidth: 100, textAlign: 'center' }}>
                  {stage.desc}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {activeStage === 'done' && (
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          background: 'rgba(16,185,129,0.1)',
          border: '1px solid rgba(16,185,129,0.3)',
          borderRadius: '999px',
          padding: '4px 16px',
          color: 'var(--color-conf-high)',
          fontSize: '0.8rem',
          fontWeight: 600,
          marginTop: 'var(--space-sm)',
        }}>
          ✓ Pipeline complete
        </div>
      )}
    </div>
  )
}

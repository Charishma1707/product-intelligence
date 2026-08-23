import { useState } from 'react'

const API = ''

export default function AgentPromptBar({ jobId, onAgentUpdate, currentStage }) {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [lastAction, setLastAction] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const [error, setError] = useState(null)

  const handleRun = async () => {
    if (!prompt.trim() || !jobId) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/enrich/agent/prompt`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          },
        body: JSON.stringify({ job_id: jobId, prompt: prompt.trim() })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`)

      const agentLog = data.product?.logs?.slice(-1)?.[0]
      setLastAction(agentLog?.message || 'Agent completed task.')
      setPrompt('')

      if (onAgentUpdate && data.product) {
        onAgentUpdate({ ...data.product, job_id: data.job_id || jobId, hitl_required: data.hitl_required })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const EXAMPLE_PROMPTS = [
    'Search for warranty information',
    'Set country of origin to USA',
    'Extract missing fields from PDF',
    'SS means Stainless Steel, save it',
    'Go back to retrieval stage',
    'Boost confidence for voltage field',
  ]

  return (
    <div style={{
      marginTop: 16,
      border: '1px solid rgba(139, 92, 246, 0.3)',
      borderRadius: 10,
      background: 'rgba(139, 92, 246, 0.05)',
      overflow: 'hidden',
    }}>
      {/* Header toggle */}
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: '#c084fc',
          fontSize: '0.82rem',
          fontWeight: 700,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16 }}>🤖</span>
          Agent Prompt — Stage {currentStage}
          <span style={{
            fontSize: '0.68rem', background: 'rgba(139,92,246,0.2)',
            color: '#c084fc', borderRadius: 4, padding: '1px 6px', fontWeight: 600
          }}>BETA</span>
        </span>
        <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
          {expanded ? '▲ Hide' : '▼ Ask the agent anything'}
        </span>
      </button>

      {expanded && (
        <div style={{ padding: '0 16px 16px' }}>
          {/* Last action result */}
          {lastAction && (
            <div style={{
              marginBottom: 10, padding: '8px 12px',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              borderRadius: 6, fontSize: '0.8rem', color: '#34d399'
            }}>
              ✓ {lastAction}
            </div>
          )}

          {error && (
            <div style={{
              marginBottom: 10, padding: '8px 12px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              borderRadius: 6, fontSize: '0.8rem', color: '#f87171'
            }}>
              ✗ {error}
            </div>
          )}

          {/* Example prompt chips */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
            {EXAMPLE_PROMPTS.map(ex => (
              <button
                key={ex}
                type="button"
                onClick={() => setPrompt(ex)}
                style={{
                  fontSize: '0.72rem', padding: '3px 10px',
                  borderRadius: 999, border: '1px solid rgba(139,92,246,0.3)',
                  background: 'rgba(139,92,246,0.08)', color: '#c084fc',
                  cursor: 'pointer', fontWeight: 600,
                  transition: 'all 0.15s',
                }}
              >
                {ex}
              </button>
            ))}
          </div>

          {/* Input row */}
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              id={`agent-prompt-stage-${currentStage}`}
              type="text"
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleRun()}
              placeholder='Type an instruction, e.g. "search for voltage info" or "BRS = Brass, save it"'
              style={{
                flex: 1,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(139,92,246,0.4)',
                borderRadius: 6,
                padding: '8px 12px',
                color: '#e2e8f0',
                fontSize: '0.85rem',
                outline: 'none',
              }}
            />
            <button
              type="button"
              id={`agent-run-btn-stage-${currentStage}`}
              onClick={handleRun}
              disabled={loading || !prompt.trim()}
              style={{
                padding: '8px 18px',
                borderRadius: 6,
                border: 'none',
                background: loading ? 'rgba(139,92,246,0.3)' : 'rgba(139,92,246,0.8)',
                color: '#fff',
                fontWeight: 700,
                fontSize: '0.82rem',
                cursor: loading ? 'not-allowed' : 'pointer',
                whiteSpace: 'nowrap',
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {loading ? <><span className="spinner" />Running…</> : '▶ Run Agent'}
            </button>
          </div>

          <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 6 }}>
            The agent understands natural language and can search, extract from PDFs, update field values, save aliases, or re-route the pipeline.
          </div>
        </div>
      )}
    </div>
  )
}

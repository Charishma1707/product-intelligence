import { useState } from 'react'

const API = ''

/**
 * HITL Review Dashboard
 * Shows flagged low-confidence fields for a paused job, lets a reviewer
 * correct them, and submits corrections to POST /enrich/resume.
 */
export default function HITLReview({ product, onResolved }) {
  const { job_id, flagged_fields, specifications } = product

  // Build initial correction state from ALL fields
  const initialCorrections = Object.fromEntries(
    Object.keys(specifications || {}).map(fname => [fname, String(specifications?.[fname]?.value ?? '')])
  )

  const [corrections, setCorrections] = useState(initialCorrections)
  const [reviewer, setReviewer] = useState('reviewer')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  if (!flagged_fields || flagged_fields.length === 0) return null

  const handleChange = (fname, value) => {
    setCorrections(prev => ({ ...prev, [fname]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const typedCorrections = {}
    for (const [k, v] of Object.entries(corrections)) {
      if (v === '' || v === null) continue
      const num = Number(v)
      typedCorrections[k] = isNaN(num) || v.trim() === '' ? v : num
    }

    try {
      const res = await fetch(`${API}/enrich/resume`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Basic YWRtaW46dW5paGFjaw=='
        },
        body: JSON.stringify({ job_id, corrections: typedCorrections, reviewer }),
      })
      const data = await res.json()
      if (!res.ok || data.status === 'failed') {
        throw new Error(data.error || data.detail || `HTTP ${res.status}`)
      }
      onResolved({
        ...data.product,
        job_id: data.job_id,
        hitl_required: false,
        pipeline_status: data.status,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="hitl-panel" id="hitl-review-panel">
      <div className="hitl-header">
        <div className="hitl-icon">🧑‍💻</div>
        <div>
          <div className="hitl-title">Human Review Required</div>
          <div className="hitl-subtitle">
            Pipeline paused — Please review the extracted and inferred fields below.
            Correct any errors and click "Approve and Finalize" to generate commerce-ready copy.
          </div>
        </div>
      </div>
      <div className="hitl-job-id">Job ID: <span>{job_id}</span></div>
      
      <div style={{ display: 'flex', gap: '20px', marginTop: '20px' }}>
        {/* PDF Image Viewer (Phase 5) */}
        {product.image_base64 && (
          <div style={{ flex: '1', position: 'relative', border: '1px solid #333', borderRadius: '8px', overflow: 'hidden' }}>
            <div style={{ padding: '8px', background: '#222', fontSize: '12px', borderBottom: '1px solid #333' }}>
              Reference Document (First Page)
            </div>
            <div style={{ position: 'relative', width: '100%', height: 'calc(100% - 33px)' }}>
              <img 
                src={`data:image/png;base64,${product.image_base64}`} 
                style={{ display: 'block', width: '100%', height: 'auto', objectFit: 'contain' }} 
                alt="Document"
              />
              {/* Bounding Box Overlays */}
              {Object.entries(specifications).map(([fname, field]) => {
                const bbox = field?.citation?.bounding_box
                if (!bbox || bbox.length !== 4) return null
                // VLM returns [ymin, xmin, ymax, xmax] in 0-1000 scale
                const [ymin, xmin, ymax, xmax] = bbox
                const top = `${(ymin / 1000) * 100}%`
                const left = `${(xmin / 1000) * 100}%`
                const height = `${((ymax - ymin) / 1000) * 100}%`
                const width = `${((xmax - xmin) / 1000) * 100}%`
                
                const isFlagged = flagged_fields.includes(fname)
                const color = isFlagged ? '#ef4444' : '#10b981' // Red if flagged, Green if okay
                
                return (
                  <div key={fname} style={{
                    position: 'absolute',
                    top, left, width, height,
                    border: `2px solid ${color}`,
                    backgroundColor: `${color}33`, // 20% opacity
                    pointerEvents: 'none',
                    zIndex: isFlagged ? 10 : 5
                  }}>
                    <span style={{
                      position: 'absolute',
                      top: '-18px', left: '-2px',
                      background: color, color: '#fff',
                      fontSize: '10px', padding: '2px 4px',
                      borderRadius: '2px', whiteSpace: 'nowrap'
                    }}>
                      {fname.replace(/_/g, ' ')}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
        
        {/* HITL Form */}
        <form onSubmit={handleSubmit} className="hitl-form" style={{ flex: '1', margin: 0 }}>
        <div className="hitl-fields">
          {Object.keys(specifications || {}).map(fname => {
            const field = specifications?.[fname]
            const isFlagged = (flagged_fields || []).includes(fname)
            const isGraph = field?.method === 'inferred'

            return (
              <div key={fname} className={`hitl-field-row ${isFlagged ? 'flagged-row' : ''}`} style={{ borderLeft: isFlagged ? '4px solid #ef4444' : '4px solid transparent' }}>
                <div className="hitl-field-meta">
                  <div className="hitl-field-name">
                    {fname.replace(/_/g, ' ')}
                    {isFlagged && <span style={{ marginLeft: 8, color: '#ef4444', fontSize: '12px' }}>⚠️ Low Confidence</span>}
                  </div>
                  <div className="hitl-field-info">
                    <span className={`conf-badge ${isFlagged ? 'conf-low' : 'conf-high'}`} style={{ background: isFlagged ? '#ef444422' : '#10b98122', color: isFlagged ? '#ef4444' : '#10b981', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>
                      {Math.round((field?.confidence ?? 0) * 100)}%
                    </span>
                    <span className="hitl-method" style={{ marginLeft: 8, background: '#3b82f622', color: '#3b82f6', padding: '2px 6px', borderRadius: '4px', fontSize: '11px' }}>
                      {isGraph ? '🧠 Knowledge Graph' : '📄 PDF Extracted'}
                    </span>
                  </div>
                  
                  <div className="hitl-source-reasoning" style={{ marginTop: '8px', fontSize: '11px', color: '#9ca3af' }}>
                    <strong>Source / Reasoning:</strong><br />
                    {isGraph 
                      ? (
                          <>
                            <span style={{ color: '#f59e0b', display: 'block', marginBottom: '4px' }}>
                              {field?.cause || 'Inferred via GraphRAG domain knowledge'}
                            </span>
                            {field?.citation?.similar_products_used?.length > 0 && (
                              <span style={{ display: 'block', color: '#9ca3af' }}>
                                <strong>Inferred from:</strong> {field.citation.similar_products_used.join(', ')}
                              </span>
                            )}
                          </>
                        )
                      : (
                          <>
                            <span style={{ display: 'block', color: isFlagged ? '#ef4444' : '#9ca3af', marginBottom: '4px' }}>
                              {isFlagged ? `Issue: ${field?.cause}` : (field?.cause || 'Extracted normally')}
                            </span>
                            {field?.citation?.source_url 
                                ? <span>📄 {field.citation.source_url.split('/').pop()}</span>
                                : 'Extracted from document text'}
                          </>
                        )}
                  </div>

                  {field?.citation?.verbatim_snippet && (
                    <div className="hitl-snippet" style={{ marginTop: '4px' }}>"{field.citation.verbatim_snippet}"</div>
                  )}
                </div>
                <div className="hitl-field-input">
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" htmlFor={`hitl-${fname}`}>Corrected Value</label>
                    <input
                      id={`hitl-${fname}`}
                      className="form-input"
                      type="text"
                      value={corrections[fname] ?? ''}
                      onChange={e => handleChange(fname, e.target.value)}
                      placeholder={`Enter correct value for ${fname.replace(/_/g, ' ')}`}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        <div className="hitl-footer">
          <div className="form-group" style={{ maxWidth: 240 }}>
            <label className="form-label" htmlFor="hitl-reviewer">Reviewer ID</label>
            <input
              id="hitl-reviewer"
              className="form-input"
              type="text"
              value={reviewer}
              onChange={e => setReviewer(e.target.value)}
              placeholder="Your name or ID"
            />
          </div>
          {error && <div className="hitl-error">⚠ {error}</div>}
          <button id="hitl-submit-btn" type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', padding: '12px', fontSize: '16px' }}>
            {loading ? <><span className="spinner" /> Finalizing…</> : '✓ Approve and Finalize'}
          </button>
        </div>
      </form>
      </div>
    </div>
  )
}

import { useState } from 'react'

function confClass(confidence) {
  if (confidence >= 0.8) return 'conf-high'
  if (confidence >= 0.5) return 'conf-mid'
  return 'conf-low'
}

function confDot(confidence) {
  if (confidence >= 0.8) return '🟢'
  if (confidence >= 0.5) return '🟡'
  return '🔴'
}

function pct(confidence) {
  return `${Math.round(confidence * 100)}%`
}

function formatValue(value) {
  if (value === null || value === undefined) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

// Resolve the verbatim snippet and source URL from either v1 or v2 field shapes
function getSnippet(field) {
  // v2 shape: field.citation.verbatim_snippet
  if (field?.citation?.verbatim_snippet) return field.citation.verbatim_snippet
  // v1 shape: field.source_snippet
  if (field?.source_snippet) return field.source_snippet
  return null
}

function getSource(field) {
  if (field?.citation?.source_url) return field.citation.source_url
  if (field?.source) return field.source
  return null
}

function SpecRow({ fieldName, field, flagged }) {
  const [expanded, setExpanded] = useState(false)
  const cls = confClass(field.confidence)
  const snippet = getSnippet(field)
  const source = getSource(field)

  return (
    <>
      <tr
        className="spec-row"
        onClick={() => setExpanded(e => !e)}
        id={`spec-row-${fieldName}`}
        title="Click to see source details"
      >
        <td>
          <span className="spec-field-name">{fieldName.replace(/_/g, ' ')}</span>
          {flagged && (
            <span style={{ marginLeft: 6, fontSize: '0.65rem', background: 'rgba(245,158,11,0.15)', color: 'var(--color-conf-mid)', borderRadius: 999, padding: '1px 6px', border: '1px solid rgba(245,158,11,0.3)' }}>
              ⚠ review
            </span>
          )}
        </td>
        <td className="spec-value">{formatValue(field.value)}</td>
        <td>
          <span className={`conf-badge ${cls}`}>
            {confDot(field.confidence)} {pct(field.confidence)}
          </span>
        </td>
        <td style={{ color: 'var(--color-text-muted)', fontSize: '0.78rem' }}>
          {field.method}
        </td>
        <td style={{ color: 'var(--color-text-muted)', fontSize: '1rem', textAlign: 'right' }}>
          {expanded ? '▲' : '▼'}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} style={{ padding: 0 }}>
            <div className="spec-expand">
              {snippet ? (
                <>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                    Source Snippet
                  </div>
                  <div className="spec-snippet">"{snippet}"</div>
                </>
              ) : (
                <div style={{ color: 'var(--color-text-muted)', fontSize: '0.82rem', fontStyle: 'italic' }}>
                  <div style={{ marginBottom: 4 }}>No verbatim source snippet — value was inferred.</div>
                  {field?.cause && (
                    <div style={{ color: 'var(--color-text)', marginBottom: 4 }}>
                      <strong>Reason:</strong> {field.cause}
                    </div>
                  )}
                  {field?.citation?.similar_products_used?.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <strong>Inferred from similar products:</strong>
                      <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                        {field.citation.similar_products_used.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {source && (
                <div className="spec-source" style={{ marginTop: 8 }}>
                  📄 <strong>Source:</strong>{' '}
                  {source.startsWith('http') ? (
                    <a href={source} target="_blank" rel="noreferrer">{source}</a>
                  ) : (
                    source
                  )}
                </div>
              )}
              {/* v2 page + doc_id citation info */}
              {field?.citation?.doc_id && (
                <div style={{ marginTop: 4, fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                  Doc ID: {field.citation.doc_id.slice(0, 8)}… · Page {field.citation.page ?? 0}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// Commerce copy section (v2 only)
function CommerceCopy({ seo_title, long_description, bullet_points }) {
  const hasCopy = seo_title || long_description || (bullet_points && bullet_points.length > 0)
  if (!hasCopy) return null

  return (
    <div className="card commerce-copy-card" style={{ marginTop: 'var(--space-md)' }}>
      <div style={{ padding: 'var(--space-md) var(--space-lg)', borderBottom: '1px solid var(--color-border)' }}>
        <div className="card-title" style={{ marginBottom: 0 }}>
          ✍️ Commerce-Ready Copy
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
          AI-generated from validated facts only — no hallucinations.
        </div>
      </div>
      <div style={{ padding: 'var(--space-lg)' }}>
        {seo_title && (
          <div className="copy-section">
            <div className="copy-label">SEO Title</div>
            <div className="copy-seo-title">{seo_title}</div>
          </div>
        )}
        {long_description && (
          <div className="copy-section">
            <div className="copy-label">Product Description</div>
            <p className="copy-description">{long_description}</p>
          </div>
        )}
        {bullet_points && bullet_points.length > 0 && (
          <div className="copy-section">
            <div className="copy-label">Specification Bullets</div>
            <ul className="copy-bullets">
              {bullet_points.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

// Stage log accordion (v2 audit trail)
function StageLog({ stage_log }) {
  const [open, setOpen] = useState(false)
  if (!stage_log || stage_log.length === 0) return null

  return (
    <div className="stage-log-accordion" style={{ marginTop: 'var(--space-md)' }}>
      <button
        id="stage-log-toggle"
        className="stage-log-toggle"
        onClick={() => setOpen(o => !o)}
      >
        <span>📋 Pipeline Audit Log ({stage_log.length} entries)</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="stage-log-body">
          {stage_log.map((entry, i) => (
            <div key={i} className="stage-log-entry">{entry}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ResultCard({ product, onReview }) {
  if (!product) return null

  const {
    brand, mpn, category, subcategory, description,
    specifications, certifications,
    // v1 shape uses flagged_for_review, v2 uses flagged_fields
    flagged_for_review, flagged_fields,
    overall_confidence,
    // v2 extra fields
    job_id, pipeline_status, hitl_required,
    seo_title, long_description, bullet_points,
    stage_log,
  } = product

  // Normalise: v2 uses flagged_fields, v1 uses flagged_for_review
  const flagged = flagged_fields || flagged_for_review || []

  // Sort specs: high confidence first
  const sortedSpecs = Object.entries(specifications || {}).sort(
    ([, a], [, b]) => b.confidence - a.confidence
  )

  const statusColor = pipeline_status === 'completed' ? 'var(--color-conf-high)'
    : pipeline_status === 'hitl_paused' ? 'var(--color-conf-mid)'
    : pipeline_status === 'failed' ? 'var(--color-conf-low)'
    : 'var(--color-text-muted)'

  return (
    <div style={{ marginTop: 'var(--space-xl)' }}>
      {/* Header card */}
      <div className="card" id="result-card">
        <div className="result-header">
          <div className="result-brand-mpn" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
              <div>
                <div className="result-brand">{brand}</div>
                <div className="result-mpn">{mpn}</div>
              </div>
              {pipeline_status && (
                <span className="result-status-badge" style={{ color: statusColor, borderColor: statusColor }}>
                  {pipeline_status === 'completed' ? '✓' : pipeline_status === 'hitl_paused' ? '⏸' : pipeline_status === 'failed' ? '✗' : '⟳'}{' '}
                  {pipeline_status}
                </span>
              )}
            </div>

            <div style={{ marginTop: 'var(--space-sm)', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <span className="result-category-badge">⚙ {category}</span>
              {subcategory && (
                <span className="result-category-badge" style={{ background: 'rgba(139,92,246,0.1)', borderColor: 'rgba(139,92,246,0.3)', color: 'var(--color-accent-2)' }}>
                  {subcategory}
                </span>
              )}
            </div>

            <div className="result-description">{description}</div>

            {certifications && certifications.length > 0 && (
              <div className="certs-section">
                <span style={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>Certifications:</span>
                {certifications.map((c, i) => <span key={i} className="cert-chip">{c}</span>)}
              </div>
            )}

            {job_id && (
              <div style={{ marginTop: 'var(--space-sm)', fontSize: '0.72rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                Job: {job_id}
              </div>
            )}
          </div>

          {/* Overall confidence ring */}
          <div className="overall-conf-ring">
            <div className="conf-ring-value">{pct(overall_confidence)}</div>
            <div className="conf-ring-label">Overall<br/>Confidence</div>
          </div>
        </div>
      </div>

      {/* HITL notice — if paused, prompt to review */}
      {hitl_required && (
        <div className="hitl-notice" id="hitl-notice">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '1.4rem' }}>⏸</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: 2 }}>Pipeline Paused for Human Review</div>
              <div style={{ fontSize: '0.85rem', opacity: 0.85 }}>
                Overall confidence ({pct(overall_confidence)}) is below the 90% threshold. Review flagged fields to generate commerce copy.
              </div>
            </div>
          </div>
          {onReview && (
            <button className="btn btn-primary" onClick={onReview} id="show-hitl-btn">
              🧑‍💻 Open Review Panel
            </button>
          )}
        </div>
      )}

      {/* Specifications table */}
      {sortedSpecs.length > 0 && (
        <div className="card" style={{ marginTop: 'var(--space-md)', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: 'var(--space-md) var(--space-lg)', borderBottom: '1px solid var(--color-border)' }}>
            <div className="card-title" style={{ marginBottom: 0 }}>
              Specifications — {sortedSpecs.length} fields
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
              Click any row to reveal the source snippet
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="spec-table">
              <thead>
                <tr>
                  <th style={{ width: '30%' }}>Field</th>
                  <th style={{ width: '30%' }}>Value</th>
                  <th style={{ width: '15%' }}>Confidence</th>
                  <th style={{ width: '15%' }}>Method</th>
                  <th style={{ width: '10%' }}></th>
                </tr>
              </thead>
              <tbody>
                {sortedSpecs.map(([fname, field]) => (
                  <SpecRow
                    key={fname}
                    fieldName={fname}
                    field={field}
                    flagged={flagged?.includes(fname)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Commerce Copy section (v2) */}
      <CommerceCopy
        seo_title={seo_title}
        long_description={long_description}
        bullet_points={bullet_points}
      />

      {/* Flagged for review */}
      {flagged && flagged.length > 0 && (
        <div className="flagged-section">
          <div className="flagged-title">
            ⚠ Flagged for Human Review ({flagged.length})
          </div>
          <div className="flagged-list">
            {flagged.map((f, i) => (
              <span key={i} className="flagged-chip">{f.replace(/_/g, ' ')}</span>
            ))}
          </div>
        </div>
      )}

      {/* Stage Log accordion */}
      <StageLog stage_log={stage_log} />
    </div>
  )
}

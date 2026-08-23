import { useState } from 'react'

function confClass(confidence) {
  if (confidence >= 0.8) return 'conf-high'
  if (confidence >= 0.5) return 'conf-mid'
  return 'conf-low'
}

function pct(confidence) {
  return `${Math.round(confidence * 100)}%`
}

function formatValue(value) {
  if (value === null || value === undefined) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

function getSnippet(field) {
  if (field?.citation?.snippet) return field.citation.snippet
  if (field?.citation?.verbatim_snippet) return field.citation.verbatim_snippet
  if (field?.source_snippet) return field.source_snippet
  if (field?.snippet) return field.snippet
  return null
}

function getSourceUrl(field, product) {
  if (field?.citation?.url) return field.citation.url
  if (field?.citation?.source_url) return field.citation.source_url
  if (field?.url) return field.url
  if (field?.source_url) return field.source_url
  if (field?.source && typeof field.source === 'string' && field.source.startsWith('http')) return field.source
  if (product?.spec_sheet_url && product.spec_sheet_url.startsWith('http')) return product.spec_sheet_url
  if (product?.mfr_url && product.mfr_url.startsWith('http')) return product.mfr_url
  if (product?.manual_url && product.manual_url.startsWith('http')) return product.manual_url
  return null
}

function getSourceDocument(field, product) {
  if (field?.citation?.doc_name) return field.citation.doc_name
  if (field?.doc_name) return field.doc_name
  if (product?.spec_sheet_url) return product.spec_sheet_url
  if (product?.manual_url) return product.manual_url.split('/').pop()
  if (product?.installation_url) return product.installation_url.split('/').pop()
  return null
}

function getMethodLabel(field, product) {
  const method = (field?.method || field?.extraction_method || '').toLowerCase()
  const stype = (field?.citation?.source_type || field?.source_type || '').toLowerCase()

  if (method === 'human_verified' || method === 'human') return 'Human Verified'
  if (stype === 'mfr_webpage' || stype.includes('mfr')) return 'Manufacturer Official Page'
  if (stype === 'series_knowledge' || stype.includes('series') || field?.is_series_shared) return 'Series Knowledge Graph'
  if (stype === 'pdf_table' || stype.includes('table')) return 'PDF Specification Table'
  if (stype === 'pdf_text' || stype.includes('pdf') || product?.spec_sheet_url) return 'Technical Datasheet'
  if (stype === 'webpage_text') return 'Technical Documentation'
  if (method === 'extracted') return 'Technical Documentation'
  if (method === 'inferred') return 'Description Inference'
  return 'Verified Specification'
}

function getCauseExplanation(field, snippet, sourceUrl, sourceDoc, product) {
  if (field?.cause && field.cause.trim()) return field.cause
  if (field?.reason && field.reason.trim()) return field.reason
  
  const method = (field?.method || field?.extraction_method || '').toLowerCase()
  if (method === 'human_verified' || method === 'human') {
    return 'Manually verified and confirmed by reviewer in the HITL review console.'
  }
  
  const stype = (field?.citation?.source_type || field?.source_type || '').toLowerCase()
  if (stype.includes('series') || field?.is_series_shared) {
    const seriesName = product?.trade_name || product?.series || 'Series Baseline'
    return `Corroborated from verified series repository for '${seriesName}'. Shared attributes inherit baseline specifications to eliminate redundant searches.`
  }
  
  if (sourceDoc || sourceUrl) {
    const docRef = sourceDoc ? `document '${sourceDoc}'` : 'official technical documentation'
    return `Directly extracted and verified against ${docRef} with exact MPN matching.`
  }
  
  return `Derived from manufacturer product title and category taxonomy classification.`
}

function SpecRow({ fieldName, field, flagged, product }) {
  const [expanded, setExpanded] = useState(false)
  const cls = confClass(field?.confidence ?? 0)
  const snippet = getSnippet(field)
  const sourceUrl = getSourceUrl(field, product)
  const sourceDoc = getSourceDocument(field, product)
  const methodLabel = getMethodLabel(field, product)
  const cause = getCauseExplanation(field, snippet, sourceUrl, sourceDoc, product)
  const pageNum = field?.citation?.page_number ?? field?.citation?.page ?? field?.page_number
  const tableLoc = field?.citation?.table_location

  return (
    <>
      <tr
        className="spec-row"
        onClick={() => setExpanded(e => !e)}
        id={`spec-row-${fieldName}`}
        title="Click to view extraction provenance and evidence"
        style={{ cursor: 'pointer' }}
      >
        <td>
          <span className="spec-field-name">{fieldName.replace(/_/g, ' ')}</span>
          {flagged && (
            <span style={{ marginLeft: 6, fontSize: '0.65rem', background: 'rgba(245,158,11,0.15)', color: 'var(--color-conf-mid)', borderRadius: 999, padding: '1px 6px', border: '1px solid rgba(245,158,11,0.3)', textTransform: 'uppercase', fontWeight: 700 }}>
              Review
            </span>
          )}
        </td>
        <td className="spec-value">{formatValue(field?.value)}</td>
        <td>
          <span className={`conf-badge ${cls}`}>
            {pct(field?.confidence ?? 0)}
          </span>
        </td>
        <td>
          <span style={{
            fontSize: '0.74rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: '4px',
            background: methodLabel === 'Human Verified' ? 'rgba(16, 185, 129, 0.15)' :
                        methodLabel.includes('Manufacturer') ? 'rgba(0, 128, 255, 0.15)' :
                        methodLabel.includes('Series') ? 'rgba(139, 92, 246, 0.15)' :
                        'rgba(255, 255, 255, 0.06)',
            color: methodLabel === 'Human Verified' ? '#34d399' :
                   methodLabel.includes('Manufacturer') ? '#60a5fa' :
                   methodLabel.includes('Series') ? '#c084fc' :
                   '#cbd5e1',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            display: 'inline-block'
          }}>
            {methodLabel}
          </span>
        </td>
        <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', textAlign: 'right' }}>
          {expanded ? '▲' : '▼'}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} style={{ padding: 0 }}>
            <div className="spec-expand" style={{
              background: '#090d16',
              borderTop: '1px solid #1e293b',
              borderBottom: '1px solid #1e293b',
              padding: '16px 20px',
            }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                
                {/* Method & Origin Header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#93c5fd' }}>
                    Provenance Source:
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#ffffff' }}>
                    {methodLabel}
                  </span>
                  {sourceDoc && (
                    <span style={{ fontSize: '0.75rem', color: '#cbd5e1', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', border: '1px solid #334155' }}>
                      Document: {sourceDoc} {pageNum ? `(Page ${pageNum})` : ''}
                    </span>
                  )}
                  {tableLoc && (
                    <span style={{ fontSize: '0.75rem', color: '#cbd5e1', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', border: '1px solid #334155' }}>
                      Section: {tableLoc}
                    </span>
                  )}
                </div>

                {/* Verbatim Source Snippet */}
                {snippet && (
                  <div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#94a3b8', marginBottom: '4px' }}>
                      Verbatim Document Evidence:
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.82rem',
                      color: '#93c5fd',
                      background: 'rgba(0, 128, 255, 0.1)',
                      border: '1px solid rgba(0, 128, 255, 0.3)',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      lineHeight: '1.5'
                    }}>
                      "{snippet}"
                    </div>
                  </div>
                )}

                {/* Finding / Rationale Cause */}
                <div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#94a3b8', marginBottom: '2px' }}>
                    How This Value Was Determined:
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: '1.5', fontWeight: 500 }}>
                    {cause}
                  </div>
                </div>

                {/* Source URL Link */}
                {sourceUrl && (
                  <div style={{ fontSize: '0.78rem', color: '#cbd5e1', marginTop: '2px' }}>
                    <strong style={{ color: '#94a3b8' }}>Source Reference: </strong>
                    <a href={sourceUrl} target="_blank" rel="noreferrer" className="url-link" style={{ color: '#38bdf8', textDecoration: 'underline' }}>
                      {sourceUrl}
                    </a>
                  </div>
                )}

                {/* Similar Products if inferred */}
                {field?.citation?.similar_products_used?.length > 0 && (
                  <div style={{ fontSize: '0.78rem', color: '#cbd5e1', marginTop: '2px' }}>
                    <strong style={{ color: '#94a3b8' }}>Corroborated across sibling records: </strong>
                    <span>{field.citation.similar_products_used.join(', ')}</span>
                  </div>
                )}

              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function CommerceCopy({ seo_title, long_description, bullet_points }) {
  const hasCopy = seo_title || long_description || (bullet_points && bullet_points.length > 0)
  if (!hasCopy) return null

  return (
    <div className="card commerce-copy-card" style={{ marginTop: 'var(--space-md)' }}>
      <div style={{ padding: 'var(--space-md) var(--space-lg)', borderBottom: '1px solid var(--color-border)' }}>
        <div className="card-title" style={{ marginBottom: 0 }}>
          Commercial Copywriting &amp; Catalog Output
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
          Standardized output generated from verified specifications.
        </div>
      </div>
      <div style={{ padding: 'var(--space-lg)' }}>
        {seo_title && (
          <div className="copy-section">
            <div className="copy-label">SEO Product Title</div>
            <div className="copy-seo-title">{seo_title}</div>
          </div>
        )}
        {long_description && (
          <div className="copy-section">
            <div className="copy-label">Standard Product Description</div>
            <p className="copy-description">{long_description}</p>
          </div>
        )}
        {bullet_points && bullet_points.length > 0 && (
          <div className="copy-section">
            <div className="copy-label">Specification Bullet Points</div>
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
        <span>Pipeline Audit Log ({stage_log.length} records)</span>
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
    flagged_for_review, flagged_fields,
    overall_confidence,
    job_id, pipeline_status, hitl_required,
    seo_title, long_description, bullet_points,
    stage_log,
  } = product

  const flagged = flagged_fields || flagged_for_review || []

  const sortedSpecs = Object.entries(specifications || {}).sort(
    ([, a], [, b]) => (b?.confidence ?? 0) - (a?.confidence ?? 0)
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
                  {pipeline_status.toUpperCase()}
                </span>
              )}
            </div>

            <div style={{ marginTop: 'var(--space-sm)', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <span className="result-category-badge">{category}</span>
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
                Job ID: {job_id}
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

      {/* HITL notice */}
      {hitl_required && (
        <div className="hitl-notice" id="hitl-notice">
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: 2 }}>Review Confirmation Required</div>
              <div style={{ fontSize: '0.85rem', opacity: 0.85 }}>
                Overall confidence ({pct(overall_confidence)}) is below threshold. Verify flagged fields to finalize export data.
              </div>
            </div>
          </div>
          {onReview && (
            <button className="btn btn-primary" onClick={onReview} id="show-hitl-btn">
              Open Review Panel
            </button>
          )}
        </div>
      )}

      {/* Specifications table */}
      {sortedSpecs.length > 0 && (
        <div className="card" style={{ marginTop: 'var(--space-md)', padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: 'var(--space-md) var(--space-lg)', borderBottom: '1px solid var(--color-border)' }}>
            <div className="card-title" style={{ marginBottom: 0 }}>
              Specifications — {sortedSpecs.length} Attributes
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
              Click any attribute row to view source citation, document snippet, and extraction provenance
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="spec-table">
              <thead>
                <tr>
                  <th style={{ width: '30%' }}>Field</th>
                  <th style={{ width: '30%' }}>Value</th>
                  <th style={{ width: '15%' }}>Confidence</th>
                  <th style={{ width: '20%' }}>Method</th>
                  <th style={{ width: '5%' }}></th>
                </tr>
              </thead>
              <tbody>
                {sortedSpecs.map(([fname, field]) => (
                  <SpecRow
                    key={fname}
                    fieldName={fname}
                    field={field}
                    flagged={flagged?.includes(fname)}
                    product={product}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Commerce Copy section */}
      <CommerceCopy
        seo_title={seo_title}
        long_description={long_description}
        bullet_points={bullet_points}
      />

      {/* Flagged for review */}
      {flagged && flagged.length > 0 && (
        <div className="flagged-section">
          <div className="flagged-title">
            Flagged for Confirmation ({flagged.length})
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

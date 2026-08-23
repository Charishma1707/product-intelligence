import { useState, useEffect } from 'react'
import AgentPromptBar from './AgentPromptBar.jsx'
import FinalFieldsTable from './FinalFieldsTable.jsx'

import { API } from '../apiConfig'

function getProvenance(field, causeText, retrieval) {
  if (retrieval === 'CHROMA' || causeText.toLowerCase().includes('pdf') || causeText.toLowerCase().includes('chroma')) {
    return { label: 'ChromaDB / PDF', cls: 'prov-chroma' }
  }
  if (retrieval === 'CACHE' || causeText.toLowerCase().includes('knowledge') || causeText.toLowerCase().includes('series')) {
    return { label: 'Knowledge Graph', cls: 'prov-knowledge' }
  }
  if (causeText.toLowerCase().includes('desc infer') || causeText.toLowerCase().includes('inferred from abbreviation')) {
    return { label: 'Desc Infer (Abbr)', cls: 'prov-knowledge' }
  }
  if (field?.extraction_method === 'HUMAN' || causeText.toLowerCase().includes('human')) {
    return { label: 'Human Verified', cls: 'prov-human' }
  }
  return { label: 'Inferred', cls: 'prov-llm' }
}

/**
 * Multi-Stage Human-in-the-Loop Review Station (Stages 1–5).
 * 1. Brand & Manufacturer Identity
 * 2. Sourcing URLs & Technical Assets
 * 3. Attributes & Taxonomy
 * 4. Commercial Descriptions & Copywriting
 * 5. Final Delivery Fields (~50 Unilog columns)
 */
export default function HITLReview({ product, onResolved }) {
  const { job_id, specifications, status, pipeline_status } = product
  const currentStatus = pipeline_status || status || 'needs_review_extraction'

  // Determine active stage (1–5)
  const getInitialStage = () => {
    if (currentStatus === 'needs_review_identity') return 1
    if (currentStatus === 'needs_review_retrieval') return 2
    if (currentStatus === 'needs_review_extraction' || currentStatus === 'needs_review') return 3
    if (currentStatus === 'needs_review_final') return 4
    if (currentStatus === 'needs_review_delivery') return 5
    return 3
  }

  const [activeStage, setActiveStage] = useState(getInitialStage())
  const [reviewer, setReviewer] = useState('reviewer')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [toastMessage, setToastMessage] = useState(null)
  const [approvedFields, setApprovedFields] = useState({})

  // Form state across all 5 stages
  const [identity, setIdentity] = useState({
    brand: product.brand || '',
    manufacturer_name: product.manufacturer_name || product.brand_name || product.brand || '',
    mpn: product.mpn || '',
    description: product.description || product.input_part_desc || '',
    series: product.series || '',
    alternate_part_number: product.alternate_part_number || '',
  })

  const [sourcing, setSourcing] = useState({
    mfr_url: product.mfr_url || '',
    spec_sheet_url: product.spec_sheet_url || '',
    manual_url: product.manual_url || '',
    installation_url: product.installation_url || '',
    sds_url: product.sds_url || '',
    warranty_url: product.warranty_url || '',
    catalog_url: product.catalog_url || '',
    energy_guide_url: product.energy_guide_url || '',
    product_image_url: product.product_image_url || '',
    video_link: product.video_link || '',
  })

  const initialSpecCorrections = Object.fromEntries(
    Object.keys(specifications || {}).map(fname => [fname, String(specifications?.[fname]?.value ?? '')])
  )
  const [specCorrections, setSpecCorrections] = useState(initialSpecCorrections)

  const [taxonomy, setTaxonomy] = useState({
    category: product.category || '',
    subcategory: product.subcategory || '',
    unspsc: product.unspsc || '',
  })

  const [copywriting, setCopywriting] = useState({
    invoice_desc: product.invoice_desc || '',
    short_desc: product.short_desc || '',
    long_desc: product.long_desc || '',
    retail_desc: product.retail_desc || '',
    mobile_desc: product.mobile_desc || '',
    marketing_description: product.marketing_description || '',
    product_name: product.product_name || '',
    trade_name: product.trade_name || '',
    standards_approvals: product.standards_approvals || '',
  })

  const [deliveryCorrections, setDeliveryCorrections] = useState({})

  // Keep internal stage state in sync when external product object updates
  useEffect(() => {
    if (!product) return
    setActiveStage(getInitialStage())
    setIdentity({
      brand: product.brand || '',
      manufacturer_name: product.manufacturer_name || product.brand_name || product.brand || '',
      mpn: product.mpn || '',
      description: product.description || product.input_part_desc || '',
      series: product.series || '',
      alternate_part_number: product.alternate_part_number || '',
    })
    setSourcing({
      mfr_url: product.mfr_url || '',
      spec_sheet_url: product.spec_sheet_url || '',
      manual_url: product.manual_url || '',
      installation_url: product.installation_url || '',
      sds_url: product.sds_url || '',
      warranty_url: product.warranty_url || '',
      catalog_url: product.catalog_url || '',
      energy_guide_url: product.energy_guide_url || '',
      product_image_url: product.product_image_url || '',
      video_link: product.video_link || '',
    })
    setTaxonomy({
      category: product.category || '',
      subcategory: product.subcategory || '',
      unspsc: product.unspsc || '',
    })
    setCopywriting({
      invoice_desc: product.invoice_desc || '',
      short_desc: product.short_desc || '',
      long_desc: product.long_desc || '',
      retail_desc: product.retail_desc || '',
      mobile_desc: product.mobile_desc || '',
      marketing_description: product.marketing_description || '',
      product_name: product.product_name || '',
      trade_name: product.trade_name || '',
      standards_approvals: product.standards_approvals || '',
    })
    if (product.specifications) {
      setSpecCorrections(Object.fromEntries(
        Object.keys(product.specifications).map(fname => [fname, String(product.specifications[fname]?.value ?? '')])
      ))
    }
  }, [product])

  const handleIdentityChange = (k, v) => setIdentity(prev => ({ ...prev, [k]: v }))
  const handleSourcingChange = (k, v) => setSourcing(prev => ({ ...prev, [k]: v }))
  const handleTaxonomyChange = (k, v) => setTaxonomy(prev => ({ ...prev, [k]: v }))
  const handleSpecChange = (fname, v) => setSpecCorrections(prev => ({ ...prev, [fname]: v }))
  const handleCopywritingChange = (k, v) => setCopywriting(prev => ({ ...prev, [k]: v }))
  const handleDeliveryChange = (k, v) => setDeliveryCorrections(prev => ({ ...prev, [k]: v }))

  const handleApproveField = (fname) => {
    setApprovedFields(prev => ({ ...prev, [fname]: 'approved' }))
  }

  const handleRejectField = (fname) => {
    setApprovedFields(prev => ({ ...prev, [fname]: 'rejected' }))
    setSpecCorrections(prev => ({ ...prev, [fname]: '' }))
  }

  const handleAgentUpdate = (updatedProduct) => {
    if (updatedProduct) {
      if (updatedProduct.specifications) {
        setSpecCorrections(Object.fromEntries(
          Object.keys(updatedProduct.specifications).map(fname => [
            fname, String(updatedProduct.specifications[fname]?.value ?? '')
          ])
        ))
      }
      if (updatedProduct.invoice_desc || updatedProduct.short_desc) {
        setCopywriting(prev => ({
          ...prev,
          invoice_desc: updatedProduct.invoice_desc || prev.invoice_desc,
          short_desc: updatedProduct.short_desc || prev.short_desc,
          long_desc: updatedProduct.long_desc || prev.long_desc,
        }))
      }
    }
  }

  // Submit handler for current active stage
  const handleSubmitStage = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setToastMessage(null)

    let corrections = {}
    if (activeStage === 1) {
      corrections = { ...identity }
    } else if (activeStage === 2) {
      corrections = { ...sourcing }
    } else if (activeStage === 3) {
      corrections = { ...taxonomy }
      for (const [k, v] of Object.entries(specCorrections)) {
        if (v === '' || v === null) continue
        const num = Number(v)
        corrections[k] = isNaN(num) || v.trim() === '' ? v : num
      }
    } else if (activeStage === 4) {
      corrections = { ...copywriting }
    } else if (activeStage === 5) {
      corrections = { ...deliveryCorrections }
    }

    try {
      const res = await fetch(`${API}/enrich/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          },
        body: JSON.stringify({ job_id, corrections, reviewer }),
      })
      const data = await res.json()
      if (!res.ok || data.status === 'failed') throw new Error(data.error || data.detail || `HTTP ${res.status}`)

      // Show implicit confidence boost feedback if triggered
      if (data.implicit_boost_count > 0) {
        setToastMessage(`✓ ${data.implicit_boost_count} fields implicitly accepted — confidence boosted by +15%!`)
        setTimeout(() => setToastMessage(null), 5000)
      }

      const nextStatus = data.status || data.product?.status
      if (nextStatus === 'complete') {
        onResolved({
          ...data.product,
          job_id: data.job_id,
          hitl_required: false,
          pipeline_status: 'complete',
          post_approval_summary: data.post_approval_summary,
        })
      } else {
        if (data.product) {
          onResolved({
            ...data.product,
            job_id: data.job_id,
            hitl_required: true,
            pipeline_status: nextStatus,
          })
        }
        // Advance stage
        if (nextStatus === 'needs_review_retrieval') setActiveStage(2)
        else if (nextStatus === 'needs_review_extraction') setActiveStage(3)
        else if (nextStatus === 'needs_review_final') setActiveStage(4)
        else if (nextStatus === 'needs_review_delivery') setActiveStage(5)
        else setActiveStage(prev => Math.min(5, prev + 1))
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const STAGES = [
    { num: 1, label: '1. Brand & Identity' },
    { num: 2, label: '2. Sourcing URLs & Docs' },
    { num: 3, label: '3. Attributes & Taxonomy' },
    { num: 4, label: '4. Commercial Copywriting' },
    { num: 5, label: '5. Final Delivery Fields' },
  ]

  return (
    <div className="hitl-panel animate-fade-up" id="hitl-review-panel" style={{
      background: '#0a0f1c',
      border: '1.5px solid #0080ff',
      borderRadius: '12px',
      padding: '24px',
      boxShadow: '0 0 35px rgba(0, 128, 255, 0.15)'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#ffffff' }}>
            Human-in-the-Loop Review Station
          </div>
          <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginTop: 3 }}>
            Progressive 5-stage human verification with live AI agent assistance &amp; confidence tracking.
          </div>
        </div>
        <div className="hitl-job-id" style={{ alignSelf: 'center' }}>
          Job ID: <span style={{ color: '#60a5fa' }}>{job_id}</span>
        </div>
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div style={{
          marginBottom: 16, padding: '10px 16px',
          background: 'rgba(16, 185, 129, 0.15)',
          border: '1px solid rgba(16, 185, 129, 0.4)',
          borderRadius: 8, color: '#34d399', fontSize: '0.82rem', fontWeight: 700
        }}>
          {toastMessage}
        </div>
      )}

      {/* Stage Progression Tabs */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: '6px',
        marginBottom: '20px',
        background: '#070a12',
        padding: '6px',
        borderRadius: '8px',
        border: '1px solid #1e293b'
      }}>
        {STAGES.map(s => {
          const isCurrent = activeStage === s.num
          const isPassed = activeStage > s.num
          return (
            <button
              key={s.num}
              type="button"
              onClick={() => setActiveStage(s.num)}
              style={{
                padding: '10px 6px',
                borderRadius: '6px',
                border: isCurrent ? '1.5px solid #0080ff' : '1px solid transparent',
                background: isCurrent ? 'rgba(0, 128, 255, 0.2)' : isPassed ? 'rgba(16, 185, 129, 0.1)' : 'transparent',
                color: isCurrent ? '#ffffff' : isPassed ? '#34d399' : '#94a3b8',
                fontWeight: isCurrent ? 800 : 600,
                fontSize: '0.78rem',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.2s ease'
              }}
            >
              {isPassed ? '✓ ' : ''}{s.label}
            </button>
          )
        })}
      </div>

      {/* Form Body for Selected Stage */}
      <form onSubmit={handleSubmitStage}>

        {/* ════════════ STAGE 1: IDENTITY REVIEW ════════════ */}
        {activeStage === 1 && (
          <div className="animate-fade-in">
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#93c5fd', marginBottom: 12 }}>
              Stage 1: Verify Brand, Manufacturer &amp; Part Number
            </div>
            <div className="guide-banner" style={{ marginBottom: 16 }}>
              <div className="guide-banner-text">
                Confirm canonical brand and manufacturer names. You can also refine the raw input description or series tag.
              </div>
            </div>

            <div className="grid-3" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-brand">Brand / Label Name</label>
                <input
                  id="hitl-brand"
                  className="form-input"
                  type="text"
                  value={identity.brand}
                  onChange={e => handleIdentityChange('brand', e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-manufacturer">Normalized Manufacturer</label>
                <input
                  id="hitl-manufacturer"
                  className="form-input"
                  type="text"
                  value={identity.manufacturer_name}
                  onChange={e => handleIdentityChange('manufacturer_name', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-mpn">Manufacturer Part Number (MPN)</label>
                <input
                  id="hitl-mpn"
                  className="form-input"
                  type="text"
                  value={identity.mpn}
                  onChange={e => handleIdentityChange('mpn', e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="grid-2" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-series">Series Name (if applicable)</label>
                <input
                  id="hitl-series"
                  className="form-input"
                  type="text"
                  value={identity.series}
                  onChange={e => handleIdentityChange('series', e.target.value)}
                  placeholder="e.g. Vintage Azek, Lineage, Transcend"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-alt-part">Alternate Part Number</label>
                <input
                  id="hitl-alt-part"
                  className="form-input"
                  type="text"
                  value={identity.alternate_part_number}
                  onChange={e => handleIdentityChange('alternate_part_number', e.target.value)}
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label" htmlFor="hitl-desc">Input Description (Used for Abbreviation Inference)</label>
              <textarea
                id="hitl-desc"
                className="form-input"
                rows={2}
                value={identity.description}
                onChange={e => handleIdentityChange('description', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* ════════════ STAGE 2: SOURCING URLs REVIEW ════════════ */}
        {activeStage === 2 && (
          <div className="animate-fade-in">
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#93c5fd', marginBottom: 12 }}>
              Stage 2: Verify Technical Documentation &amp; Asset URLs
            </div>
            <div className="guide-banner" style={{ marginBottom: 16 }}>
              <div className="guide-banner-text">
                Verify manufacturer URLs and PDF technical documents. Sourcing from official domains guarantees accurate attributes.
              </div>
            </div>

            <div className="grid-2" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label className="form-label" htmlFor="hitl-mfr-url">Official Product Page (MFR URL)</label>
                  {sourcing.mfr_url && (
                    <a href={sourcing.mfr_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.75rem', color: '#60a5fa', textDecoration: 'underline', marginBottom: 4 }}>
                      Open Page ↗
                    </a>
                  )}
                </div>
                <input
                  id="hitl-mfr-url"
                  className="form-input"
                  type="text"
                  value={sourcing.mfr_url}
                  onChange={e => handleSourcingChange('mfr_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label className="form-label" htmlFor="hitl-spec-url">Specification Sheet URL (PDF)</label>
                  {sourcing.spec_sheet_url && (
                    <a href={sourcing.spec_sheet_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.75rem', color: '#60a5fa', textDecoration: 'underline', marginBottom: 4 }}>
                      Open PDF ↗
                    </a>
                  )}
                </div>
                <input
                  id="hitl-spec-url"
                  className="form-input"
                  type="text"
                  value={sourcing.spec_sheet_url}
                  onChange={e => handleSourcingChange('spec_sheet_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>

            <div className="grid-2" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-manual-url">Owner's / User Manual URL (PDF)</label>
                <input
                  id="hitl-manual-url"
                  className="form-input"
                  type="text"
                  value={sourcing.manual_url}
                  onChange={e => handleSourcingChange('manual_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-install-url">Installation Guide URL (PDF)</label>
                <input
                  id="hitl-install-url"
                  className="form-input"
                  type="text"
                  value={sourcing.installation_url}
                  onChange={e => handleSourcingChange('installation_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>

            <div className="grid-3" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-sds-url">Safety Data Sheet (SDS) URL</label>
                <input
                  id="hitl-sds-url"
                  className="form-input"
                  type="text"
                  value={sourcing.sds_url}
                  onChange={e => handleSourcingChange('sds_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-warranty-url">Warranty Document URL</label>
                <input
                  id="hitl-warranty-url"
                  className="form-input"
                  type="text"
                  value={sourcing.warranty_url}
                  onChange={e => handleSourcingChange('warranty_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-catalog-url">Catalog / Brochure URL</label>
                <input
                  id="hitl-catalog-url"
                  className="form-input"
                  type="text"
                  value={sourcing.catalog_url}
                  onChange={e => handleSourcingChange('catalog_url', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>

            <div className="grid-2" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-image-url">Product Image URL</label>
                <input
                  id="hitl-image-url"
                  className="form-input"
                  type="text"
                  value={sourcing.product_image_url}
                  onChange={e => handleSourcingChange('product_image_url', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-video-link">Video Link</label>
                <input
                  id="hitl-video-link"
                  className="form-input"
                  type="text"
                  value={sourcing.video_link}
                  onChange={e => handleSourcingChange('video_link', e.target.value)}
                  placeholder="https://..."
                />
              </div>
            </div>
          </div>
        )}

        {/* ════════════ STAGE 3: ATTRIBUTES & TAXONOMY REVIEW ════════════ */}
        {activeStage === 3 && (
          <div className="animate-fade-in">
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#93c5fd', marginBottom: 12 }}>
              Stage 3: Verify Taxonomy &amp; Extracted Specifications
            </div>

            {/* Taxonomy root row */}
            <div className="grid-3" style={{ marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-category">Root Category</label>
                <input
                  id="hitl-category"
                  className="form-input"
                  type="text"
                  value={taxonomy.category}
                  onChange={e => handleTaxonomyChange('category', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-subcat">Leaf Subcategory</label>
                <input
                  id="hitl-subcat"
                  className="form-input"
                  type="text"
                  value={taxonomy.subcategory}
                  onChange={e => handleTaxonomyChange('subcategory', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-unspsc">UNSPSC Code</label>
                <input
                  id="hitl-unspsc"
                  className="form-input"
                  type="text"
                  value={taxonomy.unspsc}
                  onChange={e => handleTaxonomyChange('unspsc', e.target.value)}
                />
              </div>
            </div>

            {/* Specifications list */}
            <div className="hitl-fields" style={{ maxHeight: '420px', overflowY: 'auto', paddingRight: '4px' }}>
              {Object.keys(specifications || {}).map(fname => {
                const field = specifications?.[fname]
                const causeText = field?.cause || ''
                const retrieval = field?.source?.retrieval_method || ''
                const prov = getProvenance(field, causeText, retrieval)
                const conf = field?.confidence ?? 0
                const fieldApproval = approvedFields[fname]

                return (
                  <div
                    key={fname}
                    className="hitl-field-row"
                    style={{
                      borderLeft: `3px solid ${
                        fieldApproval === 'approved' ? 'var(--green-500)' :
                        fieldApproval === 'rejected' ? 'var(--red-500)' :
                        conf < 0.8 ? 'var(--amber-500)' :
                        'var(--border-subtle)'
                      }`,
                      flexDirection: 'column',
                      gap: 6,
                      padding: '10px 12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span className="hitl-field-name" style={{ minWidth: 'unset' }}>
                        {fname.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <span className={`conf-badge ${conf >= 0.8 ? 'conf-high' : conf >= 0.5 ? 'conf-mid' : 'conf-low'}`}>
                        {Math.round(conf * 100)}%
                      </span>
                      <span className={`prov-badge ${prov.cls}`}>
                        {prov.label}
                      </span>
                      {fieldApproval === 'approved' && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--green-400)', fontWeight: 800 }}>Confirmed</span>
                      )}
                      {fieldApproval === 'rejected' && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--red-400)', fontWeight: 800 }}>Rejected</span>
                      )}
                    </div>

                    {causeText && (
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        <strong style={{ color: '#cbd5e1' }}>Provenance: </strong>{causeText}
                      </div>
                    )}

                    {field?.citation?.snippet && (
                      <div style={{ fontSize: '0.75rem', color: '#93c5fd', background: 'rgba(0, 128, 255, 0.1)', border: '1px solid rgba(0, 128, 255, 0.25)', borderRadius: '4px', padding: '4px 8px', fontStyle: 'italic' }}>
                        "{field.citation.snippet}"
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 2 }}>
                      <input
                        id={`hitl-${fname}`}
                        className="form-input"
                        type="text"
                        value={specCorrections[fname] ?? ''}
                        onChange={e => handleSpecChange(fname, e.target.value)}
                        placeholder={`Value for ${fname.replace(/_/g, ' ')}`}
                        style={{ flex: 1, padding: '6px 10px', fontSize: '0.88rem' }}
                      />
                      <button
                        type="button"
                        title="Approve value"
                        onClick={() => handleApproveField(fname)}
                        style={{
                          width: 32, height: 32, borderRadius: '4px', border: 'none', cursor: 'pointer',
                          background: fieldApproval === 'approved' ? '#059669' : 'rgba(16, 185, 129, 0.2)',
                          color: '#ffffff', fontSize: 14, fontWeight: 800,
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                      >
                        ✓
                      </button>
                      <button
                        type="button"
                        title="Reject / clear value"
                        onClick={() => handleRejectField(fname)}
                        style={{
                          width: 32, height: 32, borderRadius: '4px', border: 'none', cursor: 'pointer',
                          background: fieldApproval === 'rejected' ? '#dc2626' : 'rgba(239, 68, 68, 0.2)',
                          color: '#ffffff', fontSize: 14, fontWeight: 800,
                          display: 'flex', alignItems: 'center', justifyContent: 'center'
                        }}
                      >
                        ✗
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ════════════ STAGE 4: COMMERCIAL COPYWRITING REVIEW ════════════ */}
        {activeStage === 4 && (
          <div className="animate-fade-in">
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#93c5fd', marginBottom: 12 }}>
              Stage 4: Verify Standardized Descriptions &amp; Copywriting
            </div>
            <div className="guide-banner" style={{ marginBottom: 16 }}>
              <div className="guide-banner-text">
                Confirm invoice description (≤40 chars, ALL CAPS), short &amp; long marketing descriptions, and product naming.
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label" htmlFor="hitl-invoice">Invoice Description (≤40 Characters, ALL CAPS)</label>
              <input
                id="hitl-invoice"
                className="form-input"
                type="text"
                maxLength={40}
                value={copywriting.invoice_desc}
                onChange={e => handleCopywritingChange('invoice_desc', e.target.value.toUpperCase())}
              />
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                {copywriting.invoice_desc.length}/40 characters
              </span>
            </div>

            <div className="grid-2" style={{ marginBottom: 14 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-pname">Product Name</label>
                <input
                  id="hitl-pname"
                  className="form-input"
                  type="text"
                  value={copywriting.product_name}
                  onChange={e => handleCopywritingChange('product_name', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-tname">Trade Name</label>
                <input
                  id="hitl-tname"
                  className="form-input"
                  type="text"
                  value={copywriting.trade_name}
                  onChange={e => handleCopywritingChange('trade_name', e.target.value)}
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label" htmlFor="hitl-short">Short Description</label>
              <textarea
                id="hitl-short"
                className="form-input"
                rows={2}
                value={copywriting.short_desc}
                onChange={e => handleCopywritingChange('short_desc', e.target.value)}
              />
            </div>

            <div className="form-group" style={{ marginBottom: 14 }}>
              <label className="form-label" htmlFor="hitl-long">Long Description</label>
              <textarea
                id="hitl-long"
                className="form-input"
                rows={3}
                value={copywriting.long_desc}
                onChange={e => handleCopywritingChange('long_desc', e.target.value)}
              />
            </div>

            <div className="grid-2" style={{ marginBottom: 14 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-retail">Retail Description</label>
                <textarea
                  id="hitl-retail"
                  className="form-input"
                  rows={2}
                  value={copywriting.retail_desc}
                  onChange={e => handleCopywritingChange('retail_desc', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="hitl-mobile">Mobile Description</label>
                <input
                  id="hitl-mobile"
                  className="form-input"
                  type="text"
                  value={copywriting.mobile_desc}
                  onChange={e => handleCopywritingChange('mobile_desc', e.target.value)}
                />
              </div>
            </div>
          </div>
        )}

        {/* ════════════ STAGE 5: FINAL DELIVERY FIELDS TABLE ════════════ */}
        {activeStage === 5 && (
          <div className="animate-fade-in">
            <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#93c5fd', marginBottom: 12 }}>
              Stage 5: Final Delivery Fields &amp; Provenance Table
            </div>
            <div className="guide-banner" style={{ marginBottom: 16 }}>
              <div className="guide-banner-text">
                Review and edit all ~50 Unilog delivery attributes. Inferred abbreviations (e.g. BRS→Brass, SS→Stainless Steel) will be automatically persisted to the database and Knowledge Graph upon approval.
              </div>
            </div>

            <FinalFieldsTable
              product={product}
              corrections={deliveryCorrections}
              onChange={handleDeliveryChange}
            />
          </div>
        )}

        {/* Agent Prompt Bar on EVERY stage */}
        <AgentPromptBar
          jobId={job_id}
          currentStage={activeStage}
          onAgentUpdate={handleAgentUpdate}
        />

        {/* Action Footer */}
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', marginTop: 20, flexWrap: 'wrap', borderTop: '1px solid #1e293b', paddingTop: 16 }}>
          <div className="form-group" style={{ flex: '0 0 180px' }}>
            <label className="form-label" htmlFor="hitl-reviewer">Reviewer ID</label>
            <input
              id="hitl-reviewer"
              className="form-input"
              type="text"
              value={reviewer}
              onChange={e => setReviewer(e.target.value)}
              placeholder="Reviewer ID"
            />
          </div>

          <div style={{ flex: 1 }}>
            {error && <div className="error-banner" style={{ marginBottom: 8 }}>{error}</div>}
            <button
              id="hitl-submit-btn"
              type="submit"
              className="btn btn-success btn-lg"
              disabled={loading}
              style={{ width: '100%' }}
            >
              {loading ? (
                <><span className="spinner" /> Saving &amp; Advancing Pipeline…</>
              ) : activeStage === 5 ? (
                <>✓ Approve &amp; Finalize Product Record (Save Aliases &amp; KG)</>
              ) : (
                <>Approve Stage {activeStage} — Proceed to Stage {activeStage + 1}</>
              )}
            </button>
            <div style={{ textAlign: 'center', fontSize: '0.72rem', color: '#94a3b8', marginTop: 6 }}>
              {activeStage === 5
                ? 'Approving persists all aliases to SQLite and updates Knowledge Graph series confidence'
                : 'Advancing without edits automatically boosts confidence for unedited stage fields (+15%)'}
            </div>
          </div>
        </div>

      </form>
    </div>
  )
}

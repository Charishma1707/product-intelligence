import { useState, useEffect, useRef } from 'react'

const API = 'http://localhost:8000'  // same-origin via Vite proxy

const STAGE_MESSAGES = [
  { stage: 'interpreting', msg: 'Classifying product taxonomy and resolving brand identity…' },
  { stage: 'searching',    msg: 'Searching manufacturer websites and technical datasheets…' },
  { stage: 'extracting',   msg: 'Extracting specifications with ChromaDB RAG and series knowledge…' },
  { stage: 'validating',   msg: 'Validating extracted attributes and scoring provenance confidence…' },
  { stage: 'copywriting',  msg: 'Generating standardized descriptions and 252-column output…' },
]

export default function ProductForm({ onResult, onStageChange }) {
  const [mpn,            setMpn]           = useState('')
  const [description,    setDescription]   = useState('')
  const [partManuf,      setPartManuf]     = useState('')
  const [e1Brand,        setE1Brand]       = useState('')
  const [unilogBrand,    setUnilogBrand]   = useState('')
  const [dibBrand,       setDibBrand]      = useState('')
  const [brand,          setBrand]         = useState('')
  const [showCatalogFields, setShowCatalogFields] = useState(false)
  const [providedSchema, setSchema]        = useState('')
  const [strictSchema,   setStrict]        = useState(false)
  const [loading,        setLoading]       = useState(false)
  const [error,          setError]         = useState(null)
  const [statusMsg,      setStatusMsg]     = useState('')
  const [samples,        setSamples]       = useState([])
  const [dropdownOpen,   setDropdown]      = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    fetch(`${API}/sample-products`).then(r => r.json()).then(setSamples).catch(() => {})
  }, [])

  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setDropdown(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const loadSample = (s) => {
    setMpn(s.mpn || '')
    setDescription(s.description || '')
    setPartManuf(s.part_manuf || s.brand || '')
    setE1Brand(s.e1_brand || '')
    setUnilogBrand(s.unilog_brand || '')
    setDibBrand(s.dib_brand || '')
    setBrand(s.brand || s.part_manuf || '')
    setDropdown(false)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const activeBrand = brand.trim() || partManuf.trim() || e1Brand.trim()
    if (!mpn.trim()) return

    setLoading(true)
    setError(null)
    setStatusMsg('')
    onResult(null)

    // Simulated stage transitions while waiting for API
    const delays = [0, 3000, 7000, 12000, 16000]
    STAGE_MESSAGES.forEach(({ stage, msg }, i) => {
      setTimeout(() => {
        onStageChange(stage)
        setStatusMsg(msg)
      }, delays[i])
    })

    try {
      const res = await fetch(`${API}/enrich/v2`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          },
        body: JSON.stringify({
          brand: activeBrand,
          mpn: mpn.trim(),
          description: description.trim(),
          part_manuf: partManuf.trim(),
          e1_brand: e1Brand.trim(),
          unilog_brand: unilogBrand.trim(),
          dib_brand: dibBrand.trim(),
          provided_schema: providedSchema ? providedSchema.split(',').map(s => s.trim()).filter(Boolean) : null,
          strict_schema: strictSchema,
        }),
      })
      const data = await res.json()
      onStageChange('done')
      setStatusMsg('')

      if (data.status === 'failed') {
        setError(data.error || 'Pipeline failed — check system logs.')
        onResult(null)
      } else {
        onResult({
          ...data.product,
          job_id: data.job_id,
          hitl_required: data.hitl_required,
          pipeline_status: data.status,
        })
      }
    } catch (err) {
      setError(err.message || 'Network error — backend is unreachable.')
      onStageChange('idle')
    } finally {
      setLoading(false)
    }
  }

  const canSubmit = brand.trim() !== '' && mpn.trim() !== '' && (!strictSchema || providedSchema.trim() !== '')

  return (
    <div className="card" style={{ maxWidth: 720, margin: '0 auto' }}>
      {/* Card header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="step-indicator">1</span>
          <span className="card-title" style={{ margin: 0 }}>Product Input</span>
        </div>
        {/* Sample loader */}
        {/* Foolproof direct sample buttons */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setBrand('Fluke')
              setPartManuf('Fluke Corporation')
              setMpn('FLUKE-117')
              setDescription('Fluke 117 Electricians Multimeter')
              setE1Brand('Fluke')
              setUnilogBrand('')
              setDibBrand('')
              setError(null)
            }}
            style={{ fontSize: '0.75rem', padding: '4px 8px' }}
          >
            ⚡ Load Fluke
          </button>
          
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setBrand('3M')
              setPartManuf('3M Company')
              setMpn('3MABR-7100075690')
              setDescription('3M 775L Stikit Film P180 - Cubitron II 50 Disc/Box')
              setE1Brand('3M')
              setUnilogBrand('')
              setDibBrand('')
              setError(null)
            }}
            style={{ fontSize: '0.75rem', padding: '4px 8px' }}
          >
            💿 Load 3M
          </button>
          
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setBrand('Whirlpool')
              setPartManuf('APPDE')
              setMpn('WDTS7024RZ')
              setDescription('Dishwasher SS')
              setE1Brand('APPDE')
              setUnilogBrand('')
              setDibBrand('')
              setError(null)
            }}
            style={{ fontSize: '0.75rem', padding: '4px 8px' }}
          >
            💧 Load Whirlpool
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

          {/* Primary Input Grid: MPN & Part_Manuf */}
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="mpn-input">
                Part Number (Mfg_Part_Num)
                <span className="form-hint" style={{ marginLeft: 4, color: 'var(--blue-400)' }}>required</span>
              </label>
              <input
                id="mpn-input"
                className="form-input"
                type="text"
                placeholder="e.g. 3MABR-7100075690"
                value={mpn}
                onChange={e => setMpn(e.target.value)}
                required
                autoComplete="off"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="part-manuf-input">
                Part Manufacturer (Part_Manuf)
                <span className="form-hint" style={{ marginLeft: 4 }}>vendor or OEM</span>
              </label>
              <input
                id="part-manuf-input"
                className="form-input"
                type="text"
                placeholder="e.g. Jam Industrial Supply LLC (JAMIN)"
                value={partManuf}
                onChange={e => {
                  setPartManuf(e.target.value)
                  if (!brand) setBrand(e.target.value)
                }}
                autoComplete="off"
              />
            </div>
          </div>

          {/* Description */}
          <div className="form-group">
            <label className="form-label" htmlFor="description-input">
              Part Description (Part_Desc)
              <span className="form-hint" style={{ marginLeft: 4 }}>improves taxonomy, spec extraction & brand resolution</span>
            </label>
            <input
              id="description-input"
              className="form-input"
              type="text"
              placeholder="e.g. 3M 775L Stikit Film P180 - Cubitron II 50 Disc/Box"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>

          {/* Dataset Source Brands (E1, Unilog, DIB) */}
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 14px',
          }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                userSelect: 'none',
              }}
              onClick={() => setShowCatalogFields(!showCatalogFields)}
            >
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Catalog Brand Sources & Overrides (E1_Brand, Unilog_Brand, DIB_Brand)
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--blue-400)' }}>
                {showCatalogFields ? 'Hide Details ▲' : 'Show Details ▼'}
              </div>
            </div>

            {showCatalogFields && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 12 }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="e1-brand-input" style={{ fontSize: '0.78rem' }}>
                    E1_Brand
                  </label>
                  <input
                    id="e1-brand-input"
                    className="form-input"
                    style={{ fontSize: '0.82rem', padding: '6px 10px' }}
                    type="text"
                    placeholder="e.g. -- Unbranded --"
                    value={e1Brand}
                    onChange={e => setE1Brand(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="unilog-brand-input" style={{ fontSize: '0.78rem' }}>
                    Unilog_Brand
                  </label>
                  <input
                    id="unilog-brand-input"
                    className="form-input"
                    style={{ fontSize: '0.82rem', padding: '6px 10px' }}
                    type="text"
                    placeholder="e.g. -- No Unilog Brand --"
                    value={unilogBrand}
                    onChange={e => setUnilogBrand(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="dib-brand-input" style={{ fontSize: '0.78rem' }}>
                    DIB_Brand
                  </label>
                  <input
                    id="dib-brand-input"
                    className="form-input"
                    style={{ fontSize: '0.82rem', padding: '6px 10px' }}
                    type="text"
                    placeholder="e.g. -- No DIB Brand --"
                    value={dibBrand}
                    onChange={e => setDibBrand(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Custom Schema */}
          <div className="form-group">
            <label className="form-label" htmlFor="schema-input">
              Custom Attribute Schema
              <span className="form-hint" style={{ marginLeft: 4 }}>optional, comma-separated</span>
            </label>
            <textarea
              id="schema-input"
              className="form-input"
              rows={2}
              placeholder="e.g. grit, diameter, backing_material, abrasive_material, package_quantity"
              value={providedSchema}
              onChange={e => setSchema(e.target.value)}
              style={{ resize: 'vertical', minHeight: 52 }}
            />
            {strictSchema && !providedSchema.trim() && (
              <div style={{ color: 'var(--color-conf-low)', fontSize: '0.75rem', marginTop: 4 }}>
                ⚠️ You must provide a custom schema if "Strict Schema" is checked.
              </div>
            )}
          </div>

          {/* Options row */}
          <div style={{ display: 'flex', gap: 'var(--space-lg)', flexWrap: 'wrap', padding: '4px 0' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.86rem', color: 'var(--text-secondary)' }}
              data-tooltip="Only extract the fields listed in Custom Schema above">
              <input type="checkbox" checked={strictSchema} onChange={e => setStrict(e.target.checked)} />
              <span><strong style={{ color: 'var(--text-primary)' }}>Strict Schema</strong> — Exact fields only</span>
            </label>
          </div>

          {/* Error banner */}
          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}

          {/* Status message while running */}
          {loading && statusMsg && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              background: 'rgba(0,128,255,0.07)',
              border: '1px solid var(--border-blue)',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 14px',
              fontSize: '0.83rem',
              color: 'var(--blue-300)',
              fontWeight: 600,
            }}>
              <span className="spinner spinner-sm" style={{ borderTopColor: 'var(--blue-400)' }} />
              {statusMsg}
            </div>
          )}

          {/* Submit button */}
          <button
            id="enrich-submit-btn"
            type="submit"
            className={`btn btn-primary btn-lg ${loading ? 'btn-loading' : ''}`}
            disabled={!canSubmit}
            style={{ width: '100%', marginTop: 4 }}
          >
            {loading ? (
              <>
                <span className="spinner" />
                Processing Product…
              </>
            ) : (
              <>Enrich Product</>
            )}
          </button>

          {/* Helper hint */}
          {!loading && (
            <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Sequential stages: Identity Resolution → Taxonomy → Sourcing → Extraction → Validation → Copywriting
            </div>
          )}
        </div>
      </form>
    </div>
  )
}

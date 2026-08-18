import { useState, useEffect, useRef } from 'react'

const API = ''   // empty = same origin (proxied by Vite)

export default function ProductForm({ onResult, onStageChange }) {
  const [brand, setBrand] = useState('')
  const [mpn, setMpn] = useState('')
  const [description, setDescription] = useState('')
  const [providedSchema, setProvidedSchema] = useState('')
  const [strictSchema, setStrictSchema] = useState(false)
  const [forceReview, setForceReview] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [samples, setSamples] = useState([])
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  // Load sample products on mount
  useEffect(() => {
    fetch(`${API}/sample-products`)
      .then(r => r.json())
      .then(setSamples)
      .catch(() => {})
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const loadSample = (s) => {
    setBrand(s.brand)
    setMpn(s.mpn)
    setDescription(s.description)
    setDropdownOpen(false)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!brand.trim() || !mpn.trim()) return

    setLoading(true)
    setError(null)
    onResult(null)

    // Simulate stage progression (timed) while waiting for the API
    const stages = ['interpreting', 'searching', 'extracting', 'validating', 'copywriting']
    const delays  = [0, 3000, 7000, 12000, 16000]
    delays.forEach((delay, i) => {
      setTimeout(() => onStageChange(stages[i]), delay)
    })

    try {
      const res = await fetch(`${API}/enrich/v2`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Basic YWRtaW46dW5paGFjaw=='
        },
        body: JSON.stringify({ 
          brand, 
          mpn, 
          description,
          provided_schema: providedSchema ? providedSchema.split(',').map(s => s.trim()).filter(Boolean) : null,
          strict_schema: strictSchema,
          force_review: forceReview
        }),
      })
      const data = await res.json()
      onStageChange('done')

      if (data.status === 'failed') {
        setError(data.error || 'Pipeline failed')
        onResult(null)
      } else {
        // Pass the full v2 response envelope (product + job_id + hitl_required)
        onResult({
          ...data.product,
          job_id: data.job_id,
          hitl_required: data.hitl_required,
          pipeline_status: data.status,
        })
      }
    } catch (err) {
      setError(err.message || 'Network error')
      onStageChange('idle')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: 680, margin: '0 auto' }}>
      <div className="card-title">Product Input</div>

      {/* Sample loader */}
      <div className="dropdown-wrapper" ref={dropdownRef} style={{ marginBottom: 'var(--space-md)' }}>
        <button
          id="load-sample-btn"
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setDropdownOpen(o => !o)}
        >
          ⚡ Load Sample Product
          <span style={{ marginLeft: 4 }}>{dropdownOpen ? '▲' : '▼'}</span>
        </button>
        {dropdownOpen && samples.length > 0 && (
          <div className="dropdown-menu">
            {samples.map((s, i) => (
              <div
                key={i}
                id={`sample-${i}`}
                className="dropdown-item"
                onClick={() => loadSample(s)}
              >
                <div className="dropdown-item-brand">{s.brand}</div>
                <div className="dropdown-item-mpn">{s.mpn}</div>
                <div className="dropdown-item-desc">{s.description}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label" htmlFor="brand-input">Brand</label>
              <input
                id="brand-input"
                className="form-input"
                type="text"
                placeholder="e.g. Siemens"
                value={brand}
                onChange={e => setBrand(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="mpn-input">Part Number (MPN)</label>
              <input
                id="mpn-input"
                className="form-input"
                type="text"
                placeholder="e.g. 3RT2015-1BB41"
                value={mpn}
                onChange={e => setMpn(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="description-input">Short Description</label>
            <input
              id="description-input"
              className="form-input"
              type="text"
              placeholder="e.g. Contactor 3-pole 7A 24VDC coil"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>

          <div className="form-group" style={{ marginTop: 'var(--space-sm)' }}>
            <label className="form-label" htmlFor="schema-input">Custom Schema (Optional, comma-separated)</label>
            <textarea
              id="schema-input"
              className="form-input"
              rows={2}
              placeholder="e.g. voltage, current, material, weight"
              value={providedSchema}
              onChange={e => setProvidedSchema(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', marginTop: 'var(--space-xs)', marginBottom: 'var(--space-xs)' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
              <input 
                type="checkbox" 
                checked={strictSchema} 
                onChange={e => setStrictSchema(e.target.checked)} 
              />
              <strong>Strict Schema Mode</strong> (Only extract requested fields)
            </label>
            
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
              <input 
                type="checkbox" 
                checked={forceReview} 
                onChange={e => setForceReview(e.target.checked)} 
              />
              <strong>Force Human Review</strong> (Review every field)
            </label>
          </div>

          {error && (
            <div style={{
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 'var(--radius-sm)',
              padding: 'var(--space-sm) var(--space-md)',
              color: '#ef4444',
              fontSize: '0.875rem',
            }}>
              ⚠ {error}
            </div>
          )}

          <button
            id="enrich-submit-btn"
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading || !brand.trim() || !mpn.trim()}
            style={{ width: '100%', marginTop: 'var(--space-xs)' }}
          >
            {loading ? (
              <><span className="spinner" /> Enriching Product…</>
            ) : (
              <> Enrich Product</>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

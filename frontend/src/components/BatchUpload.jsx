import { useState, useRef } from 'react'

const API = ''

function confClass(confidence) {
  if (!confidence && confidence !== 0) return ''
  if (confidence >= 0.8) return 'conf-high'
  if (confidence >= 0.5) return 'conf-mid'
  return 'conf-low'
}

export default function BatchUpload() {
  const [file, setFile] = useState(null)
  const [providedSchema, setProvidedSchema] = useState('')
  const [strictSchema, setStrictSchema] = useState(false)
  const [forceReview, setForceReview] = useState(false)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  const handleFile = (f) => {
    if (f && f.name.endsWith('.csv')) {
      setFile(f)
      setError(null)
    } else {
      setError('Please upload a CSV file.')
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    handleFile(f)
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResults(null)

    const form = new FormData()
    form.append('file', file)
    if (providedSchema) {
      form.append('provided_schema', providedSchema)
    }
    form.append('strict_schema', strictSchema)
    form.append('force_review', forceReview)

    try {
      const res = await fetch(`${API}/enrich/batch`, { 
        method: 'POST', 
        body: form,
        headers: {
          'Authorization': 'Basic YWRtaW46dW5paGFjaw=='
        }
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    window.open(`${API}/enrich/batch/download`, '_blank')
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="card">
        <div className="card-title">Batch Enrichment</div>
        <p style={{ marginBottom: 'var(--space-lg)', fontSize: '0.9rem' }}>
          Upload a CSV with columns: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-1)' }}>brand, mpn, description</code>.
          Up to 100 products per batch.
        </p>

        {/* Dropzone */}
        <div
          id="batch-dropzone"
          className={`dropzone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <div className="dropzone-icon">📂</div>
          {file ? (
            <>
              <p style={{ color: 'var(--color-conf-high)', fontWeight: 600 }}>✓ {file.name}</p>
              <small>{(file.size / 1024).toFixed(1)} KB — click to change</small>
            </>
          ) : (
            <>
              <p>Drop your CSV file here, or click to browse</p>
              <small>Supports .csv files up to 100 products</small>
            </>
          )}
          <input
            ref={inputRef}
            id="batch-file-input"
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={(e) => handleFile(e.target.files[0])}
          />
        </div>

        <div className="form-group" style={{ marginTop: 'var(--space-md)' }}>
          <label className="form-label" htmlFor="batch-schema-input">Custom Schema for Batch (Optional, comma-separated)</label>
          <textarea
            id="batch-schema-input"
            className="form-input"
            rows={2}
            placeholder="e.g. voltage, current, material, weight"
            value={providedSchema}
            onChange={e => setProvidedSchema(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', marginTop: 'var(--space-xs)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
            <input 
              type="checkbox" 
              checked={strictSchema} 
              onChange={e => setStrictSchema(e.target.checked)} 
            />
            <strong>Strict Schema Mode</strong>
          </label>
          
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
            <input 
              type="checkbox" 
              checked={forceReview} 
              onChange={e => setForceReview(e.target.checked)} 
            />
            <strong>Force Human Review</strong> (Pauses pipeline for each item)
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
            marginTop: 'var(--space-md)',
          }}>
            ⚠ {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          <button
            id="batch-submit-btn"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!file || loading}
          >
            {loading ? <><span className="spinner" /> Processing…</> : '⚡ Process Batch'}
          </button>

          {results && (
            <button
              id="batch-download-btn"
              className="btn btn-secondary"
              onClick={handleDownload}
            >
              ↓ Download CSV
            </button>
          )}
        </div>
      </div>

      {/* Results summary */}
      {results && (
        <div style={{ marginTop: 'var(--space-lg)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', marginBottom: 'var(--space-md)' }}>
            {[
              { label: 'Total', value: results.total, color: 'var(--color-text-primary)' },
              { label: 'Succeeded', value: results.succeeded, color: 'var(--color-conf-high)' },
              { label: 'Failed', value: results.failed, color: results.failed > 0 ? 'var(--color-conf-low)' : 'var(--color-text-muted)' },
            ].map(stat => (
              <div key={stat.label} className="card" style={{ flex: 1, minWidth: 100, textAlign: 'center', padding: 'var(--space-md)' }}>
                <div style={{ fontSize: '2rem', fontWeight: 800, color: stat.color, fontFamily: 'var(--font-mono)' }}>{stat.value}</div>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginTop: 4 }}>{stat.label}</div>
              </div>
            ))}
          </div>

          <div className="batch-table-wrap">
            <table className="batch-table" id="batch-results-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Brand</th>
                  <th>MPN</th>
                  <th>Category</th>
                  <th>Confidence</th>
                  <th>Certifications</th>
                  <th>Flagged Fields</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {results.results.map((r, i) => (
                  <tr key={i} id={`batch-row-${i}`}>
                    <td style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>{i + 1}</td>
                    <td style={{ fontWeight: 600 }}>{r.brand || '—'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-1)' }}>{r.mpn || '—'}</td>
                    <td>{r.category || '—'}</td>
                    <td>
                      {r.overall_confidence != null ? (
                        <span className={`conf-badge ${confClass(r.overall_confidence)}`}>
                          {Math.round(r.overall_confidence * 100)}%
                        </span>
                      ) : '—'}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)' }}>
                      {Array.isArray(r.certifications) ? r.certifications.join(', ') || '—' : '—'}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--color-conf-mid)' }}>
                      {Array.isArray(r.flagged_for_review) && r.flagged_for_review.length > 0
                        ? `${r.flagged_for_review.length} fields`
                        : '—'}
                    </td>
                    <td>
                      {r.status === 'success'
                        ? <span className="status-success">✓ OK</span>
                        : <span className="status-failed" title={r.error}>✗ Failed</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

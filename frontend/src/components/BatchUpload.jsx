import { useState, useRef } from 'react'

const API = 'https://unilog-backend-api.loca.lt'

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
      setError('Please select a valid CSV file.')
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

    try {
      const res = await fetch(`${API}/enrich/batch`, { 
        method: 'POST', 
        body: form,
        headers: {
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
        <div className="card-title">Batch Catalog Ingestion</div>
        <p style={{ marginBottom: 'var(--space-lg)', fontSize: '0.9rem' }}>
          Upload a CSV file containing columns: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-1)' }}>brand, mpn, description</code>.
          Processes up to 100 catalog records concurrently.
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
          {file ? (
            <>
              <p style={{ color: 'var(--color-conf-high)', fontWeight: 600 }}>{file.name}</p>
              <small>{(file.size / 1024).toFixed(1)} KB — click to replace file</small>
            </>
          ) : (
            <>
              <p>Drag and drop a CSV catalog file here, or click to browse</p>
              <small>Standard CSV format (max 100 rows per batch)</small>
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
          <label className="form-label" htmlFor="batch-schema-input">Custom Attribute Schema (Optional, comma-separated)</label>
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
        </div>

        {error && (
          <div className="error-banner" style={{ marginTop: 'var(--space-md)' }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
          <button
            id="batch-submit-btn"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!file || loading}
          >
            {loading ? <><span className="spinner" /> Processing Batch…</> : 'Start Batch Processing'}
          </button>

          {results && (
            <button
              id="batch-download-btn"
              className="btn btn-secondary"
              onClick={handleDownload}
            >
              Download Export CSV
            </button>
          )}
        </div>
      </div>

      {/* Results summary */}
      {results && (
        <div style={{ marginTop: 'var(--space-lg)' }}>
          <div style={{ display: 'flex', gap: 'var(--space-md)', flexWrap: 'wrap', marginBottom: 'var(--space-md)' }}>
            {[
              { label: 'Total Records', value: results.total, color: 'var(--color-text-primary)' },
              { label: 'Processed', value: results.succeeded, color: 'var(--color-conf-high)' },
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
                        ? <span className="status-success">COMPLETE</span>
                        : <span className="status-failed" title={r.error}>FAILED</span>}
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

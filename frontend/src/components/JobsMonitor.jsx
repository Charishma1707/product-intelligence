import { useState, useEffect, useCallback } from 'react'

const API = 'http://localhost:8000'

const STATUS_COLORS = {
  completed:   'conf-high',
  validated:   'conf-high',
  hitl_paused: 'conf-mid',
  running:     'conf-mid',
  failed:      'conf-low',
}

const STATUS_LABELS = {
  completed:   'Complete',
  validated:   'Validated',
  hitl_paused: 'Needs Review',
  running:     'Running',
  failed:      'Failed',
}

export default function JobsMonitor({ onLoadJob }) {
  const [jobs, setJobs] = useState([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const url = filter ? `${API}/jobs?status=${filter}&limit=50` : `${API}/jobs?limit=50`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setJobs(data.jobs || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { fetchJobs() }, [fetchJobs])

  const handleLoadJob = async (job_id) => {
    try {
      const res = await fetch(`${API}/jobs/${job_id}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const record = await res.json()
      onLoadJob({
        ...record,
        hitl_required: record.status === 'hitl_paused',
        pipeline_status: record.status,
      })
    } catch (err) {
      alert(`Could not load job: ${err.message}`)
    }
  }

  const FILTERS = [
    { value: '',            label: 'All' },
    { value: 'completed',   label: 'Completed' },
    { value: 'hitl_paused', label: 'Needs Review' },
    { value: 'failed',      label: 'Failed' },
  ]

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
          <div className="card-title" style={{ marginBottom: 0 }}>Pipeline Jobs</div>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
            {FILTERS.map(f => (
              <button
                key={f.value}
                id={`jobs-filter-${f.value || 'all'}`}
                className={`btn btn-sm ${filter === f.value ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
            <button
              id="jobs-refresh-btn"
              className="btn btn-ghost btn-sm"
              onClick={fetchJobs}
              disabled={loading}
            >
              {loading ? <span className="spinner" /> : ''} Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="error-banner" style={{ marginBottom: 'var(--space-md)' }}>
            {error}
          </div>
        )}

        {jobs.length === 0 && !loading ? (
          <div style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: 'var(--space-xl)', fontSize: '0.9rem' }}>
            {filter ? `No ${filter} jobs found.` : 'No pipeline jobs yet. Submit a product to get started.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="batch-table" id="jobs-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Brand</th>
                  <th>MPN</th>
                  <th>Status</th>
                  <th>Confidence Score</th>
                  <th>Confidence Rationale & Human Escrow</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => {
                  const confPct = job.overall_confidence != null ? Math.round(job.overall_confidence * 100) : 0
                  const isHigh = confPct >= 90
                  const isMid = confPct >= 70
                  const isHITL = job.status === 'hitl_paused' || job.status === 'needs_review_identity' || job.status === 'needs_review_retrieval' || job.status === 'needs_review_attributes' || job.status === 'needs_review_delivery'

                  let rationale = ''
                  let rationaleClass = 'conf-high'

                  if (isHITL) {
                    rationale = '⏳ Awaiting Human Audit — Automated baseline pending Stage Verification'
                    rationaleClass = 'conf-mid'
                  } else if (isHigh) {
                    rationale = '🛡️ Human Manager Approved / 100% OEM Vector Spec Match'
                    rationaleClass = 'conf-high'
                  } else if (isMid) {
                    rationale = '⚡ Multi-Source AI Sourced — High Confidence (Human Escrow Optional)'
                    rationaleClass = 'conf-high'
                  } else {
                    rationale = '⚠️ Low Confidence — Requires Human Intervention Gate Approval'
                    rationaleClass = 'conf-low'
                  }

                  return (
                    <tr key={job.job_id} id={`job-row-${job.job_id}`}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                        {job.job_id.slice(0, 8)}…
                      </td>
                      <td style={{ fontWeight: 600 }}>{job.brand}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-1)' }}>{job.mpn}</td>
                      <td>
                        <span className={`conf-badge ${STATUS_COLORS[job.status] || 'conf-mid'}`}>
                          {STATUS_LABELS[job.status] || job.status}
                        </span>
                      </td>
                      <td>
                        <span className={`conf-badge ${isHigh ? 'conf-high' : isMid ? 'conf-mid' : 'conf-low'}`}>
                          {confPct}%
                        </span>
                      </td>
                      <td>
                        <span className={`conf-badge ${rationaleClass}`} style={{ fontSize: '0.72rem', padding: '3px 8px' }}>
                          {rationale}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                        {new Date(job.updated_at).toLocaleString()}
                      </td>
                      <td>
                        <button
                          id={`job-load-${job.job_id}`}
                          className={`btn btn-sm ${isHITL ? 'btn-primary' : 'btn-ghost'}`}
                          onClick={() => handleLoadJob(job.job_id)}
                        >
                          {isHITL ? 'Intervene / Review' : 'View Details'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

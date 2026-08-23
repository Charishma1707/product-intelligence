import { useState, useEffect, useCallback } from 'react'

const API = ''

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
      const res = await fetch(url, { headers: { 'Authorization': 'Basic YWRtaW46dW5paGFjaw==' } })
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
      const res = await fetch(`${API}/jobs/${job_id}`, { headers: { 'Authorization': 'Basic YWRtaW46dW5paGFjaw==' } })
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
                  <th>Confidence</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.job_id} id={`job-row-${job.job_id}`}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                      {job.job_id.slice(0, 8)}…
                    </td>
                    <td style={{ fontWeight: 600 }}>{job.brand}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-accent-1)' }}>{job.mpn}</td>
                    <td>
                      <span className={`conf-badge ${STATUS_COLORS[job.status] || ''}`}>
                        {STATUS_LABELS[job.status] || job.status}
                      </span>
                    </td>
                    <td>
                      {job.overall_confidence != null
                        ? <span className={`conf-badge ${job.overall_confidence >= 0.8 ? 'conf-high' : job.overall_confidence >= 0.5 ? 'conf-mid' : 'conf-low'}`}>
                            {Math.round(job.overall_confidence * 100)}%
                          </span>
                        : '—'}
                    </td>
                    <td style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                      {new Date(job.updated_at).toLocaleString()}
                    </td>
                    <td>
                      <button
                        id={`job-load-${job.job_id}`}
                        className={`btn btn-sm ${job.status === 'hitl_paused' ? 'btn-primary' : 'btn-ghost'}`}
                        onClick={() => handleLoadJob(job.job_id)}
                      >
                        {job.status === 'hitl_paused' ? 'Review' : 'View'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

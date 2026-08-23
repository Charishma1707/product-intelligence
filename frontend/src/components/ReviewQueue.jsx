import { useState, useEffect, useCallback } from 'react'


/**
 * ReviewQueue — loads all needs_review jobs and displays them as cards.
 * Clicking "Open in Review" calls onOpenJob(job) which switches to the HITL panel.
 */
export default function ReviewQueue({ onOpenJob }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch('/jobs?limit=500')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const all = data.jobs || (Array.isArray(data) ? data : [])
      const review = all.filter(j => j.status && j.status.startsWith('needs_review'))
      setJobs(review)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    const id = setInterval(fetchJobs, 8000)
    return () => clearInterval(id)
  }, [fetchJobs])

  const handleOpen = async (job) => {
    try {
      const res = await fetch(`/jobs/${job.job_id}`)
      const full = res.ok ? await res.json() : job
      onOpenJob({ ...(full.product || full), job_id: job.job_id, pipeline_status: job.status, hitl_required: true })
    } catch {
      onOpenJob({ ...job, pipeline_status: job.status, hitl_required: true })
    }
  }

  const confColor = (c) => {
    if (!c && c !== 0) return '#94a3b8'
    if (c >= 0.8) return '#34d399'
    if (c >= 0.5) return '#fbbf24'
    return '#f87171'
  }

  const stageLabel = (status) => {
    const map = {
      needs_review_identity:   'Stage 1 — Brand & Identity',
      needs_review_retrieval:  'Stage 2 — Sourcing URLs',
      needs_review_extraction: 'Stage 3 — Attributes',
      needs_review:            'Stage 3 — Attributes',
      needs_review_final:      'Stage 4 — Copywriting',
      needs_review_delivery:   'Stage 5 — Delivery Fields',
    }
    return map[status] || status
  }

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
      <span className="spinner" style={{ marginRight: 8 }} />
      Loading review queue…
    </div>
  )

  if (error) return (
    <div className="error-banner" style={{ maxWidth: 600, margin: '0 auto' }}>
      Failed to load review queue: {error}
    </div>
  )

  if (jobs.length === 0) return (
    <div style={{
      textAlign: 'center', padding: '48px 24px',
      background: 'rgba(255,255,255,0.02)',
      border: '1px dashed var(--border-subtle)',
      borderRadius: 'var(--radius-lg)',
      color: '#64748b'
    }}>
      <div style={{ fontSize: '2.5rem', marginBottom: 12 }}>✅</div>
      <div style={{ fontWeight: 700, fontSize: '1rem', color: '#94a3b8' }}>No products pending review</div>
      <div style={{ fontSize: '0.8rem', marginTop: 6 }}>All catalog records have been processed or approved.</div>
    </div>
  )

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
          {jobs.length} product{jobs.length !== 1 ? 's' : ''} pending human verification
        </div>
        <button
          className="btn btn-sm btn-primary"
          onClick={fetchJobs}
          style={{ fontSize: '0.78rem' }}
        >
          Refresh
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {jobs.map(job => (
          <div
            key={job.job_id}
            style={{
              background: '#0a0f1c',
              border: '1px solid #1e3a5f',
              borderLeft: '4px solid #f59e0b',
              borderRadius: 10,
              padding: '16px 20px',
              display: 'flex',
              alignItems: 'center',
              gap: 20,
              flexWrap: 'wrap',
            }}
          >
            {/* Product identity */}
            <div style={{ flex: '1 1 220px' }}>
              <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#f1f5f9' }}>
                {job.brand || '—'} &nbsp;·&nbsp; <span style={{ color: '#60a5fa' }}>{job.mpn || '—'}</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 3 }}>
                Job: {job.job_id?.slice(0, 8)}…
              </div>
            </div>

            {/* Stage */}
            <div style={{ flex: '0 0 auto' }}>
              <span style={{
                background: 'rgba(245,158,11,0.12)',
                border: '1px solid rgba(245,158,11,0.35)',
                color: '#fbbf24',
                borderRadius: 6,
                padding: '3px 10px',
                fontSize: '0.75rem',
                fontWeight: 700,
              }}>
                {stageLabel(job.status)}
              </span>
            </div>

            {/* Confidence */}
            <div style={{ flex: '0 0 auto', textAlign: 'center' }}>
              <div style={{
                fontSize: '1.15rem', fontWeight: 900,
                color: confColor(job.overall_confidence)
              }}>
                {job.overall_confidence != null
                  ? `${Math.round(job.overall_confidence * 100)}%`
                  : '—'
                }
              </div>
              <div style={{ fontSize: '0.65rem', color: '#64748b' }}>Confidence</div>
            </div>

            {/* Timestamp */}
            <div style={{ flex: '0 0 auto', fontSize: '0.72rem', color: '#64748b' }}>
              {job.updated_at ? new Date(job.updated_at).toLocaleString() : ''}
            </div>

            {/* Action */}
            <button
              className="btn btn-primary btn-sm"
              onClick={() => handleOpen(job)}
              style={{ flex: '0 0 auto', fontWeight: 700 }}
            >
              Open in Review →
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

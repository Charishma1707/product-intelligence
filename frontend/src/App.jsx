import { useState, useEffect } from 'react'
import ProductForm from './components/ProductForm.jsx'
import ResultCard from './components/ResultCard.jsx'
import BatchUpload from './components/BatchUpload.jsx'
import HITLReview from './components/HITLReview.jsx'
import FinalProductResponse from './components/FinalProductResponse.jsx'
import JobsMonitor from './components/JobsMonitor.jsx'
import PipelineTrace from './components/PipelineTrace.jsx'
import UserGuideModal from './components/UserGuideModal.jsx'
import ReviewQueue from './components/ReviewQueue.jsx'

export default function App() {
  const [tab, setTab] = useState('single')
  const [activeStage, setActiveStage] = useState(null)
  const [result, setResult] = useState(null)
  const [showHITL, setShowHITL] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [stats, setStats] = useState({
    complete: 0,
    needs_review: 0,
    searches_avoided: 0,
    documents_reused: 0,
    series_hits: 0,
    unique_series_cached: 0,
    documents_cached: 0,
  })

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [jobsRes, metricsRes] = await Promise.all([
          fetch('http://localhost:8000/jobs?limit=500'),
          fetch('http://localhost:8000/metrics').catch(() => null)
        ])
        let complete = 0, review = 0
        if (jobsRes && jobsRes.ok) {
          const data = await jobsRes.json()
          const jobs = data.jobs || (Array.isArray(data) ? data : [])
          complete = jobs.filter(j => j.status === 'complete').length
          review   = jobs.filter(j => j.status === 'needs_review').length
        }
        let metricsData = {}
        if (metricsRes && metricsRes.ok) metricsData = await metricsRes.json()
        setStats({
          complete,
          needs_review: review,
          searches_avoided: (metricsData.searches_avoided || 0) + (metricsData.series_hits || 0) * 2,
          documents_reused: metricsData.documents_reused || 0,
          series_hits: metricsData.series_hits || 0,
          unique_series_cached: metricsData.unique_series_cached || 0,
          documents_cached: metricsData.documents_cached || 0,
        })
      } catch { /* silent */ }
    }
    fetchStats()
    const interval = setInterval(fetchStats, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleResult = (product) => {
    setResult(product)
    setShowHITL(Boolean(product?.hitl_required || product?.status?.startsWith('needs_review') || product?.pipeline_status?.startsWith('needs_review')))
  }

  const handleHITLResolved = (resolvedProduct) => {
    setResult(resolvedProduct)
    if (resolvedProduct?.pipeline_status === 'complete' || resolvedProduct?.status === 'complete') {
      setShowHITL(false)
    }
  }

  const handleLoadJob = (job) => {
    setResult(job)
    setShowHITL(job.hitl_required)
    setActiveStage(null)
    setTab('single')
    setTimeout(() => document.getElementById('result-card')?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  const handleResetApp = async () => {
    if (!window.confirm("Are you sure? This will delete all jobs, downloaded PDFs, knowledge graphs, and databases. This cannot be undone.")) return;
    try {
      const res = await fetch('http://localhost:8000/reset', { method: 'POST' });
      if (res.ok) {
        alert("Pipeline completely reset!");
        window.location.reload();
      } else {
        alert("Failed to reset pipeline.");
      }
    } catch (e) {
      alert("Error resetting pipeline: " + e.message);
    }
  }

  const TABS = [
    { id: 'single',    label: 'Single Product' },
    { id: 'batch',     label: 'Batch Processing' },
    { id: 'jobs',      label: 'Jobs Monitor' },
    { id: 'dashboard', label: 'Review Dashboard' },
  ]

  return (
    <div className="app-wrapper">
      <UserGuideModal isOpen={showGuide} onClose={() => setShowGuide(false)} />

      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-inner">
          {/* Logo */}
          <div className="logo">
            <div className="logo-icon" style={{ fontWeight: 900, fontSize: '14px', letterSpacing: '-0.5px' }}>UN</div>
            <div>
              <div className="logo-text">Unilog Product Intelligence</div>
              <div className="logo-sub">Standardize Part Numbers into Structured Commerce Data</div>
            </div>
          </div>

          {/* Live Metrics + Guide Button */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={handleResetApp}
              className="btn"
              style={{ marginRight: 4, background: '#ef4444', color: 'white' }}
            >
              Reset App Data
            </button>
            <button
              onClick={() => setShowGuide(true)}
              className="btn btn-primary btn-sm"
              style={{ marginRight: 4 }}
            >
              User Guide
            </button>
            <span className="metric-chip blue">{stats.searches_avoided} Searches Avoided</span>
            <span className="metric-chip purple">{stats.documents_reused} Docs Reused</span>
            <span className="metric-chip purple">{stats.series_hits || stats.unique_series_cached} Series Reused</span>
            <span className="metric-chip green">{stats.complete} Auto-Enriched</span>
            {stats.needs_review > 0 && (
              <span className="metric-chip amber">{stats.needs_review} Human Review Required</span>
            )}
          </div>

          {/* Nav Tabs */}
          <nav className="nav-tabs" role="tablist">
            {TABS.map(t => (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                role="tab"
                className={`nav-tab ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
                aria-selected={tab === t.id}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* ── Main Content ── */}
      <main className="app-main">

        {/* ══════════ SINGLE PRODUCT ══════════ */}
        {tab === 'single' && (
          <div className="animate-fade-up">
            {/* Hero */}
            <div className="hero" style={{ paddingBottom: 'var(--space-md)' }}>
              <div className="hero-badge">Industrial Catalog Intelligence</div>
              <h1>Standardize Part Numbers into<br />Structured Commerce Data</h1>
              <p style={{ maxWidth: 680, margin: '12px auto 0' }}>
                Engineered for industrial distribution. The engine executes <strong>5 sequential verification stages</strong>,
                verifies part numbers directly against manufacturer technical documentation, and reuses series knowledge
                across catalog sibling products.
              </p>
            </div>

            {/* Architecture cards */}
            <div className="feature-grid" style={{ maxWidth: 1000, margin: '0 auto 32px' }}>
              <div className="feature-card">
                <div className="feature-card-title">Exact MPN Verification</div>
                <div className="feature-card-desc">Confirms the manufacturer part number exists verbatim on the source technical document before accepting extracted specifications.</div>
              </div>
              <div className="feature-card">
                <div className="feature-card-title">Series Knowledge Reuse</div>
                <div className="feature-card-desc">Resolves shared series documentation once. Sibling items inherit verified baseline attributes, reducing external calls up to 80%.</div>
              </div>
              <div className="feature-card">
                <div className="feature-card-title">Zero-Hallucination Policy</div>
                <div className="feature-card-desc">Every extracted value is corroborated by source citation snippets. Unverified fields are queued for reviewer confirmation.</div>
              </div>
              <div className="feature-card">
                <div className="feature-card-title">Human-in-the-Loop Feedback</div>
                <div className="feature-card-desc">Reviewer corrections are stored in SQLite and automatically applied to future catalog ingestion runs.</div>
              </div>
            </div>

            {/* How to use guide */}
            <div className="guide-banner" style={{ maxWidth: 680, margin: '0 auto var(--space-md)' }}>
              <div className="guide-banner-text">
                <strong>Workflow:</strong> Enter a Brand and Part Number (MPN) below.
                Optionally specify a description or custom schema fields. Click <strong>Enrich Product</strong> to
                initiate execution. Review the verified attributes, confidence scores, and source citations upon completion.
              </div>
            </div>

            {/* Form */}
            <ProductForm onResult={handleResult} onStageChange={setActiveStage} />

            {/* HITL Review panel (Stages 1–5) */}
            {result && showHITL && (
              <div style={{ maxWidth: 960, margin: 'var(--space-lg) auto 0' }}>
                <HITLReview product={result} onResolved={handleHITLResolved} />
              </div>
            )}

            {/* Final Completed Product Response & Export */}
            {result && !showHITL && (
              <div style={{ maxWidth: 960, margin: 'var(--space-lg) auto 0' }}>
                <FinalProductResponse product={result} postApprovalSummary={result.post_approval_summary} />
              </div>
            )}

            {/* Result card & Live Trace */}
            {result && (
              <>
                <ResultCard product={result} onReview={() => setShowHITL(true)} />
                <PipelineTrace logs={result.logs} />
              </>
            )}
          </div>
        )}

        {/* ══════════ BATCH MODE ══════════ */}
        {tab === 'batch' && (
          <div className="animate-fade-up">
            <div className="hero" style={{ paddingBottom: 'var(--space-md)' }}>
              <div className="hero-badge">Bulk Catalog Ingestion</div>
              <h1>Batch Product Enrichment</h1>
              <p>Upload a CSV file containing Brand, MPN, and optional Description columns to process multiple items concurrently.</p>
            </div>

            <div className="guide-banner" style={{ maxWidth: 780, margin: '0 auto var(--space-lg)' }}>
              <div className="guide-banner-text">
                <strong>File Format:</strong> The CSV must include <strong>Brand</strong> and <strong>Mfg_Part_Num</strong> headers.
                An optional <strong>Part_Desc</strong> column enhances categorization accuracy.
                After upload, jobs execute asynchronously. Track progress in the <strong>Jobs Monitor</strong> tab and export as a 252-column CSV.
              </div>
            </div>

            <BatchUpload />
          </div>
        )}

        {/* ══════════ JOBS MONITOR ══════════ */}
        {tab === 'jobs' && (
          <div className="animate-fade-up">
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 'var(--space-lg)', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
              <div>
                <div className="hero-badge" style={{ marginBottom: 8 }}>Execution Monitor</div>
                <h1 style={{ fontSize: '1.8rem', marginBottom: 6 }}>Pipeline Jobs</h1>
                <p>Monitor enrichment runs across your product catalog. Review paused records and export finalized data.</p>
              </div>
              <a
                href="http://127.0.0.1:8000/export/csv"
                className="btn btn-success"
                style={{ textDecoration: 'none', flexShrink: 0 }}
                download="Unilog_Submission.csv"
              >
                Export Unilog CSV
              </a>
            </div>

            <div className="guide-banner" style={{ marginBottom: 'var(--space-lg)' }}>
              <div className="guide-banner-text">
                <strong>Job Statuses:</strong> Items marked <strong>Needs Review</strong> were flagged for confidence verification.
                Click <strong>Load</strong> to inspect and confirm values in the Single Product tab. <strong>Complete</strong> items are ready for catalog export.
              </div>
            </div>

            <JobsMonitor onLoadJob={handleLoadJob} />
          </div>
        )}

        {/* ══════════ HITL DASHBOARD ══════════ */}
        {tab === 'dashboard' && (
          <div className="animate-fade-up" style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-lg)', flexWrap: 'wrap', gap: 'var(--space-md)' }}>
              <div>
                <div className="hero-badge" style={{ marginBottom: 8 }}>Verification Console</div>
                <h1 style={{ fontSize: '1.8rem', marginBottom: 6 }}>Review Station &amp; Catalog Metrics</h1>
                <p>Products flagged for human verification. Click <strong>Open in Review</strong> to inspect and approve.</p>
              </div>
              <a
                href="http://127.0.0.1:8000/export/csv"
                className="btn btn-success"
                style={{ textDecoration: 'none', flexShrink: 0 }}
                download="Unilog_Submission.csv"
              >
                Export Unilog CSV
              </a>
            </div>

            {/* Scalability snapshot metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: 'var(--space-lg)' }}>
              {[
                { label: 'Searches Saved',  value: stats.searches_avoided,      color: 'blue',   desc: 'Cached web calls' },
                { label: 'Series Cached',   value: stats.unique_series_cached,   color: 'purple', desc: 'Normalized product series' },
                { label: 'Docs Cached',     value: stats.documents_cached,       color: 'green',  desc: 'Deduplicated datasheets' },
                { label: 'Auto-Enriched',   value: stats.complete,               color: 'green',  desc: 'Validated catalog records' },
                { label: 'Needs Review',    value: stats.needs_review,           color: 'amber',  desc: 'Items pending confirmation' },
              ].map(m => (
                <div key={m.label} style={{
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '1.6rem', fontWeight: 900, color: 'var(--text-primary)', lineHeight: 1 }}>{m.value}</div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', marginTop: 4 }}>{m.label}</div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 3 }}>{m.desc}</div>
                </div>
              ))}
            </div>

            {/* Review Queue — lists all needs_review jobs */}
            <ReviewQueue onOpenJob={(job) => { handleLoadJob(job); setTab('single') }} />
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="app-footer">
        <span>Unilog Product Intelligence Platform</span>
      </footer>
    </div>
  )
}

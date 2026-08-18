import { useState, useEffect } from 'react'
import ProductForm from './components/ProductForm.jsx'
import PipelineStages from './components/PipelineStages.jsx'
import ResultCard from './components/ResultCard.jsx'
import BatchUpload from './components/BatchUpload.jsx'
import HITLReview from './components/HITLReview.jsx'
import JobsMonitor from './components/JobsMonitor.jsx'
import PipelineTrace from './components/PipelineTrace.jsx'

export default function App() {
  const [tab, setTab] = useState('single')
  const [activeStage, setActiveStage] = useState(null)
  const [result, setResult] = useState(null)
  const [showHITL, setShowHITL] = useState(false)
  const [stats, setStats] = useState({ complete: 0, needs_review: 0, total_specs: 0 })

  // Live stats counter — polls every 15 seconds
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('/jobs?limit=500', { headers: { 'Authorization': 'Basic YWRtaW46dW5paGFjaw==' } })
        if (!res.ok) return
        const jobs = await res.json()
        const complete = jobs.filter(j => j.status === 'complete').length
        const review = jobs.filter(j => j.status === 'needs_review').length
        const total_specs = jobs.reduce((acc, j) => acc + (j.flagged_count ?? 0), 0)
        setStats({ complete, needs_review: review, total_specs })
      } catch (e) { /* silently fail */ }
    }
    fetchStats()
    const interval = setInterval(fetchStats, 15000)
    return () => clearInterval(interval)
  }, [])

  const handleResult = (product) => {
    setResult(product)
    // Auto-show HITL panel if pipeline is paused
    if (product?.hitl_required) {
      setShowHITL(true)
    } else {
      setShowHITL(false)
    }
  }

  const handleStageChange = (stage) => {
    setActiveStage(stage)
  }

  const handleHITLResolved = (resolvedProduct) => {
    setResult(resolvedProduct)
    setShowHITL(false)
  }

  // When a job is loaded from the Jobs Monitor, switch to Single tab and show it
  const handleLoadJob = (job) => {
    setResult(job)
    setShowHITL(job.hitl_required)
    setActiveStage(null)
    setTab('single')
    // Scroll to result after brief delay
    setTimeout(() => {
      document.getElementById('result-card')?.scrollIntoView({ behavior: 'smooth' })
    }, 100)
  }

  const TABS = [
    { id: 'single', label: 'Single Product', icon: '⚡' },
    { id: 'batch',  label: 'Batch Mode',     icon: '📦' },
    { id: 'jobs',   label: 'Jobs Monitor',   icon: '📋' },
  ]

  return (
    <div className="app-wrapper">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon">⚡</div>
            <div>
              <div className="logo-text">Product Intelligence</div>
              <div className="logo-sub">AI-Powered Enrichment Pipeline</div>
            </div>
          </div>

          {/* Live Stats Counter */}
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', fontSize: '12px' }}>
            <div style={{ background: '#10b98122', color: '#10b981', padding: '4px 10px', borderRadius: '20px', border: '1px solid #10b98144' }}>
              ✅ {stats.complete} Enriched
            </div>
            {stats.needs_review > 0 && (
              <div style={{ background: '#f59e0b22', color: '#f59e0b', padding: '4px 10px', borderRadius: '20px', border: '1px solid #f59e0b44' }}>
                🟡 {stats.needs_review} Awaiting Review
              </div>
            )}
          </div>

          <nav className="nav-tabs" role="tablist">
            {TABS.map(t => (
              <button
                key={t.id}
                id={`tab-${t.id}`}
                role="tab"
                className={`nav-tab ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="app-main">
        {tab === 'single' && (
          <>
            {/* Hero */}
            <div className="hero">
              <div className="hero-badge">✨ 5-Stage LangGraph Pipeline</div>
              <h1>Turn Part Numbers into<br />Rich Product Records</h1>
              <p>
                Enter a brand, MPN and short description — our pipeline searches,
                extracts, validates and confidence-scores every specification field,
                then generates commerce-ready copy automatically.
              </p>
            </div>

            {/* Form */}
            <ProductForm
              onResult={handleResult}
              onStageChange={handleStageChange}
            />

            {/* Pipeline stages */}
            {activeStage && activeStage !== 'idle' && (
              <div style={{ maxWidth: 720, margin: 'var(--space-lg) auto 0' }}>
                <PipelineStages activeStage={activeStage} />
              </div>
            )}

            {/* HITL Review panel (shows when pipeline paused) */}
            {result && showHITL && result.hitl_required && (
              <div style={{ maxWidth: 900, margin: 'var(--space-lg) auto 0' }}>
                <HITLReview product={result} onResolved={handleHITLResolved} />
              </div>
            )}

            {/* Result */}
            {result && (
              <>
                <ResultCard
                  product={result}
                  onReview={() => setShowHITL(true)}
                />
                <PipelineTrace logs={result.logs} />
              </>
            )}
          </>
        )}

        {tab === 'batch' && (
          <>
            <div className="hero" style={{ paddingBottom: 'var(--space-md)' }}>
              <div className="hero-badge">📦 Bulk Processing</div>
              <h1>Batch Product Enrichment</h1>
              <p>Upload a CSV and enrich up to 100 products concurrently with full confidence scoring.</p>
            </div>
            <BatchUpload />
          </>
        )}

        {tab === 'jobs' && (
          <>
            <div className="hero" style={{ paddingBottom: 'var(--space-md)', position: 'relative' }}>
              <div className="hero-badge">📋 Pipeline Monitor</div>
              <h1>Pipeline Jobs</h1>
              <p>Monitor all pipeline runs. Review HITL-paused jobs and track confidence scores across your product catalog.</p>
              
              <div style={{ position: 'absolute', top: 'var(--space-lg)', right: 'var(--space-lg)' }}>
                <a 
                  href="http://127.0.0.1:8000/export/csv" 
                  className="btn btn-primary" 
                  style={{ textDecoration: 'none', display: 'inline-block', padding: '10px 20px', background: '#10b981' }}
                  download="Unilog_Submission.csv"
                >
                  📥 Export to Unilog CSV
                </a>
              </div>
            </div>
            <JobsMonitor onLoadJob={handleLoadJob} />
          </>
        )}
      </main>

      {/* ── Footer ── */}
      <footer style={{
        textAlign: 'center',
        padding: 'var(--space-lg)',
        borderTop: '1px solid var(--color-border)',
        color: 'var(--color-text-muted)',
        fontSize: '0.78rem',
      }}>
        Product Intelligence Pipeline — Powered by Groq (Llama 3.3) + LangGraph + DuckDuckGo + Trafilatura
      </footer>
    </div>
  )
}

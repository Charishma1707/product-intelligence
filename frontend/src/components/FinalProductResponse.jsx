import { useState } from 'react'

import { API } from '../apiConfig'

export default function FinalProductResponse({ product, postApprovalSummary }) {
  const [savingDb, setSavingDb] = useState(false)
  const [dbSaved, setDbSaved] = useState(false)
  const [dbMessage, setDbMessage] = useState(null)

  const handleSaveToDb = async () => {
    setSavingDb(true)
    setDbMessage(null)
    try {
      const res = await fetch(`${API}/export/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          },
        body: JSON.stringify({ job_id: product?.job_id })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Save failed')
      setDbSaved(true)
      setDbMessage(`✓ Successfully persisted ${data.attributes_saved || 'all'} product attributes to Database.`)
    } catch (err) {
      setDbMessage(`✗ Failed to save to database: ${err.message}`)
    } finally {
      setSavingDb(false)
    }
  }

  const handleDownloadCsv = () => {
    window.open(`${API}/export/csv`, '_blank')
  }

  const summary = postApprovalSummary || product?.post_approval_summary

  return (
    <div style={{
      marginTop: 24,
      background: 'linear-gradient(180deg, rgba(16, 185, 129, 0.06) 0%, rgba(15, 23, 42, 0.9) 100%)',
      border: '1px solid rgba(16, 185, 129, 0.3)',
      borderRadius: 12,
      padding: 24,
      boxShadow: '0 0 30px rgba(16, 185, 129, 0.08)'
    }}>
      {/* Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 999, background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', fontSize: '0.75rem', fontWeight: 700, marginBottom: 6 }}>
            ✓ ENRICHMENT &amp; HUMAN VERIFICATION COMPLETE
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f8fafc', margin: 0 }}>
            {product?.brand} {product?.mpn}
          </h2>
          <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginTop: 4 }}>
            {product?.category || 'Industrial Product'} {product?.subcategory ? `› ${product.subcategory}` : ''}
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={handleDownloadCsv}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.82rem', padding: '9px 18px' }}
          >
            ⬇ Download Unilog CSV
          </button>
          <button
            onClick={handleSaveToDb}
            disabled={savingDb || dbSaved}
            className="btn btn-secondary"
            style={{
              display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.82rem', padding: '9px 18px',
              background: dbSaved ? 'rgba(16, 185, 129, 0.2)' : undefined,
              borderColor: dbSaved ? '#34d399' : undefined,
              color: dbSaved ? '#34d399' : undefined,
            }}
          >
            {savingDb ? '💾 Saving to DB…' : dbSaved ? '✓ Saved in DB' : '💾 Save to Database'}
          </button>
        </div>
      </div>

      {/* DB Save feedback */}
      {dbMessage && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, fontSize: '0.82rem', marginBottom: 16,
          background: dbSaved ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
          border: `1px solid ${dbSaved ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
          color: dbSaved ? '#34d399' : '#f87171',
        }}>
          {dbMessage}
        </div>
      )}

      {/* Post-Approval Learning Feedback Box */}
      {summary && (
        <div style={{
          padding: '14px 18px',
          background: 'rgba(139, 92, 246, 0.08)',
          border: '1px solid rgba(139, 92, 246, 0.25)',
          borderRadius: 8,
          marginBottom: 20,
        }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#c084fc', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🧠 Autonomous Knowledge Graph Learning</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#e2e8f0', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            <span>⚡ <strong>{summary.aliases_saved ?? 0}</strong> description abbreviation aliases saved</span>
            <span>📈 <strong>{summary.series_boosted ?? 0}</strong> series-shared attributes boosted to 100% confidence</span>
            <span>💾 <strong>{summary.unique_attrs_saved ?? 0}</strong> unique product attributes stored in Knowledge Graph</span>
          </div>
        </div>
      )}

      {/* Final Copywriting Showcase */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 20 }}>
        {product?.invoice_desc && (
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: 12, borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.06)' }}>
            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 4 }}>
              Invoice Description (≤40 chars)
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#38bdf8', fontFamily: 'monospace' }}>
              {product.invoice_desc}
            </div>
          </div>
        )}

        {product?.short_desc && (
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: 12, borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.06)' }}>
            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 4 }}>
              Short Description
            </div>
            <div style={{ fontSize: '0.8rem', color: '#e2e8f0' }}>
              {product.short_desc}
            </div>
          </div>
        )}

        {product?.unspsc && (
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: 12, borderRadius: 6, border: '1px solid rgba(255, 255, 255, 0.06)' }}>
            <div style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: 4 }}>
              UNSPSC Code
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fbbf24', fontFamily: 'monospace' }}>
              {product.unspsc}
            </div>
          </div>
        )}
      </div>

      {/* Core Attributes Summary */}
      <div style={{ fontSize: '0.78rem', color: '#94a3b8', textAlign: 'center' }}>
        Record is verified, persisted, and ready for deployment to the Unilog 252-column master catalog.
      </div>
    </div>
  )
}

import { useState } from 'react'

/**
 * UserGuideModal.jsx — System Architecture & Workflow Reference Guide.
 */
export default function UserGuideModal({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('quickstart')

  if (!isOpen) return null

  const GUIDE_TABS = [
    { id: 'quickstart', label: 'Quick Start' },
    { id: 'single', label: 'Single Product' },
    { id: 'batch', label: 'Batch Processing' },
    { id: 'review', label: 'Review & Verification' },
    { id: 'pipeline', label: 'Pipeline Architecture' },
  ]

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.85)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div style={{
        background: '#0a0e17',
        border: '1px solid #1e293b',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '900px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
        overflow: 'hidden',
        color: '#f8fafc'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#0f172a'
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '18px', color: '#ffffff' }}>
              Product Intelligence Platform Guide
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#94a3b8' }}>
              Operational workflows, architectural stages, and validation rules.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: '#1e293b',
              border: '1px solid #334155',
              color: '#f8fafc',
              fontSize: '16px',
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            ✕
          </button>
        </div>

        {/* Navigation Tabs inside Guide */}
        <div style={{
          display: 'flex',
          gap: '8px',
          padding: '12px 24px',
          background: '#0a0e17',
          borderBottom: '1px solid #1e293b',
          overflowX: 'auto'
        }}>
          {GUIDE_TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                border: 'none',
                background: activeTab === tab.id ? '#0080ff' : '#1e293b',
                color: activeTab === tab.id ? '#ffffff' : '#94a3b8',
                fontSize: '13px',
                fontWeight: activeTab === tab.id ? '600' : '400',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1, fontSize: '14px', lineHeight: '1.6' }}>
          
          {/* TAB 1: QUICK START */}
          {activeTab === 'quickstart' && (
            <div>
              <h3 style={{ color: '#60a5fa', marginTop: 0 }}>System Workflow in 3 Steps</h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                <div style={{ background: '#0f172a', padding: '16px', borderRadius: '10px', borderLeft: '4px solid #0096ff' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '15px', color: '#ffffff', marginBottom: '4px' }}>
                    1. Input Product Record
                  </div>
                  <div style={{ color: '#cbd5e1' }}>
                    Navigate to <strong>Single Product</strong>. Enter <strong>Brand</strong> (e.g. <code>Siemens</code>), <strong>Part Number (MPN)</strong> (e.g. <code>3RT2015-1BB41</code>), and optional description, then click <strong>Enrich Product</strong>.
                  </div>
                </div>

                <div style={{ background: '#0f172a', padding: '16px', borderRadius: '10px', borderLeft: '4px solid #8b5cf6' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '15px', color: '#ffffff', marginBottom: '4px' }}>
                    2. Automated Multi-Stage Execution
                  </div>
                  <div style={{ color: '#cbd5e1' }}>
                    The engine searches official manufacturer technical documentation, downloads and indexes PDF datasheets in ChromaDB, verifies exact part numbers, splits values and units (UOM), and assigns provenance confidence scores.
                  </div>
                </div>

                <div style={{ background: '#0f172a', padding: '16px', borderRadius: '10px', borderLeft: '4px solid #10b981' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '15px', color: '#ffffff', marginBottom: '4px' }}>
                    3. Validation &amp; Catalog Export
                  </div>
                  <div style={{ color: '#cbd5e1' }}>
                    High-confidence records auto-finalize to commerce output. Records below the 80% confidence threshold pause for reviewer confirmation. Confirmed values persist as canonical normalization aliases in SQLite.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: SINGLE PRODUCT */}
          {activeTab === 'single' && (
            <div>
              <h3 style={{ color: '#60a5fa', marginTop: 0 }}>Single Product Ingestion</h3>
              <p style={{ color: '#cbd5e1' }}>
                Used for ad-hoc enrichment of individual distributor records.
              </p>

              <div style={{ background: '#0f172a', padding: '16px', borderRadius: '10px', marginTop: '12px' }}>
                <h4 style={{ color: '#93c5fd', margin: '0 0 8px 0' }}>Field Specifications:</h4>
                <ul style={{ margin: 0, paddingLeft: '20px', color: '#e2e8f0' }}>
                  <li><strong>Brand Input:</strong> Manufacturer or distributor string. The engine maps aliases to canonical OEM names.</li>
                  <li><strong>MPN Input:</strong> Exact Manufacturer Part Number.</li>
                  <li><strong>Description:</strong> Raw distributor catalog text. Used to disambiguate product categories.</li>
                  <li><strong>Custom Schema:</strong> Optional comma-separated list of attributes to enforce during extraction.</li>
                </ul>
              </div>
            </div>
          )}

          {/* TAB 3: BATCH PROCESSING */}
          {activeTab === 'batch' && (
            <div>
              <h3 style={{ color: '#c084fc', marginTop: 0 }}>Bulk Catalog Ingestion</h3>
              <p style={{ color: '#cbd5e1' }}>
                Process multi-thousand catalog records from CSV files with series-aware knowledge reuse.
              </p>

              <div style={{ background: '#0f172a', padding: '16px', borderRadius: '10px', marginTop: '12px' }}>
                <h4 style={{ color: '#d8b4fe', margin: '0 0 8px 0' }}>Batch Processing Procedure:</h4>
                <ol style={{ margin: 0, paddingLeft: '20px', color: '#e2e8f0' }}>
                  <li>Upload a CSV file containing <code>Brand</code> and <code>Mfg_Part_Num</code> headers.</li>
                  <li>Click <strong>Start Batch Processing</strong>.</li>
                  <li><strong>Series Knowledge Sharing:</strong> Sibling products in the same product line automatically share baseline specs, eliminating redundant external queries.</li>
                  <li>Monitor job completion under <strong>Jobs Monitor</strong> and download the standardized 252-column export.</li>
                </ol>
              </div>
            </div>
          )}

          {/* TAB 4: HUMAN REVIEW & EDIT */}
          {activeTab === 'review' && (
            <div>
              <h3 style={{ color: '#34d399', marginTop: 0 }}>Human-in-the-Loop Verification Console</h3>
              <p style={{ color: '#cbd5e1' }}>
                The engine halts execution when source evidence is ambiguous or confidence is below threshold.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginTop: '14px' }}>
                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px' }}>
                  <div style={{ fontWeight: 'bold', color: '#60a5fa', marginBottom: '4px' }}>Provenance Auditing</div>
                  <div style={{ fontSize: '13px', color: '#cbd5e1' }}>
                    Each attribute card displays exact document citations, chunk provenance, and confidence levels.
                  </div>
                </div>

                <div style={{ background: '#0f172a', padding: '14px', borderRadius: '8px' }}>
                  <div style={{ fontWeight: 'bold', color: '#34d399', marginBottom: '4px' }}>Value and Unit Normalization</div>
                  <div style={{ fontSize: '13px', color: '#cbd5e1' }}>
                    Measurements are partitioned into separate value and unit (UOM) fields for clean catalog standardization.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: PIPELINE ARCHITECTURE */}
          {activeTab === 'pipeline' && (
            <div>
              <h3 style={{ color: '#60a5fa', marginTop: 0 }}>5-Stage Architecture Overview</h3>
              <p style={{ color: '#cbd5e1' }}>
                Sequential verification pipeline implemented in LangGraph:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px' }}>
                <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '8px' }}>
                  <strong style={{ color: '#60a5fa' }}>Stage 1: Taxonomy &amp; Identity</strong> — Normalizes brand names and maps items to deep leaf categories with 8-digit UNSPSC codes.
                </div>
                <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '8px' }}>
                  <strong style={{ color: '#c084fc' }}>Stage 2: Exact-MPN Sourcing</strong> — Discovers official technical datasheets, downloads PDFs, and verifies verbatim part numbers.
                </div>
                <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '8px' }}>
                  <strong style={{ color: '#38bdf8' }}>Stage 3: RAG Extraction &amp; Knowledge Reuse</strong> — Retrieves attribute chunks from ChromaDB and applies shared series attributes.
                </div>
                <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '8px' }}>
                  <strong style={{ color: '#fbbf24' }}>Stage 4: Validation &amp; Confidence Scoring</strong> — Filters invalid values and applies 5-tier confidence scoring.
                </div>
                <div style={{ background: '#0f172a', padding: '12px 16px', borderRadius: '8px' }}>
                  <strong style={{ color: '#34d399' }}>Stage 5: Commercial Copywriting</strong> — Produces invoice descriptions ≤40 chars, long descriptions, bullet specifications, and 252-column export formatting.
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'flex-end',
          background: '#0f172a'
        }}>
          <button
            onClick={onClose}
            className="btn btn-primary"
            style={{ padding: '8px 20px' }}
          >
            Close Guide
          </button>
        </div>
      </div>
    </div>
  )
}

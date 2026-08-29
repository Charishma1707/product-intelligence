import React from 'react';

const CRAG_COLORS = {
  relevant: '#22c55e',
  ambiguous: '#f59e0b',
  irrelevant: '#ef4444',
};

function CRAGBadge({ grades, contextCount }) {
  if (!grades) return null;
  const { relevant, ambiguous, irrelevant, avg_score, corrective_triggered } = grades;
  return (
    <div style={{
      marginTop: 8,
      padding: '8px 12px',
      background: 'rgba(99,102,241,0.12)',
      border: '1px solid rgba(99,102,241,0.35)',
      borderRadius: 8,
      display: 'flex',
      gap: 12,
      flexWrap: 'wrap',
      alignItems: 'center',
      fontSize: 11,
    }}>
      <span style={{ color: '#a5b4fc', fontWeight: 700, letterSpacing: 1 }}>⬡ CRAG</span>
      <span style={{ color: CRAG_COLORS.relevant }}>✓ {relevant} Relevant</span>
      <span style={{ color: CRAG_COLORS.ambiguous }}>~ {ambiguous} Ambiguous</span>
      <span style={{ color: CRAG_COLORS.irrelevant }}>✗ {irrelevant} Irrelevant</span>
      <span style={{ color: '#9ca3af' }}>Avg Score: <strong style={{ color: '#e5e7eb' }}>{(avg_score * 100).toFixed(0)}%</strong></span>
      {contextCount != null && (
        <span style={{
          background: 'rgba(99,102,241,0.2)',
          color: '#c4b5fd',
          padding: '2px 8px',
          borderRadius: 20,
          fontWeight: 700,
          border: '1px solid rgba(99,102,241,0.4)',
        }}>
          📌 {contextCount} sub-chunks → extractor
        </span>
      )}
      {corrective_triggered && (
        <span style={{
          background: 'rgba(245,158,11,0.2)',
          color: '#fbbf24',
          padding: '2px 8px',
          borderRadius: 20,
          fontWeight: 700,
          border: '1px solid rgba(245,158,11,0.4)',
        }}>
          ⚡ Corrective Search Triggered
        </span>
      )}
    </div>
  );
}

export default function PipelineTrace({ logs }) {
  if (!logs || logs.length === 0) return null;

  const nodeColors = {
    identity:  '#818cf8',
    taxonomy:  '#34d399',
    retrieve:  '#60a5fa',
    extract:   '#f59e0b',
    validate:  '#a78bfa',
    copywrite: '#fb923c',
    finalize:  '#22c55e',
  };

  return (
    <div className="card" style={{ marginTop: 'var(--space-lg)' }}>
      <div className="card-header">
        <h2 className="card-title">⚡ Pipeline Execution Trace</h2>
      </div>
      <div className="card-body" style={{
        background: '#0d1117',
        color: '#e5e7eb',
        padding: '16px',
        borderRadius: '0 0 12px 12px',
        overflowX: 'auto',
        fontFamily: 'monospace',
        fontSize: '13px',
      }}>
        {logs.map((log, i) => (
          <div key={i} style={{
            marginBottom: '12px',
            paddingBottom: '12px',
            borderBottom: i < logs.length - 1 ? '1px solid #1f2937' : 'none',
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              color: '#6b7280',
              marginBottom: '6px',
              fontSize: '11px',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 6,
            }}>
              <span style={{ color: '#4b5563' }}>[{new Date(log.timestamp).toLocaleTimeString()}]</span>
              <span style={{
                background: nodeColors[log.node] ? `${nodeColors[log.node]}22` : '#374151',
                color: nodeColors[log.node] || '#9ca3af',
                padding: '2px 8px',
                borderRadius: 20,
                textTransform: 'uppercase',
                fontWeight: 700,
                fontSize: 10,
                border: `1px solid ${nodeColors[log.node] ? nodeColors[log.node] + '44' : '#4b5563'}`,
              }}>
                {log.node}
              </span>
            </div>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.7', color: '#d1d5db' }}>
              {log.message}
            </div>
            {/* CRAG Grades badge — shown on retrieve node log entries */}
            {log.node === 'retrieve' && log.crag_grades && (
              <CRAGBadge
                grades={log.crag_grades}
                contextCount={log.relevant_context_count ?? null}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

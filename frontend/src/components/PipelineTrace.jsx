import React from 'react';

export default function PipelineTrace({ logs }) {
  if (!logs || logs.length === 0) return null;

  return (
    <div className="card" style={{ marginTop: 'var(--space-lg)' }}>
      <div className="card-header">
        <h2 className="card-title">🔍 Pipeline Execution Trace</h2>
      </div>
      <div className="card-body" style={{ background: '#111827', color: '#e5e7eb', padding: '16px', borderRadius: '0 0 12px 12px', overflowX: 'auto', fontFamily: 'monospace', fontSize: '13px' }}>
        {logs.map((log, i) => (
          <div key={i} style={{ marginBottom: '12px', paddingBottom: '12px', borderBottom: i < logs.length - 1 ? '1px solid #374151' : 'none' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#9ca3af', marginBottom: '4px', fontSize: '11px' }}>
              <span>[{new Date(log.timestamp).toLocaleTimeString()}]</span>
              <span style={{ background: '#374151', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>{log.node}</span>
            </div>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
              {log.message}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

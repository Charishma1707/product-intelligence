import { useState, useMemo } from 'react'

const FIELD_GROUPS = [
  {
    title: '🔑 Product Identifiers & Classification',
    fields: [
      { key: 'upc', label: 'UPC', category: 'universal' },
      { key: 'ean', label: 'EAN', category: 'universal' },
      { key: 'gtin', label: 'GTIN', category: 'universal' },
      { key: 'unspsc', label: 'UNSPSC', category: 'universal' },
      { key: 'alternate_part_number', label: 'Alternate Part Number', category: 'universal' },
    ]
  },
  {
    title: '💰 Commercial & Packaging Details',
    fields: [
      { key: 'warranty', label: 'Warranty', category: 'commercial' },
      { key: 'list_price', label: 'List Price', category: 'commercial' },
      { key: 'selling_qty', label: 'Selling Qty', category: 'commercial' },
      { key: 'selling_uom', label: 'Selling UOM', category: 'commercial' },
      { key: 'standard_packaging_info', label: 'Standard Packaging Information', category: 'commercial' },
      { key: 'country_of_origin', label: 'Country Of Origin', category: 'commercial' },
      { key: 'discontinued', label: 'Discontinued', category: 'commercial' },
    ]
  },
  {
    title: '📐 Physical Dimensions & Weight',
    fields: [
      { key: 'length', label: 'LENGTH', category: 'dimensions' },
      { key: 'length_uom', label: 'LENGTH_UOM', category: 'dimensions' },
      { key: 'height', label: 'HEIGHT', category: 'dimensions' },
      { key: 'height_uom', label: 'HEIGHT_UOM', category: 'dimensions' },
      { key: 'width', label: 'WIDTH', category: 'dimensions' },
      { key: 'width_uom', label: 'WIDTH_UOM', category: 'dimensions' },
      { key: 'weight', label: 'WEIGHT', category: 'dimensions' },
      { key: 'weight_uom', label: 'WEIGHT_UOM', category: 'dimensions' },
      { key: 'volume', label: 'VOLUME', category: 'dimensions' },
      { key: 'volume_uom', label: 'VOLUME_UOM', category: 'dimensions' },
    ]
  },
  {
    title: '🖼️ Product Media & Imagery',
    fields: [
      { key: 'product_image_url', label: 'Product Image', category: 'media' },
      { key: 'actual_image', label: 'Actual Image (Yes/No)', category: 'media' },
      { key: 'alt_img_1', label: 'Alternate Image 1', category: 'media' },
      { key: 'alt_img_2', label: 'Alternate Image 2', category: 'media' },
      { key: 'alt_img_3', label: 'Alternate Image 3', category: 'media' },
      { key: 'alt_img_4', label: 'Alternate Image 4', category: 'media' },
      { key: 'video_link', label: 'Video Link', category: 'media' },
      { key: 'video_link_1', label: 'Video Link 1', category: 'media' },
    ]
  },
  {
    title: '📄 Technical Compliance & Documentation',
    fields: [
      { key: 'spec_sheet_url', label: 'Specification Sheet', category: 'documents' },
      { key: 'manual_url', label: 'Owners/User Manual', category: 'documents' },
      { key: 'installation_url', label: 'Instruction/Installation Manual', category: 'documents' },
      { key: 'sds_url', label: 'SDS', category: 'documents' },
      { key: 'sds_1', label: 'SDS_1', category: 'documents' },
      { key: 'warranty_url', label: 'Warranty Information', category: 'documents' },
      { key: 'catalog_url', label: 'Catalog', category: 'documents' },
      { key: 'service_manual', label: 'Service Manual', category: 'documents' },
      { key: 'line_drawing', label: 'Line Drawing', category: 'documents' },
      { key: 'mtr', label: 'MTR', category: 'documents' },
      { key: 'rohs', label: 'RoHS', category: 'documents' },
      { key: 'full_engineering_drawing', label: 'Full Engineering Drawing', category: 'documents' },
      { key: 'energy_guide_url', label: 'Energy Star Guide', category: 'documents' },
      { key: 'technical_bulletin', label: 'Technical Bulletin', category: 'documents' },
      { key: 'submittal', label: 'Submittal', category: 'documents' },
      { key: 'compatibility_chart', label: 'Compatibility Chart', category: 'documents' },
      { key: 'size_chart', label: 'Size Chart', category: 'documents' },
      { key: 'product_label', label: 'Product Label / Package Insert', category: 'documents' },
    ]
  }
]

export default function FinalFieldsTable({ product, corrections, onChange }) {
  const [filterText, setFilterText] = useState('')
  const [expandedSections, setExpandedSections] = useState({
    0: true, 1: true, 2: true, 3: true, 4: true
  })

  const toggleSection = (idx) => {
    setExpandedSections(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  // Helper to extract field value & metadata from product
  const getFieldInfo = (key) => {
    // 1. Check corrections override first
    if (corrections[key] !== undefined) {
      return {
        value: corrections[key],
        confidence: 1.0,
        source: 'Human Edit',
        sourceType: 'human',
        highReason: 'Verified and manually edited by human reviewer',
        lowReason: null,
        isEdited: true,
      }
    }

    // 2. Check specifications object
    const spec = product?.specifications?.[key]
    if (spec) {
      const val = typeof spec === 'object' ? spec.value : spec
      const conf = typeof spec === 'object' ? (spec.confidence ?? 0.8) : 0.8
      const method = typeof spec === 'object' ? spec.method : 'llm'
      const cause = typeof spec === 'object' ? spec.cause : ''
      const abbrSource = typeof spec === 'object' ? spec.abbr_source : null

      let sourceTag = 'LLM'
      let sourceType = 'llm'
      if (method === 'llm_inferred_from_description' || abbrSource) {
        sourceTag = `Desc Infer (${abbrSource || 'abbr'})`
        sourceType = 'desc_infer'
      } else if (method === 'chromadb_exact' || method === 'exact_match') {
        sourceTag = 'ChromaDB'
        sourceType = 'chroma'
      } else if (method === 'series_reuse' || method === 'series_knowledge') {
        sourceTag = 'Knowledge Graph'
        sourceType = 'kg'
      } else if (method === 'human_verified') {
        sourceTag = 'Human Verified'
        sourceType = 'human'
      } else if (method === 'web_search') {
        sourceTag = 'Search'
        sourceType = 'search'
      }

      return {
        value: val ?? '',
        confidence: conf,
        source: sourceTag,
        sourceType,
        highReason: conf >= 0.8 ? (cause || 'Corroborated by high-confidence source snippet') : null,
        lowReason: conf < 0.8 ? (cause || 'Inferred with moderate confidence — needs review') : null,
        isEdited: false,
      }
    }

    // 3. Check direct product state properties
    const directVal = product?.[key]
    if (directVal !== undefined && directVal !== null && directVal !== '') {
      let sourceTag = 'Pipeline Direct'
      let sourceType = 'llm'
      if (key.includes('url')) {
        sourceTag = 'Official MFR Site'
        sourceType = 'search'
      }

      return {
        value: String(directVal),
        confidence: 0.9,
        source: sourceTag,
        sourceType,
        highReason: 'Directly verified from product state or manufacturer domain',
        lowReason: null,
        isEdited: false,
      }
    }

    // 4. Missing / Not Found
    return {
      value: '',
      confidence: 0.0,
      source: 'Not Found',
      sourceType: 'missing',
      highReason: null,
      lowReason: 'Not found in manufacturer domain or spec sheet',
      isEdited: false,
    }
  }

  const getSourceBadgeStyle = (sourceType) => {
    switch (sourceType) {
      case 'desc_infer':
        return { background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.3)' }
      case 'chroma':
        return { background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.3)' }
      case 'kg':
        return { background: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', border: '1px solid rgba(139, 92, 246, 0.3)' }
      case 'human':
        return { background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)' }
      case 'search':
        return { background: 'rgba(6, 182, 212, 0.15)', color: '#22d3ee', border: '1px solid rgba(6, 182, 212, 0.3)' }
      default:
        return { background: 'rgba(148, 163, 184, 0.1)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.2)' }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Search / Filter bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <input
          type="text"
          value={filterText}
          onChange={e => setFilterText(e.target.value)}
          placeholder="🔍 Filter delivery fields (e.g. UPC, SDS, Image, Length)..."
          style={{
            flex: 1, minWidth: 260,
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: 6, padding: '8px 14px',
            color: '#e2e8f0', fontSize: '0.85rem'
          }}
        />
        <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
          Showing all <strong>~50 Unilog Delivery Attributes</strong> with provenance &amp; confidence explanations
        </div>
      </div>

      {/* Field Groups */}
      {FIELD_GROUPS.map((grp, gIdx) => {
        const filteredFields = grp.fields.filter(f =>
          f.label.toLowerCase().includes(filterText.toLowerCase()) ||
          f.key.toLowerCase().includes(filterText.toLowerCase())
        )

        if (filteredFields.length === 0) return null
        const isExpanded = expandedSections[gIdx] !== false

        return (
          <div key={grp.title} style={{
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 8,
            overflow: 'hidden',
            background: 'rgba(15, 23, 42, 0.4)'
          }}>
            {/* Section Header */}
            <div
              onClick={() => toggleSection(gIdx)}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 16px',
                background: 'rgba(255, 255, 255, 0.03)',
                cursor: 'pointer',
                userSelect: 'none',
                borderBottom: isExpanded ? '1px solid rgba(255, 255, 255, 0.06)' : 'none'
              }}
            >
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f1f5f9' }}>
                {grp.title} ({filteredFields.length})
              </span>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                {isExpanded ? '▲ Collapse' : '▼ Expand'}
              </span>
            </div>

            {/* Table */}
            {isExpanded && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: 'rgba(0, 0, 0, 0.2)', borderBottom: '1px solid rgba(255, 255, 255, 0.06)' }}>
                      <th style={{ padding: '8px 12px', color: '#94a3b8', width: '22%' }}>Delivery Field</th>
                      <th style={{ padding: '8px 12px', color: '#94a3b8', width: '28%' }}>Extracted / Human Value</th>
                      <th style={{ padding: '8px 12px', color: '#94a3b8', width: '22%' }}>Why High / Low Confidence</th>
                      <th style={{ padding: '8px 12px', color: '#94a3b8', width: '14%' }}>Source / Extraction Method</th>
                      <th style={{ padding: '8px 12px', color: '#94a3b8', width: '14%', textAlign: 'center' }}>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredFields.map(field => {
                      const info = getFieldInfo(field.key)
                      const isHigh = info.confidence >= 0.8
                      const isMissing = !info.value

                      return (
                        <tr key={field.key} style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          background: info.isEdited ? 'rgba(16, 185, 129, 0.04)' : 'transparent'
                        }}>
                          {/* Field Label */}
                          <td style={{ padding: '8px 12px', fontWeight: 600, color: '#e2e8f0' }}>
                            {field.label}
                            <div style={{ fontSize: '0.68rem', color: '#64748b' }}>{field.key}</div>
                          </td>

                          {/* Editable Value */}
                          <td style={{ padding: '6px 12px' }}>
                            <input
                              type="text"
                              value={corrections[field.key] !== undefined ? corrections[field.key] : info.value}
                              onChange={e => onChange(field.key, e.target.value)}
                              placeholder={`Enter ${field.label}...`}
                              style={{
                                width: '100%',
                                background: info.isEdited ? 'rgba(16, 185, 129, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                                border: `1px solid ${info.isEdited ? 'rgba(16, 185, 129, 0.4)' : 'rgba(255, 255, 255, 0.1)'}`,
                                borderRadius: 4,
                                padding: '5px 8px',
                                color: '#f8fafc',
                                fontSize: '0.8rem',
                                outline: 'none'
                              }}
                            />
                          </td>

                          {/* Confidence Explanation */}
                          <td style={{ padding: '8px 12px', fontSize: '0.74rem' }}>
                            {isMissing ? (
                              <span style={{ color: '#f87171' }}>
                                ⚠️ {info.lowReason || 'Not Found in Available Sources'}
                              </span>
                            ) : isHigh ? (
                              <span style={{ color: '#34d399' }}>
                                ✓ {info.highReason || 'Directly corroborated with high confidence'}
                              </span>
                            ) : (
                              <span style={{ color: '#fbbf24' }}>
                                ⚡ {info.lowReason || 'Inferred from description shorthand'}
                              </span>
                            )}
                          </td>

                          {/* Source Tag */}
                          <td style={{ padding: '8px 12px' }}>
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 4,
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              ...getSourceBadgeStyle(info.sourceType)
                            }}>
                              {info.source}
                            </span>
                          </td>

                          {/* Score pill */}
                          <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                            <span style={{
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              color: isHigh ? '#34d399' : info.confidence > 0.4 ? '#fbbf24' : '#f87171'
                            }}>
                              {Math.round(info.confidence * 100)}%
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

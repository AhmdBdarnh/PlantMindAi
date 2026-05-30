import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';
import { fmtDate, fmtNum } from '../utils/format';

// ── Status badge colours ──────────────────────────────────────────────────────
const STATUS_STYLES = {
  pending:             { bg: '#fef9c3', color: '#854d0e', border: '#fde047', label: 'Pending Review' },
  approved:            { bg: '#dcfce7', color: '#166534', border: '#86efac', label: 'Approved' },
  applied:             { bg: '#dbeafe', color: '#1e40af', border: '#93c5fd', label: 'Applied' },
  rejected:            { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'Rejected' },
  invalid:             { bg: '#fce7f3', color: '#9d174d', border: '#f9a8d4', label: 'Invalid' },
  needs_manual_review: { bg: '#ffedd5', color: '#9a3412', border: '#fdba74', label: 'Needs Review' },
};

const PLANT_STATUS_COLOURS = {
  healthy:          '#16a34a',
  slightly_stressed:'#ca8a04',
  stressed:         '#ea580c',
  unhealthy:        '#dc2626',
  unknown:          '#6b7280',
};

const SEVERITY_COLOURS = {
  none:   '#6b7280',
  low:    '#16a34a',
  medium: '#ca8a04',
  high:   '#dc2626',
};

const RISK_COLOURS = {
  low:    '#16a34a',
  medium: '#ca8a04',
  high:   '#dc2626',
};

// ── Component: StatusBadge ────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db', label: status };
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 700,
      background: s.bg,
      color: s.color,
      border: `1px solid ${s.border}`,
      letterSpacing: '0.03em',
    }}>
      {s.label}
    </span>
  );
}

// ── Component: DataQualityWarning ─────────────────────────────────────────────
function DataQualityWarning({ recommendation }) {
  if (!recommendation) return null;
  const quality   = recommendation.data_quality;
  const missing   = recommendation.context_summary?.missing_data || [];
  const isWeak    = quality === 'weak' || quality === 'medium';
  const hasMissing = missing.length > 0;
  if (!isWeak && !hasMissing) return null;
  return (
    <div style={{
      background: '#fff7ed',
      border: '1px solid #fb923c',
      borderRadius: 8,
      padding: '12px 16px',
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <svg width="18" height="18" fill="none" stroke="#ea580c" strokeWidth="2" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        <strong style={{ color: '#9a3412', fontSize: 13 }}>
          Data Quality: {quality?.toUpperCase()}
          {hasMissing ? ` — ${missing.length} data source(s) unavailable` : ''}
        </strong>
      </div>
      {hasMissing && (
        <ul style={{ margin: 0, paddingLeft: 20, color: '#7c2d12', fontSize: 12 }}>
          {missing.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      <p style={{ margin: '6px 0 0', color: '#9a3412', fontSize: 12 }}>
        This recommendation may be conservative or incomplete due to missing data. Review carefully before approving.
      </p>
    </div>
  );
}

// ── Component: SetpointComparisonTable ────────────────────────────────────────
function SetpointComparisonTable({ current, recommended, changes }) {
  if (!current || !recommended) return null;

  const UNITS = {
    temperature:    '°C',    humidity:       '%',      light:        'lux',
    soil_ph:        'pH',    soil_ec:        'µS/cm',  soil_temp:    '°C',
    soil_moisture:  '%',     soil_hysteresis:'%',
    water_flow:     'L/h',   fertilizer_flow:'L/h',
  };

  const AI_KEY_MAP = {
    temperature:    'Temperature',    humidity:       'Humidity',
    light:          'Light',          soil_ph:        'Soil pH',
    soil_ec:        'Soil EC',        soil_temp:      'Soil Temp',
    soil_moisture:  'Soil Moisture',  soil_hysteresis:'Soil Hysteresis',
    water_flow:     'Water Flow',     fertilizer_flow:'Fertilizer Flow',
  };

  const changedParams = new Set((changes || []).map(c => c.parameter));

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#f8fafc' }}>
            {['Parameter', 'Current', 'AI Recommended', 'Difference', 'Changed'].map(h => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(AI_KEY_MAP).map(([dbKey, aiKey]) => {
            const curVal  = current[dbKey];
            const recVal  = recommended[aiKey];
            const unit    = UNITS[dbKey] || '';
            const changed = changedParams.has(aiKey);
            const diff    = (recVal != null && curVal != null) ? (Number(recVal) - Number(curVal)) : null;
            const diffStr = diff != null ? (diff > 0 ? `+${fmtNum(diff)}` : fmtNum(diff)) : '—';
            const diffColor = diff === null ? '#6b7280' : diff > 0 ? '#059669' : diff < 0 ? '#dc2626' : '#6b7280';
            return (
              <tr key={dbKey} style={{ background: changed ? '#f0fdf4' : 'transparent', borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '8px 12px', fontWeight: changed ? 700 : 400, color: changed ? '#166534' : '#334155' }}>
                  {aiKey}
                </td>
                <td style={{ padding: '8px 12px', color: '#475569' }}>
                  {curVal != null ? `${fmtNum(curVal)} ${unit}` : '—'}
                </td>
                <td style={{ padding: '8px 12px', fontWeight: changed ? 700 : 400, color: changed ? '#166534' : '#475569' }}>
                  {recVal != null ? `${typeof recVal === 'string' ? recVal : fmtNum(recVal)} ${typeof recVal !== 'string' ? unit : ''}` : '—'}
                </td>
                <td style={{ padding: '8px 12px', color: diffColor, fontWeight: 600 }}>
                  {changed ? diffStr : '—'}
                </td>
                <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                  {changed ? (
                    <span style={{ background: '#dcfce7', color: '#166534', padding: '1px 8px', borderRadius: 8, fontSize: 11, fontWeight: 700 }}>YES</span>
                  ) : (
                    <span style={{ color: '#94a3b8', fontSize: 11 }}>no</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Component: ChangesDetail ──────────────────────────────────────────────────
function ChangesDetail({ changes }) {
  if (!changes || changes.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#6b7280', background: '#f8fafc', borderRadius: 8 }}>
        <p style={{ margin: 0 }}>No setpoint changes recommended — the AI suggests keeping all current values.</p>
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {changes.map((chg, i) => {
        const diff = chg.difference;
        const diffStr = diff != null ? (diff > 0 ? `+${fmtNum(diff)}` : fmtNum(diff)) : '—';
        const diffColor = diff > 0 ? '#059669' : diff < 0 ? '#dc2626' : '#6b7280';
        const riskColor = RISK_COLOURS[chg.risk_level] || '#6b7280';
        return (
          <div key={i} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontWeight: 700, color: '#1e293b', fontSize: 14 }}>{chg.parameter}</span>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontWeight: 700, color: diffColor, fontSize: 13 }}>
                  {fmtNum(chg.current_value)} → {fmtNum(chg.recommended_value)} ({diffStr})
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 8, background: riskColor + '22', color: riskColor, border: `1px solid ${riskColor}44` }}>
                  {(chg.risk_level || 'low').toUpperCase()} RISK
                </span>
                {chg.clamped && (
                  <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 8, background: '#fef9c3', color: '#854d0e', border: '1px solid #fde04788' }}>
                    CLAMPED
                  </span>
                )}
              </div>
            </div>
            <p style={{ margin: 0, color: '#475569', fontSize: 13, lineHeight: 1.5 }}>
              {chg.reason || 'No reason provided.'}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ── Component: ValidationNotes ────────────────────────────────────────────────
function ValidationNotes({ notes }) {
  if (!notes || notes.length === 0) return null;
  return (
    <div style={{ background: '#fffbeb', border: '1px solid #fbbf24', borderRadius: 8, padding: '12px 16px' }}>
      <p style={{ margin: '0 0 8px', fontWeight: 700, color: '#92400e', fontSize: 13 }}>
        Safety Validation Notes ({notes.length})
      </p>
      <ul style={{ margin: 0, paddingLeft: 18, color: '#78350f', fontSize: 12, lineHeight: 1.6 }}>
        {notes.map((n, i) => <li key={i}>{n}</li>)}
      </ul>
    </div>
  );
}

// ── Component: ContextSummary ─────────────────────────────────────────────────
function ContextSummary({ rec }) {
  if (!rec) return null;
  const s = rec.context_summary || {};
  const items = [
    { label: 'Plant Health Data',  ok: s.health_available,  icon: '🌿' },
    { label: 'Growth Metrics',     ok: s.growth_available,  icon: '📏' },
    { label: 'Sensor Readings',    ok: s.sensors_available, icon: '📡' },
    { label: 'Growth Trend',       ok: s.trend_available,   icon: '📈' },
  ];
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {items.map(item => (
        <div key={item.label} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '5px 12px', borderRadius: 20,
          background: item.ok ? '#f0fdf4' : '#fef2f2',
          border: `1px solid ${item.ok ? '#86efac' : '#fca5a5'}`,
          fontSize: 12, color: item.ok ? '#166534' : '#991b1b',
        }}>
          <span>{item.icon}</span>
          <span>{item.label}</span>
          <span>{item.ok ? '✓' : '✗'}</span>
        </div>
      ))}
      {s.collection_timestamp && (
        <div style={{ padding: '5px 12px', borderRadius: 20, background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: 12, color: '#64748b' }}>
          📅 Collected: {fmtDate(s.collection_timestamp)}
        </div>
      )}
    </div>
  );
}

// ── Main page component ───────────────────────────────────────────────────────
export default function AISetpointAdvisor({ setpoints, onSetpointsRefresh }) {
  const [recommendation, setRecommendation] = useState(null);
  const [rateLimit,      setRateLimit]      = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [message,    setMessage]    = useState(null); // {type: 'success'|'error', text: string}
  const [activeTab,  setActiveTab]  = useState('overview');

  const fetchLatest = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/ai-advisor/latest`);
      const data = await res.json();
      if (data.success) {
        setRecommendation(data.recommendation);
        setRateLimit(data.rate_limit);
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'Could not reach backend: ' + e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  const handleRunNow = async () => {
    setRunLoading(true);
    setMessage(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/ai-advisor/run`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setMessage({ type: 'success', text: data.message });
        setTimeout(() => fetchLatest(), 35000); // refresh after ~35s
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to start AI Advisor.' });
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'Request failed: ' + e.message });
    } finally {
      setRunLoading(false);
    }
  };

  const rec    = recommendation;
  const status = rec?.status;

  const tabs = [
    { id: 'overview',    label: 'Overview' },
    { id: 'setpoints',   label: 'Setpoint Comparison' },
    { id: 'changes',     label: `Changes (${rec?.changes?.length || 0})` },
    { id: 'validation',  label: 'Validation' },
    { id: 'context',     label: 'Data Context' },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 0' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: '0 0 4px', fontSize: 24, fontWeight: 800, color: '#0f172a' }}>
            AI Setpoint Advisor
          </h1>
          <p style={{ margin: 0, color: '#64748b', fontSize: 14 }}>
            GPT-powered analysis of plant health & growth → setpoint recommendations
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {rateLimit && (
            <span style={{ fontSize: 12, color: '#64748b', padding: '4px 10px', background: '#f1f5f9', borderRadius: 8 }}>
              {rateLimit.remaining_today}/{rateLimit.max_per_day} runs left today
            </span>
          )}
          <button
            onClick={fetchLatest}
            style={{ padding: '6px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: 13, color: '#374151' }}
          >
            ↻ Refresh
          </button>
          <button
            onClick={handleRunNow}
            disabled={runLoading || (rateLimit?.remaining_today === 0)}
            style={{
              padding: '8px 18px', borderRadius: 8, border: 'none',
              background: (runLoading || rateLimit?.remaining_today === 0) ? '#94a3b8' : '#4f46e5',
              color: '#fff', cursor: (runLoading || rateLimit?.remaining_today === 0) ? 'not-allowed' : 'pointer',
              fontWeight: 700, fontSize: 13,
            }}
          >
            {runLoading ? 'Starting…' : '▶ Run AI Advisor Now'}
          </button>
        </div>
      </div>

      {/* Feedback message */}
      {message && (
        <div style={{
          padding: '12px 16px', borderRadius: 8, marginBottom: 16,
          background: message.type === 'success' ? '#f0fdf4' : '#fef2f2',
          border: `1px solid ${message.type === 'success' ? '#86efac' : '#fca5a5'}`,
          color: message.type === 'success' ? '#166534' : '#991b1b',
          fontSize: 13,
        }}>
          {message.text}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
          Loading AI recommendation…
        </div>
      )}

      {/* No recommendation yet */}
      {!loading && !rec && (
        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: '48px 24px', textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🤖</div>
          <h3 style={{ margin: '0 0 8px', color: '#334155' }}>No Recommendation Yet</h3>
          <p style={{ color: '#64748b', margin: '0 0 20px', fontSize: 14 }}>
            The AI Advisor runs automatically every day at 15:30.<br />
            You can also trigger it manually using the button above.
          </p>
        </div>
      )}

      {/* Recommendation card */}
      {!loading && rec && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden' }}>

          {/* Card header */}
          <div style={{ padding: '20px 24px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                <StatusBadge status={status} />
                <span style={{ fontSize: 12, color: '#64748b' }}>
                  {fmtDate(rec.created_at)}
                </span>
                {rec.triggered_by && (
                  <span style={{ fontSize: 11, color: '#94a3b8', padding: '1px 8px', background: '#f1f5f9', borderRadius: 8 }}>
                    {rec.triggered_by}
                  </span>
                )}
                {rec.openai_model && (
                  <span style={{ fontSize: 11, color: '#7c3aed', padding: '1px 8px', background: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: 8 }}>
                    {rec.openai_model}
                  </span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#475569', fontStyle: 'italic', maxWidth: 600 }}>
                {rec.summary || '—'}
              </p>
            </div>

            {/* KPI chips */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: PLANT_STATUS_COLOURS[rec.plant_status] || '#6b7280' }}>
                  {(rec.plant_status || 'unknown').replace('_', ' ').toUpperCase()}
                </div>
                <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Plant Status</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: SEVERITY_COLOURS[rec.severity] || '#6b7280' }}>
                  {(rec.severity || 'none').toUpperCase()}
                </div>
                <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Severity</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#0f172a' }}>
                  {rec.confidence != null ? `${Math.round(rec.confidence * 100)}%` : '—'}
                </div>
                <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Confidence</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#0f172a' }}>
                  {rec.changes?.length || 0}
                </div>
                <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Changes</div>
              </div>
            </div>
          </div>

          {/* Problem detected banner */}
          {rec.problem_detected && rec.main_problem && rec.main_problem !== 'none' && (
            <div style={{ padding: '10px 24px', background: '#fef2f2', borderBottom: '1px solid #fca5a5' }}>
              <span style={{ fontWeight: 700, color: '#991b1b', fontSize: 13 }}>
                ⚠ Problem Detected:
              </span>
              <span style={{ color: '#991b1b', fontSize: 13, marginLeft: 8 }}>
                {rec.main_problem}
              </span>
            </div>
          )}

          {/* Applied info */}
          {status === 'applied' && (
            <div style={{ padding: '10px 24px', background: '#dbeafe', borderBottom: '1px solid #93c5fd' }}>
              <span style={{ fontWeight: 700, color: '#1e40af', fontSize: 13 }}>
                ✓ Applied at {fmtDate(rec.applied_at)} — approved via Budget Manager (Layer 3).
              </span>
            </div>
          )}

          {/* Rejected info */}
          {status === 'rejected' && rec.rejection_reason && (
            <div style={{ padding: '10px 24px', background: '#fee2e2', borderBottom: '1px solid #fca5a5' }}>
              <span style={{ fontWeight: 700, color: '#991b1b', fontSize: 13 }}>
                ✗ Rejected: {rec.rejection_reason}
              </span>
            </div>
          )}

          {/* Invalid / API-failure info */}
          {status === 'invalid' && rec.rejection_reason && (
            <div style={{ padding: '12px 24px', background: '#fce7f3', borderBottom: '1px solid #f9a8d4' }}>
              <span style={{ fontWeight: 700, color: '#9d174d', fontSize: 13 }}>
                ⚠ Failed: {rec.rejection_reason}
              </span>
            </div>
          )}

          {/* Data quality warning */}
          <div style={{ padding: '0 24px', paddingTop: 16 }}>
            <DataQualityWarning recommendation={rec} />
          </div>

          {/* Tabs */}
          <div style={{ padding: '0 24px', borderBottom: '1px solid #f1f5f9', display: 'flex', gap: 0, overflowX: 'auto' }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '10px 16px',
                  border: 'none',
                  borderBottom: activeTab === tab.id ? '2px solid #4f46e5' : '2px solid transparent',
                  background: 'transparent',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: activeTab === tab.id ? 700 : 400,
                  color: activeTab === tab.id ? '#4f46e5' : '#64748b',
                  whiteSpace: 'nowrap',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ padding: '20px 24px' }}>

            {/* Overview tab */}
            {activeTab === 'overview' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <h4 style={{ margin: '0 0 8px', color: '#334155', fontSize: 14 }}>AI Explanation</h4>
                  <p style={{ margin: 0, color: '#475569', fontSize: 13, lineHeight: 1.7, background: '#f8fafc', padding: '12px 16px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                    {rec.detailed_explanation || 'No explanation provided.'}
                  </p>
                </div>
                <ContextSummary rec={rec} />
              </div>
            )}

            {/* Setpoint comparison tab */}
            {activeTab === 'setpoints' && (
              <SetpointComparisonTable
                current={rec.current_setpoints}
                recommended={rec.recommended_setpoints}
                changes={rec.changes}
              />
            )}

            {/* Changes tab */}
            {activeTab === 'changes' && (
              <ChangesDetail changes={rec.changes} />
            )}

            {/* Validation tab */}
            {activeTab === 'validation' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <ValidationNotes notes={rec.validation_notes} />
                {(!rec.validation_notes || rec.validation_notes.length === 0) && (
                  <div style={{ padding: '20px', textAlign: 'center', color: '#6b7280', background: '#f8fafc', borderRadius: 8 }}>
                    All validation checks passed — no issues found.
                  </div>
                )}
              </div>
            )}

            {/* Context tab */}
            {activeTab === 'context' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <ContextSummary rec={rec} />
                {rec.context_summary?.missing_data?.length > 0 && (
                  <div>
                    <h4 style={{ margin: '0 0 8px', color: '#334155', fontSize: 14 }}>Missing Data Sources</h4>
                    <ul style={{ margin: 0, paddingLeft: 18, color: '#dc2626', fontSize: 13 }}>
                      {rec.context_summary.missing_data.map((m, i) => <li key={i}>{m}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Layer 3 routing banner — single approval point */}
          <div style={{ padding: '14px 24px', borderTop: '1px solid #f1f5f9', background: '#eff6ff', borderBottomLeftRadius: 12, borderBottomRightRadius: 12 }}>
            {(status === 'pending' || status === 'needs_manual_review') && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <div style={{ fontSize: 13, color: '#1e40af', lineHeight: 1.6 }}>
                  <strong>Waiting for Layer 3 review.</strong> This Layer 2 recommendation is reviewed by the Budget Manager (Layer 3),
                  which checks sensor safety, plant health, and daily budget before presenting a final decision.
                  <br />
                  <span style={{ fontWeight: 700 }}>To approve or reject, go to the <span style={{ textDecoration: 'underline', cursor: 'default' }}>Budget Manager</span> page.</span>
                  {status === 'needs_manual_review' && (
                    <div style={{ marginTop: 6, padding: '6px 10px', background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 6, color: '#92400e', fontSize: 12 }}>
                      Note: Some recommended changes exceeded normal limits and were clamped. Layer 3 will factor this into its decision.
                    </div>
                  )}
                </div>
              </div>
            )}
            {status === 'applied' && (
              <div style={{ fontSize: 13, color: '#166534' }}>
                ✓ Recommendation applied via Budget Manager at {rec.applied_at ? new Date(rec.applied_at).toLocaleString() : '—'}.
              </div>
            )}
            {status === 'rejected' && (
              <div style={{ fontSize: 13, color: '#991b1b' }}>
                ✗ Recommendation rejected. {rec.rejection_reason ? `Reason: ${rec.rejection_reason}` : ''}
              </div>
            )}
            {status === 'invalid' && (
              <div style={{ fontSize: 13, color: '#9d174d' }}>
                ⚠ This recommendation was invalid and cannot be applied.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Info footer */}
      <div style={{ marginTop: 24, padding: '16px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
        <p style={{ margin: 0, fontSize: 12, color: '#64748b', lineHeight: 1.7 }}>
          <strong>How it works:</strong> Every day at 15:30 the AI Advisor (Layer 2) collects plant health data, growth metrics, 24-hour sensor statistics, and current setpoints, then sends them to GPT for analysis. The AI returns a recommendation validated against safety limits and saved here as "Pending Review".
          After Layer 2 finishes, Layer 3 (Budget Manager) automatically reviews the recommendation against sensor safety, plant health, and daily budget constraints before presenting a final decision.
          <strong> Approval happens only in the Budget Manager page</strong> — setpoints are <strong>never changed automatically</strong>.
        </p>
      </div>
    </div>
  );
}

import React, { useState } from 'react';
import { fmtDate } from '../utils/format';

// ── SVG icon helper ───────────────────────────────────────────────────────────

function Icon({ path, size = 16, color = 'currentColor', sw = 2, fill = 'none' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill}
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const IC = {
  healthy:   'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  warning:   'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  unknown:   'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  refresh:   'M1 4v6h6M23 20v-6h-6M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15',
  camera:    'M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z M12 13m-3 0a3 3 0 106 0 3 3 0 00-6 0',
  image:     'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
  history:   'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  leaf:      'M17 8C8 10 5.9 16.17 3.82 19c3.15.6 6.41-.34 8.68-2.61 2.56-2.56 3.07-6.44 1.5-9.39zm0 0c-.2 4.17-2.69 7.78-6 10',
  disease:   'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  check:     'M5 13l4 4L19 7',
  s3:        'M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z',
  info:      'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  bio:       'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z',
  chemical:  'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z',
  shield:    'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
};

// ── Disease card ──────────────────────────────────────────────────────────────

function DiseaseCard({ disease }) {
  const [open, setOpen] = useState(false);
  const { name, probability, description, cause, treatment } = disease;
  const sections = [
    { label: 'Prevention', icon: IC.shield,   color: '#16a34a', items: treatment?.prevention },
    { label: 'Biological', icon: IC.bio,      color: '#2563eb', items: treatment?.biological },
    { label: 'Chemical',   icon: IC.chemical, color: '#dc2626', items: treatment?.chemical   },
  ].filter(s => s.items && s.items.length > 0);

  const sev = probability >= 50 ? { bg: '#fee2e2', border: '#fca5a5', color: '#991b1b', bar: '#dc2626' }
            : probability >= 20 ? { bg: '#fffbeb', border: '#fde68a', color: '#92400e', bar: '#d97706' }
            :                     { bg: '#f9fafb', border: '#e5e7eb', color: '#374151', bar: '#9ca3af' };

  return (
    <div style={{ background: sev.bg, border: `1px solid ${sev.border}`, borderRadius: 12, overflow: 'hidden' }}>
      <button onClick={() => setOpen(v => !v)} style={{ width: '100%', padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left' }}>
          <Icon path={IC.disease} size={16} color={sev.color} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: sev.color }}>{name}</div>
            {cause && <div style={{ fontSize: 11, color: sev.color, opacity: 0.75, marginTop: 1 }}>{cause}</div>}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: sev.color }}>{probability}%</div>
            <div style={{ background: '#e5e7eb', borderRadius: 99, height: 5, width: 60, overflow: 'hidden', marginTop: 3 }}>
              <div style={{ width: `${probability}%`, height: '100%', background: sev.bar, borderRadius: 99 }} />
            </div>
          </div>
          <Icon path={open ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} size={14} color={sev.color} />
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 16px 14px', borderTop: `1px solid ${sev.border}` }}>
          {description && (
            <p style={{ fontSize: 13, color: sev.color, lineHeight: 1.6, margin: '12px 0', opacity: 0.9 }}>{description}</p>
          )}
          {sections.map(({ label, icon, color, items }) => (
            <div key={label} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                <Icon path={icon} size={12} color={color} />
                <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color }}>{label}</span>
              </div>
              <ul style={{ paddingLeft: 18, margin: 0 }}>
                {items.slice(0, 3).map((item, i) => (
                  <li key={i} style={{ fontSize: 12, color: sev.color, lineHeight: 1.6 }}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function deriveStatus(dbLatest, liveResult) {
  const r = dbLatest || liveResult;
  if (!r)           return { type: 'unknown',   title: 'No data yet',      conf: null };
  if (!r.success && !dbLatest) return { type: 'error', title: 'Check failed', conf: null };
  if (r.is_healthy) return { type: 'healthy',   title: 'Plant is Healthy', conf: r.health_probability };
  return             { type: 'unhealthy', title: 'Issues Detected',  conf: r.health_probability };
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PlantHealth({
  healthResult,
  healthDbLatest,
  healthDbHistory,
  healthFetchError,
  onRefreshHealth,
  captureSessions,
  captureSessionsLoading,
  captureManualLoading,
  captureManualError,
  onCapture,
}) {
  const [localLoading, setLocalLoading] = useState(false);

  const handleRefresh = async () => {
    if (!onRefreshHealth) return;
    setLocalLoading(true);
    await onRefreshHealth();
    setLocalLoading(false);
  };

  const hasData   = !!(healthDbLatest || healthResult?.success);
  const showError = healthFetchError && !hasData;

  const status    = deriveStatus(healthDbLatest, healthResult);
  const r         = healthDbLatest || (healthResult?.success ? healthResult : null);
  const diseases  = r?.diseases || [];
  const pct       = r?.health_probability ?? 0;
  const isHealthy = r?.is_healthy ?? true;

  // Color theme based on health
  const accent = isHealthy ? '#16a34a' : pct >= 40 ? '#d97706' : '#dc2626';
  const accentBg = isHealthy ? '#f0fdf4' : pct >= 40 ? '#fffbeb' : '#fef2f2';
  const accentBorder = isHealthy ? '#86efac' : pct >= 40 ? '#fde68a' : '#fca5a5';

  // Text palette
  const T = { primary: '#111827', secondary: '#1f2937', label: '#374151', muted: '#6b7280' };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: T.primary }}>Plant Health</h2>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>
            AI-powered health analysis via Plant.id · runs daily at 14:00
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onCapture} disabled={captureManualLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: '1.5px solid #e5e7eb', background: '#fff', color: T.label, fontWeight: 700, fontSize: 12, cursor: captureManualLoading ? 'not-allowed' : 'pointer' }}>
            <Icon path={IC.camera} size={13} color={T.muted} />
            {captureManualLoading ? 'Capturing…' : 'Capture Now'}
          </button>
          <button onClick={handleRefresh} disabled={localLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: 'none', background: localLoading ? '#86efac' : '#16a34a', color: '#fff', fontWeight: 700, fontSize: 12, cursor: localLoading ? 'not-allowed' : 'pointer' }}>
            <Icon path={IC.refresh} size={13} color='#fff' />
            {localLoading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {captureManualError && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 8, padding: '9px 14px', color: '#991b1b', fontSize: 12 }}>
          {captureManualError}
        </div>
      )}

      {/* ── Error state ────────────────────────────────────────────────────── */}
      {showError && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 12, padding: '36px', textAlign: 'center' }}>
          <Icon path={IC.warning} size={36} color='#dc2626' />
          <div style={{ fontSize: 15, fontWeight: 700, color: '#991b1b', marginTop: 10 }}>Could not load health data</div>
          <button onClick={handleRefresh} style={{ marginTop: 14, display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 16px', borderRadius: 8, border: '1.5px solid #fca5a5', background: '#fff', color: '#dc2626', fontWeight: 700, fontSize: 12, cursor: 'pointer' }}>
            <Icon path={IC.refresh} size={12} color='#dc2626' /> Try Again
          </button>
        </div>
      )}

      {/* ── Empty state ────────────────────────────────────────────────────── */}
      {!showError && !hasData && (
        <div style={{ background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 12, padding: '50px', textAlign: 'center' }}>
          <Icon path={IC.leaf} size={36} color='#d1d5db' />
          <div style={{ fontSize: 15, fontWeight: 700, color: T.label, marginTop: 12, marginBottom: 6 }}>No health data yet</div>
          <div style={{ fontSize: 12, color: T.muted, maxWidth: 320, margin: '0 auto' }}>
            Health analysis runs automatically every day at 14:00. Trigger manually with Capture Now.
          </div>
        </div>
      )}

      {/* ── Main content ───────────────────────────────────────────────────── */}
      {!showError && hasData && (
        <>
          {/* ── One compact summary bar — shown ONCE ── */}
          <div style={{
            background: accentBg, border: `1.5px solid ${accentBorder}`,
            borderRadius: 12, padding: '12px 20px',
            display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap',
          }}>
            {/* Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, paddingRight: 24, borderRight: `1px solid ${accentBorder}` }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: accent, flexShrink: 0 }} />
              <span style={{ fontSize: 15, fontWeight: 800, color: accent }}>{status.title}</span>
            </div>
            {/* Confidence */}
            <div style={{ paddingLeft: 24, paddingRight: 24, borderRight: `1px solid ${accentBorder}` }}>
              <div style={{ fontSize: 10, color: T.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Confidence</div>
              <div style={{ fontSize: 22, fontWeight: 900, color: accent, lineHeight: 1 }}>{pct}%</div>
            </div>
            {/* Issues */}
            <div style={{ paddingLeft: 24, paddingRight: 24, borderRight: `1px solid ${accentBorder}` }}>
              <div style={{ fontSize: 10, color: T.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Issues Found</div>
              <div style={{ fontSize: 22, fontWeight: 900, color: diseases.length > 0 ? '#d97706' : '#16a34a', lineHeight: 1 }}>
                {diseases.length}
              </div>
            </div>
            {/* Last check */}
            <div style={{ paddingLeft: 24, marginLeft: 'auto' }}>
              <div style={{ fontSize: 10, color: T.muted, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Last Check</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.primary }}>
                {r?.created_at ? fmtDate(r.created_at) : '—'}
              </div>
            </div>
          </div>

          {/* ── Two-column: API Result | Health History ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignItems: 'start' }}>

            {/* Left: API Result */}
            <div style={{ background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 14, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}>
              {/* Card header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 18px', borderBottom: '1px solid #e5e7eb', background: '#fafafa' }}>
                <div style={{ background: accentBg, borderRadius: 8, padding: 7, display: 'flex' }}>
                  <Icon path={IC.leaf} size={14} color={accent} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>API Result</div>
                  <div style={{ fontSize: 10, color: T.muted, marginTop: 1 }}>Latest health check from Plant.id</div>
                </div>
              </div>

              {/* Body — no scroll, grows with content */}
              <div style={{ padding: '16px 20px' }}>
                {/* Status + confidence row */}
                <div style={{ display: 'flex', gap: 12, marginBottom: 18 }}>
                  <div style={{ flex: 1, textAlign: 'center', padding: '14px 10px', background: accentBg, borderRadius: 10, border: `1px solid ${accentBorder}` }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Status</div>
                    <div style={{ fontSize: 20, fontWeight: 900, color: accent }}>{isHealthy ? 'Healthy' : 'Issues'}</div>
                  </div>
                  <div style={{ flex: 1, textAlign: 'center', padding: '14px 10px', background: '#f9fafb', borderRadius: 10, border: '1px solid #e5e7eb' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Confidence</div>
                    <div style={{ fontSize: 20, fontWeight: 900, color: accent }}>{pct}%</div>
                  </div>
                  <div style={{ flex: 1, textAlign: 'center', padding: '14px 10px', background: diseases.length > 0 ? '#fffbeb' : '#f0fdf4', borderRadius: 10, border: `1px solid ${diseases.length > 0 ? '#fde68a' : '#86efac'}` }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Issues</div>
                    <div style={{ fontSize: 20, fontWeight: 900, color: diseases.length > 0 ? '#d97706' : '#16a34a' }}>{diseases.length}</div>
                  </div>
                </div>

                {/* No issues banner */}
                {diseases.length === 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, marginBottom: 12 }}>
                    <Icon path={IC.check} size={13} color='#16a34a' />
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#166534' }}>No diseases or issues detected</span>
                  </div>
                )}

                {/* Disease cards */}
                {diseases.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 800, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                      Detected Issues — click to expand
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {diseases.map((d, i) => <DiseaseCard key={i} disease={d} />)}
                    </div>
                  </div>
                )}

              </div>
            </div>

            {/* Right: Health History */}
            <div style={{ background: '#fff', border: '1.5px solid #e5e7eb', borderRadius: 14, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}>
              {/* Card header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 18px', borderBottom: '1px solid #e5e7eb', background: '#fafafa' }}>
                <div style={{ background: '#f5f3ff', borderRadius: 8, padding: 7, display: 'flex' }}>
                  <Icon path={IC.history} size={14} color='#7c3aed' />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>Health History</div>
                  <div style={{ fontSize: 10, color: T.muted, marginTop: 1 }}>
                    {healthDbHistory?.length || 0} check{healthDbHistory?.length !== 1 ? 's' : ''} recorded
                  </div>
                </div>
              </div>

              {/* Body — no scroll */}
              <div>
                {!healthDbHistory || healthDbHistory.length === 0 ? (
                  <div style={{ padding: '30px', textAlign: 'center', color: T.muted, fontSize: 13 }}>No history yet</div>
                ) : (
                  <>
                    {/* Column headers */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 90px 64px 64px', padding: '9px 20px', background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                      {['Date / Time', 'Status', 'Conf.', 'Issues'].map(h => (
                        <span key={h} style={{ fontSize: 10, fontWeight: 800, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>{h}</span>
                      ))}
                    </div>
                    {/* Rows */}
                    {healthDbHistory.map((e, i) => {
                      const ok = e.is_healthy;
                      const p  = e.health_probability ?? 0;
                      const c  = p >= 70 ? '#16a34a' : p >= 40 ? '#d97706' : '#dc2626';
                      const issueCount = (e.diseases || []).length;
                      return (
                        <div key={i} style={{
                          display: 'grid', gridTemplateColumns: '1fr 90px 64px 64px',
                          padding: '12px 20px', borderBottom: '1px solid #f3f4f6',
                          background: i % 2 === 0 ? '#fff' : '#fafafa',
                          alignItems: 'center',
                        }}>
                          <span style={{ fontSize: 12, color: T.label, fontWeight: 600 }}>
                            {fmtDate(e.created_at)}
                          </span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: 7, height: 7, borderRadius: '50%', background: c, flexShrink: 0 }} />
                            <span style={{ fontSize: 12, fontWeight: 700, color: c }}>
                              {ok ? 'Healthy' : 'Issues'}
                            </span>
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 800, color: c }}>{p}%</span>
                          <span style={{ fontSize: 13, fontWeight: 700, color: issueCount > 0 ? '#d97706' : '#9ca3af' }}>
                            {issueCount}
                          </span>
                        </div>
                      );
                    })}
                  </>
                )}
              </div>
            </div>

          </div>
        </>
      )}


    </div>
  );
}

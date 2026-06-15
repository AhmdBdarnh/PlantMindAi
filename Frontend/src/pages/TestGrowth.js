import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';

// ── Test Growth ────────────────────────────────────────────────────────────────
// Debug/verification page: shows the GROWTH ALGORITHM's detection output images
// (segmentation overlays where the plant is detected) for the last 2 days, so the
// algorithm's plant detection can be checked visually. Read-only; no DB writes.

const CAMS = [
  { key: 'detection_cam1_url', label: 'Camera 1' },
  { key: 'detection_cam2_url', label: 'Camera 2' },
  { key: 'detection_cam3_url', label: 'Camera 3' },
];

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString([], {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return String(iso); }
}

function fmtNum(v, d = 2) {
  if (v == null || isNaN(v)) return '—';
  return Number(v).toFixed(d);
}

function StatusBadge({ status }) {
  const ok = status === 'success';
  return (
    <span style={{
      display: 'inline-block', padding: '3px 11px', borderRadius: 99, fontSize: 12, fontWeight: 700,
      background: ok ? '#dcfce7' : '#fee2e2', color: ok ? '#166534' : '#991b1b',
      border: `1px solid ${ok ? '#86efac' : '#fca5a5'}`,
    }}>
      {ok ? 'DETECTED' : (status || 'ERROR').toUpperCase()}
    </span>
  );
}

function Metric({ label, value, unit }) {
  return (
    <div style={{ background: '#f9fafb', border: '1px solid #f3f4f6', borderRadius: 10, padding: '8px 12px', minWidth: 110 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 800, color: '#111827' }}>
        {value}{value !== '—' && unit ? <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600 }}> {unit}</span> : ''}
      </div>
    </div>
  );
}

export default function TestGrowth() {
  const [items,   setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [lightbox, setLightbox] = useState(null);
  const [failed,   setFailed]   = useState({});

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/growth/history?limit=5`, { cache: 'no-store' });
      const data = await res.json();
      if (data?.success) {
        // Most recent 2 measurements (last 2 days)
        setItems((data.data || data.history || []).slice(0, 2));
      } else {
        setError(data?.error || 'Could not load growth history.');
      }
    } catch (e) {
      setError('Could not reach backend: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '8px 0' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: 'linear-gradient(135deg, #16a34a, #15803d)', borderRadius: 12, padding: 10, display: 'flex' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 3h6m-6 0v5l-5 9a1 1 0 00.9 1.5h14.2a1 1 0 00.9-1.5l-5-9V3m-6 0h6" />
            </svg>
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#111827' }}>Test Growth</h2>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
              Growth-algorithm detection output for the last 2 days — verify the plant is detected correctly
            </div>
          </div>
        </div>
        <button onClick={load} disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 9, border: '1px solid #e5e7eb', background: '#fff', color: '#374151', fontWeight: 700, fontSize: 13, cursor: loading ? 'not-allowed' : 'pointer' }}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 10, padding: '12px 16px', marginBottom: 16, color: '#991b1b', fontSize: 13 }}>
          {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af' }}>
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
          <div style={{ width: 36, height: 36, border: '3px solid #e5e7eb', borderTopColor: '#16a34a', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 14px' }} />
          <div style={{ fontSize: 14 }}>Loading detection output…</div>
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div style={{ background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 16, padding: '56px 32px', textAlign: 'center', color: '#9ca3af' }}>
          No growth analysis has run yet. Capture photos and run growth analysis first, then come back here.
        </div>
      )}

      {/* One card per measurement (last 2 days) */}
      {!loading && items.map((m, i) => {
        const dayLabel = i === 0 ? 'Latest' : 'Previous';
        const detections = CAMS.map(c => ({ ...c, url: m[c.key] }));
        const anyDetection = detections.some(d => d.url);
        return (
          <div key={m.captured_at || i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, padding: '18px 20px', marginBottom: 18 }}>
            {/* Card header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 12, fontWeight: 800, color: '#16a34a', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 99, padding: '3px 11px' }}>{dayLabel}</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: '#111827' }}>{fmtDate(m.captured_at)}</span>
                <StatusBadge status={m.status} />
              </div>
            </div>

            {/* Metrics — what the algorithm measured */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
              <Metric label="Canopy Area" value={fmtNum(m.canopy_area_cm2 ?? m.area_cm2)} unit="cm²" />
              <Metric label="Height" value={fmtNum(m.height_cm)} unit="cm" />
              <Metric label="Width" value={fmtNum(m.width_cm)} unit="cm" />
              <Metric label="Volume" value={fmtNum(m.volume_cm3)} unit="cm³" />
              <Metric label="Growth %" value={m.growth_pct == null ? '—' : fmtNum(m.growth_pct, 1)} unit="%" />
            </div>

            {/* Detection output images (the algorithm's view of the green plant) */}
            <div style={{ fontSize: 11, fontWeight: 800, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
              Detection Output {anyDetection ? '— click to enlarge' : ''}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: 14 }}>
              {detections.map(d => (
                <div key={d.key} style={{ border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden', background: '#f9fafb' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', padding: '7px 10px', borderBottom: '1px solid #f3f4f6' }}>{d.label}</div>
                  {d.url && !failed[d.url] ? (
                    <img src={d.url} alt={`${d.label} detection`} onClick={() => setLightbox(d.url)}
                      onError={() => setFailed(prev => ({ ...prev, [d.url]: true }))}
                      style={{ width: '100%', height: 'auto', display: 'block', cursor: 'zoom-in', objectFit: 'contain', background: '#000' }} />
                  ) : (
                    <div style={{ padding: '60px 12px', textAlign: 'center', color: '#9ca3af', fontSize: 12 }}>
                      {d.url ? 'Image failed to load (link may have expired — click Refresh)' : 'No detection image'}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Growth chart, if present */}
            {m.growth_chart_url && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Growth Chart</div>
                <img src={m.growth_chart_url} alt="Growth chart" onClick={() => setLightbox(m.growth_chart_url)}
                  style={{ maxWidth: '100%', borderRadius: 10, border: '1px solid #e5e7eb', cursor: 'zoom-in' }} />
              </div>
            )}

            {m.status !== 'success' && m.error_message && (
              <div style={{ marginTop: 14, fontSize: 12, color: '#991b1b', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '8px 12px' }}>
                Algorithm error: {m.error_message}
              </div>
            )}
          </div>
        );
      })}

      {/* Lightbox */}
      {lightbox && (
        <div onClick={() => setLightbox(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'zoom-out', padding: 20 }}>
          <img src={lightbox} alt="enlarged" style={{ maxWidth: '95%', maxHeight: '95%', borderRadius: 8 }} />
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts';
import { fmt, fmtNum, fmtDate, fmtDateShort } from '../utils/format';
import { API_BASE_URL } from '../api/config';

// ── Growth metric card ────────────────────────────────────────────────────────

function MetricCard({ label, value, unit, icon, color = 'var(--green)' }) {
  return (
    <div className="sensor-summary-card">
      <div className="sensor-card-header">
        <div className="sensor-card-label">{label}</div>
        <div className="sensor-card-icon-wrap" style={{ background: color + '22' }}>
          <svg viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2"
               strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18 }}>
            <path d={icon} />
          </svg>
        </div>
      </div>
      <div>
        <span className="sensor-card-value">{fmt(value)}</span>
        {unit && <span className="sensor-card-unit" style={{ marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  );
}

// ── Growth history chart ──────────────────────────────────────────────────────

function GrowthChart({ history }) {
  const [activeMetric, setActiveMetric] = useState('area_cm2');

  const successHistory = (history || []).filter(d => d.status === 'success');

  if (successHistory.length === 0) {
    return (
      <div className="loading-state" style={{ minHeight: 160 }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
             style={{ width: 32, height: 32, opacity: .35 }}>
          <path d="M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z"/>
        </svg>
        <span>No history yet — run an analysis to see growth trends</span>
      </div>
    );
  }

  const chartData = [...successHistory]
    .reverse()
    .map(d => ({
      date:       fmtDateShort(d.captured_at),
      area_cm2:   d.area_cm2   != null ? Number(d.area_cm2.toFixed(3))   : null,
      height_cm:  d.height_cm  != null ? Number(d.height_cm.toFixed(3))  : null,
      growth_pct: d.growth_pct != null ? Number(d.growth_pct.toFixed(2)) : null,
    }));

  const METRICS = [
    { key: 'area_cm2',   label: 'Area (cm²)',    color: '#22c55e' },
    { key: 'height_cm',  label: 'Height (cm)',   color: '#3b82f6' },
    { key: 'growth_pct', label: 'Growth %',      color: '#f59e0b' },
  ];

  const active = METRICS.find(m => m.key === activeMetric) || METRICS[0];

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        {METRICS.map(m => (
          <button
            key={m.key}
            onClick={() => setActiveMetric(m.key)}
            style={{
              padding: '4px 14px',
              borderRadius: 20,
              border: `1.5px solid ${activeMetric === m.key ? m.color : 'var(--border)'}`,
              background: activeMetric === m.key ? m.color + '22' : 'transparent',
              color: activeMetric === m.key ? m.color : 'var(--text-muted)',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all .15s',
            }}
          >
            {m.label}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--card-bg)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey={active.key}
            name={active.label}
            stroke={active.color}
            strokeWidth={2.5}
            dot={{ r: 4, fill: active.color }}
            activeDot={{ r: 6 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Growth summary sidebar card ───────────────────────────────────────────────

function GrowthSummaryCard({ g }) {
  const rows = [
    ['Canopy Area',  fmtNum(g.canopy_area_cm2, 3), 'cm²'],
    ['Depth',        fmtNum(g.depth_cm, 3),        'cm'],
    ['Volume',       fmtNum(g.volume_cm3, 3),      'cm³'],
    ['Vol. Growth',  g.vol_growth_pct != null ? fmtNum(g.vol_growth_pct, 2) : 'N/A', '%'],
  ];

  return (
    <div style={{
      background: 'var(--card-bg)', borderRadius: 'var(--r)',
      border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)',
      padding: '20px 24px',
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2" style={{ width: 16, height: 16 }}>
          <path d="M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z"/>
        </svg>
        Growth Summary
      </div>
      {rows.map(([lbl, val, unit]) => (
        <div key={lbl} style={{
          display: 'flex', justifyContent: 'space-between',
          padding: '7px 0', borderBottom: '1px solid var(--border-light)', fontSize: 13,
        }}>
          <span style={{ color: 'var(--text-muted)' }}>{lbl}</span>
          <span style={{ fontWeight: 600 }}>{val} {unit}</span>
        </div>
      ))}
      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
        Source: {g.source_type === 's3' ? 'AWS S3' : 'Camera capture'}
      </div>
    </div>
  );
}

// ── Growth Images Timeline (Tab 2) ───────────────────────────────────────────

const CAMERAS = [
  { id: 1, label: 'Camera 1' },
  { id: 2, label: 'Camera 2' },
  { id: 4, label: 'Camera 3' },   // physical cam ID 4 = display "Camera 3"
];

function fmtDisplayDate(isoDate) {
  // "2026-06-04" → "04 Jun 2026"
  try {
    const d = new Date(isoDate + 'T00:00:00');
    return d.toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return isoDate; }
}

function fmtDisplayTime(isoTs) {
  if (!isoTs) return null;
  try {
    return new Date(isoTs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return null; }
}

function GrowthImagesTab({ growthHistory }) {
  const [sessions,     setSessions]     = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [selectedCam,  setSelectedCam]  = useState(1);
  const [lightbox,     setLightbox]     = useState(null); // url string or null

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE_URL}/capture_sessions?limit=60`, { cache: 'no-store' })
      .then(r => r.json())
      .then(d => { if (d.success) setSessions(d.sessions || []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const MAX_COLS = 4;   // show the last 4 captures

  // Group ALL sessions by local date → pick most-recent session per day
  const sessionByDay = {};
  for (const s of sessions) {
    if (!s.timestamp) continue;
    // timestamp is ISO string: "2026-06-04T14:10:23..."
    const dateKey = s.timestamp.slice(0, 10);
    if (!sessionByDay[dateKey] || s.timestamp > sessionByDay[dateKey].timestamp) {
      sessionByDay[dateKey] = s;
    }
  }

  // Group successful growth measurements by local date → most recent per day.
  // These come from the metrics tab's history (one 3D measurement per analysis run).
  const growthByDay = {};
  for (const m of (growthHistory || [])) {
    if (m.status !== 'success' || !m.captured_at) continue;
    const dateKey = String(m.captured_at).slice(0, 10);
    if (!growthByDay[dateKey] || m.captured_at > growthByDay[dateKey].captured_at) {
      growthByDay[dateKey] = m;
    }
  }

  // Columns = the last MAX_COLS capture dates that actually have data
  // (an image session and/or growth metrics), newest first. This replaces the
  // fixed Today/Yesterday/2-days-ago view so non-consecutive captures
  // (e.g. 19, 18, 16, 14 Jun) all appear with no empty calendar gaps.
  const dayStrings = Array.from(new Set([
    ...Object.keys(sessionByDay),
    ...Object.keys(growthByDay),
  ])).sort((a, b) => (a < b ? 1 : -1)).slice(0, MAX_COLS);

  // Friendly label per column: relative when it lands on today/yesterday,
  // otherwise "Latest" for the newest column and "Capture" for the rest
  // (the exact date is always shown on the line below the label).
  const _ymd = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const _today = _ymd(new Date());
  const _yest  = (() => { const d = new Date(); d.setDate(d.getDate() - 1); return _ymd(d); })();
  const dayLabelFor = (dateStr, idx) =>
    dateStr === _today ? 'Today'
      : dateStr === _yest ? 'Yesterday'
        : idx === 0 ? 'Latest'
          : 'Capture';

  const T = { primary: '#111827', label: '#374151', muted: '#6b7280' };

  return (
    <div>
      {/* ── Camera selector ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          View:
        </span>
        {CAMERAS.map(cam => (
          <button key={cam.id} onClick={() => setSelectedCam(cam.id)} style={{
            padding: '8px 22px', borderRadius: 10, fontWeight: 700, fontSize: 13,
            cursor: 'pointer', transition: 'all 0.13s',
            background: selectedCam === cam.id ? '#111827' : '#fff',
            color:      selectedCam === cam.id ? '#fff'    : T.label,
            border:     selectedCam === cam.id ? '2px solid #111827' : '2px solid #e5e7eb',
            boxShadow:  selectedCam === cam.id ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
          }}>
            {cam.label}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 11, color: T.muted }}>
          Click any image to enlarge
        </span>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '48px', color: T.muted, fontSize: 13 }}>
          Loading capture sessions…
        </div>
      ) : dayStrings.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px', color: T.muted, fontSize: 13 }}>
          No captures yet — run a growth analysis to see photos here.
        </div>
      ) : (
        /* ── last 4 captures (newest first) ── */
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${dayStrings.length}, 1fr)`, gap: 20 }}>
          {dayStrings.map((dateStr, idx) => {
            const session  = sessionByDay[dateStr];
            const image    = session?.images?.find(img => Number(img.camera_id) === selectedCam);
            const hasImage = image?.url && image?.success !== false;
            const camLabel = CAMERAS.find(c => c.id === selectedCam)?.label || '';
            const time     = fmtDisplayTime(session?.timestamp);
            const growth   = growthByDay[dateStr];   // metrics for this day (shared across cameras)

            return (
              <div key={dateStr} style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {/* Day header */}
                <div style={{
                  background: '#111827', borderRadius: '12px 12px 0 0',
                  padding: '12px 16px',
                }}>
                  <div style={{ fontSize: 14, fontWeight: 800, color: '#fff', marginBottom: 2 }}>
                    {dayLabelFor(dateStr, idx)}
                  </div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>
                    {fmtDisplayDate(dateStr)}
                  </div>
                  {time && (
                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 1 }}>
                      {time} · {camLabel}
                    </div>
                  )}
                </div>

                {/* Image area */}
                <div style={{
                  background: '#f1f5f9',
                  border: '1.5px solid #e2e8f0',
                  borderTop: 'none',
                  borderBottom: 'none',
                  overflow: 'hidden',
                  minHeight: 280,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  {hasImage ? (
                    <div
                      onClick={() => setLightbox(image.url)}
                      style={{ width: '100%', cursor: 'zoom-in', lineHeight: 0 }}
                      title="Click to enlarge"
                    >
                      <img
                        src={image.url}
                        alt={`${dayLabelFor(dateStr, idx)} — ${camLabel}`}
                        style={{ width: '100%', display: 'block', objectFit: 'cover' }}
                        onError={e => { e.target.parentElement.style.display = 'none'; }}
                      />
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '32px 20px' }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5"
                        style={{ width: 40, height: 40, margin: '0 auto 10px', display: 'block' }}>
                        <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" strokeLinecap="round"/>
                      </svg>
                      <div style={{ fontSize: 12, color: T.muted, fontWeight: 600 }}>
                        No image for this day
                      </div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                        {session ? `Session found but no ${camLabel} image` : 'No capture session recorded'}
                      </div>
                    </div>
                  )}
                </div>

                {/* Metrics strip — height / width / area for this day */}
                <div style={{
                  background: '#fff',
                  border: '1.5px solid #e2e8f0',
                  borderTop: '1px solid #f1f5f9',
                  borderRadius: '0 0 12px 12px',
                  padding: '12px 14px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: 8,
                }}>
                  {growth ? (
                    [
                      { lbl: 'Height', val: growth.height_cm, unit: 'cm', color: '#3b82f6' },
                      { lbl: 'Width',  val: growth.width_cm,  unit: 'cm', color: '#14b8a6' },
                      { lbl: 'Area',   val: growth.area_cm2,  unit: 'cm²', color: '#22c55e' },
                    ].map(({ lbl, val, unit, color }) => (
                      <div key={lbl} style={{
                        textAlign: 'center', padding: '8px 4px',
                        background: '#f8fafc', borderRadius: 8,
                      }}>
                        <div style={{ fontSize: 9, fontWeight: 700, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 3 }}>
                          {lbl}
                        </div>
                        <div style={{ fontSize: 16, fontWeight: 900, color: val != null ? color : '#cbd5e1', lineHeight: 1 }}>
                          {val != null ? Number(val).toFixed(2) : '—'}
                        </div>
                        {val != null && (
                          <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>{unit}</div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div style={{ gridColumn: '1 / -1', textAlign: 'center', fontSize: 11, color: '#94a3b8', padding: '6px 0' }}>
                      No growth measurement for this day
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Lightbox ─────────────────────────────────────────────────── */}
      {lightbox && (
        <div
          onClick={() => setLightbox(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.92)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'zoom-out', padding: 24,
          }}
        >
          <img
            src={lightbox}
            alt="Enlarged view"
            style={{
              maxWidth: '90vw', maxHeight: '88vh',
              borderRadius: 10, boxShadow: '0 8px 60px rgba(0,0,0,0.5)',
              objectFit: 'contain',
            }}
            onClick={e => e.stopPropagation()}
          />
          <button
            onClick={() => setLightbox(null)}
            style={{
              position: 'fixed', top: 20, right: 24,
              background: 'rgba(255,255,255,0.15)', border: 'none',
              borderRadius: '50%', width: 40, height: 40,
              color: '#fff', fontSize: 20, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >×</button>
        </div>
      )}
    </div>
  );
}

// ── Tab button ────────────────────────────────────────────────────────────────
function GrowthTabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '8px 20px', borderRadius: 10,
      fontWeight: 700, fontSize: 13, cursor: 'pointer', transition: 'all 0.15s',
      background: active ? '#111827' : '#fff',
      color:      active ? '#fff'    : '#374151',
      border:     active ? '2px solid #111827' : '2px solid #e5e7eb',
      boxShadow:  active ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
    }}>{children}</button>
  );
}

// ── Main PlantGrowth component ────────────────────────────────────────────────

export default function PlantGrowth({
  growthLatest,
  growthHistory,
  growthLoading,
  growthAnalyzing,
  growthError,
  captureWaiting,
  onRunGrowthS3,
  onCaptureAndAnalyze,
  onRefreshGrowth,
}) {
  const [activeTab, setActiveTab] = useState('metrics'); // 'metrics' | 'images'
  const g            = growthLatest || {};
  const hasGrowth    = growthLatest && growthLatest.status === 'success';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Page title + tabs ────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', margin: 0, letterSpacing: '-0.3px' }}>
            {activeTab === 'metrics' ? 'Plant Growth Statistics' : 'Plant Growth Photos'}
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '3px 0 0' }}>
            {activeTab === 'metrics' ? 'Growth measurements and analysis results' : 'Visual comparison — Today / Yesterday / 2 Days Ago'}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 5, padding: 5, background: '#f3f4f6', borderRadius: 11 }}>
            <GrowthTabBtn active={activeTab === 'metrics'} onClick={() => setActiveTab('metrics')}>
              📊 Growth Statistics
            </GrowthTabBtn>
            <GrowthTabBtn active={activeTab === 'images'} onClick={() => setActiveTab('images')}>
              🌱 Growth Photos
            </GrowthTabBtn>
          </div>
        </div>
      </div>

      {/* ── Tab 2: Growth Images ─────────────────────────────────────────── */}
      {activeTab === 'images' && <GrowthImagesTab growthHistory={growthHistory} />}

      {/* ── Tab 1: Metrics (everything below only renders in metrics tab) ── */}
      {activeTab === 'metrics' && (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className="btn btn-primary"
            onClick={onCaptureAndAnalyze}
            disabled={growthAnalyzing || captureWaiting}
            title="Capture 3 photos from cameras and run growth analysis"
          >
            {growthAnalyzing ? (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                     className="spin-svg" style={{ width: 13, height: 13 }}>
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" strokeLinecap="round"/>
                </svg>
                Analyzing…
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                     style={{ width: 13, height: 13 }}>
                  <path d="M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z"/>
                </svg>
                Capture &amp; Analyze
              </>
            )}
          </button>

          <button
            className="btn btn-outline"
            onClick={onRunGrowthS3}
            disabled={growthAnalyzing || captureWaiting}
            title="Run growth analysis using the latest photos already in S3"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                 style={{ width: 13, height: 13 }}>
              <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Analyze from S3
          </button>

          <button className="btn btn-outline" onClick={onRefreshGrowth} disabled={growthLoading}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                 style={{ width: 13, height: 13 }}>
              <path d="M1 4v6h6M23 20v-6h-6" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Refresh
          </button>
        </div>

      {/* Capture waiting banner — shown while another capture is running */}
      {captureWaiting && (
        <div style={{
          background: '#fffbeb', border: '1px solid #fbbf24',
          borderRadius: 'var(--r-sm)', padding: '12px 16px',
          fontSize: 13, color: '#92400e', fontWeight: 500,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
               className="spin-svg" style={{ width: 16, height: 16, flexShrink: 0 }}>
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" strokeLinecap="round"/>
          </svg>
          <span>
            <strong>Camera capture is running.</strong> Waiting for it to finish — the page will refresh automatically when it completes.
          </span>
        </div>
      )}

      {/* Growth error banner */}
      {growthError && (
        <div style={{
          background: 'var(--red-light)', border: '1px solid #fecaca',
          borderRadius: 'var(--r-sm)', padding: '12px 16px',
          fontSize: 13, color: '#b91c1c', fontWeight: 500,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
               style={{ width: 15, height: 15, flexShrink: 0 }}>
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          Could not load data right now. {growthError}
        </div>
      )}

      {/* ── No data empty state ─────────────────────────────────────────── */}
      {!growthLatest && !growthLoading && !growthError && (
        <div style={{
          background: 'var(--card-bg)', borderRadius: 'var(--r-lg)',
          border: '1px dashed var(--border)', padding: '60px 40px',
          textAlign: 'center',
        }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="var(--text-light)" strokeWidth="1.5"
               style={{ width: 48, height: 48, margin: '0 auto 16px', display: 'block' }}>
            <path d="M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z"/>
          </svg>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
            No plant growth data available yet
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 360, margin: '0 auto', lineHeight: 1.6 }}>
            Click <strong>Capture &amp; Analyze</strong> to take photos and run a growth analysis,
            or <strong>Analyze from S3</strong> to use existing photos.
          </div>
        </div>
      )}

      {/* ── Content when data exists ─────────────────────────────────────── */}
      {(growthLatest || growthLoading) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20, alignItems: 'start' }}>

          {/* ── Left column ─────────────────────────────────────────────── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Latest growth metrics */}
            <div style={{
              background: 'var(--card-bg)', borderRadius: 'var(--r)',
              border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)',
              padding: '20px 24px',
            }}>
              <div className="section-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                     style={{ width: 18, height: 18 }}>
                  <path d="M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z"/>
                </svg>
                Latest Growth Metrics
                {hasGrowth && (
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
                    {fmtDate(g.captured_at)} · {g.source_type === 's3' ? 'S3' : 'Camera'}
                  </span>
                )}
              </div>

              {growthLoading && !growthLatest && (
                <div className="loading-state" style={{ minHeight: 80 }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                       className="spin-svg" style={{ width: 24, height: 24 }}>
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" strokeLinecap="round"/>
                  </svg>
                  Loading…
                </div>
              )}

              {growthLatest && growthLatest.status === 'error' && (
                <div style={{
                  background: 'var(--red-light)', borderRadius: 'var(--r-sm)',
                  padding: '12px 14px', fontSize: 13, color: '#b91c1c', fontWeight: 500,
                }}>
                  Last analysis failed: {growthLatest.error_message || 'Unknown error'}
                </div>
              )}

              {hasGrowth && (
                <div className="grid-3" style={{ marginTop: 4 }}>
                  <MetricCard
                    label="Area"
                    value={fmtNum(g.area_cm2, 3)}
                    unit="cm²"
                    icon="M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z"
                    color="var(--green)"
                  />
                  <MetricCard
                    label="Height"
                    value={fmtNum(g.height_cm, 3)}
                    unit="cm"
                    icon="M12 2v20M2 12h20"
                    color="var(--blue)"
                  />
                  <MetricCard
                    label="Width"
                    value={fmtNum(g.width_cm, 3)}
                    unit="cm"
                    icon="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"
                    color="var(--teal)"
                  />
                  <MetricCard
                    label="RGR"
                    value={fmtNum(g.rgr, 6)}
                    unit="/day"
                    icon="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    color="var(--amber)"
                  />
                  <MetricCard
                    label="Growth"
                    value={g.growth_pct != null ? fmtNum(g.growth_pct, 2) : 'N/A'}
                    unit="%"
                    icon="M5 10l7-7m0 0l7 7m-7-7v18"
                    color={g.growth_pct >= 0 ? 'var(--green)' : 'var(--red)'}
                  />
                </div>
              )}
            </div>

            {/* Growth chart */}
            <div style={{
              background: 'var(--card-bg)', borderRadius: 'var(--r)',
              border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)',
              padding: '20px 24px',
            }}>
              <div className="section-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                     style={{ width: 18, height: 18 }}>
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
                Growth History
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>
                  {(growthHistory || []).filter(d => d.status === 'success').length} measurement(s)
                </span>
              </div>
              <GrowthChart history={growthHistory} />
            </div>

          </div>

          {/* ── Right column: growth summary ─────────────────────────────── */}
          {hasGrowth && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <GrowthSummaryCard g={g} />

              {/* Quick stats */}
              <div style={{
                background: 'var(--card-bg)', borderRadius: 'var(--r)',
                border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)',
                padding: '20px 24px',
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text)' }}>
                  Last Analysis
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.8 }}>
                  <div>{fmtDate(g.captured_at)}</div>
                  <div style={{ marginTop: 4 }}>
                    Source: <strong>{g.source_type === 's3' ? 'AWS S3' : 'Camera capture'}</strong>
                  </div>
                  {g.plant_count != null && (
                    <div>Plants detected: <strong>{g.plant_count}</strong></div>
                  )}
                </div>
              </div>
            </div>
          )}

        </div>
      )}

      </div>
      )}

    </div>
  );
}

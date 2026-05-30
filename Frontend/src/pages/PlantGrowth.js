import React, { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts';
import { fmt, fmtNum, fmtDate, fmtDateShort } from '../utils/format';

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

// ── Detection image card ───────────────────────────────────────────────────────

function DetectionImageCard({ url, label }) {
  if (!url) return null;
  return (
    <div style={{
      width: '100%',
      background: 'var(--bg)',
      borderRadius: 'var(--r)',
      border: '1px solid var(--border)',
      overflow: 'hidden',
    }}>
      <a href={url} target="_blank" rel="noopener noreferrer" style={{ display: 'block' }}>
        <img
          src={url}
          alt={label}
          style={{ width: '100%', display: 'block', objectFit: 'contain' }}
          onError={e => { e.target.style.display = 'none'; }}
        />
      </a>
      <div style={{
        padding: '8px 12px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 13,
      }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span className="capture-img-s3">Detection result</span>
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
      agr:        d.agr        != null ? Number(d.agr.toFixed(3))        : null,
    }));

  const METRICS = [
    { key: 'area_cm2',   label: 'Area (cm²)',    color: '#22c55e' },
    { key: 'height_cm',  label: 'Height (cm)',   color: '#3b82f6' },
    { key: 'growth_pct', label: 'Growth %',      color: '#f59e0b' },
    { key: 'agr',        label: 'AGR (cm²/day)', color: '#8b5cf6' },
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
  const g            = growthLatest || {};
  const hasGrowth    = growthLatest && growthLatest.status === 'success';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* ── Page title ──────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0, letterSpacing: '-0.4px' }}>
            Plant Growth
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            Growth measurements and analysis results
          </p>
        </div>

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
                    label="AGR"
                    value={fmtNum(g.agr, 4)}
                    unit="cm²/day"
                    icon="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                    color="var(--purple)"
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

            {/* Detection images from latest growth run */}
            {hasGrowth && (g.detection_cam1_url || g.detection_cam2_url || g.detection_cam3_url) && (
              <div style={{
                background: 'var(--card-bg)', borderRadius: 'var(--r)',
                border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)',
                padding: '20px 24px',
              }}>
                <div className="section-title">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                       style={{ width: 18, height: 18 }}>
                    <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" strokeLinecap="round"/>
                  </svg>
                  Detection Results
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <DetectionImageCard url={g.detection_cam1_url} label="cam1 — Side view" />
                  <DetectionImageCard url={g.detection_cam2_url} label="cam2 — Front view" />
                  <DetectionImageCard url={g.detection_cam3_url} label="cam3 — Top-down" />
                </div>
              </div>
            )}

            {/* Growth chart image from growth calculator */}
            {hasGrowth && g.growth_chart_url && (
              <div style={{
                background: 'var(--card-bg)', borderRadius: 'var(--r)',
                border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)',
                padding: '20px 24px',
              }}>
                <div className="section-title">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                       style={{ width: 18, height: 18 }}>
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <polyline points="3 9 9 9 9 21"/>
                  </svg>
                  Growth Chart (Camera Output)
                </div>
                <a href={g.growth_chart_url} target="_blank" rel="noopener noreferrer">
                  <img
                    src={g.growth_chart_url}
                    alt="Growth chart"
                    style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }}
                  />
                </a>
              </div>
            )}

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
  );
}

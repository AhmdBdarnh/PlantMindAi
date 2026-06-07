import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';

// ── Text palette ──────────────────────────────────────────────────────────────
const T = { primary: '#111827', secondary: '#1f2937', label: '#374151', muted: '#6b7280' };

// ── Sensor definitions ────────────────────────────────────────────────────────
const SENSORS = [
  { key: 'air_temperature',  label: 'Air Temperature',  unit: '°C',    color: '#f59e0b', iconBg: '#fef3c7', iconColor: '#d97706', icon: 'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z', spKey: 'temperature',   dec: 1 },
  { key: 'air_humidity',     label: 'Humidity',          unit: '%',     color: '#3b82f6', iconBg: '#eff6ff', iconColor: '#2563eb', icon: 'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',         spKey: 'humidity',       dec: 1 },
  { key: 'soil_temperature', label: 'Root Temperature',  unit: '°C',    color: '#ef4444', iconBg: '#fee2e2', iconColor: '#dc2626', icon: 'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z', spKey: 'soil_temp',    dec: 1 },
  { key: 'soil_humidity',    label: 'Soil Moisture',     unit: '%',     color: '#22c55e', iconBg: '#dcfce7', iconColor: '#16a34a', icon: 'M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z', spKey: 'soil_moisture', dec: 1 },
  { key: 'soil_ec',          label: 'Soil EC',           unit: 'µS/cm', color: '#14b8a6', iconBg: '#f0fdfa', iconColor: '#0d9488', icon: 'M13 10V3L4 14h7v7l9-11h-7z',                            spKey: 'soil_ec',        dec: 0 },
  { key: 'soil_ph',          label: 'Soil pH',           unit: 'pH',    color: '#8b5cf6', iconBg: '#f5f3ff', iconColor: '#7c3aed', icon: 'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18', spKey: 'soil_ph', dec: 2 },
  { key: 'light_intensity',  label: 'Light',             unit: 'lux',   color: '#eab308', iconBg: '#fefce8', iconColor: '#ca8a04', icon: 'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z', spKey: 'light', dec: 0 },
];

// ── VPD calculation ───────────────────────────────────────────────────────────
function calcVPD(tempC, rhPct) {
  if (tempC == null || rhPct == null || isNaN(tempC) || isNaN(rhPct)) return null;
  const svp = 0.6108 * Math.exp(17.27 * tempC / (tempC + 237.3));
  return +((1 - rhPct / 100) * svp).toFixed(3);
}

// ── Sensor status relative to setpoint ───────────────────────────────────────
function sensorStatus(sensor, value, sp) {
  if (value == null || !sp) return 'ok';
  const spVal = sp[sensor.spKey];
  if (spVal == null) return 'ok';
  const diff = Math.abs(value - spVal);
  const threshold = sensor.unit === '°C' ? 3 : sensor.unit === '%' ? 15 : spVal * 0.25;
  if (diff > threshold * 2) return 'danger';
  if (diff > threshold)     return 'warn';
  return 'ok';
}

// ── Tab button (with SVG icon) ────────────────────────────────────────────────
function TabBtn({ active, onClick, iconPath, children }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '8px 20px', borderRadius: 10,
      fontWeight: 700, fontSize: 13, cursor: 'pointer', transition: 'all 0.15s',
      background: active ? '#111827' : '#fff',
      color:      active ? '#fff'    : T.label,
      border:     active ? '2px solid #111827' : '2px solid #e5e7eb',
      boxShadow:  active ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
    }}>
      <svg viewBox="0 0 24 24" fill="none" stroke={active ? '#fff' : T.muted}
        strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ width: 14, height: 14, flexShrink: 0 }}>
        <path d={iconPath} />
      </svg>
      {children}
    </button>
  );
}

// ── Live sensor card ──────────────────────────────────────────────────────────
function SensorCard({ cfg, value, sp }) {
  const status = sensorStatus(cfg, value, sp);
  const SP = {
    ok:     { bg: '#f0fdf4', text: '#15803d', dot: '#16a34a', border: '#86efac' },
    warn:   { bg: '#fef9c3', text: '#92400e', dot: '#d97706', border: '#fde047' },
    danger: { bg: '#fee2e2', text: '#7f1d1d', dot: '#ef4444', border: '#fca5a5' },
  };
  const clr     = SP[status];
  const spVal   = sp?.[cfg.spKey];
  const display = value != null ? Number(value).toFixed(cfg.dec ?? 1) : null;

  return (
    <div style={{
      background: '#fff', borderRadius: 14,
      border: `1.5px solid ${cfg.color}40`,
      boxShadow: display ? `0 2px 12px ${cfg.color}18` : '0 1px 4px rgba(0,0,0,0.06)',
      padding: '16px 18px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: cfg.iconBg, borderRadius: 9, padding: 8, display: 'flex', flexShrink: 0 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke={cfg.iconColor}
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              style={{ width: 16, height: 16 }}>
              <path d={cfg.icon} />
            </svg>
          </div>
          <span style={{ fontSize: 14, fontWeight: 700, color: T.primary }}>{cfg.label}</span>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '4px 10px', borderRadius: 99,
          background: clr.bg, border: `1px solid ${clr.border}`,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: clr.dot }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: clr.text }}>
            {status === 'ok' ? 'OK' : status === 'warn' ? 'WARN' : 'CHECK'}
          </span>
        </div>
      </div>

      {/* Big value */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 42, fontWeight: 900, color: display ? cfg.color : '#d1d5db', lineHeight: 1 }}>
          {display ?? '—'}
        </span>
        {display && <span style={{ fontSize: 16, fontWeight: 600, color: T.muted }}>{cfg.unit}</span>}
      </div>

      {/* Target */}
      {spVal != null && (
        <div style={{ fontSize: 12, color: T.muted }}>
          Target: <b style={{ color: T.primary, fontSize: 13 }}>{spVal} {cfg.unit}</b>
        </div>
      )}
    </div>
  );
}

// ── VPD card ──────────────────────────────────────────────────────────────────
function VPDCard({ vpd }) {
  const ok   = vpd != null && vpd >= 0.4 && vpd <= 1.6;
  const warn = vpd != null && (vpd >= 1.6 || vpd < 0.2);
  const clr  = warn ? { bg: '#fee2e2', text: '#7f1d1d', dot: '#ef4444', border: '#fca5a5' }
             : ok   ? { bg: '#f0fdf4', text: '#15803d', dot: '#16a34a', border: '#86efac' }
                    : { bg: '#fef9c3', text: '#92400e', dot: '#d97706', border: '#fde047' };
  return (
    <div style={{ background: '#fff', borderRadius: 14, border: '1.5px solid #a855f740', padding: '16px 18px', boxShadow: '0 2px 10px #a855f710' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: '#f5f3ff', borderRadius: 9, padding: 8, display: 'flex', flexShrink: 0 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2"
              strokeLinecap="round" style={{ width: 16, height: 16 }}>
              <path d="M2 12h20M12 2v20" />
            </svg>
          </div>
          <span style={{ fontSize: 14, fontWeight: 700, color: T.primary }}>VPD</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 99, background: clr.bg, border: `1px solid ${clr.border}` }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: clr.dot }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: clr.text }}>
            {vpd == null ? '—' : warn ? 'HIGH' : ok ? 'OK' : 'LOW'}
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 8 }}>
        <span style={{ fontSize: 42, fontWeight: 900, color: vpd != null ? '#a855f7' : '#d1d5db', lineHeight: 1 }}>
          {vpd != null ? vpd.toFixed(2) : '—'}
        </span>
        {vpd != null && <span style={{ fontSize: 16, fontWeight: 600, color: T.muted }}>kPa</span>}
      </div>
      <div style={{ fontSize: 12, color: T.muted }}>Optimal range: 0.4 – 1.2 kPa</div>
    </div>
  );
}

// ── 24h chart with axes ───────────────────────────────────────────────────────
function EnvChart({ points, color, unit, liveValue, height = 130 }) {
  if (!points || points.length < 2) {
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#f9fafb', borderRadius: 8,
        fontSize: 12, color: T.muted, fontStyle: 'italic',
      }}>
        No history in database yet
      </div>
    );
  }

  const values = points.map(p => p.value).filter(v => v != null && !isNaN(v));
  if (values.length < 2) return null;

  const min  = Math.min(...values);
  const max  = Math.max(...values);
  const rng  = max - min || 1;
  const avg  = values.reduce((a, b) => a + b, 0) / values.length;

  const W = 500, H = height;
  const padL = 36, padR = 8, padT = 6, padB = 18;
  const iW = W - padL - padR;
  const iH = H - padT - padB;

  const pts = values.map((v, i) => [
    padL + (i / (values.length - 1)) * iW,
    padT + iH - ((v - min) / rng) * iH,
  ]);
  const linePts = pts.map(([x, y]) => `${x},${y}`).join(' ');
  const areaPts = [
    `${pts[0][0]},${padT + iH}`,
    ...pts.map(([x, y]) => `${x},${y}`),
    `${pts[pts.length - 1][0]},${padT + iH}`,
  ].join(' ');
  const gid = `e24-${color.replace('#', '')}-${Math.random().toString(36).slice(2, 6)}`;

  // Time labels
  const fmtT = iso => { try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch { return ''; } };
  const t0   = fmtT(points[0]?.time);
  const tMid = fmtT(points[Math.floor(points.length / 2)]?.time);
  const tEnd = fmtT(points[points.length - 1]?.time);

  // Y-axis ticks
  const yTicks = [max, (max + min) / 2, min];

  return (
    <div>
      {/* Stats bar */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 6, flexWrap: 'wrap' }}>
        {[['Min', min], ['Avg', avg], ['Max', max]].map(([lbl, v]) => (
          <span key={lbl} style={{ fontSize: 11, color: T.muted }}>
            {lbl}: <b style={{ color: T.primary }}>{Number(v).toFixed(1)} {unit}</b>
          </span>
        ))}
        {liveValue != null && (
          <span style={{ marginLeft: 'auto', fontSize: 11, color: T.muted }}>
            Now: <b style={{ color }}>{liveValue} {unit}</b>
          </span>
        )}
      </div>

      {/* SVG chart */}
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height }} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={color} stopOpacity="0.20" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Horizontal grid + Y labels */}
        {yTicks.map((v, i) => {
          const y = padT + iH - ((v - min) / rng) * iH;
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={padL + iW} y2={y}
                stroke="#e5e7eb" strokeWidth="0.6" strokeDasharray="3,3" />
              <text x={padL - 3} y={y + 3.5} textAnchor="end"
                fontSize="7.5" fill="#6b7280" fontFamily="system-ui">
                {Number(v).toFixed(v % 1 === 0 ? 0 : 1)}
              </text>
            </g>
          );
        })}

        {/* Area + line */}
        <polygon fill={`url(#${gid})`} points={areaPts} />
        <polyline fill="none" stroke={color} strokeWidth="1.8"
          strokeLinejoin="round" strokeLinecap="round" points={linePts} />

        {/* Current value dot */}
        <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3.5" fill={color} />

        {/* X-axis labels */}
        {[[t0, padL, 'start'], [tMid, padL + iW / 2, 'middle'], [tEnd, padL + iW, 'end']].map(([lbl, x, anchor], i) => (
          <text key={i} x={x} y={H - 3} textAnchor={anchor}
            fontSize="7.5" fill="#6b7280" fontFamily="system-ui">
            {lbl}
          </text>
        ))}
      </svg>
    </div>
  );
}

// ── Tab 1: Live environment ───────────────────────────────────────────────────
function LiveTab({ sensors, setpoints, lastUpdate }) {
  const s       = sensors || {};
  const sp      = setpoints;
  const vpd     = calcVPD(s.air_temperature, s.air_humidity);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

      {/* Live sensors — 4 columns, 2 rows */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: T.muted, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            Live Sensor Data
          </div>
          {lastUpdate && <span style={{ fontSize: 11, color: T.muted }}>Updated {lastUpdate}</span>}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {SENSORS.map(cfg => <SensorCard key={cfg.key} cfg={cfg} value={s[cfg.key]} sp={sp} />)}
          <VPDCard vpd={vpd} />
        </div>
      </div>

    </div>
  );
}

// ── Tab 2: 24h graphs ─────────────────────────────────────────────────────────
function GraphsTab({ sensors }) {
  const [history, setHistory]   = useState(null);
  const [loading, setLoading]   = useState(true);
  const [fetchedAt, setFetchedAt] = useState(null);

  const fetchHistory = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/sensors/history?hours=24`, { cache: 'no-store' });
      const data = await res.json();
      if (data.success) {
        setHistory(data.data);
        setFetchedAt(new Date().toLocaleTimeString());
      }
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchHistory();
    const id = setInterval(fetchHistory, 60000); // refresh every 60 s
    return () => clearInterval(id);
  }, [fetchHistory]);

  const s = sensors || {};

  return (
    <div>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16,
        padding: '10px 14px', background: '#fff', borderRadius: 10, border: '1.5px solid #e5e7eb',
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>24-Hour Sensor History</div>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>
            Each graph shows readings from the last 24 hours stored in the database
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {fetchedAt && <span style={{ fontSize: 11, color: T.muted }}>Fetched {fetchedAt}</span>}
          <button onClick={fetchHistory} style={{
            padding: '5px 14px', borderRadius: 8, fontSize: 11, fontWeight: 700,
            background: '#fff', color: T.secondary, border: '2px solid #e5e7eb', cursor: 'pointer',
          }}>↻ Refresh</button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: T.muted, fontSize: 13 }}>
          Loading 24h history from database…
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
          {SENSORS.map(cfg => {
            const pts = history?.[cfg.key] || [];
            const live = s[cfg.key] != null ? Number(s[cfg.key]).toFixed(cfg.dec ?? 1) : null;
            return (
              <div key={cfg.key} style={{
                background: '#fff', borderRadius: 12,
                border: `1.5px solid ${cfg.color}30`,
                padding: '14px 16px',
                boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
              }}>
                {/* Chart header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
                  <div style={{ background: cfg.iconBg, borderRadius: 7, padding: 6, display: 'flex', flexShrink: 0 }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke={cfg.iconColor}
                      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                      style={{ width: 13, height: 13 }}>
                      <path d={cfg.icon} />
                    </svg>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>{cfg.label}</span>
                  {live && (
                    <span style={{
                      marginLeft: 'auto', fontSize: 18, fontWeight: 900, color: cfg.color,
                    }}>{live} <span style={{ fontSize: 11, fontWeight: 600, color: T.muted }}>{cfg.unit}</span></span>
                  )}
                </div>
                <EnvChart
                  points={pts}
                  color={cfg.color}
                  unit={cfg.unit}
                  liveValue={live}
                />
                {pts.length > 0 && (
                  <div style={{ fontSize: 10, color: T.muted, marginTop: 6, textAlign: 'right' }}>
                    {pts.length} readings · 24 h window
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function PlantEnvironment({ sensors, sensorHistory, setpoints, lastUpdate }) {
  const [tab, setTab] = useState('live');

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>

      {/* Page header + tabs on same row to save vertical space */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: T.primary }}>
            Plant Environment
          </h2>
          {tab !== 'live' && (
            <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>
              24-hour sensor trends from database
            </div>
          )}
        </div>

        {/* Tab bar — right-aligned in the header row */}
        <div style={{
          display: 'flex', gap: 5,
          padding: 5, background: '#f3f4f6', borderRadius: 11,
        }}>
          <TabBtn
            active={tab === 'live'}
            onClick={() => setTab('live')}
            iconPath='M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'
          >
            Live Environment
          </TabBtn>
          <TabBtn
            active={tab === 'graphs'}
            onClick={() => setTab('graphs')}
            iconPath='M22 12h-4l-3 9L9 3l-3 9H2'
          >
            24h Graphs
          </TabBtn>
        </div>
      </div>

      {/* Tab content */}
      {tab === 'live'
        ? <LiveTab sensors={sensors} setpoints={setpoints} lastUpdate={lastUpdate} />
        : <GraphsTab sensors={sensors} sensorHistory={sensorHistory} />
      }

    </div>
  );
}

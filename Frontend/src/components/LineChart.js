import React from 'react';

/**
 * Lightweight SVG line chart — no external dependencies.
 * Used by PlantEnvironment and ResourceConsumption.
 *
 * Props:
 *   data     — array of objects (sensorHistory entries)
 *   dataKey  — key to read from each entry
 *   color    — stroke + fill colour (#hex)
 *   height   — pixel height of the chart (default 120)
 */
export default function LineChart({ data, dataKey, color, height = 120 }) {
  if (!data || data.length < 2) {
    return <div className="chart-empty">Collecting data…</div>;
  }

  const values = data.map(d => parseFloat(d[dataKey])).filter(v => !isNaN(v));
  if (values.length < 2) return <div className="chart-empty">Collecting data…</div>;

  const min   = Math.min(...values);
  const max   = Math.max(...values);
  const range = max - min || 1;
  const W = 400, H = height;
  const px = 4, py = 6;
  const iW = W - px * 2;
  const iH = H - py * 2;

  const pts = values.map((v, i) => [
    px + (i / (values.length - 1)) * iW,
    py + iH - ((v - min) / range) * iH,
  ]);

  const linePts = pts.map(([x, y]) => `${x},${y}`).join(' ');
  const areaPts = [
    `${pts[0][0]},${py + iH}`,
    ...pts.map(([x, y]) => `${x},${y}`),
    `${pts[pts.length - 1][0]},${py + iH}`,
  ].join(' ');

  const gid = `lc-${dataKey}-${color.replace('#', '')}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="line-chart-full"
      preserveAspectRatio="none"
      style={{ height }}
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0"    />
        </linearGradient>
      </defs>
      <polygon fill={`url(#${gid})`} points={areaPts} />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={linePts}
      />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3" fill={color} />
    </svg>
  );
}

/**
 * Optional min/avg/max stats row shown below a LineChart.
 * Usage: <ChartStats data={sensorHistory} dataKey="air_temperature" />
 */
export function ChartStats({ data, dataKey }) {
  const values = (data || []).map(d => parseFloat(d[dataKey])).filter(v => !isNaN(v));
  if (values.length === 0) return null;
  const min = Math.min(...values).toFixed(1);
  const max = Math.max(...values).toFixed(1);
  const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
  return (
    <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
      {[['Min', min], ['Avg', avg], ['Max', max]].map(([lbl, val]) => (
        <div key={lbl} style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ fontWeight: 600, color: 'var(--text)' }}>{val}</span> {lbl}
        </div>
      ))}
    </div>
  );
}

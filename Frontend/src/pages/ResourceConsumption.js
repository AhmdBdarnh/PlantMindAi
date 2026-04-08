import React from 'react';

/* ── SVG Line chart ── */
function LineChart({ data, dataKey, color, height = 120 }) {
  if (!data || data.length < 2) {
    return <div className="chart-empty">Collecting data…</div>;
  }
  const values = data.map(d => parseFloat(d[dataKey])).filter(v => !isNaN(v));
  if (values.length < 2) return <div className="chart-empty">Collecting data…</div>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 500, H = height;
  const px = 4, py = 6;
  const iW = W - px * 2, iH = H - py * 2;

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

  const gid = `g-${dataKey}`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="line-chart-full" preserveAspectRatio="none" style={{ height }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0"   />
        </linearGradient>
      </defs>
      <polygon fill={`url(#${gid})`} points={areaPts} />
      <polyline fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" points={linePts} />
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="3" fill={color} />
    </svg>
  );
}

const fmt  = (v, dec = 2) => (v !== undefined && v !== null ? Number(v).toFixed(dec) : 'N/A');
const fmtN = v => (v !== undefined && v !== null ? v : 'N/A');

function MetricBox({ label, value, unit, big }) {
  return (
    <div className="resource-metric">
      <div className="resource-metric-label">{label}</div>
      <div className="resource-metric-value" style={big ? { fontSize: 36 } : {}}>
        {value !== undefined && value !== null ? value : <span className="na">N/A</span>}
        {unit && value !== undefined && value !== null && (
          <span className="resource-metric-unit">{unit}</span>
        )}
      </div>
    </div>
  );
}

export default function ResourceConsumption({ sensors, sensorHistory }) {
  const s = sensors || {};

  const energyKwh = s.energy !== undefined && s.energy !== null
    ? (parseFloat(s.energy) / 1000).toFixed(3)
    : null;

  return (
    <div>
      {/* ── Electricity ── */}
      <div className="resource-big-card page-section">
        <div className="resource-section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
          Electricity Consumption
          <span className="status-badge status-badge-amber" style={{ marginLeft: 'auto', fontWeight: 600 }}>
            Live
          </span>
        </div>

        <div className="resource-metrics">
          <MetricBox label="Power"        value={fmtN(s.power)}     unit="W"   big />
          <MetricBox label="Energy (Total)" value={fmtN(s.energy)}  unit="Wh"  />
          <MetricBox label="Energy (kWh)"  value={energyKwh}        unit="kWh" />
          <MetricBox label="Voltage"       value={fmtN(s.voltage)}  unit="V"   />
          <MetricBox label="Current"       value={fmtN(s.current)}  unit="A"   />
          <MetricBox label="Frequency"     value={fmtN(s.frequency)}unit="Hz"  />
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
            Power (W) over time
          </div>
          <LineChart data={sensorHistory} dataKey="power" color="#f59e0b" height={110} />
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
            Energy accumulated (Wh)
          </div>
          <LineChart data={sensorHistory} dataKey="energy" color="#ef4444" height={100} />
        </div>
      </div>

      {/* ── Water ── */}
      <div className="resource-big-card page-section">
        <div className="resource-section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z"/>
          </svg>
          Water Consumption
          <span className="status-badge status-badge-blue" style={{ marginLeft: 'auto', fontWeight: 600 }}>
            Live
          </span>
        </div>

        <div className="resource-metrics">
          <MetricBox label="Flow Rate"    value={fmtN(s.water_flow)}   unit="L/min" big />
          <MetricBox label="Total Volume" value={fmtN(s.water_amount)} unit="L"     />
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
            Flow rate (L/min) over time
          </div>
          <LineChart data={sensorHistory} dataKey="water_flow" color="#3b82f6" height={110} />
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
            Water amount accumulated (L)
          </div>
          <LineChart data={sensorHistory} dataKey="water_amount" color="#06b6d4" height={100} />
        </div>
      </div>
    </div>
  );
}

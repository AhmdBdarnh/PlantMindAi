import React, { useState, useEffect } from 'react';

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

function CostBadge({ value }) {
  if (value === undefined || value === null) return <span className="na">N/A</span>;
  return <span style={{ color: '#16a34a', fontWeight: 700 }}>₪{Number(value).toFixed(4)}</span>;
}

function PumpLogs() {
  const [logs, setLogs]       = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch_logs = () => {
      fetch('/api/pump-logs?limit=50')
        .then(r => r.json())
        .then(d => { if (d.success) setLogs(d.logs || []); })
        .catch(() => {})
        .finally(() => setLoading(false));
    };
    fetch_logs();
    const id = setInterval(fetch_logs, 30000);
    return () => clearInterval(id);
  }, []);

  const fmtTime = iso => {
    if (!iso) return 'N/A';
    const d = new Date(iso);
    return d.toLocaleString();
  };

  const waterLogs      = logs.filter(l => l.pump === 'water');
  const fertLogs       = logs.filter(l => l.pump === 'fertilizer');
  const lastWater      = waterLogs[0];
  const lastFert       = fertLogs[0];

  return (
    <div className="resource-big-card page-section">
      <div className="resource-section-title">
        <svg viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
          <rect x="9" y="3" width="6" height="4" rx="1"/>
          <path d="M9 12h6M9 16h4"/>
        </svg>
        Pump Activity Log
        <span className="status-badge status-badge-blue" style={{ marginLeft: 'auto', fontWeight: 600 }}>Auto-refresh 30s</span>
      </div>

      {loading ? (
        <div className="chart-empty">Loading logs…</div>
      ) : logs.length === 0 ? (
        <div className="chart-empty">No pump events recorded yet.</div>
      ) : (
        <>
          {/* Last activation summary */}
          <div className="resource-metrics" style={{ marginBottom: 16 }}>
            <div className="resource-metric">
              <div className="resource-metric-label">Last Water Pump</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#3b82f6' }}>
                {lastWater ? fmtTime(lastWater.timestamp) : 'Never'}
              </div>
              {lastWater && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {lastWater.pulse_sec}s pulse · {Math.round((lastWater.duty_cycle / 4095) * 100)}% power
                  {lastWater.flow_rate_l_min > 0 && ` · ${lastWater.flow_rate_l_min} L/min`}
                </div>
              )}
            </div>
            <div className="resource-metric">
              <div className="resource-metric-label">Last Fertilizer Pump</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#16a34a' }}>
                {lastFert ? fmtTime(lastFert.timestamp) : 'Never'}
              </div>
              {lastFert && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {lastFert.pulse_sec}s pulse · {Math.round((lastFert.duty_cycle / 4095) * 100)}% power
                  {lastFert.flow_rate_l_min > 0 && ` · ${lastFert.flow_rate_l_min} L/min`}
                </div>
              )}
            </div>
            <div className="resource-metric">
              <div className="resource-metric-label">Water Activations</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#3b82f6' }}>{waterLogs.length}</div>
            </div>
            <div className="resource-metric">
              <div className="resource-metric-label">Fertilizer Activations</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#16a34a' }}>{fertLogs.length}</div>
            </div>
          </div>

          {/* Full event table */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {['Time', 'Pump', 'Duration', 'Power', 'Flow Rate'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => {
                  const isWater = log.pump === 'water';
                  const color   = isWater ? '#3b82f6' : '#16a34a';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'transparent' : 'var(--surface)' }}>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontSize: 12 }}>{fmtTime(log.timestamp)}</td>
                      <td style={{ padding: '7px 10px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontWeight: 600, color }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
                          {isWater ? 'Water' : 'Fertilizer'}
                        </span>
                      </td>
                      <td style={{ padding: '7px 10px' }}>{log.pulse_sec}s</td>
                      <td style={{ padding: '7px 10px' }}>{Math.round((log.duty_cycle / 4095) * 100)}%</td>
                      <td style={{ padding: '7px 10px' }}>
                        {log.flow_rate_l_min > 0 ? `${log.flow_rate_l_min} L/min` : <span style={{ color: 'var(--text-light)' }}>—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function ResourceConsumption({ sensors, sensorHistory }) {
  const s = sensors || {};

  const energyKwh = s.energy !== undefined && s.energy !== null
    ? (parseFloat(s.energy) / 1000).toFixed(3)
    : null;

  const totalCost = s.total_cost_nis !== undefined && s.total_cost_nis !== null
    ? Number(s.total_cost_nis).toFixed(4)
    : null;

  return (
    <div>

      {/* ── Total Cost Summary ── */}
      <div className="resource-big-card page-section">
        <div className="resource-section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
            <path d="M12 6v12M8 9h8M8 15h8"/>
          </svg>
          Total Resource Cost (₪)
        </div>
        <div className="resource-metrics">
          <MetricBox label="Electricity Cost" value={<CostBadge value={s.electricity_cost_nis} />} />
          <MetricBox label="Water Cost"        value={<CostBadge value={s.water_cost_nis} />} />
          <MetricBox label="Fertilizer Cost"   value={<CostBadge value={s.fertilizer_cost_nis} />} />
          <MetricBox label="Total Cost" big
            value={totalCost !== null ? <span style={{ color: '#16a34a', fontWeight: 800 }}>₪{totalCost}</span> : <span className="na">N/A</span>}
          />
        </div>
      </div>

      {/* ── Electricity ── */}
      <div className="resource-big-card page-section">
        <div className="resource-section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
          </svg>
          Electricity Consumption
          <span className="status-badge status-badge-amber" style={{ marginLeft: 'auto', fontWeight: 600 }}>Live</span>
        </div>

        <div className="resource-metrics">
          <MetricBox label="Power"            value={fmtN(s.power)}       unit="W"   big />
          <MetricBox label="Energy (Total)"   value={fmtN(s.energy)}      unit="Wh"  />
          <MetricBox label="Energy (kWh)"     value={energyKwh}            unit="kWh" />
          <MetricBox label="Cost"             value={<CostBadge value={s.electricity_cost_nis} />} />
          <MetricBox label="Voltage"          value={fmtN(s.voltage)}      unit="V"   />
          <MetricBox label="Current"          value={fmtN(s.current)}      unit="A"   />
          <MetricBox label="Frequency"        value={fmtN(s.frequency)}    unit="Hz"  />
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Power (W) over time</div>
          <LineChart data={sensorHistory} dataKey="power"  color="#f59e0b" height={110} />
        </div>
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Energy accumulated (Wh)</div>
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
          <span className="status-badge status-badge-blue" style={{ marginLeft: 'auto', fontWeight: 600 }}>Live</span>
        </div>

        <div className="resource-metrics">
          <MetricBox label="Flow Rate"    value={fmtN(s.water_flow)}   unit="L/min" big />
          <MetricBox label="Total Volume" value={fmtN(s.water_amount)} unit="L"     />
          <MetricBox label="Cost"         value={<CostBadge value={s.water_cost_nis} />} />
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Flow rate (L/min) over time</div>
          <LineChart data={sensorHistory} dataKey="water_flow"   color="#3b82f6" height={110} />
        </div>
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Water amount accumulated (L)</div>
          <LineChart data={sensorHistory} dataKey="water_amount" color="#06b6d4" height={100} />
        </div>
      </div>

      {/* ── Fertilizer ── */}
      <div className="resource-big-card page-section">
        <div className="resource-section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
            <path d="M8 12h8M12 8v8"/>
          </svg>
          Fertilizer Consumption
          <span className="status-badge status-badge-green" style={{ marginLeft: 'auto', fontWeight: 600 }}>Live</span>
        </div>

        <div className="resource-metrics">
          <MetricBox label="Flow Rate"    value={fmtN(s.fertilizer_flow)}   unit="L/min" big />
          <MetricBox label="Total Volume" value={fmtN(s.fertilizer_amount)} unit="L"     />
          <MetricBox label="Cost"         value={<CostBadge value={s.fertilizer_cost_nis} />} />
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Flow rate (L/min) over time</div>
          <LineChart data={sensorHistory} dataKey="fertilizer_flow"   color="#16a34a" height={110} />
        </div>
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Fertilizer amount accumulated (L)</div>
          <LineChart data={sensorHistory} dataKey="fertilizer_amount" color="#84cc16" height={100} />
        </div>
      </div>

      {/* ── Pump Activity Log ── */}
      <PumpLogs />

    </div>
  );
}

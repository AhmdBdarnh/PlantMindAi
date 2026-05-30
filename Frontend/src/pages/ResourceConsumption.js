import React, { useState, useEffect } from 'react';
import LineChart from '../components/LineChart';
import { API_BASE_URL } from '../api/config';

const fmtN = v => (v !== undefined && v !== null ? v : 'N/A');

// ── New Plant Cycle reset button + confirmation modal ─────────────────────────
function NewCycleButton({ onNewCycle }) {
  const [confirm,  setConfirm]  = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [result,   setResult]   = useState(null);   // {ok: bool, msg: string}

  const handleConfirm = async () => {
    setLoading(true);
    setResult(null);
    const data = await onNewCycle();
    setLoading(false);
    setConfirm(false);
    if (data.success) {
      setResult({ ok: true,  msg: data.message || 'New plant cycle started. All counters reset to zero.' });
    } else {
      setResult({ ok: false, msg: data.error  || 'Reset failed — check backend logs.' });
    }
  };

  return (
    <>
      {/* Result banner */}
      {result && (
        <div style={{
          marginBottom: 16, padding: '10px 16px', borderRadius: 8,
          background: result.ok ? '#dcfce7' : '#fee2e2',
          border: `1px solid ${result.ok ? '#86efac' : '#fca5a5'}`,
          color: result.ok ? '#166534' : '#991b1b',
          fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          {result.msg}
          <button onClick={() => setResult(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'inherit' }}>✕</button>
        </div>
      )}

      {/* Trigger button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <button
          onClick={() => setConfirm(true)}
          style={{
            padding: '7px 18px', borderRadius: 8,
            border: '1px solid #d97706', background: '#fff7ed',
            color: '#92400e', fontWeight: 700, fontSize: 13, cursor: 'pointer',
          }}
        >
          🌱 Start New Plant Cycle
        </button>
      </div>

      {/* Confirmation modal */}
      {confirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 28, maxWidth: 460, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 17, color: '#111827' }}>Start New Plant Cycle?</h3>
            <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.7, margin: '0 0 14px' }}>
              This will reset only resource and cost counters for a new plant cycle.
              Historical sensor, pump, actuator, image, and decision records will be preserved.
            </p>
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '10px 14px', marginBottom: 14, fontSize: 12, color: '#166534' }}>
              <strong>What resets to zero:</strong>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                <li>Water / Fertilizer / Energy cumulative totals</li>
                <li>All cost counters (₪)</li>
                <li>Today's daily budget baseline</li>
                <li>Active Layer 3 runtime constraints</li>
                <li>Pending Layer 3 decisions (marked cancelled — kept as history)</li>
              </ul>
            </div>
            <div style={{ background: '#fef9c3', border: '1px solid #fde047', borderRadius: 8, padding: '10px 14px', marginBottom: 18, fontSize: 12, color: '#854d0e' }}>
              <strong>What is fully preserved:</strong> sensors_data, pump_logs, actuators_data, resources, plant_images,
              AI recommendations, Layer 3 decision history, plant health results, growth measurements,
              setpoints, budget config, camera calibration, all hardware control loops.
            </div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setConfirm(false)}
                style={{ padding: '8px 20px', borderRadius: 8, border: '1px solid #d1d5db', background: '#fff', fontSize: 13, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={loading}
                style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: loading ? '#d97706aa' : '#d97706', color: '#fff', fontWeight: 700, fontSize: 13, cursor: loading ? 'not-allowed' : 'pointer' }}
              >
                {loading ? 'Resetting…' : 'Yes, Start New Cycle'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

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
      fetch(`${API_BASE_URL}/pump-logs?limit=50`)
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

export default function ResourceConsumption({ sensors, sensorHistory, onNewCycle }) {
  const s = sensors || {};

  const energyKwh = s.energy !== undefined && s.energy !== null
    ? (parseFloat(s.energy) / 1000).toFixed(3)
    : null;

  const totalCost = s.total_cost_nis !== undefined && s.total_cost_nis !== null
    ? Number(s.total_cost_nis).toFixed(4)
    : null;

  return (
    <div>

      {/* ── New Plant Cycle button ── */}
      {onNewCycle && <NewCycleButton onNewCycle={onNewCycle} />}

      {/* ── Total Cost Summary ── */}
      <div className="resource-big-card page-section">
        <div className="resource-section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
            <path d="M12 6v12M8 9h8M8 15h8"/>
          </svg>
          Total Cost Since Reset (cumulative)
        </div>
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12, padding: '6px 0', borderBottom: '1px solid #f3f4f6' }}>
          Cumulative resource cost since the last plant cycle reset. Resets to zero when a new cycle starts.
          For today's cost relative to your daily budget, see the <strong>Budget Manager</strong> page.
        </div>
        <div className="resource-metrics">
          <MetricBox label="Electricity Cost (since reset)" value={<CostBadge value={s.electricity_cost_nis} />} />
          <MetricBox label="Water Cost (since reset)"        value={<CostBadge value={s.water_cost_nis} />} />
          <MetricBox label="Fertilizer Cost (since reset)"   value={<CostBadge value={s.fertilizer_cost_nis} />} />
          <MetricBox label="Total Cost (since reset)" big
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
          <MetricBox label="Energy (Total)"         value={fmtN(s.energy)}      unit="Wh"  />
          <MetricBox label="Energy (kWh)"           value={energyKwh}            unit="kWh" />
          <MetricBox label="Cost (since reset)"     value={<CostBadge value={s.electricity_cost_nis} />} />
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
          <MetricBox label="Flow Rate"              value={fmtN(s.water_flow)}   unit="L/min" big />
          <MetricBox label="Total Volume (since reset)" value={fmtN(s.water_amount)} unit="L"     />
          <MetricBox label="Cost (since reset)"     value={<CostBadge value={s.water_cost_nis} />} />
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
          <MetricBox label="Flow Rate"              value={fmtN(s.fertilizer_flow)}   unit="L/min" big />
          <MetricBox label="Total Volume (since reset)" value={fmtN(s.fertilizer_amount)} unit="L"     />
          <MetricBox label="Cost (since reset)"     value={<CostBadge value={s.fertilizer_cost_nis} />} />
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

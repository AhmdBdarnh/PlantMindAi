import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';

// ── Text palette ──────────────────────────────────────────────────────────────
const T = { primary: '#111827', secondary: '#1f2937', label: '#374151', muted: '#6b7280' };

// ── SVG icon helper ───────────────────────────────────────────────────────────
function Icon({ path, size = 16, color = 'currentColor', sw = 2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const IC = {
  water:      'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
  electric:   'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  fertilizer: 'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2v-4M9 21H5a2 2 0 01-2-2v-4m0 0h18',
  total:      'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  leaf:       'M17 8C8 10 5.9 16.17 3.82 19c3.15.6 6.41-.34 8.68-2.61 2.56-2.56 3.07-6.44 1.5-9.39zm0 0c-.2 4.17-2.69 7.78-6 10',
  reset:      'M1 4v6h6M23 20v-6h-6M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15',
  check:      'M5 13l4 4L19 7',
  info:       'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  pump:       'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 3h6a1 1 0 010 2H9a1 1 0 010-2zM9 12h6M9 16h4',
  calendar:   'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  history:    'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
};

// ── Date formatters ───────────────────────────────────────────────────────────
const fmtTableTime = iso => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch { return iso; }
};

// ── Tab button ────────────────────────────────────────────────────────────────
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
      <Icon path={iconPath} size={14} color={active ? '#fff' : T.muted} />
      {children}
    </button>
  );
}

// ── Section divider ───────────────────────────────────────────────────────────
function SectionLabel({ children, sub }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 10, fontWeight: 800, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        {children}
      </div>
      {sub && <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

// ── Resource summary card ─────────────────────────────────────────────────────
function ResourceCard({ icon, iconBg, iconColor, title, amount, amountUnit, cost, accent, tag }) {
  const hasData = amount != null && amount !== 'N/A';
  return (
    <div style={{
      background: '#fff', borderRadius: 14,
      border: `1.5px solid ${accent}30`,
      padding: '16px 18px',
      boxShadow: `0 2px 10px ${accent}10`,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ background: iconBg, borderRadius: 9, padding: 8, display: 'flex' }}>
            <Icon path={icon} size={16} color={iconColor} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>{title}</span>
        </div>
        {tag && (
          <span style={{
            fontSize: 9, fontWeight: 800, padding: '2px 8px', borderRadius: 99,
            background: accent + '18', color: accent,
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>{tag}</span>
        )}
      </div>

      {/* Amount */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
          Total Used
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
          <span style={{ fontSize: 28, fontWeight: 900, color: hasData ? accent : '#d1d5db', lineHeight: 1 }}>
            {hasData ? amount : '—'}
          </span>
          {hasData && <span style={{ fontSize: 13, fontWeight: 600, color: T.muted }}>{amountUnit}</span>}
        </div>
      </div>

      {/* Cost */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '7px 11px', borderRadius: 8,
        background: accent + '0c', border: `1px solid ${accent}20`,
      }}>
        <span style={{ fontSize: 11, color: T.label, fontWeight: 600 }}>Cost</span>
        <span style={{ fontSize: 15, fontWeight: 800, color: accent }}>
          {cost != null ? `₪${cost}` : '—'}
        </span>
      </div>
    </div>
  );
}

// ── Total cost card ───────────────────────────────────────────────────────────
function TotalCostCard({ cost, waterCost, fertCost, elecCost, tag }) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #111827, #1f2937)',
      borderRadius: 14, padding: '16px 18px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 9, padding: 8, display: 'flex' }}>
            <Icon path={IC.total} size={16} color='#fff' />
          </div>
          <span style={{ fontSize: 13, fontWeight: 800, color: '#fff' }}>Total Cost</span>
        </div>
        {tag && (
          <span style={{ fontSize: 9, fontWeight: 800, padding: '2px 8px', borderRadius: 99, background: 'rgba(255,255,255,0.15)', color: '#fff', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            {tag}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginBottom: 12 }}>
        <span style={{ fontSize: 32, fontWeight: 900, color: cost != null ? '#fff' : '#4b5563', lineHeight: 1 }}>
          {cost != null ? `₪${cost}` : '—'}
        </span>
      </div>

      {[['Water', waterCost, '#60a5fa'], ['Fertilizer', fertCost, '#4ade80'], ['Electricity', elecCost, '#fbbf24']].map(([lbl, v, c]) => (
        <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>{lbl}</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: v != null ? c : '#4b5563' }}>
            {v != null ? `₪${v}` : '—'}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── New Plant Cycle button (trigger + confirmation modal only, no result banner)
function NewCycleButton({ onNewCycle }) {
  const [confirm, setConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    setLoading(true);
    await onNewCycle();   // result banner is handled by parent
    setLoading(false);
    setConfirm(false);
  };

  return (
    <>
      <button onClick={() => setConfirm(true)} style={{
        display: 'flex', alignItems: 'center', gap: 7,
        padding: '8px 14px', borderRadius: 10, border: '1.5px solid #d97706',
        background: '#fff7ed', color: '#92400e', fontWeight: 700, fontSize: 12,
        cursor: 'pointer', flexShrink: 0,
      }}>
        <Icon path={IC.leaf} size={13} color='#d97706' />
        Start New Plant Cycle
      </button>

      {confirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 28, maxWidth: 460, width: '90%', boxShadow: '0 25px 60px rgba(0,0,0,0.3)' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 17, color: T.primary }}>Start New Plant Cycle?</h3>
            <p style={{ fontSize: 13, color: T.label, lineHeight: 1.7, margin: '0 0 12px' }}>
              Resets all resource and cost counters to zero. All historical data is preserved.
            </p>
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '10px 14px', marginBottom: 12, fontSize: 12, color: '#166534' }}>
              <strong>Resets:</strong> Water · Fertilizer · Energy totals · All cost counters · Layer 3 decisions
            </div>
            <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '10px 14px', marginBottom: 18, fontSize: 12, color: '#854d0e' }}>
              <strong>Preserved:</strong> All sensor history, pump logs, images, AI recommendations, setpoints.
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirm(false)} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 600 }}>Cancel</button>
              <button onClick={handleConfirm} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 18px', borderRadius: 8, border: 'none', background: loading ? '#fbbf24' : '#d97706', color: '#fff', fontWeight: 700, fontSize: 13, cursor: loading ? 'not-allowed' : 'pointer' }}>
                <Icon path={IC.reset} size={13} color='#fff' />
                {loading ? 'Resetting…' : 'Yes, Start New Cycle'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Tab 1: Summary ────────────────────────────────────────────────────────────
// Receives all shared data from parent — no internal fetches, no duplicate sources.
function SummaryTab({ sensors, prices, daily, cycleStart }) {
  const s = sensors || {};

  // All number formatting uses the SAME prices object that came from the backend
  const f4  = v => v != null ? Number(v).toFixed(4) : null;
  const fL  = v => v != null ? Number(v).toFixed(3) : null;
  const fKwh = v => v != null ? (Number(v) / 1000).toFixed(3) : null;

  // Cumulative totals (from the sensors prop — already calculated by backend
  // using the same prices stored in resource-prices endpoint)
  const cum = {
    water:  fL(s.water_amount),
    fert:   fL(s.fertilizer_amount),
    elec:   fKwh(s.energy),
    wCost:  f4(s.water_cost_nis),
    fCost:  f4(s.fertilizer_cost_nis),
    eCost:  f4(s.electricity_cost_nis),
    total:  f4(s.total_cost_nis),
  };

  // Daily totals (from backend get_today_costs — same prices, consistent)
  const tod = daily ? {
    water:  fL(daily.water_liters_today),
    fert:   fL(daily.fertilizer_liters_today),
    elec:   fKwh(daily.energy_wh_today),
    wCost:  f4(daily.water_cost_nis),
    fCost:  f4(daily.fertilizer_cost_nis),
    eCost:  f4(daily.electricity_cost_nis),
    total:  f4(daily.total_cost_nis),
  } : null;

  // "Counting from" — show real date/time or clear message
  const cycleLabel = cycleStart
    ? (() => {
        try {
          return new Date(cycleStart).toLocaleString([], {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
          });
        } catch { return cycleStart; }
      })()
    : null;

  const cycleSubtitle = cycleLabel
    ? `Counting from: ${cycleLabel}`
    : 'Counting from: — (click "Start New Plant Cycle" to record start date)';

  // Today's date label
  const todayLabel = (() => {
    try {
      return new Date().toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    } catch { return new Date().toISOString().slice(0, 10); }
  })();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Section A: Cycle totals ───────────────────────────────────────── */}
      <div>
        <SectionLabel sub={cycleSubtitle}>
          Total since plant cycle started
        </SectionLabel>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <ResourceCard icon={IC.water}      iconBg='#dbeafe' iconColor='#1d4ed8' accent='#2563eb'
            title="Water" amount={cum.water} amountUnit="L" cost={cum.wCost} tag="Cycle" />
          <ResourceCard icon={IC.fertilizer} iconBg='#dcfce7' iconColor='#15803d' accent='#16a34a'
            title="Fertilizer" amount={cum.fert} amountUnit="L" cost={cum.fCost} tag="Cycle" />
          <ResourceCard icon={IC.electric}   iconBg='#fef3c7' iconColor='#92400e' accent='#ca8a04'
            title="Electricity" amount={cum.elec} amountUnit="kWh" cost={cum.eCost} tag="Cycle" />
          <TotalCostCard cost={cum.total} waterCost={cum.wCost} fertCost={cum.fCost} elecCost={cum.eCost} tag="Cycle" />
        </div>
      </div>

      {/* ── Section B: Daily ─────────────────────────────────────────────── */}
      <div>
        <SectionLabel sub={`Today — ${todayLabel}`}>
          Daily usage
        </SectionLabel>
        {tod ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <ResourceCard icon={IC.water}      iconBg='#dbeafe' iconColor='#1d4ed8' accent='#0ea5e9'
              title="Water" amount={tod.water} amountUnit="L" cost={tod.wCost} tag="Daily" />
            <ResourceCard icon={IC.fertilizer} iconBg='#dcfce7' iconColor='#15803d' accent='#10b981'
              title="Fertilizer" amount={tod.fert} amountUnit="L" cost={tod.fCost} tag="Daily" />
            <ResourceCard icon={IC.electric}   iconBg='#fef3c7' iconColor='#92400e' accent='#f59e0b'
              title="Electricity" amount={tod.elec} amountUnit="kWh" cost={tod.eCost} tag="Daily" />
            <TotalCostCard cost={tod.total} waterCost={tod.wCost} fertCost={tod.fCost} elecCost={tod.eCost} tag="Daily" />
          </div>
        ) : (
          <div style={{ fontSize: 12, color: T.muted, padding: '16px', background: '#f9fafb', borderRadius: 10, textAlign: 'center' }}>
            Loading daily totals…
          </div>
        )}
      </div>

      {/* ── Section C: Live electricity ────────────────────────────────────── */}
      <div>
        <SectionLabel>Live electricity readings</SectionLabel>
        <div style={{
          background: '#fff', borderRadius: 12, border: '1.5px solid #fde68a',
          padding: '14px 20px',
          display: 'flex', alignItems: 'center', gap: 30, flexWrap: 'wrap',
        }}>
          {[
            ['Power',       s.power,       'W'],
            ['Voltage',     s.voltage,     'V'],
            ['Current',     s.current,     'A'],
            ['Frequency',   s.frequency,   'Hz'],
            ['Energy',      s.energy,      'Wh'],
            ['Power Factor',s.power_factor,''],
          ].map(([lbl, val, unit]) => (
            <div key={lbl} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: T.muted, marginBottom: 4, fontWeight: 600 }}>{lbl}</div>
              <div style={{ fontSize: 18, fontWeight: 900, color: val != null ? '#92400e' : '#d1d5db', lineHeight: 1 }}>
                {val != null ? val : '—'}
              </div>
              {val != null && unit && <div style={{ fontSize: 10, color: T.muted, marginTop: 2 }}>{unit}</div>}
            </div>
          ))}
        </div>
      </div>

      {/* ── Prices footnote — exact same values used for all cost calculations */}
      {prices && (
        <div style={{ fontSize: 11, color: T.muted, borderTop: '1px solid #f3f4f6', paddingTop: 8 }}>
          Price rates (same values used for all cycle, daily, and history costs):
          {' '}Water <b style={{ color: T.primary }}>₪{prices.water_per_liter_nis}/L</b>
          {' · '}Fertilizer <b style={{ color: T.primary }}>₪{prices.fertilizer_per_liter_nis}/L</b>
          {' · '}Electricity <b style={{ color: T.primary }}>₪{prices.electricity_per_kwh_nis}/kWh</b>
        </div>
      )}

    </div>
  );
}

// ── Tab 2: Resource History ───────────────────────────────────────────────────
function HistoryTab({ prices }) {
  const [logs,    setLogs]    = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => {
      fetch(`${API_BASE_URL}/pump-logs?limit=60`)
        .then(r => r.json())
        .then(d => { if (d.success) setLogs(d.logs || []); })
        .catch(() => {})
        .finally(() => setLoading(false));
    };
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const getAmount = log => {
    if (log.amount_l != null && log.amount_l > 0) return log.amount_l;
    if (log.flow_rate_l_min > 0 && log.pulse_sec > 0)
      return log.flow_rate_l_min * (log.pulse_sec / 60);
    return null;
  };

  const getCost = (log, amount) => {
    if (!prices || amount == null) return null;
    if (log.pump === 'water')      return amount * prices.water_per_liter_nis;
    if (log.pump === 'fertilizer') return amount * prices.fertilizer_per_liter_nis;
    return null;
  };

  const COLS = ['Time', 'Resource', 'Actuator', 'Duration', 'Amount Used', 'Cost', 'Reason'];

  return (
    <div style={{
      background: '#fff', borderRadius: 14,
      border: '1.5px solid #e5e7eb',
      overflow: 'hidden',
      boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 20px', borderBottom: '1px solid #e5e7eb', background: '#fafafa',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ background: '#f5f3ff', borderRadius: 8, padding: 8, display: 'flex' }}>
            <Icon path={IC.history} size={15} color='#7c3aed' />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: T.primary }}>Resource History</div>
            <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>
              {logs.length} events · auto-refreshes every 30 s
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 99, background: '#eff6ff' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#2563eb' }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: '#2563eb' }}>Live</span>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '30px', textAlign: 'center', color: T.muted, fontSize: 13 }}>Loading history…</div>
      ) : logs.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <Icon path={IC.pump} size={32} color='#d1d5db' />
          <div style={{ fontSize: 13, color: T.muted, marginTop: 10 }}>No pump events recorded yet.</div>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                {COLS.map(h => (
                  <th key={h} style={{
                    padding: '9px 14px', textAlign: 'left',
                    fontSize: 10, fontWeight: 800, color: T.muted,
                    letterSpacing: '0.08em', textTransform: 'uppercase', whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.map((log, i) => {
                const isWater  = log.pump === 'water';
                const accent   = isWater ? '#2563eb' : '#16a34a';
                const bg       = isWater ? '#eff6ff' : '#f0fdf4';
                const amount   = getAmount(log);
                const cost     = getCost(log, amount);
                const amountStr = amount != null
                  ? `${amount < 0.001 ? amount.toFixed(6) : amount.toFixed(4)} L`
                  : '—';
                const costStr = cost != null
                  ? `₪${cost < 0.0001 ? cost.toExponential(2) : cost.toFixed(5)}`
                  : '—';

                return (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6', background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: T.muted, whiteSpace: 'nowrap' }}>
                      {fmtTableTime(log.timestamp)}
                    </td>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: bg, borderRadius: 99, padding: '3px 10px', fontWeight: 700, color: accent, fontSize: 11 }}>
                        <Icon path={isWater ? IC.water : IC.fertilizer} size={10} color={accent} />
                        {isWater ? 'Water' : 'Fertilizer'}
                      </span>
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: T.label, whiteSpace: 'nowrap' }}>
                      {isWater ? 'Water Pump' : 'Fertilizer Pump'}
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 12, fontWeight: 700, color: T.primary }}>
                      {log.pulse_sec != null ? `${log.pulse_sec} s` : '—'}
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 12, fontWeight: 700, color: amount != null ? accent : '#d1d5db' }}>
                      {amountStr}
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 12, fontWeight: 700, color: cost != null ? '#16a34a' : '#d1d5db' }}>
                      {costStr}
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 11, color: T.muted, maxWidth: 300 }}>
                      {log.reason || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
// All shared state lives here — single source of truth for prices, daily, cycleStart.
export default function ResourceConsumption({ sensors, onNewCycle }) {
  const [tab,        setTab]        = useState('summary');
  const [prices,     setPrices]     = useState(null);
  const [daily,      setDaily]      = useState(null);
  const [cycleStart, setCycleStart] = useState(null);
  const [cycleResult, setCycleResult] = useState(null); // result message for header

  const fetchDaily = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/resources/daily`, { cache: 'no-store' });
      const data = await res.json();
      if (data.success) {
        setDaily(data.daily);
        if (data.cycle_started_at) setCycleStart(data.cycle_started_at);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/resource-prices`).then(r => r.json())
      .then(d => { if (d.success) setPrices(d.prices); }).catch(() => {});
    fetchDaily();
    const id = setInterval(fetchDaily, 30000);
    return () => clearInterval(id);
  }, [fetchDaily]);

  // Wrap onNewCycle to refresh dates after reset
  const handleNewCycle = useCallback(async () => {
    const data = await onNewCycle();
    if (data?.success) {
      // Re-fetch daily/cycleStart immediately after reset
      await fetchDaily();
      setCycleResult({ ok: true, msg: data.message || 'New plant cycle started.' });
    } else {
      setCycleResult({ ok: false, msg: data?.error || 'Reset failed.' });
    }
    return data;
  }, [onNewCycle, fetchDaily]);

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>

      {/* ── Header row: title + New Cycle button + tabs ───────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6, flexWrap: 'wrap' }}>
        {/* Title */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: T.primary }}>
            Resource Consumption
          </h2>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>
            {tab === 'summary' ? 'Cycle totals · daily usage · live electricity' : 'Pump event log with amounts and costs'}
          </div>
        </div>

        {/* New Plant Cycle button — always visible in header */}
        {onNewCycle && (
          <NewCycleButton onNewCycle={handleNewCycle} />
        )}

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 5, padding: 5, background: '#f3f4f6', borderRadius: 11, flexShrink: 0 }}>
          <TabBtn active={tab === 'summary'} onClick={() => setTab('summary')}
            iconPath='M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'>
            Summary
          </TabBtn>
          <TabBtn active={tab === 'history'} onClick={() => setTab('history')}
            iconPath='M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'>
            Resource History
          </TabBtn>
        </div>
      </div>

      {/* Cycle reset result banner (under header, above tabs content) */}
      {cycleResult && (
        <div style={{
          marginBottom: 14, padding: '10px 16px', borderRadius: 10,
          background: cycleResult.ok ? '#f0fdf4' : '#fee2e2',
          border:     `1px solid ${cycleResult.ok ? '#86efac' : '#fca5a5'}`,
          color:      cycleResult.ok ? '#166534'  : '#991b1b',
          fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon path={cycleResult.ok ? IC.check : IC.info} size={14} color={cycleResult.ok ? '#16a34a' : '#dc2626'} />
            {cycleResult.msg}
          </div>
          <button onClick={() => setCycleResult(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'inherit' }}>×</button>
        </div>
      )}

      {/* Tab content */}
      {tab === 'summary' ? (
        <SummaryTab
          sensors={sensors}
          prices={prices}
          daily={daily}
          cycleStart={cycleStart}
        />
      ) : (
        <HistoryTab prices={prices} />
      )}

    </div>
  );
}

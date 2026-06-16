import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';

function Icon({ path, size = 16, color = 'currentColor', sw = 2, fill = 'none' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill}
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const ICONS = {
  temp:   'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z',
  humid:  'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
  light:  'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z',
  ph:     'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18',
  ec:     'M13 10V3L4 14h7v7l9-11h-7z',
  money:  'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  elec:   'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  water:  'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
  fert:   'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z M8 12h8M12 8v8',
  clock:  'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  leaf:   'M17 8C8 10 5.9 16.17 3.82 19c3.15.6 6.41-.34 8.68-2.61 2.56-2.56 3.07-6.44 1.5-9.39zm0 0c-.2 4.17-2.69 7.78-6 10',
  auto:   'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  manual: 'M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z',
  warn:   'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  arrow:  'M5 12h14M12 5l7 7-7 7',
  bulb:   'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  health: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  growth: 'M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z',
  cal:    'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  drop:   'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
};

// ── Environment parameters (current value + active setpoint) ───────────────────
const ENV_PARAMS = [
  { key: 'air_temperature',  label: 'Air Temperature', unit: '°C',    spKey: 'temperature',   dec: 1, tol: 3 },
  { key: 'air_humidity',     label: 'Humidity',         unit: '%',     spKey: 'humidity',       dec: 1, tol: 15 },
  { key: 'soil_temperature', label: 'Root Temperature', unit: '°C',    spKey: 'soil_temp',      dec: 1, tol: 3 },
  { key: 'soil_humidity',    label: 'Soil Moisture',    unit: '%',     spKey: 'soil_moisture',  dec: 1, tol: 15 },
  { key: 'soil_ec',          label: 'EC',               unit: 'µS/cm', spKey: 'soil_ec',        dec: 0, tolPct: 0.25 },
  { key: 'soil_ph',          label: 'pH',               unit: 'pH',    spKey: 'soil_ph',        dec: 2, tol: 0.8 },
  { key: 'light_intensity',  label: 'Light',            unit: 'lux',   spKey: 'light',          dec: 0, tolPct: 0.25 },
];

function envStatus(cfg, value, sp) {
  if (value == null || !sp) return 'unknown';
  const spVal = sp[cfg.spKey];
  if (spVal == null) return 'unknown';
  const diff = Math.abs(value - spVal);
  const threshold = cfg.tolPct != null ? spVal * cfg.tolPct : cfg.tol;
  return diff > threshold ? 'warning' : 'normal';
}

const nis =(v, d = 2) => (v == null || isNaN(v)) ? '—' : `₪${Number(v).toFixed(d)}`;

// ── Compact trend sparkline (line + area) ─────────────────────────────────────
function Sparkline({ points, color, unit = '', height = 78, valueDec = 1 }) {
  const vals = (points || []).map(p => p.value).filter(v => v != null && !isNaN(v));
  if (vals.length < 2) {
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#f9fafb', borderRadius: 8, border: '1px dashed #e5e7eb',
        fontSize: 12, color: '#9ca3af', fontStyle: 'italic', textAlign: 'center', padding: '0 12px',
      }}>
        Need at least 2 measurements to show a trend
      </div>
    );
  }
  const min = Math.min(...vals), max = Math.max(...vals), rng = (max - min) || 1;
  const W = 460, H = height, padL = 4, padR = 4, padT = 8, padB = 14;
  const iW = W - padL - padR, iH = H - padT - padB;
  const pts = vals.map((v, i) => [
    padL + (i / (vals.length - 1)) * iW,
    padT + iH - ((v - min) / rng) * iH,
  ]);
  const line = pts.map(([x, y]) => `${x},${y}`).join(' ');
  const area = `${pts[0][0]},${padT + iH} ${line} ${pts[pts.length - 1][0]},${padT + iH}`;
  const gid = `spk-${color.replace('#', '')}-${vals.length}`;
  const lastLabel = points[points.length - 1]?.label || '';
  const firstLabel = points[0]?.label || '';
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height }} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polygon fill={`url(#${gid})`} points={area} />
        <polyline fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" points={line} />
        <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3.2" fill={color} />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
        <span>{firstLabel}</span>
        <span>Min {min.toFixed(valueDec)}{unit} · Max {max.toFixed(valueDec)}{unit}</span>
        <span>{lastLabel}</span>
      </div>
    </div>
  );
}

// ── Daily expenses bar chart ──────────────────────────────────────────────────
function DailyBars({ history, todayDate }) {
  if (!history || history.length === 0) {
    return (
      <div style={{
        height: 96, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#f9fafb', borderRadius: 8, border: '1px dashed #e5e7eb',
        fontSize: 12, color: '#9ca3af', fontStyle: 'italic',
      }}>
        No daily expense history yet
      </div>
    );
  }
  const vals = history.map(d => d.total_cost_nis || 0);
  const max  = Math.max(...vals, 0.0001);
  const PLOT = 78; // px height of the tallest bar
  const fmtDay = (iso) => { try { return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); } catch { return iso; } };

  return (
    <div>
      {/* peak reference */}
      <div style={{ fontSize: 10.5, color: '#9ca3af', marginBottom: 2 }}>Peak day: <b style={{ color: '#374151' }}>{nis(max)}</b></div>

      {/* plot area with baseline */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: history.length < 6 ? 'flex-start' : 'space-between',
                    gap: 8, height: PLOT + 22, padding: '14px 2px 0', borderBottom: '2px solid #e5e7eb', overflowX: 'auto' }}>
        {history.map((d) => {
          const v = d.total_cost_nis || 0;
          const h = v > 0 ? Math.max(6, (v / max) * PLOT) : 2;
          const isToday = d.date === todayDate;
          return (
            <div key={d.date} title={`${fmtDay(d.date)}: ${nis(v, 4)}`}
              style={{ flex: '1 0 40px', maxWidth: 70, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
              {/* value label above the bar */}
              <span style={{ fontSize: 10.5, fontWeight: 800, color: isToday ? '#15803d' : '#6b7280', marginBottom: 4, whiteSpace: 'nowrap' }}>
                {v > 0 ? nis(v) : '—'}
              </span>
              {/* bar */}
              <div style={{
                width: '74%', maxWidth: 38, height: h, borderRadius: '6px 6px 0 0',
                background: isToday ? 'linear-gradient(180deg,#22c55e,#15803d)' : '#4ade80',
                boxShadow: isToday ? '0 2px 6px rgba(21,128,61,0.35)' : 'none',
              }} />
            </div>
          );
        })}
      </div>

      {/* date labels under the baseline */}
      <div style={{ display: 'flex', justifyContent: history.length < 6 ? 'flex-start' : 'space-between', gap: 8, marginTop: 6 }}>
        {history.map((d) => {
          const isToday = d.date === todayDate;
          return (
            <span key={d.date} style={{ flex: '1 0 40px', maxWidth: 70, textAlign: 'center', fontSize: 10.5,
              color: isToday ? '#15803d' : '#9ca3af', fontWeight: isToday ? 800 : 500, whiteSpace: 'nowrap' }}>
              {isToday ? 'Today' : fmtDay(d.date)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ icon, iconColor = '#16a34a', iconBg = '#f0fdf4', title, right, children, accentBg = '#fff', accentBorder = '#e5e7eb' }) {
  return (
    <div style={{ background: accentBg, border: `1px solid ${accentBorder}`, borderRadius: 16, padding: '16px 20px', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ background: iconBg, borderRadius: 9, padding: 8, display: 'flex' }}>
          <Icon path={icon} size={16} color={iconColor} />
        </div>
        <span style={{ fontSize: 16, fontWeight: 800, color: '#111827' }}>{title}</span>
        {right && <div style={{ marginLeft: 'auto' }}>{right}</div>}
      </div>
      {children}
    </div>
  );
}

function fmtDate(iso, withTime = false) {
  if (!iso) return null;
  try {
    const opts = withTime
      ? { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
      : { day: 'numeric', month: 'short', year: 'numeric' };
    return new Date(iso).toLocaleString('en-US', opts);
  } catch { return iso; }
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function Dashboard({
  sensors, setpoints, lastUpdate, healthDbLatest, healthDbHistory,
  growthLatest, growthHistory, onNavigate,
}) {
  const sp = setpoints || {};
  const s  = sensors   || {};
  const isAuto = sp.operation_mode === 'autonomous';

  const [tab, setTab] = useState('state'); // 'state' = sections 1+2, 'budget' = sections 3+4

  // ── Self-fetched data (budget / costs / recommendation) ─────────────────────
  const [decision,   setDecision]   = useState(null);
  const [budgetCfg,  setBudgetCfg]  = useState(null);
  const [dailyCosts, setDailyCosts] = useState(null);
  const [cycleStart, setCycleStart] = useState(null);
  const [layer2Rec,  setLayer2Rec]  = useState(null);
  const [costHistory, setCostHistory] = useState(null);

  const getJson = (url) => fetch(url, { cache: 'no-store' }).then(r => r.json()).catch(() => null);

  const fetchAll = useCallback(async () => {
    const [l3, cfg, daily, l2, hist] = await Promise.all([
      getJson(`${API_BASE_URL}/layer3/latest`),
      getJson(`${API_BASE_URL}/layer3/budget-config`),
      getJson(`${API_BASE_URL}/resources/daily`),
      getJson(`${API_BASE_URL}/ai-advisor/latest`),
      getJson(`${API_BASE_URL}/resources/daily-history?days=14`),
    ]);
    if (l3?.success)    setDecision(l3.decision);
    if (cfg?.success)   setBudgetCfg(cfg.config);
    if (daily?.success) { setDailyCosts(daily.daily); setCycleStart(daily.cycle_started_at || null); }
    if (l2?.success)    setLayer2Rec(l2.recommendation);
    if (hist?.success)  setCostHistory(hist.history || []);
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 15000);
    return () => clearInterval(id);
  }, [fetchAll]);

  // ── Recommendation / approval state (Layer 2 → Layer 3) ─────────────────────
  const DEC_STYLE = {
    APPROVE:    { color: '#166534', border: '#86efac', label: 'APPROVE',    dot: '#16a34a' },
    MODIFY:     { color: '#854d0e', border: '#fde047', label: 'MODIFY',     dot: '#d97706' },
    BLOCK:      { color: '#991b1b', border: '#fca5a5', label: 'BLOCK',      dot: '#dc2626' },
    ALERT_ONLY: { color: '#92400e', border: '#fcd34d', label: 'ALERT ONLY', dot: '#f59e0b' },
  };
  const decType  = decision?.decision;
  const decStatus = decision?.status;
  const decStyle = DEC_STYLE[decType] || { color: '#6b7280', border: '#e5e7eb', label: decType || '—', dot: '#9ca3af' };
  const isActioned = decStatus && ['approved', 'rejected', 'cancelled'].includes(decStatus);
  const hasPending = !!decision && !isActioned && decType !== 'BLOCK';

  const buildChanges = () => {
    if (!decision || !setpoints) return [];
    const PARAMS = [
      { key: 'light',          label: 'Light',          unit: '' },
      { key: 'soil_moisture',  label: 'Soil Moisture',  unit: '%' },
      { key: 'soil_ec',        label: 'Soil EC',        unit: 'µS/cm' },
      { key: 'soil_ph',        label: 'Soil pH',        unit: '' },
      { key: 'temperature',    label: 'Air Temp',       unit: '°C' },
      { key: 'humidity',       label: 'Humidity',       unit: '%' },
      { key: 'fan_day_duty',   label: 'Fan Day',        unit: '' },
      { key: 'fan_night_duty', label: 'Fan Night',      unit: '' },
      { key: 'soil_temp',      label: 'Soil Temp',      unit: '°C' },
    ];
    const L2 = { 'soil ph':'soil_ph','soil ec':'soil_ec','soil moisture':'soil_moisture','light':'light','light setpoint':'light','temperature':'temperature','air temperature':'temperature','humidity':'humidity','fan day duty':'fan_day_duty','fan night duty':'fan_night_duty','soil temperature':'soil_temp','soil temp':'soil_temp' };
    const L3 = { 'light_setpoint':'light','soil_moisture_setpoint':'soil_moisture','soil_ec_setpoint':'soil_ec','soil_ph_setpoint':'soil_ph','soil_temp_setpoint':'soil_temp','temperature_setpoint':'temperature','humidity_setpoint':'humidity','fan_day_duty':'fan_day_duty','fan_night_duty':'fan_night_duty' };
    const l2v = {}; (layer2Rec?.changes || []).forEach(c => { const k = L2[(c.parameter||'').toLowerCase()]; if (k) l2v[k] = c.recommended_value; });
    const l3v = {}; (decision?.proposed_modifications || []).forEach(m => { const k = L3[m.parameter] || m.parameter; l3v[k] = m.proposed_value; });
    return PARAMS.map(p => {
      const current = setpoints[p.key];
      const final   = l3v[p.key] !== undefined ? l3v[p.key] : (l2v[p.key] !== undefined ? l2v[p.key] : current);
      return { ...p, current, final, changed: final !== undefined && current !== undefined && Number(final) !== Number(current) };
    }).filter(r => r.changed);
  };
  const changes = buildChanges();

  // ── Expenses figures ────────────────────────────────────────────────────────
  const totalSoFar  = s.total_cost_nis;
  const todayDate   = dailyCosts?.date || null;
  const costToday   = dailyCosts?.total_cost_nis ?? null;
  // Only show days from the current plant cycle onward (graph + yesterday).
  const cycleStartDate = cycleStart ? String(cycleStart).slice(0, 10) : null;
  const cycleCostHistory = (cycleStartDate && costHistory)
    ? costHistory.filter(d => d.date >= cycleStartDate)
    : costHistory;
  // yesterday = the entry before the last (today) in the chronological history
  let costYesterday = null;
  if (cycleCostHistory && cycleCostHistory.length >= 2) {
    const last = cycleCostHistory[cycleCostHistory.length - 1];
    const prev = cycleCostHistory[cycleCostHistory.length - 2];
    if (todayDate && last?.date === todayDate) costYesterday = prev.total_cost_nis;
    else costYesterday = last.total_cost_nis; // no entry for today yet → last is yesterday
  }
  const deltaAbs = (costToday != null && costYesterday != null) ? costToday - costYesterday : null;
  const deltaPct = (deltaAbs != null && costYesterday > 0) ? (deltaAbs / costYesterday) * 100 : null;

  // ── Budget figures ──────────────────────────────────────────────────────────
  const cycleBudget = (budgetCfg?.monthly_budget && budgetCfg.monthly_budget > 0)
    ? budgetCfg.monthly_budget
    : (budgetCfg?.daily_budget && budgetCfg.daily_budget > 0 ? budgetCfg.daily_budget : null);
  const spent     = totalSoFar != null ? Number(totalSoFar) : null;
  const remaining = (cycleBudget != null && spent != null) ? Math.max(0, cycleBudget - spent) : null;
  const usedPct   = (cycleBudget != null && spent != null && cycleBudget > 0) ? (spent / cycleBudget) * 100 : null;
  const budgetColor = usedPct == null ? '#9ca3af' : usedPct > 100 ? '#dc2626' : usedPct >= 80 ? '#d97706' : '#16a34a';
  const daysSinceStart = cycleStart ? Math.max(0, Math.floor((Date.now() - new Date(cycleStart).getTime()) / 86400000)) : null;

  // ── Health panel ────────────────────────────────────────────────────────────
  const hp       = healthDbLatest;
  const hHealthy = hp?.is_healthy;
  const hPct     = hp?.health_probability ?? null;
  const hDiseases = hp?.diseases || [];
  const hAccent  = !hp ? '#9ca3af' : hHealthy ? '#16a34a' : (hPct != null && hPct >= 40) ? '#d97706' : '#dc2626';
  const hMessage = !hp ? null
    : hHealthy ? 'Plant appears healthy — no issues detected.'
    : hDiseases.length > 0
      ? `Possible issue: ${hDiseases[0].name || hDiseases[0].disease || 'unknown'}${hDiseases.length > 1 ? ` (+${hDiseases.length - 1} more)` : ''}`
      : 'Issues detected in the latest analysis.';
  const healthSpark = [...(healthDbHistory || [])]
    .filter(r => r.health_probability != null)
    .reverse()
    .map(r => ({ value: Number(r.health_probability), label: fmtShort(r.created_at) }));

  // ── Growth panel ────────────────────────────────────────────────────────────
  const gd = growthLatest && growthLatest.status === 'success' ? growthLatest : null;

  // Growth % since day 1 — vs the FIRST measurement of the current plant cycle
  // (history is scoped per-cycle and ordered newest-first → oldest is last).
  const gSuccess = [...(growthHistory || [])].filter(r => r.status === 'success' && r.area_cm2 != null);
  const gFirst   = gSuccess.length ? gSuccess[gSuccess.length - 1] : null;
  const areaSincePct = (gd && gFirst && gFirst.area_cm2 > 0)
    ? ((gd.area_cm2 - gFirst.area_cm2) / gFirst.area_cm2) * 100
    : null;
  const gDays = (gd && gFirst && gFirst.captured_at && gd.captured_at)
    ? Math.max(0, Math.round((new Date(gd.captured_at) - new Date(gFirst.captured_at)) / 86400000))
    : null;
  // Volume (V_index) trend over time — oldest → newest for the chart.
  const growthSpark = [...(growthHistory || [])]
    .filter(r => r.status === 'success' && r.volume_cm3 != null)
    .reverse()
    .map(r => ({ value: Number(r.volume_cm3), label: fmtShort(r.created_at) }));

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Page header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ background: 'linear-gradient(135deg, #16a34a, #15803d)', borderRadius: 10, padding: 8, display: 'flex' }}>
            <Icon path={ICONS.leaf} size={18} color='#fff' />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 900, color: '#111827' }}>Dashboard</h2>
            <div style={{ fontSize: 12, color: '#9ca3af' }}>System Overview · Lettuce</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '6px 14px', borderRadius: 99, background: isAuto ? '#f0fdf4' : '#eff6ff', border: `1px solid ${isAuto ? '#86efac' : '#bfdbfe'}` }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: isAuto ? '#16a34a' : '#2563eb' }} />
          <Icon path={isAuto ? ICONS.auto : ICONS.manual} size={14} color={isAuto ? '#16a34a' : '#2563eb'} />
          <span style={{ fontSize: 13, fontWeight: 700, color: isAuto ? '#15803d' : '#1d4ed8' }}>{isAuto ? 'Autonomous' : 'Manual'}</span>
        </div>
      </div>

      {/* ── Tab bar (below the header) ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <TabBtn active={tab === 'state'}  onClick={() => setTab('state')}  icon={ICONS.leaf}>Environment &amp; Plant</TabBtn>
        <TabBtn active={tab === 'budget'} onClick={() => setTab('budget')} icon={ICONS.money}>Expenses &amp; Budget</TabBtn>
      </div>

      {tab === 'state' && (<>
      {/* ═══ 1. CURRENT ENVIRONMENT CONTROL ═══ */}
      <Section
        icon={ICONS.temp} iconColor='#d97706' iconBg='#fef3c7'
        title='Current Environment Control'
        right={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#6b7280' }}>
          <Icon path={ICONS.clock} size={13} color='#9ca3af' />
          {lastUpdate ? `Updated ${lastUpdate}` : 'Waiting for sensor data…'}
        </span>}
      >
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 7 }}>
          {ENV_PARAMS.map(cfg => (
            <EnvMiniCard
              key={cfg.key}
              label={cfg.label}
              value={s[cfg.key] != null ? Number(s[cfg.key]).toFixed(cfg.dec) : null}
              target={sp[cfg.spKey] != null ? String(sp[cfg.spKey]) : null}
              unit={cfg.unit}
              status={envStatus(cfg, s[cfg.key], sp)}
            />
          ))}
        </div>
      </Section>

      {/* ═══ 2. CURRENT PLANT STATE ═══ */}
      <div style={{ fontSize: 12, fontWeight: 800, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 2px 8px' }}>Current Plant State</div>
      <div className="grid-2" style={{ marginBottom: 0 }}>

        {/* A. Plant Health */}
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div style={{ background: '#f0fdf4', borderRadius: 9, padding: 8, display: 'flex' }}><Icon path={ICONS.health} size={16} color={hAccent} /></div>
            <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Plant Health</span>
            {hp && <span style={{ marginLeft: 'auto', fontSize: 11, color: '#9ca3af' }}>{fmtDate(hp.created_at, true)}</span>}
          </div>
          {!hp ? (
            <div style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.6, padding: '20px 0' }}>
              No health analysis yet. Open <strong>Plant Health</strong> and run a capture.
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 26, fontWeight: 900, color: hAccent }}>{hHealthy ? 'Healthy' : 'Issues'}</span>
                {hPct != null && <span style={{ fontSize: 15, fontWeight: 700, color: '#6b7280' }}>{hPct}% confidence</span>}
              </div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.5, marginBottom: 14 }}>{hMessage}</div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Health trend (confidence %)</div>
              <Sparkline points={healthSpark} color={hAccent === '#9ca3af' ? '#16a34a' : hAccent} unit='%' valueDec={0} height={58} />
            </>
          )}
        </div>

        {/* B. Plant Growth */}
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '14px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div style={{ background: '#f0fdf4', borderRadius: 9, padding: 8, display: 'flex' }}><Icon path={ICONS.growth} size={16} color='#16a34a' /></div>
            <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Plant Growth</span>
            {gd && <span style={{ marginLeft: 'auto', fontSize: 11, color: '#9ca3af' }}>{fmtDate(gd.created_at, true)}</span>}
          </div>
          {!gd ? (
            <div style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.6, padding: '20px 0' }}>
              No growth measurement yet. Open <strong>Plant Growth</strong> and run an analysis.
            </div>
          ) : (
            <>
              {/* Just four — Height, Width, Volume, Growth % since day 1 (all from the new pipeline) */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                <Metric label='Height' value={gd.height_cm  != null ? Number(gd.height_cm ).toFixed(1) : '—'} unit='cm' />
                <Metric label='Width'  value={gd.width_cm   != null ? Number(gd.width_cm  ).toFixed(1) : '—'} unit='cm' />
                <Metric label='Volume' value={gd.volume_cm3 != null ? Number(gd.volume_cm3).toFixed(0) : '—'} unit='cm³' />
                <Metric
                  label={gDays && gDays > 0 ? `Growth · ${gDays}d` : 'Growth · day 1'}
                  value={areaSincePct != null ? `${areaSincePct >= 0 ? '+' : ''}${areaSincePct.toFixed(1)}` : '—'}
                  unit='%'
                  color={areaSincePct == null ? '#111827' : areaSincePct >= 0 ? '#16a34a' : '#dc2626'}
                />
              </div>

              {/* Growth trend chart — Volume (V_index) over time */}
              <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 12, marginBottom: 4 }}>Growth trend (volume cm³)</div>
              <Sparkline points={growthSpark} color='#16a34a' unit=' cm³' valueDec={0} height={64} />
            </>
          )}
        </div>
      </div>
      </>)}

      {tab === 'budget' && (
      <div className="grid-2" style={{ alignItems: 'start' }}>
      {/* ═══ 3. EXPENSES ═══ */}
      <Section icon={ICONS.money} title='Expenses'
        right={resetLabelChip(cycleStart)}
      >
        <div className="grid-2" style={{ marginBottom: 12 }}>
          <BigStat label='Total cost so far' value={nis(totalSoFar, 4)} accent />
          <BigStat label='Cost today' value={nis(costToday)} />
          <BigStat label='Cost yesterday' value={nis(costYesterday)} />
          <BigStat
            label='Δ vs yesterday'
            value={deltaAbs == null ? '—' : `${deltaAbs >= 0 ? '+' : ''}${nis(Math.abs(deltaAbs))}`}
            sub={deltaPct == null ? null : `${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(0)}%`}
            color={deltaAbs == null ? '#111827' : deltaAbs > 0 ? '#dc2626' : '#16a34a'}
          />
        </div>

        <div className="grid-3" style={{ marginBottom: 12 }}>
          {[
            { label: 'Water cost',       value: s.water_cost_nis,       icon: ICONS.water, iconBg: '#eff6ff', iconColor: '#2563eb' },
            { label: 'Fertilizer cost',  value: s.fertilizer_cost_nis,  icon: ICONS.fert,  iconBg: '#f0fdf4', iconColor: '#16a34a' },
            { label: 'Electricity cost', value: s.electricity_cost_nis, icon: ICONS.elec,  iconBg: '#fefce8', iconColor: '#ca8a04' },
          ].map(({ label, value, icon, iconBg, iconColor }) => (
            <div key={label} style={{ background: '#f9fafb', borderRadius: 10, padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                <div style={{ background: iconBg, borderRadius: 6, padding: 5, display: 'flex' }}><Icon path={icon} size={12} color={iconColor} /></div>
                <span style={{ fontSize: 12, color: '#6b7280' }}>{label}</span>
              </div>
              <span style={{ fontSize: 16, fontWeight: 800, color: '#111827' }}>{nis(value, 4)}</span>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 11, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Daily expenses (this cycle)</div>
        <DailyBars history={cycleCostHistory} todayDate={todayDate} />

        {cycleBudget != null && spent != null && (
          <div style={{ marginTop: 14, fontSize: 13, color: '#374151' }}>
            Total spent vs cycle budget: <strong style={{ color: '#111827' }}>{nis(spent)} / {nis(cycleBudget)}</strong>
            {usedPct != null && <span style={{ color: budgetColor, fontWeight: 700 }}> ({usedPct.toFixed(1)}%)</span>}
          </div>
        )}
      </Section>

      {/* ═══ 4. BUDGET SUMMARY ═══ */}
      <Section icon={ICONS.money} iconColor='#15803d' title='Budget Summary'>
        {cycleBudget == null ? (
          <div style={{ fontSize: 13, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, padding: '12px 16px', lineHeight: 1.5 }}>
            No cycle budget configured. Set a <strong>monthly/cycle budget</strong> in <strong>Budget Manager → Budget Configuration</strong>.
          </div>
        ) : (
          <>
            <div className="grid-2" style={{ marginBottom: 12 }}>
              <BigStat label='Cycle budget' value={nis(cycleBudget)} />
              <BigStat label='Spent so far' value={nis(spent)} accent />
              <BigStat label='Remaining' value={nis(remaining)} color={remaining === 0 ? '#dc2626' : '#16a34a'} />
              <BigStat label='Used' value={usedPct != null ? `${usedPct.toFixed(1)}%` : '—'} color={budgetColor} />
            </div>

            {/* progress bar */}
            <div style={{ background: usedPct != null && usedPct > 100 ? '#fee2e2' : usedPct >= 80 ? '#fef3c7' : '#dcfce7', borderRadius: 99, height: 12, overflow: 'hidden', marginBottom: 8 }}>
              <div style={{ width: `${Math.min(100, Math.max(0, usedPct || 0))}%`, height: '100%', background: budgetColor, borderRadius: 99, transition: 'width 0.5s ease' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, color: '#6b7280', flexWrap: 'wrap', gap: 8 }}>
              <span><strong style={{ color: '#111827' }}>{nis(spent)}</strong> spent · <strong style={{ color: '#111827' }}>{nis(remaining)}</strong> remaining</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Icon path={ICONS.cal} size={13} color='#9ca3af' />
                {cycleStart ? `Cycle started ${fmtDate(cycleStart)}${daysSinceStart != null ? ` · day ${daysSinceStart}` : ''}` : 'Cycle start not recorded'}
              </span>
            </div>
          </>
        )}

        {/* Approval action — reuses Layer 3 Budget Manager (no duplicate approval logic) */}
        <div style={{ marginTop: 18, paddingTop: 16, borderTop: '1px solid #f3f4f6' }}>
          {!hasPending ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#9ca3af' }}>
              <Icon path={ICONS.bulb} size={14} color='#9ca3af' />
              {decType === 'BLOCK'
                ? 'Latest recommendation is BLOCKED by a safety gate — resolve the issue in Budget Manager.'
                : isActioned
                  ? `Latest recommendation already ${decStatus}. No action pending.`
                  : 'No pending recommendation to approve.'}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
              <div style={{ minWidth: 220, flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 800, color: '#111827' }}>Pending recommendation</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 9px', borderRadius: 99, border: `1px solid ${decStyle.border}`, fontSize: 11, fontWeight: 800, color: decStyle.color }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: decStyle.dot }} />{decStyle.label}
                  </span>
                </div>
                {changes.length > 0 ? (
                  <div style={{ fontSize: 12.5, color: '#374151', lineHeight: 1.5 }}>
                    {changes.slice(0, 3).map(c => `${c.label} ${c.current}→${c.final}${c.unit ? ' ' + c.unit : ''}`).join(' · ')}
                    {changes.length > 3 && ` · +${changes.length - 3} more`}
                  </div>
                ) : (
                  <div style={{ fontSize: 12.5, color: '#6b7280' }}>{decision?.reason || 'Review the cost impact before approving.'}</div>
                )}
              </div>
              <button onClick={() => onNavigate && onNavigate('layer3')}
                style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 20px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg,#16a34a,#15803d)', color: '#fff', fontWeight: 700, fontSize: 13.5, cursor: 'pointer' }}>
                Review &amp; Approve Recommendation <Icon path={ICONS.arrow} size={15} color='#fff' />
              </button>
            </div>
          )}
        </div>
      </Section>
      </div>
      )}

    </div>
  );
}

// ── Tab button (clear, solid button look) ─────────────────────────────────────
function TabBtn({ active, onClick, icon, children }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 9,
      padding: '11px 22px', borderRadius: 12, cursor: 'pointer', whiteSpace: 'nowrap',
      fontSize: 14, fontWeight: 800, transition: 'all 0.15s', outline: 'none',
      background: active ? 'linear-gradient(135deg,#16a34a,#15803d)' : '#fff',
      color: active ? '#fff' : '#374151',
      border: active ? '1px solid #15803d' : '1.5px solid #d1d5db',
      boxShadow: active ? '0 4px 12px rgba(21,128,61,0.30)' : '0 1px 2px rgba(0,0,0,0.06)',
      transform: active ? 'translateY(-1px)' : 'none',
    }}>
      <span style={{
        display: 'flex', borderRadius: 7, padding: 5,
        background: active ? 'rgba(255,255,255,0.22)' : '#f0fdf4',
      }}>
        <Icon path={icon} size={15} color={active ? '#fff' : '#16a34a'} />
      </span>
      {children}
    </button>
  );
}

// ── Compact environment mini-card (reading + target together) ─────────────────
function EnvMiniCard({ label, value, target, unit, status }) {
  const clr = status === 'warning' ? { dot: '#d97706', bd: '#fde68a', val: '#92400e' }
            : status === 'normal'  ? { dot: '#16a34a', bd: '#e5e7eb', val: '#111827' }
            :                        { dot: '#9ca3af', bd: '#e5e7eb', val: '#9ca3af' };
  return (
    <div style={{ background: '#fff', border: `1px solid ${clr.bd}`, borderRadius: 10, padding: '9px 11px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: clr.dot, flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontSize: 19, fontWeight: 900, color: clr.val, lineHeight: 1 }}>{value ?? '—'}</span>
        <span style={{ fontSize: 10, color: '#9ca3af', fontWeight: 600 }}>{unit}</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#9ca3af', fontWeight: 600, whiteSpace: 'nowrap' }}>
          🎯 {target ?? '—'}
        </span>
      </div>
    </div>
  );
}

// ── Small helpers ─────────────────────────────────────────────────────────────
function Metric({ label, value, unit, color = '#111827' }) {
  return (
    <div style={{ textAlign: 'center', background: '#f9fafb', borderRadius: 8, padding: '8px 6px' }}>
      <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 900, color }}>{value}<span style={{ fontSize: 10, color: '#9ca3af', fontWeight: 600 }}> {unit}</span></div>
    </div>
  );
}

function BigStat({ label, value, sub, accent, color = '#111827' }) {
  return (
    <div style={{ background: accent ? '#f0fdf4' : '#f9fafb', border: accent ? '1px solid #bbf7d0' : '1px solid #f3f4f6', borderRadius: 12, padding: '14px 16px' }}>
      <div style={{ fontSize: 11, color: accent ? '#15803d' : '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 22, fontWeight: 900, color, lineHeight: 1 }}>{value}</span>
        {sub && <span style={{ fontSize: 13, fontWeight: 700, color }}>{sub}</span>}
      </div>
    </div>
  );
}

function resetLabelChip(cycleStart) {
  if (!cycleStart) return null;
  let label;
  try { label = new Date(cycleStart).toLocaleString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { label = cycleStart; }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 99, background: '#f0fdf4', border: '1px solid #bbf7d0', fontSize: 12, fontWeight: 700, color: '#15803d' }}>
      <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={ICONS.cal} /></svg>
      Since {label}
    </span>
  );
}

function fmtShort(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
  catch { return ''; }
}

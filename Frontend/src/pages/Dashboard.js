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

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function Dashboard({ sensors, setpoints, lastUpdate, captureSessions, healthDbLatest, growthLatest, onNavigate }) {
  const sp = setpoints || {};
  const s  = sensors   || {};

  const isAuto = sp.operation_mode === 'autonomous';

  // Warning logic
  const tempWarn     = s.air_temperature  != null && (s.air_temperature  > 28 || s.air_temperature  < 16);
  const moistureWarn = s.soil_humidity    != null && s.soil_humidity    < 20;
  const ecWarn       = s.soil_ec          != null && (s.soil_ec          > 1600 || s.soil_ec < 200);
  const phWarn       = s.soil_ph          != null && (s.soil_ph          > 7.5  || s.soil_ph < 5.0);

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
    check:  'M20 6L9 17l-5-5',
    x:      'M18 6L6 18M6 6l12 12',
    arrow:  'M5 12h14M12 5l7 7-7 7',
    bulb:   'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
    health: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
    growth: 'M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z',
    cal:    'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
  };

  const warnings = [
    tempWarn     && `Air temperature ${s.air_temperature}°C is outside optimal range (16–28°C)`,
    moistureWarn && `Soil moisture ${s.soil_humidity}% is critically low (< 20%)`,
    ecWarn       && `Soil EC ${s.soil_ec} µS/cm is outside safe range (200–1600)`,
    phWarn       && `Soil pH ${s.soil_ph} is outside optimal range (5.0–7.5)`,
  ].filter(Boolean);

  // ── Action card + budget data (fetched by the Dashboard itself) ─────────────
  const [decision,      setDecision]      = useState(null);
  const [budgetCfg,     setBudgetCfg]     = useState(null);
  const [dailyCosts,    setDailyCosts]    = useState(null);
  const [cycleStart,    setCycleStart]    = useState(null);
  const [layer2Rec,     setLayer2Rec]     = useState(null);

  const getJson = (url) => fetch(url, { cache: 'no-store' }).then(r => r.json()).catch(() => null);

  const fetchAction = useCallback(async () => {
    const [l3, cfg, daily, l2] = await Promise.all([
      getJson(`${API_BASE_URL}/layer3/latest`),
      getJson(`${API_BASE_URL}/layer3/budget-config`),
      getJson(`${API_BASE_URL}/resources/daily`),
      getJson(`${API_BASE_URL}/ai-advisor/latest`),
    ]);
    if (l3?.success)    setDecision(l3.decision);
    if (cfg?.success)   setBudgetCfg(cfg.config);
    if (daily?.success) { setDailyCosts(daily.daily); setCycleStart(daily.cycle_started_at || null); }
    if (l2?.success)    setLayer2Rec(l2.recommendation);
  }, []);

  useEffect(() => {
    fetchAction();
    const id = setInterval(fetchAction, 15000);
    return () => clearInterval(id);
  }, [fetchAction]);

  // Decision-derived state
  const DEC_STYLE = {
    APPROVE:    { bg: '#dcfce7', color: '#166534', border: '#86efac', label: 'APPROVE',    dot: '#16a34a' },
    MODIFY:     { bg: '#fef9c3', color: '#854d0e', border: '#fde047', label: 'MODIFY',     dot: '#d97706' },
    BLOCK:      { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'BLOCK',      dot: '#dc2626' },
    ALERT_ONLY: { bg: '#fef3c7', color: '#92400e', border: '#fcd34d', label: 'ALERT ONLY', dot: '#f59e0b' },
  };
  const decType    = decision?.decision;
  const decStatus  = decision?.status;
  const decStyle   = DEC_STYLE[decType] || { bg: '#f9fafb', color: '#6b7280', border: '#e5e7eb', label: decType || '—', dot: '#9ca3af' };
  const isActioned = decStatus && ['approved', 'rejected', 'cancelled'].includes(decStatus);

  // Build a short "what changes" list (current → final), from Layer 2 + Layer 3 mods
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

  // Budget today vs daily budget
  const todaySpend  = dailyCosts?.total_cost_nis ?? 0;
  const dailyBudget = budgetCfg?.daily_budget ?? null;
  const hasDaily    = dailyBudget != null && dailyBudget > 0;
  const budgetPct   = hasDaily ? (todaySpend / dailyBudget) * 100 : null;
  const budgetColor = budgetPct == null ? '#9ca3af' : budgetPct > 100 ? '#dc2626' : budgetPct >= 80 ? '#d97706' : '#16a34a';

  // Cost reset date label (e.g. "4 Jun 2026, 14:30")
  const resetLabel = cycleStart
    ? (() => { try { return new Date(cycleStart).toLocaleString([], { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return cycleStart; } })()
    : null;

  // Plant health summary
  const hp          = healthDbLatest;
  const hHealthy    = hp?.is_healthy;
  const hPct        = hp?.health_probability ?? null;
  const hIssues     = (hp?.diseases || []).length;
  const hAccent     = !hp ? '#9ca3af' : hHealthy ? '#16a34a' : (hPct != null && hPct >= 40) ? '#d97706' : '#dc2626';
  const hAccentBg   = !hp ? '#f9fafb' : hHealthy ? '#f0fdf4' : (hPct != null && hPct >= 40) ? '#fffbeb' : '#fef2f2';
  const hAccentBd   = !hp ? '#e5e7eb' : hHealthy ? '#86efac' : (hPct != null && hPct >= 40) ? '#fde68a' : '#fca5a5';

  // Plant growth summary
  const gd          = growthLatest && growthLatest.status === 'success' ? growthLatest : null;
  const gGrowth     = gd?.growth_pct;
  const gHeight     = gd?.height_cm;
  const gArea       = gd?.canopy_area_cm2 ?? gd?.area_cm2;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ background: 'linear-gradient(135deg, #16a34a, #15803d)', borderRadius: 14, padding: 12, display: 'flex' }}>
            <Icon path={ICONS.leaf} size={26} color='#fff' />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 900, color: '#111827' }}>Dashboard</h2>
            <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 2, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>System Overview · Lettuce</span>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '8px 16px', borderRadius: 99, background: isAuto ? '#f0fdf4' : '#eff6ff', border: `1px solid ${isAuto ? '#86efac' : '#bfdbfe'}` }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: isAuto ? '#16a34a' : '#2563eb', boxShadow: isAuto ? '0 0 0 3px #bbf7d0' : '0 0 0 3px #bfdbfe' }} />
            <Icon path={isAuto ? ICONS.auto : ICONS.manual} size={14} color={isAuto ? '#16a34a' : '#2563eb'} />
            <span style={{ fontSize: 13, fontWeight: 700, color: isAuto ? '#15803d' : '#1d4ed8' }}>
              {isAuto ? 'Autonomous' : 'Manual'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Warnings ──────────────────────────────────────────────────────────── */}
      {warnings.length > 0 && (
        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 12, padding: '14px 18px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: warnings.length > 1 ? 8 : 0 }}>
            <Icon path={ICONS.warn} size={16} color='#d97706' />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#92400e' }}>
              {warnings.length} Alert{warnings.length > 1 ? 's' : ''}
            </span>
          </div>
          {warnings.length > 1 && (
            <ul style={{ margin: 0, paddingLeft: 22, color: '#92400e', fontSize: 13, lineHeight: 1.8 }}>
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
          {warnings.length === 1 && (
            <div style={{ fontSize: 13, color: '#92400e', marginTop: 2 }}>{warnings[0]}</div>
          )}
        </div>
      )}

      {/* ── Important: Action card + Budget Today ─────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 16, marginBottom: 20 }}>

        {/* Latest Layer 3 recommendation — status only; approval happens in Budget Manager */}
        <div style={{ background: decision ? decStyle.bg : '#fff', border: `1.5px solid ${decision ? decStyle.border : '#e5e7eb'}`, borderRadius: 16, padding: '18px 22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12, flexWrap: 'wrap' }}>
            <div style={{ background: '#fff', borderRadius: 9, padding: 8, display: 'flex', border: `1px solid ${decision ? decStyle.border : '#e5e7eb'}` }}>
              <Icon path={ICONS.bulb} size={16} color={decision ? decStyle.color : '#7c3aed'} />
            </div>
            <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Recommendation</span>
            {decision && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 11px', borderRadius: 99, background: '#fff', border: `1px solid ${decStyle.border}`, fontSize: 12, fontWeight: 800, color: decStyle.color }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: decStyle.dot }} />
                {decStyle.label}
              </span>
            )}
            {isActioned && (
              <span style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'capitalize' }}>· {decStatus.replace(/_/g, ' ')}</span>
            )}
          </div>

          {!decision ? (
            <div style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.6 }}>
              No recommendation yet. Open <strong>Budget Manager</strong> and click <strong>Run Review</strong> to generate one.
            </div>
          ) : (
            <>
              {/* What changes */}
              {decType === 'BLOCK' ? (
                <div style={{ fontSize: 13, color: '#991b1b', lineHeight: 1.55 }}>{decision.reason || 'Blocked by a safety check.'}</div>
              ) : changes.length === 0 ? (
                <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.55 }}>
                  No setpoint changes — all values stay the same. {decType === 'APPROVE' ? 'Safe to approve.' : ''}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 4 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>What changes</div>
                  {changes.slice(0, 4).map((c) => (
                    <div key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                      <span style={{ fontWeight: 700, color: '#111827', minWidth: 96 }}>{c.label}</span>
                      <span style={{ color: '#6b7280' }}>{c.current}{c.unit && ` ${c.unit}`}</span>
                      <Icon path={ICONS.arrow} size={13} color='#9ca3af' />
                      <span style={{ fontWeight: 800, color: '#16a34a' }}>{c.final}{c.unit && ` ${c.unit}`}</span>
                    </div>
                  ))}
                  {changes.length > 4 && <div style={{ fontSize: 12, color: '#9ca3af' }}>+{changes.length - 4} more…</div>}
                </div>
              )}

              {/* Why this decision — short explanation */}
              {decType !== 'BLOCK' && decision.reason && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, marginTop: 12, padding: '8px 11px', background: '#fff', border: `1px solid ${decStyle.border}`, borderRadius: 9 }}>
                  <div style={{ flexShrink: 0, marginTop: 1 }}><Icon path={ICONS.bulb} size={13} color={decStyle.color} /></div>
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 800, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginRight: 6 }}>Why</span>
                    <span style={{ fontSize: 12.5, color: '#374151', lineHeight: 1.5 }}>{decision.reason}</span>
                  </div>
                </div>
              )}

              {/* Review & approval happen in the Budget Manager (Layer 3) */}
              {!isActioned && decType !== 'BLOCK' && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, color: '#6b7280' }}>Review the cost impact and approve or reject in the Budget Manager.</span>
                  <button onClick={() => onNavigate && onNavigate('layer3')}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 18px', borderRadius: 9, border: `1px solid ${decStyle.border}`, background: '#fff', color: decStyle.color, fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
                    Review in Budget Manager <Icon path={ICONS.arrow} size={14} color={decStyle.color} />
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* BUDGET TODAY — today's spending vs daily budget */}
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '18px 22px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
            <div style={{ background: '#f0fdf4', borderRadius: 9, padding: 8, display: 'flex' }}>
              <Icon path={ICONS.money} size={16} color='#16a34a' />
            </div>
            <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Budget Today</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 10 }}>
            <span style={{ fontSize: 30, fontWeight: 900, color: '#111827', lineHeight: 1 }}>₪{Number(todaySpend).toFixed(2)}</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: hasDaily ? '#6b7280' : '#9ca3af' }}>
              / {hasDaily ? `₪${Number(dailyBudget).toFixed(2)}` : 'no budget'}
            </span>
          </div>

          {/* progress bar */}
          <div style={{ background: budgetPct != null && budgetPct > 100 ? '#fee2e2' : budgetPct >= 80 ? '#fef3c7' : '#dcfce7', borderRadius: 99, height: 9, overflow: 'hidden', marginBottom: 8 }}>
            <div style={{ width: `${Math.min(100, Math.max(0, budgetPct || 0))}%`, height: '100%', background: budgetColor, borderRadius: 99, transition: 'width 0.5s ease' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12 }}>
            <span style={{ fontWeight: 700, color: budgetColor }}>
              {budgetPct != null ? `${budgetPct.toFixed(1)}% used today` : 'Budget not set'}
            </span>
            <span style={{ color: '#9ca3af' }}>resets at midnight</span>
          </div>

          {!hasDaily && (
            <div style={{ marginTop: 10, fontSize: 11, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '7px 10px', lineHeight: 1.5 }}>
              Set your daily budget in <strong>Budget Manager → Budget Configuration</strong>.
            </div>
          )}
        </div>
      </div>

      {/* ── Plant Health + Plant Growth ──────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20, alignItems: 'stretch' }}>

          {/* Plant Health status */}
          <div style={{ background: hAccentBg, border: `1.5px solid ${hAccentBd}`, borderRadius: 16, padding: '18px 22px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
              <div style={{ background: '#fff', borderRadius: 9, padding: 8, display: 'flex', border: `1px solid ${hAccentBd}` }}>
                <Icon path={ICONS.health} size={16} color={hAccent} />
              </div>
              <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Plant Health</span>
              {hp && (
                <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 11px', borderRadius: 99, background: '#fff', border: `1px solid ${hAccentBd}`, fontSize: 12, fontWeight: 800, color: hAccent }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: hAccent }} />
                  {hHealthy ? 'Healthy' : 'Issues'}
                </span>
              )}
            </div>

            {!hp ? (
              <div style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.6 }}>
                No health check yet. Open <strong>Plant Health</strong> and click <strong>Capture Now</strong>.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                <div style={{ textAlign: 'center', background: '#fff', borderRadius: 8, padding: '12px 6px', border: `1px solid ${hAccentBd}` }}>
                  <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Status</div>
                  <div style={{ fontSize: 17, fontWeight: 900, color: hAccent }}>{hHealthy ? 'Healthy' : 'Issues'}</div>
                </div>
                <div style={{ textAlign: 'center', background: '#fff', borderRadius: 8, padding: '12px 6px', border: '1px solid #e5e7eb' }}>
                  <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Confidence</div>
                  <div style={{ fontSize: 17, fontWeight: 900, color: hAccent }}>{hPct != null ? `${hPct}%` : '—'}</div>
                </div>
                <div style={{ textAlign: 'center', background: '#fff', borderRadius: 8, padding: '12px 6px', border: `1px solid ${hIssues > 0 ? '#fde68a' : '#86efac'}` }}>
                  <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Issues</div>
                  <div style={{ fontSize: 17, fontWeight: 900, color: hIssues > 0 ? '#d97706' : '#16a34a' }}>{hIssues}</div>
                </div>
              </div>
            )}
          </div>

          {/* Plant Growth */}
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '18px 22px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
              <div style={{ background: '#f0fdf4', borderRadius: 9, padding: 8, display: 'flex' }}>
                <Icon path={ICONS.growth} size={16} color='#16a34a' />
              </div>
              <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Plant Growth</span>
            </div>

            {!gd ? (
              <div style={{ fontSize: 13, color: '#6b7280', lineHeight: 1.6 }}>
                No growth measurement yet. Open <strong>Plant Growth</strong> and run an analysis.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                <div style={{ textAlign: 'center', background: '#f9fafb', borderRadius: 8, padding: '12px 6px' }}>
                  <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Growth</div>
                  <div style={{ fontSize: 17, fontWeight: 900, color: gGrowth == null ? '#111827' : gGrowth >= 0 ? '#16a34a' : '#dc2626' }}>
                    {gGrowth != null ? `${gGrowth >= 0 ? '+' : ''}${Number(gGrowth).toFixed(1)}%` : '—'}
                  </div>
                </div>
                <div style={{ textAlign: 'center', background: '#f9fafb', borderRadius: 8, padding: '12px 6px' }}>
                  <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Height</div>
                  <div style={{ fontSize: 17, fontWeight: 900, color: '#111827' }}>{gHeight != null ? Number(gHeight).toFixed(1) : '—'}<span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600 }}> cm</span></div>
                </div>
                <div style={{ textAlign: 'center', background: '#f9fafb', borderRadius: 8, padding: '12px 6px' }}>
                  <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Canopy</div>
                  <div style={{ fontSize: 17, fontWeight: 900, color: '#111827' }}>{gArea != null ? Number(gArea).toFixed(0) : '—'}<span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600 }}> cm²</span></div>
                </div>
              </div>
            )}
          </div>
      </div>

      {/* ── Cost Since Reset ─────────────────────────────────────────────────── */}
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '22px 24px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ background: '#f0fdf4', borderRadius: 9, padding: 8, display: 'flex' }}>
            <Icon path={ICONS.money} size={16} color='#16a34a' />
          </div>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>Cost Since Reset</span>
          <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 99, background: '#f0fdf4', border: '1px solid #bbf7d0', fontSize: 12, fontWeight: 700, color: '#15803d' }}>
            <Icon path={ICONS.cal} size={13} color='#16a34a' />
            {resetLabel ? `Since ${resetLabel}` : 'Reset date not recorded'}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16, alignItems: 'center' }}>
          {/* Total */}
          <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 12, padding: '16px 18px' }}>
            <div style={{ fontSize: 11, color: '#15803d', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>Total Cost</div>
            <div style={{ fontSize: 32, fontWeight: 900, color: '#111827', lineHeight: 1 }}>
              {s.total_cost_nis != null ? `₪${Number(s.total_cost_nis).toFixed(4)}` : '—'}
            </div>
          </div>

          {/* Breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            {[
              { label: 'Electricity', value: s.electricity_cost_nis, icon: ICONS.elec,  iconBg: '#fefce8', iconColor: '#ca8a04' },
              { label: 'Water',       value: s.water_cost_nis,       icon: ICONS.water, iconBg: '#eff6ff', iconColor: '#2563eb' },
              { label: 'Fertilizer',  value: s.fertilizer_cost_nis,  icon: ICONS.fert,  iconBg: '#f0fdf4', iconColor: '#16a34a' },
            ].map(({ label, value, icon, iconBg, iconColor }) => (
              <div key={label} style={{ background: '#f9fafb', borderRadius: 8, padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                  <div style={{ background: iconBg, borderRadius: 6, padding: 5, display: 'flex' }}>
                    <Icon path={icon} size={12} color={iconColor} />
                  </div>
                  <span style={{ fontSize: 12, color: '#6b7280' }}>{label}</span>
                </div>
                <span style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>
                  {value != null ? `₪${Number(value).toFixed(4)}` : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}

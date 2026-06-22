import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';
import { fmtDate, fmtNum } from '../utils/format';

// ── Colour palettes ───────────────────────────────────────────────────────────

const DECISION_STYLE = {
  APPROVE:    { bg: '#dcfce7', color: '#166534', border: '#86efac', label: 'APPROVE',    dot: '#16a34a' },
  MODIFY:     { bg: '#fef9c3', color: '#854d0e', border: '#fde047', label: 'MODIFY',     dot: '#d97706' },
  BLOCK:      { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'BLOCK',      dot: '#dc2626' },
  ALERT_ONLY: { bg: '#fef3c7', color: '#92400e', border: '#fcd34d', label: 'ALERT ONLY', dot: '#f59e0b' },
};

const DOC_STATUS_STYLE = {
  pending_approval: { bg: '#fef9c3', color: '#854d0e', border: '#fde047', label: 'Pending Approval' },
  approved:         { bg: '#dcfce7', color: '#166534', border: '#86efac', label: 'Approved' },
  rejected:         { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'Rejected' },
  blocked:          { bg: '#fce7f3', color: '#9d174d', border: '#f9a8d4', label: 'Blocked' },
  alert_only:       { bg: '#fef3c7', color: '#92400e', border: '#fcd34d', label: 'Alert Only' },
  cancelled:        { bg: '#f3f4f6', color: '#6b7280', border: '#d1d5db', label: 'Cancelled' },
};

const BUDGET_STATUS_STYLE = {
  ok:           { bg: '#f0fdf4', color: '#166534', border: '#86efac', barColor: '#16a34a', label: 'OK' },
  warning:      { bg: '#fffbeb', color: '#854d0e', border: '#fde68a', barColor: '#d97706', label: 'WARNING' },
  over_budget:  { bg: '#fef2f2', color: '#991b1b', border: '#fca5a5', barColor: '#dc2626', label: 'OVER BUDGET' },
  no_budget_set:{ bg: '#f9fafb', color: '#6b7280', border: '#e5e7eb', barColor: '#9ca3af', label: 'NOT SET' },
};

// ── SVG Icon helper ───────────────────────────────────────────────────────────

function Icon({ path, size = 16, color = 'currentColor', strokeWidth = 2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const ICONS = {
  budget:    'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  water:     'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
  electric:  'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  fertilizer:'M12 2a10 10 0 110 20A10 10 0 0112 2zm0 4c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm-4 8c0 2.2 1.8 4 4 4s4-1.8 4-4H8z',
  led:       'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  fan:       'M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z',
  moisture:  'M3 15a4 4 0 004 4h9a5 5 0 10-4.584-7H5a4 4 0 00-2 .5M12 3v3m0 0l2-2m-2 2L10 4',
  check:     'M20 6L9 17l-5-5',
  x:         'M18 6L6 18M6 6l12 12',
  run:       'M5 3l14 9-14 9V3z',
  flask:     'M9 3h6m-6 0v5l-5 9a1 1 0 00.9 1.5h14.2a1 1 0 00.9-1.5l-5-9V3m-6 0h6',
  settings:  'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  history:   'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  approve:   'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  reject:    'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  info:      'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  arrow:     'M5 12h14M12 5l7 7-7 7',
  advisor:   'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
};

const RISK_STYLE = {
  low:    { bg: '#f0fdf4', color: '#166534', border: '#86efac', label: 'LOW' },
  medium: { bg: '#fffbeb', color: '#854d0e', border: '#fde68a', label: 'MEDIUM' },
  high:   { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'HIGH' },
};

// ── Small reusable components ─────────────────────────────────────────────────

function Badge({ text, style }) {
  const s = style || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db' };
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 700, letterSpacing: '0.03em',
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>
      {text}
    </span>
  );
}

function BudgetBar({ pct, color }) {
  const clamped = Math.min(100, Math.max(0, pct || 0));
  const barColor = color || (pct > 100 ? '#dc2626' : pct >= 80 ? '#d97706' : '#16a34a');
  return (
    <div style={{ background: '#e5e7eb', borderRadius: 99, height: 8, overflow: 'hidden', margin: '6px 0 4px' }}>
      <div style={{ width: `${clamped}%`, height: '100%', background: barColor, borderRadius: 99, transition: 'width 0.5s ease' }} />
    </div>
  );
}

// ── Budget metric card ────────────────────────────────────────────────────────

function BudgetMetricCard({ label, icon, iconBg, iconColor, cost, budget, pct, status, threshold }) {
  const st    = BUDGET_STATUS_STYLE[status] || BUDGET_STATUS_STYLE.no_budget_set;
  const noBudget = !budget || budget <= 0;
  return (
    <div style={{
      background: '#fff', border: `1px solid ${st.border}`,
      borderRadius: 14, padding: '18px 20px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: iconBg, borderRadius: 8, padding: 7, display: 'flex' }}>
            <Icon path={icon} size={16} color={iconColor} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#374151' }}>{label}</span>
        </div>
        <Badge text={st.label} style={st} />
      </div>

      <div style={{ marginBottom: 4 }}>
        <span style={{ fontSize: 22, fontWeight: 800, color: '#111827' }}>
          ₪{fmtNum(cost, 4)}
        </span>
        {!noBudget && (
          <span style={{ fontSize: 13, color: '#9ca3af', marginLeft: 4 }}>
            / ₪{fmtNum(budget, 2)}
          </span>
        )}
      </div>

      {!noBudget && pct != null ? (
        <>
          <BudgetBar pct={pct} color={st.barColor} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ fontWeight: 700, color: st.color }}>{fmtNum(pct, 1)}% used</span>
            <span style={{ color: '#9ca3af' }}>threshold {threshold}%</span>
          </div>
        </>
      ) : (
        <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>No budget set</div>
      )}
    </div>
  );
}

// ── Modification card ─────────────────────────────────────────────────────────

function ModCard({ mod }) {
  const typeConfig = {
    led_power_reduction:     { icon: ICONS.led,      iconBg: '#fefce8', iconColor: '#ca8a04', label: 'LED Reduction' },
    fan_night_reduction:     { icon: ICONS.fan,      iconBg: '#f0fdf4', iconColor: '#16a34a', label: 'Fan Reduction' },
    moisture_target_reduction:{ icon: ICONS.moisture, iconBg: '#eff6ff', iconColor: '#2563eb', label: 'Moisture Target' },
  };
  const cfg = typeConfig[mod.type] || { icon: ICONS.info, iconBg: '#f3f4f6', iconColor: '#6b7280', label: mod.type };

  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '14px 16px', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ background: cfg.iconBg, borderRadius: 8, padding: 7, display: 'flex' }}>
            <Icon path={cfg.icon} size={15} color={cfg.iconColor} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#111827' }}>{cfg.label}</div>
            <div style={{ fontSize: 11, color: '#6b7280' }}>{mod.parameter}</div>
          </div>
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 99, background: mod.savings_impact === 'medium' ? '#fef3c7' : '#f3f4f6', color: mod.savings_impact === 'medium' ? '#92400e' : '#6b7280' }}>
          {mod.savings_impact || 'low'} savings
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, padding: '8px 12px', background: '#f9fafb', borderRadius: 8 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: '#374151' }}>{mod.current_value}</span>
        <Icon path={ICONS.arrow} size={16} color='#9ca3af' />
        <span style={{ fontSize: 15, fontWeight: 800, color: '#16a34a' }}>{mod.proposed_value}</span>
        {mod.unit && <span style={{ fontSize: 12, color: '#9ca3af' }}>{mod.unit}</span>}
      </div>

      <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.5 }}>{mod.reason}</div>
      {mod.safety && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 8, padding: '6px 10px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6 }}>
          <Icon path={ICONS.info} size={13} color='#d97706' />
          <span style={{ fontSize: 11, color: '#92400e', lineHeight: 1.4 }}>{mod.safety}</span>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Layer3Decision() {
  const [decision,      setDecision]      = useState(null);
  const [l3Status,      setL3Status]      = useState(null);
  const [budgetCfg,     setBudgetCfg]     = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg,     setActionMsg]     = useState(null);
  const [error,         setError]         = useState(null);

  const [confirmOpen,   setConfirmOpen]   = useState(false);
  const [rejectOpen,    setRejectOpen]    = useState(false);
  const [rejectReason,  setRejectReason]  = useState('');

  const [budgetFormOpen, setBudgetFormOpen] = useState(false);
  const [budgetForm,     setBudgetForm]     = useState({});

  const [currentSetpoints, setCurrentSetpoints] = useState(null);
  const [layer2Rec,         setLayer2Rec]        = useState(null);

  const [testPanelOpen, setTestPanelOpen] = useState(false);
  const [testLoading,   setTestLoading]   = useState(false);
  const [testResult,    setTestResult]    = useState(null);
  const [testCosts,     setTestCosts]     = useState({
    water_cost_nis: '0.4', electricity_cost_nis: '0.77', fertilizer_cost_nis: '0.01',
  });

  const safeJson = async (res) => {
    const text = await res.text();
    try { return JSON.parse(text); } catch { return null; }
  };

  const fetchAll = useCallback(async () => {
    try {
      const [latestRes, cfgRes, spRes, l2Res] = await Promise.all([
        fetch(`${API_BASE_URL}/layer3/latest`,           { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/layer3/budget-config`,    { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/setpoints`,               { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/ai-advisor/latest`,       { cache: 'no-store' }),
      ]);
      const latest  = await safeJson(latestRes);
      const cfg     = await safeJson(cfgRes);
      const sp      = await safeJson(spRes);
      const l2      = await safeJson(l2Res);

      if (latest?.success) { setDecision(latest.decision); setL3Status(latest.status); }
      if (cfg?.success)     setBudgetCfg(cfg.config);
      if (sp?.success)      setCurrentSetpoints(sp.setpoints);
      if (l2?.success)      setLayer2Rec(l2.recommendation);
      setError(null);
    } catch (e) {
      setError('Cannot reach backend: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 15000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line

  const handleRunLayer3 = async () => {
    setActionLoading(true); setActionMsg(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/layer3/run`, { method: 'POST' });
      const data = await safeJson(res);
      if (data?.success) { setActionMsg({ type: 'ok', text: 'Layer 3 review started. Refreshing in 5s…' }); setTimeout(fetchAll, 5000); }
      else setActionMsg({ type: 'err', text: data?.error || 'Run failed.' });
    } catch (e) { setActionMsg({ type: 'err', text: 'Connection error: ' + e.message }); }
    finally { setActionLoading(false); }
  };

  const handleApprove = async () => {
    setConfirmOpen(false); setActionLoading(true); setActionMsg(null);
    try {
      const body = decision?.decision_id ? { decision_id: decision.decision_id } : {};
      const res  = await fetch(`${API_BASE_URL}/layer3/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await safeJson(res);
      if (data?.success) { const applied = (data.applied || []).map(a => a.parameter).join(', ') || 'none'; setActionMsg({ type: 'ok', text: `Approved. Applied: ${applied}.` }); await fetchAll(); }
      else setActionMsg({ type: 'err', text: data?.error || 'Approve failed.' });
    } catch (e) { setActionMsg({ type: 'err', text: 'Connection error: ' + e.message }); }
    finally { setActionLoading(false); }
  };

  const handleReject = async () => {
    setRejectOpen(false); setActionLoading(true); setActionMsg(null);
    try {
      const body = { reason: rejectReason || 'Rejected by user.', ...(decision?.decision_id ? { decision_id: decision.decision_id } : {}) };
      const res  = await fetch(`${API_BASE_URL}/layer3/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await safeJson(res);
      if (data?.success) { setActionMsg({ type: 'ok', text: 'Decision rejected. No changes applied.' }); setRejectReason(''); await fetchAll(); }
      else setActionMsg({ type: 'err', text: data?.error || 'Reject failed.' });
    } catch (e) { setActionMsg({ type: 'err', text: 'Connection error: ' + e.message }); }
    finally { setActionLoading(false); }
  };

  const handleBudgetSave = async () => {
    setActionLoading(true); setActionMsg(null);
    try {
      const payloadData = {
        daily_budget: parseFloat(budgetForm.daily_budget), monthly_budget: parseFloat(budgetForm.monthly_budget),
        water_budget: parseFloat(budgetForm.water_budget), electricity_budget: parseFloat(budgetForm.electricity_budget),
        fertilizer_budget: parseFloat(budgetForm.fertilizer_budget), warning_threshold_pct: parseFloat(budgetForm.warning_threshold_pct),
      };
      const res  = await fetch(`${API_BASE_URL}/layer3/budget-config`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payloadData) });
      const data = await safeJson(res);
      if (data?.success) {
        setBudgetCfg(data.config);
        setBudgetForm({ daily_budget: String(data.config.daily_budget ?? ''), monthly_budget: String(data.config.monthly_budget ?? ''), water_budget: String(data.config.water_budget ?? ''), electricity_budget: String(data.config.electricity_budget ?? ''), fertilizer_budget: String(data.config.fertilizer_budget ?? ''), warning_threshold_pct: String(data.config.warning_threshold_pct ?? '') });
        setActionMsg({ type: 'ok', text: 'Budget configuration saved.' }); setBudgetFormOpen(false);
      } else setActionMsg({ type: 'err', text: data?.error || 'Save failed.' });
    } catch (e) { setActionMsg({ type: 'err', text: 'Connection error: ' + e.message }); }
    finally { setActionLoading(false); }
  };

  const handleRunTest = async () => {
    setTestLoading(true); setTestResult(null);
    try {
      const costs = { water_cost_nis: parseFloat(testCosts.water_cost_nis) || 0, electricity_cost_nis: parseFloat(testCosts.electricity_cost_nis) || 0, fertilizer_cost_nis: parseFloat(testCosts.fertilizer_cost_nis) || 0 };
      const res  = await fetch(`${API_BASE_URL}/layer3/run-test`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ costs }) });
      const data = await safeJson(res);
      if (data?.success) setTestResult(data); else setTestResult({ error: data?.error || 'Test run failed.' });
    } catch (e) { setTestResult({ error: 'Connection error: ' + e.message }); }
    finally { setTestLoading(false); }
  };

  // ── Derived state ──────────────────────────────────────────────────────────

  const decisionType = decision?.decision;
  const docStatus    = decision?.status;
  const isActioned   = docStatus && ['approved', 'rejected', 'cancelled'].includes(docStatus);
  const canApprove   = !isActioned && decisionType !== 'BLOCK' && decision !== null;
  const canReject    = !isActioned && decision !== null;

  const gateResults = decision?.gate_results || {};
  const mods        = decision?.proposed_modifications || [];
  const budgetInfo  = gateResults.budget || {};
  const todayCosts  = budgetInfo.today_costs || {};
  const breakdown   = budgetInfo.resource_breakdown || [];

  const decStyle = DECISION_STYLE[decisionType] || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db', label: decisionType || '—', dot: '#9ca3af' };
  const stStyle  = DOC_STATUS_STYLE[docStatus]  || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db', label: docStatus || '—' };

  const getResourceBreakdown = (name) => breakdown.find(r => r.resource === name) || {};

  // ── Plain-English decision summary ────────────────────────────────────────
  // The raw AI `reason` is a dense run-on sentence. We lead with a clear headline
  // and a row of scannable fact chips, and keep the AI's own wording as a small
  // detail line so no information is lost.
  const DECISION_HEADLINE = {
    APPROVE:    'All costs are within budget — this recommendation is ready to apply.',
    MODIFY:     'Costs are under pressure. The cost-saving changes below keep you within budget.',
    ALERT_ONLY: 'Costs are under pressure, but no safe savings are available right now — this is for your awareness only.',
    BLOCK:      "This recommendation can't be applied right now. See the details below.",
  };
  const headline = DECISION_HEADLINE[decisionType] || decision?.reason || '';

  // Layer 2 recommendation age (hours) — used for the freshness chip.
  let l2AgeH = null;
  if (layer2Rec?.created_at) {
    const t = new Date(layer2Rec.created_at).getTime();
    if (!Number.isNaN(t)) l2AgeH = Math.max(0, (Date.now() - t) / 3600000);
  }

  const cap = s => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const budgetPct  = decision?.budget_usage_pct;
  const totalCost  = todayCosts.total_cost_nis;
  const dailyBudg  = budgetInfo.daily_budget;
  const driver     = decision?.main_cost_driver;
  const budgetTone = budgetInfo.status === 'over_budget' ? { bg: '#fee2e2', color: '#991b1b' }
                   : budgetInfo.status === 'warning'     ? { bg: '#fef3c7', color: '#92400e' }
                   : { bg: '#dcfce7', color: '#166534' };

  const decisionChips = [];
  if (budgetPct != null)
    decisionChips.push({ label: 'Budget used', value: `${fmtNum(budgetPct, 1)}%`, tone: budgetTone });
  if (totalCost != null && dailyBudg != null)
    decisionChips.push({ label: 'Spent today', value: `₪${fmtNum(totalCost, 4)} / ₪${fmtNum(dailyBudg, 2)}`, tone: { bg: '#eff6ff', color: '#1e40af' } });
  if (driver)
    decisionChips.push({ label: 'Main cost', value: cap(driver), tone: { bg: '#f3e8ff', color: '#6b21a8' } });
  if (l2AgeH != null)
    decisionChips.push({
      label: 'Recommendation',
      value: l2AgeH <= 48 ? `Fresh · ${fmtNum(l2AgeH, 1)}h old` : `Stale · ${fmtNum(l2AgeH, 1)}h old`,
      tone: l2AgeH <= 48 ? { bg: '#dcfce7', color: '#166534' } : { bg: '#fee2e2', color: '#991b1b' },
    });

  if (loading) return (
    <div style={{ padding: 60, textAlign: 'center' }}>
      <div style={{ width: 40, height: 40, border: '3px solid #e5e7eb', borderTopColor: '#2563eb', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
      <div style={{ color: '#6b7280', fontSize: 14 }}>Loading Budget Manager…</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );

  // ── RENDER ─────────────────────────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '8px 0' }}>

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: 'linear-gradient(135deg, #2563eb, #1d4ed8)', borderRadius: 12, padding: 10, display: 'flex' }}>
            <Icon path={ICONS.budget} size={22} color='#fff' />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#111827' }}>Budget Manager</h2>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
              Layer 3 · Reviews the Layer 2 recommendation, checks cost &amp; budget, and makes the final decision
              {l3Status?.last_run_at && <> · Last run: {fmtDate(l3Status.last_run_at)}</>}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => { setTestPanelOpen(v => !v); setTestResult(null); }}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8, border: `1px solid ${testPanelOpen ? '#d97706' : '#e5e7eb'}`, cursor: 'pointer', background: testPanelOpen ? '#fef3c7' : '#fff', color: testPanelOpen ? '#92400e' : '#374151', fontWeight: 600, fontSize: 13 }}>
            <Icon path={ICONS.flask} size={14} color={testPanelOpen ? '#d97706' : '#6b7280'} />
            Test Mode
          </button>
          <button onClick={handleRunLayer3} disabled={actionLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: 'none', cursor: actionLoading ? 'not-allowed' : 'pointer', background: actionLoading ? '#93c5fd' : '#2563eb', color: '#fff', fontWeight: 700, fontSize: 13 }}>
            <Icon path={ICONS.run} size={13} color='#fff' />
            {actionLoading ? 'Running…' : 'Run Review'}
          </button>
        </div>
      </div>

      {/* ── Banners ───────────────────────────────────────────────────────────── */}
      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 10, padding: '12px 16px', marginBottom: 16, color: '#991b1b', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon path={ICONS.reject} size={16} color='#dc2626' /> {error}
        </div>
      )}
      {actionMsg && (
        <div style={{ background: actionMsg.type === 'ok' ? '#f0fdf4' : '#fee2e2', border: `1px solid ${actionMsg.type === 'ok' ? '#86efac' : '#fca5a5'}`, borderRadius: 10, padding: '12px 16px', marginBottom: 16, color: actionMsg.type === 'ok' ? '#166534' : '#991b1b', fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon path={actionMsg.type === 'ok' ? ICONS.approve : ICONS.reject} size={16} color={actionMsg.type === 'ok' ? '#16a34a' : '#dc2626'} />
            {actionMsg.text}
          </div>
          <button onClick={() => setActionMsg(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'inherit', lineHeight: 1 }}>×</button>
        </div>
      )}

      {/* ── Recommendation received from Layer 2 ──────────────────────────────── */}
      {layer2Rec && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 16, padding: '18px 22px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ background: '#f5f3ff', borderRadius: 10, padding: 8, display: 'flex' }}>
                <Icon path={ICONS.advisor} size={18} color='#7c3aed' />
              </div>
              <div>
                <div style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>Recommendation Received from Layer 2</div>
                <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 1 }}>
                  From the AI Setpoint Advisor
                  {layer2Rec.created_at && <> · {fmtDate(layer2Rec.created_at)}</>}
                </div>
              </div>
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 99, background: '#f5f3ff', color: '#7c3aed', border: '1px solid #ddd6fe' }}>
              {layer2Rec.changes?.length || 0} change{(layer2Rec.changes?.length || 0) !== 1 ? 's' : ''}
            </span>
          </div>

          {(layer2Rec.summary || layer2Rec.detailed_explanation) && (
            <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, background: '#f9fafb', border: '1px solid #f3f4f6', borderRadius: 10, padding: '12px 14px', marginBottom: 14 }}>
              {layer2Rec.summary || layer2Rec.detailed_explanation}
            </div>
          )}

          {layer2Rec.changes?.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e5e7eb', background: '#f9fafb' }}>
                    {['Parameter', 'Current', 'Proposed', 'Difference', 'Risk'].map(h => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#374151', fontWeight: 700, fontSize: 12, whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {layer2Rec.changes.map((c, i) => {
                    const diff = c.difference != null ? c.difference
                      : (c.recommended_value != null && c.current_value != null ? Number(c.recommended_value) - Number(c.current_value) : null);
                    const diffStr   = diff != null ? (diff > 0 ? `▲ +${fmtNum(diff, 2)}` : diff < 0 ? `▼ ${fmtNum(diff, 2)}` : '—') : '—';
                    const diffColor = diff > 0 ? '#16a34a' : diff < 0 ? '#dc2626' : '#9ca3af';
                    const rk = RISK_STYLE[c.risk_level] || RISK_STYLE.low;
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6', background: i % 2 === 0 ? '#fff' : '#f9fafb' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600, color: '#111827' }}>
                          {c.parameter}
                          {c.clamped && <span style={{ marginLeft: 8, fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 99, background: '#fef9c3', color: '#854d0e', border: '1px solid #fde047' }}>CLAMPED</span>}
                        </td>
                        <td style={{ padding: '8px 12px', color: '#6b7280' }}>{fmtNum(c.current_value)}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 800, color: '#15803d' }}>{fmtNum(c.recommended_value)}</td>
                        <td style={{ padding: '8px 12px', fontWeight: 700, color: diffColor, whiteSpace: 'nowrap' }}>{diffStr}</td>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ display: 'inline-block', padding: '2px 9px', borderRadius: 99, fontSize: 11, fontWeight: 700, background: rk.bg, color: rk.color, border: `1px solid ${rk.border}` }}>{rk.label}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ fontSize: 13, color: '#9ca3af', padding: '12px 0' }}>Layer 2 did not recommend any setpoint changes.</div>
          )}

          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 12 }}>
            Cost impact and budget fit for these changes are shown in the budget breakdown below. The final decision is made here in the Budget Manager.
          </div>
        </div>
      )}

      {/* ── Decision hero ─────────────────────────────────────────────────────── */}
      {decision && (
        <div style={{ background: decStyle.bg, border: `1px solid ${decStyle.border}`, borderRadius: 16, padding: '20px 24px', marginBottom: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: decStyle.dot, flexShrink: 0 }} />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 18, fontWeight: 800, color: decStyle.color }}>{decStyle.label}</span>
                <Badge text={stStyle.label} style={stStyle} />
              </div>
              <div style={{ fontSize: 14, color: decStyle.color, fontWeight: 600, lineHeight: 1.45, maxWidth: 640 }}>{headline}</div>
              {decisionChips.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                  {decisionChips.map((chip, i) => (
                    <span key={i} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, padding: '4px 10px', borderRadius: 99, background: chip.tone.bg, color: chip.tone.color, fontSize: 12, fontWeight: 600 }}>
                      <span style={{ opacity: 0.7, fontWeight: 500 }}>{chip.label}:</span>{chip.value}
                    </span>
                  ))}
                </div>
              )}
              {decision.reason && headline !== decision.reason && (
                <div style={{ fontSize: 12, color: decStyle.color, opacity: 0.7, lineHeight: 1.5, maxWidth: 640, marginTop: 10 }}>
                  <span style={{ fontWeight: 700 }}>Why: </span>{decision.reason}
                </div>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            {canApprove && (
              <button onClick={() => setConfirmOpen(true)} disabled={actionLoading}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', borderRadius: 10, border: 'none', background: '#16a34a', color: '#fff', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}>
                <Icon path={ICONS.check} size={14} color='#fff' /> Approve
              </button>
            )}
            {canReject && (
              <button onClick={() => setRejectOpen(true)} disabled={actionLoading}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', borderRadius: 10, border: '1px solid #fca5a5', background: '#fff', color: '#dc2626', fontWeight: 700, fontSize: 14, cursor: 'pointer' }}>
                <Icon path={ICONS.x} size={14} color='#dc2626' /> Reject
              </button>
            )}
          </div>
        </div>
      )}

      {!decision && (
        <div style={{ background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 16, padding: '32px', marginBottom: 20, textAlign: 'center' }}>
          <Icon path={ICONS.budget} size={32} color='#9ca3af' />
          <div style={{ color: '#6b7280', fontSize: 14, marginTop: 12 }}>No budget review has run yet. Click <strong>Run Review</strong> to start.</div>
        </div>
      )}

      {/* ── Two columns: daily budgets (left) · final review (right) ──────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 16, marginBottom: 20, alignItems: 'start' }}>

        {/* LEFT: daily budget cards (Total Daily, Water, Electricity, Fertilizer) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Total daily */}
        {(() => {
          const pct = decision?.budget_usage_pct;
          const status = pct == null ? 'no_budget_set' : pct > 100 ? 'over_budget' : pct >= (budgetCfg?.warning_threshold_pct || 80) ? 'warning' : 'ok';
          return (
            <BudgetMetricCard
              label="Total Daily" icon={ICONS.budget} iconBg="#eff6ff" iconColor="#2563eb"
              cost={todayCosts.total_cost_nis ?? 0}
              budget={budgetInfo.daily_budget}
              pct={pct}
              status={status}
              threshold={budgetCfg?.warning_threshold_pct || 80}
            />
          );
        })()}
        {/* Water */}
        {(() => {
          const r = getResourceBreakdown('water');
          return (
            <BudgetMetricCard
              label="Water" icon={ICONS.water} iconBg="#eff6ff" iconColor="#3b82f6"
              cost={r.current_cost_nis ?? todayCosts.water_cost_nis ?? 0}
              budget={r.daily_budget_nis}
              pct={r.usage_pct}
              status={r.status || 'no_budget_set'}
              threshold={r.threshold_pct || budgetCfg?.warning_threshold_pct || 80}
            />
          );
        })()}
        {/* Electricity */}
        {(() => {
          const r = getResourceBreakdown('electricity');
          return (
            <BudgetMetricCard
              label="Electricity" icon={ICONS.electric} iconBg="#fefce8" iconColor="#ca8a04"
              cost={r.current_cost_nis ?? todayCosts.electricity_cost_nis ?? 0}
              budget={r.daily_budget_nis}
              pct={r.usage_pct}
              status={r.status || 'no_budget_set'}
              threshold={r.threshold_pct || budgetCfg?.warning_threshold_pct || 80}
            />
          );
        })()}
        {/* Fertilizer */}
        {(() => {
          const r = getResourceBreakdown('fertilizer');
          return (
            <BudgetMetricCard
              label="Fertilizer" icon={ICONS.fertilizer} iconBg="#f0fdf4" iconColor="#16a34a"
              cost={r.current_cost_nis ?? todayCosts.fertilizer_cost_nis ?? 0}
              budget={r.daily_budget_nis}
              pct={r.usage_pct}
              status={r.status || 'no_budget_set'}
              threshold={r.threshold_pct || budgetCfg?.warning_threshold_pct || 80}
            />
          );
        })()}
        </div>{/* end LEFT column */}

        {/* RIGHT: proposed cost-saving changes + final setpoint review */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Proposed modifications ────────────────────────────────────────────── */}
      {mods.length > 0 && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, padding: '18px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <div style={{ background: '#fef3c7', borderRadius: 8, padding: 7, display: 'flex' }}>
              <Icon path={ICONS.settings} size={15} color='#d97706' />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#111827' }}>Proposed Cost-Saving Changes</div>
              <div style={{ fontSize: 11, color: '#9ca3af' }}>{mods.length} modification{mods.length > 1 ? 's' : ''} — requires your approval</div>
            </div>
          </div>
          {mods.map((m, i) => <ModCard key={i} mod={m} />)}
        </div>
      )}

      {/* ── Final Setpoints Preview ───────────────────────────────────────────── */}
      {decision && currentSetpoints && (() => {
        const PARAMS = [
          { key: 'light',         label: 'Light (LED)',          unit: 'units' },
          { key: 'soil_moisture', label: 'Soil Moisture Target', unit: '%'     },
          { key: 'soil_ec',       label: 'Soil EC Target',       unit: 'µS/cm' },
          { key: 'soil_ph',       label: 'Soil pH Target',       unit: ''      },
          { key: 'temperature',   label: 'Air Temperature',      unit: '°C'    },
          { key: 'humidity',      label: 'Air Humidity',         unit: '%'     },
          { key: 'fan_day_duty',  label: 'Fan Day Duty',         unit: '/4095' },
          { key: 'fan_night_duty',label: 'Fan Night Duty',       unit: '/4095' },
          { key: 'soil_temp',     label: 'Soil Temp Target',     unit: '°C'    },
        ];
        const L2_LABEL_MAP = { 'soil ph':'soil_ph','soil ec':'soil_ec','soil moisture':'soil_moisture','light':'light','light setpoint':'light','temperature':'temperature','air temperature':'temperature','humidity':'humidity','fan day duty':'fan_day_duty','fan night duty':'fan_night_duty','soil temperature':'soil_temp' };
        const L3_PARAM_MAP = { 'light_setpoint':'light','soil_moisture_setpoint':'soil_moisture','soil_ec_setpoint':'soil_ec','fan_day_duty':'fan_day_duty','fan_night_duty':'fan_night_duty' };
        const l2Values = {};
        const l2Current = {};   // setpoint snapshot captured when Layer 2 ran (same source as the Proposed Changes table)
        if (layer2Rec?.changes) layer2Rec.changes.forEach(c => {
          const k = L2_LABEL_MAP[c.parameter?.toLowerCase()];
          if (k) {
            l2Values[k] = c.recommended_value;
            if (c.current_value != null) l2Current[k] = c.current_value;
          }
        });
        const l3Mods = {};
        const l3Current = {};   // baseline the Budget Manager saw when it proposed a modification
        (decision.proposed_modifications || []).forEach(m => {
          const k = L3_PARAM_MAP[m.parameter] || m.parameter;
          l3Mods[k] = m.proposed_value;
          if (m.current_value != null) l3Current[k] = m.current_value;
        });
        const rows = PARAMS.map(p => {
          // "Current" must be the value before this workflow ran — the Layer 2 snapshot
          // (matching the Proposed Changes table), then the Layer 3 baseline, then the live
          // setpoint as a last resort. Using the live setpoint directly is wrong: once a
          // decision is approved the live value moves to the applied figure, which made the
          // preview contradict the Proposed Changes table and hide the real difference.
          const current = l2Current[p.key] !== undefined ? l2Current[p.key]
                        : l3Current[p.key] !== undefined ? l3Current[p.key]
                        : currentSetpoints[p.key];
          const l2val   = l2Values[p.key];
          const l3val   = l3Mods[p.key];
          const final   = l3val !== undefined ? l3val : (l2val !== undefined ? l2val : current);
          const source  = l3val !== undefined ? 'l3_modified' : l2val !== undefined ? 'l2_changed' : 'unchanged';
          const diff    = final !== undefined && current !== undefined ? Number(final) - Number(current) : null;
          return { ...p, current, l2val, l3val, final, source, diff };
        });
        const sourceStyle = { l3_modified: { bg: '#fef3c7', color: '#92400e', label: 'L3 Modified' }, l2_changed: { bg: '#dbeafe', color: '#1e40af', label: 'L2 Changed' }, unchanged: { bg: '#f3f4f6', color: '#6b7280', label: 'Unchanged' } };
        const hasChanges = rows.some(r => r.source !== 'unchanged');
        return (
          <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, padding: '18px 20px', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ background: '#eff6ff', borderRadius: 8, padding: 7, display: 'flex' }}>
                <Icon path={ICONS.arrow} size={15} color='#2563eb' />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#111827' }}>Final Setpoints Preview</div>
                <div style={{ fontSize: 11, color: '#9ca3af' }}>What gets applied if you Approve</div>
              </div>
            </div>
            <div style={{ fontSize: 12, color: '#6b7280', margin: '10px 0 14px', padding: '8px 12px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 8 }}>
              Priority: <strong>L3 Modified</strong> overrides <strong>L2 Changed</strong> overrides current. Nothing changes until you click Approve.
            </div>
            {!hasChanges && <div style={{ color: '#9ca3af', fontSize: 13, marginBottom: 8 }}>No setpoint changes proposed — all values remain at current.</div>}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e5e7eb', background: '#f9fafb' }}>
                    {['Parameter', 'Current', 'Layer 2', 'After Approve', 'Change', 'Source'].map(h => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#374151', fontWeight: 700, whiteSpace: 'nowrap', fontSize: 12 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const ss = sourceStyle[r.source];
                    const bg = r.source !== 'unchanged' ? ss.bg : i % 2 === 0 ? '#fff' : '#f9fafb';
                    const diffStr = r.diff !== null ? (r.diff > 0 ? `▲ +${fmtNum(r.diff, 2)}` : r.diff < 0 ? `▼ ${fmtNum(r.diff, 2)}` : '—') : '—';
                    return (
                      <tr key={r.key} style={{ borderBottom: '1px solid #f3f4f6', background: bg }}>
                        <td style={{ padding: '7px 12px', fontWeight: 600, color: '#111827', whiteSpace: 'nowrap' }}>{r.label}</td>
                        <td style={{ padding: '7px 12px', color: '#374151' }}>{r.current !== undefined ? `${fmtNum(r.current, 1)} ${r.unit}` : '—'}</td>
                        <td style={{ padding: '7px 12px', color: r.l2val !== undefined ? '#1e40af' : '#9ca3af', fontWeight: r.l2val !== undefined ? 700 : 400 }}>{r.l2val !== undefined ? `${fmtNum(r.l2val, 1)} ${r.unit}` : '—'}</td>
                        <td style={{ padding: '7px 12px', fontWeight: 700, color: r.source !== 'unchanged' ? '#111827' : '#9ca3af' }}>{r.final !== undefined ? `${fmtNum(r.final, 1)} ${r.unit}` : '—'}</td>
                        <td style={{ padding: '7px 12px', fontWeight: 700, color: r.diff > 0 ? '#16a34a' : r.diff < 0 ? '#dc2626' : '#9ca3af', whiteSpace: 'nowrap' }}>{r.source !== 'unchanged' ? diffStr : '—'}</td>
                        <td style={{ padding: '7px 12px' }}>
                          {r.source !== 'unchanged' ? (
                            <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 700, background: ss.bg, color: ss.color }}>{ss.label}</span>
                          ) : (
                            <span style={{ color: '#d1d5db', fontSize: 12 }}>—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

        </div>{/* end RIGHT column */}
      </div>{/* end two-column grid */}

      {/* ── Budget Configuration ──────────────────────────────────────────────── */}
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, padding: '18px 20px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: budgetCfg && !budgetFormOpen ? 14 : 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ background: '#f3f4f6', borderRadius: 8, padding: 7, display: 'flex' }}>
              <Icon path={ICONS.settings} size={15} color='#374151' />
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#111827' }}>Budget Configuration</div>
          </div>
          <button onClick={() => { if (!budgetFormOpen && budgetCfg) setBudgetForm({ daily_budget: String(budgetCfg.daily_budget ?? ''), monthly_budget: String(budgetCfg.monthly_budget ?? ''), water_budget: String(budgetCfg.water_budget ?? ''), electricity_budget: String(budgetCfg.electricity_budget ?? ''), fertilizer_budget: String(budgetCfg.fertilizer_budget ?? ''), warning_threshold_pct: String(budgetCfg.warning_threshold_pct ?? '') }); setBudgetFormOpen(v => !v); }}
            style={{ padding: '5px 14px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: 12, fontWeight: 600, cursor: 'pointer', color: '#374151' }}>
            {budgetFormOpen ? 'Cancel' : 'Edit'}
          </button>
        </div>
        {budgetCfg && !budgetFormOpen && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
            {[
              { label: 'Total Daily',    value: `₪${fmtNum(budgetCfg.daily_budget, 2)}`,       icon: ICONS.budget,     ic: '#2563eb', ib: '#eff6ff' },
              { label: 'Water / Day',    value: `₪${fmtNum(budgetCfg.water_budget, 2)}`,        icon: ICONS.water,      ic: '#3b82f6', ib: '#eff6ff' },
              { label: 'Electricity/Day',value: `₪${fmtNum(budgetCfg.electricity_budget, 2)}`,  icon: ICONS.electric,   ic: '#ca8a04', ib: '#fefce8' },
              { label: 'Fertilizer/Day', value: `₪${fmtNum(budgetCfg.fertilizer_budget, 2)}`,   icon: ICONS.fertilizer, ic: '#16a34a', ib: '#f0fdf4' },
              { label: 'Monthly Limit',  value: `₪${fmtNum(budgetCfg.monthly_budget, 2)}`,      icon: ICONS.history,    ic: '#7c3aed', ib: '#f5f3ff' },
              { label: 'Warn Threshold', value: `${budgetCfg.warning_threshold_pct}%`,           icon: ICONS.info,       ic: '#d97706', ib: '#fffbeb' },
            ].map(({ label, value, icon, ic, ib }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#f9fafb', borderRadius: 10, border: '1px solid #f3f4f6' }}>
                <div style={{ background: ib, borderRadius: 7, padding: 6, display: 'flex', flexShrink: 0 }}>
                  <Icon path={icon} size={13} color={ic} />
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#9ca3af' }}>{label}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#111827' }}>{value}</div>
                </div>
              </div>
            ))}
          </div>
        )}
        {budgetFormOpen && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
              {[
                ['daily_budget',          'Total Daily Budget (₪)',     ICONS.budget,     '#2563eb'],
                ['monthly_budget',        'Monthly Budget (₪)',         ICONS.history,    '#7c3aed'],
                ['water_budget',          'Water Budget/day (₪)',       ICONS.water,      '#3b82f6'],
                ['electricity_budget',    'Electricity Budget/day (₪)', ICONS.electric,   '#ca8a04'],
                ['fertilizer_budget',     'Fertilizer Budget/day (₪)',  ICONS.fertilizer, '#16a34a'],
                ['warning_threshold_pct', 'Warning Threshold (%)',      ICONS.info,       '#d97706'],
              ].map(([key, label, icon, color]) => (
                <div key={key}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#374151', marginBottom: 5, fontWeight: 600 }}>
                    <Icon path={icon} size={13} color={color} /> {label}
                  </label>
                  <input type="number" step="0.01" value={budgetForm[key] ?? ''} onChange={e => setBudgetForm(f => ({ ...f, [key]: e.target.value }))}
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, boxSizing: 'border-box', outline: 'none' }} />
                </div>
              ))}
            </div>
            <button onClick={handleBudgetSave} disabled={actionLoading}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 20px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
              <Icon path={ICONS.check} size={14} color='#fff' /> Save Budget Config
            </button>
          </div>
        )}
      </div>

      {/* ── Test Mode Panel ───────────────────────────────────────────────────── */}
      {testPanelOpen && (
        <div style={{ background: '#fffbeb', border: '2px solid #fde68a', borderRadius: 14, padding: '20px 24px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Icon path={ICONS.flask} size={18} color='#d97706' />
            <span style={{ fontSize: 15, fontWeight: 700, color: '#92400e' }}>Test Mode</span>
            <span style={{ fontSize: 11, color: '#92400e', background: '#fde68a', padding: '2px 8px', borderRadius: 99, fontWeight: 600 }}>No DB writes</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
            {[
              ['water_cost_nis', 'Water Cost (₪)', ICONS.water, '#3b82f6'],
              ['electricity_cost_nis', 'Electricity Cost (₪)', ICONS.electric, '#ca8a04'],
              ['fertilizer_cost_nis', 'Fertilizer Cost (₪)', ICONS.fertilizer, '#16a34a'],
            ].map(([key, label, icon, color]) => (
              <div key={key}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#374151', marginBottom: 5, fontWeight: 600 }}>
                  <Icon path={icon} size={12} color={color} /> {label}
                </label>
                <input type="number" step="0.01" value={testCosts[key]} onChange={e => setTestCosts(f => ({ ...f, [key]: e.target.value }))}
                  style={{ width: '100%', padding: '7px 10px', border: '1px solid #fde68a', borderRadius: 8, fontSize: 13, boxSizing: 'border-box', background: '#fff' }} />
              </div>
            ))}
          </div>
          <div style={{ fontSize: 12, color: '#92400e', marginBottom: 12 }}>Budget limits come from your saved budget config above.</div>
          <button onClick={handleRunTest} disabled={testLoading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 18px', borderRadius: 8, border: 'none', background: '#d97706', color: '#fff', fontWeight: 700, fontSize: 13, cursor: testLoading ? 'not-allowed' : 'pointer', opacity: testLoading ? 0.6 : 1 }}>
            <Icon path={ICONS.run} size={13} color='#fff' />
            {testLoading ? 'Running…' : 'Run Test'}
          </button>

          {testResult?.error && (
            <div style={{ marginTop: 14, color: '#991b1b', background: '#fee2e2', borderRadius: 8, padding: '10px 14px', fontSize: 13 }}>{testResult.error}</div>
          )}

          {testResult && !testResult.error && (() => {
            const tr = testResult;
            const tStyle = DECISION_STYLE[tr.decision] || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db', label: tr.decision };
            const tBreakdown = tr.resource_breakdown || [];
            const tMods = tr.proposed_modifications || [];
            return (
              <div style={{ marginTop: 18, borderTop: '1px solid #fde68a', paddingTop: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                  <span style={{ fontSize: 13, color: '#92400e', fontWeight: 600 }}>Result:</span>
                  <Badge text={tStyle.label} style={tStyle} />
                  <span style={{ fontSize: 12, color: '#92400e' }}>{tr.reason}</span>
                </div>
                {tBreakdown.length > 0 && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginBottom: 14 }}>
                    {tBreakdown.map((r, i) => {
                      const st = BUDGET_STATUS_STYLE[r.status] || BUDGET_STATUS_STYLE.no_budget_set;
                      return (
                        <div key={i} style={{ background: st.bg, border: `1px solid ${st.border}`, borderRadius: 10, padding: '10px 14px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: '#374151', textTransform: 'capitalize' }}>{r.resource}</span>
                            <Badge text={st.label} style={st} />
                          </div>
                          <div style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>₪{fmtNum(r.current_cost_nis, 4)}</div>
                          {r.usage_pct != null && (
                            <>
                              <BudgetBar pct={r.usage_pct} color={st.barColor} />
                              <div style={{ fontSize: 11, color: st.color, fontWeight: 700 }}>{fmtNum(r.usage_pct, 1)}% of ₪{fmtNum(r.daily_budget_nis, 2)}</div>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
                {tMods.length > 0 && (
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#92400e', marginBottom: 8 }}>Proposed Modifications ({tMods.length})</div>
                    {tMods.map((m, i) => <ModCard key={i} mod={m} />)}
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* ── Approve modal ─────────────────────────────────────────────────────── */}
      {confirmOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 28, maxWidth: 480, width: '90%', boxShadow: '0 25px 60px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ background: '#f0fdf4', borderRadius: 10, padding: 8, display: 'flex' }}>
                <Icon path={ICONS.approve} size={20} color='#16a34a' />
              </div>
              <h3 style={{ margin: 0, fontSize: 17, color: '#111827' }}>Confirm Approval</h3>
            </div>
            <p style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, margin: '0 0 14px' }}>
              This will apply the approved setpoints to the <strong>live system</strong>. Changes take effect on the next control loop cycle.
            </p>
            {mods.length > 0 && (
              <div style={{ background: '#f9fafb', borderRadius: 8, padding: '10px 14px', marginBottom: 14 }}>
                {mods.map((m, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', fontSize: 13 }}>
                    <Icon path={ICONS.arrow} size={13} color='#16a34a' />
                    <strong>{m.parameter}</strong>: {m.current_value} → <strong style={{ color: '#16a34a' }}>{m.proposed_value}</strong>{m.unit ? ` ${m.unit}` : ''}
                  </div>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmOpen(false)} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 600 }}>Cancel</button>
              <button onClick={handleApprove} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 18px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
                <Icon path={ICONS.check} size={14} color='#fff' /> Yes, Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Reject modal ──────────────────────────────────────────────────────── */}
      {rejectOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 28, maxWidth: 420, width: '90%', boxShadow: '0 25px 60px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ background: '#fee2e2', borderRadius: 10, padding: 8, display: 'flex' }}>
                <Icon path={ICONS.reject} size={20} color='#dc2626' />
              </div>
              <h3 style={{ margin: 0, fontSize: 17, color: '#111827' }}>Reject Decision</h3>
            </div>
            <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 12px' }}>No setpoints will be changed. Optionally enter a reason.</p>
            <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)} placeholder="Reason (optional)" rows={3}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, resize: 'vertical', boxSizing: 'border-box', marginBottom: 14 }} />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button onClick={() => { setRejectOpen(false); setRejectReason(''); }} style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 600 }}>Cancel</button>
              <button onClick={handleReject} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 18px', borderRadius: 8, border: 'none', background: '#dc2626', color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
                <Icon path={ICONS.x} size={14} color='#fff' /> Reject
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

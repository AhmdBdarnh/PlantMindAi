import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';
import { fmtDate, fmtNum } from '../utils/format';

// ── Colour palettes ───────────────────────────────────────────────────────────

const DECISION_STYLE = {
  APPROVE:    { bg: '#dcfce7', color: '#166534', border: '#86efac', label: 'APPROVE' },
  MODIFY:     { bg: '#fef9c3', color: '#854d0e', border: '#fde047', label: 'MODIFY' },
  BLOCK:      { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'BLOCK' },
  ALERT_ONLY: { bg: '#fef3c7', color: '#92400e', border: '#fcd34d', label: 'ALERT ONLY' },
};

const DOC_STATUS_STYLE = {
  pending_approval: { bg: '#fef9c3', color: '#854d0e', border: '#fde047', label: 'Pending Approval' },
  approved:         { bg: '#dcfce7', color: '#166534', border: '#86efac', label: 'Approved' },
  rejected:         { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', label: 'Rejected' },
  blocked:          { bg: '#fce7f3', color: '#9d174d', border: '#f9a8d4', label: 'Blocked' },
  alert_only:       { bg: '#fef3c7', color: '#92400e', border: '#fcd34d', label: 'Alert Only' },
  cancelled:        { bg: '#f3f4f6', color: '#6b7280', border: '#d1d5db', label: 'Cancelled' },
};

const GATE_STYLE = {
  pass:       { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  marginal:   { bg: '#fef9c3', color: '#854d0e', border: '#fde047' },
  fail:       { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
  ok:         { bg: '#dcfce7', color: '#166534', border: '#86efac' },
  warning:    { bg: '#fef9c3', color: '#854d0e', border: '#fde047' },
  over_budget:{ bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
  unknown:    { bg: '#f3f4f6', color: '#6b7280', border: '#d1d5db' },
};

// ── Reusable tiny components ──────────────────────────────────────────────────

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

function Card({ title, children, extra }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12,
      padding: '20px 24px', marginBottom: 20,
    }}>
      {title && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#111827' }}>{title}</h3>
          {extra}
        </div>
      )}
      {children}
    </div>
  );
}

function Row({ label, value, valueStyle }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ color: '#6b7280', fontSize: 13 }}>{label}</span>
      <span style={{ fontWeight: 600, fontSize: 13, color: '#111827', ...valueStyle }}>{value ?? '—'}</span>
    </div>
  );
}

function BudgetBar({ pct }) {
  const clamped = Math.min(100, Math.max(0, pct || 0));
  const color = pct > 100 ? '#dc2626' : pct >= 80 ? '#d97706' : '#16a34a';
  return (
    <div style={{ background: '#f3f4f6', borderRadius: 8, height: 12, overflow: 'hidden', margin: '8px 0' }}>
      <div style={{ width: `${clamped}%`, height: '100%', background: color, borderRadius: 8, transition: 'width 0.4s' }} />
    </div>
  );
}

function GateRow({ label, gate }) {
  if (!gate) return null;
  const st = gate.status || 'unknown';
  const style = GATE_STYLE[st] || GATE_STYLE.unknown;
  return (
    <div style={{ padding: '10px 14px', borderRadius: 8, border: `1px solid ${style.border}`, background: style.bg, marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontWeight: 700, fontSize: 13, color: '#111827' }}>{label}</span>
        <Badge text={st.replace('_', ' ').toUpperCase()} style={style} />
      </div>
      {gate.reason && <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.4 }}>{gate.reason}</div>}
      {gate.stability_score != null && (
        <div style={{ fontSize: 12, color: '#374151', marginTop: 4 }}>
          Stability score: <strong>{fmtNum(gate.stability_score, 2)}</strong>
          {gate.growth_trend && <> &nbsp;|&nbsp; Growth: <strong>{gate.growth_trend}</strong></>}
          {gate.data_age_hours != null && <> &nbsp;|&nbsp; Data age: <strong>{gate.data_age_hours}h</strong></>}
        </div>
      )}
      {gate.failed_sensors?.length > 0 && (
        <ul style={{ margin: '4px 0 0 0', paddingLeft: 16, fontSize: 12, color: '#991b1b' }}>
          {gate.failed_sensors.map((f, i) => (
            <li key={i}>{f.sensor}: {f.issue}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Main page component ───────────────────────────────────────────────────────

export default function Layer3Decision() {
  const [decision,      setDecision]      = useState(null);
  const [l3Status,      setL3Status]      = useState(null);
  const [history,       setHistory]       = useState([]);
  const [budgetCfg,     setBudgetCfg]     = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMsg,     setActionMsg]     = useState(null);
  const [error,         setError]         = useState(null);

  // Approve confirmation dialog state
  const [confirmOpen,   setConfirmOpen]   = useState(false);
  // Reject reason dialog state
  const [rejectOpen,    setRejectOpen]    = useState(false);
  const [rejectReason,  setRejectReason]  = useState('');

  // Budget config form state
  const [budgetFormOpen, setBudgetFormOpen] = useState(false);
  const [budgetForm,     setBudgetForm]     = useState({});

  const safeJson = async (res) => {
    const text = await res.text();
    try { return JSON.parse(text); } catch { return null; }
  };

  const fetchAll = useCallback(async () => {
    try {
      const [latestRes, historyRes, cfgRes] = await Promise.all([
        fetch(`${API_BASE_URL}/layer3/latest`, { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/layer3/history?limit=10`, { cache: 'no-store' }),
        fetch(`${API_BASE_URL}/layer3/budget-config`, { cache: 'no-store' }),
      ]);
      const latest  = await safeJson(latestRes);
      const hist    = await safeJson(historyRes);
      const cfg     = await safeJson(cfgRes);

      if (latest?.success) {
        setDecision(latest.decision);
        setL3Status(latest.status);
      }
      if (hist?.success) setHistory(hist.decisions || []);
      if (cfg?.success)  {
        setBudgetCfg(cfg.config);
        // Do NOT update budgetForm here — the form is initialized when the user
        // clicks Edit. Updating it in the polling loop would overwrite mid-typing values.
      }
      setError(null);
    } catch (e) {
      setError('Cannot reach backend: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 15000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleRunLayer3 = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/layer3/run`, { method: 'POST' });
      const data = await safeJson(res);
      if (data?.success) {
        setActionMsg({ type: 'ok', text: 'Layer 3 review started. Refreshing in 5s…' });
        setTimeout(fetchAll, 5000);
      } else {
        setActionMsg({ type: 'err', text: data?.error || 'Run failed.' });
      }
    } catch (e) {
      setActionMsg({ type: 'err', text: 'Connection error: ' + e.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async () => {
    setConfirmOpen(false);
    setActionLoading(true);
    setActionMsg(null);
    try {
      const body = decision?.decision_id ? { decision_id: decision.decision_id } : {};
      const res  = await fetch(`${API_BASE_URL}/layer3/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await safeJson(res);
      if (data?.success) {
        const applied = (data.applied || []).map(a => a.parameter).join(', ') || 'none';
        setActionMsg({ type: 'ok', text: `Approved. Applied: ${applied}. ${data.message}` });
        await fetchAll();
      } else {
        setActionMsg({ type: 'err', text: data?.error || 'Approve failed.' });
      }
    } catch (e) {
      setActionMsg({ type: 'err', text: 'Connection error: ' + e.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    setRejectOpen(false);
    setActionLoading(true);
    setActionMsg(null);
    try {
      const body = {
        reason: rejectReason || 'Rejected by user.',
        ...(decision?.decision_id ? { decision_id: decision.decision_id } : {}),
      };
      const res  = await fetch(`${API_BASE_URL}/layer3/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await safeJson(res);
      if (data?.success) {
        setActionMsg({ type: 'ok', text: 'Decision rejected. No changes applied.' });
        setRejectReason('');
        await fetchAll();
      } else {
        setActionMsg({ type: 'err', text: data?.error || 'Reject failed.' });
      }
    } catch (e) {
      setActionMsg({ type: 'err', text: 'Connection error: ' + e.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleBudgetSave = async () => {
    setActionLoading(true);
    setActionMsg(null);
    try {
      // Convert string form values to numbers for the API
      const payloadData = {
        daily_budget: parseFloat(budgetForm.daily_budget),
        monthly_budget: parseFloat(budgetForm.monthly_budget),
        water_budget: parseFloat(budgetForm.water_budget),
        electricity_budget: parseFloat(budgetForm.electricity_budget),
        fertilizer_budget: parseFloat(budgetForm.fertilizer_budget),
        warning_threshold_pct: parseFloat(budgetForm.warning_threshold_pct),
      };

      const res  = await fetch(`${API_BASE_URL}/layer3/budget-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payloadData),
      });
      const data = await safeJson(res);
      if (data?.success) {
        setBudgetCfg(data.config);
        // After save, reset form to server values (as strings for editing)
        setBudgetForm({
          daily_budget: String(data.config.daily_budget ?? ''),
          monthly_budget: String(data.config.monthly_budget ?? ''),
          water_budget: String(data.config.water_budget ?? ''),
          electricity_budget: String(data.config.electricity_budget ?? ''),
          fertilizer_budget: String(data.config.fertilizer_budget ?? ''),
          warning_threshold_pct: String(data.config.warning_threshold_pct ?? ''),
        });
        setActionMsg({ type: 'ok', text: 'Budget configuration saved.' });
        setBudgetFormOpen(false);
      } else {
        setActionMsg({ type: 'err', text: data?.error || 'Save failed.' });
      }
    } catch (e) {
      setActionMsg({ type: 'err', text: 'Connection error: ' + e.message });
    } finally {
      setActionLoading(false);
    }
  };

  // ── Derived state ────────────────────────────────────────────────────────

  const decisionType  = decision?.decision;
  const docStatus     = decision?.status;
  const isActioned    = docStatus && ['approved', 'rejected', 'cancelled'].includes(docStatus);
  const canApprove    = !isActioned && decisionType !== 'BLOCK' && decision !== null;
  const canReject     = !isActioned && decision !== null;

  const gateResults  = decision?.gate_results || {};
  const snap         = decision?.sensor_snapshot || {};
  const mods         = decision?.proposed_modifications || [];
  const rc           = decision?.runtime_constraints || {};
  const budgetInfo   = gateResults.budget || {};
  const todayCosts   = budgetInfo.today_costs || {};

  const decStyle = DECISION_STYLE[decisionType] || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db', label: decisionType || '—' };
  const stStyle  = DOC_STATUS_STYLE[docStatus] || { bg: '#f3f4f6', color: '#374151', border: '#d1d5db', label: docStatus || '—' };

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: '#6b7280' }}>
        Loading Layer 3 data…
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>

      {/* Error banner */}
      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 8, padding: '12px 16px', marginBottom: 16, color: '#991b1b', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* Action message */}
      {actionMsg && (
        <div style={{
          background: actionMsg.type === 'ok' ? '#dcfce7' : '#fee2e2',
          border: `1px solid ${actionMsg.type === 'ok' ? '#86efac' : '#fca5a5'}`,
          borderRadius: 8, padding: '12px 16px', marginBottom: 16,
          color: actionMsg.type === 'ok' ? '#166534' : '#991b1b', fontSize: 13,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          {actionMsg.text}
          <button onClick={() => setActionMsg(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'inherit' }}>✕</button>
        </div>
      )}

      {/* ── 1. Status card ─────────────────────────────────────────────────── */}
      <Card
        title="Layer 3 — Budget Manager Status"
        extra={
          <button
            onClick={handleRunLayer3}
            disabled={actionLoading}
            style={{
              padding: '6px 16px', borderRadius: 8, border: 'none', cursor: actionLoading ? 'not-allowed' : 'pointer',
              background: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 13,
              opacity: actionLoading ? 0.6 : 1,
            }}
          >
            {actionLoading ? 'Running…' : '▶ Run Layer 3 Review'}
          </button>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Row label="System Status" value={l3Status?.current_status?.replace(/_/g, ' ') || '—'} />
          <Row label="Last Run" value={fmtDate(l3Status?.last_run_at)} />
          <Row label="Sensor Safety" value={l3Status?.sensor_safety_status?.toUpperCase() || '—'} valueStyle={{ color: l3Status?.sensor_safety_status === 'pass' ? '#16a34a' : '#dc2626' }} />
          <Row label="Plant Health" value={l3Status?.plant_health_status?.toUpperCase() || '—'} />
          <Row label="Budget Status" value={l3Status?.budget_status?.replace(/_/g, ' ').toUpperCase() || '—'} />
          <Row label="Decision ID" value={l3Status?.latest_decision_id?.slice(0, 8) + '…' || '—'} />
        </div>
      </Card>

      {/* ── 2. Layer 2 summary ─────────────────────────────────────────────── */}
      {decision && (
        <Card title="Layer 2 Recommendation Reviewed">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Row label="Recommendation ID" value={decision.layer2_recommendation_id?.slice(0, 20) + '…' || '—'} />
            <Row label="Plant Status" value={decision.plant_status || '—'} />
            <Row label="Stability Score" value={fmtNum(gateResults.plant_health?.stability_score, 2)} />
            <Row label="Growth Trend" value={gateResults.plant_health?.growth_trend || '—'} />
            <Row label="Decision Time" value={fmtDate(decision.timestamp)} />
            <Row label="Data Age" value={gateResults.plant_health?.data_age_hours != null ? `${gateResults.plant_health.data_age_hours}h` : '—'} />
          </div>
        </Card>
      )}

      {/* ── 3. Gate results ────────────────────────────────────────────────── */}
      <Card title="Gate Results">
        {!decision
          ? <div style={{ color: '#6b7280', fontSize: 13 }}>No Layer 3 review has run yet.</div>
          : <>
              <GateRow label="Gate 1 — Sensor Safety" gate={gateResults.sensor_safety} />
              <GateRow label="Gate 2 — Plant Health"  gate={gateResults.plant_health} />
              <GateRow label="Gate 3 — Budget"        gate={gateResults.budget} />
            </>
        }
      </Card>

      {/* ── 4. Sensor snapshot ─────────────────────────────────────────────── */}
      {decision && (
        <Card title="Sensor Snapshot (at time of review)">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <Row label="Soil Moisture" value={snap.soil_moisture != null ? `${fmtNum(snap.soil_moisture, 1)}%` : '—'} />
            <Row label="Soil EC" value={snap.soil_ec != null ? `${fmtNum(snap.soil_ec, 0)} µS/cm` : '—'} />
            <Row label="Soil pH" value={snap.soil_ph != null ? fmtNum(snap.soil_ph, 2) : '—'} />
            <Row label="Air Temp" value={snap.air_temperature != null ? `${fmtNum(snap.air_temperature, 1)}°C` : '—'} />
            <Row label="Air Humidity" value={snap.air_humidity != null ? `${fmtNum(snap.air_humidity, 1)}%` : '—'} />
            <Row label="Soil Temp" value={snap.soil_temperature != null ? `${fmtNum(snap.soil_temperature, 1)}°C` : '—'} />
          </div>
        </Card>
      )}

      {/* ── 5. Budget section ──────────────────────────────────────────────── */}
      <Card title="Daily Budget Usage (today's cost only)">
        {/* Source note — makes it clear these are NOT cumulative totals */}
        <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 12, padding: '6px 10px', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 6 }}>
          These costs are calculated for <strong>today only</strong>, using a midnight baseline from the
          <code style={{ margin: '0 4px', fontSize: 11 }}>daily_costs</code> collection.
          Cumulative totals since reset are shown in the <strong>Resource Consumption</strong> page.
        </div>
        {decision ? (
          <>
            {/* Budget usage bar */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, color: '#374151', fontWeight: 700, marginBottom: 4 }}>
                <span>Budget usage today</span>
                <span>{fmtNum(decision.budget_usage_pct, 1)}%</span>
              </div>
              <BudgetBar pct={decision.budget_usage_pct} />
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                Daily budget: <strong>₪{budgetInfo.daily_budget != null ? fmtNum(budgetInfo.daily_budget, 2) : '—'}</strong>
                &nbsp;|&nbsp; Main cost driver: <strong>{decision.main_cost_driver || '—'}</strong>
              </div>
            </div>

            {/* Per-resource daily cost breakdown */}
            <div style={{ fontWeight: 700, fontSize: 13, color: '#374151', marginBottom: 8 }}>
              Today's cost per resource
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <Row
                label="Water cost today"
                value={`₪${fmtNum(todayCosts.water_cost_nis ?? 0, 4)}`}
              />
              <Row
                label="Electricity cost today"
                value={`₪${fmtNum(todayCosts.electricity_cost_nis ?? 0, 4)}`}
              />
              <Row
                label="Fertilizer cost today"
                value={`₪${fmtNum(todayCosts.fertilizer_cost_nis ?? 0, 4)}`}
              />
              <Row
                label="Total cost today"
                value={`₪${fmtNum(todayCosts.total_cost_nis ?? 0, 4)}`}
                valueStyle={{ color: '#111827', fontWeight: 700 }}
              />
            </div>
          </>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <Row label="Water cost today"       value="₪0.0000" />
            <Row label="Electricity cost today" value="₪0.0000" />
            <Row label="Fertilizer cost today"  value="₪0.0000" />
            <Row label="Total cost today"       value="₪0.0000" />
          </div>
        )}
      </Card>

      {/* ── 6. Final decision ──────────────────────────────────────────────── */}
      {decision && (
        <Card title="Layer 3 Final Decision">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <Badge text={decStyle.label} style={decStyle} />
            <Badge text={stStyle.label} style={stStyle} />
          </div>
          <div style={{ fontSize: 13, color: '#374151', marginBottom: 12, lineHeight: 1.5, background: '#f9fafb', borderRadius: 8, padding: '10px 14px' }}>
            {decision.reason || '—'}
          </div>

          {/* Proposed modifications */}
          {mods.length > 0 && (
            <>
              <div style={{ fontWeight: 700, fontSize: 13, color: '#374151', marginBottom: 8 }}>
                Proposed Modifications ({mods.length})
              </div>
              {mods.map((m, i) => (
                <div key={i} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: '10px 14px', marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <strong style={{ fontSize: 13 }}>{m.parameter}</strong>
                    <span style={{ fontSize: 12, color: '#6b7280' }}>savings: {m.savings_impact || '—'}</span>
                  </div>
                  <div style={{ fontSize: 13, color: '#374151' }}>
                    {m.current_value} → <strong>{m.proposed_value}</strong>
                    {m.unit ? ` ${m.unit}` : ''}
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{m.reason}</div>
                </div>
              ))}
            </>
          )}

          {/* Runtime constraints */}
          {Object.keys(rc).length > 0 && (
            <>
              <div style={{ fontWeight: 700, fontSize: 13, color: '#374151', marginTop: 12, marginBottom: 8 }}>
                Runtime Constraints
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {Object.entries(rc).map(([k, v]) => (
                  <Row key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {/* ── 7. Approve / Reject controls ───────────────────────────────────── */}
      <Card title="Actions">
        {!decision ? (
          <div style={{ color: '#6b7280', fontSize: 13 }}>No decision to act on. Run a Layer 3 review first.</div>
        ) : (
          <>
            {isActioned && (
              <div style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
                This decision has already been <strong>{docStatus}</strong>. No further action available.
              </div>
            )}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button
                onClick={() => setConfirmOpen(true)}
                disabled={!canApprove || actionLoading}
                style={{
                  padding: '8px 24px', borderRadius: 8, border: 'none',
                  background: canApprove ? '#16a34a' : '#d1fae5',
                  color: canApprove ? '#fff' : '#6b7280',
                  fontWeight: 700, fontSize: 14, cursor: canApprove ? 'pointer' : 'not-allowed',
                  opacity: actionLoading ? 0.6 : 1,
                }}
              >
                ✓ Approve
              </button>
              <button
                onClick={() => setRejectOpen(true)}
                disabled={!canReject || actionLoading}
                style={{
                  padding: '8px 24px', borderRadius: 8, border: 'none',
                  background: canReject ? '#dc2626' : '#fee2e2',
                  color: canReject ? '#fff' : '#6b7280',
                  fontWeight: 700, fontSize: 14, cursor: canReject ? 'pointer' : 'not-allowed',
                  opacity: actionLoading ? 0.6 : 1,
                }}
              >
                ✗ Reject
              </button>
            </div>
            {decisionType === 'BLOCK' && !isActioned && (
              <div style={{ marginTop: 10, fontSize: 12, color: '#991b1b', background: '#fee2e2', borderRadius: 6, padding: '8px 12px' }}>
                Approval is disabled — this decision is BLOCK. Resolve the sensor or plant health issue first.
              </div>
            )}
          </>
        )}
      </Card>

      {/* ── 8. Budget config panel ─────────────────────────────────────────── */}
      <Card
        title="Budget Configuration"
        extra={
          <button
            onClick={() => {
              if (!budgetFormOpen && budgetCfg) {
                // Opening Edit mode — initialize the form with current server values as strings
                // to allow typing decimals like "0.5" without intermediate parseFloat eating the dot
                setBudgetForm({
                  daily_budget: String(budgetCfg.daily_budget ?? ''),
                  monthly_budget: String(budgetCfg.monthly_budget ?? ''),
                  water_budget: String(budgetCfg.water_budget ?? ''),
                  electricity_budget: String(budgetCfg.electricity_budget ?? ''),
                  fertilizer_budget: String(budgetCfg.fertilizer_budget ?? ''),
                  warning_threshold_pct: String(budgetCfg.warning_threshold_pct ?? ''),
                });
              }
              setBudgetFormOpen(v => !v);
            }}
            style={{ padding: '4px 14px', borderRadius: 6, border: '1px solid #e5e7eb', background: '#f9fafb', fontSize: 13, cursor: 'pointer' }}
          >
            {budgetFormOpen ? 'Cancel' : 'Edit'}
          </button>
        }
      >
        {budgetCfg && !budgetFormOpen && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Row label="Daily budget" value={`₪${fmtNum(budgetCfg.daily_budget, 2)}`} />
            <Row label="Monthly budget" value={`₪${fmtNum(budgetCfg.monthly_budget, 2)}`} />
            <Row label="Water budget/day" value={`₪${fmtNum(budgetCfg.water_budget, 2)}`} />
            <Row label="Electricity budget/day" value={`₪${fmtNum(budgetCfg.electricity_budget, 2)}`} />
            <Row label="Fertilizer budget/day" value={`₪${fmtNum(budgetCfg.fertilizer_budget, 2)}`} />
            <Row label="Warning threshold" value={`${budgetCfg.warning_threshold_pct}%`} />
            <Row label="Active" value={budgetCfg.active ? 'Yes' : 'No'} />
          </div>
        )}
        {budgetFormOpen && (
          <div>
            {[
              ['daily_budget', 'Daily Budget (₪)', 'number'],
              ['monthly_budget', 'Monthly Budget (₪)', 'number'],
              ['water_budget', 'Water Budget/day (₪)', 'number'],
              ['electricity_budget', 'Electricity Budget/day (₪)', 'number'],
              ['fertilizer_budget', 'Fertilizer Budget/day (₪)', 'number'],
              ['warning_threshold_pct', 'Warning Threshold (%)', 'number'],
            ].map(([key, label, type]) => (
              <div key={key} style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 13, color: '#374151', display: 'block', marginBottom: 4 }}>{label}</label>
                <input
                  type={type}
                  value={budgetForm[key] ?? ''}
                  onChange={e => setBudgetForm(f => ({ ...f, [key]: e.target.value }))}
                  style={{ width: '100%', padding: '7px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
                />
              </div>
            ))}
            <button
              onClick={handleBudgetSave}
              disabled={actionLoading}
              style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}
            >
              Save Budget Config
            </button>
          </div>
        )}
      </Card>

      {/* ── 9. Decision history ─────────────────────────────────────────────── */}
      <Card title="Recent Decision History">
        {history.length === 0 ? (
          <div style={{ color: '#6b7280', fontSize: 13 }}>No history yet.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  {['Time', 'Decision', 'Status', 'Budget %', 'Driver', 'Reason'].map(h => (
                    <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: '#6b7280', fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const ds = DECISION_STYLE[h.decision] || {};
                  const ss = DOC_STATUS_STYLE[h.status] || {};
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '7px 10px', whiteSpace: 'nowrap' }}>{fmtDate(h.timestamp)}</td>
                      <td style={{ padding: '7px 10px' }}><Badge text={h.decision || '—'} style={ds} /></td>
                      <td style={{ padding: '7px 10px' }}><Badge text={ss.label || h.status || '—'} style={ss} /></td>
                      <td style={{ padding: '7px 10px' }}>{h.budget_usage_pct != null ? `${fmtNum(h.budget_usage_pct, 1)}%` : '—'}</td>
                      <td style={{ padding: '7px 10px' }}>{h.main_cost_driver || '—'}</td>
                      <td style={{ padding: '7px 10px', maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={h.reason}>{h.reason || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Approve confirmation modal ─────────────────────────────────────── */}
      {confirmOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 28, maxWidth: 480, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 17, color: '#111827' }}>Confirm Approval</h3>
            <p style={{ fontSize: 14, color: '#374151', lineHeight: 1.6, margin: '0 0 16px' }}>
              This will apply the approved setpoints and runtime constraints to the <strong>live system</strong>.
              Changes take effect on the next control loop cycle.
            </p>
            {mods.length > 0 && (
              <ul style={{ margin: '0 0 16px', paddingLeft: 20, fontSize: 13, color: '#374151' }}>
                {mods.map((m, i) => (
                  <li key={i}><strong>{m.parameter}</strong>: {m.current_value} → {m.proposed_value}{m.unit ? ` ${m.unit}` : ''}</li>
                ))}
              </ul>
            )}
            <p style={{ fontSize: 13, fontWeight: 700, color: '#92400e', background: '#fef3c7', borderRadius: 6, padding: '8px 12px', margin: '0 0 16px' }}>
              Are you sure you want to apply these changes?
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmOpen(false)} style={{ padding: '8px 20px', borderRadius: 8, border: '1px solid #d1d5db', background: '#fff', fontSize: 13, cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={handleApprove} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: '#16a34a', color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
                Yes, Apply Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Reject reason modal ────────────────────────────────────────────── */}
      {rejectOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 28, maxWidth: 420, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 17, color: '#111827' }}>Reject Decision</h3>
            <p style={{ fontSize: 13, color: '#6b7280', margin: '0 0 12px' }}>
              No setpoints or constraints will be changed. Optionally enter a reason.
            </p>
            <textarea
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
              placeholder="Reason (optional)"
              rows={3}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, resize: 'vertical', boxSizing: 'border-box', marginBottom: 16 }}
            />
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button onClick={() => { setRejectOpen(false); setRejectReason(''); }} style={{ padding: '8px 20px', borderRadius: 8, border: '1px solid #d1d5db', background: '#fff', fontSize: 13, cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={handleReject} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: '#dc2626', color: '#fff', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
                Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

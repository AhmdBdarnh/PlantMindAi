import React, { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '../api/config';
import { fmtDate, fmtNum } from '../utils/format';

// ── Review status display ──────────────────────────────────────────────────────
// Layer 2 only recommends — it never approves. This badge reflects whether the
// recommendation is still awaiting review, or has already been decided by the
// Budget Manager (Layer 3). The decision is always attributed to Layer 3.

function layer3Status(status) {
  switch (status) {
    case 'approved':
    case 'applied':
      return { bg: '#dcfce7', color: '#166534', border: '#86efac', dot: '#16a34a', label: 'Reviewed · Approved by Budget Manager' };
    case 'rejected':
      return { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5', dot: '#dc2626', label: 'Reviewed · Rejected by Budget Manager' };
    case 'invalid':
      return { bg: '#fce7f3', color: '#9d174d', border: '#f9a8d4', dot: '#db2777', label: 'Invalid Recommendation' };
    // pending, needs_manual_review, and anything else → not yet reviewed
    default:
      return { bg: '#eef2ff', color: '#3730a3', border: '#c7d2fe', dot: '#4f46e5', label: 'Ready for Budget Review' };
  }
}

const PLANT_COLOR = { healthy: '#16a34a', slightly_stressed: '#ca8a04', stressed: '#ea580c', unhealthy: '#dc2626', unknown: '#6b7280' };
const SEV_COLOR   = { none: '#6b7280', low: '#16a34a', medium: '#ca8a04', high: '#dc2626' };

// ── Icon helper ───────────────────────────────────────────────────────────────

function Icon({ path, size = 16, color = 'currentColor', sw = 2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const IC = {
  ai:       'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  run:      'M5 3l14 9-14 9V3z',
  check:    'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  x:        'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  warn:     'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  info:     'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  leaf:     'M17 8C8 10 5.9 16.17 3.82 19c3.15.6 6.41-.34 8.68-2.61 2.56-2.56 3.07-6.44 1.5-9.39zm0 0c-.2 4.17-2.69 7.78-6 10',
  clock:    'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
  arrow:    'M5 12h14M12 5l7 7-7 7',
  budget:   'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  brain:    'M9.5 2A2.5 2.5 0 017 4.5v0A2.5 2.5 0 014.5 7v0A2.5 2.5 0 017 9.5h.5M9.5 2A2.5 2.5 0 0112 4.5v0A2.5 2.5 0 0114.5 7v0A2.5 2.5 0 0112 9.5h-.5M9.5 2h5M14.5 9.5A2.5 2.5 0 0017 7v0A2.5 2.5 0 0019.5 4.5v0A2.5 2.5 0 0017 2h-2.5M7 9.5v5M17 9.5v5M7 14.5A2.5 2.5 0 004.5 17v0A2.5 2.5 0 007 19.5h10A2.5 2.5 0 0019.5 17v0A2.5 2.5 0 0017 14.5',
  settings: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  chart:    'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  data:     'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4',
};

// ── KPI stat card ─────────────────────────────────────────────────────────────

function KpiCard({ label, value, icon, iconBg, iconColor, valueColor }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ background: iconBg, borderRadius: 9, padding: 9, display: 'flex', flexShrink: 0 }}>
        <Icon path={icon} size={17} color={iconColor} />
      </div>
      <div>
        <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>{label}</div>
        <div style={{ fontSize: 18, fontWeight: 800, color: valueColor || '#111827', lineHeight: 1 }}>{value || '—'}</div>
      </div>
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status, size = 'md' }) {
  const s = layer3Status(status);
  const pad = size === 'sm' ? '3px 9px' : '4px 12px';
  const fs  = size === 'sm' ? 11 : 12;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: pad, borderRadius: 99, fontSize: fs, fontWeight: 700, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.dot }} />
      {s.label}
    </span>
  );
}

// ── Compact change summary row ──────────────────────────────────────────────────
// Layer 2 shows only a lightweight summary of WHAT is proposed (parameter and
// current → proposed value). The full detail table — difference, risk level and
// cost impact — lives in the Budget Manager (Layer 3), which decides.

function ChangeSummaryRow({ chg }) {
  const diff = chg.difference != null
    ? chg.difference
    : (chg.recommended_value != null && chg.current_value != null
        ? Number(chg.recommended_value) - Number(chg.current_value)
        : null);
  const arrowColor = diff > 0 ? '#16a34a' : diff < 0 ? '#dc2626' : '#9ca3af';

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '11px 14px', background: '#f9fafb', border: '1px solid #f3f4f6', borderRadius: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
        <div style={{ background: '#f3f4f6', borderRadius: 7, padding: 6, display: 'flex', flexShrink: 0 }}>
          <Icon path={IC.settings} size={13} color='#6b7280' />
        </div>
        <span style={{ fontSize: 13.5, fontWeight: 700, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{chg.parameter}</span>
        {chg.clamped && (
          <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 7px', borderRadius: 99, background: '#fef9c3', color: '#854d0e', border: '1px solid #fde047', flexShrink: 0 }}>CLAMPED</span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 800, whiteSpace: 'nowrap', flexShrink: 0 }}>
        <span style={{ color: '#6b7280' }}>{fmtNum(chg.current_value)}</span>
        <Icon path={IC.arrow} size={13} color={arrowColor} />
        <span style={{ color: '#15803d' }}>{fmtNum(chg.recommended_value)}</span>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AISetpointAdvisor({ setpoints, onSetpointsRefresh }) {
  const [recommendation, setRecommendation] = useState(null);
  const [rateLimit,      setRateLimit]      = useState(null);
  const [loading,        setLoading]        = useState(true);
  const [runLoading,     setRunLoading]     = useState(false);
  const [sendLoading,    setSendLoading]    = useState(false);
  const [polling,        setPolling]        = useState(false);
  const [pollElapsed,    setPollElapsed]    = useState(0);
  const [message,        setMessage]        = useState(null);
  const prevRecTimestampRef = useRef(null);

  const fetchLatest = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/ai-advisor/latest`, { cache: 'no-store' });
      const data = await res.json();
      if (data.success) { setRecommendation(data.recommendation); setRateLimit(data.rate_limit); }
    } catch (e) {
      setMessage({ type: 'error', text: 'Could not reach backend: ' + e.message });
    } finally { setLoading(false); }
  }, []);

  // Initial load + periodic refresh so the Layer 3 status stays in sync
  // (e.g. after the user approves/rejects in the Budget Manager page).
  useEffect(() => {
    fetchLatest();
    const id = setInterval(fetchLatest, 15000);
    return () => clearInterval(id);
  }, [fetchLatest]);

  useEffect(() => {
    if (!polling) return;
    const startTime = Date.now();
    const id = setInterval(async () => {
      const elapsed = Date.now() - startTime;
      setPollElapsed(Math.floor(elapsed / 1000));
      if (elapsed > 3 * 60 * 1000) {
        setPolling(false);
        setMessage({ type: 'error', text: 'AI Advisor is taking longer than expected. Results will appear when ready.' });
        return;
      }
      try {
        const res  = await fetch(`${API_BASE_URL}/ai-advisor/latest`);
        const data = await res.json();
        if (data.success && data.recommendation) {
          const newTs = data.recommendation.created_at;
          if (newTs !== prevRecTimestampRef.current) {
            setRecommendation(data.recommendation);
            setRateLimit(data.rate_limit);
            setPolling(false);
            setMessage({ type: 'success', text: 'AI Advisor completed — results are ready.' });
          }
        }
      } catch {}
    }, 5000);
    return () => clearInterval(id);
  }, [polling]); // eslint-disable-line

  const handleRunNow = async () => {
    setRunLoading(true); setMessage(null);
    prevRecTimestampRef.current = recommendation?.created_at || null;
    try {
      const res  = await fetch(`${API_BASE_URL}/ai-advisor/run`, { method: 'POST' });
      const data = await res.json();
      if (data.success) { setMessage({ type: 'success', text: 'AI Advisor is running — results will appear automatically…' }); setPollElapsed(0); setPolling(true); }
      else setMessage({ type: 'error', text: data.error || 'Failed to start AI Advisor.' });
    } catch (e) { setMessage({ type: 'error', text: 'Request failed: ' + e.message }); }
    finally { setRunLoading(false); }
  };

  const handleSendToBudget = async () => {
    setSendLoading(true); setMessage(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/layer3/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ triggered_by: 'advisor' }),
      });
      const data = await res.json();
      if (data.success) {
        setMessage({ type: 'success', text: 'Sent to Budget Manager for review. Open the Budget Manager (Layer 3) page to approve or reject.' });
        await fetchLatest();
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to send to Budget Manager.' });
      }
    } catch (e) { setMessage({ type: 'error', text: 'Request failed: ' + e.message }); }
    finally { setSendLoading(false); }
  };

  const rec    = recommendation;
  const status = rec?.status;
  const ss     = layer3Status(status);
  const decided = ['approved', 'applied', 'rejected', 'invalid'].includes(status);

  const canRun = !runLoading && !polling && rateLimit?.remaining_today !== 0;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '8px 0', fontSize: '0.88em' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: 'linear-gradient(135deg, #4f46e5, #7c3aed)', borderRadius: 12, padding: 10, display: 'flex' }}>
            <Icon path={IC.ai} size={22} color='#fff' />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#111827' }}>AI Setpoint Advisor</h2>
            <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
              Layer 2 · AI recommends setpoint changes — final approval happens in the Budget Manager (Layer 3) · runs daily at 15:30
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {rateLimit && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', background: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: 99 }}>
              <Icon path={IC.run} size={12} color='#7c3aed' />
              <span style={{ fontSize: 12, fontWeight: 700, color: '#7c3aed' }}>
                {rateLimit.remaining_today}/{rateLimit.max_per_day} runs left today
              </span>
            </div>
          )}
          {polling && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 14px', background: '#ede9fe', border: '1px solid #c4b5fd', borderRadius: 99 }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2.5" style={{ animation: 'spin 0.8s linear infinite' }}>
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
              </svg>
              <span style={{ fontSize: 12, fontWeight: 700, color: '#7c3aed' }}>Analyzing… {pollElapsed}s</span>
            </div>
          )}
          <button onClick={handleRunNow} disabled={!canRun}
            style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 10, border: 'none', background: canRun ? '#4f46e5' : '#a5b4fc', color: '#fff', cursor: canRun ? 'pointer' : 'not-allowed', fontWeight: 700, fontSize: 13 }}>
            <Icon path={IC.run} size={13} color='#fff' />
            {runLoading ? 'Starting…' : polling ? 'Running…' : 'Run Now'}
          </button>
        </div>
      </div>

      {/* ── Feedback banner ───────────────────────────────────────────────────── */}
      {message && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderRadius: 10, marginBottom: 16, background: message.type === 'success' ? '#f0fdf4' : '#fef2f2', border: `1px solid ${message.type === 'success' ? '#86efac' : '#fca5a5'}`, color: message.type === 'success' ? '#166534' : '#991b1b', fontSize: 13 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon path={message.type === 'success' ? IC.check : IC.warn} size={15} color={message.type === 'success' ? '#16a34a' : '#dc2626'} />
            {message.text}
          </div>
          <button onClick={() => setMessage(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'inherit', lineHeight: 1 }}>×</button>
        </div>
      )}

      {/* ── Loading ───────────────────────────────────────────────────────────── */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '60px', color: '#9ca3af' }}>
          <div style={{ width: 36, height: 36, border: '3px solid #e5e7eb', borderTopColor: '#4f46e5', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 14px' }} />
          <div style={{ fontSize: 14 }}>Loading AI recommendation…</div>
        </div>
      )}

      {/* ── No recommendation ────────────────────────────────────────────────── */}
      {!loading && !rec && (
        <div style={{ background: '#f9fafb', border: '1px dashed #d1d5db', borderRadius: 16, padding: '60px 32px', textAlign: 'center' }}>
          <div style={{ background: '#ede9fe', borderRadius: '50%', width: 64, height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px' }}>
            <Icon path={IC.ai} size={28} color='#7c3aed' />
          </div>
          <h3 style={{ margin: '0 0 10px', color: '#374151', fontSize: 18 }}>No Recommendation Yet</h3>
          <p style={{ color: '#9ca3af', margin: '0 0 22px', fontSize: 14, lineHeight: 1.6 }}>
            The AI Advisor runs automatically every day at 15:30.<br />
            You can also trigger it manually using the Run Now button.
          </p>
          <button onClick={handleRunNow} disabled={!canRun}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '10px 22px', borderRadius: 10, border: 'none', background: '#4f46e5', color: '#fff', cursor: 'pointer', fontWeight: 700, fontSize: 14 }}>
            <Icon path={IC.run} size={14} color='#fff' /> Run AI Advisor
          </button>
        </div>
      )}


      {/* ── Main recommendation ───────────────────────────────────────────────── */}
      {!loading && rec && (
        <>
          {/* Status banner — single Layer-3-synced status, shown once */}
          <div style={{ background: ss.bg, border: `1px solid ${ss.border}`, borderRadius: 14, padding: '14px 20px', marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <StatusBadge status={status} />
              <span style={{ fontSize: 12, color: '#6b7280', display: 'flex', alignItems: 'center', gap: 5 }}>
                <Icon path={IC.clock} size={12} color='#9ca3af' />
                Last run: {fmtDate(rec.created_at)}
              </span>
              {rec.openai_model && (
                <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 99, background: '#f5f3ff', border: '1px solid #ddd6fe', color: '#7c3aed' }}>
                  {rec.openai_model}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              {status === 'rejected' && rec.rejection_reason && (
                <span style={{ fontSize: 12, color: '#991b1b', fontWeight: 600 }}>Reason: {rec.rejection_reason}</span>
              )}
              {!decided && rec.changes?.length > 0 && (
                <button onClick={handleSendToBudget} disabled={sendLoading}
                  style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 10, border: 'none', background: sendLoading ? '#a5b4fc' : '#4f46e5', color: '#fff', cursor: sendLoading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 13 }}>
                  <Icon path={IC.arrow} size={14} color='#fff' />
                  {sendLoading ? 'Sending…' : 'Send to Budget Manager'}
                </button>
              )}
            </div>
          </div>

          {/* Two main areas: LEFT Overview · RIGHT Changes */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>

            {/* ── LEFT: Overview ── */}
            <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 18px', borderBottom: '1px solid #e5e7eb', background: '#fafafa' }}>
                <div style={{ background: '#f5f3ff', borderRadius: 8, padding: 7, display: 'flex' }}>
                  <Icon path={IC.brain} size={14} color='#7c3aed' />
                </div>
                <span style={{ fontSize: 14, fontWeight: 800, color: '#111827' }}>Overview</span>
              </div>

              <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Stat grid: plant status / severity / confidence / data quality */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
                  <KpiCard label="Plant Status"     icon={IC.leaf}     iconBg='#f0fdf4' iconColor='#16a34a'
                    value={(rec.plant_status || 'unknown').replace(/_/g,' ').toUpperCase()} valueColor={PLANT_COLOR[rec.plant_status]} />
                  <KpiCard label="Problem Severity" icon={IC.warn}     iconBg={rec.severity === 'none' ? '#f0fdf4' : '#fffbeb'} iconColor={SEV_COLOR[rec.severity] || '#9ca3af'}
                    value={(rec.severity || 'none').toUpperCase()} valueColor={SEV_COLOR[rec.severity]} />
                  <KpiCard label="AI Confidence"    icon={IC.brain}    iconBg='#f5f3ff' iconColor='#7c3aed'
                    value={rec.confidence != null ? `${Math.round(rec.confidence * 100)}%` : '—'} />
                  <KpiCard label="Data Quality"     icon={IC.data}     iconBg={rec.data_quality === 'high' ? '#f0fdf4' : '#fffbeb'} iconColor={rec.data_quality === 'high' ? '#16a34a' : '#d97706'}
                    value={(rec.data_quality || '—').toUpperCase()} valueColor={rec.data_quality === 'high' ? '#16a34a' : rec.data_quality === 'medium' ? '#d97706' : '#dc2626'} />
                </div>

                {/* Problem banner */}
                {rec.problem_detected && rec.main_problem && rec.main_problem !== 'none' && (
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, padding: '11px 14px', background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 10 }}>
                    <Icon path={IC.warn} size={15} color='#dc2626' />
                    <div style={{ fontSize: 13, color: '#991b1b' }}>
                      <strong>Problem Detected: </strong>{rec.main_problem}
                    </div>
                  </div>
                )}

                {/* AI analysis text */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 800, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>AI Analysis</div>
                  <p style={{ margin: 0, color: '#1f2937', fontSize: 13.5, lineHeight: 1.75, background: '#f9fafb', padding: '14px 16px', borderRadius: 10, border: '1px solid #f3f4f6' }}>
                    {rec.detailed_explanation || rec.summary || 'No explanation provided.'}
                  </p>
                </div>

                {/* Environment issues */}
                {rec.environment_issues?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 800, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                      Environment Issues ({rec.environment_issues.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {rec.environment_issues.map((issue, i) => (
                        <div key={i} style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 9, padding: '10px 13px' }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: '#92400e', marginBottom: issue.current_value != null ? 3 : 0 }}>{issue.description}</div>
                          {issue.current_value != null && (
                            <div style={{ fontSize: 12, color: '#92400e' }}>
                              Current: <strong>{issue.current_value}</strong>
                              {issue.optimal_range && <> · Optimal: <strong>{issue.optimal_range}</strong></>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Warnings */}
                {rec.warnings?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 800, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Warnings</div>
                    <ul style={{ margin: 0, paddingLeft: 20, color: '#6b7280', fontSize: 13, lineHeight: 1.7 }}>
                      {rec.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* ── RIGHT: Changes ── */}
            <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '13px 18px', borderBottom: '1px solid #e5e7eb', background: '#fafafa' }}>
                <div style={{ background: '#eff6ff', borderRadius: 8, padding: 7, display: 'flex' }}>
                  <Icon path={IC.settings} size={14} color='#2563eb' />
                </div>
                <span style={{ fontSize: 14, fontWeight: 800, color: '#111827' }}>Recommended Changes</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.04em' }}>summary</span>
                <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, padding: '2px 9px', borderRadius: 99, background: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe' }}>
                  {rec.changes?.length || 0}
                </span>
              </div>

              <div style={{ padding: '16px 18px' }}>
                {rec.changes?.length > 0 ? (
                  <>
                    <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 14 }}>
                      {rec.changes.length} setpoint change{rec.changes.length !== 1 ? 's' : ''} recommended.
                      This is a proposal only — the full detail (difference, risk, cost impact) and final approval are in the Budget Manager (Layer 3).
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {rec.changes.map((chg, i) => <ChangeSummaryRow key={i} chg={chg} />)}
                    </div>
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px 20px', background: '#f9fafb', borderRadius: 10 }}>
                    <Icon path={IC.check} size={32} color='#d1d5db' />
                    <div style={{ color: '#6b7280', marginTop: 12, fontSize: 13.5, fontWeight: 600 }}>No setpoint changes recommended</div>
                    <div style={{ color: '#9ca3af', marginTop: 4, fontSize: 12 }}>AI agrees with all current setpoints.</div>
                  </div>
                )}
              </div>
            </div>

          </div>
        </>
      )}

    </div>
  );
}

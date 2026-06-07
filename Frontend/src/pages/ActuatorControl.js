import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../api/config';

// ── SVG icon helper ───────────────────────────────────────────────────────────
function Icon({ path, size = 16, color = 'currentColor', sw = 2 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

// ── Actuator metadata ─────────────────────────────────────────────────────────
const ACTUATOR_CONFIGS = [
  {
    key:       'water_pump',
    label:     'Water Pump',
    accent:    '#2563eb',
    iconBg:    '#dbeafe',
    iconColor: '#1d4ed8',
    icon:      'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
    isPump:    true,
  },
  {
    key:       'fertilizer_pump',
    label:     'Fertilizer Pump',
    accent:    '#16a34a',
    iconBg:    '#dcfce7',
    iconColor: '#15803d',
    icon:      'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2v-4M9 21H5a2 2 0 01-2-2v-4m0 0h18',
    isPump:    true,
  },
  {
    key:       'light',
    label:     'Grow Light',
    accent:    '#b45309',
    iconBg:    '#fef3c7',
    iconColor: '#92400e',
    icon:      'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z',
    isPump:    false,
  },
  {
    key:       'fan',
    label:     'Ventilator',
    accent:    '#047857',
    iconBg:    '#d1fae5',
    iconColor: '#065f46',
    icon:      'M12 3v1m0 16v1M4.22 4.22l.71.71M18.36 18.36l.71.71M1 12h1m18 0h1M4.22 19.78l.71-.71M18.36 5.64l.71-.71M16 12a4 4 0 11-8 0 4 4 0 018 0z',
    isPump:    false,
  },
  {
    key:       'heater',
    label:     'Heater',
    accent:    '#c2410c',
    iconBg:    '#ffedd5',
    iconColor: '#9a3412',
    icon:      'M12 2c1 3 4 5 4 9a4 4 0 01-8 0c0-4 3-6 4-9z M12 17a1 1 0 110 2 1 1 0 010-2z',
    isPump:    false,
  },
];

// ── Text palette ──────────────────────────────────────────────────────────────
const T = {
  primary:   '#111827',
  secondary: '#1f2937',
  label:     '#374151',
  muted:     '#6b7280',
};

// ── Reusable sub-components ───────────────────────────────────────────────────
function SecLabel({ children }) {
  return (
    <div style={{
      fontSize: 9, fontWeight: 800, color: T.muted,
      letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6,
    }}>{children}</div>
  );
}

function DataRow({ label, value, unit }) {
  const display = value == null ? '–' : `${value}${unit ? ' ' + unit : ''}`;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <span style={{ fontSize: 11, color: T.label }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 700, color: T.primary }}>{display}</span>
    </div>
  );
}

function SensorBadge({ label, value, unit, status }) {
  const palette = {
    ok:     { bg: '#dcfce7', text: '#14532d', border: '#86efac' },
    warn:   { bg: '#fef9c3', text: '#713f12', border: '#fde047' },
    error:  { bg: '#fee2e2', text: '#7f1d1d', border: '#fca5a5' },
    danger: { bg: '#fee2e2', text: '#7f1d1d', border: '#fca5a5' },
  };
  const clr = palette[status] || palette.ok;
  const display = value == null ? '–' : `${value}${unit ? ' ' + unit : ''}`;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
      <span style={{ fontSize: 11, color: T.label }}>{label}</span>
      <span style={{
        fontSize: 11, fontWeight: 700, padding: '1px 8px', borderRadius: 99,
        background: clr.bg, color: clr.text, border: `1px solid ${clr.border}`,
      }}>{display}</span>
    </div>
  );
}

// ── Tab button ────────────────────────────────────────────────────────────────
function TabBtn({ active, onClick, icon, children }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 7,
      padding: '9px 20px', borderRadius: 10,
      fontWeight: 700, fontSize: 13, cursor: 'pointer',
      transition: 'all 0.15s',
      background: active ? '#111827' : '#fff',
      color:      active ? '#fff'    : T.label,
      border:     active ? '2px solid #111827' : '2px solid #e5e7eb',
      boxShadow:  active ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
    }}>
      {icon && <Icon path={icon} size={14} color={active ? '#fff' : T.muted} />}
      {children}
    </button>
  );
}

// ── LIVE STATUS card ──────────────────────────────────────────────────────────
function ActuatorCard({ cfg, liveData, dashData, operationMode, onControlState, onControlPower }) {
  const isAuto = operationMode === 'autonomous';

  const dd      = dashData || {};
  const sensors  = dd.sensors  || [];
  const setps    = dd.setpoints || [];
  const action   = dd.action   || {};
  const reason   = dd.reason   || null;

  const dutyCycle  = liveData?.duty_cycle ?? 0;
  const livePct    = Math.round((dutyCycle / 4095) * 100);
  const displayPct = action.percentage != null ? action.percentage : livePct;

  // Local slider state — tracks the slider while dragging without spamming the API
  const [sliderVal, setSliderVal] = useState(dutyCycle);
  // Sync slider when live duty cycle changes from outside (auto mode updates)
  useEffect(() => { setSliderVal(dutyCycle); }, [dutyCycle]);

  const state      = action.state || liveData?.state || 'off';
  const isOn       = state === 'on';
  const inCooldown = !!action.is_in_cooldown;

  const isDanger  = reason && (reason.includes('DANGER') || reason.includes('root burn'));
  const isBlocked = reason && (reason.includes('Blocked') || reason.includes('invalid'));
  const isWarning = reason && (reason.includes('too high') || reason.includes('above safe'));

  const borderColor = isDanger    ? '#ef4444'
                    : isBlocked   ? '#f59e0b'
                    : isOn        ? cfg.accent
                    : inCooldown  ? '#f59e0b'
                    : '#e5e7eb';

  const pillBg = isOn ? cfg.accent : inCooldown ? '#f59e0b' : '#6b7280';

  const reasonBg   = isDanger || isBlocked ? '#fee2e2'
                   : isWarning             ? '#fef9c3'
                   : '#f0fdf4';
  const reasonText = isDanger || isBlocked ? '#7f1d1d'
                   : isWarning             ? '#713f12'
                   : '#14532d';

  return (
    <div style={{
      background: '#fff', borderRadius: 12,
      border: `1.5px solid ${borderColor}`,
      boxShadow: isOn ? `0 2px 12px ${cfg.accent}20` : '0 1px 4px rgba(0,0,0,0.07)',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px',
        background: isOn ? cfg.accent + '0d' : '#fafafa',
        borderBottom: '1px solid #e5e7eb',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ background: cfg.iconBg, borderRadius: 8, padding: 7, display: 'flex' }}>
            <Icon path={cfg.icon} size={15} color={cfg.iconColor} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>{cfg.label}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {cfg.key === 'fan' && action.phase && (
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
              background: action.phase === 'day' ? '#fef9c3' : '#e0f2fe',
              color:      action.phase === 'day' ? '#713f12' : '#0c4a6e',
              border:     `1px solid ${action.phase === 'day' ? '#fde047' : '#7dd3fc'}`,
            }}>
              {action.phase === 'day' ? '☀ Day' : '🌙 Night'}
            </span>
          )}
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '3px 10px', borderRadius: 99,
            background: pillBg, color: '#fff',
            fontSize: 11, fontWeight: 800,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff', opacity: 0.8, display: 'inline-block' }} />
            {isOn ? 'ON' : inCooldown ? 'COOLDOWN' : 'OFF'}
          </span>
        </div>
      </div>

      {/* Sensors | Setpoints — flex:1 so this section expands and pushes bottom content down */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', flex: 1 }}>
        <div style={{ padding: '9px 13px', borderRight: '1px solid #e5e7eb', borderBottom: '1px solid #e5e7eb' }}>
          <SecLabel>Sensors</SecLabel>
          {sensors.length === 0
            ? <span style={{ fontSize: 11, color: T.muted }}>No data yet</span>
            : sensors.map((s, i) => (
              <SensorBadge key={i} label={s.label} value={s.value} unit={s.unit} status={s.status || 'ok'} />
            ))}
        </div>
        <div style={{ padding: '9px 13px', borderBottom: '1px solid #e5e7eb' }}>
          <SecLabel>Setpoints</SecLabel>
          {setps.length === 0
            ? <span style={{ fontSize: 11, color: T.muted }}>No data yet</span>
            : setps.map((s, i) => (
              <DataRow key={i} label={s.label} value={s.value} unit={s.unit} />
            ))}
        </div>
      </div>

      {/* ── Bottom-anchored block: status + reason + controls always at the same position ── */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>

      {/* Current Status */}
      <div style={{ padding: '9px 13px', borderBottom: '1px solid #e5e7eb' }}>
        <SecLabel>Current Status</SecLabel>
        <div style={{ display: 'flex', gap: 18, marginBottom: inCooldown ? 6 : 0 }}>
          <div>
            <span style={{ fontSize: 10, color: T.muted, display: 'block', marginBottom: 2 }}>State</span>
            <span style={{ fontSize: 13, fontWeight: 800, color: isOn ? cfg.accent : T.primary }}>
              {isOn ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div>
            <span style={{ fontSize: 10, color: T.muted, display: 'block', marginBottom: 2 }}>Power</span>
            <span style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>
              {displayPct}<span style={{ fontSize: 10, fontWeight: 600, color: T.label }}>%</span>
            </span>
          </div>
          {cfg.key === 'fan' && action.current_time && (
            <div>
              <span style={{ fontSize: 10, color: T.muted, display: 'block', marginBottom: 2 }}>Time</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: T.primary }}>{action.current_time}</span>
            </div>
          )}
        </div>
        {cfg.isPump && inCooldown && action.cooldown_remaining_str && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', borderRadius: 8,
            background: '#fef9c3', border: '1px solid #fde047',
          }}>
            <span style={{ fontSize: 12 }}>⏱</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#713f12' }}>
              Cooldown: {action.cooldown_remaining_str} remaining
            </span>
          </div>
        )}
      </div>

      {/* Reason */}
      <div style={{
        padding: reason ? '7px 13px' : '0',
        minHeight: reason ? 'auto' : 0,
        background: reason ? reasonBg : 'transparent',
        borderBottom: reason ? '1px solid #e5e7eb' : 'none',
      }}>
        {reason && (
          <span style={{ fontSize: 11, fontWeight: 600, color: reasonText, lineHeight: 1.5, display: 'block' }}>
            {(isDanger || isBlocked) ? '⚠ ' : 'ℹ '}{reason}
          </span>
        )}
      </div>

      {/* Manual controls — always rendered in same position (hidden in auto mode) */}
      <div style={{ padding: '10px 13px', minHeight: isAuto ? 0 : undefined }}>
      {!isAuto && (<>

          {/* Duty cycle slider */}
          <div style={{ marginBottom: 9 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: T.muted, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                Power Control
              </span>
              <span style={{
                fontSize: 13, fontWeight: 800, color: cfg.accent,
                background: cfg.accent + '12', padding: '1px 9px', borderRadius: 7,
              }}>
                {Math.round((sliderVal / 4095) * 100)}%
              </span>
            </div>
            <input
              type="range" min="0" max="4095" value={sliderVal}
              onChange={e => setSliderVal(parseInt(e.target.value))}
              onMouseUp={e => onControlPower(cfg.key, parseInt(e.target.value))}
              onTouchEnd={e => onControlPower(cfg.key, sliderVal)}
              style={{ width: '100%', accentColor: cfg.accent, cursor: 'pointer' }}
            />
            {/* Preset buttons */}
            <div style={{ display: 'flex', gap: 4, marginTop: 5 }}>
              {[0, 25, 50, 75, 100].map(p => {
                const dc = Math.round((p / 100) * 4095);
                const active = Math.round((sliderVal / 4095) * 100) === p;
                return (
                  <button key={p}
                    onClick={() => { setSliderVal(dc); onControlPower(cfg.key, dc); }}
                    style={{
                      flex: 1, padding: '3px 0', borderRadius: 6, fontSize: 10, fontWeight: 700,
                      cursor: 'pointer', transition: 'all 0.1s',
                      background: active ? cfg.accent : '#f3f4f6',
                      color:      active ? '#fff'      : T.label,
                      border:     active ? `1px solid ${cfg.accent}` : '1px solid #e5e7eb',
                    }}
                  >{p}%</button>
                );
              })}
            </div>
          </div>

          {/* ON / OFF buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
            <button onClick={() => onControlState(cfg.key, 'on')} style={{
              padding: '7px 0', borderRadius: 8, fontWeight: 800, fontSize: 12, cursor: 'pointer',
              background: isOn ? cfg.accent : '#fff', color: isOn ? '#fff' : cfg.accent,
              border: `2px solid ${cfg.accent}`, transition: 'all 0.12s',
            }}>▶ ON</button>
            <button onClick={() => onControlState(cfg.key, 'off')} style={{
              padding: '7px 0', borderRadius: 8, fontWeight: 800, fontSize: 12, cursor: 'pointer',
              background: !isOn ? '#ef4444' : '#fff', color: !isOn ? '#fff' : '#ef4444',
              border: '2px solid #ef4444', transition: 'all 0.12s',
            }}>■ OFF</button>
          </div>
        </>)}
      </div>

      </div>{/* end bottom-anchored block */}
    </div>
  );
}

// ── HISTORY tab view ──────────────────────────────────────────────────────────
const ACTUATOR_META = {
  water_pump:      { label: 'Water Pump',      accent: '#2563eb', iconBg: '#dbeafe', iconColor: '#1d4ed8', icon: 'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z' },
  fertilizer_pump: { label: 'Fertilizer Pump', accent: '#16a34a', iconBg: '#dcfce7', iconColor: '#15803d', icon: 'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2v-4M9 21H5a2 2 0 01-2-2v-4m0 0h18' },
  light:           { label: 'Grow Light',      accent: '#b45309', iconBg: '#fef3c7', iconColor: '#92400e', icon: 'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z' },
  fan:             { label: 'Ventilator',      accent: '#047857', iconBg: '#d1fae5', iconColor: '#065f46', icon: 'M12 3v1m0 16v1M4.22 4.22l.71.71M18.36 18.36l.71.71M1 12h1m18 0h1M4.22 19.78l.71-.71M18.36 5.64l.71-.71M16 12a4 4 0 11-8 0 4 4 0 018 0z' },
  heater:          { label: 'Heater',          accent: '#c2410c', iconBg: '#ffedd5', iconColor: '#9a3412', icon: 'M12 2c1 3 4 5 4 9a4 4 0 01-8 0c0-4 3-6 4-9z M12 17a1 1 0 110 2 1 1 0 010-2z' },
};

const FILTER_OPTS = [
  { key: 'all',            label: 'All' },
  { key: 'water_pump',     label: 'Water Pump' },
  { key: 'fertilizer_pump',label: 'Fertilizer' },
  { key: 'light',          label: 'Grow Light' },
  { key: 'fan',            label: 'Fan' },
  { key: 'heater',         label: 'Heater' },
];

function HistoryTab() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [filter, setFilter]     = useState('all');

  const fetchSessions = useCallback(async () => {
    try {
      // Backend returns ready-made sessions (one per ON→OFF run, no duplication)
      const url = filter === 'all'
        ? `${API_BASE_URL}/actuators/history?limit=60`
        : `${API_BASE_URL}/actuators/history?limit=60&actuator=${filter}`;
      const res  = await fetch(url, { cache: 'no-store' });
      const data = await res.json();
      if (data.success) setSessions(data.events || []);
    } catch {}
    finally { setLoading(false); }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    fetchSessions();
    const id = setInterval(fetchSessions, 15000);
    return () => clearInterval(id);
  }, [fetchSessions]);

  const fmtTime = iso => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString([], {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return iso; }
  };

  const fmtAgo = iso => {
    if (!iso) return '';
    try {
      const diff = Date.now() - new Date(iso).getTime();
      const m = Math.floor(diff / 60000);
      if (m < 2)  return 'just now';
      if (m < 60) return `${m}m ago`;
      const h = Math.floor(m / 60);
      if (h < 24) return `${h}h ${m % 60}m ago`;
      return `${Math.floor(h / 24)}d ago`;
    } catch { return ''; }
  };

  // Format a duration in seconds. For a running session, count up to "now".
  const fmtDurationSec = (sec) => {
    if (sec == null || sec < 0) return null;
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    if (m < 60) return `${m}m ${s}s`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  };

  return (
    <div>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 16, padding: '12px 16px',
        background: '#fff', borderRadius: 12,
        border: '1.5px solid #e5e7eb',
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
        flexWrap: 'wrap', gap: 10,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: T.primary }}>Actuator Logs</div>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>
            {sessions.length} session{sessions.length !== 1 ? 's' : ''} · one row per run · refreshes every 15 s
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 4, padding: 4, background: '#f3f4f6', borderRadius: 10 }}>
            {FILTER_OPTS.map(o => (
              <button key={o.key} onClick={() => setFilter(o.key)} style={{
                padding: '4px 12px', borderRadius: 7, fontSize: 11, fontWeight: 700,
                cursor: 'pointer', transition: 'all 0.12s',
                background: filter === o.key ? '#111827' : 'transparent',
                color:      filter === o.key ? '#fff'    : T.label,
                border:     'none',
              }}>{o.label}</button>
            ))}
          </div>
          <button onClick={fetchSessions} style={{
            padding: '6px 14px', borderRadius: 8, fontSize: 11, fontWeight: 700,
            background: '#fff', color: T.secondary,
            border: '2px solid #e5e7eb', cursor: 'pointer',
          }}>↻ Refresh</button>
        </div>
      </div>

      {/* Session cards */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', background: '#fff', borderRadius: 12, border: '1.5px solid #e5e7eb' }}>
          <div style={{ fontSize: 13, color: T.muted }}>Loading logs…</div>
        </div>
      ) : sessions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', background: '#fff', borderRadius: 12, border: '1.5px solid #e5e7eb' }}>
          <Icon path='M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' size={36} color='#d1d5db' />
          <div style={{ fontSize: 13, color: T.secondary, marginTop: 12, fontWeight: 600 }}>No sessions recorded yet</div>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 4 }}>
            A card appears each time an actuator turns ON. Restart the backend to start logging.
          </div>
        </div>
      ) : (
        <div style={{
          background: '#fff', borderRadius: 12, border: '1.5px solid #e5e7eb',
          boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
          padding: 12, maxHeight: 520, overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          {sessions.map((s, i) => {
            const meta = ACTUATOR_META[s.actuator] || {
              label: s.actuator, accent: '#374151', iconBg: '#f3f4f6', iconColor: '#374151',
              icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
            };

            const isRunning = s.status === 'running';

            // Duration: stored on close; for running sessions, count up to now.
            let durSec = s.duration_sec;
            if (isRunning && s.started_at) {
              durSec = Math.max(0, Math.round((Date.now() - new Date(s.started_at).getTime()) / 1000));
            }
            const duration = fmtDurationSec(durSec);

            const headerBg = isRunning ? meta.accent : '#6b7280';

            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
                background: '#fff', borderRadius: 10,
                border: `1.5px solid ${meta.accent}40`,
                borderLeft: `4px solid ${meta.accent}`,
                boxShadow: isRunning ? `0 2px 10px ${meta.accent}20` : '0 1px 4px rgba(0,0,0,0.06)',
                padding: '10px 16px',
              }}>
                {/* Actuator label + when */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 160 }}>
                  <div style={{ background: meta.iconBg, borderRadius: 8, padding: 7, display: 'flex' }}>
                    <Icon path={meta.icon} size={15} color={meta.iconColor} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: T.primary }}>{meta.label}</div>
                    <div style={{ fontSize: 10, color: T.muted, marginTop: 1 }}>
                      {fmtAgo(s.stopped_at || s.started_at)}
                    </div>
                  </div>
                </div>

                {/* Status badge */}
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  padding: '3px 10px', borderRadius: 99,
                  background: headerBg, color: '#fff',
                  fontSize: 10, fontWeight: 800, flexShrink: 0,
                }}>
                  <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff', opacity: 0.85, display: 'inline-block' }} />
                  {isRunning ? 'Running' : 'Stopped'}
                </span>

                {/* Started / Stopped / Power / Duration fields */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 22, marginLeft: 'auto', flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ fontSize: 10, color: meta.accent, fontWeight: 700 }}>▶ Started</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: T.primary }}>{fmtTime(s.started_at)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: isRunning ? '#16a34a' : T.muted, fontWeight: 700 }}>
                      ■ {isRunning ? 'Still ON' : 'Stopped'}
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: T.primary }}>
                      {isRunning ? '—' : fmtTime(s.stopped_at)}
                    </div>
                  </div>
                  {s.percentage != null && (
                    <div style={{ textAlign: 'right', minWidth: 44 }}>
                      <div style={{ fontSize: 10, color: T.muted, fontWeight: 700 }}>Power</div>
                      <div style={{ fontSize: 12, fontWeight: 800, color: T.primary }}>{s.percentage}%</div>
                    </div>
                  )}
                  {duration && (
                    <div style={{ textAlign: 'right', minWidth: 56 }}>
                      <div style={{ fontSize: 10, color: T.muted, fontWeight: 700 }}>Duration</div>
                      <div style={{ fontSize: 12, fontWeight: 800, color: T.primary }}>{duration}</div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── LIVE STATUS tab view ──────────────────────────────────────────────────────
function LiveStatusTab({
  actuators, dashboard, operationMode, onToggleMode, onControlState, onControlPower, loading,
}) {
  const isAuto = operationMode === 'autonomous';

  return (
    <div>
      {/* Mode banner */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', borderRadius: 10, marginBottom: 16,
        background: isAuto ? '#f0fdf4' : '#eff6ff',
        border: `1.5px solid ${isAuto ? '#86efac' : '#93c5fd'}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: isAuto ? '#16a34a' : '#2563eb',
            boxShadow: isAuto ? '0 0 0 3px #bbf7d0' : '0 0 0 3px #bfdbfe',
            flexShrink: 0,
          }} />
          <span style={{ fontSize: 13, fontWeight: 800, color: isAuto ? '#14532d' : '#1e3a8a' }}>
            {isAuto ? 'Autonomous Mode Active' : 'Manual Mode Active'}
          </span>
          <span style={{ fontSize: 12, color: isAuto ? '#166534' : '#1d4ed8' }}>
            {isAuto
              ? '— PID & schedule loops control all actuators. Controls locked.'
              : '— You have full control. Use ON / OFF buttons in each card.'}
          </span>
        </div>
        <button onClick={onToggleMode} disabled={loading || !operationMode} style={{
          display: 'flex', alignItems: 'center', gap: 7,
          padding: '7px 16px', borderRadius: 9, fontWeight: 700, fontSize: 12,
          cursor: loading || !operationMode ? 'not-allowed' : 'pointer',
          background: isAuto ? '#fff7ed' : '#f0fdf4',
          color:      isAuto ? '#c2410c' : '#15803d',
          border:     `2px solid ${isAuto ? '#fed7aa' : '#86efac'}`,
          opacity:    loading || !operationMode ? 0.6 : 1,
        }}>
          <Icon
            path={isAuto
              ? 'M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z'
              : 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z'}
            size={13} color={isAuto ? '#c2410c' : '#15803d'}
          />
          {isAuto ? 'Switch to Manual' : 'Switch to Autonomous'}
        </button>
      </div>

      {/* Cards grid */}
      {actuators ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {ACTUATOR_CONFIGS.map(cfg => (
            <ActuatorCard
              key={cfg.key}
              cfg={cfg}
              liveData={actuators[cfg.key]}
              dashData={dashboard?.[cfg.key]}
              operationMode={operationMode}
              onControlState={onControlState}
              onControlPower={onControlPower}
            />
          ))}
        </div>
      ) : (
        <div style={{
          textAlign: 'center', padding: '60px',
          background: '#fff', borderRadius: 12, border: '1.5px solid #e5e7eb',
        }}>
          <Icon path='M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4'
            size={36} color='#9ca3af' />
          <div style={{ fontSize: 13, color: T.secondary, marginTop: 12 }}>
            Waiting for actuator data…
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ActuatorControl({
  actuators, operationMode, onToggleMode, onControlState, onControlPower, loading,
}) {
  const [activeTab, setActiveTab]     = useState('live');
  const [dashboard, setDashboard]     = useState(null);
  const [dashError, setDashError]     = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/actuators/dashboard`, { cache: 'no-store' });
      const d   = await res.json();
      if (d.success) {
        setDashboard(d.data);
        setLastUpdated(d.last_updated);
        setDashError(false);
      } else {
        setDashError(true);
      }
    } catch {
      setDashError(true);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const id = setInterval(fetchDashboard, 10000);
    return () => clearInterval(id);
  }, [fetchDashboard]);

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '6px 0' }}>

      {/* ── Page header ────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            background: activeTab === 'live'
              ? 'linear-gradient(135deg,#1d4ed8,#1e3a8a)'
              : 'linear-gradient(135deg,#374151,#111827)',
            borderRadius: 10, padding: 9, display: 'flex',
          }}>
            <Icon
              path={activeTab === 'live'
                ? 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z'
                : 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'}
              size={20} color='#fff'
            />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: T.primary }}>
              Actuator Control
            </h2>
            <div style={{ fontSize: 11, color: T.muted, marginTop: 1 }}>
              {activeTab === 'live'
                ? 'Live sensor readings, setpoints and current actuator decisions'
                : 'Past pump events and activation logs'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {lastUpdated && activeTab === 'live' && (
            <span style={{ fontSize: 11, color: T.muted }}>
              Live · {lastUpdated.slice(11, 16)}
            </span>
          )}
          {dashError && activeTab === 'live' && (
            <span style={{
              fontSize: 11, fontWeight: 700, color: '#713f12',
              background: '#fef9c3', border: '1px solid #fde047',
              borderRadius: 6, padding: '3px 10px',
            }}>⚠ Restart backend</span>
          )}
        </div>
      </div>

      {/* ── Tab bar ──────────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 6, marginBottom: 18,
        padding: '6px', borderRadius: 12,
        background: '#f3f4f6',
        width: 'fit-content',
      }}>
        <TabBtn
          active={activeTab === 'live'}
          onClick={() => setActiveTab('live')}
          icon='M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z'
        >
          Live Status
        </TabBtn>
        <TabBtn
          active={activeTab === 'history'}
          onClick={() => setActiveTab('history')}
          icon='M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
        >
          Logs
        </TabBtn>
      </div>

      {/* ── Tab content ──────────────────────────────────────────────────────── */}
      {activeTab === 'live' ? (
        <LiveStatusTab
          actuators={actuators}
          dashboard={dashboard}
          operationMode={operationMode}
          onToggleMode={onToggleMode}
          onControlState={onControlState}
          onControlPower={onControlPower}
          loading={loading}
        />
      ) : (
        <HistoryTab />
      )}

    </div>
  );
}

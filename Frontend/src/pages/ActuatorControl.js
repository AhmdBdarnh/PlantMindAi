import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:5000/api';
const dutyToPercent = dc => Math.round((dc / 4095) * 100);

const ACTUATORS = [
  {
    key:        'water_pump',
    label:      'Water Pump',
    sliderLabel:'Flow Rate',
    iconBg:     '#eff6ff',
    iconColor:  '#3b82f6',
    accentColor:'#3b82f6',
    icon:       'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
  },
  {
    key:        'fertilizer_pump',
    label:      'Fertilizer Pump',
    sliderLabel:'Flow Rate',
    iconBg:     '#f0fdf4',
    iconColor:  '#16a34a',
    accentColor:'#16a34a',
    icon:       'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2v-4M9 21H5a2 2 0 01-2-2v-4m0 0h18',
  },
  {
    key:        'fan',
    label:      'Ventilator',
    sliderLabel:'Fan Speed',
    iconBg:     '#ecfdf5',
    iconColor:  '#10b981',
    accentColor:'#10b981',
    icon:       'M12 3v1m0 16v1M4.22 4.22l.71.71M18.36 18.36l.71.71M1 12h1m18 0h1M4.22 19.78l.71-.71M18.36 5.64l.71-.71M16 12a4 4 0 11-8 0 4 4 0 018 0z',
  },
  {
    key:        'heater',
    label:      'Heater',
    sliderLabel:'Power Level',
    iconBg:     '#fef3c7',
    iconColor:  '#f59e0b',
    accentColor:'#f59e0b',
    icon:       'M12 2c1 3 4 5 4 9a4 4 0 01-8 0c0-4 3-6 4-9z M12 17a1 1 0 110 2 1 1 0 010-2z',
  },
  {
    key:        'light',
    label:      'Grow Light',
    sliderLabel:'Brightness',
    iconBg:     '#fefce8',
    iconColor:  '#eab308',
    accentColor:'#eab308',
    icon:       'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z',
  },
];

function ActuatorCard({ config, data, operationMode, onControlState, onControlPower }) {
  const isAuto     = operationMode === 'autonomous';
  const state      = data?.state     || 'off';
  const dutyCycle  = data?.duty_cycle ?? 0;
  const pct        = dutyToPercent(dutyCycle);
  const isOn       = state === 'on';

  return (
    <div className="actuator-card">
      {/* Header */}
      <div className="actuator-card-header">
        <div className="actuator-card-name">
          <div
            className="actuator-icon-wrap"
            style={{ background: config.iconBg }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke={config.iconColor}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d={config.icon} />
            </svg>
          </div>
          {config.label}
        </div>
        <div className={`actuator-state-badge ${state}`}>
          <span className="actuator-state-dot" />
          {state.toUpperCase()}
        </div>
      </div>

      {/* Power % display */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            flex: 1,
            height: 6,
            background: 'var(--border)',
            borderRadius: 3,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: '100%',
              background: isOn ? config.accentColor : 'var(--text-light)',
              borderRadius: 3,
              transition: 'width .3s ease',
            }}
          />
        </div>
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: isOn ? config.accentColor : 'var(--text-muted)',
            minWidth: 36,
            textAlign: 'right',
          }}
        >
          {pct}%
        </span>
      </div>

      {/* Slider */}
      <div className="actuator-slider-section">
        <div className="actuator-duty-row">
          <span className="actuator-duty-label">{config.sliderLabel}</span>
          <span className="actuator-duty-value">{pct}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="4095"
          value={dutyCycle}
          onChange={e => onControlPower(config.key, parseInt(e.target.value))}
          disabled={isAuto}
          style={isOn ? { accentColor: config.accentColor } : {}}
        />
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 10,
            color: 'var(--text-light)',
            marginTop: 4,
          }}
        >
          {['0%', '25%', '50%', '75%', '100%'].map(l => (
            <span key={l}>{l}</span>
          ))}
        </div>
      </div>

      {/* ON / OFF buttons */}
      <div className="actuator-buttons">
        <button
          className="btn-actuator-on"
          onClick={() => onControlState(config.key, 'on')}
          disabled={isAuto}
        >
          Turn ON
        </button>
        <button
          className="btn-actuator-off"
          onClick={() => onControlState(config.key, 'off')}
          disabled={isAuto}
        >
          Turn OFF
        </button>
      </div>
    </div>
  );
}

function PHPumpCard({ operationMode }) {
  const [state, setState]     = useState('off');
  const [busy, setBusy]       = useState(false);
  const isAuto = operationMode === 'autonomous';
  const isOn   = state === 'on';

  useEffect(() => {
    fetch(`${API_BASE_URL}/actuators/ph_pump`)
      .then(r => r.json())
      .then(d => { if (d.success) setState(d.state); })
      .catch(() => {});
  }, []);

  const toggle = async (newState) => {
    setBusy(true);
    try {
      const res  = await fetch(`${API_BASE_URL}/actuators/ph_pump`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: newState }),
      });
      const data = await res.json();
      if (data.success) setState(newState);
    } catch {}
    setBusy(false);
  };

  return (
    <div className="actuator-card">
      <div className="actuator-card-header">
        <div className="actuator-card-name">
          <div className="actuator-icon-wrap" style={{ background: '#f0fdf4' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
              <text x="6" y="16" fontSize="9" fill="#22c55e" stroke="none" fontWeight="bold">pH</text>
            </svg>
          </div>
          pH Pump
        </div>
        <div className={`actuator-state-badge ${state}`}>
          <span className="actuator-state-dot" />
          {state.toUpperCase()}
        </div>
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        USB mini pump · GPIO relay · ON/OFF only
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: isOn ? '100%' : '0%', height: '100%', background: isOn ? '#22c55e' : 'var(--text-light)', borderRadius: 3, transition: 'width .3s ease' }} />
        </div>
        <span style={{ fontSize: 13, fontWeight: 700, color: isOn ? '#22c55e' : 'var(--text-muted)', minWidth: 36, textAlign: 'right' }}>
          {isOn ? '100%' : '0%'}
        </span>
      </div>

      <div className="actuator-buttons">
        <button className="btn-actuator-on" onClick={() => toggle('on')} disabled={isAuto || busy}>
          Turn ON
        </button>
        <button className="btn-actuator-off" onClick={() => toggle('off')} disabled={isAuto || busy}>
          Turn OFF
        </button>
      </div>
    </div>
  );
}

export default function ActuatorControl({
  actuators,
  operationMode,
  onToggleMode,
  onControlState,
  onControlPower,
  loading,
}) {
  const isAuto = operationMode === 'autonomous';

  return (
    <div>
      {/* Mode bar */}
      <div className="actuator-mode-bar page-section">
        <div className="mode-bar-left">
          <div className="mode-bar-title">
            Operation Mode
            <span style={{ marginLeft: 10 }}>
              {operationMode ? (
                <span
                  className={`status-badge ${isAuto ? 'status-badge-green' : 'status-badge-blue'}`}
                >
                  <span className="status-dot" />
                  {isAuto ? 'Autonomous' : 'Manual'}
                </span>
              ) : (
                <span className="status-badge status-badge-gray">Unknown</span>
              )}
            </span>
          </div>
          <div className="mode-bar-desc">
            {isAuto
              ? 'PID controllers are managing all actuators automatically'
              : 'Manual mode — you control all actuators directly'}
          </div>
        </div>
        <button
          className={`mode-toggle-btn ${isAuto ? 'to-manual' : 'to-auto'}`}
          onClick={onToggleMode}
          disabled={loading || !operationMode}
        >
          {isAuto ? (
            <>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              Switch to Manual
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93A10 10 0 115 19.07"/>
              </svg>
              Switch to Autonomous
            </>
          )}
        </button>
      </div>

      {/* Warning when in auto mode */}
      {isAuto && (
        <div className="auto-warning page-section">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13" strokeLinecap="round"/>
            <line x1="12" y1="17" x2="12.01" y2="17" strokeLinecap="round"/>
          </svg>
          System is in <strong>Autonomous</strong> mode. Switch to Manual to control actuators.
        </div>
      )}

      {/* Actuator cards */}
      {actuators ? (
        <div className="grid-2">
          {ACTUATORS.map(cfg => (
            <ActuatorCard
              key={cfg.key}
              config={cfg}
              data={actuators[cfg.key]}
              operationMode={operationMode}
              onControlState={onControlState}
              onControlPower={onControlPower}
            />
          ))}
          <PHPumpCard operationMode={operationMode} />
        </div>
      ) : (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
          </svg>
          Waiting for actuator data…
        </div>
      )}
    </div>
  );
}

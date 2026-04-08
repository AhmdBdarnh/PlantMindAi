import React from 'react';

const fmt = v => (v !== undefined && v !== null ? v : 'N/A');

function SensorSummaryCard({ icon, iconBg, iconColor, label, value, unit, time }) {
  return (
    <div className="sensor-summary-card">
      <div className="sensor-card-header">
        <div>
          <div className="sensor-card-label">{label}</div>
        </div>
        <div className="sensor-card-icon-wrap" style={{ background: iconBg }}>
          <svg viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={icon} />
          </svg>
        </div>
      </div>
      <div>
        <span className="sensor-card-value">{fmt(value)}</span>
        {unit && <span className="sensor-card-unit">{unit}</span>}
      </div>
      {time && <div className="sensor-card-time">Updated {time}</div>}
    </div>
  );
}

function SetpointItem({ label, value, unit }) {
  return (
    <div className="setpoint-item">
      <div className="setpoint-label">{label}</div>
      <div className="setpoint-value">
        {value !== undefined && value !== null ? value : <span className="na">N/A</span>}
        {unit && value !== undefined && value !== null && (
          <span className="setpoint-unit">{unit}</span>
        )}
      </div>
    </div>
  );
}

function getLatestImage(sessions) {
  for (const session of (sessions || [])) {
    for (const img of (session.images || [])) {
      if (img.success && img.url) return { url: img.url, ts: session.timestamp };
    }
  }
  return null;
}

export default function Dashboard({ sensors, setpoints, lastUpdate, captureSessions }) {
  const latestImage = getLatestImage(captureSessions);
  const sp = setpoints || {};
  const s  = sensors   || {};

  const sensorCards = [
    {
      label: 'Air Temperature',
      value: s.air_temperature,
      unit: '°C',
      iconBg: '#fef3c7',
      iconColor: '#d97706',
      icon: 'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z',
    },
    {
      label: 'Air Humidity',
      value: s.air_humidity,
      unit: '%',
      iconBg: '#eff6ff',
      iconColor: '#3b82f6',
      icon: 'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
    },
    {
      label: 'Soil Temperature',
      value: s.soil_temperature,
      unit: '°C',
      iconBg: '#fef9c3',
      iconColor: '#ca8a04',
      icon: 'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z',
    },
    {
      label: 'Soil Moisture',
      value: s.soil_humidity,
      unit: '%',
      iconBg: '#ecfdf5',
      iconColor: '#059669',
      icon: 'M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05zm6.9-8.28c1.47 0 2.67-1.22 2.67-2.7 0-.78-.38-1.51-1.14-2.13-.76-.62-1.17-1.61-1.53-2.2-.36.59-.78 1.58-1.53 2.2-.76.62-1.14 1.35-1.14 2.14 0 1.47 1.2 2.69 2.67 2.69z M13 21v-2 M13 15v-1',
    },
    {
      label: 'Light Intensity',
      value: s.light_intensity,
      unit: 'Lux',
      iconBg: '#fefce8',
      iconColor: '#eab308',
      icon: 'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z',
    },
    {
      label: 'Soil pH',
      value: s.soil_ph,
      unit: '',
      iconBg: '#f5f3ff',
      iconColor: '#8b5cf6',
      icon: 'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18',
    },
    {
      label: 'Soil EC',
      value: s.soil_ec,
      unit: 'µS/cm',
      iconBg: '#f0fdfa',
      iconColor: '#0d9488',
      icon: 'M13 10V3L4 14h7v7l9-11h-7z',
    },
  ];

  return (
    <div>
      {/* ── Hero row: Plant info + Plant image ── */}
      <div className="dash-hero page-section">
        {/* Left: Info + setpoints */}
        <div className="dash-plant-info">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
            <div className="dash-plant-name">Lettuce</div>
            <span className="status-badge status-badge-green">
              <span className="status-dot" />
              Monitoring
            </span>
          </div>

          <div style={{ marginBottom: 14 }}>
            <div className="card-subtitle" style={{ marginBottom: 10 }}>
              Current Setpoints
            </div>
            <div className="setpoints-grid">
              <SetpointItem label="Temperature"   value={sp.temperature}    unit="°C" />
              <SetpointItem label="Humidity"      value={sp.humidity}       unit="%" />
              <SetpointItem label="Soil Moisture" value={sp.soil_moisture}  unit="%" />
              <SetpointItem label="Light"         value={sp.light}          unit="Lux" />
            </div>
          </div>

          {lastUpdate && (
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 8, display:'flex', alignItems:'center', gap:5 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{width:12,height:12}}>
                <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2" strokeLinecap="round"/>
              </svg>
              Last updated: {lastUpdate}
            </div>
          )}
        </div>

        {/* Right: Plant image */}
        <div className="dash-plant-image-card">
          <div className="plant-image-area">
            <img src="/plant.jpeg" alt="Lettuce plant" />
          </div>
        </div>
      </div>

      {/* ── Sensor summary grid ── */}
      <div className="page-section">
        <div className="section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{width:18,height:18}}>
            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Sensor Readings
        </div>

        {sensors ? (
          <div className="grid-3">
            {sensorCards.map(c => (
              <SensorSummaryCard key={c.label} {...c} time={lastUpdate} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
            </svg>
            Waiting for sensor data…
          </div>
        )}
      </div>
    </div>
  );
}

import React from 'react';

/* ── SVG Line chart (no external dep) ──────────────────────── */
function LineChart({ data, dataKey, color, height = 120 }) {
  if (!data || data.length < 2) {
    return <div className="chart-empty">Collecting data…</div>;
  }

  const values = data.map(d => parseFloat(d[dataKey])).filter(v => !isNaN(v));
  if (values.length < 2) return <div className="chart-empty">Collecting data…</div>;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 400, H = height;
  const padX = 4, padY = 6;
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;

  const pts = values.map((v, i) => {
    const x = padX + (i / (values.length - 1)) * innerW;
    const y = padY + innerH - ((v - min) / range) * innerH;
    return [x, y];
  });

  const linePts  = pts.map(([x, y]) => `${x},${y}`).join(' ');
  const areaPts  = [
    `${pts[0][0]},${padY + innerH}`,
    ...pts.map(([x, y]) => `${x},${y}`),
    `${pts[pts.length - 1][0]},${padY + innerH}`,
  ].join(' ');

  const gradId = `grad-${dataKey}-${color.replace('#', '')}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="line-chart-full"
      preserveAspectRatio="none"
      style={{ height }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0"    />
        </linearGradient>
      </defs>
      <polygon fill={`url(#${gradId})`} points={areaPts} />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={linePts}
      />
      {/* last dot */}
      <circle
        cx={pts[pts.length - 1][0]}
        cy={pts[pts.length - 1][1]}
        r="3"
        fill={color}
      />
    </svg>
  );
}

/* ── Mini stats below chart ── */
function ChartStats({ data, dataKey }) {
  const values = (data || []).map(d => parseFloat(d[dataKey])).filter(v => !isNaN(v));
  if (values.length === 0) return null;
  const min = Math.min(...values).toFixed(1);
  const max = Math.max(...values).toFixed(1);
  const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
  return (
    <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
      {[['Min', min], ['Avg', avg], ['Max', max]].map(([lbl, val]) => (
        <div key={lbl} style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ fontWeight: 600, color: 'var(--text)' }}>{val}</span> {lbl}
        </div>
      ))}
    </div>
  );
}

const fmt = v => (v !== undefined && v !== null ? v : 'N/A');

const SENSORS = [
  {
    key:   'air_temperature',
    label: 'Air Temperature',
    unit:  '°C',
    color: '#f59e0b',
    iconBg: '#fef3c7',
    iconColor: '#d97706',
    icon:  'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z',
  },
  {
    key:   'soil_temperature',
    label: 'Soil Temperature',
    unit:  '°C',
    color: '#ef4444',
    iconBg: '#fee2e2',
    iconColor: '#ef4444',
    icon:  'M14 14.76V3.5a2.5 2.5 0 00-5 0v11.26a4.5 4.5 0 105 0z',
  },
  {
    key:   'air_humidity',
    label: 'Air Humidity',
    unit:  '%',
    color: '#3b82f6',
    iconBg: '#eff6ff',
    iconColor: '#3b82f6',
    icon:  'M12 2.69l5.66 5.66a8 8 0 11-11.31 0L12 2.69z',
  },
  {
    key:   'soil_humidity',
    label: 'Soil Moisture',
    unit:  '%',
    color: '#22c55e',
    iconBg: '#dcfce7',
    iconColor: '#16a34a',
    icon:  'M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z',
  },
  {
    key:   'light_intensity',
    label: 'Light Intensity',
    unit:  'Lux',
    color: '#eab308',
    iconBg: '#fefce8',
    iconColor: '#ca8a04',
    icon:  'M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41M12 6a6 6 0 000 12 6 6 0 000-12z',
  },
  {
    key:   'soil_ph',
    label: 'Soil pH',
    unit:  'pH',
    color: '#8b5cf6',
    iconBg: '#f5f3ff',
    iconColor: '#8b5cf6',
    icon:  'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18',
  },
  {
    key:   'soil_ec',
    label: 'Soil EC',
    unit:  'µS/cm',
    color: '#14b8a6',
    iconBg: '#f0fdfa',
    iconColor: '#0d9488',
    icon:  'M13 10V3L4 14h7v7l9-11h-7z',
  },
];

export default function PlantEnvironment({ sensors, sensorHistory, lastUpdate }) {
  const s = sensors || {};

  return (
    <div>
      <div className="page-section">
        <div className="section-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{width:18,height:18}}>
            <path d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Sensor Data — Live &amp; History
          {lastUpdate && (
            <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 8 }}>
              Updated {lastUpdate}
            </span>
          )}
        </div>

        <div className="grid-2">
          {SENSORS.map(sensor => (
            <div className="env-sensor-card" key={sensor.key}>
              <div className="env-sensor-top">
                <div className="env-sensor-name">
                  <div
                    className="card-icon"
                    style={{ background: sensor.iconBg, width: 30, height: 30 }}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke={sensor.iconColor}
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      style={{ width: 15, height: 15 }}
                    >
                      <path d={sensor.icon} />
                    </svg>
                  </div>
                  {sensor.label}
                </div>
                <span
                  className="status-badge"
                  style={{ background: sensor.iconBg, color: sensor.iconColor }}
                >
                  {sensor.unit}
                </span>
              </div>

              <div className="env-sensor-big">
                {fmt(s[sensor.key])}
                {s[sensor.key] !== undefined && s[sensor.key] !== null && (
                  <span className="unit"> {sensor.unit}</span>
                )}
              </div>

              <div className="env-sensor-meta">
                {sensorHistory.length > 0
                  ? `${sensorHistory.length} readings collected`
                  : 'No history yet'}
              </div>

              <LineChart
                data={sensorHistory}
                dataKey={sensor.key}
                color={sensor.color}
                height={100}
              />

              <ChartStats data={sensorHistory} dataKey={sensor.key} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

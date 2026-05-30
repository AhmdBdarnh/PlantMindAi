import React from 'react';
import LineChart, { ChartStats } from '../components/LineChart';
import { fmt } from '../utils/format';

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

import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const API_BASE_URL = 'http://localhost:5000/api';

function App() {
  const [sensors, setSensors] = useState(null);
  const [actuators, setActuators] = useState(null);
  const [operationMode, setOperationMode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Plant health
  const [healthResult, setHealthResult] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthLastChecked, setHealthLastChecked] = useState(null);

  // Capture sessions gallery
  const [showCaptureSessions, setShowCaptureSessions] = useState(false);
  const [captureSessions, setCaptureSessions] = useState([]);
  const [captureSessionsLoading, setCaptureSessionsLoading] = useState(false);
  const [captureManualLoading, setCaptureManualLoading] = useState(false);
  const [captureManualError, setCaptureManualError] = useState(null);

  // ==================== DATA FETCHING ====================

  const fetchSensors = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/sensors`);
      const data = await response.json();
      if (data.success) {
        setSensors(data.data);
        setLastUpdate(new Date().toLocaleTimeString());
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    }
  };

  const fetchActuators = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/actuators`);
      const data = await response.json();
      if (data.success) {
        setActuators(data.data);
      }
    } catch (err) {
      // silent – sensor error message is enough
    }
  };

  const fetchOperationMode = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/operation_mode`);
      const data = await response.json();
      if (data.success) setOperationMode(data.mode);
    } catch (err) {
      // silent
    }
  };

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    await Promise.all([fetchSensors(), fetchActuators(), fetchOperationMode()]);
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ==================== OPERATION MODE ====================

  const toggleOperationMode = async () => {
    setLoading(true);
    setError(null);
    try {
      const newMode = operationMode === 'manual' ? 'autonomous' : 'manual';
      const response = await fetch(`${API_BASE_URL}/operation_mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      const data = await response.json();
      if (data.success) {
        setOperationMode(data.mode);
      } else {
        setError(data.error || 'Failed to change operation mode');
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==================== ACTUATOR CONTROL ====================

  const controlActuator = async (actuatorName, state) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/actuators/${actuatorName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state }),
      });
      const data = await response.json();
      if (data.success) {
        await fetchActuators();
      } else {
        setError(data.error || `Failed to control ${actuatorName}`);
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const controlActuatorPower = async (actuatorName, dutyCycle) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/actuators/${actuatorName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duty_cycle: dutyCycle }),
      });
      const data = await response.json();
      if (data.success) {
        await fetchActuators();
      } else {
        setError(data.error || `Failed to control ${actuatorName}`);
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==================== PLANT HEALTH ====================

  const fetchLatestHealthResult = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/plant_health`);
      if (response.status === 404) return;
      const data = await response.json();
      setHealthResult(data);
      setHealthLastChecked(new Date().toLocaleTimeString());
    } catch (err) {
      // silent
    }
  };

  const checkPlantHealth = async () => {
    setHealthLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/plant_health`, { method: 'POST' });
      const data = await response.json();
      setHealthResult(data);
      setHealthLastChecked(new Date().toLocaleTimeString());
      // Also refresh capture sessions if the panel is open
      if (showCaptureSessions) fetchCaptureSessions();
    } catch (err) {
      setHealthResult({ success: false, error: 'Connection error: ' + err.message });
    } finally {
      setHealthLoading(false);
    }
  };

  // ==================== CAPTURE SESSIONS ====================

  const fetchCaptureSessions = async () => {
    setCaptureSessionsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/capture_sessions?limit=20`);
      const data = await response.json();
      if (data.success) setCaptureSessions(data.sessions);
    } catch (err) {
      // silent
    } finally {
      setCaptureSessionsLoading(false);
    }
  };

  const triggerCaptureNow = async () => {
    setCaptureManualLoading(true);
    setCaptureManualError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/capture_sessions`, { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        // Prepend the new session, keep list sorted newest-first
        setCaptureSessions(prev => [data.session, ...prev].slice(0, 20));
        // Also refresh health result since a health check ran
        fetchLatestHealthResult();
      } else {
        setCaptureManualError(data.error || 'Capture failed');
      }
    } catch (err) {
      setCaptureManualError('Connection error: ' + err.message);
    } finally {
      setCaptureManualLoading(false);
    }
  };

  // ==================== EFFECTS ====================

  // Initial load + auto-refresh every 3 seconds
  useEffect(() => {
    fetchAllData();
    if (autoRefresh) {
      const interval = setInterval(fetchAllData, 3000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch latest health result on mount and every 60 seconds
  useEffect(() => {
    fetchLatestHealthResult();
    const interval = setInterval(fetchLatestHealthResult, 60000);
    return () => clearInterval(interval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load capture sessions whenever the gallery opens
  useEffect(() => {
    if (showCaptureSessions) fetchCaptureSessions();
  }, [showCaptureSessions]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh sessions every 2 minutes while the gallery is open
  useEffect(() => {
    if (!showCaptureSessions) return;
    const interval = setInterval(fetchCaptureSessions, 120000);
    return () => clearInterval(interval);
  }, [showCaptureSessions]); // eslint-disable-line react-hooks/exhaustive-deps

  // ==================== HELPERS ====================

  const formatTimestamp = (ts) => {
    if (!ts) return 'Unknown';
    try {
      const d = new Date(ts);
      return d.toLocaleString();
    } catch {
      return ts;
    }
  };

  const healthBadge = (session) => {
    const h = session.health;
    if (!h) return { label: 'No check', cls: 'badge-neutral' };
    if (!h.success) return { label: 'Check failed', cls: 'badge-error' };
    if (h.is_healthy) return { label: `Healthy ${h.health_probability}%`, cls: 'badge-healthy' };
    return { label: `Issues ${h.health_probability}%`, cls: 'badge-unhealthy' };
  };

  // ==================== RENDER ====================

  return (
    <div className="App">
      <header className="App-header">
        <h1>🌱 Smart Greenhouse Control Panel</h1>
      </header>

      <div className="container">
        {/* Status Bar */}
        <div className="status-bar">
          <div className="status-info">
            {lastUpdate && (
              <span className="last-update">🕒 Last Update: {lastUpdate}</span>
            )}
            {loading && <span className="loading-indicator">⟳ Loading...</span>}
          </div>
          <div className="refresh-controls">
            <label className="refresh-toggle">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              <span>Auto-Refresh (3s)</span>
            </label>
            <button
              onClick={fetchAllData}
              disabled={loading}
              className="btn btn-secondary btn-refresh"
            >
              🔄 Refresh Now
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="error-box">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Operation Mode */}
        <section className="section mode-section">
          <div className="mode-container">
            <div className="mode-info">
              <h2>🎚️ Operation Mode</h2>
              {operationMode ? (
                <div className="mode-display">
                  <p className="mode-text">
                    Current Mode:{' '}
                    <span className={`mode-badge ${operationMode}`}>
                      {operationMode.toUpperCase()}
                    </span>
                  </p>
                  {operationMode === 'manual' ? (
                    <p className="mode-description">
                      Manual mode: You have full control over all actuators
                    </p>
                  ) : (
                    <p className="mode-description">
                      Autonomous mode: PID controllers automatically manage climate
                    </p>
                  )}
                </div>
              ) : (
                <p className="mode-text">Click button to fetch current mode</p>
              )}
            </div>
            <div className="mode-controls">
              <button
                onClick={fetchOperationMode}
                disabled={loading}
                className="btn btn-primary"
              >
                {loading ? 'Loading...' : '🔄 Check Mode'}
              </button>
              <button
                onClick={toggleOperationMode}
                disabled={loading || !operationMode}
                className={`btn btn-toggle ${operationMode === 'autonomous' ? 'btn-manual' : 'btn-autonomous'}`}
              >
                {loading
                  ? 'Switching...'
                  : operationMode === 'manual'
                  ? '🤖 Switch to Autonomous'
                  : '👤 Switch to Manual'}
              </button>
            </div>
          </div>
        </section>

        {/* Plant Captures Section */}
        <section className="section camera-section">
          <div className="camera-section-header">
            <h2>📸 Plant Captures</h2>
            <div className="camera-section-actions">
              <button
                className="btn btn-captures"
                onClick={() => setShowCaptureSessions(true)}
              >
                🖼️ View Captures
              </button>
              <button
                className="btn btn-health-check"
                onClick={checkPlantHealth}
                disabled={healthLoading}
              >
                {healthLoading ? 'Analyzing...' : '🔬 Check Plant Health Now'}
              </button>
            </div>
          </div>

          {/* Auto-capture status banner */}
          <div className="capture-auto-banner">
            <span className="capture-auto-icon">⏱️</span>
            <div className="capture-auto-text">
              <strong>Automatic capture active</strong>
              <span>Cameras capture every 2 minutes → uploaded to S3 → plant health checked automatically.</span>
            </div>
          </div>

          {/* Plant Health Result */}
          {healthLastChecked && (
            <p className="health-auto-info">
              Auto-check every 60s · Last updated: {healthLastChecked}
            </p>
          )}
          {healthResult && (
            <div
              className={`health-result-panel ${
                healthResult.success
                  ? healthResult.is_healthy
                    ? 'healthy'
                    : 'unhealthy'
                  : 'error'
              }`}
            >
              {!healthResult.success ? (
                <p className="health-error">Error: {healthResult.error}</p>
              ) : (
                <>
                  <div className="health-summary">
                    <span className="health-icon">
                      {healthResult.is_healthy ? '✅' : '⚠️'}
                    </span>
                    <div>
                      <h3 className="health-title">
                        {healthResult.is_healthy
                          ? 'Plant is Healthy'
                          : 'Plant Health Issue Detected'}
                      </h3>
                      <p className="health-confidence">
                        Health confidence: <strong>{healthResult.health_probability}%</strong>
                        {' · '}{healthResult.images_sent} image
                        {healthResult.images_sent !== 1 ? 's' : ''} analyzed
                      </p>
                    </div>
                  </div>

                  {!healthResult.is_healthy &&
                    healthResult.diseases &&
                    healthResult.diseases.length > 0 && (
                      <div className="disease-list">
                        <h4>Detected Issues</h4>
                        {healthResult.diseases.map((disease, idx) => (
                          <div key={idx} className="disease-card">
                            <div className="disease-header">
                              <span className="disease-name">{disease.name}</span>
                              <span className="disease-probability">
                                {disease.probability}%
                              </span>
                            </div>
                            {disease.description && (
                              <p className="disease-description">{disease.description}</p>
                            )}
                            {disease.treatment && (
                              <div className="disease-treatment">
                                {disease.treatment.prevention &&
                                  disease.treatment.prevention.length > 0 && (
                                    <div>
                                      <strong>Prevention:</strong>
                                      <ul>
                                        {disease.treatment.prevention.map((p, i) => (
                                          <li key={i}>{p}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                {disease.treatment.biological &&
                                  disease.treatment.biological.length > 0 && (
                                    <div>
                                      <strong>Biological treatment:</strong>
                                      <ul>
                                        {disease.treatment.biological.map((b, i) => (
                                          <li key={i}>{b}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                {disease.treatment.chemical &&
                                  disease.treatment.chemical.length > 0 && (
                                    <div>
                                      <strong>Chemical treatment:</strong>
                                      <ul>
                                        {disease.treatment.chemical.map((c, i) => (
                                          <li key={i}>{c}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                </>
              )}
            </div>
          )}
        </section>

        {/* ===================== CAPTURE SESSIONS OVERLAY ===================== */}
        {showCaptureSessions && (
          <div className="sessions-overlay">
            <div className="sessions-page">
              {/* Header */}
              <div className="sessions-header">
                <div>
                  <h2>🖼️ Plant Capture Sessions</h2>
                  <p className="sessions-subtitle">
                    Automatic captures every 2 minutes · Stored in S3 + MongoDB
                  </p>
                </div>
                <button
                  className="sessions-close"
                  onClick={() => setShowCaptureSessions(false)}
                >
                  ✕ Close
                </button>
              </div>

              {/* Manual trigger */}
              <div className="sessions-controls">
                <button
                  className="btn btn-capture-now"
                  onClick={triggerCaptureNow}
                  disabled={captureManualLoading}
                >
                  {captureManualLoading
                    ? '⏳ Capturing & uploading...'
                    : '📸 Capture Now'}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={fetchCaptureSessions}
                  disabled={captureSessionsLoading}
                >
                  🔄 Refresh
                </button>
                {captureManualError && (
                  <div className="sessions-error">❌ {captureManualError}</div>
                )}
              </div>

              {captureManualLoading && (
                <div className="sessions-loading-bar">
                  <div className="sessions-loading-fill" />
                  <p>Capturing from all 3 cameras, uploading to S3, running health check…</p>
                </div>
              )}

              {/* Session list */}
              {captureSessionsLoading && captureSessions.length === 0 && (
                <div className="sessions-empty">
                  <p>Loading capture sessions…</p>
                </div>
              )}

              {!captureSessionsLoading && captureSessions.length === 0 && (
                <div className="sessions-empty">
                  <p>
                    No captures yet. The system captures every 2 minutes automatically,
                    or press <strong>Capture Now</strong> to take photos immediately.
                  </p>
                </div>
              )}

              {captureSessions.map((session, idx) => {
                const badge = healthBadge(session);
                const ts = formatTimestamp(session.timestamp);
                const isLatest = idx === 0;
                const successImages = (session.images || []).filter(img => img.success);
                const failedImages = (session.images || []).filter(img => !img.success);

                return (
                  <div
                    key={session.session_id || idx}
                    className={`session-card ${isLatest ? 'session-latest' : 'session-previous'}`}
                  >
                    {/* Card header */}
                    <div className="session-card-header">
                      <div className="session-card-meta">
                        <span className={`session-label ${isLatest ? 'label-latest' : 'label-previous'}`}>
                          {isLatest ? '🟢 Latest' : `#${idx + 1}`}
                        </span>
                        <span className="session-timestamp">🕒 {ts}</span>
                        <span className="session-camera-count">
                          📷 {session.camera_count}/3 cameras
                        </span>
                        {session.triggered_by && (
                          <span className="session-trigger">
                            {session.triggered_by === 'manual' ? '👆 Manual' : '⏱️ Auto'}
                          </span>
                        )}
                      </div>
                      <span className={`session-health-badge ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </div>

                    {/* Images row */}
                    <div className="session-images-row">
                      {successImages.length === 0 && (
                        <p className="session-no-images">
                          No images were captured in this session.
                        </p>
                      )}
                      {successImages.map((img) => (
                        <div key={img.camera_id} className="session-image-card">
                          <div className="session-cam-label">Camera {img.camera_id}</div>
                          <div className="session-cam-name">{img.camera_name}</div>
                          {img.url ? (
                            <a href={img.url} target="_blank" rel="noopener noreferrer">
                              <img
                                src={img.url}
                                alt={`Camera ${img.camera_id}`}
                                className="session-image"
                                onError={(e) => {
                                  e.target.style.display = 'none';
                                  e.target.nextSibling.style.display = 'flex';
                                }}
                              />
                              <div className="session-image-expired" style={{ display: 'none' }}>
                                🔗 URL expired – <a href={img.url} target="_blank" rel="noopener noreferrer">open link</a>
                              </div>
                            </a>
                          ) : (
                            <div className="session-image-missing">No URL</div>
                          )}
                          <div className="session-s3-badge">✅ S3</div>
                        </div>
                      ))}

                      {/* Failed camera placeholders */}
                      {failedImages.map((img) => (
                        <div key={img.camera_id} className="session-image-card session-image-failed">
                          <div className="session-cam-label">Camera {img.camera_id}</div>
                          <div className="session-cam-name">{img.camera_name}</div>
                          <div className="session-image-error">
                            <span>⚠️ Failed</span>
                            {img.error && <small>{img.error}</small>}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Health details (collapsed by default for older sessions) */}
                    {session.health && session.health.success && (
                      <div className={`session-health ${session.health.is_healthy ? 'health-ok' : 'health-warn'}`}>
                        <span>
                          {session.health.is_healthy ? '✅ Healthy' : '⚠️ Issues detected'}
                          {' — '}confidence: <strong>{session.health.health_probability}%</strong>
                          {!session.health.is_healthy &&
                            session.health.diseases &&
                            session.health.diseases.length > 0 &&
                            ` · Top issue: ${session.health.diseases[0].name} (${session.health.diseases[0].probability}%)`}
                        </span>
                      </div>
                    )}
                    {session.health && !session.health.success && (
                      <div className="session-health health-error-row">
                        ⚠️ Health check failed: {session.health.error}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ==================== SENSOR SECTION ==================== */}
        <section className="section">
          <h2>📊 Sensor Readings</h2>
          {sensors ? (
            <div className="data-grid">
              <div className="data-card">
                <h3>🌡️ Air Temperature</h3>
                <p className="value">{sensors.air_temperature}°C</p>
              </div>
              <div className="data-card">
                <h3>💧 Air Humidity</h3>
                <p className="value">{sensors.air_humidity}%</p>
              </div>
              <div className="data-card">
                <h3>💡 Light Intensity</h3>
                <p className="value">{sensors.light_intensity} Lux</p>
              </div>
              <div className="data-card">
                <h3>🌿 Soil Humidity</h3>
                <p className="value">{sensors.soil_humidity}%</p>
              </div>
              <div className="data-card">
                <h3>🧪 Soil pH</h3>
                <p className="value">{sensors.soil_ph}</p>
              </div>
              <div className="data-card">
                <h3>⚡ Soil EC</h3>
                <p className="value">{sensors.soil_ec} µS/cm</p>
              </div>
              <div className="data-card">
                <h3>🌡️ Soil Temp</h3>
                <p className="value">{sensors.soil_temperature}°C</p>
              </div>
              <div className="data-card">
                <h3>🚰 Water Flow</h3>
                <p className="value">{sensors.water_flow} L/min</p>
              </div>
              <div className="data-card">
                <h3>💧 Water Amount</h3>
                <p className="value">{sensors.water_amount} L</p>
              </div>
              <div className="data-card">
                <h3>⚡ Voltage</h3>
                <p className="value">{sensors.voltage} V</p>
              </div>
              <div className="data-card">
                <h3>🔌 Current</h3>
                <p className="value">{sensors.current} A</p>
              </div>
              <div className="data-card">
                <h3>💡 Power</h3>
                <p className="value">{sensors.power} W</p>
              </div>
              <div className="data-card">
                <h3>🔋 Energy</h3>
                <p className="value">{sensors.energy} Wh</p>
              </div>
              <div className="data-card">
                <h3>📡 Frequency</h3>
                <p className="value">{sensors.frequency} Hz</p>
              </div>
            </div>
          ) : (
            <div className="no-data">
              <p>No sensor data available. Waiting for data...</p>
            </div>
          )}
        </section>

        {/* ==================== ACTUATOR SECTION ==================== */}
        <section className="section">
          <h2>🎛️ Actuator Controls</h2>

          {operationMode === 'autonomous' && (
            <div className="warning-box">
              <strong>⚠️ Warning:</strong> System is in AUTONOMOUS mode. Manual controls are
              disabled. Switch to MANUAL mode to control actuators manually.
            </div>
          )}

          {actuators ? (
            <div className="actuator-grid">
              {/* Heater */}
              <div className="actuator-card">
                <h3>🔥 Heater</h3>
                <p className="status">
                  Status:{' '}
                  <span className={`badge ${actuators.heater.state}`}>
                    {actuators.heater.state.toUpperCase()}
                  </span>
                </p>
                <p className="percentage">{actuators.heater.percentage}% Power</p>
                <div className="power-control">
                  <label htmlFor="heater-power" className="slider-label">
                    Power Level: {Math.round((actuators.heater.duty_cycle / 4095) * 100)}%
                  </label>
                  <input
                    type="range"
                    id="heater-power"
                    min="0"
                    max="4095"
                    value={actuators.heater.duty_cycle}
                    onChange={(e) => controlActuatorPower('heater', parseInt(e.target.value))}
                    disabled={loading || operationMode === 'autonomous'}
                    className="power-slider"
                  />
                  <div className="slider-markers">
                    <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
                  </div>
                </div>
                <div className="button-group">
                  <button onClick={() => controlActuator('heater', 'on')} disabled={loading || operationMode === 'autonomous'} className="btn btn-success">Turn ON</button>
                  <button onClick={() => controlActuator('heater', 'off')} disabled={loading || operationMode === 'autonomous'} className="btn btn-danger">Turn OFF</button>
                </div>
              </div>

              {/* Light Strips */}
              <div className="actuator-card">
                <h3>💡 Light Strips</h3>
                <p className="status">
                  Status:{' '}
                  <span className={`badge ${actuators.light.state}`}>
                    {actuators.light.state.toUpperCase()}
                  </span>
                </p>
                <p className="percentage">{actuators.light.percentage}% Power</p>
                <div className="power-control">
                  <label htmlFor="light-power" className="slider-label">
                    Brightness: {Math.round((actuators.light.duty_cycle / 4095) * 100)}%
                  </label>
                  <input
                    type="range"
                    id="light-power"
                    min="0"
                    max="4095"
                    value={actuators.light.duty_cycle}
                    onChange={(e) => controlActuatorPower('light', parseInt(e.target.value))}
                    disabled={loading || operationMode === 'autonomous'}
                    className="power-slider"
                  />
                  <div className="slider-markers">
                    <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
                  </div>
                </div>
                <div className="button-group">
                  <button onClick={() => controlActuator('light', 'on')} disabled={loading || operationMode === 'autonomous'} className="btn btn-success">Turn ON</button>
                  <button onClick={() => controlActuator('light', 'off')} disabled={loading || operationMode === 'autonomous'} className="btn btn-danger">Turn OFF</button>
                </div>
              </div>

              {/* Fan */}
              <div className="actuator-card">
                <h3>🌀 Fan</h3>
                <p className="status">
                  Status:{' '}
                  <span className={`badge ${actuators.fan.state}`}>
                    {actuators.fan.state.toUpperCase()}
                  </span>
                </p>
                <p className="percentage">{actuators.fan.percentage}% Power</p>
                <div className="power-control">
                  <label htmlFor="fan-power" className="slider-label">
                    Speed: {Math.round((actuators.fan.duty_cycle / 4095) * 100)}%
                  </label>
                  <input
                    type="range"
                    id="fan-power"
                    min="0"
                    max="4095"
                    value={actuators.fan.duty_cycle}
                    onChange={(e) => controlActuatorPower('fan', parseInt(e.target.value))}
                    disabled={loading || operationMode === 'autonomous'}
                    className="power-slider"
                  />
                  <div className="slider-markers">
                    <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
                  </div>
                </div>
                <div className="button-group">
                  <button onClick={() => controlActuator('fan', 'on')} disabled={loading || operationMode === 'autonomous'} className="btn btn-success">Turn ON</button>
                  <button onClick={() => controlActuator('fan', 'off')} disabled={loading || operationMode === 'autonomous'} className="btn btn-danger">Turn OFF</button>
                </div>
              </div>

              {/* Water Pump */}
              <div className="actuator-card">
                <h3>💦 Water Pump</h3>
                <p className="status">
                  Status:{' '}
                  <span className={`badge ${actuators.water_pump.state}`}>
                    {actuators.water_pump.state.toUpperCase()}
                  </span>
                </p>
                <p className="percentage">{actuators.water_pump.percentage}% Power</p>
                <div className="power-control">
                  <label htmlFor="pump-power" className="slider-label">
                    Flow Rate: {Math.round((actuators.water_pump.duty_cycle / 4095) * 100)}%
                  </label>
                  <input
                    type="range"
                    id="pump-power"
                    min="0"
                    max="4095"
                    value={actuators.water_pump.duty_cycle}
                    onChange={(e) => controlActuatorPower('water_pump', parseInt(e.target.value))}
                    disabled={loading || operationMode === 'autonomous'}
                    className="power-slider"
                  />
                  <div className="slider-markers">
                    <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
                  </div>
                </div>
                <div className="button-group">
                  <button onClick={() => controlActuator('water_pump', 'on')} disabled={loading || operationMode === 'autonomous'} className="btn btn-success">Turn ON</button>
                  <button onClick={() => controlActuator('water_pump', 'off')} disabled={loading || operationMode === 'autonomous'} className="btn btn-danger">Turn OFF</button>
                </div>
              </div>
            </div>
          ) : (
            <div className="no-data">
              <p>No actuator data available. Waiting for data...</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default App;

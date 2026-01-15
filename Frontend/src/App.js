import React, { useState, useEffect } from 'react';
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

  // Fetch sensor data
  const fetchSensors = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/sensors`);
      const data = await response.json();

      if (data.success) {
        setSensors(data.data);
        setLastUpdate(new Date().toLocaleTimeString());
      } else {
        setError(data.error || 'Failed to fetch sensors');
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch actuator states
  const fetchActuators = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/actuators`);
      const data = await response.json();

      if (data.success) {
        setActuators(data.data);
        setLastUpdate(new Date().toLocaleTimeString());
      } else {
        setError(data.error || 'Failed to fetch actuators');
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Fetch all data
  const fetchAllData = async () => {
    await Promise.all([
      fetchSensors(),
      fetchActuators(),
      fetchOperationMode()
    ]);
  };

  // Fetch operation mode
  const fetchOperationMode = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/operation_mode`);
      const data = await response.json();

      if (data.success) {
        setOperationMode(data.mode);
      } else {
        setError(data.error || 'Failed to fetch operation mode');
      }
    } catch (err) {
      setError('Failed to connect to backend: ' + err.message);
    }
  };

  // Toggle operation mode
  const toggleOperationMode = async () => {
    setLoading(true);
    setError(null);
    try {
      const newMode = operationMode === 'manual' ? 'autonomous' : 'manual';

      const response = await fetch(`${API_BASE_URL}/operation_mode`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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

  // Control actuator (on/off)
  const controlActuator = async (actuatorName, state) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/actuators/${actuatorName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ state }),
      });

      const data = await response.json();

      if (data.success) {
        // Refresh actuator states after control
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

  // Control actuator power (duty cycle)
  const controlActuatorPower = async (actuatorName, dutyCycle) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/actuators/${actuatorName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ duty_cycle: dutyCycle }),
      });

      const data = await response.json();

      if (data.success) {
        // Refresh actuator states after control
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

  // Auto-refresh data every 3 seconds
  useEffect(() => {
    // Fetch data on mount
    fetchAllData();

    // Set up interval for auto-refresh
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchAllData();
      }, 3000); // 3 seconds

      return () => clearInterval(interval);
    }
  }, [autoRefresh]); // eslint-disable-line react-hooks/exhaustive-deps

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
              <span className="last-update">
                🕒 Last Update: {lastUpdate}
              </span>
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

        {/* Operation Mode Section */}
        <section className="section mode-section">
          <div className="mode-container">
            <div className="mode-info">
              <h2>🎚️ Operation Mode</h2>
              {operationMode ? (
                <div className="mode-display">
                  <p className="mode-text">
                    Current Mode: <span className={`mode-badge ${operationMode}`}>
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
                {loading ? 'Switching...' : (
                  operationMode === 'manual'
                    ? '🤖 Switch to Autonomous'
                    : '👤 Switch to Manual'
                )}
              </button>
            </div>
          </div>
        </section>

        {/* Sensor Section */}
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

        {/* Actuator Section */}
        <section className="section">
          <h2>🎛️ Actuator Controls</h2>

          {operationMode === 'autonomous' && (
            <div className="warning-box">
              <strong>⚠️ Warning:</strong> System is in AUTONOMOUS mode. Manual controls are disabled.
              Switch to MANUAL mode to control actuators manually.
            </div>
          )}

          {actuators ? (
            <div className="actuator-grid">
              {/* Heater Control */}
            <div className="actuator-card">
              <h3>🔥 Heater</h3>
              {actuators && (
                <div>
                  <p className="status">
                    Status: <span className={`badge ${actuators.heater.state}`}>
                      {actuators.heater.state.toUpperCase()}
                    </span>
                  </p>
                  <p className="percentage">{actuators.heater.percentage}% Power</p>

                  {/* Power Slider */}
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
                      <span>0%</span>
                      <span>25%</span>
                      <span>50%</span>
                      <span>75%</span>
                      <span>100%</span>
                    </div>
                  </div>
                </div>
              )}
              <div className="button-group">
                <button
                  onClick={() => controlActuator('heater', 'on')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-success"
                >
                  Turn ON
                </button>
                <button
                  onClick={() => controlActuator('heater', 'off')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-danger"
                >
                  Turn OFF
                </button>
              </div>
            </div>

            {/* Light Control */}
            <div className="actuator-card">
              <h3>💡 Light Strips</h3>
              {actuators && (
                <div>
                  <p className="status">
                    Status: <span className={`badge ${actuators.light.state}`}>
                      {actuators.light.state.toUpperCase()}
                    </span>
                  </p>
                  <p className="percentage">{actuators.light.percentage}% Power</p>

                  {/* Power Slider */}
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
                      <span>0%</span>
                      <span>25%</span>
                      <span>50%</span>
                      <span>75%</span>
                      <span>100%</span>
                    </div>
                  </div>
                </div>
              )}
              <div className="button-group">
                <button
                  onClick={() => controlActuator('light', 'on')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-success"
                >
                  Turn ON
                </button>
                <button
                  onClick={() => controlActuator('light', 'off')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-danger"
                >
                  Turn OFF
                </button>
              </div>
            </div>

            {/* Fan Control */}
            <div className="actuator-card">
              <h3>🌀 Fan</h3>
              {actuators && (
                <div>
                  <p className="status">
                    Status: <span className={`badge ${actuators.fan.state}`}>
                      {actuators.fan.state.toUpperCase()}
                    </span>
                  </p>
                  <p className="percentage">{actuators.fan.percentage}% Power</p>

                  {/* Power Slider */}
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
                      <span>0%</span>
                      <span>25%</span>
                      <span>50%</span>
                      <span>75%</span>
                      <span>100%</span>
                    </div>
                  </div>
                </div>
              )}
              <div className="button-group">
                <button
                  onClick={() => controlActuator('fan', 'on')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-success"
                >
                  Turn ON
                </button>
                <button
                  onClick={() => controlActuator('fan', 'off')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-danger"
                >
                  Turn OFF
                </button>
              </div>
            </div>

            {/* Water Pump Control */}
            <div className="actuator-card">
              <h3>💦 Water Pump</h3>
              {actuators && (
                <div>
                  <p className="status">
                    Status: <span className={`badge ${actuators.water_pump.state}`}>
                      {actuators.water_pump.state.toUpperCase()}
                    </span>
                  </p>
                  <p className="percentage">{actuators.water_pump.percentage}% Power</p>

                  {/* Power Slider */}
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
                      <span>0%</span>
                      <span>25%</span>
                      <span>50%</span>
                      <span>75%</span>
                      <span>100%</span>
                    </div>
                  </div>
                </div>
              )}
              <div className="button-group">
                <button
                  onClick={() => controlActuator('water_pump', 'on')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-success"
                >
                  Turn ON
                </button>
                <button
                  onClick={() => controlActuator('water_pump', 'off')}
                  disabled={loading || operationMode === 'autonomous'}
                  className="btn btn-danger"
                >
                  Turn OFF
                </button>
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

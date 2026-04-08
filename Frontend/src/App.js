import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import Dashboard from './pages/Dashboard';
import PlantEnvironment from './pages/PlantEnvironment';
import ActuatorControl from './pages/ActuatorControl';
import ResourceConsumption from './pages/ResourceConsumption';
import PlantGrowth from './pages/PlantGrowth';
import LiveCams from './pages/LiveCams';

const API_BASE_URL = 'http://localhost:5000/api';
const MAX_HISTORY = 60;

const NAV_ITEMS = [
  { id: 'dashboard',    label: 'Dashboard',            icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { id: 'environment',  label: 'Plant Environment',    icon: 'M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z' },
  { id: 'actuators',    label: 'Actuator Control',     icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' },
  { id: 'resources',    label: 'Resource Consumption', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { id: 'growth',       label: 'Plant Growth',         icon: 'M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z' },
  { id: 'livecams',     label: 'Live Cams',            icon: 'M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z' },
];

function App() {
  const [activePage, setActivePage]     = useState('dashboard');
  const [sidebarOpen, setSidebarOpen]   = useState(true);

  // Core data
  const [sensors, setSensors]           = useState(null);
  const [actuators, setActuators]       = useState(null);
  const [operationMode, setOperationMode] = useState(null);
  const [setpoints, setSetpoints]       = useState(null);

  // Status
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);
  const [lastUpdate, setLastUpdate]     = useState(null);
  const [autoRefresh, setAutoRefresh]   = useState(true);

  // Sensor history for charts (ring buffer)
  const [sensorHistory, setSensorHistory] = useState([]);

  // Plant health
  const [healthResult, setHealthResult]       = useState(null);
  const [healthLoading, setHealthLoading]     = useState(false);
  const [healthLastChecked, setHealthLastChecked] = useState(null);

  // Capture sessions
  const [captureSessions, setCaptureSessions]             = useState([]);
  const [captureSessionsLoading, setCaptureSessionsLoading] = useState(false);
  const [captureManualLoading, setCaptureManualLoading]   = useState(false);
  const [captureManualError, setCaptureManualError]       = useState(null);

  // ==================== DATA FETCHING ====================

  const safeJson = async (res) => {
    const text = await res.text();
    try { return JSON.parse(text); } catch { return null; }
  };

  const fetchSensors = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/sensors`);
      const data = await safeJson(res);
      if (!data) { setError('Backend is offline — start the Flask server on port 5000'); return; }
      if (data.success) {
        setSensors(data.data);
        setLastUpdate(new Date().toLocaleTimeString());
        setSensorHistory(prev => {
          const entry = { ...data.data, time: new Date().toLocaleTimeString() };
          return [...prev, entry].slice(-MAX_HISTORY);
        });
      }
    } catch {
      setError('Backend is offline — start the Flask server on port 5000');
    }
  };

  const fetchActuators = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/actuators`);
      const data = await safeJson(res);
      if (data?.success) setActuators(data.data);
    } catch {}
  };

  const fetchOperationMode = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/operation_mode`);
      const data = await safeJson(res);
      if (data?.success) setOperationMode(data.mode);
    } catch {}
  };

  const fetchSetpoints = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/setpoints`);
      const data = await safeJson(res);
      if (data?.success) setSetpoints(data.setpoints);
    } catch {}
  };

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    await Promise.all([fetchSensors(), fetchActuators(), fetchOperationMode(), fetchSetpoints()]);
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ==================== OPERATION MODE ====================

  const toggleOperationMode = async () => {
    try {
      const newMode = operationMode === 'manual' ? 'autonomous' : 'manual';
      const res  = await fetch(`${API_BASE_URL}/operation_mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      });
      const data = await res.json();
      if (data.success) setOperationMode(data.mode);
      else setError(data.error || 'Failed to change mode');
    } catch (err) {
      setError('Connection failed: ' + err.message);
    }
  };

  // ==================== ACTUATOR CONTROL ====================

  const controlActuator = async (name, state) => {
    try {
      const res  = await fetch(`${API_BASE_URL}/actuators/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state }),
      });
      const data = await res.json();
      if (data.success) await fetchActuators();
      else setError(data.error || `Failed to control ${name}`);
    } catch (err) {
      setError('Connection failed: ' + err.message);
    }
  };

  const controlActuatorPower = async (name, dutyCycle) => {
    try {
      const res  = await fetch(`${API_BASE_URL}/actuators/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duty_cycle: dutyCycle }),
      });
      const data = await res.json();
      if (data.success) await fetchActuators();
      else setError(data.error || `Failed to control ${name}`);
    } catch (err) {
      setError('Connection failed: ' + err.message);
    }
  };

  // ==================== PLANT HEALTH ====================

  const fetchLatestHealthResult = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/plant_health`);
      if (res.status === 404) return;
      const data = await res.json();
      setHealthResult(data);
      setHealthLastChecked(new Date().toLocaleTimeString());
    } catch {}
  };

  const checkPlantHealth = async () => {
    setHealthLoading(true);
    try {
      const res  = await fetch(`${API_BASE_URL}/plant_health`, { method: 'POST' });
      const data = await res.json();
      setHealthResult(data);
      setHealthLastChecked(new Date().toLocaleTimeString());
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
      const res  = await fetch(`${API_BASE_URL}/capture_sessions?limit=20`);
      const data = await res.json();
      if (data.success) setCaptureSessions(data.sessions);
    } catch {}
    finally { setCaptureSessionsLoading(false); }
  };

  const triggerCaptureNow = async () => {
    setCaptureManualLoading(true);
    setCaptureManualError(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/capture_sessions`, { method: 'POST' });
      const data = await res.json();
      if (!data.success) {
        setCaptureManualError(data.error || 'Capture failed');
        setCaptureManualLoading(false);
        return;
      }
      // 202 pending — session is being built in the background; poll until it appears
      const poll = async (attemptsLeft) => {
        await fetchCaptureSessions();
        fetchLatestHealthResult();
        setCaptureManualLoading(false);
        if (attemptsLeft > 1) {
          // Schedule one more refresh after 5 s to pick up health result
          setTimeout(() => {
            fetchCaptureSessions();
            fetchLatestHealthResult();
          }, 5000);
        }
      };
      setTimeout(() => poll(2), 10000);
    } catch (err) {
      setCaptureManualError('Connection error: ' + err.message);
      setCaptureManualLoading(false);
    }
  };

  // ==================== EFFECTS ====================

  useEffect(() => {
    fetchAllData();
    if (autoRefresh) {
      const id = setInterval(fetchAllData, 3000);
      return () => clearInterval(id);
    }
  }, [autoRefresh]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchLatestHealthResult();
    const id = setInterval(fetchLatestHealthResult, 60000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchCaptureSessions();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ==================== RENDER ====================

  return (
    <div className="app-layout">

      {/* ── Sidebar ── */}
      <aside className={`sidebar ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <div className="sidebar-brand">
          <svg className="brand-leaf" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14.5v-4.74l-4 2.31-1-1.73 4-2.31-4-2.31 1-1.73 4 2.31V4.5h2v4.8l4-2.31 1 1.73-4 2.31 4 2.31-1 1.73-4-2.31v4.74h-2z" fill="currentColor"/>
          </svg>
          {sidebarOpen && <span className="brand-name">PlantMind AI</span>}
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              className={`nav-item ${activePage === item.id ? 'nav-active' : ''}`}
              onClick={() => setActivePage(item.id)}
              title={!sidebarOpen ? item.label : ''}
            >
              <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={item.icon} />
              </svg>
              {sidebarOpen && <span className="nav-label">{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          {sidebarOpen && operationMode && (
            <div className={`mode-pill mode-pill-${operationMode}`}>
              <span className="mode-dot" />
              {operationMode === 'autonomous' ? 'Autonomous' : 'Manual'}
            </div>
          )}
          {sidebarOpen && (
            <div className="sidebar-plant-label">Lettuce</div>
          )}
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="main-area">

        {/* Top header */}
        <header className="top-header">
          <button className="sidebar-toggle-btn" onClick={() => setSidebarOpen(v => !v)} aria-label="Toggle sidebar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round"/>
            </svg>
          </button>

          <span className="header-page-title">
            {NAV_ITEMS.find(n => n.id === activePage)?.label}
          </span>

          <div className="header-right">
            {loading && (
              <span className="header-spinner" title="Loading…">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="spin-svg">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" strokeLinecap="round"/>
                </svg>
              </span>
            )}
            {lastUpdate && (
              <span className="header-update">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="icon-xs">
                  <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2" strokeLinecap="round"/>
                </svg>
                {lastUpdate}
              </span>
            )}
            <label className="auto-refresh-label">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
              />
              <span>Auto-refresh</span>
            </label>
            <button className="btn-icon-header" onClick={fetchAllData} disabled={loading} title="Refresh now">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M1 4v6h6M23 20v-6h-6" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </header>

        {/* Error banner */}
        {error && (
          <div className="error-banner">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="icon-sm">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            {error}
            <button onClick={() => setError(null)} className="error-close">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        )}

        {/* Page content */}
        <main className="page-content">
          {activePage === 'dashboard' && (
            <Dashboard
              sensors={sensors}
              setpoints={setpoints}
              lastUpdate={lastUpdate}
              captureSessions={captureSessions}
            />
          )}
          {activePage === 'environment' && (
            <PlantEnvironment
              sensors={sensors}
              sensorHistory={sensorHistory}
              lastUpdate={lastUpdate}
            />
          )}
          {activePage === 'actuators' && (
            <ActuatorControl
              actuators={actuators}
              operationMode={operationMode}
              onToggleMode={toggleOperationMode}
              onControlState={controlActuator}
              onControlPower={controlActuatorPower}
              loading={loading}
            />
          )}
          {activePage === 'resources' && (
            <ResourceConsumption
              sensors={sensors}
              sensorHistory={sensorHistory}
            />
          )}
          {activePage === 'livecams' && (
            <LiveCams
              captureSessions={captureSessions}
              captureManualLoading={captureManualLoading}
              onCapture={triggerCaptureNow}
              onRefreshSessions={fetchCaptureSessions}
            />
          )}
          {activePage === 'growth' && (
            <PlantGrowth
              captureSessions={captureSessions}
              captureSessionsLoading={captureSessionsLoading}
              captureManualLoading={captureManualLoading}
              captureManualError={captureManualError}
              healthResult={healthResult}
              healthLoading={healthLoading}
              healthLastChecked={healthLastChecked}
              onCapture={triggerCaptureNow}
              onRefreshSessions={fetchCaptureSessions}
              onCheckHealth={checkPlantHealth}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;

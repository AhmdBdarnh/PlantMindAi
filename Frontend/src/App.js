import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import Dashboard from './pages/Dashboard';
import ActuatorControl from './pages/ActuatorControl';
import ResourceConsumption from './pages/ResourceConsumption';
import PlantGrowth from './pages/PlantGrowth';
import PlantHealth from './pages/PlantHealth';
import LiveCams from './pages/LiveCams';
import AISetpointAdvisor from './pages/AISetpointAdvisor';
import Layer3Decision    from './pages/Layer3Decision';
import TestGrowth        from './pages/TestGrowth';
import NotificationBell from './components/NotificationBell';
import Toast from './components/Toast';
import { API_BASE_URL } from './api/config';
const MAX_HISTORY = 60;

const NAV_ITEMS = [
  { id: 'dashboard',    label: 'Dashboard',            icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { id: 'actuators',    label: 'Actuator Control',     icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' },
  { id: 'resources',    label: 'Resource Consumption', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { id: 'health',       label: 'Plant Health',         icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { id: 'growth',       label: 'Plant Growth',         icon: 'M3 9a2 2 0 014 0v9a2 2 0 01-4 0V9zM9 3a2 2 0 014 0v15a2 2 0 01-4 0V3zM15 6a2 2 0 014 0v12a2 2 0 01-4 0V6z' },
  { id: 'livecams',     label: 'Live Cams',            icon: 'M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z' },
  { id: 'ai-advisor',  label: 'AI Setpoint Advisor',  icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
  { id: 'layer3',      label: 'Budget Manager',       icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { id: 'testgrowth',  label: 'Test Growth',          icon: 'M9 3h6m-6 0v5l-5 9a1 1 0 00.9 1.5h14.2a1 1 0 00.9-1.5l-5-9V3m-6 0h6' },
];

function App() {
  const validPages = NAV_ITEMS.map(n => n.id);
  const [activePage, setActivePage] = useState(() => {
    const hash = window.location.hash.slice(1);
    return validPages.includes(hash) ? hash : 'dashboard';
  });
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

  // Backend health status — populated by /api/health polling every 15 s
  const [healthStatus, setHealthStatus] = useState(null);
  // Tracks when captureWaiting started so we can enforce a 3-minute timeout
  const captureWaitStartRef             = useRef(null);

  // Sensor history for charts (ring buffer)
  const [sensorHistory, setSensorHistory] = useState([]);

  // Plant health (live API result + DB-backed latest)
  const [healthResult, setHealthResult]       = useState(null);
  const [healthLoading, setHealthLoading]     = useState(false);
  const [healthLastChecked, setHealthLastChecked] = useState(null);
  const [healthDbLatest, setHealthDbLatest]   = useState(null);
  const [healthDbHistory, setHealthDbHistory] = useState([]);
  const [healthFetchError, setHealthFetchError] = useState(false);

  // Capture sessions
  const [captureSessions, setCaptureSessions]             = useState([]);
  const [captureSessionsLoading, setCaptureSessionsLoading] = useState(false);
  const [captureManualLoading, setCaptureManualLoading]   = useState(false);
  const [captureManualError, setCaptureManualError]       = useState(null);

  // Plant growth metrics
  const [growthLatest,    setGrowthLatest]    = useState(null);
  const [growthHistory,   setGrowthHistory]   = useState([]);
  const [growthLoading,   setGrowthLoading]   = useState(false);
  const [growthAnalyzing, setGrowthAnalyzing] = useState(false);
  const [growthError,     setGrowthError]     = useState(null);
  // captureWaiting = true when capture is running and we are polling for it to finish
  const [captureWaiting,  setCaptureWaiting]  = useState(false);

  // ==================== DATA FETCHING ====================

  const safeJson = async (res) => {
    const text = await res.text();
    try { return JSON.parse(text); } catch { return null; }
  };

  const fetchSensors = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/sensors`, { cache: 'no-store' });
      const data = await safeJson(res);
      if (!data) { setError('Backend is offline — start the Flask server on port 5000'); return; }
      if (data.success) {
        setError(null);
        setSensors(data.data);
        // Use the actual hardware measurement timestamp from the backend cache,
        // not the browser clock. Falls back to browser time if the field is missing.
        const rawTs = data.last_sensor_update;
        setLastUpdate(
          rawTs
            ? new Date(rawTs.replace(' ', 'T')).toLocaleTimeString()
            : new Date().toLocaleTimeString()
        );
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
      const res  = await fetch(`${API_BASE_URL}/actuators`, { cache: 'no-store' });
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
      const res  = await fetch(`${API_BASE_URL}/setpoints`, { cache: 'no-store' });
      const data = await safeJson(res);
      if (data?.success) setSetpoints(data.setpoints);
    } catch {}
  };

  // Silent background refresh — does NOT touch the loading spinner.
  const fetchAllData = useCallback(async () => {
    await Promise.all([fetchSensors(), fetchActuators(), fetchOperationMode(), fetchSetpoints()]);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Polls /api/health every 15 s to detect sensor loop freeze and data age.
  const fetchBackendHealth = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/health`, { cache: 'no-store' });
      const text = await res.text();
      let data = null;
      try { data = JSON.parse(text); } catch {}
      if (data) {
        setHealthStatus({
          online:             true,
          sensorAlive:        data.sensor_loop_alive === true,
          secondsSinceUpdate: typeof data.seconds_since_last_sensor_update === 'number'
                                ? data.seconds_since_last_sensor_update : null,
          status:             data.status,
        });
      } else {
        setHealthStatus({ online: false });
      }
    } catch {
      setHealthStatus({ online: false });
    }
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

  const fetchHealthFromDb = async () => {
    try {
      const [latestRes, historyRes] = await Promise.all([
        fetch(`${API_BASE_URL}/plant-health/latest`),
        fetch(`${API_BASE_URL}/plant-health/history?limit=20`),
      ]);
      const latestData  = await latestRes.json();
      const historyData = await historyRes.json();
      if (latestData.success && latestData.result) setHealthDbLatest(latestData.result);
      if (historyData.success) setHealthDbHistory(historyData.results || []);
      setHealthFetchError(false);
    } catch {
      setHealthFetchError(true);
    }
  };

  const checkPlantHealth = async () => {
    setHealthLoading(true);
    try {
      const res  = await fetch(`${API_BASE_URL}/plant_health`, { method: 'POST' });
      const data = await res.json();
      setHealthResult(data);
      setHealthLastChecked(new Date().toLocaleTimeString());
      // Refresh DB copy after a short delay (health check runs in background)
      setTimeout(fetchHealthFromDb, 8000);
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

  // ==================== NEW PLANT CYCLE RESET ====================

  const handleNewCycle = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/new-plant-cycle`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        // Immediately refresh sensors so UI shows zeros without waiting for the 2s auto-tick
        await fetchAllData();
      }
      return data;
    } catch (e) {
      return { success: false, error: 'Connection error: ' + e.message };
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ==================== PLANT GROWTH ====================

  const fetchGrowthLatest = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/growth/latest`);
      const data = await safeJson(res);
      if (data?.success) {
        setGrowthLatest(data.data);
        setGrowthError(null);   // clear any stale error when data loads successfully
      }
    } catch {}
  };

  const fetchGrowthHistory = async () => {
    setGrowthLoading(true);
    try {
      const res  = await fetch(`${API_BASE_URL}/growth/history?limit=50`);
      const data = await safeJson(res);
      if (data?.success) setGrowthHistory(data.data);
    } catch {}
    finally { setGrowthLoading(false); }
  };

  const runGrowthFromS3 = async () => {
    setGrowthAnalyzing(true);
    setGrowthError(null);
    try {
      const res  = await fetch(`${API_BASE_URL}/growth/run-latest-s3`, { method: 'POST' });
      const data = await safeJson(res);
      if (data?.success) {
        setGrowthLatest(data.data);
        await fetchGrowthHistory();
      } else {
        setGrowthError(data?.error || 'Growth analysis failed');
      }
    } catch (err) {
      setGrowthError('Connection error: ' + err.message);
    } finally {
      setGrowthAnalyzing(false);
    }
  };

  const fetchCaptureStatus = async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/camera/status`, { cache: 'no-store' });
      const data = await safeJson(res);
      return data;
    } catch { return null; }
  };

  const captureAndAnalyze = async () => {
    setGrowthAnalyzing(true);
    setGrowthError(null);
    setCaptureWaiting(false);
    try {
      const res  = await fetch(`${API_BASE_URL}/growth/capture-and-analyze`, { method: 'POST' });
      const data = await safeJson(res);
      if (data?.success) {
        setGrowthLatest(data.data);
        await fetchGrowthHistory();
      } else if (data?.capture_busy || res.status === 409) {
        // Not a real error — another capture is running; poll until it finishes
        setCaptureWaiting(true);
      } else {
        setGrowthError(data?.error || 'Capture & analyze failed');
      }
    } catch (err) {
      setGrowthError('Connection error: ' + err.message);
    } finally {
      setGrowthAnalyzing(false);
    }
  };

  // ==================== EFFECTS ====================

  // ── Sync URL hash with active page so F5 restores position ──────────────
  useEffect(() => {
    window.location.hash = activePage;
  }, [activePage]);

  // ── Initial load: show loading spinner exactly once on mount ──────────────
  useEffect(() => {
    setLoading(true);
    fetchAllData().finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Background auto-refresh: silently updates data every 2 s, no spinner ──
  useEffect(() => {
    const id = setInterval(fetchAllData, 2000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Backend health polling: every 15 s, detects sensor loop / data age ────
  useEffect(() => {
    fetchBackendHealth();
    const id = setInterval(fetchBackendHealth, 15000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchLatestHealthResult();
    fetchHealthFromDb();
    const id = setInterval(() => {
      fetchLatestHealthResult();
      fetchHealthFromDb();
    }, 60000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchCaptureSessions();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchGrowthLatest();
    fetchGrowthHistory();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll /api/camera/status while a capture is running and auto-refresh growth data when done.
  // Times out after 3 minutes so the UI never gets permanently stuck if the backend hangs.
  useEffect(() => {
    if (!captureWaiting) {
      captureWaitStartRef.current = null;
      return;
    }
    captureWaitStartRef.current = Date.now();
    const TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

    const id = setInterval(async () => {
      // Give up if we have been waiting longer than TIMEOUT_MS
      if (captureWaitStartRef.current !== null &&
          Date.now() - captureWaitStartRef.current > TIMEOUT_MS) {
        setCaptureWaiting(false);
        setGrowthError(
          'Camera capture timed out after 3 minutes. ' +
          'Check backend logs or call POST /api/capture/unlock to release the lock.'
        );
        return;
      }
      const status = await fetchCaptureStatus();
      if (status && !status.in_progress) {
        setCaptureWaiting(false);
        await fetchGrowthLatest();
        await fetchGrowthHistory();
      }
    }, 3000);
    return () => clearInterval(id);
  }, [captureWaiting]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Notifications (bell + toast) ──────────────────────────────────────────
  const [notifications, setNotifications] = useState([]);
  const [unreadCount,   setUnreadCount]   = useState(0);
  const [toasts,        setToasts]        = useState([]);
  const seenNotifIdsRef = useRef(null); // null until first load (don't toast pre-existing)

  const fetchNotifications = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE_URL}/notifications?limit=30`, { cache: 'no-store' });
      const data = await res.json();
      if (!data?.success) return;
      const items = data.notifications || [];
      setNotifications(items);
      setUnreadCount(data.unread_count || 0);

      // Toast only notifications that are new since the previous poll.
      const ids = new Set(items.map(n => n.notification_id));
      if (seenNotifIdsRef.current === null) {
        seenNotifIdsRef.current = ids; // first load — seed silently, no toasts
        return;
      }
      const fresh = items.filter(n => !seenNotifIdsRef.current.has(n.notification_id));
      seenNotifIdsRef.current = ids;
      const toToast = fresh
        .filter(n => n.severity === 'warning' || n.severity === 'critical')
        .slice(0, 3);
      if (toToast.length) {
        setToasts(prev => [
          ...prev,
          ...toToast.map(n => ({ id: n.notification_id, severity: n.severity, title: n.title, message: n.message })),
        ]);
      }
    } catch { /* backend unreachable — ignore; next poll retries */ }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const id = setInterval(fetchNotifications, 10000);
    return () => clearInterval(id);
  }, [fetchNotifications]);

  const handleNotifClick = useCallback(async (n) => {
    // Mark-read on click only (opening the panel does NOT mark as read).
    if (!n.read) {
      setNotifications(prev => prev.map(x => x.notification_id === n.notification_id ? { ...x, read: true } : x));
      setUnreadCount(c => Math.max(0, c - 1));
      try { await fetch(`${API_BASE_URL}/notifications/${n.notification_id}/read`, { method: 'POST' }); } catch { /* retry next poll */ }
    }
    if (n.link) setActivePage(n.link);
  }, []);

  const handleMarkAllRead = useCallback(async () => {
    setNotifications(prev => prev.map(x => ({ ...x, read: true })));
    setUnreadCount(0);
    try { await fetch(`${API_BASE_URL}/notifications/read-all`, { method: 'POST' }); } catch { /* retry next poll */ }
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // ==================== RENDER ====================

  // Compute health banner content once per render (only shown when backend is reachable
  // but sensors have issues — backend-offline is already covered by the error banner).
  const healthBanner = (() => {
    if (!healthStatus || !healthStatus.online) return null;
    if (!healthStatus.sensorAlive)
      return { type: 'frozen', msg: 'Sensor loop is not responding — sensor data may be frozen' };
    if (healthStatus.secondsSinceUpdate !== null && healthStatus.secondsSinceUpdate > 120) {
      const ageStr = healthStatus.secondsSinceUpdate < 300
        ? `${healthStatus.secondsSinceUpdate}s`
        : `${Math.round(healthStatus.secondsSinceUpdate / 60)} min`;
      return { type: 'stale', msg: `Sensor data is ${ageStr} old — may not be current` };
    }
    return null;
  })();

  return (
    <div className="app-layout">

      {/* ── Sidebar ── */}
      <aside className={`sidebar ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <div className="sidebar-brand">
          <svg className="brand-leaf" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14.5v-4.74l-4 2.31-1-1.73 4-2.31-4-2.31 1-1.73 4 2.31V4.5h2v4.8l4-2.31 1 1.73-4 2.31 4 2.31-1 1.73-4-2.31v4.74h-2z" fill="currentColor"/>
          </svg>
          {sidebarOpen && (
            <span className="brand-text">
              <span className="brand-name">PlantMind</span>
              <span className="brand-tagline">Smart Greenhouse System</span>
            </span>
          )}
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

        {/* Top bar — notification bell (right-aligned) */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', padding: '8px 4px 0', marginBottom: 4 }}>
          <NotificationBell
            notifications={notifications}
            unreadCount={unreadCount}
            onItemClick={handleNotifClick}
            onMarkAllRead={handleMarkAllRead}
          />
        </div>

        {/* Error banner — backend unreachable or command failure */}
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

        {/* Health banner — sensor loop frozen or data age warning (auto-clears when resolved) */}
        {healthBanner && (
          <div className={`health-banner health-banner-${healthBanner.type}`}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="icon-sm">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13" strokeLinecap="round"/>
              <line x1="12" y1="17" x2="12.01" y2="17" strokeLinecap="round"/>
            </svg>
            {healthBanner.msg}
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
              healthDbLatest={healthDbLatest}
              healthDbHistory={healthDbHistory}
              growthLatest={growthLatest}
              growthHistory={growthHistory}
              onNavigate={setActivePage}
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
              onNewCycle={handleNewCycle}
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
          {activePage === 'health' && (
            <PlantHealth
              healthResult={healthResult}
              healthDbLatest={healthDbLatest}
              healthDbHistory={healthDbHistory}
              healthFetchError={healthFetchError}
              onRefreshHealth={() => { fetchLatestHealthResult(); return fetchHealthFromDb(); }}
              captureSessions={captureSessions}
              captureSessionsLoading={captureSessionsLoading}
              captureManualLoading={captureManualLoading}
              captureManualError={captureManualError}
              onCapture={triggerCaptureNow}
            />
          )}
          {activePage === 'growth' && (
            <PlantGrowth
              growthLatest={growthLatest}
              growthHistory={growthHistory}
              growthLoading={growthLoading}
              growthAnalyzing={growthAnalyzing}
              growthError={growthError}
              captureWaiting={captureWaiting}
              onRunGrowthS3={runGrowthFromS3}
              onCaptureAndAnalyze={captureAndAnalyze}
              onRefreshGrowth={() => { fetchGrowthLatest(); fetchGrowthHistory(); }}
            />
          )}
          {activePage === 'ai-advisor' && (
            <AISetpointAdvisor setpoints={setpoints} onSetpointsRefresh={fetchSetpoints} />
          )}
          {activePage === 'layer3' && (
            <Layer3Decision />
          )}
          {activePage === 'testgrowth' && (
            <TestGrowth />
          )}
        </main>
      </div>

      {/* ── Toast stack ── */}
      {toasts.length > 0 && (
        <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 2000, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {toasts.map(t => <Toast key={t.id} toast={t} onClose={dismissToast} />)}
        </div>
      )}
    </div>
  );
}

export default App;

import React, { useState, useEffect } from 'react';

const CAMERAS = [
  { id: 1, displayId: 1, name: '2K USB Camera', streamPath: '/video_c1' },
  { id: 2, displayId: 2, name: '4K USB Camera', streamPath: '/video_c2' },
  { id: 4, displayId: 3, name: 'USB Webcam',    streamPath: '/video_c4' },
];

function CamCard({ cam }) {
  const [status, setStatus]         = useState('connecting'); // connecting | live | error
  const [capturing, setCapturing]   = useState(false);
  const [captureMsg, setCaptureMsg] = useState(null); // null | { ok: bool, text: string }

  // If no first frame arrives within 8 s, mark as unavailable
  useEffect(() => {
    if (status !== 'connecting') return;
    const t = setTimeout(() => setStatus('error'), 8000);
    return () => clearTimeout(t);
  }, [status]);

  const captureOne = async () => {
    setCapturing(true);
    setCaptureMsg(null);
    try {
      const res = await fetch(`/api/capture_local/${cam.id}`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setCaptureMsg({ ok: false, text: data.error || 'Capture failed' });
      } else {
        const blob = await res.blob();
        const disposition = res.headers.get('Content-Disposition') || '';
        const nameMatch = disposition.match(/filename="?([^"]+)"?/);
        const rawName = nameMatch ? nameMatch[1] : `cam${cam.id}_capture.jpg`;
        const filename = rawName.replace(`cam${cam.id}_`, `cam${cam.displayId}_`);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        setCaptureMsg({ ok: true, text: 'Saved' });
      }
    } catch (e) {
      setCaptureMsg({ ok: false, text: e.message });
    }
    setCapturing(false);
    setTimeout(() => setCaptureMsg(null), 3000);
  };

  const dotColor = status === 'live' ? '#22c55e' : status === 'error' ? '#ef4444' : '#f59e0b';
  const dotGlow  = status === 'live' ? '0 0 6px #22c55e' : 'none';

  return (
    <div style={{
      background: '#0d1b2a',
      borderRadius: 12,
      border: '1px solid #1a2e44',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header bar */}
      <div style={{
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        borderBottom: '1px solid #1a2e44',
        background: '#0a1628',
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: dotColor,
          boxShadow: dotGlow,
          flexShrink: 0,
          transition: 'background .3s',
        }} />
        <span style={{ color: '#e2e8f0', fontWeight: 700, fontSize: 13 }}>
          Camera {cam.displayId}
        </span>
        <span style={{ color: '#64748b', fontSize: 12 }}>{cam.name}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {status === 'live' && (
            <span style={{
              background: 'rgba(34,197,94,.15)',
              border: '1px solid rgba(34,197,94,.3)',
              color: '#22c55e',
              fontSize: 10, fontWeight: 800,
              padding: '2px 8px', borderRadius: 10,
              letterSpacing: '.5px',
            }}>
              LIVE
            </span>
          )}
          {status === 'connecting' && (
            <span style={{ color: '#f59e0b', fontSize: 11, fontWeight: 600 }}>
              Connecting…
            </span>
          )}
          {status === 'error' && (
            <span style={{ color: '#ef4444', fontSize: 11, fontWeight: 600 }}>
              Unavailable
            </span>
          )}

          {/* Per-camera capture button */}
          {captureMsg && (
            <span style={{
              fontSize: 11, fontWeight: 600,
              color: captureMsg.ok ? '#22c55e' : '#ef4444',
            }}>
              {captureMsg.ok ? '✓' : '✗'} {captureMsg.text}
            </span>
          )}
          <button
            onClick={captureOne}
            disabled={capturing || status === 'error'}
            title="Capture frame"
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: capturing ? '#1e3a5f' : 'rgba(37,99,235,.2)',
              color: status === 'error' ? '#475569' : '#60a5fa',
              border: '1px solid rgba(37,99,235,.35)',
              borderRadius: 6,
              padding: '3px 8px', fontSize: 11, fontWeight: 600,
              cursor: (capturing || status === 'error') ? 'not-allowed' : 'pointer',
              opacity: status === 'error' ? 0.4 : 1,
              transition: 'background .2s',
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{ width: 12, height: 12 }}>
              <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"
                strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="13" r="4" strokeLinecap="round"/>
            </svg>
            {capturing ? '…' : 'Capture'}
          </button>
        </div>
      </div>

      {/* Video frame */}
      <div style={{
        aspectRatio: '16/9',
        background: '#060e1a',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {status !== 'error' ? (
          <img
            src={cam.streamPath}
            alt={`Camera ${cam.displayId}`}
            onLoad={() => setStatus('live')}
            onError={() => setStatus('error')}
            style={{
              width: '100%', height: '100%',
              objectFit: 'contain',
              display: status === 'error' ? 'none' : 'block',
            }}
          />
        ) : null}
        {status !== 'live' && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 12, color: '#334155',
          }}>
            {status === 'connecting' ? (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2"
                  style={{ width: 32, height: 32, animation: 'spin 1s linear infinite' }}>
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
                    strokeLinecap="round"/>
                </svg>
                <span style={{ fontSize: 12, color: '#475569' }}>Connecting to camera…</span>
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="1.5"
                  style={{ width: 40, height: 40 }}>
                  <path d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z"
                    strokeLinecap="round" strokeLinejoin="round"/>
                  <line x1="2" y1="2" x2="22" y2="22" strokeLinecap="round"/>
                </svg>
                <span style={{ fontSize: 13, color: '#64748b' }}>Camera unavailable</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function LiveCams() {
  const [capturing, setCapturing]       = useState(false);
  const [captureResult, setCaptureResult] = useState(null);

  const captureAll = async () => {
    setCapturing(true);
    setCaptureResult(null);
    try {
      const res  = await fetch('/api/capture_local', { method: 'POST' });
      const data = await res.json();
      setCaptureResult(data);
    } catch (e) {
      setCaptureResult({ success: false, error: e.message });
    }
    setCapturing(false);
    setTimeout(() => setCaptureResult(null), 5000);
  };

  return (
    <div>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, flexWrap: 'wrap',
      }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: '#22c55e',
          boxShadow: '0 0 8px #22c55e',
          animation: 'livePulse 1.5s ease-in-out infinite',
        }} />
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>
          Live Camera Feeds
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          3 cameras · MJPEG stream · ~30 FPS
        </span>

        {/* Capture button */}
        <button
          onClick={captureAll}
          disabled={capturing}
          style={{
            marginLeft: 'auto',
            display: 'flex', alignItems: 'center', gap: 6,
            background: capturing ? '#1e3a5f' : '#2563eb',
            color: '#fff', border: 'none', borderRadius: 8,
            padding: '7px 14px', fontSize: 13, fontWeight: 600,
            cursor: capturing ? 'not-allowed' : 'pointer',
            opacity: capturing ? 0.7 : 1,
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            style={{ width: 15, height: 15 }}>
            <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"
              strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="12" cy="13" r="4" strokeLinecap="round"/>
          </svg>
          {capturing ? 'Saving...' : 'Capture All Cameras'}
        </button>
      </div>

      {/* Capture result feedback */}
      {captureResult && (
        <div style={{
          marginBottom: 16, padding: '10px 14px', borderRadius: 8,
          background: captureResult.success ? 'rgba(34,197,94,.1)' : 'rgba(239,68,68,.1)',
          border: `1px solid ${captureResult.success ? 'rgba(34,197,94,.3)' : 'rgba(239,68,68,.3)'}`,
          fontSize: 12, color: captureResult.success ? '#22c55e' : '#ef4444',
        }}>
          {captureResult.success ? (
            <>
              ✓ Saved {captureResult.captures?.filter(c => c.success).length} image(s)
              — {captureResult.timestamp}
              <span style={{ color: '#64748b', marginLeft: 8 }}>
                → Backend/captures/
              </span>
            </>
          ) : (
            `✗ Capture failed: ${captureResult.error}`
          )}
        </div>
      )}

      {/* Grid — 2×2 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {CAMERAS.map(cam => <CamCard key={cam.id} cam={cam} />)}
      </div>

      <style>{`
        @keyframes livePulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 8px #22c55e; }
          50%       { opacity: .4; box-shadow: 0 0 2px #22c55e; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @media (max-width: 700px) {
          .livecams-bottom { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

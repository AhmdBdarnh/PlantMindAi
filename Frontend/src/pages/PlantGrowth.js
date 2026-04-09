
const formatTs = ts => {
  if (!ts) return 'Unknown';
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
};

/* Health status helpers */
function healthStatus(healthResult) {
  if (!healthResult)               return { type: 'unknown',  title: 'No data',           desc: 'No health check has been run yet.' };
  if (!healthResult.success)       return { type: 'error',    title: 'Check failed',       desc: healthResult.error || 'Unknown error' };
  if (healthResult.is_healthy)     return { type: 'healthy',  title: 'Plant is Healthy',   desc: `Confidence: ${healthResult.health_probability}%` };
  return                                  { type: 'unhealthy',title: 'Issues Detected',    desc: `Confidence: ${healthResult.health_probability}%` };
}

const HEALTH_ICONS = {
  healthy:  'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  unhealthy:'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  error:    'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z',
  unknown:  'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
};

/* Get all images from the most recent session, one entry per camera */
function getLatestImagePerCamera(sessions) {
  if (!sessions || sessions.length === 0) return [];
  const latest = sessions[0]; // sessions are sorted newest-first
  const images = latest.images || [];

  // Build camera_id → image map (coerce to Number to handle string ids from MongoDB)
  const byCamera = {};
  images.forEach(img => {
    const id = Number(img.camera_id);
    if (!isNaN(id) && id > 0 && !byCamera[id]) {
      byCamera[id] = img;
    }
  });

  return [1, 2, 3].map(camId => {
    const img = byCamera[camId];
    if (img) return { ...img, camera_id: camId, sessionTs: latest.timestamp };
    return { camera_id: camId, success: false, sessionTs: latest.timestamp };
  });
}

function CaptureImageCard({ img, label }) {
  return (
    <div className="capture-image-card">
      <div className="capture-img-container">
        {img ? (
          <a href={img.url} target="_blank" rel="noopener noreferrer">
            <img
              src={img.url}
              alt={`Camera ${img.camera_id}`}
              onError={e => {
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'flex';
              }}
            />
            <div className="capture-img-placeholder" style={{ display: 'none', position: 'absolute', inset: 0 }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" strokeLinecap="round"/>
              </svg>
              <span>URL expired</span>
            </div>
          </a>
        ) : (
          <div className="capture-img-placeholder">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" strokeLinecap="round"/>
              <circle cx="12" cy="13" r="3"/>
            </svg>
            <span>No image</span>
          </div>
        )}
      </div>
      <div className="capture-img-footer">
        <div className="capture-img-cam">
          {img ? `Camera ${img.camera_id} — ${img.camera_name || label}` : label}
        </div>
        <div className="capture-img-time">{img ? formatTs(img.sessionTs) : 'No capture yet'}</div>
        {img && (
          <span className="capture-img-s3">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{width:10,height:10}}>
              <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Saved to S3
          </span>
        )}
      </div>
    </div>
  );
}

export default function PlantGrowth({
  captureSessions,
  captureSessionsLoading,
  captureManualLoading,
  captureManualError,
  healthResult,
  healthLoading,
  healthLastChecked,
  onCapture,
  onRefreshSessions,
  onCheckHealth,
}) {
  const latestImages = getLatestImagePerCamera(captureSessions);
  const hs           = healthStatus(healthResult);

  return (
    <div className="growth-layout">
      {/* ── Left: Images + controls ── */}
      <div className="growth-images-section">
        {/* Controls */}
        <div className="sessions-controls page-section">
          <button
            className="btn btn-primary"
            onClick={onCapture}
            disabled={captureManualLoading}
          >
            {captureManualLoading ? (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="spin-svg" style={{width:14,height:14}}>
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" strokeLinecap="round"/>
                </svg>
                Capturing…
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z" strokeLinecap="round"/>
                  <circle cx="12" cy="13" r="4"/>
                </svg>
                Capture Now
              </>
            )}
          </button>
          <button
            className="btn btn-outline"
            onClick={onRefreshSessions}
            disabled={captureSessionsLoading}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{width:14,height:14}}>
              <path d="M1 4v6h6M23 20v-6h-6" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Refresh
          </button>
          {captureManualError && (
            <span style={{ fontSize: 12, color: 'var(--red)', fontWeight: 600 }}>
              {captureManualError}
            </span>
          )}
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {captureSessions.length} session{captureSessions.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Latest 2 images */}
        <div className="page-section">
          <div className="section-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{width:18,height:18}}>
              <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" strokeLinecap="round"/>
            </svg>
            Latest Captures
          </div>
          {captureSessionsLoading && captureSessions.length === 0 ? (
            <div className="loading-state">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" strokeLinecap="round"/>
              </svg>
              Loading…
            </div>
          ) : (
            <div className="image-cards-row">
              {latestImages.map(img => (
                <CaptureImageCard
                  key={img.camera_id}
                  img={img.success && img.url ? img : null}
                  label={`Camera ${img.camera_id}`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Future features */}
        <div className="page-section">
          <div className="section-title" style={{ color: 'var(--text-muted)' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{width:18,height:18}}>
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12" strokeLinecap="round"/><line x1="12" y1="16" x2="12.01" y2="16" strokeLinecap="round"/>
            </svg>
            Coming Soon
          </div>
          <div className="grid-3">
            {['Growth Tracking', 'Disease Detection', 'Image Comparison'].map(f => (
              <div className="future-card" key={f}>
                <div className="future-card-title">{f}</div>
                <div style={{ fontSize: 11 }}>Feature in development</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right: Health card ── */}
      <div>
        <div className="health-card">
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>Plant Health</div>

          <div className="health-status-hero">
            <div className={`health-status-icon ${hs.type}`}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={HEALTH_ICONS[hs.type]} />
              </svg>
            </div>
            <div className="health-status-title">{hs.title}</div>
            <div className="health-confidence">{hs.desc}</div>
            {healthResult?.images_sent && (
              <div className="health-confidence" style={{ marginTop: 4 }}>
                {healthResult.images_sent} image{healthResult.images_sent !== 1 ? 's' : ''} analyzed
              </div>
            )}
          </div>

          <div className="health-divider" />

          <div className="health-actions">
            <button
              className="btn btn-primary btn-sm"
              onClick={onCheckHealth}
              disabled={healthLoading}
              style={{ flex: 1 }}
            >
              {healthLoading ? (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="spin-svg" style={{width:13,height:13}}>
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83" strokeLinecap="round"/>
                  </svg>
                  Analyzing…
                </>
              ) : 'Check Health'}
            </button>
          </div>

          {healthLastChecked && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 10, textAlign: 'center' }}>
              Last checked: {healthLastChecked}
            </div>
          )}

          {/* Diseases */}
          {healthResult?.diseases && healthResult.diseases.length > 0 && (
            <>
              <div className="health-divider" />
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: '#92400e' }}>
                Detected Issues
              </div>
              {healthResult.diseases.map((d, i) => (
                <div className="disease-item" key={i}>
                  <div className="disease-item-header">
                    <span className="disease-item-name">{d.name}</span>
                    <span className="disease-item-prob">{d.probability}%</span>
                  </div>
                  {d.description && (
                    <div className="disease-item-desc">{d.description}</div>
                  )}
                  {d.treatment && (
                    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {[
                        ['Prevention',  d.treatment.prevention],
                        ['Biological',  d.treatment.biological],
                        ['Chemical',    d.treatment.chemical],
                      ].map(([lbl, items]) =>
                        items && items.length > 0 ? (
                          <div key={lbl}>
                            <div style={{ fontSize: 11, fontWeight: 700, color: '#b45309', marginBottom: 3 }}>
                              {lbl}
                            </div>
                            <ul style={{ paddingLeft: 14, fontSize: 11, color: '#92400e', lineHeight: 1.5, margin: 0 }}>
                              {items.slice(0, 2).map((item, j) => <li key={j}>{item}</li>)}
                            </ul>
                          </div>
                        ) : null
                      )}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

        </div>
      </div>
    </div>
  );
}

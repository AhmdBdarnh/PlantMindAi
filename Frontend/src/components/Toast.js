import React, { useEffect } from 'react';

const SEV = {
  info:     { border: '#2563eb', icon: '#2563eb' },
  warning:  { border: '#d97706', icon: '#d97706' },
  critical: { border: '#dc2626', icon: '#dc2626' },
};

// A single auto-dismissing toast. Shown only for warning/critical events.
export default function Toast({ toast, onClose, duration = 6000 }) {
  useEffect(() => {
    const id = setTimeout(() => onClose(toast.id), duration);
    return () => clearTimeout(id);
  }, [toast.id, duration, onClose]);

  const sv = SEV[toast.severity] || SEV.info;
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', width: 340, maxWidth: '90vw', background: '#fff', border: '1px solid #e5e7eb', borderLeft: `4px solid ${sv.border}`, borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.14)', padding: '12px 14px' }}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={sv.icon} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
        <path d="M12 9v2m0 4h.01M12 3a9 9 0 100 18 9 9 0 000-18z" />
      </svg>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: '#111827' }}>{toast.title}</div>
        <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.45, marginTop: 1 }}>{toast.message}</div>
      </div>
      <button onClick={() => onClose(toast.id)} aria-label="Dismiss"
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', fontSize: 16, lineHeight: 1 }}>×</button>
    </div>
  );
}

import React, { useState, useRef, useEffect } from 'react';

// Severity → colors (info / warning / critical)
const SEV = {
  info:     { dot: '#2563eb', bg: '#eff6ff' },
  warning:  { dot: '#d97706', bg: '#fffbeb' },
  critical: { dot: '#dc2626', bg: '#fef2f2' },
};

function timeAgo(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (isNaN(then)) return '';
  const sec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

export default function NotificationBell({ notifications = [], unreadCount = 0, onItemClick, onMarkAllRead }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close the panel on outside click
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const hasUnread = notifications.some(n => !n.read);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} aria-label="Notifications" title="Notifications"
        style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38, borderRadius: 10, border: '1px solid #e5e7eb', background: '#fff', cursor: 'pointer' }}>
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span style={{ position: 'absolute', top: -4, right: -4, minWidth: 18, height: 18, padding: '0 5px', borderRadius: 99, background: '#dc2626', color: '#fff', fontSize: 11, fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '2px solid #fff' }}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div style={{ position: 'absolute', right: 0, top: 46, width: 360, maxWidth: '90vw', background: '#fff', border: '1px solid #e5e7eb', borderRadius: 14, boxShadow: '0 12px 32px rgba(0,0,0,0.16)', zIndex: 1000, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #f3f4f6' }}>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#111827' }}>Notifications</span>
            {hasUnread && (
              <button onClick={onMarkAllRead} style={{ background: 'none', border: 'none', color: '#2563eb', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>Mark all read</button>
            )}
          </div>
          <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            {notifications.length === 0 ? (
              <div style={{ padding: '32px 16px', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>No notifications</div>
            ) : (
              notifications.map((n) => {
                const sv = SEV[n.severity] || SEV.info;
                return (
                  <button key={n.notification_id} onClick={() => { onItemClick && onItemClick(n); setOpen(false); }}
                    style={{ display: 'flex', gap: 10, width: '100%', textAlign: 'left', padding: '11px 16px', border: 'none', borderBottom: '1px solid #f7f7f7', background: n.read ? '#fff' : sv.bg, cursor: 'pointer' }}>
                    <span style={{ flexShrink: 0, marginTop: 5, width: 9, height: 9, borderRadius: '50%', background: sv.dot }} />
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <span style={{ display: 'block', fontSize: 13, fontWeight: n.read ? 600 : 800, color: '#111827' }}>{n.title}</span>
                      <span style={{ display: 'block', fontSize: 12, color: '#6b7280', lineHeight: 1.45, marginTop: 1 }}>{n.message}</span>
                      <span style={{ display: 'block', fontSize: 11, color: '#9ca3af', marginTop: 3 }}>{timeAgo(n.created_at)}</span>
                    </span>
                    {!n.read && <span style={{ flexShrink: 0, alignSelf: 'center', width: 8, height: 8, borderRadius: '50%', background: '#2563eb' }} />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

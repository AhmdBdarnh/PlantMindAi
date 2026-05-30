export const fmt = v => (v !== undefined && v !== null ? v : 'N/A');

export const fmtNum = (v, dec = 2) =>
  v !== undefined && v !== null ? Number(v).toFixed(dec) : 'N/A';

export const fmtDate = ts => {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString(); } catch { return String(ts); }
};

export const fmtDateShort = ts => {
  if (!ts) return '';
  try { return new Date(ts).toLocaleDateString(); } catch { return String(ts); }
};

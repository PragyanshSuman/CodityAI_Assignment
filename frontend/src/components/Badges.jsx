export function StatusBadge({ status }) {
  const map = {
    pending:    'badge-pending',
    running:    'badge-running',
    completed:  'badge-completed',
    failed:     'badge-failed',
    scheduled:  'badge-scheduled',
    claimed:    'badge-claimed',
    dead_letter:'badge-dead-letter',
    cancelled:  'badge-cancelled',
    active:     'badge-active',
    idle:       'badge-active',
    offline:    'badge-offline',
    draining:   'badge-paused',
    paused:     'badge-paused',
  };
  const cls = map[status?.toLowerCase()] || 'badge-cancelled';
  return <span className={`badge ${cls}`}>{status}</span>;
}

export function PriorityBadge({ priority }) {
  const color = priority >= 8 ? 'var(--danger-400)' : priority >= 5 ? 'var(--warning-400)' : 'var(--text-muted)';
  return <span style={{ color, fontWeight: 600, fontSize: 13 }}>P{priority}</span>;
}

export function JobTypeBadge({ type }) {
  const colors = {
    immediate: { bg: 'rgba(14,165,233,0.1)', color: 'var(--accent-400)', border: 'rgba(14,165,233,0.25)' },
    delayed:   { bg: 'rgba(251,191,36,0.1)', color: 'var(--warning-400)', border: 'rgba(251,191,36,0.25)' },
    scheduled: { bg: 'rgba(139,92,246,0.1)', color: 'var(--primary-400)', border: 'rgba(139,92,246,0.25)' },
    recurring: { bg: 'rgba(34,197,94,0.1)', color: 'var(--success-400)', border: 'rgba(34,197,94,0.25)' },
    batch:     { bg: 'rgba(249,115,22,0.1)', color: '#fb923c', border: 'rgba(249,115,22,0.25)' },
  };
  const s = colors[type] || colors.immediate;
  return (
    <span style={{
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, textTransform: 'uppercase'
    }}>
      {type}
    </span>
  );
}

import { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, LineChart, Line, Legend } from 'recharts';
import { TrendingUp, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--bg-700)', border: '1px solid var(--border-default)', borderRadius: 8, padding: '10px 14px' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 13, color: p.color || 'var(--text-primary)', marginBottom: 2 }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</strong>
        </div>
      ))}
    </div>
  );
}

export default function Metrics({ wsEvents }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api.getMetricsOverview();
      setData(res);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  useEffect(() => {
    if (!wsEvents) return;
    if (['job.completed', 'job.failed', 'job.created'].includes(wsEvents?.event)) load();
  }, [wsEvents, load]);

  const throughputData = (data?.throughput_history || []).map(d => ({
    time: format(new Date(d.timestamp), 'HH:mm'),
    completed: d.completed,
    failed: d.failed,
  }));

  const queueBarData = (data?.queues || []).slice(0, 10).map(q => ({
    name: q.queue_name.length > 12 ? q.queue_name.slice(0, 12) + '…' : q.queue_name,
    pending: q.pending_count,
    running: q.running_count,
    completed: q.completed_count,
    failed: q.failed_count,
  }));

  if (loading) return <div className="loading-overlay"><div className="spinner" /></div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Metrics & Analytics</h1>
          <p className="page-subtitle">System performance and throughput analysis</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={load}><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* System Stats */}
      <div className="grid-4 mb-8">
        {[
          ['Jobs/Minute', data?.system?.jobs_per_minute?.toFixed(1) ?? '0', '#8b5cf6'],
          ['Success Rate', `${data?.system?.success_rate ?? 100}%`, '#22c55e'],
          ['Avg Exec Time', data?.system?.avg_execution_time_ms ? `${Math.round(data.system.avg_execution_time_ms)}ms` : '—', '#0ea5e9'],
          ['Active Workers', data?.system?.active_workers ?? 0, '#f59e0b'],
        ].map(([label, value, color]) => (
          <div key={label} className="stat-card">
            <span className="stat-label">{label}</span>
            <span className="stat-value" style={{ color }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Throughput Over Time */}
      <div className="card mb-6">
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 20 }}>Throughput — Last 60 Minutes</h3>
        {throughputData.length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={throughputData}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Area type="monotone" dataKey="completed" stroke="#8b5cf6" fill="url(#g1)" name="Completed" strokeWidth={2} />
              <Area type="monotone" dataKey="failed" stroke="#ef4444" fill="url(#g2)" name="Failed" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state"><TrendingUp /><p>No throughput data yet. Jobs will appear here as they complete.</p></div>
        )}
      </div>

      {/* Queue Breakdown */}
      <div className="card mb-6">
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 20 }}>Job Distribution by Queue</h3>
        {queueBarData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={queueBarData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="pending" fill="#f59e0b" name="Pending" radius={[3, 3, 0, 0]} />
              <Bar dataKey="running" fill="#0ea5e9" name="Running" radius={[3, 3, 0, 0]} />
              <Bar dataKey="completed" fill="#22c55e" name="Completed" radius={[3, 3, 0, 0]} />
              <Bar dataKey="failed" fill="#ef4444" name="Failed" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state"><p>No queue data yet.</p></div>
        )}
      </div>

      {/* Full Queue Table */}
      <div className="card">
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>All Queues — Full Breakdown</h3>
        {data?.queues?.length > 0 ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Queue</th>
                  <th>Paused</th>
                  <th>Pending</th>
                  <th>Running</th>
                  <th>Completed</th>
                  <th>Failed</th>
                  <th>DLQ</th>
                  <th>Success Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.queues.map(q => {
                  const total = q.completed_count + q.failed_count;
                  const sr = total > 0 ? ((q.completed_count / total) * 100).toFixed(1) : '100.0';
                  return (
                    <tr key={q.queue_id}>
                      <td style={{ fontWeight: 600 }}>{q.queue_name}</td>
                      <td>{q.is_paused ? '⏸ Yes' : '—'}</td>
                      <td style={{ color: 'var(--warning-400)' }}>{q.pending_count}</td>
                      <td style={{ color: 'var(--accent-400)' }}>{q.running_count}</td>
                      <td style={{ color: 'var(--success-400)' }}>{q.completed_count}</td>
                      <td style={{ color: q.failed_count > 0 ? 'var(--danger-400)' : 'var(--text-muted)' }}>{q.failed_count}</td>
                      <td style={{ color: q.dead_letter_count > 0 ? 'var(--danger-400)' : 'var(--text-muted)' }}>{q.dead_letter_count}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ flex: 1, height: 6, background: 'var(--surface-3)', borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{ width: `${sr}%`, height: '100%', background: parseFloat(sr) > 90 ? 'var(--success-500)' : parseFloat(sr) > 70 ? 'var(--warning-500)' : 'var(--danger-500)', borderRadius: 3 }} />
                          </div>
                          <span style={{ fontSize: 12, fontWeight: 600, color: parseFloat(sr) > 90 ? 'var(--success-400)' : 'var(--danger-400)' }}>{sr}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state"><p>No queues found.</p></div>
        )}
      </div>
    </div>
  );
}

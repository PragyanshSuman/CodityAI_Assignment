import { useEffect, useState, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { api } from '../services/api';
import { StatusBadge } from '../components/Badges';
import { Briefcase, Server, Layers, TrendingUp, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react';
import { format } from 'date-fns';

const COLORS = ['#8b5cf6', '#0ea5e9', '#22c55e', '#ef4444', '#f59e0b'];

function StatCard({ label, value, sub, color, icon: Icon }) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={16} color={color} />
        </div>
      </div>
      <div className="stat-value" style={{ color }}>{value?.toLocaleString() ?? '—'}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--bg-700)', border: '1px solid var(--border-default)', borderRadius: 8, padding: '10px 14px' }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 13, color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
}

export default function Overview({ wsEvents }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const res = await api.getMetricsOverview();
      setData(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  // Refresh on relevant WS events
  useEffect(() => {
    if (!wsEvents) return;
    const relevant = ['job.completed', 'job.failed', 'job.created', 'job.dead_letter'];
    if (relevant.includes(wsEvents.event)) fetch();
  }, [wsEvents, fetch]);

  if (loading) return (
    <div className="loading-overlay">
      <div className="spinner" />
      <span>Loading dashboard...</span>
    </div>
  );

  const sys = data?.system;
  const statusPieData = sys ? [
    { name: 'Pending', value: sys.pending_jobs },
    { name: 'Running', value: sys.running_jobs },
    { name: 'Completed', value: sys.completed_jobs },
    { name: 'Failed', value: sys.failed_jobs },
    { name: 'DLQ', value: sys.dead_letter_jobs },
  ].filter(d => d.value > 0) : [];

  const throughputData = (data?.throughput_history || []).map(d => ({
    time: format(new Date(d.timestamp), 'HH:mm'),
    completed: d.completed,
    failed: d.failed,
  }));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">System Overview</h1>
          <p className="page-subtitle">Real-time health and performance metrics</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={fetch}>Refresh</button>
      </div>

      {/* Stats Row */}
      <div className="grid-4 mb-6">
        <StatCard label="Total Jobs" value={sys?.total_jobs} icon={Briefcase} color="var(--primary-400)" sub={`${sys?.jobs_per_minute?.toFixed(1) ?? 0}/min throughput`} />
        <StatCard label="Active Workers" value={sys?.active_workers} icon={Server} color="var(--accent-400)" sub={`${sys?.total_queues} queues`} />
        <StatCard label="Success Rate" value={`${sys?.success_rate ?? 100}%`} icon={CheckCircle} color="var(--success-400)" sub={`${sys?.completed_jobs} completed`} />
        <StatCard label="Dead Letter" value={sys?.dead_letter_jobs} icon={AlertTriangle} color="var(--danger-400)" sub={`${sys?.failed_jobs} failed total`} />
      </div>

      {/* Running & Pending */}
      <div className="grid-4 mb-8" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <StatCard label="Running Now" value={sys?.running_jobs} icon={Zap} color="var(--warning-400)" />
        <StatCard label="Pending" value={sys?.pending_jobs} icon={Clock} color="var(--text-secondary)" />
        <StatCard label="Queues Paused" value={sys?.paused_queues} icon={Layers} color="var(--warning-400)" />
        <StatCard label="Avg Exec Time" value={sys?.avg_execution_time_ms ? `${Math.round(sys.avg_execution_time_ms)}ms` : '—'} icon={TrendingUp} color="var(--primary-400)" />
      </div>

      {/* Charts Row */}
      <div className="grid-2 mb-8">
        {/* Throughput Chart */}
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 20 }}>Job Throughput (Last Hour)</h3>
          {throughputData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={throughputData}>
                <defs>
                  <linearGradient id="completedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="failedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="completed" stroke="#8b5cf6" fill="url(#completedGrad)" name="Completed" strokeWidth={2} />
                <Area type="monotone" dataKey="failed" stroke="#ef4444" fill="url(#failedGrad)" name="Failed" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state" style={{ padding: '40px 0' }}>
              <TrendingUp />
              <p>No throughput data yet. Jobs will appear here as they complete.</p>
            </div>
          )}
        </div>

        {/* Status Breakdown */}
        <div className="card">
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 20 }}>Job Status Distribution</h3>
          {statusPieData.length > 0 ? (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={160} height={160}>
                <PieChart>
                  <Pie data={statusPieData} cx={75} cy={75} innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                    {statusPieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-col gap-2">
                {statusPieData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div style={{ width: 10, height: 10, borderRadius: 2, background: COLORS[i % COLORS.length] }} />
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{d.name}</span>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>{d.value.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state" style={{ padding: '40px 0' }}>
              <Briefcase />
              <p>No jobs yet. Create a queue and submit jobs to get started.</p>
            </div>
          )}
        </div>
      </div>

      {/* Queue Health Table */}
      <div className="card mb-8">
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>Queue Health</h3>
        {data?.queues?.length > 0 ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Queue</th>
                  <th>Status</th>
                  <th>Pending</th>
                  <th>Running</th>
                  <th>Completed</th>
                  <th>Failed</th>
                  <th>DLQ</th>
                  <th>Throughput/min</th>
                </tr>
              </thead>
              <tbody>
                {data.queues.map(q => (
                  <tr key={q.queue_id}>
                    <td style={{ fontWeight: 600 }}>{q.queue_name}</td>
                    <td><StatusBadge status={q.is_paused ? 'paused' : 'active'} /></td>
                    <td style={{ color: q.pending_count > 0 ? 'var(--warning-400)' : 'var(--text-muted)' }}>{q.pending_count}</td>
                    <td style={{ color: q.running_count > 0 ? 'var(--accent-400)' : 'var(--text-muted)' }}>{q.running_count}</td>
                    <td style={{ color: 'var(--success-400)' }}>{q.completed_count}</td>
                    <td style={{ color: q.failed_count > 0 ? 'var(--danger-400)' : 'var(--text-muted)' }}>{q.failed_count}</td>
                    <td style={{ color: q.dead_letter_count > 0 ? 'var(--danger-400)' : 'var(--text-muted)' }}>{q.dead_letter_count}</td>
                    <td>{q.throughput_per_minute?.toFixed(1) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <Layers />
            <h3>No queues yet</h3>
            <p>Create a project and add queues to start scheduling jobs.</p>
          </div>
        )}
      </div>
    </div>
  );
}

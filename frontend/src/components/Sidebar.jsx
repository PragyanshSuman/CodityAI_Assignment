import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, Layers, Briefcase, Server,
  AlertTriangle, Settings, LogOut, Zap, Activity
} from 'lucide-react';

const navItems = [
  { icon: LayoutDashboard, label: 'Overview', to: '/' },
  { icon: Layers, label: 'Queues', to: '/queues' },
  { icon: Briefcase, label: 'Jobs', to: '/jobs' },
  { icon: Server, label: 'Workers', to: '/workers' },
  { icon: AlertTriangle, label: 'Dead Letter', to: '/dlq' },
  { icon: Activity, label: 'Metrics', to: '/metrics' },
  { icon: Settings, label: 'Settings', to: '/settings' },
];

export default function Sidebar({ wsConnected }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">
          <Zap size={18} color="white" fill="white" />
        </div>
        <div>
          <div className="logo-text">CodityAI</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>Job Scheduler</div>
        </div>
      </div>

      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className={`live-dot`} style={{ color: wsConnected ? 'var(--success-500)' : 'var(--text-muted)' }}>
          {wsConnected ? 'Live' : 'Offline'}
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {navItems.map(({ icon: Icon, label, to }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{user?.full_name || user?.email}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{user?.email}</div>
        </div>
        <button className="btn btn-ghost btn-sm w-full" onClick={handleLogout} style={{ justifyContent: 'flex-start' }}>
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  );
}

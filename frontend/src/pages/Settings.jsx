import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Plus, Key, Trash2, Building2, FolderOpen } from 'lucide-react';

export default function Settings() {
  const [orgs, setOrgs] = useState([]);
  const [selectedOrg, setSelectedOrg] = useState('');
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [apiKeys, setApiKeys] = useState([]);
  const [retryPolicies, setRetryPolicies] = useState([]);
  const [showNewOrg, setShowNewOrg] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [showNewKey, setShowNewKey] = useState(false);
  const [newCreatedKey, setNewCreatedKey] = useState(null);
  const [orgForm, setOrgForm] = useState({ name: '', slug: '' });
  const [projectForm, setProjectForm] = useState({ name: '', slug: '' });
  const [keyName, setKeyName] = useState('');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };

  useEffect(() => { api.listOrgs().then(setOrgs); api.listRetryPolicies().then(setRetryPolicies).catch(() => {}); }, []);
  useEffect(() => {
    if (selectedOrg) api.listProjects(selectedOrg).then(setProjects);
    else setProjects([]); setSelectedProject('');
  }, [selectedOrg]);
  useEffect(() => {
    if (selectedProject) api.listApiKeys(selectedProject).then(setApiKeys).catch(() => {});
    else setApiKeys([]);
  }, [selectedProject]);

  const handleCreateOrg = async (e) => {
    e.preventDefault(); setLoading(true);
    try { const o = await api.createOrg(orgForm); setOrgs(prev => [o, ...prev]); setShowNewOrg(false); setOrgForm({ name: '', slug: '' }); showToast('Organization created'); }
    catch (err) { showToast(err.message, 'error'); } finally { setLoading(false); }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault(); setLoading(true);
    try { const p = await api.createProject(selectedOrg, projectForm); setProjects(prev => [p, ...prev]); setShowNewProject(false); setProjectForm({ name: '', slug: '' }); showToast('Project created'); }
    catch (err) { showToast(err.message, 'error'); } finally { setLoading(false); }
  };

  const handleCreateApiKey = async (e) => {
    e.preventDefault(); setLoading(true);
    try {
      const key = await api.createApiKey(selectedProject, { name: keyName });
      setNewCreatedKey(key);
      setApiKeys(prev => [key, ...prev]);
      setShowNewKey(false);
      setKeyName('');
    } catch (err) { showToast(err.message, 'error'); } finally { setLoading(false); }
  };

  const handleDeleteKey = async (keyId) => {
    if (!confirm('Delete this API key?')) return;
    await api.deleteApiKey(selectedProject, keyId).catch(() => {});
    setApiKeys(prev => prev.filter(k => k.id !== keyId));
    showToast('API key deleted');
  };

  return (
    <div>
      {toast && <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 9999, background: 'var(--bg-600)', border: `1px solid ${toast.type === 'error' ? 'var(--danger-400)' : 'var(--success-400)'}`, borderRadius: 8, padding: '12px 18px', fontSize: 14 }}>{toast.msg}</div>}

      <div className="page-header">
        <div><h1 className="page-title">Settings</h1><p className="page-subtitle">Manage organizations, projects, and API keys</p></div>
      </div>

      {/* Organizations */}
      <div className="card mb-6">
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-2"><Building2 size={18} color="var(--primary-400)" /><h3 style={{ fontSize: 16, fontWeight: 700 }}>Organizations</h3></div>
          <button className="btn btn-primary btn-sm" onClick={() => setShowNewOrg(v => !v)}><Plus size={13} /> New Org</button>
        </div>
        {showNewOrg && (
          <form onSubmit={handleCreateOrg} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div className="grid-2" style={{ gap: 12, marginBottom: 12 }}>
              <div className="form-group">
                <label className="form-label">Name</label>
                <input className="form-input" value={orgForm.name} onChange={e => setOrgForm(f => ({ ...f, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') }))} required />
              </div>
              <div className="form-group">
                <label className="form-label">Slug</label>
                <input className="form-input" value={orgForm.slug} onChange={e => setOrgForm(f => ({ ...f, slug: e.target.value }))} required />
              </div>
            </div>
            <div className="flex gap-2"><button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowNewOrg(false)}>Cancel</button><button type="submit" className="btn btn-primary btn-sm" disabled={loading}>Create</button></div>
          </form>
        )}
        <div className="flex flex-col gap-2">
          {orgs.map(o => (
            <div key={o.id} className={`flex justify-between items-center p-3 rounded-lg cursor-pointer ${selectedOrg === o.id ? 'bg-primary-active' : ''}`}
              style={{ background: selectedOrg === o.id ? 'rgba(139,92,246,0.1)' : 'var(--surface-2)', border: `1px solid ${selectedOrg === o.id ? 'rgba(139,92,246,0.3)' : 'transparent'}`, borderRadius: 8, cursor: 'pointer' }}
              onClick={() => setSelectedOrg(o.id === selectedOrg ? '' : o.id)}>
              <div>
                <div style={{ fontWeight: 600 }}>{o.name}</div>
                <div className="mono text-xs text-muted">{o.slug}</div>
              </div>
            </div>
          ))}
          {orgs.length === 0 && <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: 8 }}>No organizations yet. Create one to get started.</div>}
        </div>
      </div>

      {/* Projects */}
      {selectedOrg && (
        <div className="card mb-6">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2"><FolderOpen size={18} color="var(--accent-400)" /><h3 style={{ fontSize: 16, fontWeight: 700 }}>Projects</h3></div>
            <button className="btn btn-primary btn-sm" onClick={() => setShowNewProject(v => !v)}><Plus size={13} /> New Project</button>
          </div>
          {showNewProject && (
            <form onSubmit={handleCreateProject} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div className="grid-2" style={{ gap: 12, marginBottom: 12 }}>
                <div className="form-group"><label className="form-label">Name</label><input className="form-input" value={projectForm.name} onChange={e => setProjectForm(f => ({ ...f, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') }))} required /></div>
                <div className="form-group"><label className="form-label">Slug</label><input className="form-input" value={projectForm.slug} onChange={e => setProjectForm(f => ({ ...f, slug: e.target.value }))} required /></div>
              </div>
              <div className="flex gap-2"><button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowNewProject(false)}>Cancel</button><button type="submit" className="btn btn-primary btn-sm" disabled={loading}>Create</button></div>
            </form>
          )}
          <div className="flex flex-col gap-2">
            {projects.map(p => (
              <div key={p.id} style={{ background: selectedProject === p.id ? 'rgba(14,165,233,0.1)' : 'var(--surface-2)', border: `1px solid ${selectedProject === p.id ? 'rgba(14,165,233,0.3)' : 'transparent'}`, borderRadius: 8, padding: '10px 14px', cursor: 'pointer' }}
                onClick={() => setSelectedProject(p.id === selectedProject ? '' : p.id)}>
                <div style={{ fontWeight: 600 }}>{p.name}</div>
                <div className="mono text-xs text-muted">{p.slug}</div>
              </div>
            ))}
            {projects.length === 0 && <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: 8 }}>No projects yet.</div>}
          </div>
        </div>
      )}

      {/* API Keys */}
      {selectedProject && (
        <div className="card mb-6">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2"><Key size={18} color="var(--warning-400)" /><h3 style={{ fontSize: 16, fontWeight: 700 }}>API Keys</h3></div>
            <button className="btn btn-primary btn-sm" onClick={() => setShowNewKey(v => !v)}><Plus size={13} /> New Key</button>
          </div>
          {newCreatedKey && (
            <div style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--success-400)', marginBottom: 6 }}>⚠ Copy this key — it will never be shown again</div>
              <div className="code-block">{newCreatedKey.raw_key}</div>
              <button className="btn btn-ghost btn-sm mt-2" onClick={() => { navigator.clipboard.writeText(newCreatedKey.raw_key); showToast('Key copied!'); setNewCreatedKey(null); }}>Copy & Dismiss</button>
            </div>
          )}
          {showNewKey && (
            <form onSubmit={handleCreateApiKey} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div className="form-group mb-3"><label className="form-label">Key Name</label><input className="form-input" value={keyName} onChange={e => setKeyName(e.target.value)} placeholder="e.g. Production API" required /></div>
              <div className="flex gap-2"><button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowNewKey(false)}>Cancel</button><button type="submit" className="btn btn-primary btn-sm" disabled={loading}>Generate Key</button></div>
            </form>
          )}
          <div className="flex flex-col gap-2">
            {apiKeys.map(k => (
              <div key={k.id} className="flex justify-between items-center" style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 14px' }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{k.name}</div>
                  <div className="mono text-xs text-muted">{k.key_prefix}••••••••••••••••</div>
                </div>
                <button className="btn btn-danger btn-sm" onClick={() => handleDeleteKey(k.id)}><Trash2 size={13} /></button>
              </div>
            ))}
            {apiKeys.length === 0 && <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: 8 }}>No API keys yet.</div>}
          </div>
        </div>
      )}

      {/* Retry Policies */}
      <div className="card">
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Retry Policies</h3>
        <div className="table-wrapper">
          <table>
            <thead><tr><th>Name</th><th>Strategy</th><th>Max Attempts</th><th>Initial Delay</th><th>Multiplier</th><th>Jitter</th></tr></thead>
            <tbody>
              {retryPolicies.map(p => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600 }}>{p.name || '—'}</td>
                  <td><span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{p.strategy}</span></td>
                  <td>{p.max_attempts}</td>
                  <td>{p.initial_delay_seconds}s</td>
                  <td>{p.multiplier}×</td>
                  <td>{p.jitter ? '✓' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

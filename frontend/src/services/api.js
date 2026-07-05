const BASE_URL = '/api/v1';

function getToken() {
  return localStorage.getItem('access_token');
}

async function request(method, path, body = null, auth = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  if (res.status === 401) {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Auth
  register: (data) => request('POST', '/auth/register', data, false),
  login: (data) => request('POST', '/auth/login', data, false),
  refresh: (data) => request('POST', '/auth/refresh', data, false),
  me: () => request('GET', '/auth/me'),

  // Orgs
  createOrg: (data) => request('POST', '/orgs', data),
  listOrgs: () => request('GET', '/orgs'),
  getOrg: (id) => request('GET', `/orgs/${id}`),
  updateOrg: (id, data) => request('PATCH', `/orgs/${id}`, data),
  deleteOrg: (id) => request('DELETE', `/orgs/${id}`),
  listMembers: (orgId) => request('GET', `/orgs/${orgId}/members`),
  inviteMember: (orgId, data) => request('POST', `/orgs/${orgId}/members`, data),

  // Projects
  createProject: (orgId, data) => request('POST', `/orgs/${orgId}/projects`, data),
  listProjects: (orgId) => request('GET', `/orgs/${orgId}/projects`),
  getProject: (id) => request('GET', `/projects/${id}`),
  updateProject: (id, data) => request('PATCH', `/projects/${id}`, data),
  deleteProject: (id) => request('DELETE', `/projects/${id}`),
  createApiKey: (projectId, data) => request('POST', `/projects/${projectId}/api-keys`, data),
  listApiKeys: (projectId) => request('GET', `/projects/${projectId}/api-keys`),
  deleteApiKey: (projectId, keyId) => request('DELETE', `/projects/${projectId}/api-keys/${keyId}`),

  // Retry Policies
  listRetryPolicies: () => request('GET', '/retry-policies'),
  createRetryPolicy: (data) => request('POST', '/retry-policies', data),

  // Queues
  createQueue: (projectId, data) => request('POST', `/projects/${projectId}/queues`, data),
  listQueues: (projectId) => request('GET', `/projects/${projectId}/queues`),
  getQueue: (id) => request('GET', `/queues/${id}`),
  updateQueue: (id, data) => request('PATCH', `/queues/${id}`, data),
  deleteQueue: (id) => request('DELETE', `/queues/${id}`),
  pauseQueue: (id) => request('POST', `/queues/${id}/pause`),
  resumeQueue: (id) => request('POST', `/queues/${id}/resume`),
  getQueueStats: (id) => request('GET', `/queues/${id}/stats`),

  // Jobs
  createJob: (queueId, data) => request('POST', `/queues/${queueId}/jobs`, data),
  createBatchJobs: (queueId, data) => request('POST', `/queues/${queueId}/jobs/batch`, data),
  listJobs: (queueId, params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request('GET', `/queues/${queueId}/jobs${q ? `?${q}` : ''}`);
  },
  getJob: (id) => request('GET', `/jobs/${id}`),
  retryJob: (id) => request('POST', `/jobs/${id}/retry`),
  cancelJob: (id) => request('DELETE', `/jobs/${id}`),
  getJobLogs: (id, params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request('GET', `/jobs/${id}/logs${q ? `?${q}` : ''}`);
  },
  getDLQ: (queueId, params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request('GET', `/queues/${queueId}/dlq${q ? `?${q}` : ''}`);
  },
  retryDLQ: (dlqId) => request('POST', `/dlq/${dlqId}/retry`),
  discardDLQ: (dlqId) => request('DELETE', `/dlq/${dlqId}`),

  // Workers
  listWorkers: () => request('GET', '/workers'),
  getWorker: (id) => request('GET', `/workers/${id}`),
  shutdownWorker: (id) => request('POST', `/workers/${id}/shutdown`),
  getWorkerHeartbeats: (id) => request('GET', `/workers/${id}/heartbeats`),

  // Metrics
  getMetricsOverview: () => request('GET', '/metrics/overview'),
  getQueueMetrics: (id) => request('GET', `/metrics/queues/${id}`),
};

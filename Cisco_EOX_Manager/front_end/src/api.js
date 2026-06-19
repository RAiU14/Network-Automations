const rawConfiguredApiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const inferredApiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;

const configuredLooksLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(rawConfiguredApiBaseUrl);
const browserIsLocal = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);

export const API_BASE_URL = rawConfiguredApiBaseUrl && !(configuredLooksLocal && !browserIsLocal)
  ? rawConfiguredApiBaseUrl
  : inferredApiBaseUrl;

export const ADMIN_TOKEN_STORAGE_KEY = 'cisco_eox_admin_token';
export const READ_TOKEN_STORAGE_KEY = 'cisco_eox_read_token';

export function getStoredAdminToken() {
  try { return localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || ''; } catch (_error) { return ''; }
}

export function setStoredAdminToken(token) {
  try {
    if (token) localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  } catch (_error) {
    return null;
  }
  return token || '';
}

export function getStoredReadToken() {
  try { return localStorage.getItem(READ_TOKEN_STORAGE_KEY) || ''; } catch (_error) { return ''; }
}

export function setStoredReadToken(token) {
  try {
    if (token) localStorage.setItem(READ_TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(READ_TOKEN_STORAGE_KEY);
  } catch (_error) {
    return null;
  }
  return token || '';
}

function authHeaders() {
  const adminToken = getStoredAdminToken();
  const readToken = getStoredReadToken();
  const token = adminToken || readToken;
  const headers = token ? { 'Authorization': `Bearer ${token}`, 'X-EOX-API-Token': token } : {};
  if (adminToken) headers['X-EOX-Admin-Token'] = adminToken;
  if (!adminToken && readToken) headers['X-EOX-Read-Token'] = readToken;
  return headers;
}

export function formatApiError(payload, fallback = 'Request failed') {
  if (!payload) return fallback;
  if (typeof payload === 'string') return payload || fallback;

  const detail = payload.detail ?? payload.message ?? payload.error;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === 'string') return item;
      const loc = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== 'body').join('.') : '';
      const msg = item?.msg || item?.message || JSON.stringify(item);
      return loc ? `${loc}: ${msg}` : msg;
    }).join('; ');
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  if (detail) return String(detail);

  try {
    return JSON.stringify(payload);
  } catch (_error) {
    return fallback;
  }
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers || {})
    }
  });

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();

  if (!response.ok) {
    throw new Error(formatApiError(payload, `Request failed with HTTP ${response.status}`));
  }

  return payload;
}

export async function graphqlRequest(query, variables = {}) {
  const payload = await apiRequest('/graphql', {
    method: 'POST',
    body: JSON.stringify({ query, variables })
  });
  if (payload?.errors?.length) {
    throw new Error(payload.errors.map((item) => item.message).join('; '));
  }
  return payload;
}

export async function getExportOptions(dataset, search = '') {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  return apiRequest(`/api/export/options/${dataset}${params.toString() ? `?${params.toString()}` : ''}`);
}

export async function downloadExport(dataset, format, search = '', limit = 10000, fields = [], includeAll = false) {
  const params = new URLSearchParams({ format, limit: String(limit), include_all: includeAll ? 'true' : 'false' });
  if (search) params.set('search', search);
  if (!includeAll) {
    fields.forEach((field) => params.append('fields', field));
  }
  const response = await fetch(`${API_BASE_URL}/api/export/${dataset}?${params.toString()}`, { headers: authHeaders() });
  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    throw new Error(formatApiError(payload, 'Export failed'));
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match ? match[1] : `cisco_eox_${dataset}.${format}`;
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function parsePids(value) {
  return value
    .split(/[\n,;\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export async function logFrontendEvent(level, eventType, message, payload = {}) {
  try {
    await apiRequest('/api/logs/frontend', {
      method: 'POST',
      body: JSON.stringify({ level, event_type: eventType, message, source: 'front_end', payload })
    });
  } catch (_error) {
    return null;
  }
}

export async function getProductEvidence(pid, tableLimit = 20, rowLimit = 500) {
  const params = new URLSearchParams({ table_limit: String(tableLimit), row_limit: String(rowLimit) });
  return apiRequest(`/api/eox/evidence/${encodeURIComponent(pid)}?${params.toString()}`);
}

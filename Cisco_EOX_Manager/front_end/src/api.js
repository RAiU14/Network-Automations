const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    }
  });

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();

  if (!response.ok) {
    const message = typeof payload === 'string' ? payload : payload.detail || payload.message || 'Request failed';
    throw new Error(message);
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
  const response = await fetch(`${API_BASE_URL}/api/export/${dataset}?${params.toString()}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || 'Export failed');
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

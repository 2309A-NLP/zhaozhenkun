import { store } from './state.js';

const API_PREFIX = '/api/v1';

function getToken() {
  return store.read().token || '';
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(path, {
    method: options.method || 'GET',
    headers,
    body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) return response.json();
  return response.text();
}

export const api = {
  rootInfo: () => request(`${API_PREFIX}/system/info`),
  health: () => request('/health'),
  login: (payload) => request(`${API_PREFIX}/auth/login`, { method: 'POST', json: payload }),
  me: () => request(`${API_PREFIX}/auth/me`),
  generate: (payload) => request(`${API_PREFIX}/lesson-prep/generate`, { method: 'POST', json: payload }),
  improve: (payload) => request(`${API_PREFIX}/lesson-prep/improve`, { method: 'POST', json: payload }),
  contents: () => request(`${API_PREFIX}/lesson-prep/contents`),
  contentDetail: (contentId) => request(`${API_PREFIX}/lesson-prep/content/${contentId}`),
  updateContent: (contentId, payload) => request(`${API_PREFIX}/lesson-prep/content/${contentId}`, { method: 'PUT', json: payload }),
  cloneContent: (contentId, title) => request(`${API_PREFIX}/lesson-prep/content/${contentId}/clone`, { method: 'POST', json: { title } }),
  deleteContent: (contentId) => request(`${API_PREFIX}/lesson-prep/content/${contentId}`, { method: 'DELETE' }),
  searchResources: (payload) => request(`${API_PREFIX}/knowledge/search`, { method: 'POST', json: payload }),
  uploadResource: (payload) => request(`${API_PREFIX}/knowledge/upload`, { method: 'POST', json: payload }),
  listResources: () => request(`${API_PREFIX}/knowledge/resources`),
  citeResource: (resourceId) => request(`${API_PREFIX}/knowledge/resource/${resourceId}/cite`, { method: 'POST' }),
  deleteResource: (resourceId) => request(`${API_PREFIX}/knowledge/resource/${resourceId}`, { method: 'DELETE' }),
  knowledgeStats: () => request(`${API_PREFIX}/knowledge/stats`),
  exportContent: (payload) => request(`${API_PREFIX}/export/convert`, { method: 'POST', json: payload }),
  versionList: (contentId) => request(`${API_PREFIX}/version/content/${contentId}/versions`),
  versionDetail: (versionId) => request(`${API_PREFIX}/version/${versionId}`),
  compareVersions: (versionIdA, versionIdB) => request(`${API_PREFIX}/version/compare`, { method: 'POST', json: { version_id_a: versionIdA, version_id_b: versionIdB } }),
  restoreVersion: (contentId, versionId) => request(`${API_PREFIX}/version/content/${contentId}/restore/${versionId}`, { method: 'POST' }),
  createSession: (contentId) => request(`${API_PREFIX}/collaboration/session/create`, { method: 'POST', json: { content_id: contentId } }),
  participants: (sessionId) => request(`${API_PREFIX}/collaboration/session/${sessionId}/participants`),
  streamGenerate(payload, handlers) {
    const token = getToken();
    const streamUrl = `${API_PREFIX}/lesson-prep/generate-stream`;
    return fetch(streamUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }).then(async (response) => {
      if (!response.ok || !response.body) throw new Error('流式生成失败');
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        for (const chunk of events) {
          if (!chunk.startsWith('data: ')) continue;
          const payload = JSON.parse(chunk.slice(6));
          handlers?.onMessage?.(payload);
        }
      }
      handlers?.onEnd?.();
    });
  },
};

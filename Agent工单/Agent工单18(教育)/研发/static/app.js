// 工单18：app.js - 智能助教前端交互与双模型切换模块。
const state = { token: '', provider: 'deepseek', resourceScope: 'all' };

function el(id) { return document.getElementById(id); }
function provider() { return document.querySelector('input[name="provider"]:checked')?.value || 'deepseek'; }
function authHeaders() { return state.token ? { Authorization: `Bearer ${state.token}` } : {}; }
async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok || data.success === false) throw new Error(data.detail || data.message || '请求失败');
  return data;
}
function renderDashboard(data) {
  el('dashboard').innerHTML = [
    `<div class="metrics-line">用户：${data.display_name}（${data.role}）</div>`,
    `<div class="metrics-line">私有知识：${data.private_resource_count}</div>`,
    `<div class="metrics-line">公共知识：${data.public_resource_count}</div>`,
    `<div class="metrics-line">问答次数：${data.qa_count}</div>`,
  ].join('');
}
function renderReferences(items, citations = []) {
  const refs = items.map((item) => `
    <div class="ref-item">
      <div><span class="badge">${item.scope}</span><span class="badge">${item.media_kinds.join('/')}</span>${item.title}</div>
      <div class="meta-line">定位：<span class="location-text">${item.location_text || '全文'}</span></div>
      <div>${item.snippet}</div>
    </div>
  `).join('');
  const citeHtml = citations.map((item) => `
    <div class="ref-item">
      <div><span class="badge">引用</span>${item.title}</div>
      <div class="meta-line">${item.scope} · ${item.media_kinds.join('/')} · <span class="location-text">${item.location_text || '全文'}</span></div>
      <div>${item.snippet}</div>
    </div>
  `).join('');
  el('references').innerHTML = refs || citeHtml ? refs + citeHtml : '<div class="empty-note">暂无结果</div>';
}
function renderResources(items) {
  el('resource-list').innerHTML = items.map((item) => `
    <div class="resource-item">
      <div><span class="badge">${item.scope}</span><span class="badge">${item.resource_type}</span>${item.title}</div>
      <div class="meta-line">模态：${item.media_kinds.join('/')} · 标签：${(item.tags || []).join('、') || '无'}</div>
      <div>${(item.content_text || '').slice(0, 220)}</div>
      <div class="resource-actions">
        <button data-action="detail" data-id="${item.resource_id}">查看详情</button>
        <button class="danger" data-action="delete" data-id="${item.resource_id}">删除</button>
      </div>
    </div>
  `).join('') || '<div class="empty-note">暂无资源</div>';
}
function renderResourceDetail(item) {
  const chunkHtml = (item.chunks || []).map((chunk) => `
    <div class="detail-block">
      <div><span class="badge">${chunk.modality || 'text'}</span>${chunk.summary || ''}</div>
      <div class="meta-line">定位：<span class="location-text">${chunk.location_text || '全文'}</span></div>
      <div>${chunk.content || ''}</div>
    </div>
  `).join('');
  el('resource-detail').innerHTML = `
    <div class="detail-block">
      <div><span class="badge">${item.scope}</span><span class="badge">${item.resource_type}</span>${item.title}</div>
      <div class="meta-line">文件：${item.file_name || ''}</div>
      <div class="meta-line">模态：${(item.media_kinds || []).join('/')} · 标签：${(item.tags || []).join('、') || '无'}</div>
      <div class="meta-line">创建时间：${item.created_at || ''}</div>
    </div>
  ` + (chunkHtml || '<div class="empty-note">暂无结构化片段</div>');
}
async function login() {
  const data = await request('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: el('username').value, password: el('password').value }),
  });
  state.token = data.data.access_token;
  el('login-status').textContent = `已登录：${data.data.user.display_name}`;
  await refreshDashboard();
  await refreshResources();
}
async function refreshDashboard() {
  const data = await request('/api/dashboard', { headers: authHeaders() });
  renderDashboard(data.data);
}
async function refreshResources() {
  const scope = el('resource-scope-filter')?.value || state.resourceScope;
  state.resourceScope = scope;
  const data = await request(`/api/knowledge/list?scope=${encodeURIComponent(scope)}`, { headers: authHeaders() });
  renderResources(data.data.items);
}
async function saveTextKnowledge() {
  const payload = {
    title: el('text-title').value,
    scope: el('text-scope').value,
    resource_type: el('text-type').value,
    tags: el('text-tags').value,
    source_url: '',
    content_text: el('text-content').value,
  };
  await request('/api/knowledge/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
  await refreshResources();
}
async function uploadFileKnowledge() {
  const file = el('file-input').files[0];
  if (!file) throw new Error('请先选择文件');
  const formData = new FormData();
  formData.append('file', file);
  const currentProvider = provider();
  const response = await fetch(`/api/knowledge/file?scope=${encodeURIComponent(el('file-scope').value)}&model_provider=${encodeURIComponent(currentProvider)}`, {
    method: 'POST', headers: authHeaders(), body: formData,
  });
  const data = await response.json();
  if (!response.ok || data.success === false) throw new Error(data.detail || data.message || '上传失败');
  await refreshResources();
  renderResourceDetail(data.data);
}
async function askQuestion() {
  state.provider = provider();
  const payload = {
    question: el('question').value,
    model_provider: state.provider,
    top_k: 6,
    use_public: el('use-public').checked,
    use_private: el('use-private').checked,
  };
  const data = await request('/api/assistant/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
  el('answer-box').textContent = `模型：${data.data.model_provider} / ${data.data.model_name}\n\n${data.data.answer}`;
  renderReferences(data.data.references, data.data.citations);
  await refreshDashboard();
}
async function onlySearch() {
  state.provider = provider();
  const payload = {
    question: el('question').value,
    model_provider: state.provider,
    top_k: 8,
    use_public: el('use-public').checked,
    use_private: el('use-private').checked,
  };
  const data = await request('/api/knowledge/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
  el('answer-box').textContent = '已完成检索，请查看右侧结果与引用。';
  renderReferences(data.data.references, data.data.citations);
}
async function showResourceDetail(resourceId) {
  const data = await request(`/api/knowledge/${encodeURIComponent(resourceId)}`, { headers: authHeaders() });
  renderResourceDetail(data.data);
}
async function removeResource(resourceId) {
  await request(`/api/knowledge/${encodeURIComponent(resourceId)}`, { method: 'DELETE', headers: authHeaders() });
  el('resource-detail').textContent = '资源已删除。';
  await refreshResources();
}
function bindEvents() {
  document.querySelectorAll('input[name="provider"]').forEach((node) => node.addEventListener('change', () => { state.provider = provider(); }));
  el('login-btn').addEventListener('click', () => login().catch((error) => { el('login-status').textContent = error.message; }));
  el('save-text-btn').addEventListener('click', () => saveTextKnowledge().catch((error) => { el('answer-box').textContent = error.message; }));
  el('upload-file-btn').addEventListener('click', () => uploadFileKnowledge().catch((error) => { el('answer-box').textContent = error.message; }));
  el('ask-btn').addEventListener('click', () => askQuestion().catch((error) => { el('answer-box').textContent = error.message; }));
  el('search-btn').addEventListener('click', () => onlySearch().catch((error) => { el('answer-box').textContent = error.message; }));
  el('refresh-btn').addEventListener('click', () => refreshResources().catch((error) => { el('answer-box').textContent = error.message; }));
  el('resource-scope-filter').addEventListener('change', () => refreshResources().catch((error) => { el('answer-box').textContent = error.message; }));
  el('clear-detail-btn').addEventListener('click', () => { el('resource-detail').textContent = '点击“查看详情”后在这里展示结构化片段、定位和原文摘要。'; });
  el('resource-list').addEventListener('click', (event) => {
    const target = event.target.closest('button[data-action]');
    if (!target) return;
    const resourceId = target.dataset.id;
    if (target.dataset.action === 'detail') showResourceDetail(resourceId).catch((error) => { el('answer-box').textContent = error.message; });
    if (target.dataset.action === 'delete') removeResource(resourceId).catch((error) => { el('answer-box').textContent = error.message; });
  });
}
bindEvents();

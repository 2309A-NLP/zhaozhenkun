const STORAGE_KEY = 'edu-agent-workspace-state';
const API_PREFIX = '/api/v1';

const TOOL_SNIPPETS = {
  text: '\n【文本模块】\n- 教学说明：\n- 关键知识：\n',
  image: '\n【图片模块】\n- 图片主题：\n- 配图说明：\n',
  shape: '\n【图形模块】\n- 图形名称：\n- 用途说明：\n',
  table: '\n【表格模块】\n| 项目 | 内容 |\n| --- | --- |\n| 示例 | 待补充 |\n',
  chart: '\n【图表模块】\n- 图表类型：柱状图/折线图\n- 数据说明：\n',
  video: '\n【视频模块】\n- 视频主题：\n- 使用场景：\n',
};

const MODE_CONTENT = {
  focus: '【教学重难点】\n1. 重点知识拆解\n2. 易错点提醒\n3. 课堂提问设计\n',
  process: '【教学流程】\n1. 情境导入\n2. 新授讲解\n3. 课堂练习\n4. 总结提升\n',
  activity: '【活动设计】\n1. 小组讨论任务\n2. 案例探究活动\n3. 互动评价方式\n',
};

const FILTER_LABELS = {
  lesson_plan: '教案',
  courseware: '课件',
  exercise: '练习',
};

const store = {
  read() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  },
  write(partial) {
    const next = { ...this.read(), ...partial };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  },
  clear() {
    localStorage.removeItem(STORAGE_KEY);
  },
};

function getToken() {
  return store.read().token || '';
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.json !== undefined) headers.set('Content-Type', 'application/json');
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
  return contentType.includes('application/json') ? response.json() : response.text();
}

const api = {
  health: () => request('/health'),
  login: (payload) => request(`${API_PREFIX}/auth/login`, { method: 'POST', json: payload }),
  demoLogin: () => request(`${API_PREFIX}/auth/demo-login`, { method: 'POST' }),
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
  knowledgeStats: () => request(`${API_PREFIX}/knowledge/stats`),
  exportContent: (payload) => request(`${API_PREFIX}/export/convert`, { method: 'POST', json: payload }),
  versionList: (contentId) => request(`${API_PREFIX}/version/content/${contentId}/versions`),
  versionDetail: (versionId) => request(`${API_PREFIX}/version/${versionId}`),
  restoreVersion: (contentId, versionId) => request(`${API_PREFIX}/version/content/${contentId}/restore/${versionId}`, { method: 'POST' }),
  createSession: (contentId) => request(`${API_PREFIX}/collaboration/session/create`, { method: 'POST', json: { content_id: contentId } }),
  streamGenerate(payload, handlers) {
    return fetch(`${API_PREFIX}/lesson-prep/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
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

const state = {
  token: store.read().token || '',
  currentUser: store.read().currentUser || null,
  contents: [],
  activeContent: null,
  activeTab: '',
  activeMode: 'focus',
  activeFilter: 'lesson_plan',
  sessionId: '',
  ws: null,
  lastResources: [],
};

const el = {
  navItems: Array.from(document.querySelectorAll('.nav-item')),
  views: Array.from(document.querySelectorAll('.view')),
  modeChips: Array.from(document.querySelectorAll('.mode-chip')),
  filterChips: Array.from(document.querySelectorAll('.filter-chip')),
  toolTiles: Array.from(document.querySelectorAll('.tool-tile')),
  sceneSelect: document.getElementById('scene-select'),
  unitSelect: document.getElementById('unit-select'),
  openLogin: document.getElementById('open-login'),
  closeLogin: document.getElementById('close-login'),
  loginModal: document.getElementById('login-modal'),
  loginForm: document.getElementById('login-form'),
  loginFeedback: document.getElementById('login-feedback'),
  demoLogin: document.getElementById('demo-login'),
  useDemo: document.getElementById('use-demo'),
  generateForm: document.getElementById('generate-form'),
  generateNormal: document.getElementById('generate-normal'),
  contentTabs: document.getElementById('content-tabs'),
  contentEditor: document.getElementById('content-editor'),
  contentStatus: document.getElementById('content-status'),
  streamStatus: document.getElementById('stream-status'),
  saveContent: document.getElementById('save-content'),
  improveContent: document.getElementById('improve-content'),
  citationList: document.getElementById('citation-list'),
  versionList: document.getElementById('version-list'),
  exportList: document.getElementById('export-list'),
  collabStatus: document.getElementById('collab-status'),
  refreshCitations: document.getElementById('refresh-citations'),
  refreshVersions: document.getElementById('refresh-versions'),
  exportMarkdown: document.getElementById('export-markdown'),
  startSession: document.getElementById('start-session'),
  resourceQuery: document.getElementById('resource-query'),
  searchResource: document.getElementById('search-resource'),
  resourceResults: document.getElementById('resource-results'),
  uploadTitle: document.getElementById('upload-title'),
  uploadType: document.getElementById('upload-type'),
  uploadTags: document.getElementById('upload-tags'),
  uploadContent: document.getElementById('upload-content'),
  uploadUrl: document.getElementById('upload-url'),
  uploadResource: document.getElementById('upload-resource'),
  refreshContents: document.getElementById('refresh-contents'),
  contentList: document.getElementById('content-list'),
  metricHealth: document.getElementById('metric-health'),
  metricDocuments: document.getElementById('metric-documents'),
  metricUser: document.getElementById('metric-user'),
  metricContents: document.getElementById('metric-contents'),
  headerUserName: document.getElementById('header-user-name'),
  previewTitle: document.getElementById('preview-title'),
  previewSubtitle: document.getElementById('preview-subtitle'),
  previewTag: document.getElementById('preview-tag'),
};

function openLoginModal() {
  el.loginModal?.classList.remove('hidden');
}

function closeLoginModal() {
  el.loginModal?.classList.add('hidden');
}

function setFeedback(target, message, tone) {
  if (!target) return;
  target.textContent = message;
  target.style.color = tone === 'error' ? '#ef4444' : tone === 'success' ? '#16a34a' : '#8b98ad';
}

function showView(viewName) {
  el.views.forEach((view) => view.classList.toggle('active', view.id === `view-${viewName}`));
}

function scrollToSection(sectionId) {
  const section = document.getElementById(sectionId);
  if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function setActiveNav(navAction) {
  el.navItems.forEach((item) => item.classList.toggle('active', item.dataset.navAction === navAction));
}

function navActionForContentType(contentType) {
  if (contentType === 'courseware') return 'courseware';
  if (contentType === 'exercise') return 'exercise';
  return 'lesson_plan';
}

async function focusFirstContentByType(contentType) {
  const target = state.contents.find((item) => item.content_type === contentType);
  if (!target) return false;
  await loadContentDetail(target.content_id);
  return true;
}

async function handleNavAction(action, sectionId, viewName) {
  showView(viewName || 'workspace');
  setActiveNav(action || 'lesson_plan');
  scrollToSection(sectionId);
  if (action === 'lesson_plan') {
    setActiveFilter('lesson_plan');
    const found = await focusFirstContentByType('lesson_plan');
    if (!found) el.contentStatus.textContent = '当前定位：课程内容，可填写信息后生成教案。';
    return;
  }
  if (action === 'focus') {
    setActiveFilter('lesson_plan');
    await focusFirstContentByType('lesson_plan');
    setActiveMode('focus');
    el.contentStatus.textContent = '当前定位：教学设计，可切换重难点、流程与活动。';
    return;
  }
  if (action === 'courseware') {
    setActiveFilter('courseware');
    const found = await focusFirstContentByType('courseware');
    if (!found) el.contentStatus.textContent = '当前定位：课件资源，可点击“生成课件”快速创建。';
    return;
  }
  if (action === 'exercise') {
    setActiveFilter('exercise');
    const found = await focusFirstContentByType('exercise');
    if (!found) el.contentStatus.textContent = '当前定位：练习题库，可先生成练习内容。';
    return;
  }
  if (action === 'resource') {
    if (state.token && !state.lastResources.length) await loadResourceList();
    el.resourceQuery?.focus();
    return;
  }
  if (action === 'export') {
    el.contentStatus.textContent = '当前定位：导出/推送，可导出当前成果或模拟推送。';
    return;
  }
  if (action === 'version') {
    if (state.activeContent) await refreshVersions();
    el.contentStatus.textContent = '当前定位：版本管理，可查看或恢复历史版本。';
  }
}

function setActiveMode(mode) {
  state.activeMode = mode;
  el.modeChips.forEach((chip) => chip.classList.toggle('active', chip.dataset.mode === mode));
  if (!state.activeContent) {
    el.contentEditor.value = MODE_CONTENT[mode] || '';
    renderPreview({ title: '教学设计', content_type: mode, raw_content: el.contentEditor.value });
    el.contentStatus.textContent = `当前模式：${chipLabel(mode)}`;
  }
}

function setActiveFilter(filter) {
  state.activeFilter = filter;
  el.filterChips.forEach((chip) => chip.classList.toggle('active', chip.dataset.filter === filter));
  if (filter === 'fullscreen') {
    enterFullscreenPreview();
    return;
  }
  if (filter === 'export') {
    el.exportMarkdown?.click();
    scrollToSection('panel-export');
    setActiveNav('export');
    return;
  }
  if (filter === 'push') {
    simulatePush();
    return;
  }
  renderContentList(state.contents, filter);
}

function chipLabel(mode) {
  return mode === 'focus' ? '教学重难点' : mode === 'process' ? '教学流程' : '活动设计';
}

function insertAtCursor(target, text) {
  const start = target.selectionStart || 0;
  const end = target.selectionEnd || 0;
  const value = target.value || '';
  target.value = `${value.slice(0, start)}${text}${value.slice(end)}`;
  target.selectionStart = target.selectionEnd = start + text.length;
  target.focus();
}

function renderPreview(content) {
  if (!content) {
    el.previewTag.textContent = '课程预览';
    el.previewTitle.textContent = 'MATH';
    el.previewSubtitle.textContent = '输入课程信息后，这里会展示当前教案/课件预览摘要。';
    return;
  }
  el.previewTag.textContent = FILTER_LABELS[content.content_type] || content.content_type || '教学内容';
  el.previewTitle.textContent = (content.title || '教学成果').slice(0, 36);
  el.previewSubtitle.textContent = (content.raw_content || '').slice(0, 120) || '已生成内容，可继续编辑。';
}

function renderTabs(contents) {
  el.contentTabs.innerHTML = '';
  (contents || []).forEach((item) => {
    const btn = document.createElement('button');
    btn.className = `tab-btn ${item.content_id === state.activeTab ? 'active' : ''}`;
    btn.textContent = item.title || item.content_type;
    btn.onclick = async function () {
      await loadContentDetail(item.content_id);
    };
    el.contentTabs.appendChild(btn);
  });
}

function renderKnowledgeSummary(items) {
  if (!items || !items.length) {
    el.citationList.className = 'summary-list empty';
    el.citationList.textContent = '暂无知识点摘要';
    return;
  }
  el.citationList.className = 'summary-list';
  el.citationList.innerHTML = '';
  items.slice(0, 4).forEach((item) => {
    const div = document.createElement('div');
    div.className = 'list-item clickable-card';
    div.innerHTML = `<strong>${item.title || '知识点'}</strong><small>${item.citation_text || item.snippet || item.content || ''}</small>`;
    div.onclick = function () {
      el.uploadTitle.value = item.title || '';
      el.uploadContent.value = item.content || item.snippet || item.citation_text || '';
      el.resourceQuery.value = item.title || '';
      scrollToSection('panel-resource');
      setActiveNav('resource');
    };
    el.citationList.appendChild(div);
  });
}

function renderVersions(items) {
  if (!items || !items.length) {
    el.versionList.className = 'stack-list empty';
    el.versionList.textContent = '暂无版本记录';
    return;
  }
  el.versionList.className = 'stack-list';
  el.versionList.innerHTML = '';
  items.forEach((item) => {
    const versionId = item.version_id || item.id || '';
    const div = document.createElement('div');
    div.className = 'list-item';
    div.innerHTML = `<strong>${item.change_summary || '版本记录'}</strong><small>${item.created_at || ''}</small><small>${versionId}</small>`;
    const actions = document.createElement('div');
    actions.className = 'content-card-actions';
    const openBtn = document.createElement('button');
    openBtn.className = 'ghost-btn';
    openBtn.textContent = '查看';
    openBtn.onclick = async function () {
      if (!versionId) return;
      const result = await api.versionDetail(versionId);
      const data = result.data || result;
      el.contentEditor.value = data.content_snapshot || data.raw_content || '';
      el.contentStatus.textContent = `查看版本：${versionId}`;
      renderPreview({ title: state.activeContent?.title || '版本内容', content_type: state.activeContent?.content_type || 'lesson_plan', raw_content: el.contentEditor.value });
    };
    const restoreBtn = document.createElement('button');
    restoreBtn.className = 'ghost-btn';
    restoreBtn.textContent = '恢复';
    restoreBtn.onclick = async function () {
      if (!state.activeContent || !versionId) return;
      await api.restoreVersion(state.activeContent.content_id, versionId);
      await loadContentDetail(state.activeContent.content_id);
    };
    actions.append(openBtn, restoreBtn);
    div.appendChild(actions);
    el.versionList.appendChild(div);
  });
}

function renderExports(files) {
  const entries = Object.entries(files || {});
  if (!entries.length) {
    el.exportList.className = 'stack-list empty';
    el.exportList.textContent = '暂无导出文件';
    return;
  }
  el.exportList.className = 'stack-list';
  el.exportList.innerHTML = '';
  entries.forEach(([format, info]) => {
    const div = document.createElement('div');
    div.className = 'list-item';
    const filePath = encodeURIComponent(info.file_path || '');
    div.innerHTML = `<strong>${format.toUpperCase()}</strong><small>${info.file_name || ''}</small><small>${info.file_size_mb || 0} MB</small><a href="/api/v1/export/download?file_path=${filePath}" target="_blank">下载文件</a>`;
    el.exportList.appendChild(div);
  });
}

function renderContentList(items, filter = state.activeFilter) {
  const filteredItems = (items || []).filter((item) => {
    if (!FILTER_LABELS[filter]) return true;
    return item.content_type === filter;
  });
  if (!filteredItems.length) {
    el.contentList.className = 'result-gallery empty';
    el.contentList.textContent = '当前筛选下暂无内容数据';
    return;
  }
  el.contentList.className = 'result-gallery';
  el.contentList.innerHTML = '';
  filteredItems.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'content-card';
    card.innerHTML = `<div class="content-card-header"><div><div class="badge">${FILTER_LABELS[item.content_type] || item.content_type || 'content'}</div><h4>${item.title || '未命名内容'}</h4><small>${item.generated_at || item.updated_at || ''}</small></div><div class="content-card-actions"></div></div><small>${(item.raw_content || '').slice(0, 90)}...</small>`;
    const actions = card.querySelector('.content-card-actions');
    const openBtn = document.createElement('button');
    openBtn.className = 'ghost-btn';
    openBtn.textContent = '打开';
    openBtn.onclick = async function () {
      await loadContentDetail(item.content_id);
      scrollToSection('panel-stage');
      setActiveNav(navActionForContentType(item.content_type));
    };
    const cloneBtn = document.createElement('button');
    cloneBtn.className = 'ghost-btn';
    cloneBtn.textContent = '克隆';
    cloneBtn.onclick = async function () {
      await api.cloneContent(item.content_id, `${item.title || '内容'}-副本`);
      await refreshContents();
    };
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'ghost-btn';
    deleteBtn.textContent = '删除';
    deleteBtn.onclick = async function () {
      await api.deleteContent(item.content_id);
      await refreshContents();
    };
    actions.append(openBtn, cloneBtn, deleteBtn);
    card.onclick = async function (event) {
      if (event.target.tagName === 'BUTTON') return;
      await loadContentDetail(item.content_id);
    };
    el.contentList.appendChild(card);
  });
}

function renderResourceResults(items) {
  if (!items || !items.length) {
    el.resourceResults.className = 'resource-list empty';
    el.resourceResults.textContent = '暂无资源';
    return;
  }
  el.resourceResults.className = 'resource-list';
  el.resourceResults.innerHTML = '';
  items.forEach((item) => {
    const div = document.createElement('div');
    div.className = 'list-item clickable-card';
    div.innerHTML = `<strong>${item.title || '未命名资源'}</strong><small>${item.resource_type || ''}</small><small>${item.snippet || item.content || ''}</small>`;
    const actions = document.createElement('div');
    actions.className = 'content-card-actions';
    if (item.resource_id) {
      const citeBtn = document.createElement('button');
      citeBtn.className = 'ghost-btn';
      citeBtn.textContent = '生成引用';
      citeBtn.onclick = async function (event) {
        event.stopPropagation();
        const result = await api.citeResource(item.resource_id);
        renderKnowledgeSummary([{ ...item, citation_text: result.data?.citation_text || '' }]);
        insertAtCursor(el.contentEditor, `\n【知识引用】${result.data?.citation_text || item.title || ''}\n`);
      };
      actions.appendChild(citeBtn);
    }
    const useBtn = document.createElement('button');
    useBtn.className = 'ghost-btn';
    useBtn.textContent = '用于当前教案';
    useBtn.onclick = function (event) {
      event.stopPropagation();
      applyResourceToEditor(item);
    };
    actions.appendChild(useBtn);
    div.appendChild(actions);
    div.onclick = function () {
      applyResourceToKnowledge(item);
    };
    el.resourceResults.appendChild(div);
  });
}

function renderCollabStatus(payload) {
  if (!payload) {
    el.collabStatus.className = 'timeline-list empty';
    el.collabStatus.textContent = '尚未创建协同会话';
    return;
  }
  el.collabStatus.className = 'timeline-list';
  el.collabStatus.innerHTML = `<div class="list-item"><strong>${payload.title}</strong><small>${payload.meta || ''}</small><small>${payload.desc || ''}</small></div>`;
}

function collectGeneratePayload() {
  const formData = new FormData(el.generateForm);
  const checked = Array.from(el.generateForm.querySelectorAll('.chip-group input:checked')).map((input) => input.value);
  return {
    course_name: formData.get('course_name') || '',
    chapter: formData.get('chapter') || '',
    grade_level: formData.get('grade_level') || '',
    subject: formData.get('subject') || '',
    teaching_objectives: formData.get('teaching_objectives') || '',
    class_hours: Number(formData.get('class_hours') || 1),
    content_types: checked.join(','),
    use_kb: formData.get('use_kb') !== null,
    key_points: formData.get('key_points') || '',
    difficult_points: formData.get('difficult_points') || '',
    additional_instructions: formData.get('additional_instructions') || '',
  };
}

function applyResourceToKnowledge(item) {
  el.uploadTitle.value = item.title || '';
  el.uploadContent.value = item.content || item.snippet || '';
  el.uploadTags.value = Array.isArray(item.tags) ? item.tags.join(',') : item.tags || '';
  el.uploadType.value = item.resource_type || 'school_based';
  el.uploadUrl.value = item.source_url || '';
  renderKnowledgeSummary([item, ...state.lastResources.filter((res) => res.resource_id !== item.resource_id)].slice(0, 4));
  scrollToSection('panel-resource');
  setActiveNav('resource');
}

function applyResourceToEditor(item) {
  insertAtCursor(el.contentEditor, `\n【补充知识】${item.title || '资源'}\n${item.snippet || item.content || ''}\n`);
  renderPreview({
    title: state.activeContent?.title || '教学成果',
    content_type: state.activeContent?.content_type || 'lesson_plan',
    raw_content: el.contentEditor.value,
  });
  el.contentStatus.textContent = `已引用知识资源：${item.title || '资源'}`;
  scrollToSection('panel-stage');
  setActiveNav(navActionForContentType(item.content_type || state.activeContent?.content_type || 'lesson_plan'));
}

function enterFullscreenPreview() {
  const previewBoard = document.querySelector('.preview-board');
  if (!previewBoard) return;
  if (previewBoard.requestFullscreen) previewBoard.requestFullscreen();
  el.contentStatus.textContent = '已进入预览全屏模式';
}

function simulatePush() {
  renderCollabStatus({
    title: '推送任务已创建',
    meta: '目标：班级教学终端',
    desc: '当前为演示模式，已完成推送状态模拟。',
  });
  scrollToSection('panel-export');
  setActiveNav('export');
}

async function updateMetrics() {
  try {
    const health = await api.health();
    el.metricHealth.textContent = health.status || 'unknown';
  } catch {
    el.metricHealth.textContent = '异常';
  }
  try {
    const stats = await api.knowledgeStats();
    el.metricDocuments.textContent = (stats.data && stats.data.total_documents) || 0;
  } catch {
    el.metricDocuments.textContent = '0';
  }
  const displayName = (state.currentUser && state.currentUser.display_name) || '未登录';
  el.metricUser.textContent = displayName;
  el.headerUserName.textContent = displayName;
  el.metricContents.textContent = String(state.contents.length || 0);
}

async function refreshContents() {
  if (!state.token) return;
  const result = await api.contents();
  state.contents = result.data?.items || [];
  renderContentList(state.contents, state.activeFilter);
  if (state.contents[0] && !state.activeContent) await loadContentDetail(state.contents[0].content_id);
  await updateMetrics();
}

async function loadContentDetail(contentId) {
  const result = await api.contentDetail(contentId);
  const data = result.data || result;
  state.activeContent = data;
  state.activeTab = data.content_id;
  const listItem = state.contents.find((item) => item.content_id === contentId);
  if (listItem) Object.assign(listItem, data);
  el.contentEditor.value = data.raw_content || '';
  el.contentStatus.textContent = `当前编辑：${data.title || data.content_type}`;
  renderTabs(state.contents.length ? state.contents : [data]);
  renderVersions(data.versions || []);
  renderPreview(data);
  if (FILTER_LABELS[data.content_type]) {
    setActiveFilter(data.content_type);
    setActiveNav(navActionForContentType(data.content_type));
  }
}

async function refreshVersions() {
  if (!state.activeContent) return;
  const result = await api.versionList(state.activeContent.content_id);
  renderVersions(result.data?.versions || []);
}

async function applyLoginResult(result, fallbackName = 'teacher01') {
  const payload = result.data || {};
  state.token = payload.access_token || '';
  state.currentUser = payload.user_info || null;
  store.write({ token: state.token, currentUser: state.currentUser });
  setFeedback(el.loginFeedback, `欢迎回来，${state.currentUser?.display_name || fallbackName}`, 'success');
  closeLoginModal();
  await bootAfterLogin();
}

async function login(username, password) {
  const result = await api.login({ username, password });
  await applyLoginResult(result, username);
}

async function loginWithDemoAccount() {
  try {
    const result = await api.demoLogin();
    await applyLoginResult(result, 'teacher01');
  } catch {
    const result = await api.login({ username: 'teacher01', password: '123456' });
    await applyLoginResult(result, 'teacher01');
  }
}

async function bootAfterLogin() {
  await Promise.all([refreshContents(), loadResourceList(), updateMetrics()]);
}

async function loadResourceList() {
  if (!state.token) return;
  const result = await api.listResources();
  state.lastResources = result.data?.items || [];
  renderResourceResults(state.lastResources);
  renderKnowledgeSummary(state.lastResources.slice(0, 4));
}

function fillDemoData() {
  const scene = el.sceneSelect?.value || '高中教学';
  const unit = el.unitSelect?.value || '第一单元·集合';
  const sceneMap = {
    高中教学: {
      course_name: '高中数学',
      grade_level: '高一',
      subject: '数学',
      chapter: unit.replace('·', ' '),
      teaching_objectives: '掌握集合的定义、表示方法及基本运算，能够结合实例理解交并补关系。',
      key_points: '集合定义、表示方法、交并补运算',
      difficult_points: '抽象概念理解与应用迁移',
      additional_instructions: '内容风格要求适合课堂讲授，加入互动提问和例题讲解。',
    },
    初中教学: {
      course_name: '初中数学',
      grade_level: '初二',
      subject: '数学',
      chapter: '第二单元 函数',
      teaching_objectives: '理解一次函数图像与性质，能够通过实际问题建立函数模型。',
      key_points: '函数概念、图像绘制、性质分析',
      difficult_points: '数形结合与模型迁移',
      additional_instructions: '加入生活化案例与分层练习。',
    },
    大学教学: {
      course_name: 'Python程序设计',
      grade_level: '大学一年级',
      subject: '计算机',
      chapter: '第3章 函数与模块',
      teaching_objectives: '理解函数定义与调用，掌握参数传递方式，并能够完成基础模块拆分设计。',
      key_points: '函数定义、参数传递、模块导入',
      difficult_points: '作用域、闭包',
      additional_instructions: '加入案例驱动和编程练习。',
    },
  };
  const demo = sceneMap[scene] || sceneMap['高中教学'];
  Object.keys(demo).forEach((key) => {
    const field = el.generateForm.elements.namedItem(key);
    if (field) field.value = demo[key];
  });
  renderPreview({ title: `${demo.course_name}-${unit.replace('·', '-')}`, content_type: 'lesson_plan', raw_content: demo.teaching_objectives });
}

async function startCollabSession() {
  if (!state.activeContent) return;
  const created = await api.createSession(state.activeContent.content_id);
  state.sessionId = created.data?.session_id || created.session_id || '';
  renderCollabStatus({
    title: '协同会话已创建',
    meta: state.sessionId,
    desc: '正在连接协同通道...',
  });
  connectWebSocket();
}

function connectWebSocket() {
  if (!state.activeContent) return;
  if (state.ws) state.ws.close();
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${location.host}/ws/collaboration/${state.activeContent.content_id}`);
  ws.addEventListener('open', () => ws.send(JSON.stringify({ action: 'join' })));
  ws.addEventListener('message', (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.action === 'joined') {
        renderCollabStatus({
          title: '协同会话进行中',
          meta: data.session_id,
          desc: `参与者：${(data.participants || []).join(', ')}`,
        });
      }
      if (data.action === 'update') {
        renderCollabStatus({
          title: '收到协同更新',
          meta: data.user_id,
          desc: data.delta || '',
        });
      }
    } catch {}
  });
  state.ws = ws;
}

async function handleStreamGenerate(payload) {
  el.streamStatus.classList.remove('hidden');
  el.streamStatus.textContent = '正在流式生成中...';
  el.contentEditor.value = '';
  let metaContentId = '';
  await api.streamGenerate(payload, {
    onMessage(message) {
      if (message.type === 'meta') {
        metaContentId = message.content_id || '';
        el.contentStatus.textContent = `生成中 · 模型 ${message.model || ''}`;
      }
      if (message.type === 'token') {
        el.contentEditor.value += message.text || '';
        renderPreview({ title: payload.course_name || '教学内容', content_type: 'lesson_plan', raw_content: el.contentEditor.value });
      }
      if (message.type === 'done') {
        el.streamStatus.textContent = `生成完成，共 ${message.total_length || 0} 字`;
      }
    },
    onEnd() {
      el.streamStatus.classList.add('hidden');
    },
  });
  const generated = await api.generate(payload);
  state.contents = generated.data?.contents || [];
  renderTabs(state.contents);
  renderContentList(state.contents, state.activeFilter);
  const preferred = state.contents.find((item) => item.content_id === metaContentId) || state.contents[0];
  if (preferred) await loadContentDetail(preferred.content_id);
  await updateMetrics();
}

async function handleStandardGenerate() {
  if (!state.token) return openLoginModal();
  const result = await api.generate(collectGeneratePayload());
  state.contents = result.data?.contents || [];
  renderTabs(state.contents);
  renderContentList(state.contents, state.activeFilter);
  if (state.contents[0]) await loadContentDetail(state.contents[0].content_id);
  await updateMetrics();
}

function bindEvents() {
  el.openLogin?.addEventListener('click', openLoginModal);
  el.closeLogin?.addEventListener('click', closeLoginModal);
  el.loginModal?.addEventListener('click', (event) => {
    if (event.target === el.loginModal) closeLoginModal();
  });
  el.useDemo?.addEventListener('click', fillDemoData);
  el.sceneSelect?.addEventListener('change', fillDemoData);
  el.unitSelect?.addEventListener('change', fillDemoData);
  el.demoLogin?.addEventListener('click', async () => {
    try {
      await loginWithDemoAccount();
    } catch {
      setFeedback(el.loginFeedback, '演示账号免密进入失败，请稍后重试', 'error');
    }
  });
  el.navItems.forEach((item) => item.addEventListener('click', async () => {
    await handleNavAction(item.dataset.navAction, item.dataset.section, item.dataset.view);
  }));
  el.modeChips.forEach((chip) => chip.addEventListener('click', () => setActiveMode(chip.dataset.mode)));
  el.filterChips.forEach((chip) => chip.addEventListener('click', () => setActiveFilter(chip.dataset.filter)));
  el.toolTiles.forEach((tile) => tile.addEventListener('click', () => {
    insertAtCursor(el.contentEditor, TOOL_SNIPPETS[tile.dataset.tool] || '\n');
    el.contentStatus.textContent = `已插入${tile.textContent}模块`;
    renderPreview({
      title: state.activeContent?.title || '教学成果',
      content_type: state.activeContent?.content_type || 'lesson_plan',
      raw_content: el.contentEditor.value,
    });
  }));
  el.loginForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(el.loginForm);
    const username = formData.get('username');
    const password = formData.get('password');
    try {
      if (!password && username === 'teacher01') {
        await loginWithDemoAccount();
        return;
      }
      await login(username, password);
    } catch {
      setFeedback(el.loginFeedback, '登录失败，请检查用户名和密码，或直接点免密进入', 'error');
    }
  });
  el.generateForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!state.token) return openLoginModal();
    await handleStreamGenerate(collectGeneratePayload());
  });
  el.generateNormal?.addEventListener('click', handleStandardGenerate);
  el.saveContent?.addEventListener('click', async () => {
    if (!state.activeContent) return;
    await api.updateContent(state.activeContent.content_id, {
      raw_content: el.contentEditor.value,
      change_summary: '前端工作台保存',
    });
    await loadContentDetail(state.activeContent.content_id);
  });
  el.improveContent?.addEventListener('click', async () => {
    const requirement = prompt('请输入优化要求', '请增强课堂互动和例题说明');
    if (!requirement) return;
    const result = await api.improve({
      content_text: el.contentEditor.value,
      improvement_request: requirement,
    });
    el.contentEditor.value = result.data?.improved_content || '';
    el.contentStatus.textContent = '已完成智能优化，可继续保存';
    renderPreview({
      title: state.activeContent?.title || '教学成果',
      content_type: state.activeContent?.content_type || 'lesson_plan',
      raw_content: el.contentEditor.value,
    });
  });
  el.searchResource?.addEventListener('click', async () => {
    if (!state.token) return openLoginModal();
    const result = await api.searchResources({ query: el.resourceQuery.value || '集合', max_results: 8 });
    const data = result.data || {};
    state.lastResources = data.results || data.items || [];
    renderResourceResults(state.lastResources);
  });
  el.uploadResource?.addEventListener('click', async () => {
    if (!state.token) return openLoginModal();
    await api.uploadResource({
      title: el.uploadTitle.value,
      resource_type: el.uploadType.value || 'school_based',
      tags: el.uploadTags.value,
      content: el.uploadContent.value,
      source_url: el.uploadUrl.value,
    });
    await loadResourceList();
  });
  el.refreshContents?.addEventListener('click', refreshContents);
  el.refreshCitations?.addEventListener('click', () => renderKnowledgeSummary(state.lastResources.slice(0, 4)));
  el.refreshVersions?.addEventListener('click', refreshVersions);
  el.exportMarkdown?.addEventListener('click', async () => {
    if (!state.activeContent) return;
    const result = await api.exportContent({
      content_json: JSON.stringify([state.activeContent]),
      title: state.activeContent.title || '教学内容',
      export_format: 'markdown',
    });
    renderExports(result.data?.files || {});
    scrollToSection('panel-export');
    setActiveNav('export');
  });
  el.startSession?.addEventListener('click', startCollabSession);
}

async function init() {
  bindEvents();
  fillDemoData();
  renderPreview(null);
  setActiveMode('focus');
  setActiveFilter('lesson_plan');
  setActiveNav('lesson_plan');
  try {
    await updateMetrics();
  } catch {}
  if (state.token) {
    try {
      const me = await api.me();
      state.currentUser = me.data || me;
      store.write({ token: state.token, currentUser: state.currentUser });
      await bootAfterLogin();
    } catch {
      store.clear();
      state.token = '';
      state.currentUser = null;
      openLoginModal();
    }
  } else {
    openLoginModal();
  }
}

init();

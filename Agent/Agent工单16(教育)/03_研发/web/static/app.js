const scenes = window.__SCENES__ || [];
const sceneMap = Object.fromEntries(scenes.map((item) => [item.key, item]));
const providerLabels = { deepseek: 'DeepSeek', qwen: '千问' };
let currentScene = scenes[0]?.key || 'lesson';
const form = document.getElementById('scene-form');
const titleEl = document.getElementById('scene-title');
const descEl = document.getElementById('scene-desc');
const statusEl = document.getElementById('request-status');
const resultEl = document.getElementById('result-content');
const cardsEl = document.getElementById('result-cards');
const sceneChipEl = document.getElementById('result-scene-chip');
const providerChipEl = document.getElementById('result-provider-chip');
const providerEl = document.getElementById('model_provider');
const imageEl = document.getElementById('image');
const requestModeEl = document.getElementById('request-mode');

function syncRequestMode() {
  const hasImage = Boolean(imageEl?.files?.length);
  const modeText = hasImage ? '当前模式：图文分析' : '当前模式：文本交互';
  requestModeEl.textContent = modeText;
}

function syncProviderChip() {
  const provider = providerEl?.value || 'deepseek';
  providerChipEl.textContent = `${providerLabels[provider] || 'DeepSeek'} · 待执行`;
}

document.querySelectorAll('.scene-card').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.scene-card').forEach((node) => node.classList.remove('active'));
    button.classList.add('active');
    currentScene = button.dataset.scene;
    const meta = sceneMap[currentScene];
    titleEl.textContent = meta?.name || '教学场景';
    descEl.textContent = meta?.description || '';
    sceneChipEl.textContent = meta?.name || '教学场景';
    statusEl.textContent = '已切换场景';
  });
});

providerEl?.addEventListener('change', syncProviderChip);
imageEl?.addEventListener('change', syncRequestMode);
syncProviderChip();
syncRequestMode();

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  syncRequestMode();
  statusEl.textContent = '正在生成，请稍候...';
  resultEl.textContent = '正在处理中，请稍候。';
  cardsEl.innerHTML = '';
  const formData = new FormData(form);
  if (currentScene !== 'tutor') {
    formData.delete('session_id');
  } else {
    formData.set('session_id', 'demo-session-001');
  }
  try {
    const response = await fetch(`/api/scene/${currentScene}`, { method: 'POST', body: formData });
    const data = await response.json();
    if (!data.success) {
      throw new Error(data.message || '请求失败');
    }
    renderResult(data.data);
    statusEl.textContent = '生成完成';
  } catch (error) {
    resultEl.textContent = `处理失败：${error.message}`;
    statusEl.textContent = '处理失败';
  }
});

function renderResult(data) {
  sceneChipEl.textContent = sceneMap[data.scene]?.name || '结果';
  providerChipEl.textContent = `${providerLabels[data.model_provider] || 'DeepSeek'} · ${data.input_mode === 'image' ? '图文模式' : '文本模式'}`;
  const cards = data.cards || data.scores || data.highlights || [];
  cardsEl.innerHTML = cards.map((card) => `
    <section class="mini-card">
      <span>${card.label}</span>
      <strong>${card.value}</strong>
    </section>
  `).join('');
  resultEl.textContent = data.summary || data.answer || data.feedback || data.plan || '暂无输出内容';
}

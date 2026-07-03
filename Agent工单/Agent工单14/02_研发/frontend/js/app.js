/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * 主应用逻辑 —— 连接检查、Toast 通知、Tab 切换、影像上传、消息渲染
 */
// ====== 全局配置 ======
const API_BASE = window.location.origin;  // 自动适配当前域名端口

// ====== 全局状态 ======
const state = {
    uploadedImage: null,       // {filename, url, originalName, sizeKb}
    isUploading: false,        // 上传进行中标志
    sessionHistory: [],        // 会话历史记录
    currentTab: 'vqa',         // 当前激活的 Tab
};

// ====== 连接检查（每 30s 轮询） ======
async function checkConnection() {
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    try {
        const r = await fetch(API_BASE + '/api/health');
        if (r.ok) { dot.className = 'status-dot online'; txt.textContent = '系统就绪'; }
    } catch { dot.className = 'status-dot'; txt.textContent = '连接中...'; }
}
checkConnection();
setInterval(checkConnection, 30000);

// ====== Toast 弹出通知 ======
function showToast(msg, type = 'info') {
    const c = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => t.remove(), 4000);  // 4 秒后自动消失
}

// ====== Tab 切换 ======
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const target = tab.dataset.tab;  // vqa / mrg / rag / asst
        state.currentTab = target;
        // 移除所有 active 状态
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        // 激活当前
        tab.classList.add('active');
        document.getElementById(target + 'Panel').classList.add('active');
    });
});

// ====== 影像上传 ======
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const previewImage = document.getElementById('previewImage');
const uploadBtn = document.getElementById('uploadBtn');
const placeholder = uploadArea.querySelector('.upload-placeholder');

// 点击/拖拽触发文件选择
uploadArea.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
uploadArea.addEventListener('drop', e => {
    e.preventDefault(); uploadArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length > 0) handleFile(fileInput.files[0]); });

function handleFile(file) {
    // MIME + 扩展名双重校验（浏览器可能不识 DICOM/TIFF）
    const mimes = ['image/jpeg','image/png','image/gif','image/webp','image/tiff','application/dicom','application/octet-stream'];
    const exts = ['.jpg','.jpeg','.png','.gif','.webp','.tiff','.tif','.dcm','.dicom'];
    const ext = (file.name || '').toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!mimes.includes(file.type) && !exts.includes(ext)) {
        showToast('不支持的格式: ' + (file.type || ext), 'error'); return;
    }
    // 预览图片
    const reader = new FileReader();
    reader.onload = e => {
        previewImage.src = e.target.result;
        previewImage.style.display = 'block';
        placeholder.style.display = 'none';
    };
    reader.readAsDataURL(file);
    uploadBtn.disabled = false;
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = (file.size / 1024).toFixed(1) + ' KB';
    document.getElementById('uploadInfo').style.display = 'flex';
}

// 上传按钮点击
uploadBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    state.isUploading = true; uploadBtn.disabled = true;
    const fd = new FormData(); fd.append('file', file);
    try {
        const r = await fetch(API_BASE + '/api/upload/image', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.success) {
            state.uploadedImage = { filename: d.filename, url: d.url, originalName: d.original_name, sizeKb: d.size_kb };
            showToast('上传成功', 'success');
            // 通知 VQA/MRG 面板影像已就绪
            document.getElementById('vqaInput').disabled = false;
            document.getElementById('vqaSendBtn').disabled = false;
            document.getElementById('mrgGenerateBtn').disabled = false;
            if (typeof onVqaReady === 'function') onVqaReady();
            if (typeof onMrgReady === 'function') onMrgReady();
            addHistory(d.original_name);  // 记录到会话历史
        } else showToast('上传失败', 'error');
    } catch (e) { showToast('上传失败: ' + e.message, 'error'); }
    finally { state.isUploading = false; uploadBtn.disabled = false; }
});

// ====== 会话历史 ======
function addHistory(name) {
    state.sessionHistory.unshift({ name, time: new Date().toLocaleTimeString() });
    const c = document.getElementById('historyList');
    c.innerHTML = state.sessionHistory.map(h =>
        '<div class="history-item"><div>📷 ' + h.name + '</div><small>' + h.time + '</small></div>'
    ).join('');
}

// ====== 消息渲染工具 ======
function addMsg(containerId, role, content, meta) {
    // role: user(右对齐蓝底) / assistant(左对齐白底) / system(居中提示)
    const c = document.getElementById(containerId);
    const d = document.createElement('div');
    d.className = 'msg ' + role;
    d.innerHTML = '<div class="msg-body">' + content + '</div>' +
                  (meta ? '<div class="msg-meta">' + meta + '</div>' : '');
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;  // 自动滚动到底部
    return d;
}

function showTyping(containerId) {
    const c = document.getElementById(containerId);
    const d = document.createElement('div');
    d.className = 'msg assistant';
    d.id = '__typing';
    d.innerHTML = '<div class="msg-body"><div class="typing"><span></span><span></span><span></span></div></div>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
}

function hideTyping() {
    const e = document.getElementById('__typing');
    if (e) e.remove();
}

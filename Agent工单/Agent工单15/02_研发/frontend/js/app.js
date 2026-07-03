/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * 主应用逻辑 —— 连接检查、Toast 通知、Tab 切换、影像上传、消息渲染
 * 所有共享 API 通过 window.MA 命名空间暴露给其他 JS 模块
 */
'use strict';

(function () {
  // ====== 全局配置 ======
  var API_BASE = window.location.origin; // 自动适配当前域名端口

  // ====== 全局状态 ======
  var state = {
    uploadedImage: null, // {filename, url, originalName, sizeKb}
    isUploading: false,  // 上传进行中标志
    sessionHistory: [],  // 会话历史记录
    currentTab: 'vqa',   // 当前激活的 Tab
  };

  // ====== 连接检查（每 30s 轮询） ======
  function checkConnection() {
    var dot = document.getElementById('statusDot');
    var txt = document.getElementById('statusText');
    fetch(API_BASE + '/api/health')
      .then(function (r) {
        if (r.ok) { dot.className = 'status-dot online'; txt.textContent = '系统就绪'; }
      })
      .catch(function () { dot.className = 'status-dot'; txt.textContent = '连接中...'; });
  }
  checkConnection();
  setInterval(checkConnection, 30000);

  // ====== Toast 弹出通知 ======
  function showToast(msg, type) {
    type = type || 'info';
    var c = document.getElementById('toastContainer');
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(function () { t.remove(); }, 4000);
  }

  // ====== Tab 切换 ======
  var _mapLoaded = false;

  // 需要上传侧边栏的 Tab（只有 VQA）
  var _uploadTabs = ['vqa'];

  function toggleSidebar(show) {
    var sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.style.display = show ? '' : 'none';
  }

  document.querySelectorAll('.tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var target = tab.dataset.tab;
      state.currentTab = target;
      document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
      document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('active'); });
      tab.classList.add('active');
      document.getElementById(target + 'Panel').classList.add('active');
      toggleSidebar(_uploadTabs.indexOf(target) >= 0);
      if (target === 'map' && !_mapLoaded) loadMapIframe();
    });
  });

  // ====== 地图懒加载 ======
  function loadMapIframe() {
    if (_mapLoaded) return;
    _mapLoaded = true;
    var placeholder = document.getElementById('mapPlaceholder');
    var iframe = document.getElementById('mapIframe');
    if (placeholder) { placeholder.style.display = 'none'; }
    if (iframe) {
      iframe.src = '/map';
      iframe.style.display = '';
    }
  }

  // ====== 影像上传 ======
  var uploadArea = document.getElementById('uploadArea');
  var fileInput = document.getElementById('fileInput');
  var previewImage = document.getElementById('previewImage');
  var uploadBtn = document.getElementById('uploadBtn');
  var placeholder = uploadArea.querySelector('.upload-placeholder');

  uploadArea.addEventListener('click', function () { fileInput.click(); });
  uploadArea.addEventListener('dragover', function (e) { e.preventDefault(); uploadArea.classList.add('drag-over'); });
  uploadArea.addEventListener('dragleave', function () { uploadArea.classList.remove('drag-over'); });
  uploadArea.addEventListener('drop', function (e) {
    e.preventDefault(); uploadArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', function () { if (fileInput.files.length > 0) handleFile(fileInput.files[0]); });

  function handleFile(file) {
    var mimes = ['image/jpeg','image/png','image/gif','image/webp','image/tiff','application/dicom','application/octet-stream'];
    var exts = ['.jpg','.jpeg','.png','.gif','.webp','.tiff','.tif','.dcm','.dicom'];
    var ext = (file.name || '').toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!mimes.includes(file.type) && !exts.includes(ext)) {
      showToast('不支持的格式: ' + (file.type || ext), 'error'); return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
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

  uploadBtn.addEventListener('click', function () {
    var file = fileInput.files[0];
    if (!file) return;
    state.isUploading = true; uploadBtn.disabled = true;
    var fd = new FormData(); fd.append('file', file);
    fetch(API_BASE + '/api/upload/image', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.success) {
          state.uploadedImage = { filename: d.filename, url: d.url, originalName: d.original_name, sizeKb: d.size_kb };
          showToast('上传成功', 'success');
          document.getElementById('vqaInput').disabled = false;
          document.getElementById('vqaSendBtn').disabled = false;
          document.getElementById('mrgGenerateBtn').disabled = false;
          if (typeof window.onVqaReady === 'function') window.onVqaReady();
          if (typeof window.onMrgReady === 'function') window.onMrgReady();
          addHistory(d.original_name);
        } else showToast('上传失败', 'error');
      })
      .catch(function (e) { showToast('上传失败: ' + e.message, 'error'); })
      .finally(function () { state.isUploading = false; uploadBtn.disabled = false; });
  });

  // ====== 会话历史 ======
  function addHistory(name) {
    state.sessionHistory.unshift({ name: name, time: new Date().toLocaleTimeString() });
    var c = document.getElementById('historyList');
    c.innerHTML = state.sessionHistory.map(function (h) {
      return '<div class="history-item"><div>📷 ' + h.name + '</div><small>' + h.time + '</small></div>';
    }).join('');
  }

  // ====== 消息渲染工具 ======
  function addMsg(containerId, role, content, meta) {
    var c = document.getElementById(containerId);
    var d = document.createElement('div');
    d.className = 'msg ' + role;
    d.innerHTML = '<div class="msg-body">' + content + '</div>' +
                  (meta ? '<div class="msg-meta">' + meta + '</div>' : '');
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
    return d;
  }

  function showTyping(containerId) {
    var c = document.getElementById(containerId);
    var d = document.createElement('div');
    d.className = 'msg assistant';
    d.id = '__typing';
    d.innerHTML = '<div class="msg-body"><div class="typing"><span></span><span></span><span></span></div></div>';
    c.appendChild(d);
    c.scrollTop = c.scrollHeight;
  }

  function hideTyping() {
    var e = document.getElementById('__typing');
    if (e) e.remove();
  }

  // ====== 暴露共享 API 到 window.MA 命名空间 ======
  window.MA = {
    API_BASE: API_BASE,
    state: state,
    showToast: showToast,
    addMsg: addMsg,
    showTyping: showTyping,
    hideTyping: hideTyping,
    checkConnection: checkConnection,
    loadMapIframe: loadMapIframe,
  };

})();

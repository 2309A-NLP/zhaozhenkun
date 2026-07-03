/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * MRG 医疗报告生成模块 —— 独立上传影像 + 自动生成结构化诊断报告
 */
'use strict';

(function () {
  var MA = window.MA;

  var mrgGenerateBtn = document.getElementById('mrgGenerateBtn');
  var mrgClinicalInfo = document.getElementById('mrgClinicalInfo');
  var mrgOutput = document.getElementById('mrgOutput');
  var mrgActions = document.getElementById('mrgActions');
  var currentReport = '';

  // MRG 独立状态
  var mrgImage = null; // {filename, url}

  // ====== MRG 独立上传 ======
  var mrgUploadArea = document.getElementById('mrgUploadArea');
  var mrgFileInput = document.getElementById('mrgFileInput');
  var mrgDropZone = document.getElementById('mrgDropZone');
  var mrgPreview = document.getElementById('mrgPreview');
  var mrgFileInfo = document.getElementById('mrgFileInfo');

  mrgUploadArea.addEventListener('click', function () { mrgFileInput.click(); });
  mrgUploadArea.addEventListener('dragover', function (e) { e.preventDefault(); mrgUploadArea.style.borderColor = '#3b82f6'; });
  mrgUploadArea.addEventListener('dragleave', function () { mrgUploadArea.style.borderColor = ''; });
  mrgUploadArea.addEventListener('drop', function (e) {
    e.preventDefault(); mrgUploadArea.style.borderColor = '';
    if (e.dataTransfer.files.length > 0) handleMrgFile(e.dataTransfer.files[0]);
  });
  mrgFileInput.addEventListener('change', function () {
    if (mrgFileInput.files.length > 0) handleMrgFile(mrgFileInput.files[0]);
  });

  function handleMrgFile(file) {
    var exts = ['.jpg','.jpeg','.png','.gif','.webp','.tiff','.tif','.dcm','.dicom'];
    var ext = '.' + (file.name || '').split('.').pop().toLowerCase();
    if (exts.indexOf(ext) < 0) { MA.showToast('不支持的格式: ' + ext, 'error'); return; }

    var reader = new FileReader();
    reader.onload = function (e) {
      mrgPreview.src = e.target.result;
      mrgPreview.style.display = 'block';
      mrgDropZone.style.display = 'none';
    };
    reader.readAsDataURL(file);

    mrgFileInfo.textContent = file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)';
    mrgFileInfo.style.display = 'block';

    _uploadMrgFile(file);
  }

  function _uploadMrgFile(file) {
    var fd = new FormData(); fd.append('file', file);
    mrgGenerateBtn.disabled = true;
    mrgGenerateBtn.textContent = '⏳ 上传中...';
    fetch(MA.API_BASE + '/api/upload/image', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.success) {
          mrgImage = { filename: d.filename, url: d.url };
          mrgGenerateBtn.disabled = false;
          mrgGenerateBtn.textContent = '🩺 生成诊断报告';
          MA.showToast('影像已就绪', 'success');
        } else {
          MA.showToast('上传失败', 'error');
        }
      })
      .catch(function (e) {
        MA.showToast('上传失败: ' + e.message, 'error');
      });
  }

  // ====== 生成报告 ======
  function generateReport() {
    if (!mrgImage) { MA.showToast('请先上传影像', 'error'); return; }

    mrgGenerateBtn.disabled = true;
    mrgGenerateBtn.textContent = '⏳ 生成中...';
    mrgOutput.innerHTML = '<p class="placeholder">AI 正在分析影像...</p>';

    var ci = mrgClinicalInfo.value.trim();

    fetch(MA.API_BASE + '/api/mrg/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_filename: mrgImage.filename, clinical_info: ci }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.success) {
          currentReport = d.report;
          mrgOutput.innerHTML = '<div class="report-content">' +
            d.report.replace(/【(.+?)】/g, '<h3>【$1】</h3>').replace(/\n/g, '<br>') + '</div>';
          mrgActions.style.display = 'flex';
          mrgOutput.insertAdjacentHTML('beforeend',
            '<div class="msg-meta">模型: ' + d.model + ' | ' + d.latency_ms + 'ms</div>');
        } else {
          mrgOutput.innerHTML = '<p style="color:red">⚠ ' + (d.error || '生成失败') + '</p>';
        }
      })
      .catch(function (e) {
        mrgOutput.innerHTML = '<p style="color:red">❌ ' + e.message + '</p>';
      })
      .finally(function () {
        mrgGenerateBtn.disabled = false;
        mrgGenerateBtn.textContent = '🩺 生成诊断报告';
      });
  }

  function formatReport(r) { return r.replace(/【(.+?)】/g, '<h3>【$1】</h3>').replace(/\n/g, '<br>'); }

  window.printReport = function () {
    var w = window.open('', '_blank', 'width=800,height=600');
    w.document.write('<html><head><title>诊断报告</title>' +
      '<style>body{font-family:SimSun;padding:30px;line-height:2}h3{color:#1e40af}</style></head>' +
      '<body><h1>影像诊断报告</h1>' + formatReport(currentReport) +
      '<hr><small>AI生成仅供参考 | 工单: 医疗智能体 V1.0</small></body></html>');
    w.document.close(); setTimeout(function () { w.print(); }, 500);
  };

  window.downloadReport = function () {
    var b = new Blob([currentReport], { type: 'text/plain;charset=utf-8' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(b);
    a.download = '诊断报告_' + new Date().toISOString().slice(0, 10) + '.txt'; a.click();
  };

  mrgGenerateBtn.addEventListener('click', generateReport);

  // 影像就绪回调（由 app.js 调用）
  window.onMrgReady = function () {
    mrgGenerateBtn.disabled = false;
  };

})();

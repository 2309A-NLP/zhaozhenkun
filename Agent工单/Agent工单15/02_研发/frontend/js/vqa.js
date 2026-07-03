/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * VQA 视觉问答模块 —— 需要先上传影像才能提问
 */
'use strict';

(function () {
  var MA = window.MA;

  var vqaInput = document.getElementById('vqaInput');
  var vqaSendBtn = document.getElementById('vqaSendBtn');

  function sendVqa() {
    var q = vqaInput.value.trim();
    if (!q) return;

    if (!MA.state.uploadedImage) {
      MA.showToast('请先上传医学影像', 'error'); return;
    }

    MA.addMsg('vqaMessages', 'user', q);
    vqaInput.value = ''; vqaSendBtn.disabled = true;
    MA.showTyping('vqaMessages');

    fetch(MA.API_BASE + '/api/vqa/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image_filename: MA.state.uploadedImage.filename,
        question: q,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        MA.hideTyping();
        var meta = '模型: ' + (d.model || '?') + ' | ' +
                   (d.latency_ms || 0) + 'ms | Token: ' +
                   (d.usage ? (d.usage.prompt_tokens || 0) : 0) + '+' +
                   (d.usage ? (d.usage.completion_tokens || 0) : 0);
        MA.addMsg('vqaMessages', 'assistant',
                   d.success ? d.answer : '⚠ ' + d.error, meta);
      })
      .catch(function (e) {
        MA.hideTyping();
        MA.addMsg('vqaMessages', 'assistant', '❌ 请求失败: ' + e.message);
      })
      .finally(function () { vqaSendBtn.disabled = false; vqaInput.focus(); });
  }

  vqaSendBtn.addEventListener('click', sendVqa);
  vqaInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendVqa(); });

  // 影像上传完成后由 app.js 调用，激活输入框
  window.onVqaReady = function () {
    vqaInput.disabled = false; vqaSendBtn.disabled = false;
    vqaInput.placeholder = '输入问题...'; vqaInput.focus();
  };

})();

/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * RAG 知识检索模块 —— 上传文档扩充知识库 + 基于知识库的智能问答
 */
'use strict';

(function () {
  var MA = window.MA;

  // ====== DOM 元素 ======
  var ragInput = document.getElementById('ragInput');
  var ragSendBtn = document.getElementById('ragSendBtn');
  var ragFileInput = document.getElementById('ragFileInput');
  var ragUploadBtn = document.getElementById('ragUploadBtn');
  var ragBatchBtn = document.getElementById('ragBatchBtn');

  // ====== 知识库统计 ======
  function loadStats() {
    fetch(MA.API_BASE + '/api/rag/stats')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        document.getElementById('ragDocCount').textContent = d.document_count || 0;
      })
      .catch(function () { document.getElementById('ragDocCount').textContent = '?'; });
  }
  loadStats();

  // ====== RAG 检索问答 ======
  function sendRag() {
    var q = ragInput.value.trim();
    if (!q) return;

    MA.addMsg('ragMessages', 'user', q);
    ragInput.value = ''; ragSendBtn.disabled = true;
    MA.showTyping('ragMessages');

    fetch(MA.API_BASE + '/api/rag/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, top_k: 5 }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        MA.hideTyping();
        if (d.success) {
          var txt = d.answer;
          if (d.retrieved_docs && d.retrieved_docs.length > 0) {
            txt += '\n\n📚 参考来源:';
            d.retrieved_docs.forEach(function (doc, i) {
              txt += '\n[' + (i + 1) + '] 相似度 ' + (doc.score * 100).toFixed(1) + '%';
            });
          }
          var meta = '模型: ' + d.model + ' | 检索: ' + d.retrieval_count +
                     '条 | ' + d.latency_ms + 'ms';
          MA.addMsg('ragMessages', 'assistant', txt, meta);
        } else {
          MA.addMsg('ragMessages', 'assistant', '⚠ ' + (d.error || '查询失败'));
        }
      })
      .catch(function (e) {
        MA.hideTyping();
        MA.addMsg('ragMessages', 'assistant', '❌ ' + e.message);
      })
      .finally(function () { ragSendBtn.disabled = false; ragInput.focus(); });
  }

  // ====== 文档上传→自动入库 ======
  ragUploadBtn.addEventListener('click', function () { ragFileInput.click(); });
  ragFileInput.addEventListener('change', function () {
    var file = ragFileInput.files[0]; if (!file) return;
    var fd = new FormData(); fd.append('file', file);
    fetch(MA.API_BASE + '/api/upload/document', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (ud) {
        if (!ud.success) { MA.showToast('上传失败', 'error'); return; }
        return fetch(MA.API_BASE + '/api/rag/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: ud.filename }),
        });
      })
      .then(function (r) {
        if (!r) return;
        return r.json();
      })
      .then(function (id) {
        if (!id) return;
        if (id.success) { MA.showToast('入库成功! ' + id.chunks + ' 块', 'success'); loadStats(); }
        else MA.showToast('入库失败: ' + id.message, 'error');
      })
      .catch(function (e) { MA.showToast('操作失败: ' + e.message, 'error'); })
      .finally(function () { ragFileInput.value = ''; });
  });

  // ====== 批量导入（knowledge 目录下所有文档） ======
  ragBatchBtn.addEventListener('click', function () {
    ragBatchBtn.disabled = true; ragBatchBtn.textContent = '⏳...';
    fetch(MA.API_BASE + '/api/rag/ingest/batch', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.success) { MA.showToast('导入: ' + d.files_processed + '文件 ' + d.total_chunks + '块', 'success'); loadStats(); }
        else MA.showToast(d.message, 'error');
      })
      .catch(function (e) { MA.showToast('失败: ' + e.message, 'error'); })
      .finally(function () { ragBatchBtn.disabled = false; ragBatchBtn.textContent = '📂 批量导入'; });
  });

  ragSendBtn.addEventListener('click', sendRag);
  ragInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendRag(); });

})();

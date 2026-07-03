/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * RAG 知识检索模块 —— 上传文档扩充知识库 + 基于知识库的智能问答
 */
// ====== DOM 元素 ======
const ragInput = document.getElementById('ragInput');           // 问题输入
const ragSendBtn = document.getElementById('ragSendBtn');       // 检索按钮
const ragFileInput = document.getElementById('ragFileInput');   // 文档上传
const ragUploadBtn = document.getElementById('ragUploadBtn');   // 上传按钮
const ragBatchBtn = document.getElementById('ragBatchBtn');     // 批量导入

// ====== 知识库统计 ======
async function loadStats() {
    try {
        const r = await fetch(API_BASE + '/api/rag/stats');
        const d = await r.json();
        document.getElementById('ragDocCount').textContent = d.document_count || 0;
    } catch { document.getElementById('ragDocCount').textContent = '?'; }
}
loadStats();  // 页面加载时查询

// ====== RAG 检索问答 ======
async function sendRag() {
    const q = ragInput.value.trim();
    if (!q) return;

    addMsg('ragMessages', 'user', q);
    ragInput.value = ''; ragSendBtn.disabled = true;
    showTyping('ragMessages');

    try {
        const r = await fetch(API_BASE + '/api/rag/query', {   // 调用 RAG API
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q, top_k: 5 })     // 检索 5 条最相关文档
        });
        const d = await r.json(); hideTyping();

        if (d.success) {
            let txt = d.answer;
            if (d.retrieved_docs && d.retrieved_docs.length > 0) {
                txt += '\n\n📚 参考来源:';
                d.retrieved_docs.forEach((doc, i) => {          // 显示检索到的文档
                    txt += '\n[' + (i + 1) + '] 相似度 ' + (doc.score * 100).toFixed(1) + '%';
                });
            }
            const meta = '模型: ' + d.model + ' | 检索: ' + d.retrieval_count +
                         '条 | ' + d.latency_ms + 'ms';
            addMsg('ragMessages', 'assistant', txt, meta);
        } else {
            addMsg('ragMessages', 'assistant', '⚠ ' + (d.error || '查询失败'));
        }
    } catch (e) {
        hideTyping();
        addMsg('ragMessages', 'assistant', '❌ ' + e.message);
    } finally { ragSendBtn.disabled = false; ragInput.focus(); }
}

// ====== 文档上传→自动入库 ======
ragUploadBtn.addEventListener('click', () => ragFileInput.click());
ragFileInput.addEventListener('change', async () => {
    const file = ragFileInput.files[0]; if (!file) return;
    const fd = new FormData(); fd.append('file', file);
    try {
        // Step1: 上传文件
        const u = await fetch(API_BASE + '/api/upload/document', { method: 'POST', body: fd });
        const ud = await u.json();
        if (!ud.success) { showToast('上传失败', 'error'); return; }
        // Step2: 入库到向量数据库
        const i = await fetch(API_BASE + '/api/rag/ingest', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: ud.filename })
        });
        const id = await i.json();
        if (id.success) { showToast('入库成功! ' + id.chunks + ' 块', 'success'); loadStats(); }
        else showToast('入库失败: ' + id.message, 'error');
    } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
    finally { ragFileInput.value = ''; }
});

// ====== 批量导入（knowledge 目录下所有文档） ======
ragBatchBtn.addEventListener('click', async () => {
    ragBatchBtn.disabled = true; ragBatchBtn.textContent = '⏳...';
    try {
        const r = await fetch(API_BASE + '/api/rag/ingest/batch', { method: 'POST' });
        const d = await r.json();
        if (d.success) { showToast('导入: ' + d.files_processed + '文件 ' + d.total_chunks + '块', 'success'); loadStats(); }
        else showToast(d.message, 'error');
    } catch (e) { showToast('失败: ' + e.message, 'error'); }
    finally { ragBatchBtn.disabled = false; ragBatchBtn.textContent = '📂 批量导入'; }
});

ragSendBtn.addEventListener('click', sendRag);
ragInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendRag(); });

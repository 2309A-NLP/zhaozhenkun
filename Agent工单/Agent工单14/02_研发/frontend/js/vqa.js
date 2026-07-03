/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * VQA 视觉问答模块 —— 需要先上传影像才能提问
 */
const vqaInput = document.getElementById('vqaInput');       // 问题输入框
const vqaSendBtn = document.getElementById('vqaSendBtn');   // 发送按钮

async function sendVqa() {
    const q = vqaInput.value.trim();                        // 获取问题文本
    if (!q) return;                                          // 空消息忽略

    if (!state.uploadedImage) {                              // 没有上传影像则提示
        showToast('请先上传医学影像', 'error'); return;
    }

    addMsg('vqaMessages', 'user', q);                        // 显示用户问题
    vqaInput.value = ''; vqaSendBtn.disabled = true;
    showTyping('vqaMessages');                               // 加载动画

    try {
        const r = await fetch(API_BASE + '/api/vqa/ask', {   // 调用后端 VQA API
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_filename: state.uploadedImage.filename, // 已上传的图片
                question: q                                    // 用户问题
            })
        });
        const d = await r.json(); hideTyping();

        const meta = '模型: ' + (d.model || '?') + ' | ' +
                     (d.latency_ms || 0) + 'ms | Token: ' +
                     (d.usage?.prompt_tokens || 0) + '+' +
                     (d.usage?.completion_tokens || 0);       // 显示模型和耗时
        addMsg('vqaMessages', 'assistant',
               d.success ? d.answer : '⚠ ' + d.error, meta);  // 显示 AI 回答或错误
    } catch (e) {
        hideTyping();
        addMsg('vqaMessages', 'assistant', '❌ 请求失败: ' + e.message);
    } finally { vqaSendBtn.disabled = false; vqaInput.focus(); }
}

vqaSendBtn.addEventListener('click', sendVqa);
vqaInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendVqa(); });

// 影像上传完成后由 app.js 调用，激活输入框
function onVqaReady() {
    vqaInput.disabled = false; vqaSendBtn.disabled = false;
    vqaInput.placeholder = '输入问题...'; vqaInput.focus();
}

/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理/健康咨询/影像分析 V1.0
 * 健康助理模块 —— 自动识别挂号/咨询意图，路由到对应 API
 */
// ====== DOM 元素 ======
const asstInput = document.getElementById('asstInput');   // 输入框
const asstSendBtn = document.getElementById('asstSendBtn'); // 发送按钮

// ====== 核心：发送消息 ======
async function sendAsst() {
    const q = asstInput.value.trim();
    if (!q) return;  // 空消息忽略

    // 显示用户消息
    addMsg('asstMessages', 'user', q);
    asstInput.value = '';
    asstSendBtn.disabled = true;
    showTyping('asstMessages');  // 显示"正在输入..."动画

    // 意图路由：挂号相关 → registration API，其他 → consultation API
    const isReg = /挂号|号源|预约|取消|坐诊|挂.*号|号源|有.*号|哪.*天|什么科|哪个科|挂.*科|科室|排班|还有.*号|可以.*挂/.test(q);
    const url = isReg ? API_BASE + '/api/registration/chat'
                      : API_BASE + '/api/consultation/chat';

    try {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: q })
        });
        const d = await r.json();
        hideTyping();

        // 提取回复文本（兼容不同 API 返回字段名）
        const text = d.reply || d.answer || d.error || '无响应';
        const meta = (d.model ? '模型: ' + d.model + ' ' : '') +
                     (d.latency_ms ? ' | ' + d.latency_ms + 'ms' : '');
        addMsg('asstMessages', 'assistant', text, meta);  // 显示 AI 回复

    } catch (e) {
        hideTyping();
        addMsg('asstMessages', 'assistant', '❌ 网络错误: ' + e.message);
    } finally {
        asstSendBtn.disabled = false;
        asstInput.focus();  // 自动聚焦输入框
    }
}

// ====== 事件绑定 ======
asstSendBtn.addEventListener('click', sendAsst);
asstInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendAsst();  // 回车发送
});

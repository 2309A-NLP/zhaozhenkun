/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
 * 高德地图模块 —— 医院位置相关：出行/住宿/餐饮查询
 */
// ====== DOM 元素 ======
const mapInput = document.getElementById('mapInput');
const mapSendBtn = document.getElementById('mapSendBtn');
const mapQuickBtns = document.querySelectorAll('.map-quick-btn');

// ====== 快捷查询按钮 ======
mapQuickBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const q = btn.dataset.query;
        if (q) {
            mapInput.value = q;
            sendMapQuery();
        }
    });
});

// ====== 发送地图查询 ======
async function sendMapQuery() {
    const q = mapInput.value.trim();
    if (!q) return;

    addMsg('mapMessages', 'user', q);
    mapInput.value = '';
    mapSendBtn.disabled = true;
    showTyping('mapMessages');

    try {
        const r = await fetch(API_BASE + '/api/map/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: q })
        });
        const d = await r.json();
        hideTyping();

        const text = d.reply || d.error || '服务暂时不可用';
        const meta = (d.latency_ms ? d.latency_ms + 'ms' : '');
        addMsg('mapMessages', 'assistant', text, meta);

    } catch (e) {
        hideTyping();
        addMsg('mapMessages', 'assistant', '❌ 网络错误: ' + e.message);
    } finally {
        mapSendBtn.disabled = false;
        mapInput.focus();
    }
}

// ====== 事件绑定 ======
mapSendBtn.addEventListener('click', sendMapQuery);
mapInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendMapQuery();
});

// ====== 在健康助理中自动识别地图相关意图 ======
// 扩展原有的 sendAsst 函数（在 assistant.js 中），拦截地图类问题路由到 /api/map/chat
const _origSendAsst = window.sendAsst;
if (typeof _origSendAsst === 'function') {
    window.sendAsst = function() {
        const q = (document.getElementById('asstInput') || {}).value || '';
        // 检测是否是地图相关查询
        const isMap = /怎么去|怎么走|路线|附近|周边|酒店|住宿|吃饭|餐厅|餐饮|地铁|公交|打车|导航|地址|在哪|位置|多远|几公里|天气|出行|地图/.test(q);
        if (isMap) {
            // 切到地图 Tab 处理
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            const mapTab = document.querySelector('[data-tab="map"]');
            if (mapTab) mapTab.classList.add('active');
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            const mapPanel = document.getElementById('mapPanel');
            if (mapPanel) mapPanel.classList.add('active');

            const mapInput = document.getElementById('mapInput');
            const asstInput = document.getElementById('asstInput');
            if (mapInput && asstInput) {
                mapInput.value = asstInput.value;
                asstInput.value = '';
                sendMapQuery();
            }
            return;
        }
        _origSendAsst();
    };
}

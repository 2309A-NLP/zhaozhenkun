// ==========================================================
// 小家记账 · AI 智能体 — 前端逻辑
// ==========================================================

const chatBox = document.getElementById('chat-box');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const refreshBtn = document.getElementById('refresh-btn');
const clearBtn = document.getElementById('clear-chat');
const statIncome = document.getElementById('stat-income');
const statExpense = document.getElementById('stat-expense');
const statBalance = document.getElementById('stat-balance');
const statCount = document.getElementById('stat-count');
const recordsTableBody = document.querySelector('#records-table tbody');
const todayDate = document.getElementById('today-date');

// ==========================================================
// 初始化
// ==========================================================
function init() {
    // 显示今天日期
    const now = new Date();
    const weekMap = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    todayDate.textContent =
        `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekMap[now.getDay()]}`;

    // 加载欢迎语
    fetchWelcome();

    // 加载统计数据
    loadRecords();

    // 绑定事件
    bindEvents();

    // 自动聚焦输入框
    messageInput.focus();
}

// ==========================================================
// 欢迎语
// ==========================================================
async function fetchWelcome() {
    try {
        const res = await fetch('/api/welcome');
        if (!res.ok) return;
        const data = await res.json();
        // 替换第一条 bot 消息
        const firstBot = chatBox.querySelector('.msg-row.bot .msg-content');
        if (firstBot) {
            firstBot.textContent = data.reply;
        }
    } catch (e) {
        // 静默失败，保留默认文案
    }
}

// ==========================================================
// 消息操作
// ==========================================================
function appendMessage(role, text) {
    const row = document.createElement('div');
    row.className = `msg-row ${role}`;

    // 头像
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    // 气泡
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';

    const content = document.createElement('div');
    content.className = 'msg-content';
    content.textContent = text;

    const time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = formatTime(new Date());

    bubble.appendChild(content);
    bubble.appendChild(time);
    row.appendChild(avatar);
    row.appendChild(bubble);
    chatBox.appendChild(row);

    // 平滑滚动到底部
    chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });
}

function formatTime(date) {
    const h = date.getHours().toString().padStart(2, '0');
    const m = date.getMinutes().toString().padStart(2, '0');
    return `${h}:${m}`;
}

async function sendMessage(message) {
    const text = message.trim();
    if (!text) return;

    appendMessage('user', text);
    messageInput.value = '';
    messageInput.focus();

    // 显示输入中动画
    const thinkingRow = addThinkingIndicator();
    chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const result = await response.json();

        // 移除输入中动画
        removeThinkingIndicator(thinkingRow);

        appendMessage('bot', result.reply || '没有返回结果');

        // 刷新数据
        loadRecords();
    } catch (e) {
        removeThinkingIndicator(thinkingRow);
        appendMessage('bot', '⚠️ 网络请求失败，请稍后重试');
    }
}

// ==========================================================
// 输入中动画
// ==========================================================
function addThinkingIndicator() {
    const row = document.createElement('div');
    row.className = 'msg-row bot thinking-row';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    bubble.innerHTML =
        '<div class="thinking-dots">' +
        '<span class="dot"></span>' +
        '<span class="dot"></span>' +
        '<span class="dot"></span>' +
        '</div>';

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatBox.appendChild(row);
    return row;
}

function removeThinkingIndicator(row) {
    if (row && row.parentNode) {
        row.remove();
    }
}

// ==========================================================
// 数据面板
// ==========================================================
async function loadRecords() {
    try {
        const response = await fetch('/api/records');
        const result = await response.json();
        const records = result.records || [];

        updateStats(records);
        renderTable(records);
    } catch (e) {
        console.error('加载数据失败', e);
    }
}

function updateStats(records) {
    const now = new Date();
    const thisMonth = `${now.getFullYear()}-${(now.getMonth() + 1)
        .toString()
        .padStart(2, '0')}`;

    const monthRecords = records.filter(r =>
        (r.record_date || '').startsWith(thisMonth)
    );

    let income = 0, expense = 0;
    monthRecords.forEach(r => {
        if (r.action_type === '收入') {
            income += r.amount || 0;
        } else {
            expense += r.amount || 0;
        }
    });

    statIncome.textContent = `¥${income.toFixed(0)}`;
    statExpense.textContent = `¥${expense.toFixed(0)}`;
    statBalance.textContent = `¥${(income - expense).toFixed(0)}`;
    statCount.textContent = `${records.length} 笔`;

    // 结余颜色
    const balance = income - expense;
    statBalance.style.color = balance >= 0 ? 'var(--income)' : 'var(--expense)';
}

function renderTable(records) {
    recordsTableBody.innerHTML = '';

    if (records.length === 0) {
        recordsTableBody.innerHTML = `
            <tr class="empty-row">
                <td colspan="6">
                    <div class="empty-state">
                        <span class="empty-icon">📭</span>
                        <span>暂无数据，开始记账吧</span>
                    </div>
                </td>
            </tr>`;
        return;
    }

    // 按日期倒序
    const sorted = [...records].sort((a, b) =>
        (b.record_date || '').localeCompare(a.record_date || '')
    );

    sorted.forEach(r => {
        const isIncome = r.action_type === '收入';
        const badgeClass = isIncome ? 'badge-income' : 'badge-expense';
        const amountClass = isIncome ? 'amount-income' : 'amount-expense';
        const sign = isIncome ? '+' : '-';
        const actionLabel = isIncome ? '收入' : '支出';

        // 格式化日期
        let dateDisplay = r.record_date || '';
        const parts = dateDisplay.split('-');
        if (parts.length === 3) {
            dateDisplay = `${parts[0]}年${parts[1]}月${parts[2]}日`;
        }

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${dateDisplay}</td>
            <td>${escapeHtml(r.member || '')}</td>
            <td><span class="${badgeClass}">${actionLabel}</span></td>
            <td>${escapeHtml(r.category || '')}</td>
            <td>${escapeHtml(r.item_name || '')}</td>
            <td class="${amountClass}">${sign}${(r.amount || 0).toFixed(0)}元</td>
        `;
        recordsTableBody.appendChild(tr);
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ==========================================================
// 事件绑定
// ==========================================================
function bindEvents() {
    // 发送按钮
    sendBtn.addEventListener('click', () => sendMessage(messageInput.value));

    // 回车发送
    messageInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(messageInput.value);
        }
    });

    // 刷新按钮
    refreshBtn.addEventListener('click', loadRecords);

    // 清空聊天
    clearBtn.addEventListener('click', () => {
        const firstBot = chatBox.querySelector('.msg-row.bot');
        chatBox.innerHTML = '';
        if (firstBot) chatBox.appendChild(firstBot);
    });

    // 快捷操作按钮
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            sendMessage(chip.dataset.msg);
        });
    });
}

// ==========================================================
// 启动
// ==========================================================
document.addEventListener('DOMContentLoaded', init);

// ==========================================================
// SchedulePro · Frontend
// ==========================================================

const messages = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const refreshBtn = document.getElementById('refreshBtn');
const clearBtn = document.getElementById('clearBtn');
const recordsTable = document.getElementById('recordsTable');
const toastContainer = document.getElementById('toastContainer');
const statToday = document.getElementById('stat-today');
const statTotal = document.getElementById('stat-total');

// ==========================================================
// Init
// ==========================================================
async function init() {
    await loadWelcome();
    await loadRecords();
    bindEvents();
    input.focus();
    setInterval(pollNotifications, 5000);
    setInterval(loadRecords, 30000);
}

// ==========================================================
// Messages
// ==========================================================
function addMsg(text, type) {
    const row = document.createElement('div');
    row.className = 'msg-row ' + type;

    const ava = document.createElement('div');
    ava.className = 'avatar';
    if (type === 'you') ava.textContent = 'P';
    else if (type === 'notify') ava.textContent = '!';
    else ava.textContent = 'AI';

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const content = document.createElement('div');
    content.textContent = text;

    const ts = document.createElement('div');
    ts.className = 'ts';
    ts.textContent = new Date().toLocaleTimeString('zh-CN', {hour:'2-digit', minute:'2-digit'});

    bubble.appendChild(content);
    bubble.appendChild(ts);
    row.appendChild(ava);
    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTo({top: messages.scrollHeight, behavior: 'smooth'});
}

function addThinking() {
    const row = document.createElement('div');
    row.className = 'msg-row ai thinking';
    const ava = document.createElement('div');
    ava.className = 'avatar';
    ava.textContent = 'AI';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = '<div class="dots"><span></span><span></span><span></span></div>';
    row.appendChild(ava);
    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTo({top: messages.scrollHeight, behavior: 'smooth'});
    return row;
}

function removeThinking(row) {
    if (row && row.parentNode) row.remove();
}

// ==========================================================
// Send
// ==========================================================
async function send(msg) {
    const text = (msg || input.value).trim();
    if (!text) return;
    if (!msg) input.value = '';

    addMsg(text, 'you');
    const thinkingRow = addThinking();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text}),
        });
        const data = await res.json();
        removeThinking(thinkingRow);
        addMsg(data.reply || '已收到。', 'ai');
        await loadRecords();
    } catch (e) {
        removeThinking(thinkingRow);
        addMsg('Network error. Please try again.', 'ai');
    }
}

// ==========================================================
// Welcome
// ==========================================================
async function loadWelcome() {
    try {
        const res = await fetch('/api/welcome');
        const data = await res.json();
        addMsg(data.reply || 'Welcome.', 'ai');
    } catch (e) {
        addMsg('Hello. I am your schedule assistant. Send me a message like "Meeting at 5pm" to get started.', 'ai');
    }
}

// ==========================================================
// Records
// ==========================================================
async function loadRecords() {
    try {
        const res = await fetch('/api/records');
        const data = await res.json();
        const records = data.records || [];
        updateStats(records);
        renderTable(records);
    } catch (e) {
        console.error('Failed to load records', e);
    }
}

function updateStats(records) {
    const today = new Date().toISOString().slice(0, 10);
    const todayCount = records.filter(r => r.enabled === 1 && r.schedule_date === today).length;
    const activeCount = records.filter(r => r.enabled === 1).length;
    statToday.textContent = todayCount;
    statTotal.textContent = activeCount;
}

function renderTable(records) {
    const tbody = recordsTable.querySelector('tbody');
    tbody.innerHTML = '';

    const active = records.filter(r => r.enabled === 1);
    if (!active.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="5"><div class="empty-state">No schedules yet</div></td></tr>';
        return;
    }

    const sorted = [...active].sort((a, b) => {
        const da = (a.schedule_date || '9999') + (a.schedule_time || '99:99');
        const db = (b.schedule_date || '9999') + (b.schedule_time || '99:99');
        return da.localeCompare(db);
    });

    sorted.forEach(r => {
        const tr = document.createElement('tr');

        let date = r.schedule_date || '-';
        const parts = date.split('-');
        if (parts.length === 3) date = `${parts[1]}/${parts[2]}`;

        let repeat = '-';
        if (r.repeat_rule === 'daily') repeat = 'Daily';
        else if (r.repeat_rule === 'weekly') repeat = r.repeat_detail || 'Weekly';
        else if (r.repeat_rule === 'monthly') repeat = `Monthly ${r.repeat_detail || ''}`;

        const hasRepeat = r.repeat_rule && r.repeat_rule !== 'none';

        tr.innerHTML = `
            <td>${esc(date)}</td>
            <td>${esc(r.schedule_time || '')}</td>
            <td>${esc(r.content || '')}</td>
            <td>${hasRepeat ? `<span class="badge-repeat">${esc(repeat)}</span>` : `<span class="badge-none">-</span>`}</td>
            <td><span class="badge-active">Active</span></td>
        `;
        tbody.appendChild(tr);
    });
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// ==========================================================
// Notifications
// ==========================================================
async function pollNotifications() {
    try {
        const res = await fetch('/api/notifications');
        const data = await res.json();
        if (data.notifications && data.notifications.length) {
            for (const n of data.notifications) {
                addMsg('REMINDER: ' + n.reminder, 'notify');
                showToast(n.reminder);
            }
        }
    } catch (e) { /* ignore */ }
}

function showToast(text) {
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = text;
    toastContainer.appendChild(el);
    setTimeout(() => {
        el.classList.add('out');
        el.addEventListener('animationend', () => el.remove());
    }, 5000);
    el.addEventListener('click', () => {
        el.classList.add('out');
        el.addEventListener('animationend', () => el.remove());
    });
}

// ==========================================================
// Events
// ==========================================================
function bindEvents() {
    sendBtn.addEventListener('click', () => send());
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    });
    refreshBtn.addEventListener('click', loadRecords);
    clearBtn.addEventListener('click', () => {
        const first = messages.querySelector('.msg-row');
        messages.innerHTML = '';
        if (first) messages.appendChild(first);
    });
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => send(chip.dataset.msg));
    });
}

document.addEventListener('DOMContentLoaded', init);

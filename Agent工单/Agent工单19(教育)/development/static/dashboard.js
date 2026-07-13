const dashboardData = window.dashboardData || {};
const trendPoints = dashboardData.trend_points || [];
const studentSelect = document.getElementById('studentSelect');
const themeToggle = document.getElementById('themeToggle');
const importScoreButton = document.getElementById('importScoreButton');
const submitPracticeButton = document.getElementById('submitPracticeButton');
const practiceResult = document.getElementById('practiceResult');
const chartTooltip = document.getElementById('chartTooltip');

function applyTheme() {
    const theme = localStorage.getItem('dashboard-theme') || 'light';
    document.body.classList.toggle('dark', theme === 'dark');
}

function toggleTheme() {
    const nextTheme = document.body.classList.contains('dark') ? 'light' : 'dark';
    localStorage.setItem('dashboard-theme', nextTheme);
    applyTheme();
}

function redirectStudent() {
    const studentId = studentSelect.value;
    window.location.href = `/?student_id=${studentId}`;
}

function buildLinePath(points, width, height, padding) {
    const maxValue = 100;
    const stepX = (width - padding * 2) / Math.max(points.length - 1, 1);
    return points.map((point, index) => {
        const x = padding + index * stepX;
        const y = height - padding - ((point.score / maxValue) * (height - padding * 2));
        return { ...point, x, y };
    });
}

function renderTrendChart() {
    const svg = document.getElementById('trendChart');
    if (!svg || !trendPoints.length) {
        return;
    }
    const width = 720;
    const height = 240;
    const padding = 24;
    const mapped = buildLinePath(trendPoints, width, height, padding);
    const path = mapped.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
    const area = `${path} L ${mapped[mapped.length - 1].x} ${height - padding} L ${mapped[0].x} ${height - padding} Z`;
    const guides = [20, 40, 60, 80].map(value => {
        const y = height - padding - ((value / 100) * (height - padding * 2));
        return `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" stroke="rgba(148,163,184,0.18)" stroke-dasharray="4 6" />`;
    }).join('');
    const circles = mapped.map(point => `<circle class="chart-point" cx="${point.x}" cy="${point.y}" r="6" fill="#5b8cff" data-label="${point.label}" data-score="${point.score}" />`).join('');
    const labels = mapped.map(point => `<text x="${point.x}" y="${height - 8}" text-anchor="middle" fill="currentColor" font-size="12">${point.label}</text>`).join('');
    svg.innerHTML = `${guides}<path d="${area}" fill="url(#trendGradient)" opacity="0.2"></path><path d="${path}" fill="none" stroke="#5b8cff" stroke-width="3" stroke-linecap="round"></path>${circles}${labels}<defs><linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#7a5af8"></stop><stop offset="100%" stop-color="#14b8a6"></stop></linearGradient></defs>`;
    svg.querySelectorAll('.chart-point').forEach(point => {
        point.addEventListener('mouseenter', event => {
            chartTooltip.innerHTML = `${event.target.dataset.label}<br>${event.target.dataset.score} 分`;
            chartTooltip.classList.remove('hidden');
        });
        point.addEventListener('mousemove', event => {
            const bounds = svg.getBoundingClientRect();
            chartTooltip.style.left = `${event.clientX - bounds.left}px`;
            chartTooltip.style.top = `${event.clientY - bounds.top - 12}px`;
        });
        point.addEventListener('mouseleave', () => chartTooltip.classList.add('hidden'));
    });
}

function collectAnswers() {
    const cards = document.querySelectorAll('.practice-card');
    return Array.from(cards).map(card => {
        const questionId = card.dataset.questionId;
        const selected = card.querySelector('input[type="radio"]:checked');
        return { question_id: Number(questionId), chosen_answer: selected ? selected.value : '' };
    });
}

async function submitPractice() {
    const answers = collectAnswers();
    if (answers.some(item => !item.chosen_answer)) {
        practiceResult.textContent = '请先完成全部推荐练习题再提交。';
        practiceResult.classList.remove('hidden');
        return;
    }
    const response = await fetch('/api/practice/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: Number(studentSelect.value), answers }),
    });
    const result = await response.json();
    practiceResult.innerHTML = `本次共完成 ${result.total} 题，答对 ${result.correct} 题，答错 ${result.wrong} 题。系统已更新学习画像，并将错题写入 AIGC 错题本。`;
    practiceResult.classList.remove('hidden');
    setTimeout(() => window.location.reload(), 900);
}

async function importHistoricalScore() {
    const value = window.prompt('请输入历史成绩（0-100）', '78');
    if (value === null) {
        return;
    }
    const score = Number(value);
    if (Number.isNaN(score)) {
        return;
    }
    await fetch('/api/portrait/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: Number(studentSelect.value), score }),
    });
    window.location.reload();
}

applyTheme();
renderTrendChart();
studentSelect.addEventListener('change', redirectStudent);
themeToggle.addEventListener('click', toggleTheme);
importScoreButton.addEventListener('click', importHistoricalScore);
submitPracticeButton.addEventListener('click', submitPractice);

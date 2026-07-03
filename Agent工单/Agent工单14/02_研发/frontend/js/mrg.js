/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
 * MRG 医疗报告生成模块 —— 基于上传的影像自动生成结构化诊断报告
 */
const mrgGenerateBtn = document.getElementById('mrgGenerateBtn'); // 生成按钮
const mrgClinicalInfo = document.getElementById('mrgClinicalInfo'); // 临床信息输入
const mrgOutput = document.getElementById('mrgOutput');            // 报告展示区
const mrgActions = document.getElementById('mrgActions');          // 打印/下载按钮
let currentReport = '';  // 当前报告内容（供打印/下载用）

async function generateReport() {
    if (!state.uploadedImage) { showToast('请先上传影像', 'error'); return; }

    mrgGenerateBtn.disabled = true;
    mrgGenerateBtn.textContent = '⏳ 生成中...';
    mrgOutput.innerHTML = '<p class="placeholder">AI 正在分析影像...</p>';  // 加载状态

    const ci = mrgClinicalInfo.value.trim();  // 临床信息（可选）

    try {
        const r = await fetch(API_BASE + '/api/mrg/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_filename: state.uploadedImage.filename, // 已上传的影像
                clinical_info: ci                              // 临床描述
            })
        });
        const d = await r.json();

        if (d.success) {
            currentReport = d.report;                          // 保存报告
            // 渲染报告：将【xxx】标题格式化为 HTML
            mrgOutput.innerHTML = '<div class="report-content">' +
                d.report.replace(/【(.+?)】/g, '<h3>【$1】</h3>')  // 标题加粗
                         .replace(/\n/g, '<br>') + '</div>';         // 换行
            mrgActions.style.display = 'flex';                 // 显示打印/下载
            mrgOutput.insertAdjacentHTML('beforeend',
                '<div class="msg-meta">模型: ' + d.model + ' | ' + d.latency_ms + 'ms</div>');
        } else {
            mrgOutput.innerHTML = '<p style="color:red">⚠ ' + (d.error || '生成失败') + '</p>';
        }
    } catch (e) {
        mrgOutput.innerHTML = '<p style="color:red">❌ ' + e.message + '</p>';
    } finally {
        mrgGenerateBtn.disabled = false;
        mrgGenerateBtn.textContent = '🩺 生成诊断报告';
    }
}

function formatReport(r) { return r.replace(/【(.+?)】/g, '<h3>【$1】</h3>').replace(/\n/g, '<br>'); }

// 打印报告：打开新窗口→写入格式化HTML→触发打印
function printReport() {
    const w = window.open('', '_blank', 'width=800,height=600');
    w.document.write('<html><head><title>诊断报告</title>' +
        '<style>body{font-family:SimSun;padding:30px;line-height:2}h3{color:#1e40af}</style></head>' +
        '<body><h1>影像诊断报告</h1>' + formatReport(currentReport) +
        '<hr><small>AI生成仅供参考 | 工单: 医疗智能体 V1.0</small></body></html>');
    w.document.close(); setTimeout(() => w.print(), 500);
}

// 下载报告：Blob → 下载链接
function downloadReport() {
    const b = new Blob([currentReport], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(b);
    a.download = '诊断报告_' + new Date().toISOString().slice(0, 10) + '.txt'; a.click();
}

mrgGenerateBtn.addEventListener('click', generateReport);
function onMrgReady() { mrgGenerateBtn.disabled = false; }  // 影像就绪回调

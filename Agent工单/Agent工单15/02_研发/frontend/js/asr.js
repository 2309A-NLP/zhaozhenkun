/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
 * 实时语音识别模块 —— 录音 → WebSocket 实时识别 → 会议纪要
 *
 * 注：本模块需要一个独立的 ASR 面板（含 asrResult/asrRecordBtn/asrStatus/asrSummary）。
 *     在当前的 UI 布局中，语音识别功能由 digital.js 在「数字人」Tab 中处理，
 *     因此如果 asrResult 元素不存在，本模块会自动停用，避免与 digital.js 冲突。
 */
'use strict';

(function () {
  var MA = window.MA;
const asrRecordBtn = document.getElementById('asrRecordBtn');
const asrStatus = document.getElementById('asrStatus');
const asrResult = document.getElementById('asrResult');
const asrSummary = document.getElementById('asrSummary');
const asrTranslateBtn = document.getElementById('asrTranslateBtn');

// 如果核心元素不存在（例如数字人 Tab 已接管），则停用本模块
if (!asrResult && !asrTranslateBtn) {
  // asrRecordBtn 和 asrStatus 被 digital.js 使用，本模块不注册监听
  return;
}

// ====== 全局状态 ======
let ws = null;               // WebSocket 连接
let audioContext = null;     // AudioContext 实例
let stream = null;           // 麦克风流
let processor = null;        // ScriptProcessorNode
let isRecording = false;     // 是否正在录音
let fullTranscript = '';     // 完整转录文本
let pollTimer = null;        // 轮询定时器
let currentTaskId = null;    // 当前后处理任务 ID

// ====== 开始/停止录音 ======
asrRecordBtn.addEventListener('click', function() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

async function startRecording() {
    try {
        // ① 连接后端 WebSocket
        var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        var wsUrl = protocol + '//' + location.host + '/api/asr/ws/realtime';
        ws = new WebSocket(wsUrl);
        ws.binaryType = 'arraybuffer';

        ws.onopen = async function() {
            console.log('✅ WebSocket 已连接');
            // ② 获取麦克风权限
            stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });

            // ③ 创建 AudioContext 并降采样到 16kHz
            audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            var source = audioContext.createMediaStreamSource(stream);

            // ④ 使用 ScriptProcessor 采集 PCM 数据
            processor = audioContext.createScriptProcessor(4096, 1, 1);
            processor.onaudioprocess = function(e) {
                if (!isRecording || ws.readyState !== WebSocket.OPEN) return;
                var input = e.inputBuffer.getChannelData(0);  // Float32 [-1,1]
                // 转为 PCM 16bit
                var pcm = new Int16Array(input.length);
                for (var i = 0; i < input.length; i++) {
                    var s = Math.max(-1, Math.min(1, input[i]));
                    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                ws.send(pcm.buffer);  // 发送二进制音频帧
            };

            source.connect(processor);
            processor.connect(audioContext.destination);

            // ⑤ 更新 UI 状态
            isRecording = true;
            asrRecordBtn.textContent = '⏹ 停止录音';
            asrRecordBtn.style.background = '#dc2626';
            asrStatus.textContent = '🔴 录音中...';
            asrStatus.style.color = '#dc2626';
            asrResult.innerHTML = '<p style="color:#64748b">🎤 正在聆听，请讲话...</p>';
            asrSummary.innerHTML = '';
            fullTranscript = '';
            currentTaskId = null;
        };

        ws.onmessage = function(event) {
            var data = JSON.parse(event.data);
            if (data.type === 'partial') {
                // 中间结果（浅色显示）
                showPartial(data.text);
            } else if (data.type === 'final') {
                // 最终结果（深色显示）
                fullTranscript += data.text;
                showFinal(data.text);
            } else if (data.type === 'done') {
                // 识别完成 → 自动触发后处理
                asrStatus.textContent = '✅ 识别完成，正在生成会议纪要...';
                asrStatus.style.color = '#2563eb';
                if (fullTranscript.trim()) {
                    triggerPostProcess();
                }
            } else if (data.type === 'error') {
                asrStatus.textContent = '❌ 错误: ' + data.message;
                asrStatus.style.color = '#dc2626';
            }
        };

        ws.onerror = function(e) {
            console.error('WebSocket 错误:', e);
            asrStatus.textContent = '❌ 连接失败';
            asrStatus.style.color = '#dc2626';
        };

        ws.onclose = function() {
            console.log('WebSocket 已关闭');
            if (isRecording) stopAudioCapture();
        };

    } catch (e) {
        console.error('启动录音失败:', e);
        asrStatus.textContent = '❌ 麦克风权限被拒绝或不可用';
        asrStatus.style.color = '#dc2626';
    }
}

function stopRecording() {
    // 发送停止信号
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'stop' }));
    }
    stopAudioCapture();
    isRecording = false;
    asrRecordBtn.textContent = '🎙️ 开始录音';
    asrRecordBtn.style.background = '#2563eb';
    asrStatus.textContent = '⏳ 处理中...';
    asrStatus.style.color = '#f59e0b';
}

function stopAudioCapture() {
    if (processor) { processor.disconnect(); processor = null; }
    if (stream) { stream.getTracks().forEach(function(t){ t.stop(); }); stream = null; }
    if (audioContext) { audioContext.close(); audioContext = null; }
    if (ws) { try { ws.close(); } catch(e){} ws = null; }
}

// ====== 显示识别结果 ======
function showPartial(text) {
    var el = document.getElementById('asrPartial') || document.createElement('div');
    el.id = 'asrPartial';
    el.style.cssText = 'color:#94a3b8;font-style:italic;margin:4px 0;font-size:13px';
    el.textContent = text;
    if (!document.getElementById('asrPartial')) {
        asrResult.appendChild(el);
    }
}

function showFinal(text) {
    // 移除中间的 partial
    var partial = document.getElementById('asrPartial');
    if (partial) partial.remove();

    var div = document.createElement('div');
    div.style.cssText = 'margin:3px 0;font-size:14px;line-height:1.6';
    div.textContent = text;
    asrResult.appendChild(div);
    asrResult.scrollTop = asrResult.scrollHeight;
}

// ====== 触发后处理（轮询方式） ======
async function triggerPostProcess() {
    try {
        // ① 创建后处理任务
        var r = await fetch('/api/asr/task/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript: fullTranscript })
        });
        var d = await r.json();
        if (!d.success) { showError('任务创建失败'); return; }

        currentTaskId = d.task_id;
        // ② 每 2 秒轮询结果
        pollTask();
    } catch (e) {
        showError('后处理请求失败: ' + e.message);
    }
}

function pollTask() {
    if (!currentTaskId) return;
    if (pollTimer) clearInterval(pollTimer);

    var count = 0;
    pollTimer = setInterval(async function() {
        count++;
        try {
            var r = await fetch('/api/asr/task/' + currentTaskId);
            var d = await r.json();

            if (d.status === 'done') {
                clearInterval(pollTimer);
                pollTimer = null;
                showSummary(d.result);
                asrStatus.textContent = '✅ 会议纪要已生成';
                asrStatus.style.color = '#16a34a';
            } else if (d.status === 'error') {
                clearInterval(pollTimer);
                pollTimer = null;
                showError('后处理失败: ' + (d.error || '未知错误'));
            } else if (count > 30) {
                // 超时 (60秒)
                clearInterval(pollTimer);
                pollTimer = null;
                showError('后处理超时，请重试');
            } else {
                asrStatus.textContent = '⏳ 后处理中' + '.'.repeat(count % 4);
            }
        } catch (e) {
            clearInterval(pollTimer);
            pollTimer = null;
            showError('轮询请求失败: ' + e.message);
        }
    }, 2000);
}

// ====== 显示会议纪要 ======
function showSummary(result) {
    var html = '<div class="summary-box">';

    // 全文摘要
    if (result.summary) {
        html += '<div class="sum-section"><h4>📝 全文摘要</h4><p>' +
                escapeHtml(result.summary) + '</p></div>';
    }
    // 章节速览
    if (result.chapters) {
        html += '<div class="sum-section"><h4>📑 章节速览</h4><p>' +
                escapeHtml(result.chapters) + '</p></div>';
    }
    // 发言总结
    if (result.speaker_summary) {
        html += '<div class="sum-section"><h4>💬 发言总结</h4><p>' +
                escapeHtml(result.speaker_summary) + '</p></div>';
    }
    // 待办事项
    if (result.todos) {
        html += '<div class="sum-section"><h4>✅ 待办事项</h4><p>' +
                escapeHtml(result.todos) + '</p></div>';
    }
    // 问答对
    if (result.qa) {
        html += '<div class="sum-section"><h4>❓ 问答提取</h4><p>' +
                escapeHtml(result.qa) + '</p></div>';
    }
    // 关键词
    if (result.keywords) {
        html += '<div class="sum-section"><h4>🔑 关键词</h4><p>' +
                escapeHtml(result.keywords) + '</p></div>';
    }

    if (!result.summary && !result.chapters && !result.keywords) {
        html += '<div class="sum-section"><h4>📝 原始分析</h4><pre>' +
                escapeHtml(result.raw || JSON.stringify(result, null, 2)) +
                '</pre></div>';
    }

    html += '</div>';
    asrSummary.innerHTML = html;
}

// ====== 翻译按钮 ======
asrTranslateBtn.addEventListener('click', async function() {
    var text = fullTranscript || '';
    if (!text) { showError('没有可翻译的内容，请先录音'); return; }

    asrTranslateBtn.disabled = true;
    asrTranslateBtn.textContent = '翻译中...';

    try {
        var r = await fetch('/api/asr/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, target_lang: '英文' })
        });
        var d = await r.json();
        if (d.success) {
            var div = document.createElement('div');
            div.style.cssText = 'background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:12px;margin-top:12px';
            div.innerHTML = '<h4 style="margin:0 0 8px;color:#166534">🌐 英文翻译</h4><p style="margin:0;white-space:pre-wrap">' +
                            escapeHtml(d.translation) + '</p>';
            asrSummary.appendChild(div);
        }
    } catch (e) {
        showError('翻译失败: ' + e.message);
    } finally {
        asrTranslateBtn.disabled = false;
        asrTranslateBtn.textContent = '🌐 翻译为英文';
    }
});

// ====== 工具函数 ======
function showError(msg) {
    asrStatus.textContent = '❌ ' + msg;
    asrStatus.style.color = '#dc2626';
    MA.showToast(msg, 'error');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
              .replace(/"/g,'&quot;').replace(/\n/g,'<br>');
}

})();

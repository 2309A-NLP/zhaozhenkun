/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
 * 通义听悟前端 —— 实时语音识别 + 翻译 + 会议纪要
 *
 * 语音识别: WebSocket → 后端 /api/asr/ws/realtime → DashScope paraformer-realtime-v2
 *            (不再使用浏览器内置 SpeechRecognition，避免 Google 服务被墙)
 * 翻译/纪要: 后端 DeepSeek API
 */
'use strict';

(function() {
var recBtn    = document.getElementById('twRecordBtn'),
    pauseBtn  = document.getElementById('twPauseBtn'),
    langSel   = document.getElementById('twLang'),
    statusEl  = document.getElementById('twStatus'),
    transHint = document.getElementById('twTranscriptHint'),
    transArea = document.getElementById('twTranscripts'),
    timerEl   = document.getElementById('twTimer'),
    transTgl  = document.getElementById('twTranslateToggle'),
    targetLang= document.getElementById('twTargetLang'),
    summBtn   = document.getElementById('twSummarizeBtn'),
    clearBtn  = document.getElementById('twClearBtn'),
    summArea  = document.getElementById('twSummaryArea'),
    taskInfo  = document.getElementById('twTaskInfo'),
    modeSel   = document.getElementById('twResultMode')

// ====== 状态 ======
var isRecording = false, isPaused = false,
    ws = null, audioCtx = null, stream = null, processor = null,
    fullText = '', sentenceCount = 0, timerSec = 0, timerId = null,
    pollTimer = null;

// ====== 录音控制 ======
recBtn.addEventListener('click', function() {
    isRecording ? stopRecording() : startRecording();
});

pauseBtn.addEventListener('click', function() {
    if (!isRecording) return;
    isPaused = !isPaused;
    if (isPaused) {
        pauseBtn.textContent = '▶️ 继续';
        pauseBtn.style.background = '#16a34a';
        statusEl.textContent = '⏸️ 已暂停';
        statusEl.style.color = '#f59e0b';
    } else {
        pauseBtn.textContent = '⏸️ 暂停';
        pauseBtn.style.background = '';
        statusEl.textContent = '🔴 录音中...';
        statusEl.style.color = '#dc2626';
    }
});

clearBtn.addEventListener('click', function() {
    fullText = ''; sentenceCount = 0;
    transArea.innerHTML = '';
    transArea.style.display = 'none';
    transHint.style.display = 'block';
    summArea.innerHTML = '<div style="text-align:center;padding:40px 20px;color:#94a3b8"><div style="font-size:36px;margin-bottom:10px">📝</div><div>已清空</div></div>';
    taskInfo.style.display = 'none';
    summBtn.disabled = true;
    timerEl.textContent = '00:00';
});

// ====== 开始录音 (WebSocket → DashScope) ======
async function startRecording() {
    // ① 即时反馈：用户知道点到了
    recBtn.disabled = true;
    recBtn.textContent = '⏳ 连接中...';
    recBtn.style.background = '#f59e0b';
    statusEl.textContent = '⏳ 正在连接语音服务...';
    statusEl.style.color = '#f59e0b';

    try {
        // ② 连接后端 WebSocket ASR
        var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        var wsUrl = protocol + '//' + location.host + '/api/asr/ws/realtime';
        ws = new WebSocket(wsUrl);
        ws.binaryType = 'arraybuffer';

        // 连接超时检测
        var connectTimeout = setTimeout(function() {
            if (!isRecording && ws && ws.readyState !== WebSocket.OPEN) {
                ws.close();
                statusEl.textContent = '❌ 连接超时，请确认后端已启动';
                statusEl.style.color = '#dc2626';
                recBtn.disabled = false;
                recBtn.textContent = '🎙️ 重新开始';
                recBtn.style.background = '#2563eb';
            }
        }, 8000);

        ws.onopen = async function() {
            clearTimeout(connectTimeout);
            statusEl.textContent = '🎤 请允许麦克风权限...';
            statusEl.style.color = '#2563eb';

            try {
                // ③ 获取麦克风
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        sampleRate: 16000,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                    }
                });

                // ④ AudioContext + ScriptProcessor
                audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                var source = audioCtx.createMediaStreamSource(stream);
                processor = audioCtx.createScriptProcessor(4096, 1, 1);
                processor.onaudioprocess = function(e) {
                    if (!isRecording || isPaused || ws.readyState !== WebSocket.OPEN) return;
                    var input = e.inputBuffer.getChannelData(0);
                    var pcm = new Int16Array(input.length);
                    for (var i = 0; i < input.length; i++) {
                        var s = Math.max(-1, Math.min(1, input[i]));
                        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }
                    ws.send(pcm.buffer);
                };
                source.connect(processor);
                processor.connect(audioCtx.destination);

                // ⑤ 🎉 一切就绪，开始录音
                isRecording = true; isPaused = false;
                recBtn.disabled = false;
                recBtn.textContent = '⏹ 停止录音';
                recBtn.style.background = '#dc2626';
                pauseBtn.disabled = false;
                pauseBtn.textContent = '⏸️ 暂停';
                statusEl.textContent = '🔴 正在录音，请说话...';
                statusEl.style.color = '#dc2626';
                transHint.style.display = 'none';
                transArea.style.display = 'block';
                summBtn.disabled = true;
                timerSec = 0; updateTimer();
                timerId = setInterval(updateTimer, 1000);

            } catch (micErr) {
                console.error('麦克风错误:', micErr.name, micErr.message);
                var hint;
                if (micErr.name === 'NotAllowedError' || micErr.name === 'PermissionDeniedError') {
                    hint = '❌ 麦克风被阻止！\n👉 点击地址栏左侧的 🔒 图标 → 麦克风 → 允许\n👉 或输入 chrome://settings/content/microphone 手动允许此站点';
                } else if (micErr.name === 'NotFoundError' || micErr.name === 'DevicesNotFoundError') {
                    hint = '❌ 未检测到麦克风设备，请检查麦克风是否已连接';
                } else if (micErr.name === 'NotReadableError') {
                    hint = '❌ 麦克风被其他程序占用，请关闭其他录音应用后重试';
                } else {
                    hint = '❌ 麦克风不可用: ' + (micErr.message || micErr.name || '未知错误');
                }
                statusEl.textContent = hint;
                statusEl.style.color = '#dc2626';
                statusEl.style.whiteSpace = 'pre-line';
                recBtn.disabled = false;
                recBtn.textContent = '🎙️ 重新开始';
                recBtn.style.background = '#2563eb';
                ws.close();
            }
        };

        ws.onmessage = function(event) {
            var data = JSON.parse(event.data);
            if (data.type === 'partial') {
                updatePartial(data.text);
                // 更新状态栏显示最新文字
                statusEl.textContent = '🔴 ' + data.text.slice(0, 30);
            } else if (data.type === 'final') {
                fullText += (fullText ? '\n' : '') + data.text;
                sentenceCount++;
                var p = transArea.querySelector('.tw-partial');
                if (p) p.remove();
                appendSentence(data.text, timerSec);
                statusEl.textContent = '🔴 第' + sentenceCount + '句已识别';
                if (transTgl.checked && data.text.trim()) {
                    translateAndShow(data.text);
                }
            } else if (data.type === 'done') {
                if (isRecording) stopRecording();
                if (fullText.trim()) {
                    statusEl.textContent = '✅ 录音完成 · ' + sentenceCount + '句 · 可生成纪要';
                    statusEl.style.color = '#16a34a';
                    summBtn.disabled = false;
                } else {
                    statusEl.textContent = '⚠️ 未识别到语音，请重试';
                    statusEl.style.color = '#f59e0b';
                }
            } else if (data.type === 'error') {
                statusEl.textContent = '❌ ' + (data.message || '识别失败，请重试');
                statusEl.style.color = '#dc2626';
                if (isRecording) stopRecording();
            }
        };

        ws.onerror = function(e) {
            clearTimeout(connectTimeout);
            console.error('通义听悟 WebSocket 错误:', e);
            statusEl.textContent = '❌ 无法连接后端服务 (端口' + (location.port || 80) + ')，请确认 python main.py 已启动';
            statusEl.style.color = '#dc2626';
            recBtn.disabled = false;
            recBtn.textContent = '🎙️ 重新开始';
            recBtn.style.background = '#2563eb';
            stopAudio();
        };

        ws.onclose = function() {
            if (isRecording) stopAudio();
        };

    } catch (e) {
        console.error('启动录音失败:', e);
        statusEl.textContent = '❌ 初始化失败: ' + (e.message || '未知错误');
        statusEl.style.color = '#dc2626';
        recBtn.disabled = false;
        recBtn.textContent = '🎙️ 重新开始';
        recBtn.style.background = '#2563eb';
    }
}

// ====== 停止录音 ======
function stopRecording() {
    isRecording = false;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'stop' }));
    }
    if (timerId) { clearInterval(timerId); timerId = null; }
    recBtn.textContent = '🎙️ 开始录音';
    recBtn.style.background = '#2563eb';
    pauseBtn.disabled = true;
    pauseBtn.textContent = '⏸️ 暂停';
    pauseBtn.style.background = '';
    stopAudio();

    if (fullText.trim()) {
        statusEl.textContent = '✅ 录音完成 · ' + sentenceCount + '句';
        statusEl.style.color = '#16a34a';
        summBtn.disabled = false;
    }
}

function stopAudio() {
    if (processor) { processor.disconnect(); processor = null; }
    if (stream) { stream.getTracks().forEach(function(t) { t.stop(); }); stream = null; }
    if (audioCtx) { audioCtx.close(); audioCtx = null; }
    if (ws) { try { ws.close(); } catch(e) {} ws = null; }
}

// ====== 实时转写展示 ======
function appendSentence(text, timeSec) {
    var div = document.createElement('div');
    div.style.cssText = 'padding:6px 0;border-bottom:1px solid #f1f5f9;animation:fadeIn .3s';
    div.innerHTML =
        '<span style="font-size:10px;color:#94a3b8;margin-right:8px;font-family:monospace">' +
        fmtTime(timeSec) + '</span>' +
        '<span style="font-size:13px;color:#1e293b;line-height:1.6">' + esc(text) + '</span>';
    var tl = document.createElement('span');
    tl.className = 'tw-translation';
    tl.style.cssText = 'display:block;font-size:11px;color:#6366f1;margin-top:2px;padding-left:50px';
    div.appendChild(tl);
    transArea.appendChild(div);
    transArea.scrollTop = transArea.scrollHeight;
}

function updatePartial(text) {
    var old = transArea.querySelector('.tw-partial');
    if (old) old.remove();
    if (!text) return;
    var div = document.createElement('div');
    div.className = 'tw-partial';
    div.style.cssText = 'padding:6px 0;border-bottom:1px solid #e0e7ff;opacity:0.7';
    div.innerHTML =
        '<span style="font-size:10px;color:#6366f1;margin-right:8px">实时</span>' +
        '<span style="font-size:13px;color:#6366f1;font-style:italic">' + esc(text) + '</span>';
    transArea.appendChild(div);
    transArea.scrollTop = transArea.scrollHeight;
}

// ====== 翻译 ======
transTgl.addEventListener('change', function() {
    targetLang.style.display = this.checked ? 'inline' : 'none';
});

function translateAndShow(text) {
    var target = targetLang.value || '英文';
    fetch('/api/asr/translate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: text, target_lang: target})
    }).then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.success) {
            var spans = transArea.querySelectorAll('.tw-translation');
            var last = spans[spans.length - 1];
            if (last) last.textContent = d.translation;
        }
    }).catch(function() {});
}

// ====== 生成会议纪要 (支持轮询和回调两种方式) ======
summBtn.addEventListener('click', function() {
    if (!fullText.trim()) return;
    var mode = modeSel ? modeSel.value : 'poll';
    summBtn.disabled = true;
    summBtn.textContent = '⏳ 生成中...';
    summArea.innerHTML = '<div style="text-align:center;padding:20px;color:#64748b">⏳ 正在生成会议纪要 (' + (mode === 'callback' ? '回调模式' : '轮询模式') + ')...</div>';

    if (mode === 'callback') {
        // 回调方式: 创建异步任务 → 轮询结果
        fetch('/api/asr/task/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({transcript: fullText})
        }).then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.success) {
                taskInfo.style.display = 'block';
                taskInfo.innerHTML = '🔄 <b>回调模式</b> · 任务ID: ' + d.task_id + '<br>' +
                    '📡 回调URL: <code>/api/asr/callback</code><br>⏳ 等待后处理...';
                pollTaskResult(d.task_id);
            }
        }).catch(function(e) {
            summArea.innerHTML = '<div style="color:#dc2626">❌ 创建任务失败: ' + e.message + '</div>';
            summBtn.disabled = false; summBtn.textContent = '生成纪要';
        });
    } else {
        // 轮询方式: 直接同步后处理
        fetch('/api/asr/process', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({transcript: fullText})
        }).then(function(r) { return r.json(); })
        .then(function(data) {
            renderSummary(data);
            taskInfo.style.display = 'block';
            taskInfo.innerHTML = '✅ <b>轮询模式</b> · DeepSeek · ' + new Date().toLocaleTimeString();
            summBtn.disabled = false; summBtn.textContent = '生成纪要';
        }).catch(function(e) {
            summArea.innerHTML = '<div style="color:#dc2626">❌ ' + e.message + '</div>';
            summBtn.disabled = false; summBtn.textContent = '生成纪要';
        });
    }
});

function pollTaskResult(taskId) {
    if (pollTimer) clearInterval(pollTimer);
    var count = 0;
    pollTimer = setInterval(function() {
        count++;
        fetch('/api/asr/task/' + taskId).then(function(r) { return r.json(); })
        .then(function(d) {
            if (d.status === 'done') {
                clearInterval(pollTimer); pollTimer = null;
                renderSummary(d.result);
                taskInfo.innerHTML = '✅ <b>回调模式</b> · 完成 · ' + new Date().toLocaleTimeString();
                summBtn.disabled = false; summBtn.textContent = '生成纪要';
            } else if (d.status === 'error') {
                clearInterval(pollTimer); pollTimer = null;
                summArea.innerHTML = '<div style="color:#dc2626">❌ 后处理失败</div>';
                summBtn.disabled = false; summBtn.textContent = '生成纪要';
            } else if (count > 30) {
                clearInterval(pollTimer); pollTimer = null;
                summArea.innerHTML = '<div style="color:#f59e0b">⚠️ 超时</div>';
                summBtn.disabled = false; summBtn.textContent = '生成纪要';
            } else {
                taskInfo.innerHTML = '⏳ <b>回调模式</b> · 等待' + '.'.repeat(count % 4);
            }
        }).catch(function() { clearInterval(pollTimer); pollTimer = null; summBtn.disabled = false; });
    }, 2000);
}

// ====== 渲染纪要（工单要求：说话人分离/全文摘要/章节速览/发言总结/待办/问答/关键词）======
function renderSummary(data) {
    var raw = data.raw || '';
    var html = '<div style="font-size:13px;line-height:1.8">';

    function section(label, icon, bg, titleColor, textColor) {
        // 优先用 parsed 字段，其次从 raw 中提取
        var content = data[label] || data[label.toLowerCase()] || extractSection(raw, label);
        if (!content) return;
        html += '<div style="background:' + bg + ';padding:10px 12px;border-radius:8px;margin-bottom:10px">';
        html += '<div style="font-weight:600;color:' + titleColor + ';margin-bottom:4px">' + icon + ' ' + label + '</div>';
        html += '<div style="color:' + textColor + ';font-size:12px;white-space:pre-wrap">' + esc(content) + '</div></div>';
    }

    // 说话人分离（工单核心要求）
    section('说话人分离', '🗣️', '#fef3c7', '#92400e', '#78350f');

    // 全文摘要
    var summaryText = data.summary || extractSection(raw, '全文摘要');
    if (summaryText) {
        html += '<div style="background:#eff6ff;padding:12px;border-radius:8px;margin-bottom:10px;border-left:4px solid #3b82f6">';
        html += '<div style="font-weight:600;color:#1e40af;margin-bottom:4px">📋 全文摘要</div>';
        html += '<div style="color:#1e3a5f;font-size:13px;white-space:pre-wrap">' + esc(summaryText) + '</div></div>';
    }

    // 章节速览
    section('章节速览', '📑', '#f0fdf4', '#166534', '#14532d');

    // 发言总结
    section('发言总结', '👤', '#fdf2f8', '#9d174d', '#831843');

    // 待办事项
    section('待办事项', '📌', '#fff7ed', '#c2410c', '#9a3412');

    // 问答提取
    section('问答提取', '❓', '#f5f3ff', '#5b21b6', '#4c1d95');

    // 关键词
    var kw = data.keywords || extractSection(raw, '关键词');
    if (kw) {
        html += '<div style="background:#fefce8;padding:10px 12px;border-radius:8px;margin-bottom:10px">';
        html += '<div style="font-weight:600;color:#854d0e;margin-bottom:4px">🔑 关键词</div>';
        html += '<div style="display:flex;flex-wrap:wrap;gap:6px">';
        kw.split(/[,，、\s]+/).filter(Boolean).forEach(function(k) {
            html += '<span style="background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:12px;font-size:11px">' + esc(k.trim()) + '</span>';
        });
        html += '</div></div>';
    }

    if (!raw && !data.summary) {
        html += '<div style="color:#94a3b8;text-align:center;padding:20px">未获取到纪要内容</div>';
    }
    html += '<div style="font-size:10px;color:#94a3b8;text-align:right;margin-top:8px">' +
        '后端: ' + (data.backend || 'DeepSeek') + ' · ' + new Date().toLocaleTimeString() + '</div>';
    html += '</div>';
    summArea.innerHTML = html;
}

function extractSection(raw, label) {
    if (!raw) return '';
    var idx = raw.indexOf(label);
    if (idx < 0) return '';
    var colon = raw.indexOf('：', idx);
    if (colon < 0) colon = raw.indexOf(':', idx);
    if (colon < 0) return '';
    var next = raw.slice(colon + 1).search(/\n\d+[\.\、]/);
    var text;
    if (next > 0) {
        text = raw.slice(colon + 1, colon + 1 + next).trim();
    } else {
        text = raw.slice(colon + 1).trim();
    }
    return text.length > 500 ? text.slice(0, 500) + '...' : text;
}

// ====== 工具函数 ======
function updateTimer() { timerSec++; timerEl.textContent = fmtTime(timerSec); }
function fmtTime(s) { var m = Math.floor(s / 60), sec = s % 60; return (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec; }
function esc(s) { return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

})();

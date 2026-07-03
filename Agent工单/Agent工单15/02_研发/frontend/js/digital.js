/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
 * 数字人模块 —— 照片上传 + 语音对话 + TTS + SadTalker 唇形同步视频
 */
'use strict';

(function() {
// ====== DOM 引用 ======
var uploadBox  = document.getElementById('avaUploadBox'),
    uploadInp  = document.getElementById('avaUpload'),
    uploadHint = document.getElementById('avaUploadHint'),
    preview    = document.getElementById('avaPreview'),
    avaVideo   = document.getElementById('avaVideo'),
    avaStatus  = document.getElementById('avaStatus'),
    chatArea   = document.getElementById('asrChatArea'),
    recBtn     = document.getElementById('asrRecordBtn'),
    recStatus  = document.getElementById('asrStatus'),
    recSumm    = document.getElementById('asrSummary'),
    voiceTgl   = document.getElementById('voiceToggle'),
    digiInput  = document.getElementById('digiInput'),
    digiSend   = document.getElementById('digiSendBtn');

// ====== 状态 ======
var avatarId = null,
    voiceOn  = true,
    ws = null, audioCtx = null, stream = null, processor = null,
    isRecording = false, fullText = '',
    audioPlayer = null, pollTimer = null,
    lastReply = '';

// ====== 1. 照片上传 ======
uploadBox.addEventListener('click', function(){ uploadInp.click(); });
uploadBox.addEventListener('dragover', function(e){ e.preventDefault(); uploadBox.style.borderColor='#3b82f6'; });
uploadBox.addEventListener('dragleave', function(){ uploadBox.style.borderColor='#475569'; });
uploadBox.addEventListener('drop', function(e){
    e.preventDefault(); uploadBox.style.borderColor='#475569';
    if(e.dataTransfer.files.length>0) handlePhoto(e.dataTransfer.files[0]);
});
uploadInp.addEventListener('change', function(){
    if(this.files.length>0) handlePhoto(this.files[0]);
});

async function handlePhoto(file) {
    // 本地预览
    var reader = new FileReader();
    reader.onload = function(e){
        preview.src = e.target.result;
        preview.style.display = 'block';
        var pw = document.getElementById('avaPhotoWrap');
        if(pw) pw.style.display = 'block';
        uploadBox.style.display = 'none';
        avaVideo.style.display = 'none';
    };
    reader.readAsDataURL(file);
    // 上传后端
    var fd = new FormData(); fd.append('file', file); fd.append('name', file.name);
    try {
        var r = await fetch('/api/avatar/upload', {method:'POST',body:fd});
        var d = await r.json();
        if(d.success){
            avatarId = d.avatar_id;
            avaStatus.textContent = '✅ 照片已就绪 · 可以开始对话';
        } else {
            avaStatus.textContent = '❌ 上传失败';
        }
    } catch(e){ avaStatus.textContent = '❌ 上传失败'; }
}

// ====== 2. 文字对话 + TTS + 唇形视频 ======
digiSend.addEventListener('click', sendMsg);
digiInput.addEventListener('keydown', function(e){ if(e.key==='Enter') sendMsg(); });

async function sendMsg(){
    var q = digiInput.value.trim(); if(!q) return;
    digiInput.value = ''; digiSend.disabled = true;
    addChatBubble('user', '👤 你', q);
    avaStatus.textContent = '⏳ 思考中...';
    setVideoState('thinking');

    try {
        // Step 1: Agent 回复 + TTS 音频
        var r = await fetch('/api/asr/voice', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({text:q, enable_tts:voiceOn, voice:'xiaoxiao'})
        });
        var d = await r.json();
        lastReply = d.text || '';
        addChatBubble('ai', '🤖 小医', lastReply);
        digiSend.disabled = false; digiInput.focus();

        // Step 2: 如有照片 → 等唇形视频，否则播TTS
        if(avatarId && lastReply && voiceOn){
            avaStatus.textContent = '🎬 SadTalker 唇形视频生成中...';
            setVideoState('speaking');
            try {
                var vr = await fetch('/api/avatar/speak', {
                    method:'POST', headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({avatar_id:avatarId, question:q, async_mode:true})
                });
                var vd = await vr.json();
                if(vd.success && vd.task_id) {
                    await waitForVideo(vd.task_id);
                }
            } catch(e){}
        }

        if(!avatarId) avaStatus.textContent = '💡 上传照片可生成唇形视频';
        else if(!avaVideo.style.display.match(/block/i)){
            // 视频没出来，播 TTS 兜底
            if(d.audio_b64 && voiceOn){
                avaStatus.textContent = '✅ 回复完成（唇形生成中）';
                setVideoState('speaking');
                await playAudioAsync(d.audio_b64);
            }
        }
        setVideoState('idle');

    } catch(e){
        addChatBubble('system','','❌ 网络错误: '+e.message);
        avaStatus.textContent = '❌ 出错了';
        digiSend.disabled = false;
        setVideoState('idle');
    }
}

// ====== 3. 语音输入（WebSocket ASR） ======
recBtn.addEventListener('click', function(){ isRecording ? stopRec() : startRec(); });

async function startRec(){
    try {
        var proto = location.protocol==='https:'?'wss:':'ws:';
        ws = new WebSocket(proto+'//'+location.host+'/api/asr/ws/realtime');
        ws.binaryType = 'arraybuffer';
        ws.onopen = async function(){
            stream = await navigator.mediaDevices.getUserMedia({audio:{sampleRate:16000,channelCount:1,echoCancellation:true,noiseSuppression:true}});
            audioCtx = new (window.AudioContext||window.webkitAudioContext)({sampleRate:16000});
            var src = audioCtx.createMediaStreamSource(stream);
            processor = audioCtx.createScriptProcessor(4096,1,1);
            processor.onaudioprocess = function(e){
                if(!isRecording||ws.readyState!==WebSocket.OPEN) return;
                var input = e.inputBuffer.getChannelData(0);
                var pcm = new Int16Array(input.length);
                for(var i=0;i<input.length;i++){var s=Math.max(-1,Math.min(1,input[i]));pcm[i]=s<0?s*0x8000:s*0x7FFF;}
                ws.send(pcm.buffer);
            };
            src.connect(processor);processor.connect(audioCtx.destination);
            isRecording=true;recBtn.textContent='⏹ 停止录音';recBtn.style.background='#dc2626';
            recStatus.textContent='🔴 聆听中...';recStatus.style.color='#dc2626';
            fullText='';setVideoState('listening');
        };
        ws.onmessage=function(e){
            var d=JSON.parse(e.data);
            if(d.type==='partial') recStatus.textContent='🔴 '+d.text;
            else if(d.type==='final'){fullText+=d.text;recStatus.textContent='✅ '+d.text;}
            else if(d.type==='done'){stopRec();if(fullText.trim()){digiInput.value=fullText.trim();sendMsg();}}
            else if(d.type==='error') recStatus.textContent='❌ '+d.message;
        };
        ws.onerror=function(){recStatus.textContent='❌ 连接失败';};
    }catch(e){recStatus.textContent='❌ 麦克风不可用';}
}

function stopRec(){
    if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({action:'stop'}));
    stopAudio();isRecording=false;recBtn.textContent='🎙️ 语音输入';recBtn.style.background='#2563eb';
    recStatus.textContent='准备就绪';recStatus.style.color='#64748b';setVideoState('idle');
}

function stopAudio(){
    if(processor){processor.disconnect();processor=null;}
    if(stream){stream.getTracks().forEach(function(t){t.stop();});stream=null;}
    if(audioCtx){audioCtx.close();audioCtx=null;}
    if(ws){try{ws.close();}catch(e){}ws=null;}
}

// ====== 4. 等待视频（先秒出ffmpeg → SadTalker后台替换） ======
function waitForVideo(taskId){
    return new Promise(function(resolve){
        var cnt=0, maxWait=150;  // 最多等5分钟
        var t=setInterval(async function(){
            cnt++;
            try {
                var r=await fetch('/api/avatar/video/'+taskId),d=await r.json();
                if(d.status==='done' && d.video_url){
                    clearInterval(t);
                    // 先验证视频可访问
                    var test = await fetch(d.video_url);
                    if(test.ok && test.headers.get('content-type','').indexOf('video')>=0){
                        var pw = document.getElementById('avaPhotoWrap');
                        if(pw) pw.style.display = 'none';
                        uploadBox.style.display = 'none';
                        avaVideo.src = d.video_url + '?t=' + Date.now();
                        avaVideo.style.display = 'block';
                        avaVideo.loop = false; avaVideo.muted = false;
                        avaVideo.onerror = function(){ avaVideo.style.display='none'; if(pw)pw.style.display='block'; };
                        avaVideo.onended = function(){ avaStatus.textContent = '✅ 唇形视频播放完毕'; };
                        avaVideo.play().catch(function(){});
                        avaStatus.textContent = '✅ 唇形视频播放中';
                    } else {
                        avaStatus.textContent='✅ 回复完成（视频生成中）';
                    }
                    resolve();
                } else if(d.status==='error' || cnt>maxWait){
                    clearInterval(t); avaStatus.textContent='✅ 回复完成';
                    resolve();
                } else {
                    avaStatus.textContent='🎬 生成视频'+'.'.repeat(cnt%4)+' ('+Math.floor(cnt*2)+'s)';
                }
            } catch(e){clearInterval(t);resolve();}
        },2000);
    });
}

// ====== 4b. SadTalker 替换检查 ======
var _checkSz = 0;
function checkSadTalkerUpdate(taskId){
    _checkSz = 0;
    var cnt = 0;
    var t = setInterval(async function(){
        cnt++;
        try {
            var url = '/api/avatar/play/' + taskId + '?t=' + Date.now();
            var resp = await fetch(url);
            var sz = parseInt(resp.headers.get('content-length') || '0');
            if(resp.ok && sz > 1000){
                if(_checkSz === 0){ _checkSz = sz; }  // 首次记录
                else if(sz !== _checkSz){  // 大小变了 = SadTalker已替换
                    clearInterval(t); _checkSz = 0;
                    avaVideo.src = url;
                    avaVideo.play().catch(function(){});
                    avaStatus.textContent = '✅ 唇形视频';
                    return;
                }
            }
            if(cnt > 60){ clearInterval(t); _checkSz = 0; }
        } catch(e){ clearInterval(t); _checkSz = 0; }
    }, 3000);
}

// ====== 5. TTS 开关 ======
voiceTgl.addEventListener('click',function(){
    voiceOn=!voiceOn;
    voiceTgl.textContent=voiceOn?'🔊 语音回复':'🔇 语音关';
    voiceTgl.style.background=voiceOn?'#16a34a':'#94a3b8';
});

// ====== 6. 工具函数 ======
function addChatBubble(role, name, text){
    // 清首次提示
    var hint = chatArea.querySelector('div[style]');
    if(hint && hint.querySelector('div[style*="font-size:48px"]')) chatArea.innerHTML='';

    var div=document.createElement('div');
    div.style.cssText='margin-bottom:12px';
    var isUser=role==='user';
    div.innerHTML=
        '<div style="font-size:11px;color:#64748b;margin-bottom:2px;text-align:'+(isUser?'right':'left')+'">'+name+'</div>'+
        '<div style="display:inline-block;padding:10px 14px;border-radius:12px;font-size:13px;max-width:85%;'+
        (isUser?'background:#2563eb;color:#fff;float:right':'background:#f1f5f9;color:#1e293b')+
        ';line-height:1.6;word-break:break-word">'+esc(text)+'</div>'+
        '<div style="clear:both"></div>';
    chatArea.appendChild(div);
    chatArea.scrollTop=chatArea.scrollHeight;
}

function setVideoState(state){
    var box=uploadBox, video=avaVideo;
    switch(state){
        case 'idle':      if(box)box.style.borderColor='#475569';break;
        case 'thinking':  if(box)box.style.borderColor='#f59e0b';break;
        case 'speaking':  if(box)box.style.borderColor='#16a34a';
                          if(video&&video.style.display!='none')video.style.boxShadow='0 0 20px rgba(22,163,74,.5)';break;
        case 'listening': if(box)box.style.borderColor='#dc2626';break;
    }
}

function playAudioAsync(b64){
    return new Promise(function(resolve){
        if(audioPlayer){audioPlayer.pause();audioPlayer=null;}
        var a=new Audio('data:audio/mp3;base64,'+b64);
        a.onended=resolve;a.onerror=resolve;
        a.play().catch(function(){resolve();});
        audioPlayer=a;
    });
}

function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');}
})();

/**
 * 工单18 V20 — HTTP直连YOLO手势识别 (不用WebSocket，避免CDN被墙)
 */
(function(){
"use strict";
var $=function(id){return document.getElementById(id);};
var S={
  sid:"", lang:"zh",
  cam:null, actx:null, asrc:null, rec:null, recording:false,
  lipId:null, lipFrames:[], lipStart:0, alyser:null, useSvrLip:false,
  yoloTimer:null, yoloActive:false, yoloCD:false
};

function log(s){try{console.log("[导览]",s)}catch(e){}}

// ========== 消息 ==========
function msg(role,text){
  try{var el=document.createElement("div");el.className="msg "+role;el.textContent=text;var c=$("chatList");var w=c.querySelector(".chat-welcome");if(w)w.remove();c.appendChild(el);c.scrollTop=c.scrollHeight}catch(e){}
}
function wait(on){try{$("chatWait").className="chat-wait"+(on?" on":"")}catch(e){}}
function sub(t){try{if(t)$("subTxt").textContent=t}catch(e){}}
function bubble(t){try{if(!t)return;var b=$("bubbleBox");b.textContent=t.slice(0,80);b.classList.add("show");clearTimeout(b._t);b._t=setTimeout(function(){b.classList.remove("show")},5000)}catch(e){}}
function spots(names){
  try{if(!names||!names.length)return;$("spotsList").innerHTML=names.map(function(n){return'<span class="spot-tag">📍 '+n+"</span>"}).join("");
    var tags=$("spotsList").querySelectorAll(".spot-tag");for(var i=0;i<tags.length;i++){(function(n){tags[i].onclick=function(){$("txtInput").value=n;send()}})(names[i])}}catch(e){}
}
function glow(ms){try{var g=$("glowRing");g.classList.add("on");clearTimeout(g._t);if(ms)g._t=setTimeout(function(){g.classList.remove("on")},ms)}catch(e){}}

// ========== TTS+唇形同步 V3 — 使用 Web Audio API decodeAudioData (无 createMediaElementSource bug) ==========
function play(b64, mime, lip) {
  try {
    stopLip();
    // 工单18：确保 AudioContext 存在且已激活(解决浏览器自动播放限制)
    if (!S.actx) S.actx = new (window.AudioContext || window.webkitAudioContext)();
    var ctx = S.actx;
    if (ctx.state === "suspended") { ctx.resume(); }

    // 工单18：base64 → ArrayBuffer → decodeAudioData (每次新建，无复用限制)
    var binaryStr = atob(b64);
    var bytes = new Uint8Array(binaryStr.length);
    for (var i = 0; i < binaryStr.length; i++) { bytes[i] = binaryStr.charCodeAt(i); }

    ctx.decodeAudioData(bytes.buffer, function(audioBuffer) {
      // 工单18：创建全新的音源和分析器，每次播放都是独立链路
      var source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      var analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      analyser.connect(ctx.destination);

      S.asrc = source;
      S.alyser = analyser;
      S.lipFrames = lip || [];
      S.useSvrLip = false;  // 工单18：强制使用振幅驱动唇形(比文本估算更准确同步)

      // 工单18：开始播放时启动唇形同步
      source.onended = function() {
        stopLip(); mouthR();
        try { document.getElementById("glowRing").classList.remove("on"); } catch(e) {}
      };
      S.lipStart = ctx.currentTime;
      source.start(0);
      lipAmp();  // 使用音频振幅驱动口型
      glow(0);
    }, function(err) {
      // 工单18：解码失败时降级使用 <audio> 元素
      log("Audio decode failed, fallback to <audio>: " + err);
      try {
        var a = new Audio();
        a.src = "data:" + (mime || "audio/mp3") + ";base64," + b64;
        a.play().catch(function() {});
      } catch(e2) {}
    });
  } catch(e) { log("TTS play error: " + (e.message || e)); }
}

// 工单18：基于音频振幅的唇形同步 — 分析实际音频信号驱动口型
function lipAmp() {
  if (!S.alyser) return;
  var freqCount = S.alyser.frequencyBinCount;
  var dataArray = new Uint8Array(freqCount);
  function loop() {
    if (!S.alyser) return;
    S.alyser.getByteTimeDomainData(dataArray);
    var sumSq = 0;
    for (var i = 0; i < dataArray.length; i++) {
      var v = (dataArray[i] - 128) / 128;
      sumSq += v * v;
    }
    var rms = Math.sqrt(sumSq / dataArray.length);
    // 工单18：RMS → 口型开合度(0-1)，系数5.0使普通语音可见
    mouth(Math.min(1, rms * 5.0));
    S.lipId = requestAnimationFrame(loop);
  }
  S.lipId = requestAnimationFrame(loop);
}

// 工单18：基于服务器唇形帧的口型同步(edge-tts WordBoundary 提供精确时间戳时使用)
function lipSvr() {
  var f = S.lipFrames;
  if (!f || !f.length) { lipAmp(); return; }
  var i = 0;
  function loop() {
    if (!S.lipStart) { S.lipId = requestAnimationFrame(loop); return; }
    var c = S.actx; if (!c) { S.lipId = requestAnimationFrame(loop); return; }
    var elapsed = c.currentTime - S.lipStart;
    while (i < f.length - 1 && f[i + 1].t <= elapsed) i++;
    if (i < f.length) mouth(f[i].v);
    if (i >= f.length - 1 && elapsed > f[f.length - 1].t + 0.3) {
      mouthR(); S.lipId = null; return;
    }
    S.lipId = requestAnimationFrame(loop);
  }
  S.lipId = requestAnimationFrame(loop);
}

// 工单18：驱动CSS数字人嘴巴开合
function mouth(o) {
  try {
    var m = document.getElementById("avMouth");
    if (!m) return;
    var w = 24 + o * 10;
    var h = Math.max(2, 6 * (1 - o * 0.5) + o * 18);
    m.style.width = w + "px";
    m.style.height = h + "px";
    m.style.borderRadius = o > 0.5 ? "6px" : "0 0 " + (13 * (1 - o)) + "px " + (13 * (1 - o)) + "px";
    if (o > 0.25) { try { document.getElementById("glowRing").classList.add("on"); } catch(e) {} }
  } catch(e) {}
}

// 工单18：恢复嘴巴默认闭合状态
function mouthR() {
  try {
    var m = document.getElementById("avMouth");
    if (!m) return;
    m.style.width = "24px";
    m.style.height = "6px";
    m.style.borderRadius = "0 0 12px 12px";
  } catch(e) {}
}

// 工单18：停止唇形动画和音频分析
function stopLip() {
  try {
    if (S.lipId) { cancelAnimationFrame(S.lipId); S.lipId = null; }
    if (S.asrc) { try { S.asrc.stop(); S.asrc.disconnect(); } catch(e) {} S.asrc = null; }
    S.alyser = null;
  } catch(e) {}
}

// ========== HTTP API ==========
function api(url,opts){opts=opts||{};opts.headers={"Content-Type":"application/json"};return fetch(url,opts).then(function(r){return r.json()})}
function hok(d){wait(false);if(!d.ok){msg("sys",d.error||"失败");return}msg("ai",d.answer||"");sub(d.subtitle);spots(d.references);if(d.audio_base64)play(d.audio_base64,d.audio_mime||"audio/mp3",d.lip_sync||[]);bubble(d.answer?d.answer.slice(0,60):"");glow(2000)}

// ========== V20: HTTP 直连 YOLO 帧识别 ==========
function captureAndSendFrame(){
  try{
    if(!S.cam||!S.sid||S.yoloCD) return;
    var v=$("camVid"),c=$("camCanvas");
    if(!v||!c||v.readyState<2) return;
    var ctx=c.getContext("2d");
    c.width=v.videoWidth||640; c.height=v.videoHeight||480;
    ctx.drawImage(v,0,0,c.width,c.height);
    var b64=c.toDataURL("image/jpeg",0.5);

    fetch("/api/realtime/yolo-behavior",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({session_id:S.sid,language:S.lang,image:b64})
    }).then(function(r){return r.json()}).then(function(d){
      if(!d.detected) return;
      // 工单18：缩短冷却时间到1.0秒
      S.yoloCD=true; setTimeout(function(){S.yoloCD=false},1000);
      // 显示
      var m={wave:{ico:"👋",txt:"挥手"},thumbs_up:{ico:"👍",txt:"点赞"},point:{ico:"☝️",txt:"指向"},smile:{ico:"😊",txt:"微笑"}};
      var info=m[d.behavior]||{ico:"✨",txt:d.behavior};
      log("识别: "+d.behavior+" conf="+(d.confidence||0).toFixed(2));
      // 摄像头提示
      $("camAlertIco").textContent=info.ico;
      $("camAlertTxt").textContent=info.txt+" (AI识别)";
      $("camAlert").classList.add("show");
      $("camState").textContent=info.txt;
      $("camState").classList.add("hit");
      setTimeout(function(){$("camAlert").classList.remove("show");$("camState").classList.remove("hit");$("camState").textContent="在线 (AI)"},2500);
      // AI回复
      if(d.answer){
        msg("user","📹 "+info.txt);
        msg("ai",d.answer||"");
        sub(d.subtitle);
        if(d.audio_base64) play(d.audio_base64,d.audio_mime||"audio/mp3",d.lip_sync||[]);
        bubble(d.answer?d.answer.slice(0,60):"");
        glow(2000);
      }
    }).catch(function(e){log("帧发送失败: "+e.message)});
  }catch(e){}
}

function startYoloLoop(){
  if(S.yoloTimer) return;
  // 工单18：帧间隔500ms，与服务端节流(400ms)对齐，避免无效请求
  S.yoloTimer=setInterval(captureAndSendFrame,500);
  S.yoloActive=true;
  log("YOLO HTTP识别已启动 (500ms间隔)");
}

function stopYoloLoop(){
  if(S.yoloTimer){clearInterval(S.yoloTimer);S.yoloTimer=null;}
  S.yoloActive=false;
}

// ========== 文本 ==========
function send(){
  try{var inp=$("txtInput"),txt=inp.value.trim();if(!txt||!S.sid)return;msg("user",txt);inp.value="";wait(true);glow(0);
    api("/api/chat/text",{method:"POST",body:JSON.stringify({session_id:S.sid,question:txt,language:S.lang})}).then(hok).catch(function(){wait(false)})}catch(e){}
}

// ========== 图片/视频 ==========
function sendImg(file){try{if(!file)return;msg("user","📷 "+file.name);wait(true);var fd=new FormData();fd.append("session_id",S.sid);fd.append("language",S.lang);fd.append("image",file);fetch("/api/chat/image",{method:"POST",body:fd}).then(function(r){return r.json()}).then(hok).catch(function(){wait(false)})}catch(e){}}
function sendVid(file){try{if(!file)return;msg("user","🎬 "+file.name);wait(true);var fd=new FormData();fd.append("session_id",S.sid);fd.append("language",S.lang);fd.append("video",file);fetch("/api/chat/video",{method:"POST",body:fd}).then(function(r){return r.json()}).then(hok).catch(function(){wait(false)})}catch(e){}}

// ========== 语音 ==========
function toggleMic(){try{if(S.recording)stopMic();else startMic()}catch(e){}}
function startMic(){try{navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){S.rec=new MediaRecorder(stream,{mimeType:"audio/webm;codecs=opus"});S.chunks=[];S.rec.ondataavailable=function(e){if(e.data.size>0)S.chunks.push(e.data)};S.rec.onstop=function(){var blob=new Blob(S.chunks,{type:"audio/webm"});var fd=new FormData();fd.append("session_id",S.sid);fd.append("language",S.lang);fd.append("audio",blob,"voice.webm");msg("user","🎤 语音");wait(true);fetch("/api/chat/audio",{method:"POST",body:fd}).then(function(r){return r.json()}).then(function(d){if(d.transcript)msg("user","转写:"+d.transcript);hok(d)}).catch(function(){wait(false)});stream.getTracks().forEach(function(t){t.stop()})};S.rec.start();S.recording=true;$("btnMic").classList.add("rec")}).catch(function(){msg("sys","麦克风不可用")})}catch(e){}}
function stopMic(){try{if(S.rec&&S.recording){S.rec.stop();S.recording=false;$("btnMic").classList.remove("rec")}}catch(e){}}

// ========== 摄像头 ==========
function camOn(){
  try{
    if(S.cam)return;
    $("camState").textContent="启动中...";
    navigator.mediaDevices.getUserMedia({video:{width:640,height:480},audio:false}).then(function(stream){
      S.cam=stream;var v=$("camVid");v.srcObject=stream;v.play();
      v.classList.add("on");$("camEmpty").classList.add("off");$("camDot").classList.add("live");
      $("camState").textContent="在线 (AI)";
      startYoloLoop();
      msg("sys","📷 摄像头已开启 — AI自动识别手势中...");
    }).catch(function(e){msg("sys","摄像头不可用: "+e.message)});
  }catch(e){}
}
function camOff(){
  try{
    stopYoloLoop();
    if(S.cam){S.cam.getTracks().forEach(function(t){t.stop()});S.cam=null}
    $("camVid").classList.remove("on");$("camVid").srcObject=null;$("camEmpty").classList.remove("off");
    $("camDot").classList.remove("live");$("camState").textContent="待机"
  }catch(e){}
}

// ========== 手势按钮(手动fallback) ==========
function triggerGesture(beh){
  try{
    var m={wave:["👋","挥手"],thumbs_up:["👍","点赞"],point:["☝️","指向"],smile:["😊","微笑"]};
    var info=m[beh]||["✨",beh];
    msg("user","📹 "+info[1]);wait(true);glow(0);
    $("camAlertIco").textContent=info[0];$("camAlertTxt").textContent=info[1];
    $("camAlert").classList.add("show");$("camState").textContent=info[1];$("camState").classList.add("hit");
    setTimeout(function(){$("camAlert").classList.remove("show");$("camState").classList.remove("hit");$("camState").textContent="在线 (AI)"},3000);
    api("/api/chat/behavior",{method:"POST",body:JSON.stringify({session_id:S.sid,behavior:beh,language:S.lang})}).then(hok).catch(function(){wait(false)});
  }catch(e){}
}

// ========== 会话 ==========
function initSession(){
  api("/api/session/create",{method:"POST"}).then(function(d){
    S.sid=d.session_id;msg("sys","✨ 导览就绪！开启摄像头即可自动识别手势互动");bubble("您好！我是AI导览员~");glow(3000);loadSpots();
  }).catch(function(){msg("sys","后端未连接，请运行 python run.py")});
}
function loadSpots(){api("/api/knowledge/spots").then(function(d){if(d.spots)spots(d.spots.map(function(s){return s.name}))}).catch(function(){})}

// ========== 眨眼 ==========
function blinkLoop(){
  try{var eyes=document.querySelectorAll(".av-eye");function bl(){eyes.forEach(function(e){e.classList.add("blink")});setTimeout(function(){eyes.forEach(function(e){e.classList.remove("blink")})},150)}setInterval(function(){if(Math.random()<0.25)bl()},3000);setTimeout(bl,800)}catch(e){}
}

// ========== 事件绑定 ==========
function bind(){
  try{$("btnNewSess").onclick=initSession}catch(e){}
  try{$("btnSend").onclick=send}catch(e){}
  try{$("txtInput").onkeydown=function(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}}}catch(e){}
  try{$("langSel").onchange=function(e){S.lang=e.target.value}}catch(e){}
  try{$("btnMic").onclick=toggleMic}catch(e){}
  try{$("fileImg").onchange=function(e){if(e.target.files[0]){sendImg(e.target.files[0]);e.target.value=""}}}catch(e){}
  try{$("fileVid").onchange=function(e){if(e.target.files[0]){sendVid(e.target.files[0]);e.target.value=""}}}catch(e){}
  try{$("btnCamOn").onclick=camOn}catch(e){}
  try{$("btnCamOff").onclick=camOff}catch(e){}
  try{var gbs=document.querySelectorAll(".ges-btn");for(var i=0;i<gbs.length;i++){gbs[i].onclick=function(){triggerGesture(this.dataset.g)}}}catch(e){}
  try{$("btnClear").onclick=function(){$("chatList").innerHTML='<div class="chat-welcome"><div class="cw-emoji">🎯</div><div class="cw-text">对话已清空</div></div>'}}catch(e){}
}

// ========== 启动 ==========
document.addEventListener("DOMContentLoaded",function(){
  blinkLoop();msg("sys","⏳ 正在连接服务...");bind();initSession();
  log("V20 HTTP直连启动");
});
})();

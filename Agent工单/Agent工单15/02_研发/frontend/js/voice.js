/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
 * 数字人语音对话管线（ASR→Agent→TTS）+ 虚拟形象动画
 */
'use strict';

(function () {
  var MA = window.MA;

  var voiceInput = document.getElementById('voiceInput');
  var voiceSendBtn = document.getElementById('voiceSendBtn');
  var avatarRing = document.getElementById('avatarRing');
  var avatarStatus = document.getElementById('avatarStatus');
  var voiceToggle = document.getElementById('voiceToggle');

  var voiceEnabled = true;
  var audioPlayer = null;

  // ====== TTS 开关 ======
  if (voiceToggle) {
    voiceToggle.addEventListener('click', function () {
      voiceEnabled = !voiceEnabled;
      voiceToggle.textContent = voiceEnabled ? '🔊 语音开' : '🔇 语音关';
      voiceToggle.style.background = voiceEnabled ? '#16a34a' : '#94a3b8';
    });
  }

  // ====== 发送语音对话 ======
  function sendVoiceMessage() {
    var text = voiceInput ? voiceInput.value.trim() : '';
    if (!text) return;

    MA.addMsg('voiceMessages', 'user', text);
    if (voiceInput) voiceInput.value = '';
    if (voiceSendBtn) voiceSendBtn.disabled = true;

    setAvatarState('thinking');

    fetch('/api/asr/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, enable_tts: voiceEnabled, voice: 'xiaoxiao' }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        MA.addMsg('voiceMessages', 'assistant', d.text || '无回复');

        if (d.audio_b64 && voiceEnabled) {
          setAvatarState('speaking');
          playAudio(d.audio_b64, function () { setAvatarState('idle'); });
        } else {
          setAvatarState('idle');
        }
      })
      .catch(function (e) {
        MA.addMsg('voiceMessages', 'assistant', '❌ 数字人服务异常: ' + e.message);
        setAvatarState('idle');
      })
      .finally(function () {
        if (voiceSendBtn) voiceSendBtn.disabled = false;
        if (voiceInput) voiceInput.focus();
      });
  }

  function playAudio(b64, onEnd) {
    if (audioPlayer) { audioPlayer.pause(); audioPlayer = null; }
    var audio = new Audio('data:audio/mp3;base64,' + b64);
    audio.onended = onEnd;
    audio.onerror = function () { if (onEnd) onEnd(); };
    audio.play().catch(function () { if (onEnd) onEnd(); });
    audioPlayer = audio;
  }

  function setAvatarState(state) {
    if (!avatarRing || !avatarStatus) return;
    switch (state) {
      case 'idle':
        avatarRing.style.animation = 'avatarPulse 3s infinite';
        avatarRing.style.borderColor = '#3b82f6';
        avatarStatus.textContent = '👂 聆听中...';
        break;
      case 'thinking':
        avatarRing.style.animation = 'avatarSpin 0.8s infinite linear';
        avatarRing.style.borderColor = '#f59e0b';
        avatarStatus.textContent = '🤔 思考中...';
        break;
      case 'speaking':
        avatarRing.style.animation = 'avatarBounce 0.3s infinite';
        avatarRing.style.borderColor = '#16a34a';
        avatarStatus.textContent = '🔊 说话中...';
        break;
    }
  }

  if (voiceSendBtn) voiceSendBtn.addEventListener('click', sendVoiceMessage);
  if (voiceInput) {
    voiceInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') sendVoiceMessage();
    });
  }

})();

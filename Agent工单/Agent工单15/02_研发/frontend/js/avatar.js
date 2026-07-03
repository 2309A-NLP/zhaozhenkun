/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
 * 数字人模块 —— 上传照片 → 提问 → 看数字人用那张脸说话
 * （注：此模块已被 digital.js 取代，保留作为备用参考）
 */
'use strict';

(function () {
  var avaUpload = document.getElementById('avaUpload');
  var avaPreview = document.getElementById('avaPreview');
  var avaInput = document.getElementById('avaInput');
  var avaSendBtn = document.getElementById('avaSendBtn');
  var avaVideo = document.getElementById('avaVideo');
  var avaStatus = document.getElementById('avaStatus');
  var avaText = document.getElementById('avaText');
  var avaUploadBox = document.getElementById('avaUploadBox');

  if (!avaUpload) return; // HTML 中不存在此版本的元素则跳过

  var currentAvatarId = null;
  var pollTimer = null;

  avaUpload.addEventListener('change', function () {
    var file = this.files[0];
    if (!file) return;

    var reader = new FileReader();
    reader.onload = function (e) { avaPreview.src = e.target.result; avaPreview.style.display = 'block'; };
    reader.readAsDataURL(file);

    var form = new FormData();
    form.append('file', file);
    form.append('name', file.name);
    fetch('/api/avatar/upload', { method: 'POST', body: form })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.success) {
          currentAvatarId = d.avatar_id;
          avaStatus.textContent = '✅ 照片已上传: ' + d.name;
          avaStatus.style.color = '#16a34a';
        }
      })
      .catch(function () { avaStatus.textContent = '❌ 上传失败'; });
  });

  function askAvatar() {
    var q = avaInput.value.trim();
    if (!q) return;
    if (!currentAvatarId) { avaStatus.textContent = '⚠️ 请先上传照片'; return; }

    avaInput.value = '';
    avaSendBtn.disabled = true;
    avaStatus.textContent = '⏳ 正在生成回复...';
    if (avaVideo) avaVideo.style.display = 'none';
    if (avaText) avaText.textContent = '';

    fetch('/api/avatar/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ avatar_id: currentAvatarId, question: q, async_mode: true }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.success) { avaStatus.textContent = '❌ ' + d.error; return; }
        if (avaText) avaText.textContent = '👩‍⚕️ 小医: ' + d.text;
        avaStatus.textContent = '🎬 正在生成数字人视频...';
        pollVideo(d.task_id);
      })
      .catch(function () { avaStatus.textContent = '❌ 网络错误'; })
      .finally(function () { avaSendBtn.disabled = false; });
  }

  function pollVideo(taskId) {
    if (pollTimer) clearInterval(pollTimer);
    var count = 0;
    pollTimer = setInterval(function () {
      count++;
      fetch('/api/avatar/video/' + taskId)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.status === 'done') {
            clearInterval(pollTimer); pollTimer = null;
            avaVideo.src = d.video_url;
            avaVideo.style.display = 'block';
            avaVideo.play();
            avaStatus.textContent = '✅ 数字人正在说话...';
          } else if (d.status === 'error') {
            clearInterval(pollTimer); pollTimer = null;
            avaStatus.textContent = '⚠️ 视频生成失败（仅文字可用）';
          } else if (count > 150) {
            clearInterval(pollTimer); pollTimer = null;
            avaStatus.textContent = '⚠️ 视频生成超时';
          } else {
            avaStatus.textContent = '🎬 生成视频中' + '.'.repeat(count % 4);
          }
        })
        .catch(function () { clearInterval(pollTimer); pollTimer = null; });
    }, 2000);
  }

  avaSendBtn.addEventListener('click', askAvatar);
  avaInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') askAvatar(); });
  avaPreview.addEventListener('click', function () { avaUpload.click(); });
  if (avaUploadBox) avaUploadBox.addEventListener('click', function () { avaUpload.click(); });

})();

/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理/健康咨询/影像分析 V1.0
 * 健康助理模块 —— 自动识别挂号/咨询意图，路由到对应 API
 */
'use strict';

(function () {
  var MA = window.MA;

  var asstInput = document.getElementById('asstInput');
  var asstSendBtn = document.getElementById('asstSendBtn');

  // 意图路由正则
  var REG_PATTERN = /挂号|号源|预约|取消|坐诊|挂.*号|号源|有.*号|哪.*天|什么科|哪个科|挂.*科|科室|排班|还有.*号|可以.*挂/;

  function sendAsst() {
    var q = asstInput.value.trim();
    if (!q) return;

    MA.addMsg('asstMessages', 'user', q);
    asstInput.value = '';
    asstSendBtn.disabled = true;
    MA.showTyping('asstMessages');

    var isReg = REG_PATTERN.test(q);
    var url = isReg ? MA.API_BASE + '/api/registration/chat'
                    : MA.API_BASE + '/api/consultation/chat';

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: q }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        MA.hideTyping();
        var text = d.reply || d.answer || d.error || '无响应';
        var meta = (d.model ? '模型: ' + d.model + ' ' : '') +
                   (d.latency_ms ? ' | ' + d.latency_ms + 'ms' : '');
        MA.addMsg('asstMessages', 'assistant', text, meta);
      })
      .catch(function (e) {
        MA.hideTyping();
        MA.addMsg('asstMessages', 'assistant', '❌ 网络错误: ' + e.message);
      })
      .finally(function () {
        asstSendBtn.disabled = false;
        asstInput.focus();
      });
  }

  asstSendBtn.addEventListener('click', sendAsst);
  asstInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') sendAsst();
  });

  // 暴露 sendAsst 给 map.js 扩展
  window.sendAsst = sendAsst;

})();

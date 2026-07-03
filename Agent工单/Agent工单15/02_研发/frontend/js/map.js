/**
 * 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
 * 高德地图模块 —— 医院位置相关：出行/住宿/餐饮查询
 */
'use strict';

(function () {
  var MA = window.MA;

  var mapInput = document.getElementById('mapInput');
  var mapSendBtn = document.getElementById('mapSendBtn');

  function sendMapQuery() {
    var q = mapInput.value.trim();
    if (!q) return;

    var resultBox = document.getElementById('mapChatResult');
    if (resultBox) resultBox.style.display = 'block';

    MA.addMsg('mapMessages', 'user', q);
    mapInput.value = '';
    mapSendBtn.disabled = true;
    MA.showTyping('mapMessages');

    fetch(MA.API_BASE + '/api/map/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: q }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        MA.hideTyping();
        var text = d.reply || d.error || '服务暂时不可用';
        var meta = (d.latency_ms ? d.latency_ms + 'ms' : '');
        MA.addMsg('mapMessages', 'assistant', text, meta);
      })
      .catch(function (e) {
        MA.hideTyping();
        MA.addMsg('mapMessages', 'assistant', '❌ 网络错误: ' + e.message);
      })
      .finally(function () {
        mapSendBtn.disabled = false;
        mapInput.focus();
      });
  }

  mapSendBtn.addEventListener('click', sendMapQuery);
  mapInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') sendMapQuery();
  });

  // ====== 扩展健康助理：自动识别地图意图并路由 ======
  var _origSendAsst = window.sendAsst;
  if (typeof _origSendAsst === 'function') {
    var MAP_PATTERN = /怎么去|怎么走|路线|附近|周边|酒店|住宿|吃饭|餐厅|餐饮|地铁|公交|打车|导航|地址|在哪|位置|多远|几公里|天气|出行|地图/;
    window.sendAsst = function () {
      var asstInput = document.getElementById('asstInput');
      var q = (asstInput && asstInput.value) || '';
      if (MAP_PATTERN.test(q)) {
        document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
        var mapTab = document.querySelector('[data-tab="map"]');
        if (mapTab) mapTab.classList.add('active');
        document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.remove('active'); });
        var mapPanel = document.getElementById('mapPanel');
        if (mapPanel) mapPanel.classList.add('active');

        if (mapInput && asstInput) {
          mapInput.value = asstInput.value;
          asstInput.value = '';
          sendMapQuery();
        }
        return;
      }
      _origSendAsst();
    };
  }

})();

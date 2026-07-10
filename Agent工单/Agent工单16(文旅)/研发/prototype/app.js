// app.js - 文旅创新智脑数字人交互逻辑 | 工单CV-AIGC-16
// 功能：沉浸式数字人对话、SSE流式、语音输入(Web Speech)、拍照识物、粒子背景

mermaid.initialize({startOnLoad:true,theme:'default',securityLevel:'loose'}); // 初始化Mermaid
var API_BASE='http://localhost:8765'; // 后端API地址
var currentModel='kimi'; // 当前LLM模型
var isSpeaking=false; // 数字人是否正在说话
var recognition=null; // 语音识别实例
var isListening=false; // 是否正在听

// ===== 语音识别初始化 =====
function initSpeech(){ // 初始化Web Speech API
  var SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition; // 兼容Chrome/Edge
  if(!SpeechRecognition){console.log('浏览器不支持语音识别');return null;} // 不支持则返回null
  var rec=new SpeechRecognition(); // 创建识别实例
  rec.lang='zh-CN'; // 中文普通话
  rec.interimResults=true; // 启用中间结果（边说边显示）
  rec.continuous=false; // 单次识别
  rec.onresult=function(e){ // 识别结果回调
    var txt='';for(var i=0;i<e.results.length;i++){txt+=e.results[i][0].transcript;} // 拼接所有结果
    var inp=document.getElementById('chatInput');if(inp)inp.value=txt; // 填入输入框
    var micBtn=document.querySelector('.dh-mic-btn');if(micBtn)micBtn.classList.remove('recording'); // 取消录音样式
    isListening=false; // 标记停止
  };
  rec.onerror=function(e){ // 识别错误
    console.log('语音错误:',e.error);isListening=false;
    var micBtn=document.querySelector('.dh-mic-btn');if(micBtn)micBtn.classList.remove('recording'); // 恢复按钮
    if(e.error==='not-allowed'){toast('请允许麦克风权限后重试',true);}
  };
  rec.onend=function(){ // 识别结束
    isListening=false;
    var micBtn=document.querySelector('.dh-mic-btn');if(micBtn)micBtn.classList.remove('recording');
  };
  return rec; // 返回识别实例
}

function toggleVoice(){ // 切换语音输入开关
  if(!recognition){recognition=initSpeech();} // 首次使用时初始化
  if(!recognition){toast('浏览器不支持语音识别，请用Chrome/Edge',true);return;} // 不支持
  if(isListening){recognition.stop();isListening=false; // 停止收音
    document.querySelector('.dh-mic-btn').classList.remove('recording');
  }else{ // 开始收音
    try{recognition.start();isListening=true;
      document.querySelector('.dh-mic-btn').classList.add('recording'); // 录音样式
      toast('正在听您说话...'); // 提示
    }catch(e){console.log(e);toast('请先允许麦克风权限',true);}
  }
}

// ===== 图片上传识别 =====
function triggerImageUpload(){ // 触发文件选择
  var inp=document.getElementById('imageInput'); // 隐藏的file input
  if(inp)inp.click(); // 模拟点击
}
function handleImageUpload(e){ // 处理图片选择
  var file=e.target.files[0];if(!file)return; // 无文件则返回
  var chatInp=document.getElementById('chatInput'); // 聊天输入框
  // 构造拍照识物消息
  var msg='[拍照识物] 我拍摄了一张照片，文件名：'+file.name+'，文件大小：'+(file.size/1024).toFixed(0)+'KB。请帮我识别这张照片中的景点/文物/建筑，并进行详细讲解。';
  chatInp.value=msg;sendMsg(); // 填入消息并发送
  e.target.value=''; // 清空input以支持重复选择同一文件
  toast('照片已发送给数字人识别...');
}

// ===== 粒子背景 =====
function createParticles(){ // 生成浮动粒子
  var c=document.getElementById('dhParticles');if(!c)return;
  c.innerHTML=''; // 清空
  for(var i=0;i<35;i++){ // 35个粒子
    var p=document.createElement('div');p.className='dh-particle';
    p.style.left=Math.random()*100+'%';p.style.animationDuration=(5+Math.random()*12)+'s';
    p.style.animationDelay=Math.random()*10+'s';p.style.width=(1.5+Math.random()*3.5)+'px';
    p.style.height=p.style.width;
    var cols=['rgba(139,92,246,.45)','rgba(59,130,246,.3)','rgba(16,185,129,.25)','rgba(245,158,11,.2)'];
    p.style.background=cols[Math.floor(Math.random()*cols.length)];c.appendChild(p);
  }
}

// ===== 页面导航 =====
document.querySelectorAll('.nav-item').forEach(function(item){
  item.addEventListener('click',function(){switchPage(this.dataset.page);});
});
function switchPage(name){
  document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active');});
  document.querySelectorAll('.page').forEach(function(p){p.classList.remove('active');});
  var nav=document.querySelector('.nav-item[data-page="'+name+'"]');if(nav)nav.classList.add('active');
  var page=document.getElementById('page-'+name);if(page)page.classList.add('active');
  if(name==='dh'){createParticles();welcomeAnimation();} // 进入数字人页时重建粒子和欢迎
}
function switchModel(){currentModel=document.getElementById('modelSelect').value;toast('模型: '+currentModel.toUpperCase());}
function toast(msg,isErr){var t=document.getElementById('toast');t.textContent=msg;t.className='toast show'+(isErr?' error':'');clearTimeout(t._tid);t._tid=setTimeout(function(){t.classList.remove('show');},3000);}

// ===== 欢迎动画 =====
function welcomeAnimation(){ // 数字人出现时的欢迎效果
  var body=document.getElementById('dhBody');if(!body)return;
  body.style.animation='none';body.offsetHeight;body.style.animation='dhFloat 4s ease-in-out infinite'; // 重置浮动
  var halo=document.getElementById('dhHalo');if(halo){halo.style.transform='scale(1.3)';setTimeout(function(){halo.style.transform='scale(1)';},600);}
  // 显示欢迎气泡
  setTimeout(function(){
    var bubble=document.getElementById('dhSpeechBubble'),txt=document.getElementById('dhSpeechText');
    if(bubble&&txt){txt.textContent='你好！我是文旅小智 👋\n拍照、语音或打字，我都能为你讲解哦~';bubble.style.display='block';
      setTimeout(function(){bubble.style.display='none';},4000);}
  },800);
}

// ===== SSE流式读取 =====
async function streamFetch(url,body,onChunk,onDone,onError){
  try{
    var resp=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!resp.ok){var txt=await resp.text();onError('HTTP '+resp.status);return;}
    var reader=resp.body.getReader(),decoder=new TextDecoder(),buffer='';
    while(true){var r=await reader.read();if(r.done)break;
      buffer+=decoder.decode(r.value,{stream:true});var lines=buffer.split('\n');buffer=lines.pop()||'';
      for(var i=0;i<lines.length;i++){var line=lines[i];
        if(line.startsWith('data: ')){var d=line.slice(6);if(d.trim()==='[DONE]'){onDone();return;}
          try{var j=JSON.parse(d);if(j.error){onError(j.error);return;}if(j.content)onChunk(j.content);}catch(e){}
        }
      }
    }onDone();
  }catch(e){onError(e.message);}
}

// ===== 数字人视觉反馈 =====
function startSpeaking(){ // 开始说话动画
  isSpeaking=true;var face=document.querySelector('.dh-face-display');if(face)face.classList.add('speaking'); // 脸部脉冲
  var halo=document.getElementById('dhHalo');if(halo){halo.style.borderColor='rgba(139,92,246,.4)';halo.style.boxShadow='0 0 50px rgba(139,92,246,.2)';halo.style.animationDuration='8s';} // 光环加速旋转
}
function stopSpeaking(){ // 停止说话
  isSpeaking=false;var face=document.querySelector('.dh-face-display');if(face)face.classList.remove('speaking');
  var halo=document.getElementById('dhHalo');if(halo){halo.style.borderColor='rgba(139,92,246,.15)';halo.style.boxShadow='none';halo.style.animationDuration='20s';}
}
function showThinking(){var t=document.getElementById('dhThinking');if(t)t.style.display='flex';} // 思考中
function hideThinking(){var t=document.getElementById('dhThinking');if(t)t.style.display='none';}
function showSpeechBubble(text){ // 显示数字人说话气泡
  var b=document.getElementById('dhSpeechBubble'),t=document.getElementById('dhSpeechText');
  if(b&&t){t.innerHTML=renderMarkdown(text);b.style.display='block';}
}
function hideSpeechBubble(){var b=document.getElementById('dhSpeechBubble');if(b)b.style.display='none';}
function showUserBubble(text){ // 显示用户消息气泡
  var b=document.getElementById('dhUserBubble'),t=document.getElementById('dhUserText');
  if(b&&t){t.textContent=text;b.style.display='block';setTimeout(function(){b.style.display='none';},3500);}
}

// ===== AI对话 =====
async function sendMsg(){ // 发送消息
  var inp=document.getElementById('chatInput'),txt=inp.value.trim();if(!txt)return;
  var sendBtn=document.getElementById('sendBtn');inp.value='';sendBtn.disabled=true;
  showUserBubble(txt);hideSpeechBubble();showThinking();startSpeaking(); // 数字人开始思考+说话

  var fullText='';
  await streamFetch(API_BASE+'/api/chat',{message:txt,provider:currentModel},
    function(chunk){fullText+=chunk;showSpeechBubble(fullText);}, // 实时更新气泡
    function(){stopSpeaking();hideThinking();sendBtn.disabled=false; // 完成
      if(!fullText){showSpeechBubble('抱歉，我暂时无法回答。请换个问题试试？');}
    },
    function(err){stopSpeaking();hideThinking();sendBtn.disabled=false;
      showSpeechBubble('网络出问题了，请稍后重试...');toast(err,true);
    }
  );
}

// ===== 快捷指令 =====
function quickCmdStream(name){switchPage('dh');var inp=document.getElementById('chatInput');if(inp)inp.value=name;setTimeout(function(){sendMsg();},300);}
async function runQuickCmd(name){
  var output=document.getElementById('output-'+name);
  document.querySelectorAll('.cmd-output').forEach(function(o){if(o!==output)o.classList.remove('active');});
  if(output){output.classList.add('active');output.innerHTML='AI正在执行...';}
  var full='';
  await streamFetch(API_BASE+'/api/quick-command',{command:name,provider:currentModel},
    function(c){full+=c;if(output)output.innerHTML=renderMarkdown(full);},
    function(){},function(e){if(output)output.innerHTML='Error: '+e;toast(e,true);}
  );
}

// ===== 知识检索 =====
async function doSearch(){
  var inp=document.getElementById('searchInput'),txt=inp.value.trim();if(!txt)return;
  var result=document.getElementById('searchResult'),typing=document.getElementById('searchTyping'),status=document.getElementById('searchStatus'),btn=document.getElementById('searchBtn');
  result.innerHTML='';typing.classList.add('active');btn.disabled=true;status.textContent='检索中...';
  var full='';
  await streamFetch(API_BASE+'/api/search',{message:txt,provider:currentModel},
    function(c){full+=c;result.innerHTML=renderMarkdown(full);},
    function(){typing.classList.remove('active');btn.disabled=false;status.textContent='完成';},
    function(e){typing.classList.remove('active');btn.disabled=false;result.innerHTML='Error';toast(e,true);}
  );
}

// ===== PPT生成 =====
async function generatePPT(){
  var topic=document.getElementById('pptTopic').value.trim();if(!topic){toast('请输入主题',true);return;}
  var count=parseInt(document.getElementById('pptCount').value)||6,result=document.getElementById('pptResult'),btn=document.getElementById('pptBtn');
  result.classList.add('active');result.innerHTML='AI正在生成PPT...';btn.disabled=true;
  try{
    var resp=await fetch(API_BASE+'/api/generate-ppt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,slides_count:count,provider:currentModel})});
    var data=await resp.json();
    if(data.success){result.innerHTML='PPT生成成功！<br><a class="dl-link" href="'+API_BASE+'/api/download/'+encodeURIComponent(data.filename)+'" download>下载 '+escapeHtml(data.filename)+'</a>';}
    else{result.innerHTML='失败: '+(data.error||'未知错误');}
  }catch(e){result.innerHTML='Error: '+e.message;toast(e.message,true);}btn.disabled=false;
}

// ===== 流程图生成 =====
async function generateFlowchart(){
  var topic=document.getElementById('flowTopic').value.trim();if(!topic){toast('请输入主题',true);return;}
  var result=document.getElementById('flowResult'),btn=document.getElementById('flowBtn');
  result.classList.add('active');result.innerHTML='AI正在生成...';btn.disabled=true;
  try{
    var resp=await fetch(API_BASE+'/api/generate-flowchart',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:topic,provider:currentModel})});
    var data=await resp.json();
    if(data.success&&data.mermaid){var mc=data.mermaid;
      if(mc.startsWith('```')){var lines=mc.split('\n');lines=lines.slice(1);if(lines[lines.length-1]&&lines[lines.length-1].startsWith('```'))lines=lines.slice(0,-1);mc=lines.join('\n');}
      var id='mermaid-'+Date.now();result.innerHTML='<strong>'+escapeHtml(topic)+'</strong><div class="mermaid" id="'+id+'">'+escapeHtml(mc)+'</div><p style="font-size:10px;color:var(--text2);margin-top:8px">源码:<br><code>'+escapeHtml(mc)+'</code></p>';
      setTimeout(async function(){var el=document.getElementById(id);if(el){el.textContent=mc;el.removeAttribute('data-processed');try{await mermaid.run({nodes:[el]});}catch(e){el.innerHTML='<p style="color:red">渲染失败</p><pre>'+escapeHtml(mc)+'</pre>';}}},100);
    }else{result.innerHTML='生成失败';}
  }catch(e){result.innerHTML='Error: '+e.message;toast(e.message,true);}btn.disabled=false;
}

// ===== 工具 =====
function fmtTime(){var d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}
function escapeHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function renderMarkdown(text){
  var h=escapeHtml(text);h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');h=h.replace(/\*(.+?)\*/g,'<em>$1</em>');
  h=h.replace(/`([^`]+)`/g,'<code>$1</code>');h=h.replace(/^### (.+)$/gm,'<h4>$1</h4>');h=h.replace(/^## (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^# (.+)$/gm,'<h2>$1</h2>');h=h.replace(/^- (.+)$/gm,'• $1');h=h.replace(/\n/g,'<br>');return h;
}

// ===== 事件绑定 =====
document.getElementById('searchInput').addEventListener('keydown',function(e){if(e.key==='Enter')doSearch();});
document.getElementById('chatInput').addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();}});
// 模态标签点击
document.querySelectorAll('.mtag').forEach(function(t){t.addEventListener('click',function(){var i=document.getElementById('searchInput');if(i){i.value=this.textContent.trim();doSearch();}});});
// 语音按钮
var micBtn=document.querySelector('.dh-mic-btn');if(micBtn){micBtn.addEventListener('click',toggleVoice);}
// 图片输入
var imgInp=document.getElementById('imageInput');if(imgInp){imgInp.addEventListener('change',handleImageUpload);}

// ===== 初始化 =====
createParticles(); // 创建粒子
setTimeout(welcomeAnimation,500); // 延迟欢迎动画
console.log('文旅创新智脑 v2.0 | 数字人已就绪 | 语音/拍照/文字 | '+API_BASE);
// 30秒刷新粒子
setInterval(function(){if(document.getElementById('page-dh')&&document.getElementById('page-dh').classList.contains('active')){createParticles();}},30000);

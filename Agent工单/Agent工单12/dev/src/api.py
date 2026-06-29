"""
src/api.py - FastAPI REST API 服务
功能: 提供健康咨询 Agent 的 HTTP 访问接口。
      包括健康咨询、图谱统计、系统健康检查端点。
      CORS 开放，支持跨域访问。
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import logging
from contextlib import asynccontextmanager  # FastAPI 生命周期管理

from fastapi import FastAPI  # Web 框架
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件
from fastapi.responses import HTMLResponse  # HTML 响应
from pydantic import BaseModel, Field  # 请求/响应数据验证

from src.config import AppConfig, load_config  # 配置
from src.agent import MedicalAgent  # Agent 核心

logger = logging.getLogger(__name__)

# ---- 全局 Agent 实例 ----
_agent: MedicalAgent = None


# ---- FastAPI 生命周期 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理: 启动时初始化 Agent，关闭时释放资源。"""
    global _agent
    import os
    # 启动时: 加载配置并初始化 Agent
    # 查找 config.yaml：优先当前目录 → dev/ → 环境变量
    config_path = os.environ.get("CONFIG_PATH", "")
    if not config_path:
        for candidate in ["config.yaml", "dev/config.yaml"]:
            if os.path.exists(candidate):
                config_path = candidate
                break
    config = load_config(config_path) if config_path else load_config()
    _agent = MedicalAgent(config)
    logger.info("Medical Agent API 服务启动")
    yield  # 服务运行中
    # 关闭时: 释放资源
    if _agent:
        _agent.close()
    logger.info("Medical Agent API 服务关闭")


# ---- 创建 FastAPI 应用 ----
app = FastAPI(
    title="医疗健康咨询 Agent",
    description="基于知识图谱的智能医疗健康咨询系统",
    version="1.0.0",
    lifespan=lifespan,  # 生命周期
)

# ---- CORS 中间件 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)


# ---- 请求/响应模型 ----
class ConsultRequest(BaseModel):
    """健康咨询请求体。"""
    # 用户自然语言问题
    query: str = Field(
        ...,  # 必填
        min_length=1,  # 最少1字符
        max_length=500,  # 最多500字符
        description="用户健康咨询问题",
        examples=["百日咳的致病病原体是什么？"]  # 示例
    )


class ConsultResponse(BaseModel):
    """健康咨询响应体 — ReAct Agent 完整推理过程。"""
    query: str = Field(..., description="原始问题")
    reasoning_steps: list = Field(default_factory=list, description="Agent 思考步骤 (thought/action/observation)")
    answer: str = Field("", description="最终答案")
    latency_ms: float = Field(0.0, description="响应延迟(ms)")
    success: bool = Field(True, description="是否成功")


class HealthResponse(BaseModel):
    """健康检查响应体。"""
    status: str = "ok"
    version: str = "1.0.0"


# ---- API 端点 ----

@app.get("/", response_class=HTMLResponse)
async def chat_page():
    """医疗健康咨询 - 问答页面"""
    return """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>医疗健康咨询 Agent</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: #f0f4f8; min-height: 100vh; display: flex; justify-content: center; }
  .container { width: 100%; max-width: 800px; padding: 20px; display: flex; flex-direction: column; height: 100vh; }
  .header { text-align: center; padding: 15px 0; }
  .header h1 { font-size: 22px; color: #1a73e8; }
  .header p { font-size: 12px; color: #888; margin-top: 4px; }
  .chat-box { flex: 1; overflow-y: auto; background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .msg { margin-bottom: 16px; animation: fadeIn 0.3s; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .msg-user { display: flex; justify-content: flex-end; }
  .msg-user .bubble { background: #1a73e8; color: #fff; padding: 10px 16px; border-radius: 18px 18px 4px 18px; max-width: 75%; font-size: 15px; line-height: 1.5; word-break: break-word; }
  .msg-agent .bubble { background: #e8f0fe; color: #222; padding: 12px 18px; border-radius: 18px 18px 18px 4px; max-width: 85%; font-size: 14px; line-height: 1.7; word-break: break-word; }
  .msg-agent .meta { font-size: 11px; color: #999; margin-top: 4px; margin-left: 8px; }
  .msg-agent .disclaimer { font-size: 11px; color: #e8710a; margin-top: 6px; }
  .msg-error .bubble { background: #fce8e6; color: #c5221f; }
  .input-area { display: flex; gap: 10px; }
  .input-area input { flex: 1; padding: 14px 18px; border: 2px solid #ddd; border-radius: 24px; font-size: 15px; outline: none; transition: border 0.2s; }
  .input-area input:focus { border-color: #1a73e8; }
  .input-area button { padding: 14px 28px; background: #1a73e8; color: #fff; border: none; border-radius: 24px; font-size: 15px; cursor: pointer; transition: background 0.2s; }
  .input-area button:hover { background: #1557b0; }
  .input-area button:disabled { background: #a8c7fa; cursor: not-allowed; }
  .quick-asks { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .quick-asks span { background: #e8f0fe; color: #1a73e8; padding: 6px 14px; border-radius: 16px; font-size: 13px; cursor: pointer; transition: background 0.2s; white-space: nowrap; }
  .quick-asks span:hover { background: #d2e3fc; }
  .loading { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #999; animation: blink 1.4s infinite both; margin: 0 2px; }
  .loading:nth-child(2) { animation-delay: 0.2s; }
  .loading:nth-child(3) { animation-delay: 0.4s; }
  @keyframes blink { 0%,80%,100% { opacity: 0.2; } 40% { opacity: 1; } }
  .think-details { margin-bottom: 10px; font-size: 12px; background: #fafafa; border-radius: 8px; padding: 8px 12px; border: 1px solid #e0e0e0; }
  .think-details summary { cursor: pointer; color: #1a73e8; font-weight: 600; font-size: 13px; }
  .step { margin: 8px 0; padding: 6px 0; border-bottom: 1px dashed #eee; }
  .step:last-child { border-bottom: none; }
  .step-num { font-weight: 700; color: #1a73e8; font-size: 11px; }
  .step-thought { color: #555; margin: 2px 0; }
  .step-action { color: #333; margin: 2px 0; }
  .step-action code { background: #eee; padding: 1px 5px; border-radius: 3px; font-size: 11px; }
  .step-obs { color: #666; font-size: 11px; margin: 2px 0; max-height: 60px; overflow: hidden; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🏥 医疗健康咨询 Agent</h1>
    <p>基于 6143 种疾病知识图谱 · DeepSeek 驱动</p>
  </div>
  <div class="quick-asks" id="quickAsks">
    <span onclick="ask('百日咳的致病病原体是什么？')">🦠 百日咳病原体</span>
    <span onclick="ask('百日咳首选什么抗生素？')">💊 百日咳用药</span>
    <span onclick="ask('百日咳怎么传播的？')">🤧 百日咳传播</span>
    <span onclick="ask('百日咳隔离多久？')">🏠 百日咳隔离</span>
    <span onclick="ask('百日咳不能吃什么？')">🍽 百日咳饮食</span>
    <span onclick="ask('大叶性肺炎有什么症状？')">🫁 大叶性肺炎</span>
  </div>
  <div class="chat-box" id="chatBox">
    <div class="msg msg-agent">
      <div class="bubble">👋 你好！我是医疗健康咨询助手。<br>请在上方选择快捷问题，或直接输入你的健康问题。</div>
    </div>
  </div>
  <div class="input-area">
    <input id="queryInput" type="text" placeholder="输入健康问题，如：百日咳有什么症状？" onkeydown="if(event.key==='Enter')send()">
    <button id="sendBtn" onclick="send()">发送</button>
  </div>
</div>
<script>
function ask(q) {
  document.getElementById('queryInput').value = q;
  send();
}
function renderSteps(steps) {
  if (!steps || !steps.length) return '';
  let h = '<details class="think-details"><summary>🧠 Agent 思考过程 (' + steps.length + ' 步)</summary>';
  steps.forEach((s, i) => {
    h += '<div class="step">';
    h += '<div class="step-num">第' + (i+1) + '步</div>';
    h += '<div class="step-thought">💭 <b>思考:</b> ' + escapeHtml(s.thought || '') + '</div>';
    h += '<div class="step-action">🔧 <b>行动:</b> <code>' + escapeHtml(s.action || '') + '</code>';
    if (s.action_input) h += ' → <span>' + escapeHtml(String(s.action_input).substring(0, 100)) + '</span>';
    h += '</div>';
    if (s.observation) h += '<div class="step-obs">📋 <b>观察:</b> ' + escapeHtml(String(s.observation).substring(0, 200)) + '</div>';
    h += '</div>';
  });
  h += '</details>';
  return h;
}

async function send() {
  const input = document.getElementById('queryInput');
  const btn = document.getElementById('sendBtn');
  const query = input.value.trim();
  if (!query) return;
  input.disabled = true;
  btn.disabled = true;
  btn.textContent = 'Agent思考中...';
  const chat = document.getElementById('chatBox');
  chat.innerHTML += '<div class="msg msg-user"><div class="bubble">' + escapeHtml(query) + '</div></div>';
  chat.innerHTML += '<div id="loading" class="msg msg-agent"><div class="bubble"><span class="loading"></span><span class="loading"></span><span class="loading"></span> Agent 正在自主思考和查询...</div></div>';
  chat.scrollTop = chat.scrollHeight;
  try {
    const start = Date.now();
    const resp = await fetch('/consult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query })
    });
    const data = await resp.json();
    const el = document.getElementById('loading');
    if (el) el.remove();
    const latency = ((Date.now() - start) / 1000).toFixed(1);
    let html = '<div class="msg msg-agent">';
    html += renderSteps(data.reasoning_steps);
    html += '<div class="bubble">' + escapeHtml(data.answer || '无回答').replace(/\\n/g, '<br>') + '</div>';
    html += '<div class="meta">🤖 ReAct Agent · ' + (data.reasoning_steps ? data.reasoning_steps.length : 0) + ' 步推理 · ⚡ ' + latency + 's</div>';
    html += '<div class="disclaimer">⚠ 本回答仅供参考，具体诊疗请咨询专业医生</div></div>';
    chat.innerHTML += html;
  } catch(e) {
    const el = document.getElementById('loading');
    if (el) el.remove();
    chat.innerHTML += '<div class="msg msg-error"><div class="bubble">❌ 请求失败: ' + e.message + '</div></div>';
  }
  chat.scrollTop = chat.scrollHeight;
  input.disabled = false;
  btn.disabled = false;
  btn.textContent = '发送';
  input.value = '';
  input.focus();
}
function escapeHtml(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
</script>
</body>
</html>"""


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    系统健康检查端点。

    返回:
        HealthResponse: 系统状态
    """
    return HealthResponse(status="ok")


@app.post("/consult", response_model=ConsultResponse)
async def consult(req: ConsultRequest):
    """
    健康咨询端点 — Agent 完整推理链路。

    接收用户自然语言问题，经过:
    实体抽取 → Cypher 生成 → 图谱查询 → LLM 答案生成
    返回结构化的完整响应。

    参数:
        req: ConsultRequest — 包含用户问题

    返回:
        ConsultResponse — 包含答案和推理中间结果
    """
    # 验证 Agent 已初始化
    if _agent is None:
        return ConsultResponse(
            query=req.query,
            answer="服务未就绪，请稍后重试",
            success=False,
        )
    # 调用 Agent 推理
    result = _agent.consult(req.query)
    # 构建 API 响应
    return ConsultResponse(
        query=result.query,
        reasoning_steps=result.reasoning_steps,
        answer=result.answer,
        latency_ms=round(result.latency_ms, 1),
        success=result.success,
    )


@app.get("/kg/stats")
async def kg_stats():
    """
    知识图谱统计端点 — 返回图谱中各类实体的数量。

    返回:
        包含各实体类型计数的字典
    """
    if _agent is None:
        return {"status": "not_ready"}
    # 尝试执行统计查询
    try:
        result = _agent.graph_query.query(
            "MATCH (d:Disease) RETURN count(d) AS disease_count",
            "统计"
        )
        disease_count = result[0].get("disease_count", "0") if result else "0"
        return {
            "status": "ok",
            "disease_count": disease_count,
            "neo4j_available": _agent._neo4j_available,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def start_server(config: AppConfig = None, port: int = None) -> None:
    """
    启动 FastAPI 服务（供 run.py 调用）。

    参数:
        config: 可选的预加载配置
        port: 可选的服务端口
    """
    import uvicorn

    # 使用配置中的端口或默认8003
    host = config.server.host if config else "0.0.0.0"
    port = port or (config.server.port if config else 8003)
    logger.info(f"启动服务: http://{host}:{port}")
    # 启动 uvicorn ASGI 服务器
    uvicorn.run(
        "src.api:app",  # 模块:应用实例
        host=host,  # 监听地址
        port=port,  # 监听端口
        log_level="info",  # 日志级别
    )

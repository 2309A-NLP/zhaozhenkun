"""该文件用于提供 FastAPI 服务入口，暴露统一问答接口。"""

# 导入 JSON 模块，用于构造 SSE 事件数据。
import json
# 导入 Uvicorn 模块，用于在直接运行脚本时启动服务。
import uvicorn

# 导入 FastAPI 框架，用于构建 HTTP 服务。
from fastapi import FastAPI
# 导入 HTML 响应类型，用于返回前端测试页面。
from fastapi.responses import HTMLResponse
# 导入流式响应类型，用于返回 SSE 事件流。
from fastapi.responses import StreamingResponse
# 导入 Pydantic 模型，用于校验请求与响应结构。
from pydantic import BaseModel

# 导入配置加载函数，用于读取服务监听地址与端口。
from development.core.config import load_config
# 导入智能体服务，用于处理实际问答流程。
from development.services.agent_service import AgentService

# 初始化 FastAPI 应用对象。
app = FastAPI(title="Skills Agent 24")
# 初始化全局智能体服务实例。
service = AgentService()


# 定义请求体模型，用于接收前端传来的会话请求。
class ChatRequest(BaseModel):
    # 保存用户提问内容。
    query: str
    # 保存会话编号，默认为 default。
    session_id: str = "default"


# 定义健康检查接口，便于部署阶段快速探活。
@app.get("/health")
def health() -> dict[str, str]:
    # 返回简单健康状态结果。
    return {"status": "ok"}


# 定义聊天接口，用于处理领域智能体问答。
@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    # 调用智能体服务处理当前请求。
    response = service.handle(query=request.query, session_id=request.session_id)
    # 返回序列化后的结构化响应。
    return response.to_dict()


# 定义流式聊天接口，用于通过 SSE 持续返回生成结果。
@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    # 定义内部事件生成器，用于逐条输出 SSE 数据。
    def event_stream():
        # 迭代智能体服务返回的流式事件。
        for event in service.stream_handle(query=request.query, session_id=request.session_id):
            # 将事件编码为单行 JSON 文本。
            payload = json.dumps(event, ensure_ascii=False)
            # 按 SSE 协议输出 data 行与空行。
            yield f"data: {payload}\n\n"
    # 返回标准的 SSE 流式响应对象。
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# 定义前端测试页面接口，便于手工联调普通与流式能力。
@app.get("/demo", response_class=HTMLResponse)
def demo_page() -> str:
    # 返回内联测试页面 HTML 内容。
    return """
<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Skills Agent 24 Demo</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 960px; margin: 24px auto; padding: 0 16px; }
    textarea, input, button { width: 100%; box-sizing: border-box; margin-top: 8px; }
    textarea { min-height: 96px; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; }
    pre { white-space: pre-wrap; word-break: break-word; background: #fafafa; padding: 12px; border-radius: 8px; }
    button { padding: 10px 12px; cursor: pointer; }
  </style>
</head>
<body>
  <h1>Skills Agent 24 测试页面</h1>
  <label>会话 ID</label>
  <input id=\"sessionId\" value=\"demo-session\" />
  <label>问题</label>
  <textarea id=\"query\">请帮我从北京站到故宫怎么走，并告诉我今天北京天气</textarea>
  <div class=\"row\">
    <button id=\"sendNormal\">发送普通请求</button>
    <button id=\"sendStream\">发送流式请求</button>
  </div>
  <div class=\"row\" style=\"margin-top:16px;\">
    <div class=\"card\">
      <h3>普通响应</h3>
      <pre id=\"normalOutput\"></pre>
    </div>
    <div class=\"card\">
      <h3>流式响应</h3>
      <pre id=\"streamOutput\"></pre>
    </div>
  </div>
  <script>
    const queryEl = document.getElementById('query');
    const sessionEl = document.getElementById('sessionId');
    const normalOutput = document.getElementById('normalOutput');
    const streamOutput = document.getElementById('streamOutput');

    async function sendNormal() {
      normalOutput.textContent = '请求中...';
      try {
        const response = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: queryEl.value, session_id: sessionEl.value })
        });
        const data = await response.json();
        normalOutput.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        normalOutput.textContent = '普通请求失败：' + error.message;
        console.error(error);
      }
    }

    async function sendStream() {
      streamOutput.textContent = '流式请求中...\\n';
      try {
        const response = await fetch('/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: queryEl.value, session_id: sessionEl.value })
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let answer = '';
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\\n\\n');
          buffer = events.pop() || '';
          for (const block of events) {
            const line = block.split('\\n').find(item => item.startsWith('data: '));
            if (!line) continue;
            const payload = JSON.parse(line.slice(6));
            if (payload.type === 'meta') {
              streamOutput.textContent = '技能: ' + payload.skills_used.join(', ') + '\\n\\n';
            }
            if (payload.type === 'chunk') {
              answer += payload.content;
              streamOutput.textContent += payload.content;
            }
            if (payload.type === 'done') {
              streamOutput.textContent += '\\n\\n[完成]';
            }
          }
        }
      } catch (error) {
        streamOutput.textContent += '\\n\\n流式请求失败：' + error.message;
        console.error(error);
      }
    }

    document.getElementById('sendNormal').addEventListener('click', sendNormal);
    document.getElementById('sendStream').addEventListener('click', sendStream);
  </script>
</body>
</html>
    """


# 定义脚本直启入口，便于直接运行当前文件启动服务。
def main() -> None:
    # 读取当前服务监听配置。
    config = load_config()
    # 组装基础访问地址，便于用户直接点击。
    base_url = f"http://{config.host}:{config.port}"
    # 打印首页访问地址，便于在 IDE 控制台点击打开。
    print(f"服务地址：{base_url}", flush=True)
    # 打印测试页面地址，便于直接进入联调页面。
    print(f"测试页面：{base_url}/demo", flush=True)
    # 使用当前 app 对象直接启动 Uvicorn 服务。
    uvicorn.run(app, host=config.host, port=config.port)


# 在脚本被直接运行时启动 FastAPI 服务。
if __name__ == "__main__":
    # 调用脚本直启入口。
    main()

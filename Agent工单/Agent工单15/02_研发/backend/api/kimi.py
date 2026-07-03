"""
================================================================================
Kimi（Moonshot）API —— 需求分析 / 医学报告生成
工单要求：使用 Kimi 进行需求分析，产出分析报告
================================================================================
"""
from fastapi import APIRouter  # 导入 FastAPI 的路由器，用于定义 API 路由分组
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式的 HTTP 响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于请求数据模型定义和字段校验
from services.llm_client import get_kimi_client  # 导入 Kimi（Moonshot）客户端工厂函数，用于需求分析和对话

router = APIRouter(prefix="/api/kimi", tags=["Kimi 需求分析"])  # 创建 API 路由器，前缀 /api/kimi，Swagger 标签为"Kimi 需求分析"


class AnalyzeRequest(BaseModel):  # 定义需求分析请求数据模型
    content: str = Field(..., min_length=1, max_length=10000, description="待分析的需求文档/内容")  # 必填：待分析的需求文档或内容，最大 10000 字符
    task: str = Field(default="需求分析", description="分析任务类型")  # 分析任务类型，默认为"需求分析"


class ChatRequest(BaseModel):  # 定义 Kimi 对话请求数据模型
    message: str = Field(..., min_length=1, max_length=5000, description="输入消息")  # 必填：用户输入消息，最大 5000 字符


@router.post("/analyze")  # 注册 POST 路由：/api/kimi/analyze，Kimi 需求分析入口
async def analyze(req: AnalyzeRequest):  # 定义异步需求分析接口，接收 AnalyzeRequest 请求体
    """Kimi 需求分析：输入文档 → 结构化分析报告"""  # 接口文档字符串
    kimi = get_kimi_client()  # 获取 Kimi（Moonshot）客户端实例
    result = kimi.analyze(req.content, req.task)  # 调用 Kimi 分析接口：传入待分析内容和任务类型
    return JSONResponse({  # 返回 JSON 格式的分析结果
        "success": "error" not in result,  # 根据结果中是否包含 error 字段判断是否成功
        "report": result["content"],  # 返回生成的分析报告内容
        "model": result["model"],  # 返回使用的模型名称
        "task": req.task,  # 返回分析任务类型
        "latency_ms": result.get("latency_ms", 0),  # 返回请求延迟（毫秒），缺失时默认为 0
        "error": result.get("error", ""),  # 返回错误信息，缺失时默认为空字符串
    })


@router.post("/chat")  # 注册 POST 路由：/api/kimi/chat，Kimi 对话入口（备选推理引擎）
async def chat(req: ChatRequest):  # 定义异步 Kimi 对话接口，接收 ChatRequest 请求体
    """Kimi 对话（备选推理引擎）"""  # 接口文档字符串：说明 Kimi 作为备选推理引擎
    kimi = get_kimi_client()  # 获取 Kimi（Moonshot）客户端实例
    result = kimi.chat([{"role": "user", "content": req.message}],  # 调用 Kimi chat 接口：构造用户消息列表
                       system="你是专业的医疗需求分析师，用中文回复。")  # 系统提示词：设定为专业的医疗需求分析师
    return JSONResponse({  # 返回 JSON 格式的对话结果
        "success": "error" not in result,  # 根据结果中是否包含 error 判断是否成功
        "reply": result["content"],  # 返回 AI 的回复内容
        "model": result["model"],  # 返回使用的模型名称
        "latency_ms": result.get("latency_ms", 0),  # 返回请求延迟（毫秒），缺失时默认为 0
    })

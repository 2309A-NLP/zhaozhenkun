"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
健康助理 API —— 挂号管理 + 健康咨询 + 导诊问答
"""
from fastapi import APIRouter  # 导入 FastAPI 的路由器，用于定义 API 路由分组
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式的 HTTP 响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于请求数据模型定义和字段校验
from services.llm_client import get_deepseek_client  # 导入 DeepSeek 客户端工厂函数，用于文本对话推理

router = APIRouter(prefix="/api/assistant", tags=["健康助理"])  # 创建 API 路由器，前缀 /api/assistant，Swagger 标签为"健康助理"


class ChatRequest(BaseModel):  # 定义对话请求数据模型，继承 Pydantic BaseModel
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入的自然语言消息")  # 必填：用户输入消息，长度 1-2000 字符


SYSTEM_PROMPT = """你是一个智能医疗健康助理，名叫"小医"，专门帮助患者完成以下任务：

## 1. 挂号预约
当用户想挂号时，你需要收集以下信息：
- 就诊人姓名
- 科室（儿科/内科/外科/妇产科/骨科/眼科/耳鼻喉科/皮肤科等）
- 医生级别（普通/专家/主任）
- 期望时间（上午/下午/具体时间）
然后给出挂号结果确认。

## 2. 健康咨询
根据用户描述的症状，给出初步分析和就诊建议。
- 分析可能的病因
- 建议挂哪个科室
- 给出日常护理建议
- **重要：你是AI助手，不能替代医生诊断，请始终建议用户就医**

## 3. 导诊问答
回答医院相关的常见问题：
- 科室位置
- 就诊流程
- 检查注意事项

## 回复格式要求：
- 友好、专业、简洁
- 用中文回复
- 如果需要挂号，给出确认信息（挂号成功模拟）
- 始终包含免责声明
"""


@router.post("/chat")  # 注册 POST 路由：/api/assistant/chat，健康助理对话入口
async def chat(req: ChatRequest):  # 定义异步健康助理对话接口，接收 ChatRequest 请求体
    """健康助理对话——挂号预约+健康咨询+导诊"""  # 接口文档字符串：说明功能覆盖挂号、咨询和导诊三类场景
    ds = get_deepseek_client()  # 获取 DeepSeek 客户端实例，用于文本对话生成
    messages = [{"role": "user", "content": req.message}]  # 构建消息列表：role 为 user，content 为用户输入消息
    result = ds.chat(messages, system=SYSTEM_PROMPT, max_tokens=1024)  # 调用 DeepSeek chat 接口，传入系统提示词和最大 token 数

    return JSONResponse({  # 返回 JSON 格式的对话响应
        "success": "error" not in result,  # 根据结果中是否包含 error 字段判断是否成功
        "reply": result["content"],  # 返回 AI 生成的回复内容
        "model": result["model"],  # 返回使用的模型名称
        "latency_ms": result.get("latency_ms", 0),  # 返回请求延迟（毫秒），缺失时默认为 0
        "error": result.get("error", ""),  # 返回错误信息，缺失时默认为空字符串
    })

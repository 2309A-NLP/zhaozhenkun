"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
健康助理 API —— 挂号管理 + 健康咨询 + 导诊问答
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from services.llm_client import get_deepseek_client

router = APIRouter(prefix="/api/assistant", tags=["健康助理"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入的自然语言消息")


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


@router.post("/chat")
async def chat(req: ChatRequest):
    """健康助理对话——挂号预约+健康咨询+导诊"""
    ds = get_deepseek_client()
    messages = [{"role": "user", "content": req.message}]
    result = ds.chat(messages, system=SYSTEM_PROMPT, max_tokens=1024)

    return JSONResponse({
        "success": "error" not in result,
        "reply": result["content"],
        "model": result["model"],
        "latency_ms": result.get("latency_ms", 0),
        "error": result.get("error", ""),
    })

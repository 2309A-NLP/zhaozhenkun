"""
================================================================================
文件名:   api/asr_core.py
功能:     实时语音识别核心路由 —— WebSocket 实时 ASR、后处理、翻译
          （拆分自 asr.py）
所属项目: 医疗智能体-影像分析系统
路由列表:
  WS   /api/asr/ws/realtime            实时语音识别 WebSocket ★核心★
  POST /api/asr/process                后处理转录文本（摘要/速览/待办/关键词）
  POST /api/asr/translate              翻译文本
================================================================================
"""
import json
import logging
import asyncio
import uuid
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.tingwu_client import get_tingwu_client

_log = logging.getLogger("medical_agent.asr")

router = APIRouter(prefix="/api/asr", tags=["实时语音识别（通义听悟对接）"])


# ================================================================
# 请求模型
# ================================================================
class ProcessRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=50000,
                            description="语音转录全文")
    options: list = Field(default=["summary", "chapters", "keywords", "todos", "qa"],
                          description="需要的后处理类型")


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000,
                      description="待翻译文本")
    target_lang: str = Field(default="英文", description="目标语言")


# ================================================================
# 端点 1: 实时语音识别 WebSocket ★核心★
# ================================================================
@router.websocket("/ws/realtime")
async def realtime_asr_ws(ws: WebSocket):
    """
    实时语音识别 WebSocket 端点

    浏览器端:
      1. 连接 ws://localhost:8080/api/asr/ws/realtime
      2. 发送二进制 PCM 音频帧 (16kHz, 16bit, 单声道)
      3. 接收 JSON 文本消息: {"type":"partial","text":"中间识别..."}
      4. 接收 JSON: {"type":"final","text":"最终识别结果"}
      5. 关闭连接后，后端自动完成后处理

    前端实现参考: 使用 AudioContext + MediaRecorder 采集音频
    """
    from api.asr_tasks import _ensure_cleanup, _tasks  # 惰性导入避免循环引用

    await ws.accept()
    _log.info("WebSocket 客户端已连接")
    _ensure_cleanup()  # 确保后台清理任务已启动

    tingwu = get_tingwu_client()
    full_text = []          # 累积全部识别文本
    sentence_count = 0     # 句子计数

    async def audio_generator():
        """从浏览器 WebSocket 接收音频帧"""
        try:
            while True:
                try:
                    data = await ws.receive()
                except WebSocketDisconnect:
                    break  # 浏览器断开，停止接收
                except RuntimeError as e:
                    if "disconnect" in str(e).lower():
                        break  # ASGI 断开消息
                    _log.error("音频接收 RuntimeError: %s", e)
                    break
                if data["type"] == "websocket.receive":
                    if "bytes" in data:
                        yield data["bytes"]      # 二进制音频帧
                    elif "text" in data:
                        # 控制消息（如 stop）
                        ctrl = json.loads(data["text"])
                        if ctrl.get("action") == "stop":
                            break
        except WebSocketDisconnect:
            pass
        except GeneratorExit:
            pass  # 生成器被提前关闭（浏览器断开导致）
        except Exception as e:
            _log.error("音频接收异常: %s", e)

    try:
        # 调用实时 ASR
        async for result in tingwu.realtime_asr(audio_generator()):
            if result["type"] in ("partial", "final"):
                full_text.append(result["text"])
                if result["type"] == "final":
                    sentence_count += 1
                # 实时推送给浏览器
                try:
                    await ws.send_text(json.dumps(result, ensure_ascii=False))
                except Exception:
                    break  # 浏览器已断开，停止发送

            elif result["type"] == "done":
                try:
                    await ws.send_text(json.dumps({
                        "type": "done",
                        "task_id": result.get("task_id", ""),
                        "sentence_count": sentence_count
                    }, ensure_ascii=False))
                except Exception:
                    pass
                break

            elif result["type"] == "error":
                try:
                    await ws.send_text(json.dumps(result, ensure_ascii=False))
                except Exception:
                    pass
                break

    except WebSocketDisconnect:
        _log.info("客户端断开连接")
    except Exception as e:
        _log.error("实时ASR异常: %s", e)

    # 保存完整转录文本供后处理
    complete_text = "".join(full_text)
    if complete_text:
        task_id = uuid.uuid4().hex[:12]
        _tasks[task_id] = {
            "status": "pending",
            "transcript": complete_text,
            "created_at": time.time()
        }
        # 异步触发后处理
        asyncio.create_task(_do_postprocess(task_id, complete_text))

    try:
        await ws.close()
    except Exception:
        pass


# ================================================================
# 端点 2: 后处理转录文本（摘要/速览/待办/关键词）
# ================================================================
@router.post("/process")
async def process_transcript(req: ProcessRequest):
    """
    后处理语音转录文本 —— 生成摘要、章节速览、待办事项、关键词等

    此接口不依赖通义听悟 AK/SK，使用 DeepSeek 完成所有后处理
    """
    tingwu = get_tingwu_client()
    result = tingwu.process_transcript(req.transcript)
    result["success"] = "error" not in result
    result["latency_ms"] = 0
    return JSONResponse(result)


# ================================================================
# 端点 3: 翻译
# ================================================================
@router.post("/translate")
async def translate(req: TranslateRequest):
    """翻译文本 —— 使用 DeepSeek 进行翻译"""
    tingwu = get_tingwu_client()
    result = tingwu.translate_text(req.text, req.target_lang)
    return JSONResponse({
        "success": result.get("success", False),
        "translation": result.get("translation", ""),
        "target_lang": req.target_lang,
        "error": result.get("error", ""),
    })


# ================================================================
# 内部函数：异步后处理
# ================================================================
async def _do_postprocess(task_id: str, transcript: str):
    """异步执行后处理（在后台线程中运行）"""
    from api.asr_tasks import _tasks  # 惰性导入避免循环引用

    try:
        loop = asyncio.get_event_loop()
        # 在线程池中运行同步的 DeepSeek 调用
        result = await loop.run_in_executor(
            None, get_tingwu_client().process_transcript, transcript
        )
        if task_id in _tasks:
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["result"] = result
            _tasks[task_id]["done_at"] = time.time()
            _log.info("后处理完成: task_id=%s", task_id)
    except Exception as e:
        _log.error("后处理异常: task_id=%s error=%s", task_id, e)
        if task_id in _tasks:
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = str(e)

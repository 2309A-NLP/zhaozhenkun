"""
================================================================================
文件名:   api/asr_tasks.py
功能:     语音识别任务管理 —— 任务创建/轮询/回调/上传/通义听悟接口/数字人语音管线
          （拆分自 asr.py）
所属项目: 医疗智能体-影像分析系统
路由列表:
  POST /api/asr/task/create            创建后处理任务 → 返回 task_id
  GET  /api/asr/task/{task_id}         轮询任务结果
  POST /api/asr/callback               回调接收端点（通义听悟回调）
  POST /api/asr/upload                 上传音频文件
  POST /api/asr/tingwu/create          通义听悟 CreateTask（官方规范）
  GET  /api/asr/tingwu/{task_id}       通义听悟 GetTaskInfo（官方规范）
  POST /api/asr/voice                  数字人语音管线（ASR→Agent→TTS）
================================================================================
"""
import logging
import asyncio
import uuid
import time

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.asr_core import router  # 在 core 模块的 router 上注册路由

_log = logging.getLogger("medical_agent.asr")

# ================================================================
# 内存任务存储（轮询用）—— 含 TTL 自动清理，防止内存泄漏
# ================================================================
_tasks: dict = {}  # task_id → {"status":"processing|done","result":{...}}
_TASK_TTL_SECONDS = 3600  # 1 小时后自动清理已完成/失败/过期任务
_CLEANUP_INTERVAL = 300    # 每 5 分钟执行一次清理

def _cleanup_expired_tasks():
    """清理过期的内存任务，防止长时间运行内存泄漏"""
    now = time.time()
    expired = []
    for tid, t in _tasks.items():
        age = now - t.get("created_at", now)
        # 已完成/失败/错误的任务，超过 TTL 则清理
        if t.get("status") in ("done", "error") and age > _TASK_TTL_SECONDS:
            expired.append(tid)
        # 处理中/pending 但超过 2 倍 TTL（可能已卡死）的任务也清理
        elif t.get("status") in ("processing", "pending") and age > _TASK_TTL_SECONDS * 2:
            expired.append(tid)
    for tid in expired:
        del _tasks[tid]
    if expired:
        _log.info("清理过期任务: %d 个 (剩余 %d)", len(expired), len(_tasks))

async def _periodic_cleanup():
    """周期性后台清理协程"""
    while True:
        await asyncio.sleep(_CLEANUP_INTERVAL)
        try:
            _cleanup_expired_tasks()
        except Exception as e:
            _log.error("任务清理异常: %s", e)

# 在模块加载时启动后台清理任务（通过 asyncio.create_task）
# 但需要事件循环已运行，所以延迟到首次请求时启动
_cleanup_started = False

def _ensure_cleanup():
    """确保清理任务已启动（惰性启动，避免在导入时创建 asyncio task）"""
    global _cleanup_started
    if not _cleanup_started:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_periodic_cleanup())
                _cleanup_started = True
                _log.info("任务 TTL 清理已启动 (TTL=%ds, 间隔=%ds)",
                          _TASK_TTL_SECONDS, _CLEANUP_INTERVAL)
        except RuntimeError:
            pass  # 事件循环尚未启动，等待首次调用

# ================================================================
# 请求模型
# ================================================================
class TaskCreateRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=50000)

class CallbackRequest(BaseModel):
    task_id: str = Field(..., description="通义听悟任务ID")
    status: str = Field(default="completed", description="任务状态")
    result: dict = Field(default={}, description="回调结果数据")

class VoiceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000,
                      description="用户语音识别后的文本")
    enable_tts: bool = Field(default=True, description="启用TTS语音合成")
    enable_summary: bool = Field(default=False, description="启用会议纪要")
    voice: str = Field(default="xiaoxiao", description="TTS音色")

# ================================================================
# 端点: 创建后处理任务（触发 DeepSeek 分析）
# ================================================================
@router.post("/task/create")
async def create_task(req: TaskCreateRequest):
    """
    创建后处理任务 → 返回 task_id

    前端拿到 task_id 后，用 GET /api/asr/task/{task_id} 轮询结果
    """
    from api.asr_core import _do_postprocess  # 惰性导入避免循环引用

    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {
        "status": "processing",
        "transcript": req.transcript,
        "created_at": time.time()
    }
    # 异步执行后处理
    asyncio.create_task(_do_postprocess(task_id, req.transcript))
    return JSONResponse({
        "success": True,
        "task_id": task_id,
        "message": "任务已创建，请通过 GET /api/asr/task/{task_id} 轮询结果"
    })

# ================================================================
# 端点: 轮询任务结果
# ================================================================
@router.get("/task/{task_id}")
async def poll_task(task_id: str):
    """
    轮询任务结果 —— 前端每 2 秒轮询一次

    返回:
      {"status":"processing"}  → 继续轮询
      {"status":"done", "result":{...}}  → 完成后返回摘要/速览/关键词等
    """
    task = _tasks.get(task_id)
    if not task:
        return JSONResponse({"status": "not_found",
                             "error": "任务不存在或已过期"}, status_code=404)
    if task["status"] == "done":
        return JSONResponse(task)
    return JSONResponse({"status": task["status"],
                         "task_id": task_id,
                         "message": "处理中，请继续轮询..."})

# ================================================================
# 端点: 回调接收端点（通义听悟回调 / 模拟回调）
# ================================================================
@router.post("/callback")
async def callback_receiver(req: CallbackRequest):
    """回调接收端点 —— 通义听悟完成后 POST 到此 URL"""
    _log.info("收到回调: task_id=%s status=%s", req.task_id, req.status)
    task = _tasks.get(req.task_id)
    if task:
        task["status"] = "done"
        task["result"] = req.result
        task["callback_time"] = time.time()
        return JSONResponse({"success": True, "message": "回调已处理"})
    # 任务不存在时也返回成功（通义听悟要求）
    return JSONResponse({"success": True,
                         "message": "回调已接收（任务可能已清理）"})

# ================================================================
# 端点: 上传音频文件
# ================================================================
@router.post("/upload")
async def upload_audio(file: bytes = None):
    """
    上传音频文件（备用方式 —— 先上传再转录）

    使用 multipart/form-data 上传，字段名: file
    支持格式: WAV, MP3, PCM
    """
    # 此端点用于上传完整音频文件后进行转录
    # 实际实现可扩展为存储音频并触发异步转录
    return JSONResponse({
        "success": True,
        "message": "音频文件已接收（文件转录功能开发中，建议使用实时 WebSocket 模式）"
    })

# ================================================================
# 端点: 通义听悟 CreateTask（官方规范）
# ================================================================
@router.post("/tingwu/create")
async def tingwu_create_task(audio_url: str = "",
                             source_language: str = "cn",
                             enable_summarization: bool = True,
                             enable_chapter: bool = True,
                             enable_keywords: bool = True,
                             callback_url: str = ""):
    """
    通义听悟 CreateTask —— 按照官方接口规范

    POST /api/asr/tingwu/create?audio_url=xxx&enable_summarization=true

    状态机: NEW → QUEUEING → RUNNING → SUCCESS/FAILED
    查询: GET /api/asr/tingwu/{task_id}
    """
    from services.tingwu_client import get_tingwu_client

    tingwu = get_tingwu_client()
    result = tingwu.create_task(
        audio_url=audio_url,
        source_language=source_language,
        enable_summarization=enable_summarization,
        enable_chapter=enable_chapter,
        enable_keywords=enable_keywords,
        callback_url=callback_url
    )
    # 存储到内存任务表
    if result.get("success") and result.get("task_id"):
        _tasks[result["task_id"]] = {
            "status": "NEW",
            "created_at": time.time(),
            "params": {"audio_url": audio_url, "source_language": source_language}
        }
    return JSONResponse(result)

# ================================================================
# 端点: 通义听悟 GetTaskInfo（官方规范）
# ================================================================
@router.get("/tingwu/{task_id}")
async def tingwu_get_task_info(task_id: str):
    """
    通义听悟 GetTaskInfo —— 按照官方接口规范

    GET /api/asr/tingwu/{task_id}

    返回:
    {
      "task_id": "xxx",
      "status": "RUNNING",  // NEW|QUEUEING|RUNNING|SUCCESS|FAILED
      "result": {            // status=SUCCESS 时有值
        "transcription": "...",
        "summarization": "...",
        "chapter_notes": [...],
        "keywords": [...]
      }
    }
    """
    from services.tingwu_client import get_tingwu_client

    # 先查内存任务表
    task = _tasks.get(task_id)
    if task and task.get("status") == "done":
        return JSONResponse({
            "task_id": task_id,
            "status": "SUCCESS",
            "result": task.get("result", {})
        })
    if task:
        # 映射内存状态到通义听悟状态
        status_map = {"processing": "RUNNING", "pending": "QUEUEING",
                      "NEW": "QUEUEING", "error": "FAILED"}
        tingwu_status = status_map.get(task.get("status", ""), "RUNNING")
        return JSONResponse({
            "task_id": task_id,
            "status": tingwu_status,
            "message": f"任务{tingwu_status}"
        })

    # 内存中没有，尝试通义听悟查询
    tingwu = get_tingwu_client()
    result = tingwu.get_task_info(task_id)
    return JSONResponse(result)

# ================================================================
# 端点: 数字人语音管线（ASR→Agent→TTS）
# ================================================================
@router.post("/voice")
async def voice_pipeline(req: VoiceRequest):
    """数字人语音管线: Agent→TTS, 返回文字+Base64音频"""
    from services.tts_client import get_voice_pipeline
    pipeline = get_voice_pipeline()
    result = await pipeline.process(
        user_text=req.text,
        enable_tts=req.enable_tts,
        enable_summary=req.enable_summary
    )
    result["success"] = True
    return JSONResponse(result)

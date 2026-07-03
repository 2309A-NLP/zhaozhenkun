"""
================================================================================
文件名:   api/asr.py
功能:     实时语音识别与会议纪要 API —— 兼容性重导出模块
          （原实现已拆分至 asr_core.py + asr_tasks.py）
所属项目: 医疗智能体-影像分析系统
================================================================================
"""
# 核心路由端点（WebSocket、后处理、翻译）
from api.asr_core import (
    router,
    ProcessRequest,
    TranslateRequest,
    realtime_asr_ws,
    process_transcript,
    translate,
    _do_postprocess,
)

# 任务管理端点（创建/轮询/回调/上传/通义听悟/数字人语音管线）
from api.asr_tasks import (
    TaskCreateRequest,
    CallbackRequest,
    VoiceRequest,
    create_task,
    poll_task,
    callback_receiver,
    upload_audio,
    tingwu_create_task,
    tingwu_get_task_info,
    voice_pipeline,
    _tasks,
    _ensure_cleanup,
)

# 对 from api.asr import * 提供显式 __all__
__all__ = [
    "router",
    "ProcessRequest",
    "TranslateRequest",
    "TaskCreateRequest",
    "CallbackRequest",
    "VoiceRequest",
    "realtime_asr_ws",
    "process_transcript",
    "translate",
    "create_task",
    "poll_task",
    "callback_receiver",
    "upload_audio",
    "tingwu_create_task",
    "tingwu_get_task_info",
    "voice_pipeline",
]

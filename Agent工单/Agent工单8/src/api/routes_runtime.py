"""
src/api/routes_runtime.py - 运行时控制路由
功能: 注册健康检查、RTMP 控制、会话设置、性能指标、声音克隆和头像上传接口。
说明: RTMP 的启停细节已外提，当前文件只保留路由装配与响应封装。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import glob
import os
import uuid

from fastapi import HTTPException
from fastapi import Request

from src.api import route_state
from src.api.runtime_rtmp import start_pipeline_rtmp
from src.api.runtime_rtmp import stop_pipeline_rtmp
from src.api.schemas import HealthResponse
from src.api.schemas import PerformanceMetricsResponse
from src.api.schemas import RTMPStartRequest
from src.api.schemas import RTMPStatusResponse
from src.api.schemas import SessionSettingsRequest
from src.api.schemas import SessionSettingsResponse
from src.llm.prompts import get_prompt
from src.utils.metrics import get_metrics


def _get_avatar_dir() -> str:
    """返回头像目录绝对路径，不存在时自动创建。"""
    avatar_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "static",
        "avatars",
    )
    os.makedirs(avatar_dir, exist_ok=True)
    return avatar_dir


def register_routes() -> None:
    """注册运行时控制与扩展能力相关路由。"""
    router = route_state.router

    @router.get("/health", response_model=HealthResponse)
    async def health():
        """系统健康检查，返回 GPU 状态、显存与活跃会话数。"""
        import torch

        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        free = 0.0
        if torch.cuda.is_available():
            free = (
                torch.cuda.get_device_properties(0).total_memory
                - torch.cuda.memory_allocated()
            ) / (1024 * 1024)
        return HealthResponse(
            status="ok",
            gpu=gpu,
            vram_free_mb=free,
            active_sessions=route_state.sessions.active_count if route_state.sessions else 0,
        )

    @router.post("/session/{sid}/rtmp/start", response_model=RTMPStatusResponse)
    async def start_rtmp(sid: str, req: RTMPStartRequest):
        """启动 RTMP 推流，并返回真实底层状态。"""
        route_state.require_session(sid)
        try:
            status, rtmp_url = start_pipeline_rtmp(route_state.pipeline, req.rtmp_url)
            if status == "error":
                raise HTTPException(500, "RTMP 推流启动失败")
            return RTMPStatusResponse(status=status, rtmp_url=rtmp_url)
        except RuntimeError as error:
            raise HTTPException(500, str(error)) from error

    @router.post("/session/{sid}/rtmp/stop", response_model=RTMPStatusResponse)
    async def stop_rtmp(sid: str):
        """停止 RTMP 推流，并返回停止后的状态。"""
        route_state.require_session(sid)
        try:
            status = stop_pipeline_rtmp(route_state.pipeline)
            return RTMPStatusResponse(status=status)
        except RuntimeError as error:
            raise HTTPException(500, str(error)) from error

    @router.put("/session/{sid}/settings", response_model=SessionSettingsResponse)
    async def update_session_settings(sid: str, req: SessionSettingsRequest):
        """更新会话语言、场景、语音和自定义系统提示词。"""
        session = route_state.require_session(sid)
        updates = {}
        if req.language is not None:
            session.language = req.language
            updates["language"] = req.language
            voice_map = {
                "zh-CN": "zh-CN-XiaoxiaoNeural",
                "en-US": "en-US-JennyNeural",
                "ja-JP": "ja-JP-NanamiNeural",
            }
            if req.language in voice_map:
                session.voice = voice_map[req.language]
        if req.scenario is not None:
            session.scenario = req.scenario
            updates["scenario"] = req.scenario
            session.custom_system_prompt = get_prompt(req.scenario)
        if req.voice is not None:
            session.voice = req.voice
            updates["voice"] = req.voice
        if req.system_prompt is not None:
            session.custom_system_prompt = req.system_prompt
            updates["system_prompt"] = "(custom)"

        import logging

        logging.getLogger(__name__).info(f"会话{sid[:8]}设置更新: {updates}")
        return SessionSettingsResponse(
            session_id=sid,
            language=session.language,
            scenario=session.scenario,
            voice=session.voice,
            updated=True,
        )

    @router.get("/session/{sid}/settings", response_model=SessionSettingsResponse)
    async def get_session_settings(sid: str):
        """获取当前会话设置。"""
        session = route_state.require_session(sid)
        return SessionSettingsResponse(
            session_id=sid,
            language=session.language,
            scenario=session.scenario,
            voice=session.voice,
        )

    @router.get("/session/{sid}/metrics", response_model=PerformanceMetricsResponse)
    async def get_performance_metrics(sid: str):
        """获取会话性能指标与 SLA 结果。"""
        session = route_state.require_session(sid)
        metrics = get_metrics()
        sla = metrics.check_sla()
        stages = metrics.stages
        return PerformanceMetricsResponse(
            session_id=sid,
            total_latency_ms=stages["total"].last_ms,
            asr_latency_ms=stages["asr"].last_ms,
            llm_first_token_ms=stages["llm_first"].last_ms,
            tts_first_audio_ms=stages["tts_first"].last_ms,
            audio_feat_ms=stages["audio_feat"].last_ms,
            lipsync_infer_ms=stages["lipsync_infer"].last_ms,
            frame_comp_ms=stages["frame_comp"].last_ms,
            current_fps=metrics.fps,
            sla_total_ok=sla["total_ok"],
            sla_tts_ok=sla["tts_ok"],
            sla_audio_ok=sla["audio_ok"],
            sla_fps_ok=sla["fps_ok"],
            total_turns=session.total_turns,
            interrupt_count=session.interrupt_count,
        )

    @router.post("/voice/clone", status_code=202)
    async def clone_voice(
        voice_name: str = "custom_voice",
        reference_audio: bytes = None,
        reference_text: str = "",
    ):
        """上传参考音频，保存为后续 CosyVoice 声音克隆样本。"""
        try:
            import aiohttp

            cosyvoice_url = route_state.config.tts.cosyvoice_url
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{cosyvoice_url}/health",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    cosy_available = resp.status == 200
        except Exception:
            cosy_available = False

        if not cosy_available:
            return {
                "status": "unavailable",
                "message": (
                    "CosyVoice服务未运行。声音克隆需要CosyVoice服务。\n"
                    "请参考: https://github.com/FunAudioLLM/CosyVoice\n"
                    "启动命令: python -m cosyvoice.server --port 5001"
                ),
                "voice_id": voice_name,
            }

        clone_dir = os.path.join(os.path.dirname(_get_avatar_dir()), "voice_samples")
        os.makedirs(clone_dir, exist_ok=True)
        audio_path = os.path.join(clone_dir, f"{voice_name}.wav")
        with open(audio_path, "wb") as file:
            file.write(reference_audio or b"")
        if reference_text:
            text_path = os.path.join(clone_dir, f"{voice_name}.txt")
            with open(text_path, "w", encoding="utf-8") as file:
                file.write(reference_text)
        return {
            "status": "processing",
            "voice_id": voice_name,
            "audio_path": audio_path,
            "message": f"声音克隆样本已上传: {voice_name}。CosyVoice就绪后可进行克隆推理。",
        }

    @router.post("/avatar/upload")
    async def upload_avatar(request: Request):
        """上传数字人头像照片，保存到 static/avatars。"""
        body = await request.body()
        avatar_dir = _get_avatar_dir()
        filename = f"avatar_{uuid.uuid4().hex[:8]}.png"
        path = os.path.join(avatar_dir, filename)
        with open(path, "wb") as file:
            file.write(body)
        return {
            "status": "ok",
            "avatar_url": f"/static/avatars/{filename}",
            "path": path,
            "size_kb": round(len(body) / 1024, 1),
        }

    @router.get("/avatar/current")
    async def get_current_avatar():
        """获取当前最新上传头像的信息。"""
        avatar_dir = _get_avatar_dir()
        files = sorted(
            glob.glob(os.path.join(avatar_dir, "avatar_*.png")),
            key=os.path.getmtime,
            reverse=True,
        )
        if files:
            filename = os.path.basename(files[0])
            return {"has_avatar": True, "avatar_url": f"/static/avatars/{filename}"}
        return {"has_avatar": False, "avatar_url": None}

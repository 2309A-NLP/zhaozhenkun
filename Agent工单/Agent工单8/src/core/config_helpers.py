"""
src/core/config_helpers.py - 配置辅助函数
功能: 读取环境变量、解析 YAML、组装各子模块配置，供 load_config 调用。
说明: 将配置加载的重复逻辑拆出，避免 config.py 超过 300 行。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import logging
import os

import yaml

from src.core.config_defaults import (
    ASRConfig,
    BargeInConfig,
    GPUConfig,
    IdleVideoConfig,
    LLMConfig,
    LipsyncConfig,
    LoggingConfig,
    PipelineConfig,
    RTMPConfig,
    ServerConfig,
    SessionConfig,
    TTSConfig,
    VideoOutputConfig,
)

logger = logging.getLogger(__name__)


def get_env_api_key() -> str:
    """从环境变量、.env 和 api_key.txt 中读取 API Key。"""
    key = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    if key:
        return key

    try:
        from dotenv import load_dotenv

        load_dotenv()
        key = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        if key:
            return key
    except ImportError:
        pass

    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api_key.txt")
    try:
        if os.path.exists(key_file):
            with open(key_file, "r", encoding="utf-8") as file:
                key = file.read().strip()
                if key:
                    return key
    except (PermissionError, OSError):
        pass
    return ""


def load_yaml_config(config_path: str) -> dict:
    """读取 YAML 配置文件，失败时返回空字典。"""
    if not os.path.exists(config_path):
        logger.warning(f"配置文件 {config_path} 不存在，使用默认值")
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except (PermissionError, yaml.YAMLError) as error:
        logger.error(f"配置文件读取失败: {error}，使用默认值")
        return {}


def build_gpu_config(cfg: dict) -> GPUConfig:
    """构建 GPU 配置。"""
    gpu_cfg = cfg.get("gpu", {})
    return GPUConfig(
        device=gpu_cfg.get("device", "cuda:0"),
        use_fp16=gpu_cfg.get("use_fp16", True),
        max_vram_mb=gpu_cfg.get("max_vram_mb", 7500),
    )


def build_pipeline_config(cfg: dict) -> PipelineConfig:
    """构建流式管线配置。"""
    pipe = cfg.get("pipeline", {})
    return PipelineConfig(
        audio_sample_rate=pipe.get("audio_sample_rate", 16000),
        audio_chunk_ms=pipe.get("audio_chunk_ms", 20),
        mel_n_mels=pipe.get("mel_n_mels", 80),
        mel_hop_length=pipe.get("mel_hop_length", 200),
        stride_left_size=pipe.get("stride_left_size", 6),
        stride_right_size=pipe.get("stride_right_size", 8),
        batch_size=pipe.get("batch_size", 16),
        video_fps=pipe.get("video_fps", 25),
        video_width=pipe.get("video_width", 1280),
        video_height=pipe.get("video_height", 720),
        face_resolution=pipe.get("face_resolution", 96),
    )


def build_asr_config(cfg: dict) -> ASRConfig:
    """构建 ASR 配置。"""
    asr_cfg = cfg.get("asr", {})
    return ASRConfig(
        model=asr_cfg.get("model", "tiny"),
        language=asr_cfg.get("language", "zh"),
        device=asr_cfg.get("device", "cpu"),
        sample_rate=asr_cfg.get("sample_rate", 16000),
    )


def build_llm_config(cfg: dict, api_key: str) -> LLMConfig:
    """构建 LLM 配置。"""
    llm_cfg = cfg.get("llm", {})
    return LLMConfig(
        provider=llm_cfg.get("provider", "deepseek"),
        api_base=llm_cfg.get("api_base", "https://api.deepseek.com"),
        api_key=api_key or llm_cfg.get("api_key", ""),
        model=llm_cfg.get("model", "deepseek-chat"),
        max_tokens=llm_cfg.get("max_tokens", 2048),
        temperature=llm_cfg.get("temperature", 0.7),
        streaming=llm_cfg.get("streaming", True),
        system_prompt=llm_cfg.get("system_prompt", "你是一个友好的AI助手。"),
    )


def build_tts_config(cfg: dict) -> TTSConfig:
    """构建 TTS 配置。"""
    tts_cfg = cfg.get("tts", {})
    edge_cfg = tts_cfg.get("edge", {})
    return TTSConfig(
        default_backend=tts_cfg.get("default_backend", "edge"),
        edge_voice=edge_cfg.get("voice", "zh-CN-XiaoxiaoNeural"),
        edge_rate=edge_cfg.get("rate", "+0%"),
        edge_pitch=edge_cfg.get("pitch", "+0Hz"),
        cosyvoice_url=tts_cfg.get("cosyvoice_url", "http://localhost:5001/v1/tts"),
        cosyvoice_model_dir=tts_cfg.get("cosyvoice_model_dir", "models/cosyvoice"),
        reference_audio=tts_cfg.get("reference_audio", ""),
        reference_text=tts_cfg.get("reference_text", ""),
    )


def build_lipsync_config(cfg: dict) -> LipsyncConfig:
    """构建唇形同步配置。"""
    lip_cfg = cfg.get("lipsync", {})
    return LipsyncConfig(
        model=lip_cfg.get("model", "wav2lip"),
        checkpoint=lip_cfg.get("checkpoint", "models/wav2lip/wav2lip_288.pth"),
        face_detector=lip_cfg.get("face_detector", "sfd"),
        img_size=lip_cfg.get("img_size", 96),
        sadtalker_root=lip_cfg.get("sadtalker_root", ""),
        musetalk_checkpoint=lip_cfg.get("musetalk_checkpoint", "models/musetalk/pytorch_model.bin"),
        ernerf_checkpoint=lip_cfg.get("ernerf_checkpoint", "models/ernerf/model.ckpt"),
    )


def build_runtime_configs(cfg: dict) -> dict:
    """构建服务、会话、日志、视频、空闲视频和打断配置。"""
    srv_cfg = cfg.get("server", {})
    sess_cfg = cfg.get("sessions", {})
    log_cfg = cfg.get("logging", {})
    vid_cfg = cfg.get("video", {})
    idle_cfg = cfg.get("idle_video", {})
    bi_cfg = cfg.get("barge_in", {})
    rtmp_cfg = cfg.get("rtmp", {})
    return {
        "server": ServerConfig(
            host=srv_cfg.get("host", "0.0.0.0"),
            port=srv_cfg.get("port", 8000),
            cors_origins=srv_cfg.get("cors_origins", ["*"]),
        ),
        "sessions": SessionConfig(
            max_concurrent=sess_cfg.get("max_concurrent", 3),
            timeout_s=sess_cfg.get("timeout_s", 300),
        ),
        "logging": LoggingConfig(
            level=log_cfg.get("level", "INFO"),
            format=log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
        ),
        "video": VideoOutputConfig(
            output_width=vid_cfg.get("output_width", 1280),
            output_height=vid_cfg.get("output_height", 720),
            fps=vid_cfg.get("fps", 25),
            codec=vid_cfg.get("codec", "h264"),
            bitrate=vid_cfg.get("bitrate", "4000k"),
            background=vid_cfg.get("background", ""),
        ),
        "idle_video": IdleVideoConfig(
            enabled=idle_cfg.get("enabled", True),
            trigger_after_silence_s=idle_cfg.get("trigger_after_silence_s", 2.0),
            crossfade_frames=idle_cfg.get("crossfade_frames", 12),
        ),
        "barge_in": BargeInConfig(
            enabled=bi_cfg.get("enabled", True),
            energy_threshold=bi_cfg.get("energy_threshold", 0.02),
            silence_duration_ms=bi_cfg.get("silence_duration_ms", 300),
            trigger_duration_ms=bi_cfg.get("trigger_duration_ms", 200),
            fade_out_ms=bi_cfg.get("fade_out_ms", 100),
        ),
        "rtmp": RTMPConfig(
            encoder=rtmp_cfg.get("encoder", "libx264"),
            preset=rtmp_cfg.get("preset", "ultrafast"),
            bitrate=rtmp_cfg.get("bitrate", "4000k"),
            fps=rtmp_cfg.get("fps", 25),
        ),
    }
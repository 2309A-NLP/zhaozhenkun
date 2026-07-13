"""
src/core/config.py - 配置管理模块
功能: 从 YAML 配置文件和环境变量加载系统配置。
      API Key 等敏感信息仅从环境变量读取，不写入配置文件。
      提供类型安全的 dataclass 配置容器。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
from src.core.config_defaults import (
    ASRConfig,
    AppConfig,
    BargeInConfig,
    GPUConfig,
    IdleVideoConfig,
    LLMConfig,
    LipsyncConfig,
    LoggingConfig,
    PipelineConfig,
    ServerConfig,
    SessionConfig,
    TTSConfig,
    VideoOutputConfig,
)
from src.core.config_helpers import (
    build_asr_config,
    build_gpu_config,
    build_lipsync_config,
    build_llm_config,
    build_pipeline_config,
    build_runtime_configs,
    build_tts_config,
    get_env_api_key,
    load_yaml_config,
)

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    从 YAML 文件加载配置，API Key 从环境变量注入。
    参数:
        config_path: YAML 配置文件路径
    返回:
        完整配置的 AppConfig 实例
    """
    config = AppConfig()
    cfg = load_yaml_config(config_path)
    api_key = get_env_api_key()
    runtime_cfg = build_runtime_configs(cfg)
    config.gpu = build_gpu_config(cfg)
    config.pipeline = build_pipeline_config(cfg)
    config.asr = build_asr_config(cfg)
    config.llm = build_llm_config(cfg, api_key)
    config.tts = build_tts_config(cfg)
    config.lipsync = build_lipsync_config(cfg)
    config.server = runtime_cfg["server"]
    config.sessions = runtime_cfg["sessions"]
    config.logging = runtime_cfg["logging"]
    config.video = runtime_cfg["video"]
    config.idle_video = runtime_cfg["idle_video"]
    config.barge_in = runtime_cfg["barge_in"]
    config.rtmp = runtime_cfg["rtmp"]

    if not config.llm.api_key:
        logger.warning(
            "未检测到 DEEPSEEK_API_KEY / OPENAI_API_KEY / api_key.txt，"
            "后续调用在线LLM时可能失败"
        )

    return config

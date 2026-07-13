"""
src/core/config_defaults.py - 配置数据结构定义
功能: 定义系统各模块的 dataclass 配置结构，供配置加载逻辑和业务模块复用。
说明: 本文件只负责声明默认配置结构，不负责读取 YAML 或环境变量。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

from dataclasses import dataclass, field


@dataclass
class GPUConfig:
    """GPU 硬件配置。"""

    device: str = "cuda:0"
    use_fp16: bool = True
    max_vram_mb: int = 7500


@dataclass
class PipelineConfig:
    """流式管线基础参数。"""

    audio_sample_rate: int = 16000
    audio_chunk_ms: int = 20
    mel_n_mels: int = 80
    mel_hop_length: int = 200
    stride_left_size: int = 6
    stride_right_size: int = 8
    batch_size: int = 16
    video_fps: int = 25
    video_width: int = 1280
    video_height: int = 720
    face_resolution: int = 96


@dataclass
class ASRConfig:
    """语音识别(ASR)配置。"""

    model: str = "tiny"
    language: str = "zh"
    device: str = "cpu"
    sample_rate: int = 16000


@dataclass
class LLMConfig:
    """大语言模型(LLM)配置。"""

    provider: str = "deepseek"
    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    max_tokens: int = 2048
    temperature: float = 0.7
    streaming: bool = True
    system_prompt: str = "你是一个友好的AI数字人助手。"
    ollama_model: str = "qwen2.5:7b"
    vllm_url: str = "http://localhost:8000/v1"
    vllm_model: str = "qwen2.5-7b-instruct"
    openai_model: str = "gpt-4o-mini"


@dataclass
class TTSConfig:
    """语音合成(TTS)配置。"""

    default_backend: str = "edge"
    edge_voice: str = "zh-CN-XiaoxiaoNeural"
    edge_rate: str = "+0%"
    edge_pitch: str = "+0Hz"
    cosyvoice_url: str = "http://localhost:5001/v1/tts"
    cosyvoice_model_dir: str = "models/cosyvoice"
    reference_audio: str = ""
    reference_text: str = ""


@dataclass
class LipsyncConfig:
    """唇形同步配置。"""

    model: str = "wav2lip"
    checkpoint: str = "models/wav2lip/wav2lip_288.pth"
    face_detector: str = "sfd"
    img_size: int = 96
    sadtalker_root: str = ""
    musetalk_checkpoint: str = "models/musetalk/pytorch_model.bin"
    ernerf_checkpoint: str = "models/ernerf/model.ckpt"


@dataclass
class VideoOutputConfig:
    """视频输出配置。"""

    output_width: int = 1280
    output_height: int = 720
    fps: int = 25
    codec: str = "h264"
    bitrate: str = "4000k"
    background: str = ""


@dataclass
class IdleVideoConfig:
    """空闲视频配置。"""

    enabled: bool = True
    trigger_after_silence_s: float = 2.0
    crossfade_frames: int = 12


@dataclass
class ServerConfig:
    """Web 服务器配置。"""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class SessionConfig:
    """会话管理配置。"""

    max_concurrent: int = 3
    timeout_s: int = 300


@dataclass
class LoggingConfig:
    """日志配置。"""

    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


@dataclass
class BargeInConfig:
    """打断检测配置。"""

    enabled: bool = True
    energy_threshold: float = 0.02
    silence_duration_ms: int = 300
    trigger_duration_ms: int = 200
    fade_out_ms: int = 100


@dataclass
class RTMPConfig:
    """RTMP 推流配置。"""

    encoder: str = "libx264"
    preset: str = "ultrafast"
    bitrate: str = "4000k"
    fps: int = 25


@dataclass
class AppConfig:
    """应用总配置，聚合所有子模块配置。"""

    gpu: GPUConfig = field(default_factory=GPUConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    lipsync: LipsyncConfig = field(default_factory=LipsyncConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    barge_in: BargeInConfig = field(default_factory=BargeInConfig)
    video: VideoOutputConfig = field(default_factory=VideoOutputConfig)
    idle_video: IdleVideoConfig = field(default_factory=IdleVideoConfig)
    rtmp: RTMPConfig = field(default_factory=RTMPConfig)
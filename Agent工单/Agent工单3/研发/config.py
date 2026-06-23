# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：项目配置模块（WSL + SD WebUI API 版本）
==============================================================================
本文件定义了文生图智能体项目的所有配置参数，包括：
  - SD WebUI API 连接配置
  - 模型路径配置（WSL 路径）
  - Milvus / Redis 缓存（可选，默认关闭）
  - 图像生成参数（推理步数、引导系数、图像尺寸等）
  - 人脸旋转角度配置 / 扩图参数配置
  - 日志配置（统一使用 logging 模块）

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os
import logging
from dataclasses import dataclass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
INPUT_DIR = os.path.join(PROJECT_ROOT, "input")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: str = LOG_LEVEL):
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(OUTPUT_DIR, "app.log"),
                encoding="utf-8",
                mode="a"
            )
        ],
        force=True
    )


# ============================================================
# SD WebUI API 配置（核心：通过 REST API 调用本地 SD WebUI）
# ============================================================
@dataclass
class WebUIConfig:
    """SD WebUI API 连接配置"""
    base_url: str = "http://127.0.0.1:7861"
    timeout: int = 300                          # API 超时秒数
    wait_startup: bool = True                   # 是否等待 WebUI 启动
    startup_timeout: int = 300                  # 启动超时秒数


# ============================================================
# 模型配置（WSL 路径）
# ============================================================
def resolve_sd_model_path() -> str:
    """解析 SD 模型路径（WSL）"""
    candidates = [
        os.environ.get("SD_MODEL_PATH", ""),
        os.path.join(MODELS_DIR, "v1-5-pruned-emaonly.safetensors"),
        "/home/zzy/stable-diffusion-webui/models/Stable-diffusion/v1-5-pruned-emaonly.safetensors",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return candidates[-1]


@dataclass
class ModelConfig:
    """模型相关配置"""
    sd_model_path: str = resolve_sd_model_path()
    face_detector_backend: str = "mediapipe"
    device: str = "cpu"     # WSL 里走 WebUI API，不需要本地 GPU 推理
    dtype: str = "float32"
    use_controlnet: bool = False


# ============================================================
# Milvus 配置（可选，默认禁用）
# ============================================================
@dataclass
class MilvusConfig:
    enabled: bool = False                       # 默认关闭
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "face_prompt_vectors"
    vector_dim: int = 1024
    index_type: str = "IVF_FLAT"
    metric_type: str = "COSINE"
    nlist: int = 128
    top_k: int = 5


# ============================================================
# Redis 配置（可选，默认禁用）
# ============================================================
@dataclass
class RedisConfig:
    enabled: bool = False                       # 默认关闭
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    cache_prefix: str = "face_gen:"
    expire_seconds: int = 86400
    max_cache_size: int = 1000


# ============================================================
# 检索配置
# ============================================================
@dataclass
class RetrievalConfig:
    enable_semantic_retrieval: bool = False     # 需要 Milvus，默认关闭
    similarity_threshold: float = 0.92
    reuse_only_same_task: bool = True


# ============================================================
# 生成参数配置
# ============================================================
@dataclass
class GenerationConfig:
    """SD 推理参数"""
    num_inference_steps: int = 30
    guidance_scale: float = 7.5
    image_width: int = 512
    image_height: int = 512
    denoising_strength: float = 0.25            # img2img 噪声强度（低=保留原图）
    seed: int = 42                              # 默认种子，-1为随机


# ============================================================
# 面部旋转配置
# ============================================================
@dataclass
class FaceRotationConfig:
    """面部旋转参数"""
    left_rotation_angle: float = -30.0
    right_rotation_angle: float = 30.0
    frontal_angle: float = 0.0
    crop_margin: int = 50
    face_fidelity: float = 0.75
    denoising_strength: float = 0.25   # 低强度=保留身份，高强度=改变人脸


# ============================================================
# ControlNet 配置（本地 diffusers 管线，不依赖 WebUI API）
# ============================================================
@dataclass
class ControlNetConfig:
    """ControlNet OpenPose + SD 本地推理配置"""
    enabled: bool = False
    sd_model_path: str = (
        "/home/zzy/stable-diffusion-webui/models/Stable-diffusion/"
        "v1-5-pruned-emaonly.safetensors"
    )
    controlnet_model_path: str = (
        "/home/zzy/stable-diffusion-webui/models/ControlNet/"
        "control_v11p_sd15_openpose.pth"
    )
    controlnet_config_path: str = (
        "/home/zzy/stable-diffusion-webui/models/ControlNet/config.json"
    )
    body_pose_model_path: str = ""              # OpenPose 模型路径，留空自动查找
    device: str = "cuda"                        # 推理设备
    torch_dtype: str = "float16"                # 精度
    conditioning_scale: float = 0.85            # ControlNet 控制强度
    use_ip_adapter: bool = False                # 是否加载 IP-Adapter
    ip_adapter_model_path: str = (
        "/home/zzy/stable-diffusion-webui/models/ControlNet/models/"
        "ip-adapter-plus-face_sd15.safetensors"
    )
    ip_adapter_scale: float = 0.7               # IP-Adapter 影响强度
    offline_mode: bool = True                   # 离线模式，不从 HF 在线下载


# ============================================================
# 强控制路线配置（推荐：ComfyUI + InstantID / IP-Adapter Face）
# ============================================================
@dataclass
class StrongControlConfig:
    """强身份一致性路线配置"""
    enabled: bool = True
    workflow_path: str = os.path.join(PROJECT_ROOT, "设计", "instantid_workflow_api.json")
    input_dir: str = os.path.join(PROJECT_ROOT, "研发", "strong_input")
    output_dir: str = os.path.join(PROJECT_ROOT, "研发", "strong_output")
    comfyui_api_url: str = "http://127.0.0.1:8188"
    checkpoint_name: str = "v1-5-pruned-emaonly.safetensors"
    checkpoint_family: str = "sd15"
    instantid_controlnet_name: str = "ControlNetModel/diffusion_pytorch_model.safetensors"
    allow_fallback: bool = False
    fallback_use_controlnet: bool = False


# ============================================================
# 扩图配置
# ============================================================
@dataclass
class OutpaintConfig:
    """图像扩图参数"""
    expand_ratio: float = 1.5
    expand_top: bool = True
    expand_bottom: bool = True
    expand_left: bool = True
    expand_right: bool = True
    denoising_strength: float = 0.80
    prompt: str = (
        "professional portrait photography, same person, "
        "upper body shot, elegant casual clothing, "
        "natural studio lighting with neutral background, "
        "sharp focus, 8k, highly detailed, "
        "seamless image extension, perfect composition, "
        "clean edges, natural skin texture"
    )
    negative_prompt: str = (
        "different person, face change, identity change, "
        "deformed, bad anatomy, disfigured, blurry, "
        "distorted, visible seams, hard edges, cut off, "
        "poorly drawn, watermark, text, signature, "
        "double face, multiple faces, different clothing, "
        "messy background, cluttered, low resolution"
    )


# ============================================================
# Prompt 模板 (从 prompts.py 导入，此处保留向后兼容)
# ============================================================
from prompts import FACE_PROMPT_TEMPLATE, FACE_NEGATIVE_PROMPT, FACE_CONTROLNET_TEMPLATE  # noqa: F401


# ============================================================
# 千问图像编辑模型配置（DashScope API）
# ============================================================
@dataclass
class QwenImageEditConfig:
    """千问 Qwen-Image-Edit-Max 图像编辑模型配置"""
    # API 连接
    api_key: str = "sk-cb2873cdfdb543d1a8a05f3ffda4620c"
    # 注意：图像编辑模型使用 DashScope 原生 multimodal API，
    # 与文本模型的 compatible-mode 端点不同
    base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    # 文本对话可用: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: str = "qwen-image-edit-max"

    # 生成参数
    n: int = 1                              # 输出图片数量 (1-6)
    size: str = "1024*1024"                 # 输出分辨率
    watermark: bool = False                 # 是否添加水印
    prompt_extend: bool = True              # 是否扩展提示词
    seed: int = -1                          # 随机种子，-1为随机
    negative_prompt: str = ""               # 反向提示词


# ============================================================
# 创建全局配置实例
# ============================================================
webui_config = WebUIConfig()
model_config = ModelConfig()
milvus_config = MilvusConfig()
redis_config = RedisConfig()
retrieval_config = RetrievalConfig()
gen_config = GenerationConfig()
face_config = FaceRotationConfig()
outpaint_config = OutpaintConfig()
controlnet_config = ControlNetConfig()
strong_control_config = StrongControlConfig()
qwen_config = QwenImageEditConfig()


def log_config():
    """输出当前配置摘要"""
    logger = logging.getLogger("config")
    logger.info("=" * 60)
    logger.info("文生图智能体 - 当前配置")
    logger.info(f"WebUI URL: {webui_config.base_url}")
    logger.info(f"SD 模型: {model_config.sd_model_path}")
    logger.info(f"Milvus: {'启用' if milvus_config.enabled else '关闭'}")
    logger.info(f"Redis: {'启用' if redis_config.enabled else '关闭'}")
    logger.info(f"ControlNet: {'启用' if controlnet_config.enabled else '关闭'}")
    logger.info(f"强控制路线: {'启用' if strong_control_config.enabled else '关闭'}")
    logger.info(f"千问模型: {qwen_config.model}")
    logger.info(f"千问 API: {qwen_config.base_url}")
    logger.info("=" * 60)

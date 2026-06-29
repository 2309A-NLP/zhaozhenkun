# -*- coding: utf-8 -*-
"""
digital_human.py — 数字人视频生成引擎（核心类）
--------------------------------------------------------------
功能: 语音驱动人脸生成唇形同步视频。
      优先 SadTalker (3DMM+面部渲染) → Wav2Lip → 占位模式。
      接收 TTS 音频 → 驱动数字人口型 → 输出视频帧。

依赖子模块:
  dh_patches.py    — NumPy 2.x 兼容补丁 + GFPGAN/modelscope Mock
  dh_sadtalker.py  — SadTalker 加载/推理/Croper补丁/恢复
  dh_compositor.py — 占位模式/头像管理/音视频合成/全局单例

对应工单需求: "数字人基于Agent能力返回回复文本并生成回复视频"

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, sys, logging, glob  # 标准库
import numpy as np             # 数值计算
import cv2                     # 图像处理

# ★ 首先应用所有补丁和 Mock（必须在导入 SadTalker 之前）
import dh_patches
dh_patches.apply_all_patches()

logger = logging.getLogger("digital_human")

# ================================================================
# SadTalker 路径 — 优先从 config.py 读取
# ================================================================
try:
    import config as _cfg
    SADTALKER_CHECKPOINTS = _cfg.SADTALKER_CHECKPOINT
    SADTALKER_CONFIG = _cfg.SADTALKER_CONFIG
    SADTALKER_SRC = _cfg.SADTALKER_SRC
    SADTALKER_ROOT = os.path.dirname(SADTALKER_SRC)
    logger.info("SadTalker路径: CKPT=%s SRC=%s",
                 "✓" if os.path.isdir(SADTALKER_CHECKPOINTS) else "✗",
                 "✓" if os.path.isdir(SADTALKER_SRC) else "✗")
except Exception as e:
    logger.error("无法读取config.py中SadTalker路径: %s", e)
    SADTALKER_ROOT = os.path.expanduser("~/SadTalker_modelscope")
    SADTALKER_CHECKPOINTS = os.path.join(SADTALKER_ROOT, "checkpoints")
    SADTALKER_CONFIG = os.path.join(SADTALKER_ROOT, "src", "config")
    SADTALKER_SRC = os.path.join(SADTALKER_ROOT, "src")

# ================================================================
# Mixin: 从子模块导入方法，绑定为类属性
# ================================================================
from dh_sadtalker import (load_sadtalker, patch_croper_for_wider_crop,
                           generate_sadtalker, try_recover_sadtalker_impl)
from dh_compositor import (use_placeholder, generate_placeholder_frames,
                            composite_audio_video,
                            restore_avatar_from_disk, get_source_image,
                            imread_safe, try_load_avatar_from_path,
                            create_fallback_face_image, set_avatar_impl,
                            get_digital_human)  # 全局单例 — 重新导出供外部使用


class DigitalHumanEngine:
    """数字人引擎 — 语音驱动人脸唇形同步。

    模型优先级: SadTalker > Wav2Lip > 占位模式
    """

    # 头像持久化路径（类常量）
    LAST_AVATAR_FILE = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "static", "avatars", ".last_avatar"))
    AVATARS_DIR = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "static", "avatars"))

    # ---- 绑定外部 mixin 方法为类属性 ----
    _load_sadtalker = load_sadtalker
    _patch_croper_for_wider_crop = patch_croper_for_wider_crop
    _generate_sadtalker = generate_sadtalker
    try_recover_sadtalker = try_recover_sadtalker_impl
    _use_placeholder = use_placeholder
    _generate_placeholder_frames = generate_placeholder_frames
    composite_audio_video = staticmethod(composite_audio_video)
    _restore_avatar_from_disk = restore_avatar_from_disk
    _get_source_image = get_source_image
    _imread_safe = imread_safe
    _try_load_avatar_from_path = try_load_avatar_from_path
    _create_fallback_face_image = create_fallback_face_image
    set_avatar = set_avatar_impl

    def __init__(self, width: int = 512, height: int = 512,
                 fps: int = 25, device: str = "cuda:0",
                 avatar_path: str = None,
                 sadtalker_checkpoint: str = None,
                 sadtalker_config: str = None):
        """初始化数字人引擎。

        参数:
            width/height: 输出分辨率 (默认512)
            fps: 帧率 (默认25)
            device: 推理设备 cuda:0/cpu
            avatar_path: 数字人形象图片路径
            sadtalker_checkpoint: SadTalker checkpoint 目录
            sadtalker_config: SadTalker config 目录
        """
        self.width = width; self.height = height; self.fps = fps
        self.device = device if self._cuda_ok() else "cpu"
        self.avatar_path = avatar_path
        self.sadtalker_checkpoint = sadtalker_checkpoint or SADTALKER_CHECKPOINTS
        self.sadtalker_config = sadtalker_config or SADTALKER_CONFIG
        self._model = None           # SadTalker 实例
        self._model_type = None      # 'sadtalker'/'wav2lip'/'placeholder'
        self._avatar_frame = None    # 参考人脸帧 (BGR)
        self._loaded = False
        self._auto_load()            # 自动发现最佳模型并加载

    # ================================================================
    # GPU 工具
    # ================================================================
    def _cuda_ok(self) -> bool:
        """检查 CUDA 是否可用。"""
        try:
            import torch; return torch.cuda.is_available()
        except ImportError: return False

    def _cleanup_gpu(self):
        """清理 GPU 显存缓存。"""
        try:
            import torch
            if torch.cuda.is_available(): torch.cuda.empty_cache()
        except Exception: pass

    # ================================================================
    # 模型自动发现与加载
    # ================================================================
    def _auto_load(self):
        """自动发现并加载优先级最高的可用模型 (SadTalker > Wav2Lip > placeholder)。"""
        logger.info("DH auto_load: ckpt=%s", self.sadtalker_checkpoint)
        self._cleanup_gpu()
        # 优先级1: SadTalker (重试2次)
        if self._sadtalker_available():
            for attempt in range(2):
                try:
                    self._load_sadtalker()
                    self._restore_avatar_from_disk(); return
                except Exception as e:
                    logger.warning("SadTalker加载失败(尝试%d/2): %s", attempt + 1, str(e)[:80])
                    if attempt < 1:
                        import time; time.sleep(2); self._cleanup_gpu()
        # 优先级2: Wav2Lip
        if self._wav2lip_available():
            self._load_wav2lip(); return
        # 兜底: 占位模式
        logger.warning("无可用的数字人模型，使用占位模式")
        self._use_placeholder()
        self._restore_avatar_from_disk()

    def _sadtalker_available(self) -> bool:
        """检查 SadTalker 权重是否可用 (safetensor 或 pth)。"""
        cfg_ok = os.path.exists(os.path.join(self.sadtalker_config, "facerender.yaml"))
        src_ok = os.path.exists(os.path.join(SADTALKER_SRC, "gradio_demo.py"))
        # safetensor 模式
        st = [s for s in glob.glob(os.path.join(self.sadtalker_checkpoint, "*.safetensors"))
              if os.path.getsize(s) > 100_000_000]
        if st:
            total = sum(os.path.getsize(s) for s in st) / (1024 * 1024)
            logger.info("SadTalker safetensor: %.0fMB (%d files)", total, len(st))
            return cfg_ok and src_ok
        # pth 模式
        ckpt = os.path.join(self.sadtalker_checkpoint, "mapping_00229-model.pth.tar")
        return os.path.exists(ckpt) and os.path.getsize(ckpt) > 50_000_000 and cfg_ok and src_ok

    def _wav2lip_available(self) -> bool:
        """检查 Wav2Lip 模型是否可用。"""
        for p in [os.path.expanduser("~/Wav2Lip/checkpoints/wav2lip_gan.pth")]:
            if os.path.exists(p): return True
        return False

    def _load_wav2lip(self):
        """加载 Wav2Lip 模型（当前占位，权重就绪后启用）。"""
        logger.warning("Wav2Lip权重未就绪，回退占位模式")
        self._use_placeholder()

    # ================================================================
    # 视频生成主接口
    # ================================================================
    def generate_video(self, audio: np.ndarray, text: str = "") -> list:
        """根据 TTS 音频生成唇形同步视频帧。

        参数:
            audio: float32 音频数组，16kHz 单声道
            text: 回复文本（日志用）
        返回: BGR 视频帧列表
        """
        if not self._loaded: self._auto_load()
        if self._model_type == "placeholder":
            self.try_recover_sadtalker()                    # 尝试从占位恢复

        dur = len(audio) / 16000
        if dur < 0.05 or len(audio) < 800:                  # <50ms 跳过
            return []

        logger.info("🎬 DH: audio=%.1fs, model=%s", dur, self._model_type)

        if self._model_type == "sadtalker" and self._model is not None:
            return self._generate_sadtalker(audio, text)
        elif self._model_type == "wav2lip":
            return self._generate_wav2lip(audio)
        else:
            return self._generate_placeholder_frames(audio)

    def _generate_wav2lip(self, audio: np.ndarray) -> list:
        """Wav2Lip 推理（当前占位）。"""
        return self._generate_placeholder_frames(audio)

    # ================================================================
    # 属性
    # ================================================================
    @property
    def is_loaded(self) -> bool: return self._loaded

    @property
    def has_avatar(self) -> bool:
        return (self._avatar_frame is not None or
                (self.avatar_path and os.path.exists(self.avatar_path)) or
                os.path.exists(self.LAST_AVATAR_FILE))

    @property
    def engine_type(self) -> str: return self._model_type or "unknown"

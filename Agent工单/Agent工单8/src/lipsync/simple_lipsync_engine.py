"""
src/lipsync/simple_lipsync_engine.py - 轻量唇形动画引擎
功能: 当 SadTalker/Wav2Lip 不可用时，基于音频能量驱动头像嘴部区域形变。
说明: 图像渲染细节已拆分到 simple_lipsync_render.py，主文件负责流程与缓存管理。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from src.lipsync.simple_lipsync_render import (
    DEFAULT_MAX_OPEN,
    DEFAULT_SMOOTH_WINDOW,
    SimpleLipSyncRenderMixin,
)

logger = logging.getLogger(__name__)
_infer = ThreadPoolExecutor(max_workers=1)


class SimpleLipSyncEngine(SimpleLipSyncRenderMixin):
    """基于图像局部变形的轻量唇形同步引擎。"""

    def __init__(self, img_size: int = 96, output_size: int = 768):
        self.img_size = img_size
        self.output_size = output_size
        self._face_img = None
        self._face_landmarks = None
        self._mouth_roi = None
        self._mel_extractor = None
        self._last_audio = None
        self._audio_buffer = []
        self._last_energy = 0.0
        self._energy_history = []

    def load_face_image(self) -> np.ndarray:
        """加载用户头像，优先读取上传头像，失败时回退默认灰底图。"""
        if self._face_img is not None:
            return self._face_img
        import glob

        avatar_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "static", "avatars"))
        os.makedirs(avatar_dir, exist_ok=True)
        files = sorted(glob.glob(os.path.join(avatar_dir, "avatar_*.png")), key=os.path.getmtime, reverse=True)
        for file_path in files:
            image = self._decode_image(file_path)
            if image is not None:
                logger.info(f"SimpleLipSync 加载头像: {os.path.basename(file_path)}")
                return self._set_face_image(image)
        static_dir = os.path.normpath(os.path.join(avatar_dir, ".."))
        for filename in ["person.png", "avatar.jpg"]:
            image = self._decode_image(os.path.join(static_dir, filename))
            if image is not None:
                return self._set_face_image(image)
        logger.warning("SimpleLipSync: 无头像可用")
        return self._set_face_image(np.ones((512, 512, 3), dtype=np.uint8) * 200)

    def _decode_image(self, path: str):
        """按二进制方式解码图片，规避中文路径问题。"""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as file:
                data = np.frombuffer(file.read(), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception as error:
            logger.warning(f"读取头像失败: {path}: {error}")
            return None

    def _set_face_image(self, image: np.ndarray) -> np.ndarray:
        """保存头像并同步估算嘴部区域。"""
        self._face_img = image
        self._detect_mouth_region(image)
        return image

    def extract_features(self, audio: np.ndarray) -> np.ndarray:
        """提取 Mel 特征并缓存当前音频能量，供后续逐帧动画使用。

        重要: 每段新音频直接替换 _last_audio，不累积历史音频，
        确保每句话的口型动画由当前句子的能量驱动，而非累积的旧音频。
        """
        from src.audio.feature_extractor import MelFeatureExtractor

        if self._mel_extractor is None:
            self._mel_extractor = MelFeatureExtractor()
        mel = self._mel_extractor.extract_with_context(audio)
        audio_flat = audio if audio.ndim == 1 else audio.flatten()
        # 直接替换当前音频，不累积 — 修复唇形不随新音频变化的bug
        self._last_audio = audio_flat.astype(np.float32)
        rms = float(np.sqrt(np.mean(audio_flat ** 2)))
        self._energy_history.append(rms)
        if len(self._energy_history) > DEFAULT_SMOOTH_WINDOW:
            self._energy_history.pop(0)
        self._last_energy = np.mean(self._energy_history) if self._energy_history else rms
        return mel

    def generate_frames(self, mel_features: np.ndarray, face_images: np.ndarray = None) -> np.ndarray:
        """根据 Mel 特征窗口数生成完整输出帧序列。"""
        del face_images
        frame_count = mel_features.shape[0] if mel_features is not None else 0
        if frame_count == 0:
            return np.zeros((0, 3, self.output_size, self.output_size), dtype=np.uint8)
        face = self.load_face_image()
        face_resized, roi = self._prepare_face_canvas(face)
        normalized = self._prepare_frame_energy(frame_count)
        frames = []
        for index in range(frame_count):
            energy_norm = normalized[index] if index < len(normalized) else 0.0
            open_factor = 1.0 + (DEFAULT_MAX_OPEN - 1.0) * energy_norm
            frame = self._generate_mouth_open_frame(face_resized, *roi, open_factor)
            frames.append(frame.transpose(2, 0, 1))
        return np.stack(frames, axis=0).astype(np.uint8)

    def _prepare_face_canvas(self, face: np.ndarray):
        """将头像缩放到输出尺寸，并把嘴部 ROI 映射到新坐标。"""
        height, width = face.shape[:2]
        face_resized = cv2.resize(face, (self.output_size, self.output_size))
        scale_y = self.output_size / height
        scale_x = self.output_size / width
        my1, my2, mx1, mx2 = self._mouth_roi
        roi = (int(my1 * scale_y), int(my2 * scale_y), int(mx1 * scale_x), int(mx2 * scale_x))
        return face_resized, roi

    def _prepare_frame_energy(self, frame_count: int) -> list:
        """基于缓存音频计算每帧归一化能量。"""
        audio = getattr(self, "_last_audio", None)
        if audio is None or len(audio) == 0:
            return [0.0] * frame_count
        audio_flat = audio if audio.ndim == 1 else audio.flatten()
        return self._build_frame_energies(audio_flat, frame_count)

    async def generate_frames_async(self, mel_features, face_images=None):
        """在线程池中异步生成轻量口型动画帧。"""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_infer, self.generate_frames, mel_features, face_images)

    @property
    def generates_full_frames(self) -> bool:
        """当前引擎直接输出完整帧，不需要 compositor 二次贴脸。"""
        return True

    @property
    def vram_mb(self) -> float:
        """轻量引擎不占用 GPU 显存。"""
        return 0.0

    def reset_buffer(self):
        """重置音频与能量缓存，供新对话重新开始。"""
        self._audio_buffer.clear()
        self._last_audio = None
        self._energy_history.clear()
        self._last_energy = 0.0

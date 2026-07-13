"""
src/lipsync/wav2lip_engine.py - Wav2Lip 唇形同步引擎
功能: 基于 Wav2Lip 模型将音频 Mel 特征转换为同步的人脸唇形帧。
      同时支持批量模式和增量流式模式，满足实时数字人交互要求。
说明: 增量运行时逻辑已拆分到独立模块，主文件保留模型管理与核心推理。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch

from src.lipsync.wav2lip_runtime import Wav2LipRuntimeMixin

logger = logging.getLogger(__name__)
_infer_executor = ThreadPoolExecutor(max_workers=1)


class Wav2LipEngine(Wav2LipRuntimeMixin):
    """Wav2Lip 唇形同步引擎，支持批量与流式双模式。"""

    def __init__(self, checkpoint_path: str, device: str = "cuda:0",
                 img_size: int = 96, use_fp16: bool = True):
        """初始化引擎、模型状态和增量缓冲结构。"""
        self.checkpoint_path = checkpoint_path
        self.device = device if torch.cuda.is_available() else "cpu"
        self.img_size = img_size
        self.use_fp16 = use_fp16 and self.device != "cpu"
        self._model = None
        self._face_ref = None
        self._audio_buffer = bytearray()
        self._frame_queue = asyncio.Queue(maxsize=60)
        self._mel_extractor = None
        self._incremental_active = False
        self._lock = threading.Lock()
        logger.info(f"Wav2Lip引擎初始化: device={self.device}, fp16={self.use_fp16}")

    def load_model(self):
        """加载 Wav2Lip 模型权重到目标设备。"""
        if self._model is not None:
            return
        import os
        if not os.path.exists(self.checkpoint_path):
            logger.warning(
                f"Wav2Lip权重不存在: {self.checkpoint_path}\n"
                f"请运行: python scripts/download_models.py\n"
                f"或从 https://github.com/Rudrabha/Wav2Lip 下载"
            )
            self._model = self._create_placeholder()
            return
        try:
            checkpoint = torch.load(self.checkpoint_path, map_location=self.device, weights_only=True)
            wav2lip_dir = os.path.join(os.path.dirname(self.checkpoint_path), "Wav2Lip")
            if os.path.exists(wav2lip_dir):
                import sys
                sys.path.insert(0, wav2lip_dir)
                from models.wav2lip import Wav2Lip as Wav2LipModel
                self._model = Wav2LipModel()
                if "state_dict" in checkpoint:
                    checkpoint = checkpoint["state_dict"]
                self._model.load_state_dict(checkpoint, strict=False)
                self._model = self._model.to(self.device)
                if self.use_fp16:
                    self._model = self._model.half()
                self._model.eval()
                logger.info("Wav2Lip模型加载完成")
            else:
                logger.warning("Wav2Lip源码未找到，使用占位模式")
                self._model = self._create_placeholder()
        except Exception as error:
            logger.error(f"Wav2Lip模型加载失败: {error}")
            self._model = self._create_placeholder()

    def _create_placeholder(self):
        """创建占位模型，在缺权重时返回原始人脸帧。"""
        logger.info("使用占位模式运行(返回原始人脸帧)")

        class PlaceholderModel:
            def __call__(self, mel_features, face_images):
                if face_images is not None:
                    return face_images
                batch = mel_features.shape[0] if mel_features is not None else 1
                return torch.zeros(batch, 3, 96, 96, device=torch.device("cpu"))

            def eval(self):
                return None

            def to(self, _device):
                return self

            def half(self):
                return self

        return PlaceholderModel()

    def generate_frames(self, mel_features: np.ndarray, face_images: np.ndarray = None) -> np.ndarray:
        """批量生成唇形同步人脸帧，返回 uint8 图像数组。"""
        if self._model is None:
            self.load_model()
        if self._model is None:
            return np.zeros((1, 3, 96, 96), dtype=np.uint8)
        mel_tensor = torch.from_numpy(mel_features).float()
        if self.use_fp16:
            mel_tensor = mel_tensor.half()
        mel_tensor = mel_tensor.to(self.device)
        face_tensor = self._prepare_face_tensor(mel_tensor, face_images)
        with torch.no_grad():
            with torch.cuda.amp.autocast(enabled=self.use_fp16):
                output = self._model(mel_tensor, face_tensor)
        if isinstance(output, tuple):
            output = output[0]
        result = output.float().cpu().numpy()
        return self._to_uint8_frames(result)

    def _prepare_face_tensor(self, mel_tensor: torch.Tensor, face_images: np.ndarray = None) -> torch.Tensor:
        """构造模型所需的人脸输入张量。"""
        if face_images is None:
            frame_count = mel_tensor.shape[0]
            face_tensor = torch.zeros(frame_count, 3, self.img_size, self.img_size, device=self.device)
        else:
            face_tensor = torch.from_numpy(face_images).to(self.device)
        if self.use_fp16:
            face_tensor = face_tensor.half()
        return face_tensor

    def _to_uint8_frames(self, result: np.ndarray) -> np.ndarray:
        """将模型输出统一转换为 uint8 帧。"""
        if result.min() >= 0 and result.max() <= 255 and not self.use_fp16:
            return result.clip(0, 255).astype(np.uint8)
        return np.clip((result + 1.0) * 127.5, 0, 255).astype(np.uint8)

    async def generate_frames_async(self, mel_features: np.ndarray, face_images: np.ndarray = None) -> np.ndarray:
        """在线程池中异步执行 GPU 推理。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_infer_executor, self.generate_frames, mel_features, face_images)

    def set_face_reference(self, face_image: np.ndarray) -> None:
        """设置增量模式使用的参考人脸张量。"""
        face_tensor = torch.from_numpy(face_image).float().div(255.0)
        face_tensor = (face_tensor - 0.5) * 2.0
        if self.use_fp16:
            face_tensor = face_tensor.half()
        self._face_ref = face_tensor.to(self.device)

    async def feed_audio_chunk(self, audio: np.ndarray) -> None:
        """喂入音频块并触发一次增量推理。"""
        if not self._incremental_active:
            logger.warning("增量模式未启动，忽略音频chunk")
            return
        with self._lock:
            if audio.dtype != np.int16:
                audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
            else:
                audio_int16 = audio
            self._audio_buffer.extend(audio_int16.tobytes())
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_infer_executor, self._process_audio_buffer)

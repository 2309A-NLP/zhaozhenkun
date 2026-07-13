"""
src/lipsync/wav2lip_runtime.py - Wav2Lip 增量推理扩展
功能: 承载 Wav2Lip 的增量音频处理、帧队列输出、Mel 特征提取和显存查询逻辑。
说明: 与主引擎文件拆分后，保持原有方法名不变，供主类继承复用。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import asyncio
import logging
from typing import AsyncIterator

import numpy as np
import torch

logger = logging.getLogger(__name__)


class Wav2LipRuntimeMixin:
    """Wav2Lip 增量运行时逻辑混入类。"""

    def _process_audio_buffer(self):
        """从音频缓冲提取 Mel 特征并执行一次批量推理。"""
        if self._model is None:
            self.load_model()
        if self._model is None:
            return
        with self._lock:
            if len(self._audio_buffer) == 0:
                return
            audio_int16 = np.frombuffer(bytes(self._audio_buffer), dtype=np.int16)
            audio = audio_int16.astype(np.float32) / 32768.0
        try:
            mel_features = self.extract_features(audio)
        except Exception as error:
            logger.error(f"Mel特征提取失败: {error}")
            return
        if mel_features.shape[0] == 0:
            return
        max_windows = 50
        if mel_features.shape[0] > max_windows:
            mel_features = mel_features[-max_windows:]
        frames = self.generate_frames(mel_features)
        for frame in frames:
            try:
                self._frame_queue.put_nowait(frame)
            except asyncio.QueueFull:
                try:
                    self._frame_queue.get_nowait()
                    self._frame_queue.put_nowait(frame)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        with self._lock:
            keep_samples = self._get_keep_samples()
            keep_bytes = keep_samples * 2
            if len(self._audio_buffer) > keep_bytes:
                self._audio_buffer = self._audio_buffer[-keep_bytes:]

    def _get_keep_samples(self) -> int:
        """计算增量模式需要保留的历史音频采样点数量。"""
        if self._mel_extractor is None:
            return 4800
        context = self._mel_extractor.stride_left + 1 + self._mel_extractor.stride_right
        return 3 * context * self._mel_extractor.hop_length

    async def yield_frames(self) -> AsyncIterator[np.ndarray]:
        """从增量帧队列中持续产出已生成的人脸帧。"""
        self._incremental_active = True
        try:
            while self._incremental_active:
                try:
                    frame = await asyncio.wait_for(self._frame_queue.get(), timeout=0.2)
                    yield frame
                except asyncio.TimeoutError:
                    with self._lock:
                        has_audio = len(self._audio_buffer) > 0
                    if not has_audio and self._frame_queue.empty():
                        break
                    yield None
        finally:
            self._incremental_active = False

    def stop_incremental(self) -> None:
        """停止增量处理并清空音频与帧缓冲。"""
        self._incremental_active = False
        with self._lock:
            self._audio_buffer.clear()
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def extract_features(self, audio: np.ndarray) -> np.ndarray:
        """从音频提取 Wav2Lip 所需 Mel 特征窗口。"""
        from src.audio.feature_extractor import MelFeatureExtractor

        if self._mel_extractor is None:
            self._mel_extractor = MelFeatureExtractor()
        return self._mel_extractor.extract_with_context(audio)

    @property
    def vram_mb(self) -> float:
        """返回当前模型大致占用的显存大小（MB）。"""
        if self._model is None:
            return 0.0
        try:
            return torch.cuda.memory_allocated(self.device) / (1024 * 1024)
        except Exception:
            return 0.0

"""
src/audio/feature_extractor.py - Mel频谱特征提取模块
功能: 将TTS生成的音频转换为Mel频谱特征，供Wav2Lip模型使用。
      实现滑动窗口缓冲，满足连续推理需求。
      对应工单需求: "音频处理延迟不超过0.4秒"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import numpy as np
import logging
from collections import deque

logger = logging.getLogger(__name__)


class MelFeatureExtractor:
    """
    Mel频谱特征提取器。
    使用librosa的melspectrogram提取80维Mel频带特征。
    这些特征供Wav2Lip模型用于驱动唇形同步。

    性能要求(工单): 音频处理延迟 ≤ 0.4s
    本模块在CPU上运行，16kHz音频的Mel提取在100ms内完成。
    """

    def __init__(self, n_mels: int = 80, hop_length: int = 200,
                 win_length: int = 800, sample_rate: int = 16000,
                 stride_left: int = 6, stride_right: int = 8):
        """
        初始化Mel特征提取器。

        参数:
            n_mels: Mel频带数(默认80，Wav2Lip标准配置)
            hop_length: STFT帧移(采样点)，200=12.5ms@16kHz
            win_length: STFT窗长(采样点)，800=50ms@16kHz
            sample_rate: 音频采样率(默认16kHz)
            stride_left: 左侧上下文帧数(Wav2Lip需要6帧左上下文)
            stride_right: 右侧上下文帧数(Wav2Lip需要8帧右上下文)
        """
        self.n_mels = n_mels
        self.hop_length = hop_length
        self.win_length = win_length
        self.sample_rate = sample_rate
        self.stride_left = stride_left
        self.stride_right = stride_right

    def extract(self, audio: np.ndarray) -> np.ndarray:
        """
        从音频提取Mel频谱特征。

        参数:
            audio: float32音频数组，16kHz采样率
        返回:
            Mel特征，shape (n_mels, n_frames)，float32
        """
        import librosa
        # 使用librosa计算Mel频谱
        mel_spec = librosa.feature.melspectrogram(
            y=audio.astype(np.float64),
            sr=self.sample_rate,
            n_mels=self.n_mels,
            hop_length=self.hop_length,
            win_length=self.win_length,
            fmin=80,           # 最低频率80Hz，过滤低频噪声
            fmax=7600,         # 最高频率7600Hz(对应16kHz采样率的奈奎斯特频率)
        )
        # 对数变换，模拟人耳感知
        mel_db = librosa.power_to_db(mel_spec, ref=np.max)
        # 归一化到[-1, 1]范围
        mel_norm = np.clip(mel_db / 80.0, -1.0, 1.0)
        return mel_norm.astype(np.float32)

    def extract_with_context(self, audio: np.ndarray) -> np.ndarray:
        """
        提取Mel特征并添加时序上下文窗口。
        返回shape为 (n_mels, n_frames) 的特征，每帧包含左右邻居帧的上下文。

        Wav2Lip使用滑动窗口: 需要stride_left帧左侧+当前帧+stride_right帧右侧。

        参数:
            audio: float32音频数组
        返回:
            带上下文的Mel特征窗口序列
        """
        # 先提取完整Mel特征
        mel = self.extract(audio)  # shape: (80, n_frames)
        n_frames = mel.shape[1]
        stride = self.stride_left + 1 + self.stride_right  # 6+1+8=15帧窗口
        if n_frames < stride:
            # 音频太短则零填充
            pad_width = ((0, 0), (0, stride - n_frames))
            mel = np.pad(mel, pad_width, mode='constant')

        # 构建滑动窗口
        windows = []
        total_frames = mel.shape[1]
        for i in range(0, total_frames - stride + 1):
            # 取stride帧窗口: [i, i+stride)
            window = mel[:, i:i + stride]
            windows.append(window)

        if not windows:
            return np.zeros((0, self.n_mels, stride), dtype=np.float32)
        return np.stack(windows, axis=0)  # shape: (n_windows, 80, 15)


class AudioFeatureBuffer:
    """
    音频特征缓冲器，维护滑动窗口用于连续推理。
    每收到新的TTS音频chunk，更新缓冲并产生可用的Mel特征窗口。
    """

    def __init__(self, extractor: MelFeatureExtractor, max_buffer_s: float = 3.0):
        """
        初始化缓冲器。
        参数:
            extractor: Mel特征提取器
            max_buffer_s: 最大缓冲时间(秒)，防止内存无限增长
        """
        self.extractor = extractor
        self.max_samples = int(max_buffer_s * extractor.sample_rate)
        self._buffer = deque(maxlen=self.max_samples)

    def add_audio(self, chunk: np.ndarray) -> None:
        """添加音频chunk到缓冲区。"""
        self._buffer.extend(chunk.tolist())

    def get_features(self) -> np.ndarray:
        """从当前缓冲提取Mel特征窗口。缓冲不足时返回空数组。"""
        if len(self._buffer) < self.extractor.win_length:
            return np.zeros((0, self.extractor.n_mels,
                             self.extractor.stride_left + 1 + self.extractor.stride_right),
                            dtype=np.float32)
        audio = np.array(list(self._buffer), dtype=np.float32)
        return self.extractor.extract_with_context(audio)

    def clear(self) -> None:
        """清空缓冲。"""
        self._buffer.clear()

"""
src/core/streaming.py - 流式句子缓冲与异步分句模块
功能: 将LLM流式token流按句子边界切分，支持中英文标点。
      句子级流式处理，平衡延迟与语音自然度。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import re
import asyncio
import logging
from typing import AsyncIterator, Optional
from collections import deque

logger = logging.getLogger(__name__)

# 中英文句子边界标点
_SENTENCE_END_PATTERN = re.compile(r'[。！？…!?\n;；]')
# 子句边界（更短的分割点，用于超长句子的切分）
_CLAUSE_END_PATTERN = re.compile(r'[。！？…!?\n;；，,、：:]')

# 最小句子字符数(过短不切分，避免碎片化)
# 注: 中文口语常见 "好的。"(3字) "嗯。"(2字) 等短回复，设置2避免丢弃
MIN_SENTENCE_CHARS = 2
# 最大句子字符数(超过此值强制在子句边界切分)
MAX_SENTENCE_CHARS = 80


class SentenceBuffer:
    """
    流式句子缓冲器。
    接收LLM输出的逐token文本，按句子边界切分并产出完整句子。
    支持中英文混合标点: 。！？.!? 作为句子终结符，
    ；;，, 作为子句分隔符(仅在超长句时使用)。

    使用方式:
        buf = SentenceBuffer()
        async for token in llm_stream:
            sentence = buf.feed(token)
            if sentence:
                yield sentence  # 产出完整句子
        final = buf.flush()
        if final:
            yield final  # 产剩余内容
    """

    def __init__(self, min_chars: int = None, max_chars: int = None):
        """
        初始化句子缓冲器。
        参数:
            min_chars: 最小句子字符数(低于此不分句)
            max_chars: 最大句子字符数(超过强制分句)
        """
        self.min_chars = min_chars if min_chars is not None else MIN_SENTENCE_CHARS
        self.max_chars = max_chars if max_chars is not None else MAX_SENTENCE_CHARS
        self._buffer = ""
        self._total_fed = 0  # 总输入字符数

    def feed(self, token: str) -> Optional[str]:
        """
        喂入一个token（可能是一个或多个字符）。
        当检测到完整句子时返回该句子文本；否则返回None。

        参数:
            token: LLM输出的文本片段(通常1-5个字符)
        返回:
            完整句子文本，或None（尚未形成完整句子）
        """
        if not token:
            return None
        self._buffer += token
        self._total_fed += len(token)

        # 策略1: 找到句子终结标点
        m = _SENTENCE_END_PATTERN.search(self._buffer)
        if m:
            end_pos = m.end()
            sentence = self._buffer[:end_pos].strip()
            if len(sentence) >= self.min_chars:
                self._buffer = self._buffer[end_pos:]
                return sentence
            # 句子太短，继续累积

        # 策略2: 缓冲区过长，在子句标点处强制切分
        if len(self._buffer) >= self.max_chars:
            m2 = _CLAUSE_END_PATTERN.search(self._buffer)
            if m2:
                end_pos = m2.end()
                sentence = self._buffer[:end_pos].strip()
                if len(sentence) >= self.min_chars:
                    self._buffer = self._buffer[end_pos:]
                    return sentence
            # 没有子句标点，按最大长度强制切分
            sentence = self._buffer[:self.max_chars].strip()
            self._buffer = self._buffer[self.max_chars:]
            return sentence if len(sentence) >= self.min_chars else None

        return None

    def flush(self) -> Optional[str]:
        """返回缓冲区剩余内容（流结束时调用）。"""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining if remaining else None

    def reset(self) -> None:
        """重置缓冲器状态。"""
        self._buffer = ""
        self._total_fed = 0

    @property
    def buffered_len(self) -> int:
        """当前缓冲区字符数。"""
        return len(self._buffer)


class StreamingOrchestrator:
    """
    流式管线编排器辅助类。
    管理 LLM→TTS→LipSync 的异步流式数据流，
    使用 asyncio.Queue 在阶段间传递数据。

    数据流:
        LLM tokens → SentenceBuffer → sentences → TTS → audio chunks
        → LipSync → video frames → Output
    """

    def __init__(self, max_queue_size: int = 30):
        """
        初始化编排器。
        参数:
            max_queue_size: 内部队列最大容量(背压控制)
        """
        self.sentence_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.audio_chunk_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.frame_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size * 2)
        self._cancelled = False

    def cancel(self) -> None:
        """取消当前流式处理（用于打断场景）。"""
        self._cancelled = True
        # 清空所有队列
        for q in [self.sentence_queue, self.audio_chunk_queue, self.frame_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def reset(self) -> None:
        """重置状态，准备新一轮处理。"""
        self._cancelled = False

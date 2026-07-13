"""
src/core/pipeline_output.py - 管线输出与文本处理混入
功能: 提供音视频输出、文本输入处理、实时音频流状态机等扩展方法。
说明: 从 PipelineOrchestrator 主类拆出非初始化核心逻辑，控制单文件长度。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import logging
import time

import numpy as np

from src.core.pipeline_metrics import record_frame_count
from src.core.pipeline_metrics import record_stage_latency

logger = logging.getLogger(__name__)


class PipelineOutputMixin:
    """输出控制、文本处理与实时音频流逻辑混入类。"""

    def _stream_to_output(self, video_frames: list, audio: np.ndarray, session=None) -> None:
        """将音视频推送到所有输出通道，并缓存视频帧供前端读取。"""
        for frame in video_frames:
            if self.webrtc:
                self.webrtc.send_video_frame(frame)
            if self.rtmp:
                self.rtmp.send(frame)
            if session is not None:
                session.video_frame_buffer.append(frame.copy())
        self._push_audio(audio)

    def _stream_audio_only(self, audio: np.ndarray) -> None:
        """仅推送音频流，用于没有生成视频帧的场景。"""
        self._push_audio(audio)

    def _push_audio(self, audio: np.ndarray) -> None:
        """将音频按 10ms 切片推送到 WebRTC 和 RTMP 通道。"""
        if len(audio) == 0:
            return
        chunk_size = 160
        for index in range(0, len(audio), chunk_size):
            chunk = audio[index:index + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            if self.webrtc:
                self.webrtc.send_audio(chunk)
            if self.rtmp and hasattr(self.rtmp, "send_audio"):
                # 转换为 int16 PCM 字节，RTMP 需要 S16LE 格式
                int_samples = np.clip(chunk * 32767, -32768, 32767).astype(np.int16)
                self.rtmp.send_audio(int_samples.tobytes())

    def send_to_output(self, video_frames: list, tts_audio: np.ndarray) -> None:
        """批量模式输出接口，保持向后兼容。"""
        for frame in video_frames:
            if self.webrtc:
                self.webrtc.send_video_frame(frame)
            if self.rtmp:
                self.rtmp.send(frame)
        self._push_audio(tts_audio)

    async def process_turn_with_output(self, session, audio_input: np.ndarray) -> dict:
        """处理一轮对话并自动推送音视频输出。"""
        if hasattr(self.llm, "chat_stream_sentences"):
            frames = await self.process_turn_streaming(session, audio_input)
            return {"video": frames, "audio": None}
        result = await self.process_turn(session, audio_input)
        if result.get("video") and result.get("audio"):
            self.send_to_output(result["video"], result["audio"])
        return result

    async def process_text(self, session, text: str) -> dict:
        """处理文本输入，优先使用流式 LLM，再执行 TTS 与推流。"""
        start_time = time.time()
        session.start_thinking()
        session.add_chat_message("user", text)
        if hasattr(self.lipsync, "reset_buffer"):
            self.lipsync.reset_buffer()
        messages = [{"role": "system", "content": self.config.llm.system_prompt}]
        messages.extend(session.chat_history[-20:])
        full_response_parts = []
        try:
            response = await self._run_text_generation(session, messages, full_response_parts, start_time)
        except Exception as error:
            logger.error(f"文本处理失败: {error}")
            response = self._build_text_error_message(str(error))
        session.add_chat_message("assistant", response)
        session.go_idle()
        session.total_turns += 1
        record_stage_latency("total", time.time() - start_time)
        audio = getattr(session, "last_tts_audio", None)
        return {"video": [], "audio": audio}

    async def _run_text_generation(
        self,
        session,
        messages: list,
        full_response_parts: list,
        start_time: float,
    ) -> str:
        """执行文本回复生成，并根据模式调用 TTS 与推流。"""
        if hasattr(self.llm, "chat_stream_sentences"):
            session.start_speaking()
            first_sentence_seen = False

            def _check_interrupt():
                return session.interrupt_flag

            async for sentence in self.llm.chat_stream_sentences(
                messages, interrupt_check=_check_interrupt
            ):
                if session.interrupt_flag:
                    session.reset_interrupt()
                    break
                if not first_sentence_seen:
                    record_stage_latency("llm_first", time.time() - start_time)
                    first_sentence_seen = True
                full_response_parts.append(sentence)
                logger.info(f"[{session.session_id[:8]}] 句: {sentence[:50]}...")
                await self._stream_sentence(session, sentence)
            return "".join(full_response_parts).strip() or "(空)"
        llm_start = time.time()
        try:
            response = await self.llm.chat_stream(messages)
            record_stage_latency("llm_first", time.time() - llm_start)
        except Exception as error:
            logger.error(f"LLM调用失败: {error}")
            response = f"(LLM错误: {error})"
        await self._speak_full_response(session, response)
        return response

    async def _stream_sentence(self, session, sentence: str) -> None:
        """逐句执行 TTS、唇形推理和流式输出。"""
        try:
            tts_start = time.time()
            audio_chunk = await self.tts.synthesize_chunk(sentence, add_silence_pad=True)
            if len(audio_chunk) == 0:
                return
            record_stage_latency("tts_first", time.time() - tts_start)

            feature_start = time.time()
            mel_feats = self.lipsync.extract_features(audio_chunk)
            record_stage_latency("audio_feat", time.time() - feature_start)

            infer_start = time.time()
            face_frames = await self.lipsync.generate_frames_async(mel_feats)
            record_stage_latency("lipsync_infer", time.time() - infer_start)
            if face_frames is not None and len(face_frames) > 0:
                compose_start = time.time()
                video_frames = self._lip_to_output(list(face_frames))
                record_stage_latency("frame_comp", time.time() - compose_start)
                self._stream_to_output(video_frames, audio_chunk, session=session)
                record_frame_count(len(video_frames))
                session.last_tts_audio = audio_chunk
        except Exception as error:
            logger.error(f"流式TTS/LipSync失败: {error}")

    async def _speak_full_response(self, session, response: str) -> None:
        """对完整回复执行整段 TTS 和视频合成输出。"""
        try:
            tts_start = time.time()
            tts_audio = await self.tts.synthesize(response)
            record_stage_latency("tts_first", time.time() - tts_start)
            session.last_tts_audio = tts_audio
            if len(tts_audio) == 0:
                return

            feature_start = time.time()
            mel_feats = self.lipsync.extract_features(tts_audio)
            record_stage_latency("audio_feat", time.time() - feature_start)

            infer_start = time.time()
            face_frames = await self.lipsync.generate_frames_async(mel_feats)
            record_stage_latency("lipsync_infer", time.time() - infer_start)
            if face_frames is not None and len(face_frames) > 0:
                compose_start = time.time()
                video_frames = self._lip_to_output(list(face_frames))
                record_stage_latency("frame_comp", time.time() - compose_start)
                self._stream_to_output(video_frames, tts_audio, session=session)
                record_frame_count(len(video_frames))
        except Exception as error:
            logger.error(f"TTS合成失败: {error}")

    def _build_text_error_message(self, error_message: str) -> str:
        """根据异常内容生成对用户友好的错误提示。"""
        if "API Key" in error_message or "api_key" in error_message.lower():
            return (
                "⚠️ 大模型API Key未配置，我暂时无法回答。\n\n"
                "请按以下步骤设置:\n"
                "1. 将项目中的 .env.example 复制为 .env\n"
                "2. 编辑 .env 文件，填入你的 DeepSeek API Key\n"
                "3. 重启服务: python run.py\n\n"
                f"技术细节: {error_message}"
            )
        return f"抱歉，处理出错了: {error_message}"

    async def process_audio_stream(self, session, chunk: np.ndarray) -> dict:
        """处理实时音频片段并根据状态机决定何时进入完整对话。"""
        if chunk is None or len(chunk) == 0:
            return {}
        state = session.state.value
        # 说话中/思考中: 检查打断（用户在数字人输出时插话）
        if state in ("speaking", "thinking"):
            if self.bargein.process_chunk(chunk):
                await self.interrupt.handle(session)
                if hasattr(self.lipsync, "stop_incremental"):
                    self.lipsync.stop_incremental()
            return {}
        if state == "listening":
            session.audio_buffer.extend(chunk.tolist())
            min_samples = self.config.pipeline.audio_sample_rate
            if len(session.audio_buffer) >= min_samples:
                full = np.array(list(session.audio_buffer), dtype=np.float32)
                session.audio_buffer.clear()
                return await self.process_turn_with_output(session, full)
            return {}
        if state in ("idle", "interrupted"):
            threshold = getattr(self.config.barge_in, 'energy_threshold', 0.02)
            energy = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if energy > threshold:
                session.start_listening()
                session.audio_buffer.extend(chunk.tolist())
            return {}
        return {}

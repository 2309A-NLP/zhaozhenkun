"""
src/core/pipeline.py - 管线编排器
功能: 管理实时数字人核心处理流程，包括批量对话、流式对话和唇形帧转换。
说明: 输出控制、文本处理、实时音频流状态机已拆分到 pipeline_output.py。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import asyncio
import logging
import time

import cv2
import numpy as np

from src.core.pipeline_metrics import record_frame_count
from src.core.pipeline_metrics import record_stage_latency
from src.core.pipeline_output import PipelineOutputMixin

logger = logging.getLogger(__name__)


class PipelineOrchestrator(PipelineOutputMixin):
    """管线编排器，负责 ASR→LLM→TTS→LipSync→输出的主流程控制。"""

    def __init__(self, config, session_manager, asr_engine, llm_client, tts_engine,
                 lipsync_engine, compositor, bargein_detector, interrupt_handler,
                 webrtc_output=None, rtmp_output=None, idle_player=None):
        self.config = config
        self.sessions = session_manager
        self.asr = asr_engine
        self.llm = llm_client
        self.tts = tts_engine
        self.lipsync = lipsync_engine
        self.compositor = compositor
        self.bargein = bargein_detector
        self.interrupt = interrupt_handler
        self.webrtc = webrtc_output
        self.rtmp = rtmp_output
        self.idle_player = idle_player

    async def process_turn(self, session, audio_input: np.ndarray) -> dict:
        """处理一轮完整批量对话，返回整段视频帧和音频。"""
        start_time = time.time()
        session.start_thinking()
        user_text = await self._transcribe_audio(session, audio_input, start_time)
        if not user_text:
            return {}
        session.add_chat_message("user", user_text)
        messages = self._build_messages(session)
        response_text = await self._run_batch_llm(session, messages, start_time)
        session.add_chat_message("assistant", response_text)
        session.start_speaking()
        tts_audio, face_frames = await self._run_batch_tts_and_lipsync(response_text, start_time)
        compose_start = time.time()
        video_frames = self._lip_to_output(face_frames)
        record_stage_latency("frame_comp", time.time() - compose_start)
        self._log_batch_summary(session, start_time, tts_audio, video_frames)
        record_stage_latency("total", time.time() - start_time)
        record_frame_count(len(video_frames))
        session.go_idle()
        session.total_turns += 1
        return {"video": video_frames, "audio": tts_audio}

    async def process_turn_streaming(self, session, audio_input: np.ndarray) -> list:
        """处理一轮流式对话，边生成边推流，返回生成后的视频帧列表。"""
        start_time = time.time()
        all_frames = []
        session.start_thinking()
        user_text = await self._transcribe_audio(session, audio_input, start_time)
        if not user_text:
            return []
        session.add_chat_message("user", user_text)
        self._reset_lipsync_buffer()
        messages = self._build_messages(session, use_custom_prompt=True)
        full_response, sentence_count, first_sentence_time, cancelled = await self._stream_llm_sentences(
            session,
            messages,
            all_frames,
            start_time,
        )
        response_text = "".join(full_response).strip() if full_response else "(空)"
        session.add_chat_message("assistant", response_text)
        session.last_tts_audio = np.array([], dtype=np.float32)
        self._finalize_streaming_session(
            session,
            all_frames,
            sentence_count,
            first_sentence_time,
            start_time,
            cancelled,
        )
        return all_frames

    async def _transcribe_audio(self, session, audio_input: np.ndarray, start_time: float) -> str:
        """执行 ASR 识别并打印日志，失败或空文本时返回空字符串。"""
        try:
            user_text = await self.asr.transcribe(audio_input)
        except Exception as error:
            logger.error(f"ASR识别失败: {error}")
            session.go_idle()
            return ""
        elapsed = time.time() - start_time
        record_stage_latency("asr", elapsed)
        logger.info(f"[{session.session_id[:8]}] ASR({elapsed:.2f}s): '{user_text[:60]}'")
        if not user_text.strip():
            session.go_idle()
            return ""
        return user_text

    def _build_messages(self, session, use_custom_prompt: bool = False) -> list:
        """构造发送给 LLM 的上下文消息列表。"""
        system_prompt = self.config.llm.system_prompt
        if use_custom_prompt:
            system_prompt = session.custom_system_prompt or system_prompt
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(session.chat_history[-20:])
        return messages

    async def _run_batch_llm(self, session, messages: list, start_time: float) -> str:
        """执行批量 LLM 调用并输出耗时日志。"""
        llm_start = time.time()
        response_text = await self.llm.chat_stream(messages)
        elapsed = time.time() - llm_start
        record_stage_latency("llm_first", elapsed)
        logger.info(f"[{session.session_id[:8]}] LLM({elapsed:.2f}s): {response_text[:60]}...")
        logger.debug(f"[{session.session_id[:8]}] 已耗时 {time.time() - start_time:.2f}s")
        return response_text

    async def _run_batch_tts_and_lipsync(self, response_text: str, start_time: float = None):
        """执行整段 TTS、特征提取和唇形帧生成，并记录关键阶段耗时。"""
        tts_start = time.time()
        tts_audio = await self.tts.synthesize(response_text)
        record_stage_latency("tts_first", time.time() - tts_start)

        feature_start = time.time()
        mel_feats = self.lipsync.extract_features(tts_audio)
        record_stage_latency("audio_feat", time.time() - feature_start)

        infer_start = time.time()
        face_frames = await self.lipsync.generate_frames_async(mel_feats)
        record_stage_latency("lipsync_infer", time.time() - infer_start)
        return tts_audio, face_frames

    def _log_batch_summary(self, session, start_time: float, tts_audio: np.ndarray, video_frames: list) -> None:
        """记录批量模式处理结果摘要。"""
        total_time = time.time() - start_time
        logger.info(
            f"[{session.session_id[:8]}] 完成: total={total_time:.2f}s "
            f"audio={len(tts_audio)} samples video={len(video_frames)} frames"
        )

    def _reset_lipsync_buffer(self) -> None:
        """在新一轮对话开始前重置唇形同步缓冲。"""
        if hasattr(self.lipsync, "reset_buffer"):
            self.lipsync.reset_buffer()

    async def _stream_llm_sentences(self, session, messages: list, all_frames: list, start_time: float):
        """逐句处理 LLM 流式输出，并将音视频增量写入输出通道。"""
        full_response = []
        sentence_count = 0
        first_sentence_time = None
        cancelled = False
        session.start_speaking()
        # 构造实时打断检查回调，供 LLM 流在逐 token 级别检查
        def _check_interrupt():
            return session.interrupt_flag

        try:
            async for sentence in self.llm.chat_stream_sentences(
                messages, interrupt_check=_check_interrupt
            ):
                if session.interrupt_flag:
                    cancelled = True
                    session.reset_interrupt()
                    break
                sentence_count += 1
                if first_sentence_time is None:
                    first_sentence_time = time.time() - start_time
                    record_stage_latency("llm_first", first_sentence_time)
                full_response.append(sentence)
                logger.info(f"[{session.session_id[:8]}] 句子#{sentence_count}: '{sentence[:50]}...'")
                await self._stream_sentence_chunk(session, sentence, sentence_count, all_frames)
        except Exception as error:
            logger.error(f"流式处理异常: {error}")
        return full_response, sentence_count, first_sentence_time, cancelled

    async def _stream_sentence_chunk(self, session, sentence: str, sentence_count: int, all_frames: list) -> None:
        """对单句文本执行 TTS、LipSync 与输出推送。"""
        try:
            audio_chunk = await self.tts.synthesize_chunk(sentence, add_silence_pad=(sentence_count > 1), voice=session.voice)
        except TypeError:
            audio_chunk = await self.tts.synthesize_chunk(sentence, add_silence_pad=(sentence_count > 1))
        except Exception as error:
            logger.error(f"TTS句子合成失败: {error}")
            return
        if len(audio_chunk) == 0:
            return
        try:
            face_frames = await self._lipsync_incremental(audio_chunk)
        except Exception as error:
            logger.error(f"LipSync增量失败: {error}")
            face_frames = []
        if face_frames:
            video_frames = self._lip_to_output(list(face_frames))
            all_frames.extend(video_frames)
            self._stream_to_output(video_frames, audio_chunk, session=session)
        else:
            self._stream_audio_only(audio_chunk)

    def _finalize_streaming_session(self, session, all_frames: list, sentence_count: int,
                                    first_sentence_time, start_time: float, cancelled: bool) -> None:
        """写回流式性能指标并结束会话状态。"""
        total_time = time.time() - start_time
        ttff = first_sentence_time or total_time
        logger.info(
            f"[{session.session_id[:8]}] 流式完成: total={total_time:.2f}s "
            f"TTFF={ttff:.2f}s 句子={sentence_count} 帧={len(all_frames)} "
            f"{'被打断' if cancelled else ''}"
        )
        session.last_ttff_ms = ttff * 1000
        session.last_total_ms = total_time * 1000
        self._record_stream_metrics(all_frames, total_time)
        if cancelled:
            session.start_listening()
        else:
            session.go_idle()
        session.total_turns += 1

    def _record_stream_metrics(self, all_frames: list, total_time: float) -> None:
        """记录流式模式性能指标。"""
        try:
            from src.utils.metrics import get_metrics
            metrics = get_metrics()
            metrics.record_stage("total", total_time)
            for _ in all_frames:
                metrics.record_frame()
        except ImportError:
            return

    def _lip_to_output(self, face_frames: list) -> list:
        """将唇形帧转为输出帧，SadTalker 直通，其余经 compositor 合成。"""
        if getattr(self.lipsync, "generates_full_frames", False):
            output_frames = []
            output_width = self.config.pipeline.video_width
            output_height = self.config.pipeline.video_height
            for frame in face_frames:
                if frame.shape[0] == 3:
                    frame = frame.transpose(1, 2, 0)
                if frame.shape[:2] != (output_height, output_width):
                    frame = cv2.resize(frame, (output_width, output_height))
                output_frames.append(frame)
            return output_frames
        return self.compositor.composite(face_frames, silent=False)

    async def _lipsync_incremental(self, audio_chunk: np.ndarray) -> list:
        """对音频块执行增量 Mel 特征提取并生成对应的人脸帧。"""
        mel_feats = self.lipsync.extract_features(audio_chunk)
        if mel_feats.shape[0] == 0:
            return []
        frames = await self.lipsync.generate_frames_async(mel_feats)
        if frames is None or len(frames) == 0:
            return []
        return list(frames)

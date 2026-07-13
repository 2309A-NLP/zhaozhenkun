"""
src/lipsync/sadtalker_inference.py - SadTalker 推理辅助逻辑
功能: 承载头像加载、音频缓存、占位帧生成以及真正的 SadTalker 推理流程。
说明: 从主引擎文件中拆出大段推理与资源处理逻辑，减少主文件长度。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import os
import tempfile
import wave

import cv2
import numpy as np
import torch


def placeholder_frames(img_size: int, frame_count: int) -> np.ndarray:
    """返回灰色占位帧，避免上层因空结果崩溃。"""
    if frame_count <= 0:
        frame_count = 1
    return np.ones((frame_count, 3, img_size, img_size), dtype=np.uint8) * 128


class SadTalkerInferenceMixin:
    """SadTalker 资源加载与推理辅助混入类。"""

    def reset_buffer(self) -> None:
        """重置音频缓冲和帧缓存，供新一轮对话调用。"""
        self._audio_buffer.clear()
        self._cached_frames.clear()
        self._cached_face = None
        self._frames_served = 0
        self._last_audio = None

    def _load_avatar_image(self):
        """加载用户上传头像，失败时回退默认头像或灰底占位图。"""
        import glob

        avatar_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "static", "avatars"))
        os.makedirs(avatar_dir, exist_ok=True)
        files = sorted(glob.glob(os.path.join(avatar_dir, "avatar_*.png")), key=os.path.getmtime, reverse=True)
        for file_path in files:
            image = self._read_image(file_path)
            if image is not None:
                return image
        static_dir = os.path.normpath(os.path.join(avatar_dir, ".."))
        for filename in ["person.png", "avatar.jpg"]:
            image = self._read_image(os.path.join(static_dir, filename), fallback_name=filename)
            if image is not None:
                return image
        return np.ones((512, 512, 3), dtype=np.uint8) * 200

    def _read_image(self, path: str, fallback_name: str = ""):
        """以二进制方式读取图片，规避中文路径问题。"""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as file:
                data = np.frombuffer(file.read(), dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if image is not None:
                if fallback_name:
                    self._log(f"使用默认头像: {fallback_name}")
                else:
                    self._log(f"加载头像: {os.path.basename(path)} ({image.shape[1]}x{image.shape[0]})")
            return image
        except Exception as error:
            self._warn(f"读取头像失败: {path}: {error}")
            return None

    async def generate_frames_async(self, mel_features, face_images=None):
        """在线程池中异步执行 SadTalker 帧生成。"""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._infer_pool, self.generate_frames, mel_features, face_images)

    def extract_features(self, audio: np.ndarray) -> np.ndarray:
        """提取 Mel 特征并缓存原始音频，供后续 SadTalker 推理使用。"""
        audio_flat = audio if audio.ndim == 1 else audio.flatten()
        self._audio_buffer.append(audio_flat.astype(np.float32))
        self._last_audio = np.concatenate(self._audio_buffer) if self._audio_buffer else audio.astype(np.float32)
        from src.audio.feature_extractor import MelFeatureExtractor

        if self._mel_extractor is None:
            self._mel_extractor = MelFeatureExtractor()
        return self._mel_extractor.extract_with_context(audio)

    def generate_talking_video(self, tts_audio: np.ndarray, face_image: np.ndarray) -> list:
        """调用 SadTalker 真实推理流程，返回 BGR 帧列表。"""
        if not self._loaded:
            self.load_model()
        # 确保 numpy 兼容补丁在每次推理前生效（load_model 中已调用，此处为安全冗余）
        if hasattr(self, '_patch_numpy_compat'):
            self._patch_numpy_compat()
        if self._model is None:
            self._warn("SadTalker 模型未就绪，无法生成唇形视频")
            return []
        audio_path, img_path = self._create_temp_paths()
        try:
            self._write_audio_file(audio_path, tts_audio)
            self._write_image_file(img_path, face_image)
            result = self._run_sadtalker_test(img_path, audio_path)
            return self._collect_result_frames(result)
        except Exception as error:
            self._error(f"SadTalker推理失败: {error}")
            return []
        finally:
            self._cleanup_temp_files(audio_path, img_path)

    def _create_temp_paths(self):
        """创建推理用临时音频和图片路径。"""
        fd_audio, audio_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd_audio)
        fd_image, image_path = tempfile.mkstemp(suffix=".png")
        os.close(fd_image)
        return audio_path, image_path

    def _write_audio_file(self, audio_path: str, tts_audio: np.ndarray) -> None:
        """把 float32 音频写成 SadTalker 可读取的 WAV 文件。"""
        audio_i16 = (tts_audio * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(audio_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_i16.tobytes())

    def _write_image_file(self, image_path: str, face_image: np.ndarray) -> None:
        """把头像图像编码为 PNG 临时文件。"""
        ok, buffer = cv2.imencode(".png", face_image)
        if ok:
            with open(image_path, "wb") as file:
                file.write(buffer.tobytes())

    def _run_sadtalker_test(self, image_path: str, audio_path: str):
        """执行 SadTalker 官方 test 调用。"""
        with torch.no_grad():
            return self._model.test(
                source_image=image_path,
                driven_audio=audio_path,
                preprocess="crop",
                still_mode=True,
                use_enhancer=False,
                batch_size=2,
                size=512,
                pose_style=0,
            )

    def _collect_result_frames(self, result) -> list:
        """把 SadTalker 返回结果统一转换为 BGR 帧列表。"""
        if isinstance(result, list) and len(result) > 0:
            frames = []
            for frame in result:
                if frame.dtype != np.uint8:
                    frame = (frame * 255).clip(0, 255).astype(np.uint8)
                frames.append(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            self._log(f"SadTalker生成: {len(frames)}帧")
            return frames
        if isinstance(result, str) and os.path.exists(result):
            return self._extract_frames_from_video(result)
        self._warn("SadTalker返回空结果")
        return []

    def _extract_frames_from_video(self, video_path: str) -> list:
        """从 SadTalker 输出视频文件中逐帧提取 BGR 图像。"""
        frames = []
        capture = cv2.VideoCapture(video_path)
        while True:
            success, frame = capture.read()
            if not success:
                break
            frames.append(frame)
        capture.release()
        self._log(f"SadTalker从视频提取: {len(frames)}帧")
        return frames

    def _cleanup_temp_files(self, *paths: str) -> None:
        """删除推理产生的临时文件。"""
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

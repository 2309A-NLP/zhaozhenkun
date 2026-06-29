# -*- coding: utf-8 -*-
"""
dh_compositor.py — 数字人占位模式 + 视频合成模块
--------------------------------------------------------------
功能: 占位帧生成（基于音频时长+头像）、音视频FFmpeg合成、全局单例。
      当 SadTalker 不可用时使用占位模式：保留数字人形象，音频正常输出。

所有函数以 `self` (DigitalHumanEngine 实例) 为第一个参数。
composite_audio_video 为 staticmethod（不需要 self）。

被 digital_human.py 绑定为类方法，asr/voice_pipeline 通过 get_digital_human() 获取。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, subprocess, tempfile, logging  # 标准库
import numpy as np                        # 数值计算
import cv2                                # 图像处理
from concurrent.futures import ThreadPoolExecutor  # GPU推理线程池
from typing import Optional                         # 类型注解

logger = logging.getLogger("digital_human")

# 独立推理线程（GPU 推理在线程池中执行，不阻塞主线程）
_infer_executor = ThreadPoolExecutor(max_workers=1)


# ================================================================
# 头像管理方法（从 digital_human.py 移入，绑定为 self.xxx）
# ================================================================
def restore_avatar_from_disk(self) -> None:
    """从持久化文件恢复头像（重启后自动加载）。

    参数:
        self: DigitalHumanEngine 实例
    """
    if self.avatar_path:
        img = try_load_avatar_from_path(self, self.avatar_path)
        if img is not None: return
    if os.path.exists(self.LAST_AVATAR_FILE):
        try:
            with open(self.LAST_AVATAR_FILE, 'r', encoding='utf-8') as f:
                saved = f.read().strip()
            if saved:
                # 路径解析: 绝对路径直接用，相对路径拼接到 AVATARS_DIR
                path = saved if (os.path.isabs(saved) and os.path.exists(saved)) \
                       else os.path.join(self.AVATARS_DIR, os.path.basename(saved))
                if os.path.exists(path):
                    img = try_load_avatar_from_path(self, path)
                    if img is not None:
                        self.avatar_path = path
                        logger.info("数字人形象已从持久化恢复: %s", path)
                        return
        except Exception as e:
            logger.error("读取.last_avatar失败: %s", e)
    logger.info("未找到已保存的头像，使用内置默认形象")


def get_source_image(self) -> np.ndarray:
    """获取参考人脸图像（SadTalker 需要）。
    优先级: 1)内存中已加载 → 2)磁盘持久化 → 3)兜底占位图

    参数:
        self: DigitalHumanEngine 实例
    返回: BGR 人脸图像
    """
    if self._avatar_frame is not None:
        return self._avatar_frame
    logger.warning("无可用头像，使用内置形象。请上传人物照片获得更好效果。")
    return create_fallback_face_image(self)


def imread_safe(self, path: str) -> np.ndarray | None:
    """安全读取图片: imdecode 避免 Windows 中文路径问题。

    参数:
        path: 图片文件路径
    返回: BGR 图像数组，失败返回 None
    """
    if not path or not os.path.exists(path): return None
    try:
        with open(path, 'rb') as f:
            data = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception: return None


def try_load_avatar_from_path(self, path: str) -> np.ndarray | None:
    """从路径加载头像图片到 self._avatar_frame。

    参数:
        path: 图片文件路径
    返回: BGR 图像数组，失败返回 None
    """
    img = imread_safe(self, path)
    if img is not None and img.shape[0] > 50 and img.shape[1] > 50:
        self._avatar_frame = img
        logger.info("数字人形象: %s (%dx%d)", path, img.shape[1], img.shape[0])
        return img
    return None


def create_fallback_face_image(self) -> np.ndarray:
    """创建含简单人脸轮廓的兜底形象（可被 SadTalker 检测到面部特征点）。

    生成一张 512x512 像素的卡通风格人脸，包含：脸部椭圆、双眼、嘴巴、眉毛。
    当用户未上传真实头像时使用，确保数字人管线不中断。

    返回: 512x512 BGR 兜底人脸图像
    """
    img = np.ones((512, 512, 3), dtype=np.uint8) * 220         # 浅灰背景

    # --- 脸型: 肤色椭圆（中心偏上，给人脸留出颈部空间）---
    cv2.ellipse(img, (256, 240), (120, 150), 0, 0, 360,
                 (180, 150, 130), -1)  # (cx,cy), (rx,ry), 肤色填充

    # --- 双眼: 白色巩膜 + 深色瞳孔 ---
    # 左眼
    cv2.circle(img, (210, 200), 15, (255, 255, 255), -1)   # 巩膜（白色圆）
    cv2.circle(img, (210, 200), 8, (60, 40, 20), -1)       # 瞳孔（深棕色）
    # 右眼
    cv2.circle(img, (302, 200), 15, (255, 255, 255), -1)   # 巩膜
    cv2.circle(img, (302, 200), 8, (60, 40, 20), -1)       # 瞳孔

    # --- 嘴巴: 半椭圆弧线 ---
    cv2.ellipse(img, (256, 300), (30, 15), 0, 0, 180,
                 (140, 80, 70), -1)  # 下半圆弧，淡红色

    # --- 眉毛: 两条短线 ---
    cv2.line(img, (190, 160), (230, 155), (60, 40, 20), 3)  # 左眉
    cv2.line(img, (282, 155), (322, 160), (60, 40, 20), 3)  # 右眉

    self._avatar_frame = img
    return img


def set_avatar_impl(self, image_path: str) -> bool:
    """设置/更换数字人形象，并持久化（重启后自动恢复）。

    参数:
        image_path: 含人物的图片路径
    返回: True=设置成功
    """
    if os.path.exists(image_path):
        img = imread_safe(self, image_path)
        if img is not None:
            self._avatar_frame = img; self.avatar_path = image_path
            try:
                os.makedirs(os.path.dirname(self.LAST_AVATAR_FILE), exist_ok=True)
                with open(self.LAST_AVATAR_FILE, 'w', encoding='utf-8') as f:
                    f.write(os.path.basename(image_path))   # 只存文件名（跨平台）
            except Exception as e:
                logger.debug("头像持久化失败: %s", e)
            logger.info("数字人形象更新: %s (%dx%d)", image_path, img.shape[1], img.shape[0])
            return True
    return False


# ================================================================
# 占位模式
# ================================================================
def use_placeholder(self) -> None:
    """启用占位模式: 基于音频时长生成静态帧序列。

    参数:
        self: DigitalHumanEngine 实例
    """
    self._model_type = "placeholder"
    self._loaded = True
    logger.info("使用占位模式: 静态帧+音频输出(数字人形象保留)")


def generate_placeholder_frames(self, audio: np.ndarray) -> list:
    """占位模式: 基于音频时长生成静态帧序列。

    保留数字人形象（头像），音频正常输出。

    参数:
        self: DigitalHumanEngine 实例
        audio: float32 音频数组，16kHz
    返回: BGR 视频帧列表
    """
    duration_s = len(audio) / 16000
    n_frames = max(int(duration_s * self.fps), 1)          # 根据音频时长计算帧数

    # 获取头像帧（兜底加载）
    if self._avatar_frame is None:
        self._get_source_image()                            # 尝试从磁盘恢复

    if self._avatar_frame is not None:
        base = cv2.resize(self._avatar_frame, (self.width, self.height))
    else:
        # 最终兜底: 深色背景 + 提示文字
        base = np.ones((self.height, self.width, 3), dtype=np.uint8) * 30
        cv2.putText(base, "请上传人物照片",
                    (self.width // 2 - 160, self.height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
        logger.warning("占位模式无头像，显示提示文字")

    frames = [base.copy() for _ in range(n_frames)]
    logger.debug("占位帧: %d帧, %.1fs", n_frames, duration_s)
    return frames


# ================================================================
# 音视频合成（static 方法 — 不需要 self）
# ================================================================
def composite_audio_video(frames: list, audio: np.ndarray,
                          output_path: str, fps: int = 25) -> bool:
    """将视频帧和音频合成为 MP4 文件（FFmpeg）。

    参数:
        frames: BGR 视频帧列表
        audio: float32 音频数组，16kHz 单声道
        output_path: 输出 MP4 文件路径
        fps: 帧率，默认 25
    返回: True=合成成功
    """
    if not frames:
        return False

    vtmp = output_path + ".yuv"     # 视频原始数据临时文件
    atmp = output_path + ".pcm"     # 音频原始数据临时文件
    try:
        # *** 唇形同步深度修复 ***
        # 旧代码以帧数为基准裁剪音频, 会导致帧多时填充静音→嘴唇动但无声
        # 新策略: 以音频为基准(音频是"真值"), 调整帧数匹配音频长度
        audio_duration_sec = len(audio) / 16000.0
        expected_frames = int(audio_duration_sec * fps)
        frame_diff = len(frames) - expected_frames
        if frame_diff > 0:
            logger.info("唇形同步: 裁剪%d帧 -> %d帧", frame_diff, expected_frames)
            frames = frames[:expected_frames]
        elif frame_diff < 0:
            last = frames[-1].copy() if frames else np.ones((512, 512, 3), dtype=np.uint8) * 30
            for _ in range(-frame_diff):
                frames.append(last.copy())
            logger.info("唇形同步: 补%d帧 -> %d帧", -frame_diff, len(frames))
        # 最终精度对齐 (<10ms 忽略)
        expected_samples = int(len(frames) * 16000 / fps)
        if len(audio) > expected_samples + 160:
            audio = audio[:expected_samples]
        elif len(audio) < expected_samples - 160:
            audio = np.pad(audio, (0, expected_samples - len(audio)), mode='constant')

        h, w = frames[0].shape[:2]
        # 写入视频原始帧（BGR 格式）
        with open(vtmp, "wb") as f:
            for frame in frames:
                if frame.shape[:2] != (h, w):
                    frame = cv2.resize(frame, (w, h))
                f.write(frame.tobytes())

        # 写入音频 PCM（int16）
        audio_s16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        with open(atmp, "wb") as f:
            f.write(audio_s16.tobytes())

        # FFmpeg 合成
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "bgr24",
            "-video_size", f"{w}x{h}",
            "-framerate", str(fps), "-i", vtmp,
            "-f", "s16le", "-ar", "16000", "-ac", "1", "-i", atmp,
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",              # 最大兼容性
            "-movflags", "+faststart",           # 网页渐进加载
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", output_path,
        ], check=True)
        logger.info("音视频合成: %s", output_path)
        return True
    except Exception as e:
        logger.error("音视频合成失败: %s", e)
        return False
    finally:
        # 清理临时原始数据文件
        for tmp in [vtmp, atmp]:
            if os.path.exists(tmp):
                os.remove(tmp)


# ================================================================
# 全局单例 — 延迟初始化
# ================================================================
_dh_instance: Optional['DigitalHumanEngine'] = None


def get_digital_human(config=None):
    """获取全局数字人引擎单例。

    参数:
        config: 配置模块（可选，用于读取 AVATAR_PATH 等）
    返回:
        DigitalHumanEngine 实例
    """
    global _dh_instance
    if _dh_instance is None:
        # 延迟导入避免循环依赖
        from digital_human import DigitalHumanEngine
        avatar = getattr(config, 'AVATAR_PATH', None) if config else None
        _dh_instance = DigitalHumanEngine(avatar_path=avatar)
    return _dh_instance


# ================================================================
# 异步视频生成（供外部使用）
# ================================================================
async def generate_video_async(engine, audio: np.ndarray, text: str = "") -> list:
    """异步视频生成（在线程池中执行 GPU 推理，不阻塞事件循环）。

    参数:
        engine: DigitalHumanEngine 实例
        audio: float32 音频数组
        text: 回复文本
    返回: BGR 视频帧列表
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _infer_executor, engine.generate_video, audio, text
    )

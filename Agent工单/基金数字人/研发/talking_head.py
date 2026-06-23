# -*- coding: utf-8 -*-
"""
talking_head.py — 语音驱动的数字人说话头像生成
功能：输入人脸照片 + 语音 → 输出说话视频（嘴唇与语音同步）
支持引擎：SadTalker / Wav2Lip / Simple(ffmpeg动画)

工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import os
import sys
import time
import subprocess
import tempfile
import shutil
import traceback
from pathlib import Path
from typing import Optional
from logger import logger  # 统一日志

# ============================================================
# 项目路径
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SADTALKER_DIR = os.path.join(PROJECT_ROOT, "SadTalker_models")  # ModelScope 下载的 SadTalker


def _convert_to_h264(input_path: str, output_path: str) -> bool:
    """将视频转为浏览器兼容的 H.264 编码"""
    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ], capture_output=True, text=True, timeout=120)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.warning(f"ffmpeg 转换失败: {e}")
        return False

# ============================================================
# SadTalker 引擎（输入：照片+音频 → 输出：说话视频）
# ============================================================

class SadTalkerEngine:
    """
    SadTalker — 音频驱动的说话头像生成

    输入：1张人脸照片 + 1段音频
    输出：人脸说话的视频（嘴唇动作与语音同步）

    论文: SadTalker: Learning Realistic 3D Motion Coefficients for Stylized Audio-Driven Single Image Talking Face Animation
    模型来源: ModelScope (wwd123/SadTalker)
    """

    def __init__(
        self,
        checkpoint_dir: str = None,
        device: str = "cuda",
        pose_style: int = 0,      # 头部姿态风格 0-45
        face_model_size: int = 256,  # 人脸分辨率 256/512
        preprocess: str = "crop",  # 预处理: crop/full/resize
        still_mode: bool = False,  # 减少头部运动
        use_enhancer: bool = False,  # 是否使用 GFPGAN 面部增强
        batch_size: int = 1,
        exp_scale: float = 1.0,
    ):
        self.device = device
        self.pose_style = pose_style
        self.face_model_size = face_model_size
        self.preprocess = preprocess
        self.still_mode = still_mode
        self.use_enhancer = use_enhancer
        self.batch_size = batch_size
        self.exp_scale = exp_scale
        self._model = None

        # 检查点和配置目录
        if checkpoint_dir is None:
            checkpoint_dir = SADTALKER_DIR
        self.root_dir = checkpoint_dir

    def is_available(self) -> bool:
        """检查 SadTalker 是否已下载"""
        # 检查主代码文件
        gradio_path = os.path.join(self.root_dir, "src", "gradio_demo.py")
        # 检查模型权重
        ckpt_256 = os.path.join(self.root_dir, "checkpoints", "SadTalker_V0.0.2_256.safetensors")
        mapping_00109 = os.path.join(self.root_dir, "checkpoints", "mapping_00109-model.pth.tar")
        return os.path.exists(gradio_path) and (
            os.path.exists(ckpt_256) or os.path.exists(mapping_00109)
        )

    def _get_model(self):
        """延迟加载 SadTalker 模型"""
        if self._model is not None:
            return self._model

        if not self.is_available():
            raise RuntimeError(
                "SadTalker 模型未下载。请运行: python download_sadtalker_models.py\n"
                "或使用 ModelScope: from modelscope.hub import snapshot_download\n"
                "    snapshot_download('wwd123/SadTalker', local_dir='SadTalker_models')"
            )

        # 将 SadTalker 源码加入 Python 路径
        if self.root_dir not in sys.path:
            sys.path.insert(0, self.root_dir)

        logger.info("加载 SadTalker 模型...")

        try:
            from src.gradio_demo import SadTalker

            checkpoint_path = os.path.join(self.root_dir, "checkpoints")
            config_path = os.path.join(self.root_dir, "src", "config")

            self._model = SadTalker(
                checkpoint_path=checkpoint_path,
                config_path=config_path,
            )
            logger.info("SadTalker 模型加载完成")
        except Exception as e:
            raise RuntimeError(f"SadTalker 模型加载失败: {e}")

        return self._model

    def generate(
        self,
        source_image: str,     # 人脸照片路径
        audio_path: str,        # 音频文件路径（wav/mp3）
        output_path: str = None,  # 输出视频路径（可选）
        enhancer: str = None,   # 面部增强: gfpgan
        **kwargs
    ) -> Optional[str]:
        """
        生成数字人说话视频

        Args:
            source_image: 人脸照片（正面照效果最好，支持真人/动漫）
            audio_path: 驱动语音文件
            output_path: 输出视频路径（.mp4）或输出目录
            enhancer: 面部增强器 (gfpgan)

        Returns:
            str: 输出视频路径，失败返回 None
        """
        if not self.is_available():
            raise RuntimeError(
                "SadTalker 未安装。请从 ModelScope 下载:\n"
                "python -c \"from modelscope.hub import snapshot_download; "
                "snapshot_download('wwd123/SadTalker', local_dir='SadTalker_models')\""
            )

        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4")

        # 转换为绝对路径（SadTalker 内部需要绝对路径）
        source_image = os.path.abspath(source_image)
        audio_path = os.path.abspath(audio_path)
        output_path = os.path.abspath(output_path)

        # 检查输入文件
        if not os.path.exists(source_image):
            raise FileNotFoundError(f"人脸照片不存在: {source_image}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        # OpenCV 在 Windows 上读不了中文路径，把头像复制到临时英文路径
        safe_image = source_image
        if any('一' <= c <= '鿿' for c in source_image):
            safe_dir = os.path.join(tempfile.gettempdir(), "sadtalker_input")
            os.makedirs(safe_dir, exist_ok=True)
            safe_image = os.path.join(safe_dir, "avatar" + os.path.splitext(source_image)[1])
            shutil.copy2(source_image, safe_image)
            logger.debug(f"中文路径已转义: {safe_image}")

        # 同样处理音频
        safe_audio = audio_path
        if any('一' <= c <= '鿿' for c in audio_path):
            safe_dir = os.path.join(tempfile.gettempdir(), "sadtalker_input")
            os.makedirs(safe_dir, exist_ok=True)
            safe_audio = os.path.join(safe_dir, "audio" + os.path.splitext(audio_path)[1])
            shutil.copy2(audio_path, safe_audio)

        final_dir = os.path.dirname(output_path)
        os.makedirs(final_dir, exist_ok=True)

        # SadTalker 内部也使用中文路径，OpenCV 读不了
        # 用临时英文目录，完成后复制回来
        result_dir = os.path.join(tempfile.gettempdir(), "sadtalker_output")
        os.makedirs(result_dir, exist_ok=True)

        logger.info("SadTalker 生成数字人视频...")
        logger.debug(f"照片: {os.path.basename(source_image)}, 音频: {os.path.basename(audio_path)}")

        try:
            t0 = time.time()

            # 加载模型
            model = self._get_model()

            # 调用 SadTalker.test() 生成视频（使用英文临时路径）
            logger.debug(f"工作目录: {result_dir}")
            video_path = model.test(
                safe_image,
                driven_audio=safe_audio,
                preprocess=self.preprocess,
                still_mode=self.still_mode,
                use_enhancer=self.use_enhancer or (enhancer == "gfpgan"),
                batch_size=self.batch_size,
                size=self.face_model_size,
                pose_style=self.pose_style,
                exp_scale=self.exp_scale,
                result_dir=result_dir,
            )

            elapsed = time.time() - t0

            if video_path and os.path.exists(video_path):
                # SadTalker 直接返回了视频路径
                if video_path != output_path:
                    converted = _convert_to_h264(video_path, output_path)
                    if not converted:
                        shutil.copy2(video_path, output_path)
                logger.info(f"数字人视频生成完成 ({elapsed:.1f}s)")
                logger.debug(f"输出: {output_path}")
                return output_path

            # SadTalker 把结果放在 result_dir/timestamp/ 子目录里
            # 递归查找 mp4 并复制到 output
            found_videos = []
            for root, dirs, files in os.walk(result_dir):
                for f in files:
                    if f.endswith('.mp4'):
                        found_videos.append(os.path.join(root, f))

            if found_videos:
                # 用最新的视频
                found_videos.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                best = found_videos[0]
                # SadTalker 输出 MP4V 编码，浏览器不兼容，转 H.264
                converted = _convert_to_h264(best, output_path)
                if converted:
                    logger.info(f"数字人视频生成完成 ({elapsed:.1f}s)")
                    logger.debug(f"输出: {output_path}")
                    return output_path
                else:
                    logger.warning("H.264 转换失败，使用原始视频")
                    shutil.copy2(best, output_path)
                    return output_path

            logger.warning("SadTalker 未生成视频文件")
            return None

        except Exception as e:
            logger.error(f"SadTalker 生成失败: {e}")
            logger.error(traceback.format_exc())
            return None


# ============================================================
# Simple 引擎（ffmpeg 合成图片+音频为视频 — 备选方案）
# ============================================================

class SimpleTalkingHead:
    """
    简易数字人 — 人脸图片 + TTS 音频合成视频

    使用 ffmpeg 将静态图片和音频合成为带音频的 mp4 视频。
    虽然嘴唇不会动，但可以立即跑通，支持完整的前后端流程调试。

    适合：
    - 快速验证前后端流程
    - SadTalker 模型下载前的备选方案
    - 低配置环境
    """

    def __init__(self, add_subtitles: bool = True):
        """
        Args:
            add_subtitles: 是否在视频中叠加字幕
        """
        self.add_subtitles = add_subtitles

    def generate(
        self,
        source_image: str,      # 人脸照片
        audio_path: str,         # 语音文件
        output_path: str = None,  # 输出视频路径
        subtitle_text: str = None,  # 字幕文本
    ) -> str:
        """
        生成带音频的静态数字人视频

        Args:
            source_image: 图片路径
            audio_path: 音频路径
            output_path: 输出视频路径
            subtitle_text: 要在视频中显示的字幕

        Returns:
            str: 视频文件路径
        """
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp4")

        if not os.path.exists(source_image):
            raise FileNotFoundError(f"图片不存在: {source_image}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频不存在: {audio_path}")

        logger.info("生成数字人视频 (simple模式) ...")

        # 获取音频时长
        duration = self._get_audio_duration(audio_path)
        if duration is None:
            duration = 10  # 默认10秒

        # 构建 ffmpeg 滤镜
        # 缩放图片到 720p，居中裁剪
        scale_filter = (
            f"scale=720:1280:force_original_aspect_ratio=decrease,"
            f"pad=720:1280:(ow-iw)/2:(oh-ih)/2:black"
        )

        # 字幕滤镜
        vf = scale_filter
        if self.add_subtitles and subtitle_text:
            # 转义特殊字符
            escaped_text = subtitle_text.replace("\\", "\\\\").replace(":", "\\:")
            escaped_text = escaped_text.replace("'", "\\'").replace("\n", "\\n")
            # 字幕在底部居中，带半透明背景
            subtitle_filter = (
                f"drawtext=text='{escaped_text}':"
                f"fontsize=28:fontcolor=white:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
                f"x=(w-text_w)/2:y=h-th-60:"
                f"box=1:boxcolor=black@0.5:boxborderw=10:"
                f"enable='between(t,0,{duration})'"
            )
            vf = f"{scale_filter},{subtitle_filter}"

        cmd = [
            "ffmpeg",
            "-loop", "1",           # 循环图片
            "-i", source_image,     # 图片输入
            "-i", audio_path,       # 音频输入
            "-vf", vf,              # 视频滤镜
            "-c:v", "libx264",      # H.264 编码
            "-c:a", "aac",          # AAC 音频
            "-b:a", "128k",         # 音频码率
            "-t", str(duration),    # 时长
            "-pix_fmt", "yuv420p",  # 兼容格式
            "-shortest",            # 取最短输入
            "-y",                   # 覆盖输出
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                # 尝试不使用字幕滤镜
                logger.warning("字幕滤镜失败，重试无字幕版本...")
                cmd_basic = [
                    "ffmpeg",
                    "-loop", "1",
                    "-i", source_image,
                    "-i", audio_path,
                    "-vf", scale_filter,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-shortest", "-y",
                    output_path,
                ]
                result = subprocess.run(cmd_basic, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.error(f"ffmpeg 失败: {result.stderr[:300]}")
                return None

            logger.info(f"视频生成完成: {output_path}")
            return output_path

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg 超时")
            return None
        except FileNotFoundError:
            logger.error("ffmpeg 未安装。请运行: sudo apt install ffmpeg")
            return None

    @staticmethod
    def _get_audio_duration(audio_path: str) -> Optional[float]:
        """获取音频文件时长（秒）"""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            return None


# ============================================================
# 工厂函数
# ============================================================

def get_talking_head(engine_type: str = "sadtalker", **kwargs):
    """
    获取数字人引擎

    Args:
        engine_type: "sadtalker" / "simple" / "wav2lip"
        **kwargs: 引擎参数

    Returns:
        SadTalkerEngine / SimpleTalkingHead
    """
    if engine_type == "sadtalker":
        eng = SadTalkerEngine(**kwargs)
        if eng.is_available():
            return eng
        else:
            logger.warning("SadTalker 模型未就绪，回退到 simple 模式")
            return SimpleTalkingHead()
    elif engine_type == "simple":
        return SimpleTalkingHead(**kwargs)
    else:
        raise ValueError(f"不支持的引擎: {engine_type}。可选: sadtalker, simple")


def generate_digital_human_video(
    source_image: str,
    audio_path: str,
    output_path: str = None,
    engine: str = "sadtalker",
    fallback: bool = True,
    subtitle: str = None,
    **kwargs,
) -> Optional[str]:
    """
    便捷函数：输入图片+音频 → 输出数字人视频

    Args:
        source_image: 人脸照片（真人/动漫均可）
        audio_path: 语音文件
        output_path: 输出视频路径
        engine: 引擎类型 ("sadtalker" 优先)
        fallback: SadTalker 不可用时回退到 simple
        subtitle: 字幕文本（仅 simple 模式使用）

    Returns:
        str: 视频文件路径
    """
    # 优先使用 SadTalker
    if engine == "sadtalker":
        talker = SadTalkerEngine(**kwargs)
        if talker.is_available():
            try:
                result = talker.generate(source_image, audio_path, output_path)
                if result:
                    return result
            except Exception as e:
                logger.error(f"SadTalker 失败: {e}")
                if not fallback:
                    return None

        if fallback:
            logger.warning("SadTalker 不可用，回退到 simple 模式")
            simple = SimpleTalkingHead()
            return simple.generate(source_image, audio_path, output_path, subtitle)

    elif engine == "simple":
        simple = SimpleTalkingHead(**kwargs)
        return simple.generate(source_image, audio_path, output_path, subtitle)

    return None


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("数字人引擎测试")
    logger.info("=" * 50)

    # 检查 SadTalker 是否可用
    # 注意：首次加载模型可能需要几秒到几十秒
    talker = SadTalkerEngine()
    if talker.is_available():
        logger.info("SadTalker 模码和代码就绪")
        logger.info(f"路径: {SADTALKER_DIR}")
        # 尝试加载模型
        try:
            model = talker._get_model()
            logger.info("SadTalker 模型加载成功！")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}")
    else:
        logger.warning("SadTalker 未下载")
        logger.info("请运行: python download_sadtalker_models.py")
        logger.info("或从 ModelScope 下载: snapshot_download('wwd123/SadTalker')")

    logger.info("Simple 引擎始终可用（需要 ffmpeg）")

# -*- coding: utf-8 -*-
"""
digital_human.py — 数字人播报流水线编排器
功能：将 NL2SQL 答案 → TTS 语音 → 数字人说话视频 串成完整流水线

流水线：
  文字答案 ──[TTS]──→ 音频 ──[Talking Head]──→ 数字人视频
  用户语音 ──[ASR]──→ 问题文本 ──[NL2SQL]──→ 答案 ──→ ...

工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Callable

# 添加研发目录到 Python 路径
_研发_DIR = os.path.dirname(os.path.abspath(__file__))
if _研发_DIR not in sys.path:
    sys.path.insert(0, _研发_DIR)

from logger import logger  # 统一日志
from tts_engine import get_tts_engine, text_to_speech
from talking_head import get_talking_head, generate_digital_human_video

# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = os.path.dirname(_研发_DIR)

# 默认数字人形象照片
# 优先使用项目中的 avatar.jpg，否则使用占位图片
DEFAULT_AVATAR = os.path.join(PROJECT_ROOT, "avatar.jpg")

# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 数字人播报流水线
# ============================================================

class DigitalHumanPipeline:
    """
    数字人播报流水线

    流程: 文本答案 → TTS 语音 → 数字人说话视频

    使用示例:
        pipeline = DigitalHumanPipeline(avatar_image="avatar.jpg")
        video_path = pipeline.broadcast("您的基金查询结果是...")
    """

    def __init__(
        self,
        avatar_image: str = None,
        tts_engine: str = "edge",       # TTS: edge / paddle
        tts_voice: str = "zh-CN-XiaoyiNeural",  # 发音人
        talking_head_engine: str = "sadtalker",  # 数字人: sadtalker / simple
        output_dir: str = None,
        enable_asr: bool = False,        # 是否启用语音输入
        asr_engine: str = "funasr",
    ):
        """
        Args:
            avatar_image: 数字人形象照片路径
            tts_engine: TTS 引擎类型
            tts_voice: Edge-TTS 发音人
            talking_head_engine: 数字人引擎
            output_dir: 输出目录
            enable_asr: 是否启用语音识别
            asr_engine: ASR 引擎类型
        """
        self.avatar_image = avatar_image or DEFAULT_AVATAR
        self.tts_engine_type = tts_engine
        self.tts_voice = tts_voice
        self.talking_head_type = talking_head_engine
        self.enable_asr = enable_asr
        self.asr_engine_type = asr_engine

        if output_dir is None:
            output_dir = OUTPUT_DIR
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        # 初始化 TTS 引擎
        self.tts = get_tts_engine(tts_engine, voice=tts_voice)

        # 初始化数字人引擎（延迟加载）
        self._talking_head = None
        self._asr = None

        # 进度回调
        self._progress_callback: Optional[Callable] = None

    @property
    def talking_head(self):
        if self._talking_head is None:
            self._talking_head = get_talking_head(self.talking_head_type)
        return self._talking_head

    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数 callback(step, message, percent)"""
        self._progress_callback = callback

    def _report_progress(self, step: str, message: str, percent: int):
        if self._progress_callback:
            self._progress_callback(step, message, percent)
        else:
            logger.info(f"[{percent}%] {step}: {message}")

    def broadcast(
        self,
        answer_text: str,
        output_name: str = None,
        return_video: bool = True,
        return_audio: bool = False,
    ) -> dict:
        """
        数字人播报：将文本转为数字人说话视频

        Args:
            answer_text: 要播报的答案文本
            output_name: 输出文件名（不含扩展名）
            return_video: 是否生成视频
            return_audio: 是否保留音频文件

        Returns:
            dict: {
                "video_path": "视频路径" or None,
                "audio_path": "音频路径" or None,
                "elapsed": 总耗时,
                "success": bool,
                "engine": "使用的引擎",
            }
        """
        t0 = time.time()

        if not output_name:
            output_name = f"broadcast_{int(time.time()*1000)}"

        audio_path = None
        video_path = None

        # ===== 步骤1: TTS 文本转语音 =====
        self._report_progress("tts", "正在生成语音...", 10)

        try:
            audio_path = os.path.join(self.output_dir, f"{output_name}.mp3")
            self.tts.synthesize(answer_text, audio_path)

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                raise RuntimeError("TTS 输出文件为空")

            tts_elapsed = time.time() - t0
            self._report_progress("tts", f"语音生成完成 ({tts_elapsed:.1f}s)", 30)

        except Exception as e:
            self._report_progress("error", f"TTS 失败: {e}", 0)
            return {
                "video_path": None,
                "audio_path": None,
                "elapsed": time.time() - t0,
                "success": False,
                "error": f"TTS 合成失败: {str(e)}",
            }

        # ===== 步骤2: 生成数字人说话视频 =====
        if return_video:
            self._report_progress("video", "正在生成数字人视频...", 40)

            # 检查头像图片
            if not os.path.exists(self.avatar_image):
                logger.warning(f"头像图片不存在: {self.avatar_image}")
                self._report_progress(
                    "video", "头像图片未设置，将使用音频替代", 50
                )
            else:
                try:
                    video_output = os.path.join(
                        self.output_dir, f"{output_name}.mp4"
                    )

                    # 使用 fallback: SadTalker 不可用时自动用 simple 模式
                    engine_to_use = self.talking_head_type
                    fallback_enabled = True

                    # 如果 avatar 是默认路径且不存在，直接用 simple
                    if (self.avatar_image == DEFAULT_AVATAR
                            and not os.path.exists(DEFAULT_AVATAR)):
                        engine_to_use = "simple"
                        logger.info("使用 simple 模式（无自定义头像）")

                    video_path = generate_digital_human_video(
                        source_image=self.avatar_image,
                        audio_path=audio_path,
                        output_path=video_output,
                        engine=engine_to_use,
                        fallback=fallback_enabled,
                        subtitle=answer_text[:100],  # 前100字字幕
                    )

                    if video_path:
                        vid_elapsed = time.time() - t0
                        self._report_progress(
                            "video", f"数字人视频生成完成 ({vid_elapsed:.1f}s)", 80
                        )
                    else:
                        self._report_progress(
                            "video", "视频生成失败，仅返回音频", 60
                        )

                except Exception as e:
                    logger.error(f"视频生成异常: {e}")
                    self._report_progress("video", f"视频生成跳过: {e}", 60)

        # ===== 完成 =====
        total_elapsed = time.time() - t0
        self._report_progress("done", f"播报完成 ({total_elapsed:.1f}s)", 100)

        result = {
            "video_path": video_path,
            "audio_path": audio_path,
            "elapsed": round(total_elapsed, 2),
            "success": True if audio_path else False,
            "engine": self.talking_head_type,
        }

        # 清理不需要的音频（如果只需要视频）
        if not return_audio and video_path and audio_path:
            # 保留音频（用于调试），不删除
            pass

        return result

    def ask_with_voice(self, audio_input: str) -> str:
        """
        语音提问 → 文本识别

        Args:
            audio_input: 语音文件路径

        Returns:
            str: 识别的文本问题
        """
        if not self.enable_asr:
            raise RuntimeError("ASR 未启用。设置 enable_asr=True")

        if self._asr is None:
            from asr_engine import get_asr_engine
            self._asr = get_asr_engine(self.asr_engine_type)

        result = self._asr.transcribe(audio_input)
        return result.get("text", "")


# ============================================================
# 与现有 NL2SQL 系统的集成桥接
# ============================================================

def create_pipeline(
    avatar_image: str = None,
    voice: str = "zh-CN-XiaoyiNeural",
    engine: str = "sadtalker",
    output_dir: str = None,
) -> DigitalHumanPipeline:
    """
    创建数字人流水线实例（便捷工厂函数）

    Args:
        avatar_image: 数字人形象照片
        voice: Edge-TTS 发音人
        engine: 数字人引擎
        output_dir: 输出目录

    Returns:
        DigitalHumanPipeline 实例
    """
    return DigitalHumanPipeline(
        avatar_image=avatar_image,
        tts_voice=voice,
        talking_head_engine=engine,
        output_dir=output_dir,
    )


def broadcast_answer(
    answer_text: str,
    avatar_image: str = None,
    voice: str = "zh-CN-XiaoyiNeural",
    output_dir: str = None,
) -> dict:
    """
    快捷函数：将 NL2SQL 答案用数字人播报

    这是与 main.py 的主要集成点。在 process_question 返回答案后调用此函数。

    Args:
        answer_text: NL2SQL 生成的答案文本
        avatar_image: 数字人头像
        voice: TTS 发音人
        output_dir: 输出目录

    Returns:
        dict: {"video_path": ..., "audio_path": ..., "elapsed": ...}
    """
    pipeline = create_pipeline(
        avatar_image=avatar_image,
        voice=voice,
        engine="sadtalker",  # 优先用 SadTalker，不可用时回退 simple
        output_dir=output_dir,
    )

    # 截断过长的答案（视频太长不实用）
    max_chars = 800
    if len(answer_text) > max_chars:
        answer_text = answer_text[:max_chars] + "，以上为主要信息。"

    return pipeline.broadcast(
        answer_text,
        return_video=True,
        return_audio=True,
    )


# ============================================================
# 管理接口：设置头像、切换声音
# ============================================================

class DigitalHumanManager:
    """数字人配置管理器"""

    def __init__(self):
        self.config_file = os.path.join(PROJECT_ROOT, "digital_human_config.json")
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "avatar_image": "",
            "voice": "zh-CN-XiaoyiNeural",
            "engine": "sadtalker",
            "tts_rate": "+5%",
        }

    def _save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def set_avatar(self, image_path: str) -> bool:
        """设置数字人头像"""
        if not os.path.exists(image_path):
            return False

        # 复制到项目目录
        target = os.path.join(PROJECT_ROOT, "avatar.jpg")
        shutil.copy(image_path, target)
        self.config["avatar_image"] = target
        self._save_config()
        return True

    def set_voice(self, voice_id: str) -> bool:
        """设置 TTS 发音人"""
        valid_voices = [
            "zh-CN-XiaoyiNeural",
            "zh-CN-XiaoyiNeural",
            "zh-CN-YunjianNeural",
            "zh-CN-XiaoyiNeural",
            "zh-CN-YunyangNeural",
        ]
        if voice_id in valid_voices:
            self.config["voice"] = voice_id
            self._save_config()
            return True
        return False

    def get_avatar(self) -> str:
        return self.config.get("avatar_image", "")

    def get_voice(self) -> str:
        return self.config.get("voice", "zh-CN-XiaoyiNeural")

    def get_pipeline(self) -> DigitalHumanPipeline:
        """根据配置创建数字人流水线"""
        avatar = self.get_avatar()
        if not avatar or not os.path.exists(avatar):
            avatar = DEFAULT_AVATAR

        return DigitalHumanPipeline(
            avatar_image=avatar,
            tts_voice=self.get_voice(),
            talking_head_engine=self.config.get("engine", "sadtalker"),
        )


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("数字人播报流水线测试")
    logger.info("=" * 55)

    # 测试 TTS → 数字人视频
    test_answer = """根据查询结果，景顺长城中短债债券C基金在2021年3月31日的前三大持仓债券分别是：
第一，20国开12，持仓市值约2.5亿元；
第二，21国债01，持仓市值约1.8亿元；
第三，20农发05，持仓市值约1.2亿元。以上数据仅供参考。"""

    logger.info(f"测试答案文本: {test_answer[:80]}...")
    logger.info(f"Avatar 图片: {DEFAULT_AVATAR}")

    if os.path.exists(DEFAULT_AVATAR):
        logger.info("Avatar 图片已就绪")
    else:
        logger.warning("未设置 Avatar 图片（将使用 simple 模式生成静态视频）")

    pipeline = create_pipeline(
        avatar_image=DEFAULT_AVATAR if os.path.exists(DEFAULT_AVATAR) else None,
        voice="zh-CN-XiaoyiNeural",
        engine="sadtalker",
    )

    pipeline.set_progress_callback(
        lambda step, msg, pct: logger.info(f"[{pct:3d}%] {step}: {msg}")
    )

    logger.info("开始播报...")
    result = pipeline.broadcast(test_answer, output_name="test_broadcast")

    logger.info(f"结果: 成功={result['success']}, 视频={result.get('video_path', 'N/A')}, 音频={result.get('audio_path', 'N/A')}, 耗时={result['elapsed']}s")
    if result.get('error'):
        logger.error(f"错误: {result['error']}")

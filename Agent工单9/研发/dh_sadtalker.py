# -*- coding: utf-8 -*-
"""
dh_sadtalker.py — SadTalker 数字人推理模块
--------------------------------------------------------------
功能: SadTalker 模型加载、唇形同步推理、帧提取。
      包含: Croper 宽裁切补丁（避免"大头"效果）、占位→SadTalker恢复。

所有函数以 `self` (DigitalHumanEngine 实例) 为第一个参数。
通过 digital_human.py 的 class-level 绑定成为方法。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, sys, tempfile, logging  # 标准库
import numpy as np                 # 数值计算
import cv2                         # 图像处理
import torch                       # PyTorch (GPU推理)

logger = logging.getLogger("digital_human")

# SadTalker 源码路径（从 digital_human 模块导入）
try:
    import digital_human as _dh
    SADTALKER_SRC = _dh.SADTALKER_SRC
    SADTALKER_ROOT = _dh.SADTALKER_ROOT
    SADTALKER_CHECKPOINTS = _dh.SADTALKER_CHECKPOINTS
except Exception:
    SADTALKER_ROOT = os.path.expanduser("~/SadTalker_modelscope")
    SADTALKER_SRC = os.path.join(SADTALKER_ROOT, "src")
    SADTALKER_CHECKPOINTS = os.path.join(SADTALKER_ROOT, "checkpoints")


# ================================================================
# SadTalker 模型加载
# ================================================================
def load_sadtalker(self) -> None:
    """加载 SadTalker 模型（GPU 推理，lazy_load 延迟加载子模型）。

    参数:
        self: DigitalHumanEngine 实例
    """
    logger.info("=" * 50)
    logger.info("  加载 SadTalker 数字人模型")
    logger.info("  Checkpoint: %s", self.sadtalker_checkpoint)
    logger.info("  Config: %s", self.sadtalker_config)
    logger.info("  Device: %s", self.device)
    logger.info("=" * 50)

    # 将 SadTalker 源码加入 Python 路径
    if SADTALKER_ROOT not in sys.path:
        sys.path.insert(0, SADTALKER_ROOT)
    if SADTALKER_SRC not in sys.path:
        sys.path.insert(0, SADTALKER_SRC)

    from src.gradio_demo import SadTalker

    self._model = SadTalker(
        checkpoint_path=self.sadtalker_checkpoint,
        config_path=self.sadtalker_config,
        lazy_load=True,          # 延迟加载子模型到首次推理（节省显存）
    )
    self._model_type = "sadtalker"
    self._loaded = True
    self._patch_croper_for_wider_crop()  # 防大头补丁
    logger.info("✓ SadTalker模型加载完成 (lazy_load=True)")


# ================================================================
# Croper 宽裁切补丁 — 跳过第2层紧裁切，避免"大头"效果
# ================================================================
def patch_croper_for_wider_crop(self) -> None:
    """Monkey-patch SadTalker 的 Croper.crop 方法。

    原始: still=False 时在脸部裁切后再切一次内层 → 面部过度放大
    补丁: 强制 still=True 行为 → 保留更多背景和原始构图
    """
    try:
        from src.utils.croper import Preprocesser as _Croper
        _orig_crop = _Croper.crop

        def _wider_crop(croper_self, img_np_list, still=False, xsize=512):
            """强制 still=True: 跳过紧裁切人脸。"""
            return _orig_crop(croper_self, img_np_list, still=True, xsize=xsize)

        _Croper.crop = _wider_crop
        logger.info("Croper已补丁: 宽裁切模式（保留背景，不过度放大脸部）")
    except Exception as e:
        logger.debug("Croper补丁跳过: %s", e)


# ================================================================
# SadTalker 推理
# ================================================================
def generate_sadtalker(self, audio: np.ndarray, text: str = "") -> list:
    """使用 SadTalker Python API 生成唇形同步视频帧。

    参数:
        self: DigitalHumanEngine 实例
        audio: float32 音频数组，16kHz
        text: 回复文本（用于日志）
    返回: BGR 视频帧列表
    """
    source_img = self._get_source_image()          # 获取参考人脸
    audio_path = _save_audio_temp(audio)           # 保存临时音频
    img_path = _save_image_temp(source_img)        # 保存临时图片

    try:
        logger.info("SadTalker推理中... (img=%dx%d, audio=%.1fs)",
                     source_img.shape[1], source_img.shape[0], len(audio) / 16000)

        # 预处理策略: resize 优先（保持身份特征完整），crop 回退（更稳定但可能丢边缘）
        # 两种模式逐一尝试，任一成功即停止
        result = None
        for preprocess_mode in ['resize', 'crop']:
            try:
                with torch.no_grad():
                    result = self._model.test(
                        source_image=img_path,
                        driven_audio=audio_path,
                        preprocess=preprocess_mode,
                        still_mode=True,
                        use_enhancer=False,
                        batch_size=2,
                        size=256,
                        pose_style=0,
                    )
                if result is not None and (isinstance(result, list) and len(result) > 0):
                    logger.info("SadTalker: %s still=True size=384 ✓ (%d帧)", preprocess_mode, len(result))
                    break
                elif isinstance(result, str) and os.path.exists(result):
                    logger.info("SadTalker: %s → 视频文件 %s", preprocess_mode, result)
                    break
                else:
                    logger.warning("SadTalker %s 返回空结果: %s", preprocess_mode, type(result))
                    result = None
            except Exception as e:
                logger.error("SadTalker %s 异常: %s", preprocess_mode, str(e)[:300])
                import traceback
                logger.error(traceback.format_exc())
                continue

        if result is None:
            raise RuntimeError("SadTalker both modes failed")

        # 解析结果: 支持帧列表和视频路径两种格式
        if isinstance(result, list) and len(result) > 0:
            frames = [_ensure_bgr_uint8(f) for f in result]
            # *** 诊断日志: 检查帧数与音频时长的对齐 ***
            audio_dur = len(audio) / 16000.0
            expected_frames = int(audio_dur * 25)  # 25fps
            logger.info("SadTalker生成: %d帧, 音频%.2fs, 期望%d帧, 偏差%+d帧",
                       len(frames), audio_dur, expected_frames,
                       len(frames) - expected_frames)
            return frames
        if isinstance(result, str) and os.path.exists(result):
            return _extract_frames_from_video(result)

        logger.warning("SadTalker返回空，回退占位")
        return self._generate_placeholder_frames(audio)

    except Exception as e:
        logger.error("SadTalker推理失败(%s)，回退占位", e)
        return self._generate_placeholder_frames(audio)
    finally:
        # 清理临时文件
        for tmp in [audio_path, img_path]:
            if os.path.exists(tmp):
                try: os.remove(tmp)
                except Exception: pass


# ================================================================
# 占位→SadTalker 恢复
# ================================================================
def try_recover_sadtalker_impl(self) -> bool:
    """如果当前是占位模式，尝试重新加载 SadTalker。
    用于处理启动时 GPU 未释放导致的瞬时加载失败。

    参数:
        self: DigitalHumanEngine 实例
    返回: True=恢复成功
    """
    if self._model_type != "placeholder":
        return True                                     # 已经是正常模式
    logger.info("🔄 尝试从占位模式恢复 SadTalker...")
    self._cleanup_gpu()
    if self._sadtalker_available():
        try:
            self._load_sadtalker()
            logger.info("✅ SadTalker 恢复成功！")
            return True
        except Exception as e:
            logger.warning("SadTalker恢复失败: %s", str(e)[:80])
    return False


# ================================================================
# 帧/文件辅助函数（模块内私有）
# ================================================================
def _save_audio_temp(audio: np.ndarray) -> str:
    """将 float32 音频保存为临时 16kHz WAV 文件。返回路径。"""
    import wave
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(audio_int16.tobytes())
    return path


def _save_image_temp(img: np.ndarray) -> str:
    """将 numpy 图像保存为临时 PNG 文件。返回路径。"""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    cv2.imwrite(path, img)
    return path


def _ensure_bgr_uint8(frame: np.ndarray) -> np.ndarray:
    """确保帧为 BGR uint8 格式（SadTalker 输出 RGB → 转 BGR）。

    参数:
        frame: 输入帧（可能为 float/uint8, RGB/BGR）
    返回: BGR uint8 帧
    """
    if frame.dtype != np.uint8:
        if frame.max() <= 1.0:
            frame = (frame * 255).clip(0, 255)          # float→uint8
        frame = frame.astype(np.uint8)
    if frame.shape[-1] == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # RGB→BGR
    return frame


def _extract_frames_from_video(video_path: str) -> list:
    """从 MP4 视频文件提取帧列表。"""
    frames = []
    cap = cv2.VideoCapture(video_path)
    while True:
        ret, frame = cap.read()
        if not ret: break
        frames.append(frame)
    cap.release()
    logger.info("从视频提取: %d帧 (%s)", len(frames), video_path)
    return frames

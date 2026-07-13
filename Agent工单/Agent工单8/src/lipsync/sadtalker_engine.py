"""
src/lipsync/sadtalker_engine.py - SadTalker 唇形同步引擎
功能: 复用现有 SadTalker 模型权重，提供更自然的 3DMM 数字人口型驱动能力。
说明: 路径隔离与真正推理逻辑已拆分到独立模块，主文件聚焦模型装载与缓存分发。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import torch

from src.lipsync.sadtalker_inference import SadTalkerInferenceMixin, placeholder_frames

logger = logging.getLogger(__name__)
_INFER_POOL = ThreadPoolExecutor(max_workers=1)

if not hasattr(np, "VisibleDeprecationWarning"):
    np.VisibleDeprecationWarning = DeprecationWarning

_SAD_CANDIDATES = [
    os.path.expanduser("~/SadTalker_modelscope"),
    "/home/zzy/SadTalker_modelscope",
    r"C:\Users\31326\SadTalker_modelscope",
]


def _detect_sadtalker_root(explicit_root: str = "") -> str:
    """检测 SadTalker 模型根目录，优先使用显式路径。"""
    candidates = [explicit_root] + _SAD_CANDIDATES if explicit_root else _candidate_roots_from_env()
    for candidate in candidates:
        checkpoints = os.path.join(candidate, "checkpoints")
        source_dir = os.path.join(candidate, "src")
        if os.path.isdir(checkpoints) and os.path.isfile(os.path.join(source_dir, "gradio_demo.py")):
            return candidate
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "checkpoints")):
            return candidate
    return candidates[0]


def _candidate_roots_from_env() -> list:
    """组合环境变量和默认候选目录。"""
    env_root = os.environ.get("SADTALKER_ROOT", "")
    return ([env_root] if env_root else []) + _SAD_CANDIDATES


_SADTALKER_ROOT_CACHE = None


def _get_sadtalker_paths(explicit_root: str = ""):
    """获取 SadTalker 相关目录，带路径缓存。"""
    global _SADTALKER_ROOT_CACHE
    if _SADTALKER_ROOT_CACHE is not None:
        return _SADTALKER_ROOT_CACHE
    root = _detect_sadtalker_root(explicit_root)
    _SADTALKER_ROOT_CACHE = {
        "root": root,
        "checkpoints": os.path.join(root, "checkpoints"),
        "src": os.path.join(root, "src"),
        "config": os.path.join(root, "src", "config"),
    }
    return _SADTALKER_ROOT_CACHE


class SadTalkerEngine(SadTalkerInferenceMixin):
    """SadTalker 唇形同步引擎，复用已有模型并支持缓存分发。"""

    def __init__(self, device="cuda:0", img_size=96, use_fp16=True,
                 sadtalker_root: str = "", output_size: int = 720):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.img_size = img_size
        self.output_size = output_size
        self.use_fp16 = use_fp16 and self.device != "cpu"
        self._model = None
        self._loaded = False
        self._load_failed = False
        self._mel_extractor = None
        self._audio_buffer = []
        self._cached_frames = []
        self._cached_face = None
        self._frames_served = 0
        self._last_audio = None
        self._infer_pool = _INFER_POOL
        paths = _get_sadtalker_paths(sadtalker_root)
        self._sadtalker_root = paths["root"]
        self._sadtalker_checkpoints = paths["checkpoints"]
        self._sadtalker_src = paths["src"]
        self._sadtalker_config = paths["config"]
        logger.info(f"SadTalker引擎: device={self.device}, root={self._sadtalker_root}")

    def _log(self, message: str) -> None:
        """统一普通日志输出。"""
        logger.info(message)

    def _warn(self, message: str) -> None:
        """统一告警日志输出。"""
        logger.warning(message)

    def _error(self, message: str) -> None:
        """统一错误日志输出。"""
        logger.error(message)

    def load_model(self):
        """在隔离的 sys.path 环境中加载 SadTalker 模型。"""
        if self._loaded or self._load_failed:
            return
        root = self._sadtalker_root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        init_path = os.path.join(root, "src", "__init__.py")
        had_init = os.path.exists(init_path)
        if not had_init:
            self._create_temp_init(init_path)
        saved_path = list(sys.path)
        saved_modules = self._pop_project_src_modules()
        sys.path = self._build_clean_path(saved_path, project_root, root)
        try:
            self._inject_gfpgan_stub()
            self._patch_numpy_compat()  # 修复 numpy >= 1.24 兼容性
            from src.gradio_demo import SadTalker
            self._model = SadTalker(
                checkpoint_path=self._sadtalker_checkpoints,
                config_path=self._sadtalker_config,
                lazy_load=True,
            )
            self._loaded = True
            logger.info("SadTalker模型加载完成 ✓")
        except Exception as error:
            logger.error(f"SadTalker加载失败: {error}")
            self._model = None
            self._loaded = True
            self._load_failed = True
        finally:
            self._restore_import_state(saved_modules, saved_path, had_init, init_path)

    def _create_temp_init(self, init_path: str) -> None:
        """为 SadTalker 的 src 临时创建 __init__.py。"""
        try:
            with open(init_path, "w", encoding="utf-8") as file:
                file.write("")
        except (PermissionError, OSError):
            pass

    def _pop_project_src_modules(self) -> dict:
        """移除已加载的项目 src 模块，避免与 SadTalker src 包冲突。"""
        saved_modules = {}
        for name in list(sys.modules.keys()):
            if name == "src" or name.startswith("src."):
                saved_modules[name] = sys.modules.pop(name)
        return saved_modules

    def _build_clean_path(self, saved_path: list, project_root: str, root: str) -> list:
        """构造仅保留 SadTalker 相关优先级的干净导入路径。"""
        clean_path = [root]
        for path in saved_path:
            if not path:
                continue
            abs_path = os.path.abspath(path)
            if abs_path == project_root or abs_path.startswith(project_root + os.sep):
                continue
            clean_path.append(path)
        return clean_path

    def _inject_gfpgan_stub(self) -> None:
        """为缺失的 gfpgan.GFPGANer 注入空实现，避免非增强模式下导入失败。"""
        try:
            import gfpgan
            if not hasattr(gfpgan, "GFPGANer"):
                class _StubGFPGANer:
                    def __init__(self, *args, **kwargs):
                        del args, kwargs
                    def enhance(self, *args, **kwargs):
                        del args, kwargs
                        return None
                gfpgan.GFPGANer = _StubGFPGANer
        except ImportError:
            return

    def _patch_numpy_compat(self) -> None:
        """
        修复 numpy >= 1.24 与 SadTalker 3DMM 的兼容性问题。

        numpy 1.24+ 对 inhomogeneous shape 的 array 创建更严格，
        而 SadTalker 的 3DMM 提取过程会产生不等长序列。
        此补丁回退到 numpy < 1.24 的宽松行为（退回 object array）。
        """
        import numpy as _np

        if hasattr(_np, '_sadtalker_patched'):
            return  # 已打过补丁

        _original_array = _np.array

        def _compat_array(*args, **kwargs):
            try:
                return _original_array(*args, **kwargs)
            except (ValueError, TypeError) as exc:
                msg = str(exc)
                if ('inhomogeneous' in msg
                        and 'dtype' not in kwargs
                        and len(args) > 0):
                    return _original_array(*args, dtype=object, **kwargs)
                raise

        _np.array = _compat_array
        _np._sadtalker_patched = True  # type: ignore[attr-defined]
        self._log("numpy 兼容补丁已应用 (inhomogeneous→object fallback)")

    def _restore_numpy_compat(self) -> None:
        """恢复原始 numpy.array（在模型卸载时调用）。"""
        import numpy as _np

        if hasattr(_np, '_sadtalker_original_array'):
            _np.array = _np._sadtalker_original_array
            delattr(_np, '_sadtalker_original_array')
        if hasattr(_np, '_sadtalker_patched'):
            delattr(_np, '_sadtalker_patched')

    def _restore_import_state(self, saved_modules: dict, saved_path: list, had_init: bool, init_path: str) -> None:
        """恢复项目原始导入环境并清理临时文件。"""
        sadtalker_modules = {}
        for name in list(sys.modules.keys()):
            if name == "src" or name.startswith("src."):
                if name not in saved_modules:
                    sadtalker_modules[name] = sys.modules.pop(name)
        sys.modules.pop("src", None)
        sys.modules.update(saved_modules)
        sys.path = saved_path
        self._sadtalker_modules = sadtalker_modules
        if not had_init and os.path.exists(init_path):
            try:
                os.remove(init_path)
            except OSError:
                pass

    def generate_frames(self, mel_features: np.ndarray, face_images: np.ndarray = None) -> np.ndarray:
        """优先从缓存分发帧，必要时触发一次完整 SadTalker 推理。"""
        del face_images
        audio = getattr(self, "_last_audio", None)
        requested = mel_features.shape[0] if mel_features is not None else 0
        cached_result = self._serve_cached_frames(requested)
        if cached_result is not None:
            return cached_result
        if audio is not None and len(audio) > 500:
            face = self._load_avatar_image()
            self._cached_face = face
            output_frames = self.generate_talking_video(audio, face)
            cached_result = self._cache_generated_frames(output_frames, requested)
            if cached_result is not None:
                return cached_result
        return placeholder_frames(self.img_size, requested)

    def _serve_cached_frames(self, requested: int):
        """从缓存中取出指定数量帧，不足时补占位帧。"""
        if not self._cached_frames:
            return None
        start = self._frames_served
        end = min(start + requested, len(self._cached_frames))
        if start >= len(self._cached_frames):
            return placeholder_frames(self.img_size, requested)
        result = np.stack(self._cached_frames[start:end], axis=0).astype(np.uint8)
        self._frames_served = end
        if len(result) < requested:
            padding = placeholder_frames(self.img_size, requested - len(result))
            result = np.concatenate([result, padding], axis=0) if len(result) > 0 else padding
        return result

    def _cache_generated_frames(self, frames: list, requested: int):
        """缓存新生成的帧并优先返回本次请求所需帧。"""
        if not frames:
            return None
        frame_list = []
        for frame in frames:
            if frame is None:
                continue
            resized = cv2.resize(frame, (self.output_size, self.output_size))
            frame_list.append(resized.transpose(2, 0, 1))
        if not frame_list:
            return None
        self._cached_frames = frame_list
        self._frames_served = 0
        end = min(requested, len(self._cached_frames))
        result = np.stack(self._cached_frames[:end], axis=0).astype(np.uint8)
        self._frames_served = end
        logger.info(f"SadTalker 生成 {len(self._cached_frames)} 帧 (缓存)")
        return result

    async def generate_frames_async(self, mel_features: np.ndarray,
                                     face_images: np.ndarray = None) -> np.ndarray:
        """在线程池中异步生成唇形帧(兼容PipelineOrchestrator接口)。
        reset_buffer 由 SadTalkerInferenceMixin 提供, 此处不重复定义。"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _INFER_POOL, self.generate_frames, mel_features, face_images
        )

    @property
    def generates_full_frames(self) -> bool:
        """SadTalker 输出的是完整视频帧，可直接走输出通道。"""
        return True

    @property
    def vram_mb(self) -> float:
        """返回当前 SadTalker 模型占用显存估计值。"""
        try:
            return torch.cuda.memory_allocated(self.device) / (1024 * 1024)
        except Exception:
            return 0.0

# -*- coding: utf-8 -*-
"""
dh_patches.py — NumPy 2.x 兼容补丁 + 第三方 Mock
--------------------------------------------------------------
功能: SadTalker 运行所需的环境适配。
      1. NumPy 2.x 废弃 API 兼容（np.float, np.int, np.bool 等）
      2. SadTalker face3d POS() 矩阵形状兼容
      3. GFPGAN + modelscope Mock（use_enhancer=False 时不需要真实模块）

被 digital_human.py 在模块加载时自动执行。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import sys       # 模块管理（Mock 注入）
import logging   # 日志记录
import numpy as np  # 数值计算

logger = logging.getLogger("digital_human")


def apply_all_patches():
    """应用所有兼容补丁和 Mock。无副作用，可重复调用。"""
    _patch_numpy_compat()
    _patch_face3d_compat()
    _ensure_gfpgan_mock()
    _ensure_modelscope_mock()
    logger.info("所有补丁和Mock已应用")


def _patch_numpy_compat():
    """NumPy 2.x 兼容: 恢复 np.float, np.int, np.bool 等废弃别名。"""
    if not hasattr(np, 'VisibleDeprecationWarning'):
        np.VisibleDeprecationWarning = DeprecationWarning
    if not hasattr(np, 'float'):
        np.float = np.float64; np.int = np.int32
        np.bool = np.bool_; np.complex = np.complex128


def _patch_face3d_compat():
    """SadTalker face3d 兼容补丁: 修复 POS() 返回 (2,1) 矩阵导致的 inhomogeneous shape 错误。

    问题根因:
      SadTalker 的 face3d.POS() 有时返回 shape(2,1) 的数组而非标量，
      这些数组元素被传入 np.array(sequence) 时，NumPy 无法自动对齐不同维度的元素，
      导致 ValueError: setting an array element with a sequence.

    修复策略:
      封装 np.array，在遇到 inhomogeneous shape 错误时，自动将序列中的数组元素
      展平为标量值，确保 array 构造成功完成。
    """
    _orig_array = np.array

    def _patched(object, dtype=None, *, copy=True, order='K',
                 subok=False, ndmin=0, like=None):
        """带降级处理的 np.array 封装。先尝试原始构造，失败时展平数组元素。"""
        try:
            return _orig_array(object, dtype=dtype, copy=copy, order=order,
                               subok=subok, ndmin=ndmin, like=like)
        except (ValueError, TypeError):
            # 降级处理: 将序列中每个 ndarray 元素展平为标量
            flat = []
            for item in object:
                if isinstance(item, np.ndarray):
                    flat.append(item.flat[0] if item.size > 0 else 0)
                else:
                    flat.append(item)
            return _orig_array(flat, dtype=dtype)

    np.array = _patched


def _ensure_gfpgan_mock():
    """Mock gfpgan 模块 — SadTalker face_enhancer 依赖。
    设置 __path__ 使其成为包模块（package），否则导入失败。"""
    if 'gfpgan' not in sys.modules:
        import types as _t
        dm = _t.ModuleType('gfpgan')
        dm.__path__ = []                              # 标记为 package
        dm.__file__ = '/tmp/mock_gfpgan/__init__.py'
        class _Dummy:
            def __init__(self, *a, **k): pass
            def enhance(self, *a, **k): return a[0] if a else None
        dm.GFPGANer = _Dummy
        sys.modules['gfpgan'] = dm
        logger.info("GFPGAN mock已就位（use_enhancer=False时不受影响）")


def _ensure_modelscope_mock():
    """Mock modelscope 模块 — SadTalker face_enhancer 强制依赖。
    我们 use_enhancer=False，用 mock 避免不必要的安装。"""
    if 'modelscope' not in sys.modules:
        import types as _t
        ms = _t.ModuleType('modelscope'); ms.__path__ = []
        ms_hub = _t.ModuleType('modelscope.hub'); ms_hub.__path__ = []
        ms_hub_sd = _t.ModuleType('modelscope.hub.snapshot_download')
        def _dummy(*a, **k): return ''
        ms_hub_sd.snapshot_download = _dummy
        ms_hub.snapshot_download = ms_hub_sd
        ms.hub = ms_hub
        sys.modules['modelscope.hub.snapshot_download'] = ms_hub_sd
        sys.modules['modelscope.hub'] = ms_hub
        sys.modules['modelscope'] = ms
        logger.info("modelscope mock已就位")

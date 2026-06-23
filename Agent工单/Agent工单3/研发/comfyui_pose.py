# -*- coding: utf-8 -*-
"""
ComfyUI 姿态/面部处理模块 — 骨架图生成、InstantID 源脸标准化、姿态参考图构建。
方法通过 monkeypatch 注册为 ComfyUIClient 类方法。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
"""

import cv2
import numpy as np

# 控制 from comfyui_pose import * 导出（含私有函数以保持向后兼容）
__all__ = ['_make_face_skeleton', '_make_simple_face_skeleton',
           '_prepare_instantid_source_face', '_normalize_pose_reference',
           '_make_pose_reference_from_source', '_build_pose_refs_with_affine']


# ================================================================
# 面部骨架图生成（模块级工具函数）
# ================================================================

def _make_face_skeleton(h: int, w: int, face_shift_x: float = 0.0) -> np.ndarray:
    """生成面部+上半身 OpenPose 骨架图（白色背景）。face_shift_x 控制面部水平偏移。"""
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)  # 白色画布
    shift = face_shift_x
    # 关键点归一化坐标
    kp = {0:  (0.50 + shift, 0.28),            # 鼻子
          1:  (0.50, 0.42),                     # 颈部
          2:  (0.30, 0.55),                     # 左肩
          5:  (0.70, 0.55),                     # 右肩
          14: (0.44 + shift * 0.7, 0.23),       # 左眼
          15: (0.56 + shift * 0.7, 0.23),       # 右眼
          16: (0.42 + shift * 0.8, 0.28),       # 左耳
          17: (0.58 + shift * 0.8, 0.28)}       # 右耳
    # 骨骼连接
    bones = [(1, 0), (1, 2), (1, 5), (0, 14), (0, 15), (14, 16), (15, 17)]
    # 头部椭圆
    head_cx = int((0.50 + shift * 0.35) * w)
    head_cy = int(0.28 * h)
    head_ax = (max(28, int(0.16 * w)), max(36, int(0.22 * h)))
    cv2.ellipse(canvas, (head_cx, head_cy), head_ax, 0, 0, 360, (215, 215, 215), -1)
    # 骨骼线
    for a, b in bones:
        x1, y1 = int(kp[a][0] * w), int(kp[a][1] * h)
        x2, y2 = int(kp[b][0] * w), int(kp[b][1] * h)
        cv2.line(canvas, (x1, y1), (x2, y2), (60, 60, 60), 3)
    # 关键点
    for pt in kp.values():
        cv2.circle(canvas, (int(pt[0] * w), int(pt[1] * h)), 5, (40, 40, 40), -1)
    return canvas


def _make_simple_face_skeleton(h: int, w: int) -> np.ndarray:
    """兼容旧接口 — 默认居中骨架（无偏移）。"""
    return _make_face_skeleton(h, w, face_shift_x=0.0)


# ================================================================
# InstantID 源脸预处理（将注册为 ComfyUIClient 静态方法）
# ================================================================

def _prepare_instantid_source_face(source_img: np.ndarray) -> np.ndarray:
    """将原图整理为 InstantID 标准输入图：缩放+居中+白底，提高检脸成功率。"""
    height, width = source_img.shape[:2]
    canvas_size = max(512, max(height, width))  # 最小 512px 画布
    scale = min(0.68 * canvas_size / max(width, 1),
                0.68 * canvas_size / max(height, 1))
    new_w, new_h = max(128, int(width * scale)), max(128, int(height * scale))
    resized = cv2.resize(source_img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((canvas_size, canvas_size, 3), 255, dtype=np.uint8)
    x0, y0 = (canvas_size - new_w) // 2, (canvas_size - new_h) // 2  # 居中
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def _normalize_pose_reference(image: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """标准化姿态参考图：缩放→72%占比居中→白底，确保 InstantID 可检脸。"""
    resized = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
    scale = 0.72  # 内部图像占比
    inner_w, inner_h = max(128, int(target_w * scale)), max(128, int(target_h * scale))
    inner = cv2.resize(resized, (inner_w, inner_h), interpolation=cv2.INTER_LINEAR)
    x0, y0 = (target_w - inner_w) // 2, (target_h - inner_h) // 2
    canvas[y0:y0 + inner_h, x0:x0 + inner_w] = inner
    return canvas


def _make_pose_reference_from_source(source_img: np.ndarray, shift_ratio: float) -> np.ndarray:
    """从原图仿射变换生成姿态参考脸，优先保证 InstantID 检脸。

    shift_ratio 负值左偏、正值右偏，经归一化输出。
    """
    height, width = source_img.shape[:2]
    normalized = _normalize_pose_reference(source_img, width, height)  # 先归一化
    src = np.float32([[0.22 * width, 0.18 * height],   # 源三点
                      [0.78 * width, 0.18 * height],
                      [0.50 * width, 0.84 * height]])
    dst = np.float32([[(0.22 + shift_ratio) * width, 0.16 * height],  # 目标三点
                      [(0.78 + shift_ratio) * width, 0.20 * height],
                      [0.50 * width, 0.84 * height]])
    matrix = cv2.getAffineTransform(src, dst)  # 计算仿射矩阵
    warped = cv2.warpAffine(normalized, matrix, (width, height),
                            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return _normalize_pose_reference(warped, width, height)  # 最终归一化


def _build_pose_refs_with_affine(source_img: np.ndarray) -> dict:
    """生成左/右/正面仿射姿态参考图（PNG 字节）。

    比单纯水平翻转更稳，通过仿射变换给出明确朝向信号。
    Returns: {"left": bytes, "right": bytes, "front": bytes}
    """
    height, width = source_img.shape[:2]

    def make_variant(shift_x_ratio: float, scale_x: float) -> bytes:
        """生成单个朝向变体的 PNG 字节。"""
        src = np.float32([[0.25 * width, 0.25 * height],
                          [0.75 * width, 0.25 * height],
                          [0.50 * width, 0.82 * height]])
        dst = np.float32([[(0.25 + shift_x_ratio) * width, 0.23 * height],
                          [(0.75 + shift_x_ratio) * width, 0.27 * height],
                          [0.50 * width, 0.82 * height]])
        matrix = cv2.getAffineTransform(src, dst)
        warped = cv2.warpAffine(source_img, matrix, (width, height),
                                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if scale_x != 1.0:  # 水平缩放
            scaled_w = max(1, int(width * scale_x))
            resized = cv2.resize(warped, (scaled_w, height), interpolation=cv2.INTER_LINEAR)
            if scaled_w >= width:
                start = (scaled_w - width) // 2
                warped = resized[:, start:start + width]  # 居中裁剪
            else:
                canvas = np.zeros_like(warped)
                start = (width - scaled_w) // 2
                canvas[:, start:start + scaled_w] = resized  # 居中贴入
                warped = canvas
        warped = _normalize_pose_reference(warped, width, height)  # 归一化
        ok, buf = cv2.imencode('.png', warped)  # PNG 编码
        if not ok:
            raise RuntimeError('仿射姿态参考图编码失败')
        return buf.tobytes()

    # 正面图直接归一化
    front = _normalize_pose_reference(source_img, width, height)
    ok, front_buf = cv2.imencode('.png', front)
    if not ok:
        raise RuntimeError('正面姿态参考图编码失败')

    return {'left': make_variant(-0.08, 0.92),    # 左偏 8% + 水平压缩 8%
            'right': make_variant(0.08, 0.92),    # 右偏 8% + 水平压缩 8%
            'front': front_buf.tobytes()}          # 正面保持原样


# ================================================================
# Monkeypatch 注册
# ================================================================
from comfyui_client import ComfyUIClient  # noqa: E402 — 延迟导入

ComfyUIClient._prepare_instantid_source_face = staticmethod(_prepare_instantid_source_face)
ComfyUIClient._normalize_pose_reference = staticmethod(_normalize_pose_reference)
ComfyUIClient._make_pose_reference_from_source = staticmethod(_make_pose_reference_from_source)
ComfyUIClient._build_pose_refs_with_affine = staticmethod(_build_pose_refs_with_affine)

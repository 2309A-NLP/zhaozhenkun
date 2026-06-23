# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：人脸处理工具函数与辅助方法（FaceProcessor 扩展模块）
==============================================================================
本文件提供以下扩展功能，通过 monkeypatch 注入到 FaceProcessor 类：
  - prepare_rotation_image(): 使用 MediaPipe 3D 关键点进行面部旋转引导图生成
  - validate_face(): 验证生成图像中的人脸质量
  - _check_image_quality(): 检查图像基础质量指标（清晰度、噪声、颜色）
  - _get_landmarks_3d(): 提取 3D 人脸关键点
  - _get_contour_indices(): 面部轮廓关键点索引
  - _fallback_rotation(): 透视模拟旋转（回退方案）

本模块不独立使用，需配合 face_processor.py 中的 FaceProcessor 类。

依赖库：opencv-python, mediapipe, numpy, PIL
工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import logging                              # 日志模块
import cv2                                  # OpenCV图像处理库
import numpy as np                          # 数值计算库
from typing import Tuple, Optional, List    # 类型提示

from config import face_config              # 导入人脸配置

logger = logging.getLogger(__name__)        # 创建模块日志器


# ================================================================
# 旋转引导图生成（核心扩展）
# ================================================================
def prepare_rotation_image(self, image: np.ndarray, angle: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    准备旋转引导图像
    使用 MediaPipe 3D 人脸网格进行真实 3D 旋转：
    1. 提取 468 个 3D 人脸关键点 → 2. 围绕 Y 轴旋转 → 3. 投影回 2D 并计算透视变换
    与旧版 cv2.warpAffine 的区别：旧版只做水平压缩模拟变窄，新版做真正的 3D→2D 投影旋转
    """
    h, w = image.shape[:2]                                          # 获取图像尺寸
    theta = np.radians(angle)                                       # 角度转弧度

    landmarks_3d = self._get_landmarks_3d(image)                    # 获取468个人脸3D关键点
    if landmarks_3d is None or len(landmarks_3d) < 100:             # 关键点不足时回退
        logger.warning("无法获取 3D 人脸关键点，使用透视模拟旋转")
        return self._fallback_rotation(image, angle), self.create_depth_map(image)

    centroid = landmarks_3d.mean(axis=0)                            # 计算3D关键点中心

    # Y 轴旋转矩阵（左右转头）
    cos_a, sin_a = np.cos(theta), np.sin(theta)                     # 三角函数值
    R = np.array([[cos_a, 0, sin_a], [0, 1, 0], [-sin_a, 0, cos_a]], dtype=np.float64)

    centered = landmarks_3d - centroid                              # 关键点去中心化
    rotated_3d = centered @ R.T + centroid                          # 应用Y轴旋转矩阵

    # 投影回 2D（正交投影，对 ±30° 足够）
    src_pts = landmarks_3d[:, :2].astype(np.float32)                # 原始2D投影坐标
    dst_pts = rotated_3d[:, :2].astype(np.float32)                  # 旋转后2D投影坐标

    # 选择稳定的面部轮廓点用于透视变换
    contour_indices = self._get_contour_indices()                   # 获取轮廓关键点索引
    available = [i for i in contour_indices if i < len(src_pts)]    # 过滤有效索引
    if len(available) < 20:                                         # 轮廓点不足时均匀采样
        available = list(range(0, len(src_pts), 8))

    src_contour = src_pts[available]                                # 原始轮廓点集
    dst_contour = dst_pts[available]                                # 旋转后轮廓点集

    try:
        H, _ = cv2.findHomography(src_contour, dst_contour,         # RANSAC计算透视变换
                                   method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if H is None:
            raise ValueError("findHomography 失败")
        rotated = cv2.warpPerspective(image, H, (w, h),             # 应用透视变换
                                       flags=cv2.INTER_LANCZOS4,
                                       borderMode=cv2.BORDER_REFLECT_101)
    except Exception:
        logger.warning("透视变换失败，使用仿射变换")
        M = cv2.estimateAffine2D(src_contour, dst_contour, method=cv2.RANSAC)[0]
        if M is None:
            M = cv2.estimateAffine2D(src_pts, dst_pts)[0]           # 使用全部点计算
        if M is None:
            return image, self.create_depth_map(image)              # 全部失败返回原图
        rotated = cv2.warpAffine(image, M, (w, h),                  # 应用仿射变换
                                  flags=cv2.INTER_LANCZOS4,
                                  borderMode=cv2.BORDER_REFLECT_101)

    depth_map = self.create_depth_map(rotated)                      # 生成旋转后深度图
    logger.info(f"3D 人脸旋转完成: angle={angle}°, landmarks={len(landmarks_3d)}")
    return rotated, depth_map


# ================================================================
# 3D 关键点提取（内部辅助）
# ================================================================
def _get_landmarks_3d(self, image: np.ndarray) -> Optional[np.ndarray]:
    """获取 3D 人脸关键点坐标（468 点 × xyz）"""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)                    # BGR转RGB
    results = self.face_mesh.process(rgb)                           # MediaPipe推理
    if not results.multi_face_landmarks:                            # 未检测到人脸
        return None
    lm = results.multi_face_landmarks[0]                            # 第一个人脸关键点
    h, w = image.shape[:2]                                          # 图像宽高
    pts = np.array([[l.x * w, l.y * h, l.z * w] for l in lm.landmark], dtype=np.float64)
    return pts                                                      # 返回 (468, 3) 数组


# ================================================================
# 轮廓关键点索引
# ================================================================
def _get_contour_indices() -> list:
    """面部轮廓 + 五官关键点索引（MediaPipe Face Mesh）"""
    # Jawline + 眉毛 + 眼睛 + 鼻子 + 嘴巴 + 鼻梁
    return [
        10, 21, 33, 46, 58, 67, 79, 93, 103, 109, 117, 127, 132,   # Jawline 前半
        136, 148, 149, 150, 152, 162, 172, 176, 200, 212,           # Jawline 中部
        234, 251, 263, 276, 284, 288, 297, 310, 323, 332,           # Jawline 后半
        338, 349, 356, 361, 365, 377, 378, 379, 389, 397, 400, 454, # Jawline 尾端
        55, 70, 105, 107, 285, 300, 336, 334,                       # Eyebrows
        33, 133, 159, 145, 263, 362, 386, 374,                      # Eyes
        1, 2, 5, 98, 197, 195,                                      # Nose
        61, 78, 81, 95, 291, 308, 311, 324,                         # Mouth
    ]


# ================================================================
# 透视模拟旋转（回退方案）
# ================================================================
def _fallback_rotation(image: np.ndarray, angle: float) -> np.ndarray:
    """改进的透视模拟旋转（当无法获取 3D 关键点时使用）"""
    h, w = image.shape[:2]                                          # 图像尺寸
    src_pts = np.float32([[0, 0], [w, 0], [0, h], [w, h]])         # 原始四个角
    if angle < 0:  # 左转 — 左侧缩小，右侧放大
        dst_pts = np.float32([[w*0.08, h*0.03], [w*0.92, h*0.12],
                               [w*0.02, h*0.88], [w*0.98, h*0.97]])
    elif angle > 0:  # 右转 — 右侧缩小，左侧放大
        dst_pts = np.float32([[w*0.08, h*0.12], [w*0.92, h*0.03],
                               [w*0.02, h*0.97], [w*0.98, h*0.88]])
    else:
        return image                                                # 0度不旋转
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)               # 计算透视变换矩阵
    return cv2.warpPerspective(image, M, (w, h),                    # 应用透视变换
                                flags=cv2.INTER_LANCZOS4,
                                borderMode=cv2.BORDER_REFLECT_101)


# ================================================================
# 人脸质量验证
# ================================================================
def validate_face(self, image: np.ndarray, label: str = "") -> dict:
    """验证生成图像中的人脸质量
    Returns: dict with has_face, confidence, bbox, landmarks_count, warnings
    """
    result = {"has_face": False, "confidence": 0.0, "bbox": None,   # 初始化结果字典
              "landmarks_count": 0, "warnings": [], "label": label}

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)                    # BGR转RGB
    det_results = self.face_detector.process(rgb)                   # MediaPipe人脸检测
    if not det_results.detections:                                  # 未检测到人脸
        result["warnings"].append("未检测到人脸")
        return result

    detection = det_results.detections[0]                           # 第一个检测结果
    score = detection.score[0] if hasattr(detection, 'score') else 1.0
    result["has_face"] = True                                       # 标记检测到人脸
    result["confidence"] = float(score)                             # 记录置信度

    # 提取边界框
    bbox = detection.location_data.relative_bounding_box             # 相对边界框
    h, w = image.shape[:2]                                          # 图像尺寸
    x, y = int(bbox.xmin * w), int(bbox.ymin * h)                   # 左上角绝对坐标
    bw, bh = int(bbox.width * w), int(bbox.height * h)              # 宽高绝对值
    result["bbox"] = (x, y, bw, bh)                                 # 记录边界框

    # 检查人脸大小是否合理
    face_area_ratio = (bw * bh) / (w * h)                           # 人脸面积占比
    if face_area_ratio < 0.05:                                      # 人脸过小
        result["warnings"].append(f"人脸过小 ({face_area_ratio:.1%})")
    elif face_area_ratio > 0.8:                                     # 人脸过大
        result["warnings"].append(f"人脸占比过大 ({face_area_ratio:.1%})")

    # 提取关键点
    lm_results = self.face_mesh.process(rgb)                        # MediaPipe关键点检测
    if lm_results.multi_face_landmarks:
        result["landmarks_count"] = len(lm_results.multi_face_landmarks[0].landmark)

    # 图像质量检查与置信度
    quality_warnings = self._check_image_quality(image, label)
    result["warnings"].extend(quality_warnings)
    if score < 0.5:                                                 # 置信度过低
        result["warnings"].append(f"人脸置信度偏低 ({score:.2f})")
    return result


# ================================================================
# 图像质量检查
# ================================================================
def _check_image_quality(image: np.ndarray, label: str = "") -> List[str]:
    """检查生成图像的基础质量指标
    检查项：清晰度（拉普拉斯方差）、颜色范围、噪声水平
    Returns: 警告信息列表
    """
    warnings = []                                                   # 初始化警告列表
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)                  # 转灰度图

    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()           # 拉普拉斯方差 — 清晰度
    if laplacian_var < 50:                                          # 严重模糊
        warnings.append(f"[{label}] 图像模糊 (laplacian_var={laplacian_var:.0f})")
    elif laplacian_var < 100:                                       # 轻微模糊
        warnings.append(f"[{label}] 图像清晰度偏低 (laplacian_var={laplacian_var:.0f})")

    channel_mins = image.min(axis=(0, 1))                           # 各通道最小值
    channel_maxs = image.max(axis=(0, 1))                           # 各通道最大值
    for ch_idx, ch_name in enumerate(["B", "G", "R"]):              # 遍历BGR三通道
        if channel_maxs[ch_idx] - channel_mins[ch_idx] < 20:        # 动态范围过低
            warnings.append(f"[{label}] {ch_name}通道动态范围过低")

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)                    # 高斯平滑
    noise = np.abs(gray.astype(float) - blurred.astype(float))      # 高频噪声分量
    noise_ratio = (noise > 20).mean()                               # 噪声像素占比
    if noise_ratio > 0.3:                                           # 噪声过高
        warnings.append(f"[{label}] 噪声过高 (noise_ratio={noise_ratio:.1%})")

    return warnings


# ================================================================
# Monkeypatch: 将本模块函数注册到 FaceProcessor 类
# ================================================================
from face_processor import FaceProcessor  # noqa: E402  # 导入核心类

# 实例方法（含 self 参数）
FaceProcessor.prepare_rotation_image = prepare_rotation_image       # 旋转引导图生成
FaceProcessor._get_landmarks_3d = _get_landmarks_3d                 # 3D关键点提取
FaceProcessor.validate_face = validate_face                         # 人脸质量验证

# 静态方法（含 @staticmethod 装饰器，调用时 self 不绑定）
FaceProcessor._get_contour_indices = staticmethod(_get_contour_indices)
FaceProcessor._fallback_rotation = staticmethod(_fallback_rotation)
FaceProcessor._check_image_quality = staticmethod(_check_image_quality)

logger.debug("face_utils 扩展方法已注册到 FaceProcessor")          # 注册确认日志

# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：人脸分析与验证模块（FaceProcessor 扩展模块）
==============================================================================
本文件提供以下扩展功能，通过 monkeypatch 注入到 FaceProcessor 类：
  - validate_identity(): 验证生成图像是否保持了原始人物身份
  - validate_pose(): 验证生成图像的头部姿态是否符合预期方向
  - _procrustes_similarity(): Procrustes 配准相似度计算
  - _histogram_similarity(): 颜色直方图相似度计算

本模块不独立使用，需配合 face_processor.py 中的 FaceProcessor 类。

依赖库：opencv-python, numpy
工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import logging                              # 日志模块
import cv2                                  # OpenCV图像处理库
import numpy as np                          # 数值计算库
from typing import Dict, Optional           # 类型提示

logger = logging.getLogger(__name__)        # 创建模块日志器


# ================================================================
# 身份相似度验证
# ================================================================
def validate_identity(
    self,
    original: np.ndarray,
    generated: np.ndarray,
    threshold: float = 0.6,
) -> Dict[str, object]:
    """验证生成图像是否保持了原始人物身份

    通过比较以下特征来评估身份一致性：
    1. 人脸关键点几何分布相似度（Procrustes 配准）
    2. 面部区域颜色直方图相似度
    3. 人脸检测置信度变化

    Args:
        original: 原始人脸图像 (BGR)
        generated: 生成的人脸图像 (BGR)
        threshold: 通过阈值（综合分 ≥ threshold 视为身份一致）

    Returns:
        {"identity_preserved": bool, "geo_similarity": float,
         "color_similarity": float, "composite_score": float, "warnings": [str]}
    """
    result = {                                                      # 初始化结果字典
        "identity_preserved": False,
        "geo_similarity": 0.0,                                      # 关键点几何相似度
        "color_similarity": 0.0,                                    # 颜色直方图相似度
        "composite_score": 0.0,                                     # 综合评分
        "warnings": [],
    }

    # 1. 提取关键点几何特征
    orig_lm = self._get_landmarks_3d(original)                      # 原图3D关键点
    gen_lm = self._get_landmarks_3d(generated)                      # 生成图3D关键点

    if orig_lm is None:                                             # 原图无法提取
        result["warnings"].append("无法从原图提取人脸关键点")
        return result
    if gen_lm is None:                                              # 生成图无法提取
        result["warnings"].append("无法从生成图提取人脸关键点（可能已换人）")
        return result

    # 2. 计算关键点几何相似度 (Procrustes 配准 → 消除旋转/缩放影响)
    geo_sim = self._procrustes_similarity(orig_lm, gen_lm)
    result["geo_similarity"] = geo_sim

    if geo_sim < 0.5:                                               # 几何差异过大
        result["warnings"].append(f"面部关键点几何差异过大 (geo_sim={geo_sim:.2f})，可能是不同人")
    elif geo_sim < 0.7:                                             # 有一定差异
        result["warnings"].append(f"面部关键点几何有一定差异 (geo_sim={geo_sim:.2f})")

    # 3. 颜色直方图相似度
    color_sim = self._histogram_similarity(original, generated)
    result["color_similarity"] = color_sim

    if color_sim < 0.6:                                             # 颜色变化较大
        result["warnings"].append(f"肤色/颜色分布变化较大 (color_sim={color_sim:.2f})")

    # 4. 综合评分（几何权重更高 — 人脸结构比颜色更能说明换人）
    result["composite_score"] = 0.65 * geo_sim + 0.35 * color_sim
    result["identity_preserved"] = result["composite_score"] >= threshold

    return result


# ================================================================
# Procrustes 相似度计算
# ================================================================
def _procrustes_similarity(
    points_a: np.ndarray, points_b: np.ndarray
) -> float:
    """计算两组关键点之间的 Procrustes 相似度

    先进行 Procrustes 配准（平移 + 旋转 + 缩放），
    然后计算配准后的平均距离，转换为 [0,1] 相似度。

    Args:
        points_a: 原图关键点 (N, 3)
        points_b: 生成图关键点 (N, 3)

    Returns:
        相似度 [0, 1]，1=完全相同
    """
    a = points_a[:, :2].astype(np.float64)                          # 只用 x,y 坐标
    b = points_b[:, :2].astype(np.float64)

    # 去中心化
    a_mean = a.mean(axis=0)                                         # 原图中心
    b_mean = b.mean(axis=0)                                         # 生成图中心
    a_centered = a - a_mean
    b_centered = b - b_mean

    # 归一化尺度
    a_scale = np.sqrt((a_centered ** 2).sum()) / len(a)            # 原图尺度
    b_scale = np.sqrt((b_centered ** 2).sum()) / len(b)            # 生成图尺度
    if a_scale < 1e-6 or b_scale < 1e-6:                           # 尺度接近零
        return 0.0
    a_norm = a_centered / a_scale                                   # 归一化
    b_norm = b_centered / b_scale

    # 最优旋转（SVD 分解）
    H = a_norm.T @ b_norm                                           # 交叉协方差矩阵
    try:
        U, S, Vt = np.linalg.svd(H)                                 # SVD分解
        R_opt = Vt.T @ U.T                                          # 最优旋转矩阵
        if np.linalg.det(R_opt) < 0:                                # 确保是旋转（非反射）
            Vt[-1, :] *= -1
            R_opt = Vt.T @ U.T
    except np.linalg.LinAlgError:                                   # SVD失败
        return 0.0

    # 配准后的平均距离
    aligned = a_norm @ R_opt                                        # 应用旋转
    distances = np.sqrt(((aligned - b_norm) ** 2).sum(axis=1))     # 逐点欧氏距离
    avg_distance = distances.mean()                                 # 平均距离

    # 转换为相似度 [0, 1]
    face_diag = np.sqrt((a.max(axis=0) - a.min(axis=0)) ** 2).sum()  # 面部对角线
    normalized_dist = avg_distance / (face_diag * 0.1 + 1e-6)       # 归一化距离
    similarity = max(0.0, min(1.0, 1.0 - normalized_dist * 0.5))   # 映射到相似度
    return similarity


# ================================================================
# 颜色直方图相似度
# ================================================================
def _histogram_similarity(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """计算两张图像面部区域的颜色直方图相似度"""
    hsv_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2HSV)                  # 转HSV（对光照鲁棒）
    hsv_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2HSV)

    similarities = []                                               # 各通道相似度收集
    for ch in range(3):                                             # H, S, V 三通道
        hist_a = cv2.calcHist([hsv_a], [ch], None, [64], [0, 256])  # 直方图A
        hist_b = cv2.calcHist([hsv_b], [ch], None, [64], [0, 256])  # 直方图B
        cv2.normalize(hist_a, hist_a, 0, 1, cv2.NORM_MINMAX)        # 归一化A
        cv2.normalize(hist_b, hist_b, 0, 1, cv2.NORM_MINMAX)        # 归一化B
        corr = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)  # 相关性比较
        similarities.append(max(0.0, corr))                         # 截断负值

    return float(np.mean(similarities))                             # 平均相似度


# ================================================================
# 姿态验证
# ================================================================
def validate_pose(
    self,
    image: np.ndarray,
    expected_direction: str,
    tolerance: float = 15.0,
) -> Dict[str, object]:
    """验证生成图像的头部姿态是否符合预期方向

    Args:
        image: 生成的人脸图像
        expected_direction: 期望的方向 ("left", "right", "front")
        tolerance: 角度容差（度数）

    Returns:
        {"pose_correct": bool, "yaw": float, "pitch": float,
         "roll": float, "expected": str, "warnings": [str]}
    """
    pose = self.estimate_pose(image)                                # 估算当前姿态
    if pose is None:                                                # 姿态估计失败
        return {
            "pose_correct": False,
            "yaw": 0, "pitch": 0, "roll": 0,
            "expected": expected_direction,
            "warnings": ["无法估计姿态"],
        }

    yaw, pitch, roll = pose                                         # 解包三个欧拉角
    warnings = []

    # 根据期望方向检查 yaw 角度
    if expected_direction == "left":                                # 期望左转
        pose_correct = yaw < -tolerance                             # yaw应小于负容差
        if not pose_correct:
            warnings.append(f"期望左转但 yaw={yaw:.1f}°（应 < -{tolerance}°）")
    elif expected_direction == "right":                             # 期望右转
        pose_correct = yaw > tolerance                              # yaw应大于正容差
        if not pose_correct:
            warnings.append(f"期望右转但 yaw={yaw:.1f}°（应 > {tolerance}°）")
    else:  # front                                                  # 期望正面
        pose_correct = abs(yaw) <= tolerance                        # yaw绝对值应在容差内
        if not pose_correct:
            warnings.append(f"期望正面但 yaw={yaw:.1f}°（|yaw| 应 ≤ {tolerance}°）")

    return {
        "pose_correct": pose_correct,
        "yaw": yaw, "pitch": pitch, "roll": roll,
        "expected": expected_direction,
        "warnings": warnings,
    }


# ================================================================
# Monkeypatch: 将本模块函数注册到 FaceProcessor 类
# ================================================================
from face_processor import FaceProcessor  # noqa: E402  # 导入核心类

# 实例方法（含 self 参数）
FaceProcessor.validate_identity = validate_identity                 # 身份一致性验证
FaceProcessor.validate_pose = validate_pose                         # 姿态方向验证

# 静态方法（无 self 参数）
FaceProcessor._procrustes_similarity = staticmethod(_procrustes_similarity)
FaceProcessor._histogram_similarity = staticmethod(_histogram_similarity)

logger.debug("face_analysis 扩展方法已注册到 FaceProcessor")       # 注册确认日志

# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：人脸检测与处理模块（核心类）
==============================================================================
本文件实现了人脸图像的检测、关键点提取和姿态估计功能：
  - detect_face(): 检测图像中的人脸区域
  - extract_landmarks(): 提取人脸关键点（68点或468点）
  - estimate_pose(): 估算人脸朝向（yaw, pitch, roll）
  - crop_face_region(): 裁剪人脸区域并保留边距
  - create_depth_map(): 生成人脸深度图（用于ControlNet）

扩展方法通过 monkeypatch 注入：
  - face_utils.py: prepare_rotation_image, validate_face 等
  - face_analysis.py: validate_identity, validate_pose 等

依赖库：opencv-python, mediapipe, numpy, PIL
工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import cv2                                  # OpenCV图像处理库
import numpy as np                          # 数值计算库
from typing import Tuple, Optional, List, Dict          # 类型提示
import logging                              # 日志模块

try:
    import mediapipe as mp                  # Google人脸关键点检测库
    MEDIAPIPE_AVAILABLE = True              # 标记依赖可用
    MEDIAPIPE_IMPORT_ERROR = ""             # 记录导入错误
except Exception as e:
    mp = None                               # 缺失时置空
    MEDIAPIPE_AVAILABLE = False             # 标记依赖不可用
    MEDIAPIPE_IMPORT_ERROR = str(e)         # 保存错误信息

from config import face_config              # 导入人脸配置

logger = logging.getLogger(__name__)        # 创建模块日志器


class FaceProcessor:
    """人脸处理器类"""

    def __init__(self):
        """初始化人脸处理器"""
        self._check_dependency()                                # 先检查依赖
        self.mp_face_mesh = mp.solutions.face_mesh              # 加载人脸网格模块
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        self.mp_face_detection = mp.solutions.face_detection    # 加载人脸检测模块
        self.face_detector = self.mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5
        )
        logger.info("人脸处理器初始化完成")

    @staticmethod
    def _check_dependency():
        """检查 mediapipe 是否可用，不可用时给出明确提示"""
        if MEDIAPIPE_AVAILABLE:
            return
        message = (
            "未检测到 mediapipe，当前环境无法执行人脸检测。\n"
            "请在 Windows 的 llamafactory 环境里执行：\n"
            "pip install mediapipe==0.10.14\n"
            f"原始错误：{MEDIAPIPE_IMPORT_ERROR}"
        )
        raise RuntimeError(message)

    def detect_face(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """检测图像中的人脸，返回边界框坐标"""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.face_detector.process(rgb_image)
        if not results.detections:
            logger.warning("未检测到人脸")
            return None
        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box
        h, w, _ = image.shape
        x = int(bbox.xmin * w)
        y = int(bbox.ymin * h)
        bw = int(bbox.width * w)
        bh = int(bbox.height * h)
        logger.info(f"检测到人脸: x={x}, y={y}, w={bw}, h={bh}")
        return (x, y, bw, bh)

    def extract_landmarks(self, image: np.ndarray) -> Optional[np.ndarray]:
        """提取人脸468个关键点坐标"""
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_image)
        if not results.multi_face_landmarks:
            logger.warning("未提取到人脸关键点")
            return None
        face_landmarks = results.multi_face_landmarks[0]
        h, w, _ = image.shape
        landmarks = []
        for lm in face_landmarks.landmark:
            px = lm.x * w
            py = lm.y * h
            pz = lm.z * w
            landmarks.append([px, py, pz])
        landmarks = np.array(landmarks, dtype=np.float32)
        logger.info(f"提取到 {len(landmarks)} 个人脸关键点")
        return landmarks

    def estimate_pose(self, image: np.ndarray) -> Optional[Tuple[float, float, float]]:
        """估算人脸姿态角度"""
        landmarks = self.extract_landmarks(image)
        if landmarks is None:
            return None
        image_points = np.array([
            landmarks[1][:2],
            landmarks[152][:2],
            landmarks[33][:2],
            landmarks[263][:2],
            landmarks[61][:2],
            landmarks[291][:2],
        ], dtype=np.float64)
        model_points = np.array([
            [0.0, 0.0, 0.0],
            [0.0, -63.6, -12.5],
            [-43.3, 32.7, -26.0],
            [43.3, 32.7, -26.0],
            [-28.9, -28.9, -24.1],
            [28.9, -28.9, -24.1],
        ], dtype=np.float64)
        h, w = image.shape[:2]
        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        dist_coeffs = np.zeros((4, 1))
        success, rotation_vec, translation_vec = cv2.solvePnP(
            model_points,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        if not success:
            logger.warning("姿态估计失败")
            return None
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)
        pose_mat = cv2.hconcat([rotation_mat, translation_vec])
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(pose_mat)
        yaw = float(euler_angles[1][0])
        pitch = float(euler_angles[0][0])
        roll = float(euler_angles[2][0])
        logger.info(f"姿态估计: yaw={yaw:.1f}°, pitch={pitch:.1f}°, roll={roll:.1f}°")
        return (yaw, pitch, roll)

    def crop_face_region(self, image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """根据边界框裁剪人脸区域"""
        x, y, w, h = bbox
        margin = face_config.crop_margin
        img_h, img_w = image.shape[:2]
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img_w, x + w + margin)
        y2 = min(img_h, y + h + margin)
        cropped = image[y1:y2, x1:x2]
        logger.info(f"裁剪人脸区域: ({x1},{y1})-({x2},{y2})")
        return cropped

    def create_depth_map(self, image: np.ndarray) -> np.ndarray:
        """生成简易深度图用于 ControlNet 条件控制"""
        landmarks = self.extract_landmarks(image)
        h, w = image.shape[:2]
        depth_map = np.zeros((h, w), dtype=np.uint8)
        if landmarks is not None:
            for lm in landmarks:
                px, py = int(lm[0]), int(lm[1])
                if 0 <= px < w and 0 <= py < h:
                    depth_val = np.clip(128 + lm[2] * 500, 0, 255)
                    cv2.circle(depth_map, (px, py), 3, int(depth_val), -1)
            depth_map = cv2.GaussianBlur(depth_map, (21, 21), 0)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        depth_map = cv2.addWeighted(depth_map, 0.7, edges, 0.3, 0)
        logger.info("深度图生成完成")
        return depth_map

    # ================================================================
    # 以下扩展方法通过 monkeypatch 从独立模块注入：
    #   prepare_rotation_image, validate_face    → face_utils.py
    #   validate_identity, validate_pose         → face_analysis.py
    # 导入 face_utils / face_analysis 后即可调用全部方法
    # ================================================================


# ================================================================
# 注册 monkeypatch 扩展方法（向后兼容 — 导入即生效）
# ================================================================
import face_utils  # noqa: E402  # 注入旋转准备、人脸验证、质量检查方法
import face_analysis  # noqa: E402  # 注入身份验证、姿态分析方法


if __name__ == "__main__":
    from config import setup_logging
    setup_logging()
    try:
        processor = FaceProcessor()
        logger.info("人脸处理器初始化成功")
    except Exception as e:
        logger.error(f"初始化失败: {e}")

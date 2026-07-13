"""
src/lipsync/simple_lipsync_render.py - 轻量口型图像变形逻辑
功能: 承载嘴部区域检测、能量归一化和单帧口型变形渲染逻辑。
说明: 从 simple_lipsync_engine.py 中拆出图像处理细节，降低主文件长度。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import os

import cv2
import numpy as np

DEFAULT_MOUTH_RATIO = 0.35
DEFAULT_MAX_OPEN = 2.5
DEFAULT_SMOOTH_WINDOW = 3


class SimpleLipSyncRenderMixin:
    """轻量口型动画渲染混入类。"""

    def _detect_mouth_region(self, img: np.ndarray):
        """检测嘴部区域，优先使用 Haar 人脸框，失败时回退启发式估计。"""
        height, width = img.shape[:2]
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if os.path.exists(cascade_path):
                cascade = cv2.CascadeClassifier(cascade_path)
                if not cascade.empty():
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
                    if len(faces) > 0:
                        x, y, face_w, face_h = max(faces, key=lambda rect: rect[2] * rect[3])
                        self._mouth_roi = (
                            y + int(face_h * 0.55),
                            y + int(face_h * 0.92),
                            x + int(face_w * 0.2),
                            x + int(face_w * 0.8),
                        )
                        return
        except Exception:
            pass
        face_y1 = int(height * 0.08)
        face_y2 = int(height * 0.80)
        face_x1 = int(width * 0.10)
        face_x2 = int(width * 0.90)
        self._mouth_roi = (
            int(face_y1 + (face_y2 - face_y1) * 0.55),
            int(face_y2 * 0.98),
            int(face_x1 + (face_x2 - face_x1) * 0.18),
            int(face_x2 - (face_x2 - face_x1) * 0.18),
        )

    def _build_frame_energies(self, audio_flat: np.ndarray, frame_count: int) -> list:
        """按 Mel hop 长度估算每帧能量，并做动态归一化。

        归一化策略: 使用实际最小值而非固定比例，确保静音段→闭嘴、说话段→张嘴。
        短窗口(5 hop) 提高对快速能量变化的响应速度。
        """
        hop = 200
        window_hops = 5  # 更短的窗口 → 更快响应能量变化
        frame_energies = []
        for index in range(frame_count):
            start = index * hop
            end = start + hop * window_hops
            if start < len(audio_flat):
                segment = audio_flat[start:min(end, len(audio_flat))]
                rms = float(np.sqrt(np.mean(np.clip(segment, -1, 1) ** 2))) if len(segment) > 0 else 0.0
                frame_energies.append(rms)
            else:
                frame_energies.append(0.0)
        if not frame_energies:
            return [0.0] * frame_count
        max_energy = max(frame_energies) or 1e-6
        # 使用实际最小值(不加比例地板)，确保静音段张口为0
        actual_min = min(frame_energies)
        # 如果最大最小太接近，不强行张嘴
        if max_energy - actual_min < max_energy * 0.05:
            return [0.0] * frame_count
        # 线性映射: 最小值→0, 最大值→1
        energy_range = max_energy - actual_min + 1e-8
        return [np.clip((energy - actual_min) / energy_range, 0.0, 1.0) for energy in frame_energies]

    def _generate_mouth_open_frame(self, img: np.ndarray, my1: int, my2: int,
                                    mx1: int, mx2: int, open_factor: float) -> np.ndarray:
        """生成单帧张嘴动画，按上下嘴唇分离方向做局部位移。"""
        height, width = img.shape[:2]
        mouth_h = my2 - my1
        mouth_w = mx2 - mx1
        if mouth_h <= 2 or mouth_w <= 2 or open_factor <= 1.0:
            return img
        result = img.copy().astype(np.float32)
        max_displace = int(mouth_h * 0.5 * (open_factor - 1.0))
        if max_displace <= 1:
            return img
        mid_y = (my1 + my2) // 2
        map_y = np.arange(height, dtype=np.float32)
        for y in range(my1, my2):
            distance = abs(y - mid_y)
            max_distance = mouth_h // 2
            if max_distance > 0:
                weight = 1.0 - (distance / max_distance)
                if weight > 0:
                    map_y[y] += (-max_displace if y < mid_y else max_displace) * weight
        map_y = np.clip(map_y, 0, height - 1).astype(np.float32)
        map_x = np.arange(width, dtype=np.float32)
        map_x, map_y = np.meshgrid(map_x, map_y)
        pad = max_displace * 2
        y1_pad = max(0, my1 - pad)
        y2_pad = min(height, my2 + pad)
        x1_pad = max(0, mx1 - pad)
        x2_pad = min(width, mx2 + pad)
        warped = cv2.remap(
            img.astype(np.float32),
            map_x[y1_pad:y2_pad, x1_pad:x2_pad].astype(np.float32),
            map_y[y1_pad:y2_pad, x1_pad:x2_pad].astype(np.float32),
            cv2.INTER_LINEAR,
        )
        result[y1_pad:y2_pad, x1_pad:x2_pad] = warped
        feather = max(3, pad // 2)
        mask = np.zeros((height, width), dtype=np.float32)
        cv2.rectangle(mask, (x1_pad + feather, y1_pad + feather), (x2_pad - feather, y2_pad - feather), 1.0, -1)
        mask = cv2.GaussianBlur(mask, (feather * 2 + 1, feather * 2 + 1), feather)
        mask = mask[:, :, np.newaxis]
        result = result * mask + img.astype(np.float32) * (1 - mask)
        return result.clip(0, 255).astype(np.uint8)

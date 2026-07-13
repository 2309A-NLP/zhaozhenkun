"""
src/video/compositor.py - 视频帧合成器
功能: 将Wav2Lip生成的唇形人脸粘贴回全身视频帧。
      处理说话/空闲视频切换，支持羽化边缘混合。
      新增自动人脸检测: 从全身参考帧自动定位人脸区域。
      对应工单需求:
        - "全身视频拼接，生成完整的数字人形象"
        - "在数字人不说话时，可以播放自定义视频"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import os
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


class FrameCompositor:
    """
    视频帧合成器。
    将唇形人脸粘贴到全身参考帧，支持说话/空闲状态切换。
    支持自动人脸检测定位 + 全身背景图/视频加载。
    """

    def __init__(self, output_width: int = 1280, output_height: int = 720,
                 face_size: int = 96, fps: int = 25,
                 background_path: str = None):
        """初始化合成器，设置输出分辨率和人脸尺寸。"""
        self.out_w = output_width
        self.out_h = output_height
        self.face_size = face_size
        self.fps = fps
        self.face_region = None  # 人脸在全身帧中的位置(x1,y1,x2,y2)
        self.ref_frame = None    # 参考全身帧
        self._face_detector = None  # 延迟初始化人脸检测器
        self._bg_video_cap = None   # 背景视频捕获器
        self._bg_images = []        # 背景图列表
        self._bg_idx = 0

        # 加载背景资源
        if background_path and os.path.exists(background_path):
            self._load_background(background_path)

    def _load_background(self, path: str) -> None:
        """加载背景图片或视频。"""
        if path.lower().endswith(('.mp4', '.avi', '.mov', '.webm')):
            # 视频背景
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                self._bg_video_cap = cap
                logger.info(f"背景视频加载: {path}")
                # 读取第一帧作为参考帧
                ret, frame = cap.read()
                if ret:
                    self.set_ref_frame(frame)
            else:
                logger.warning(f"无法打开背景视频: {path}")
        elif path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
            # 图片背景
            img = cv2.imread(path)
            if img is not None:
                self.set_ref_frame(img)
                logger.info(f"背景图片加载: {path}")
            else:
                logger.warning(f"无法读取背景图片: {path}")
        else:
            logger.warning(f"不支持的背景文件格式: {path}")

    def _get_face_detector(self):
        """延迟初始化人脸检测器。"""
        if self._face_detector is None:
            try:
                from src.video.face_detector import FaceDetector
                self._face_detector = FaceDetector(method="sfd")
            except ImportError:
                logger.warning("FaceDetector不可用，将使用默认人脸位置")
                self._face_detector = None
        return self._face_detector

    def auto_detect_face(self) -> bool:
        """
        自动检测参考帧中的人脸区域。
        成功返回True，失败时使用默认位置。
        """
        if self.ref_frame is None:
            return False

        detector = self._get_face_detector()
        if detector is None:
            return False

        bbox = detector.detect(self.ref_frame)
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            # 扩展人脸框边界以包含更多头部区域
            h_pad = int((y2 - y1) * 0.15)
            w_pad = int((x2 - x1) * 0.10)
            x1 = max(0, x1 - w_pad)
            y1 = max(0, y1 - h_pad)
            x2 = min(self.out_w, x2 + w_pad)
            y2 = min(self.out_h, y2 + h_pad)
            self.face_region = (x1, y1, x2, y2)
            logger.info(f"自动检测到人脸区域: ({x1},{y1})-({x2},{y2})")
            return True

        return False

    def set_face_region(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """手动设置人脸在全身帧中的区域坐标。"""
        self.face_region = (x1, y1, x2, y2)

    def set_ref_frame(self, frame: np.ndarray) -> None:
        """设置参考全身帧(数字人不说话时的一帧画面)。"""
        if frame is not None:
            self.ref_frame = cv2.resize(frame, (self.out_w, self.out_h))
            # 自动检测人脸位置
            if not self.face_region:
                self.auto_detect_face()

    def get_next_bg_frame(self) -> np.ndarray:
        """获取下一帧背景(视频模式)。"""
        if self._bg_video_cap and self._bg_video_cap.isOpened():
            ret, frame = self._bg_video_cap.read()
            if ret:
                return cv2.resize(frame, (self.out_w, self.out_h))
            # 视频结束，循环播放
            self._bg_video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._bg_video_cap.read()
            if ret:
                return cv2.resize(frame, (self.out_w, self.out_h))
        return self.ref_frame

    def _create_feather_mask(self, w: int, h: int, feather: int = 5) -> np.ndarray:
        """创建羽化遮罩，边缘从0渐变到1，避免粘贴痕迹。"""
        mask = np.ones((h, w), dtype=np.float32)
        if w > feather * 2:
            mask[:, :feather] = np.linspace(0, 1, feather)[None, :]
            mask[:, -feather:] = np.linspace(1, 0, feather)[None, :]
        if h > feather * 2:
            mask[:feather, :] *= np.linspace(0, 1, feather)[:, None]
            mask[-feather:, :] *= np.linspace(1, 0, feather)[:, None]
        return mask

    def paste_face(self, ref: np.ndarray, face: np.ndarray, pos: tuple) -> np.ndarray:
        """
        将唇形人脸以羽化方式粘贴到参考帧的指定位置。
        参数:
            ref: 参考全身帧 (H,W,3)
            face: 唇形同步人脸 (h,w,3)
            pos: (x1,y1,x2,y2) 目标位置
        返回: 合成帧
        """
        result = ref.copy()
        x1, y1, x2, y2 = pos
        fw, fh = x2 - x1, y2 - y1
        if fw <= 0 or fh <= 0:
            return result
        # 缩放人脸到目标区域
        face_rz = cv2.resize(face, (fw, fh))
        # 羽化混合遮罩
        mask = self._create_feather_mask(fw, fh)
        for c in range(3):
            result[y1:y2, x1:x2, c] = (
                face_rz[:, :, c].astype(np.float32) * mask +
                ref[y1:y2, x1:x2, c].astype(np.float32) * (1.0 - mask)
            )
        return result.astype(np.uint8)

    def composite(self, face_frames: list, silent: bool = False) -> list:
        """
        合成完整视频帧序列。
        参数:
            face_frames: Wav2Lip输出的人脸帧列表
            silent: 是否静音(True时使用背景帧而非说话帧)
        返回: 合成后的完整帧列表
        """
        if self.ref_frame is None:
            self.ref_frame = np.zeros((self.out_h, self.out_w, 3), dtype=np.uint8)
        if self.face_region is None:
            # 尝试自动检测人脸，失败则使用默认中央位置
            if not self.auto_detect_face():
                cx, cy = self.out_w // 2, self.out_h // 3
                half = self.face_size * 2
                self.face_region = (cx - half, cy - half, cx + half, cy + half)

        results = []
        for face in face_frames:
            if face.dtype == np.float32 or face.max() <= 1.0:
                face = (face * 255).clip(0, 255).astype(np.uint8)

            # 使用动态背景帧(视频模式)或静态参考帧
            bg = self.get_next_bg_frame() if self._bg_video_cap else self.ref_frame
            if bg is None:
                bg = self.ref_frame

            results.append(self.paste_face(bg, face, self.face_region))
        return results

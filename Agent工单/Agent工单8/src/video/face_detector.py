"""
src/video/face_detector.py - 人脸检测模块
功能: 检测视频帧中的人脸区域，提供人脸框用于后续的唇形合成粘贴。
      支持SFD人脸检测器和OpenCV DNN作为后备方案。
      对应工单需求: "支持全身视频拼接，生成完整的数字人形象"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


class FaceDetector:
    """
    人脸检测器，定位视频帧中的人脸区域。
    用于将Wav2Lip生成的唇形人脸粘贴回原始视频帧。

    对应工单: 唇形同步需要精确定位人脸区域。
    """

    def __init__(self, method: str = "sfd",
                 img_size: int = 96):
        """
        初始化人脸检测器。

        参数:
            method: 检测方法 ("sfd" 或 "opencv_dnn")
            img_size: 输出人脸尺寸(Wav2Lip需要96x96)
        """
        self.method = method
        self.img_size = img_size
        self._detector = None
        self._init_detector()

    def _init_detector(self):
        """初始化具体的人脸检测器实现。"""
        import os
        if self.method == "sfd":
            try:
                import face_alignment
                self._detector = face_alignment.FaceAlignment(
                    face_alignment.LandmarksType.TWO_D, device='cpu')
                logger.info("SFD人脸检测器加载完成")
                return
            except ImportError:
                logger.warning("face_alignment未安装，回退Haar")
                self.method = "haar"
        if self.method == "opencv_dnn":
            model_file = "models/opencv/face_detection_uint8.pb"
            config_file = "models/opencv/face_detection.pbtxt"
            if os.path.exists(model_file) and os.path.exists(config_file):
                self._detector = cv2.dnn.readNetFromTensorflow(model_file, config_file)
                logger.info("OpenCV DNN人脸检测器加载完成")
                return
            logger.warning("DNN模型不存在，回退Haar")
            self.method = "haar"
        # Haar 回退: 尝试多个路径
        cascade_paths = [
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
            os.path.join(os.path.dirname(cv2.__file__), "data",
                         "haarcascade_frontalface_default.xml"),
        ]
        for cp in cascade_paths:
            if os.path.exists(cp):
                self._detector = cv2.CascadeClassifier(cp)
                if self._detector.empty():
                    continue
                self.method = "haar"
                logger.info(f"Haar级联人脸检测器加载: {cp}")
                return
        logger.error("无法加载任何人脸检测器! 将跳过人脸检测")
        self._detector = None

    def detect(self, frame: np.ndarray):
        """
        检测帧中的人脸边界框。

        参数:
            frame: BGR视频帧，uint8，shape (H, W, 3)
        返回:
            (x1, y1, x2, y2) 人脸框坐标，未检测到时返回None
        """
        if self.method == "haar":
            return self._detect_haar(frame)
        elif self.method == "opencv_dnn":
            return self._detect_dnn(frame)
        elif self.method == "sfd":
            return self._detect_sfd(frame)
        else:
            return self._detect_haar(frame)

    def _detect_haar(self, frame: np.ndarray):
        """Haar级联分类器检测。"""
        if self._detector is None:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        return (x, y, x + w, y + h)

    def _detect_dnn(self, frame: np.ndarray):
        """OpenCV DNN SSD人脸检测。"""
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 117, 123])
        self._detector.setInput(blob)
        detections = self._detector.forward()
        # 找置信度最高的检测结果
        best_conf = 0.5  # 最小置信度阈值
        best_box = None
        for i in range(detections.shape[2]):
            conf = detections[0, 0, i, 2]
            if conf > best_conf:
                best_conf = conf
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                best_box = (x1, y1, x2, y2)
        return best_box

    def _detect_sfd(self, frame: np.ndarray):
        """SFD人脸检测(通过face_alignment库)。"""
        try:
            import face_alignment
            if self._detector is None:
                self._detector = face_alignment.FaceAlignment(
                    face_alignment.LandmarksType.TWO_D, device='cpu'
                )
            # 检测人脸关键点
            landmarks = self._detector.get_landmarks(frame)
            if landmarks is None:
                return None
            # 从关键点计算边界框
            pts = landmarks[0]  # (68, 2)
            x_min, y_min = pts.min(axis=0).astype(int)
            x_max, y_max = pts.max(axis=0).astype(int)
            return (x_min, y_min, x_max, y_max)
        except ImportError:
            logger.warning("face_alignment未安装，回退到Haar")
            self.method = "haar"
            return self._detect_haar(frame)

    def extract_face(self, frame: np.ndarray, bbox):
        """
        从帧中裁剪并缩放到固定尺寸的人脸。

        参数:
            frame: BGR帧
            bbox: (x1, y1, x2, y2) 边界框
        返回:
            缩放后的人脸图像，shape (img_size, img_size, 3)
        """
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        # 确保边界在帧内
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return np.zeros((self.img_size, self.img_size, 3), dtype=np.uint8)
        # 裁剪并缩放
        face = frame[y1:y2, x1:x2]
        face_resized = cv2.resize(face, (self.img_size, self.img_size))
        return face_resized

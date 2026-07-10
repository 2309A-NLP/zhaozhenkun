"""手势识别: YOLO11n + 分区帧差法 + 相对比例 + 帧率节流 + 微笑检测"""

import base64, logging, os, sys, time
from io import BytesIO
import cv2, numpy as np
from PIL import Image
from ultralytics import YOLO

import ultralytics.nn.tasks as _ut
_o = _ut.BaseModel.fuse
_ut.BaseModel.fuse = lambda s,*a,**kw: (_o(s,*a,**kw) if False else s)

logging.basicConfig(level=logging.INFO, format="[yolo] %(message)s", stream=sys.stdout)
logger = logging.getLogger("yolo")

_P = os.path.dirname(os.path.abspath(__file__))
for _ in range(3): _P = os.path.dirname(_P)
logger.info("加载模型...")
_DET = YOLO(os.path.join(_P, "yolo11n.pt"), verbose=False)
_DET.track(source=np.zeros((480,640,3),dtype=np.uint8), persist=True,
           tracker="bytetrack.yaml", conf=0.35, iou=0.45, classes=[0], verbose=False)
logger.info("就绪")


class YOLOBehaviorDetector:
    def __init__(self):
        self._prev_gray = None
        self._blocked = 0         # 触发后硬阻止帧数
        self._last_process = 0.0  # 上次处理时间戳(秒)
        self._min_interval = 0.4  # 最小处理间隔400ms (2.5 FPS)
        self._motion_history = [] # 近N帧的运动占比，用于微笑检测
        self._face_motion_boost = 0  # 上半区运动累积

    # 工单18：帧率节流 — 限制处理频率避免请求积压
    def should_process(self) -> bool:
        now = time.time()
        if now - self._last_process < self._min_interval:
            return False
        self._last_process = now
        return True

    def process_frame(self, bgr: np.ndarray) -> dict:
        t0 = time.time()
        h,w = bgr.shape[:2]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        det = _DET.track(source=bgr, persist=True, tracker="bytetrack.yaml",
                         conf=0.35, iou=0.45, classes=[0], verbose=False)

        m = {"L":0,"C":0,"R":0, "FACE":0}
        pc = 0
        has_person = det[0].boxes is not None and len(det[0].boxes) > 0

        if has_person:
            pc = len(det[0].boxes)
            box = det[0].boxes[0]
            x1,y1,x2,y2 = map(int, box.xyxy[0].tolist())
            ph,pw = y2-y1, x2-x1

            if self._prev_gray is not None:
                # 上半身手部区域 (L/C/R) — 用于挥手/指向/点赞
                for zn, (rx1,rx2) in [("L",(0,0.33)), ("C",(0.33,0.66)), ("R",(0.66,1.0))]:
                    zx1 = max(0, int(x1+rx1*pw)); zx2 = min(w, int(x1+rx2*pw))
                    zy1 = max(0, y1-int(ph*0.25)); zy2 = min(h, y1+int(ph*0.35))
                    if zx2>zx1 and zy2>zy1:
                        diff = cv2.absdiff(gray[zy1:zy2,zx1:zx2], self._prev_gray[zy1:zy2,zx1:zx2])
                        _, th = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                        m[zn] = np.count_nonzero(th)/th.size*100
                # 工单18：面部区域 (上部中央) — 用于微笑检测
                fx1 = max(0, int(x1+0.25*pw)); fx2 = min(w, int(x1+0.75*pw))
                fy1 = max(0, y1-int(ph*0.15)); fy2 = min(h, y1+int(ph*0.10))
                if fx2>fx1 and fy2>fy1:
                    fdiff = cv2.absdiff(gray[fy1:fy2,fx1:fx2], self._prev_gray[fy1:fy2,fx1:fx2])
                    _, fth = cv2.threshold(fdiff, 20, 255, cv2.THRESH_BINARY)
                    m["FACE"] = np.count_nonzero(fth)/fth.size*100

        self._prev_gray = gray
        if self._blocked > 0:
            self._blocked -= 1

        # ====== 工单18：手势分类 — 基于相对比例的鲁棒检测 ======
        L,C,R = m["L"], m["C"], m["R"]
        F = m["FACE"]
        total = L + C + R
        gesture = "unknown"
        confidence = 0.0

        if self._blocked == 0 and has_person and total > 2.0:
            # 计算各区域的运动占比（相对比例，而非绝对值）
            lr = L / total if total > 0 else 0
            cr = C / total if total > 0 else 0
            rr = R / total if total > 0 else 0

            # 工单18：指向 — 单侧运动占主导(>48%)，中区不占优(<38%)
            if (lr > 0.48 and cr < 0.38) or (rr > 0.48 and cr < 0.38):
                gesture = "point"
                confidence = round(max(lr, rr) * 1.3, 2)
            # 工单18：点赞 — 中央运动高度集中(>55%)，两侧都很弱(<25%)
            elif cr > 0.55 and lr < 0.25 and rr < 0.25:
                gesture = "thumbs_up"
                confidence = round(cr * 1.3, 2)
            # 工单18：微笑 — 面部区域有明显运动 + 手部整体运动不大(total<10)
            elif F > 1.5 and total < 10:
                gesture = "smile"
                confidence = round(min(0.90, F / 8), 2)
            # 工单18：挥手 — 运动分布较广，中央有运动且至少一侧有明显参与(>15%)
            elif cr > 0.18 and (lr > 0.15 or rr > 0.15):
                gesture = "wave"
                confidence = round(min(0.95, total / 25), 2)

        # 工单18：微笑加强 — 累积面部运动帧
        if F > 1.5 and not gesture == "smile":
            self._face_motion_boost += 1
        else:
            self._face_motion_boost = max(0, self._face_motion_boost - 0.5)
        # 连续多帧面部运动 + 手部无大动作 = 微笑
        if self._blocked == 0 and has_person and self._face_motion_boost >= 3 and gesture == "unknown" and total < 8:
            gesture = "smile"
            confidence = 0.75
            self._face_motion_boost = 0

        triggered = bool(gesture != "unknown")
        if triggered:
            # 工单18：缩短阻止时间 — 从50帧降到15帧 (~5秒)
            block_frames = 12 if gesture == "smile" else 15
            self._blocked = block_frames

        ms = round((time.time()-t0)*1000,1)
        tag = f"→→{gesture}" if triggered else ""
        logger.info("%d人 L=%d(%.0f%%) C=%d(%.0f%%) R=%d(%.0f%%) F=%d blk=%d %sms %s",
                    pc, L, (L/total*100) if total>0 else 0,
                    C, (C/total*100) if total>0 else 0,
                    R, (R/total*100) if total>0 else 0,
                    int(F), self._blocked, ms, tag)

        return {"detected":triggered, "behavior":gesture,
                "confidence":min(0.99, confidence) if triggered else 0.0,
                "source":"yolo", "persons":[], "time_ms":ms,
                "diag":[f"L={L:.0f}({lr*100 if total>0 else 0:.0f}%) C={C:.0f}({cr*100 if total>0 else 0:.0f}%) R={R:.0f}({rr*100 if total>0 else 0:.0f}%) F={F:.0f}"],
                "person_count":pc}

    def process_base64(self, b64: str) -> dict:
        if "," in b64 and b64.startswith("data:"):
            b64 = b64.split(",",1)[1]
        raw = base64.b64decode(b64)
        img = Image.open(BytesIO(raw))
        return self.process_frame(cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR))

_d = None
def get_detector():
    global _d
    if _d is None: _d = YOLOBehaviorDetector()
    return _d
def detect_from_frame(b64: str) -> dict:
    return get_detector().process_base64(b64)

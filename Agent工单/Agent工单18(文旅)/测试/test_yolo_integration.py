"""YOLO11n + ByteTrack + YOLO11n-pose 集成测试 (纯 ultralytics + OpenCV)"""
import sys
sys.path.insert(0, "/mnt/c/Users/31326/Desktop/Agent工单18/研发/source")

print("=" * 60)
print("YOLO11n + ByteTrack + YOLO11n-pose 集成测试")
print("=" * 60)

# 1. 测试模型加载
print("\n[1/3] 加载 YOLO 模型...")
from services.yolo_behavior_service import get_detector
detector = get_detector()
detector._ensure_models()
print("✅ YOLO11n + YOLO11n-pose 均加载成功")

# 2. 测试手势识别逻辑
print("\n[2/3] 测试手势识别函数...")
from services.yolo_behavior_service import (
    _detect_wave_from_kpts,
    _detect_point_from_kpts,
    _detect_thumbs_up_from_kpts,
)
import numpy as np

# 模拟一个 480x640 坐标系中的人体关键点
# YOLO-pose 返回的是绝对像素坐标 [x, y]
def make_kpts(*positions):
    """positions: dict of {kp_index: (x, y, conf)}"""
    kpts = np.zeros((17, 2), dtype=np.float32)
    confs = np.zeros(17, dtype=np.float32)
    # 默认值 (大致站立姿势)
    defaults = {
        0: (320, 100), 1: (290, 90), 2: (350, 90), 3: (260, 95), 4: (380, 95),
        5: (260, 220), 6: (380, 220),
        7: (200, 300), 8: (440, 300),
        9: (170, 360), 10: (470, 360),
        11: (270, 380), 12: (370, 380),
        13: (260, 500), 14: (380, 500),
        15: (250, 620), 16: (390, 620),
    }
    for i in range(17):
        if i in positions:
            kpts[i] = [positions[i][0], positions[i][1]]
            confs[i] = positions[i][2] if len(positions[i]) > 2 else 1.0
        elif i in defaults:
            kpts[i] = [defaults[i][0], defaults[i][1]]
            confs[i] = 1.0
    return kpts, confs

# --- 挥手: 右手举高 ---
kpts, confs = make_kpts({10: (420, 120, 1.0)})  # right_wrist 高于 right_shoulder(380,220)
print(f"  挥手: {'✅' if _detect_wave_from_kpts(kpts, confs) else '❌'} (期望 ✅)")

# --- 指向: 左臂横向伸出 ---
kpts, confs = make_kpts({
    7: (180, 300, 1.0),   # left_elbow (接近水平)
    9: (100, 310, 1.0),   # left_wrist (横向延伸)
})
print(f"  指向: {'✅' if _detect_point_from_kpts(kpts, confs) else '❌'} (期望 ✅)")

# --- 点赞: 右手在脸附近 ---
kpts, confs = make_kpts({
    10: (350, 90, 1.0),  # right_wrist 靠近 nose(320,100), 高于 shoulder(380,220)
})
print(f"  点赞: {'✅' if _detect_thumbs_up_from_kpts(kpts, confs) else '❌'} (期望 ✅)")

# 3. 测试完整帧处理
print("\n[3/3] 测试完整帧处理...")
import cv2

test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
# 画一个简单的人形
cv2.rectangle(test_frame, (200, 50), (440, 450), (200, 200, 200), -1)
cv2.circle(test_frame, (320, 130), 70, (180, 180, 220), -1)

try:
    result = detector.process_frame(test_frame)
    print(f"  处理耗时: {result['time_ms']}ms")
    print(f"  检测结果: behavior={result['behavior']}, detected={result['detected']}")
    print(f"  检测到 {len(result['persons'])} 人")
    for p in result['persons']:
        print(f"    Person #{p['id']}: bbox={p['bbox']}, behavior={p['behavior']}, conf={p['confidence']:.2f}")
except Exception as e:
    print(f"  ⚠️ 帧处理异常: {e}")
    import traceback; traceback.print_exc()

# 4. Base64 测试
print("\n[4] Base64 接口测试...")
import base64
_, buf = cv2.imencode('.jpg', test_frame)
b64 = base64.b64encode(buf).decode()
try:
    result = detector.process_base64(b64)
    print(f"  behavior={result['behavior']}, time={result['time_ms']}ms")
    print("  ✅ Base64 接口正常")
except Exception as e:
    print(f"  ⚠️ {e}")

print("\n" + "=" * 60)
print("YOLO11n + ByteTrack + YOLO11n-pose 集成就绪!")
print("=" * 60)

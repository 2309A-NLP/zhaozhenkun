"""工单18：实时视觉辅助服务，负责基于前端关键点数据识别挥手、点赞、指向和微笑。"""
MIN_VISIBILITY = 0.1

# 工单18：安全读取关键点坐标，避免前端缺字段时直接报错。
def point(data: dict, name: str) -> dict:
    # 工单18：从关键点字典中取指定点位，不存在就返回默认坐标。
    return data.get(name, {"x": 0.0, "y": 0.0, "visibility": 0.0})

# 工单18：判断单个关键点是否足够可靠。
def visible(item: dict) -> bool:
    # 工单18：根据visibility阈值判断当前关键点能否参与识别。
    return item.get("visibility", 0.0) >= MIN_VISIBILITY

# 工单18：检测挥手动作，放宽为手腕接近或高于肩膀并有明显外展即可。
def detect_wave(pose: dict) -> bool:
    left_wrist, right_wrist = point(pose, "left_wrist"), point(pose, "right_wrist")
    left_shoulder, right_shoulder = point(pose, "left_shoulder"), point(pose, "right_shoulder")
    left_wave = visible(left_wrist) and visible(left_shoulder) and left_wrist["y"] < left_shoulder["y"] + 0.15 and abs(left_wrist["x"] - left_shoulder["x"]) > 0.03
    right_wave = visible(right_wrist) and visible(right_shoulder) and right_wrist["y"] < right_shoulder["y"] + 0.15 and abs(right_wrist["x"] - right_shoulder["x"]) > 0.03
    return left_wave or right_wave

# 工单18：检测指向动作，手臂与肩膀高度接近且横向跨度明显时判定。
def detect_pointing(pose: dict) -> bool:
    left_wrist, right_wrist = point(pose, "left_wrist"), point(pose, "right_wrist")
    left_shoulder, right_shoulder = point(pose, "left_shoulder"), point(pose, "right_shoulder")
    left_point = visible(left_wrist) and visible(left_shoulder) and abs(left_wrist["y"] - left_shoulder["y"]) < 0.25 and abs(left_wrist["x"] - left_shoulder["x"]) > 0.08
    right_point = visible(right_wrist) and visible(right_shoulder) and abs(right_wrist["y"] - right_shoulder["y"]) < 0.25 and abs(right_wrist["x"] - right_shoulder["x"]) > 0.08
    return left_point or right_point

# 工单18：检测点赞动作，当前采用手部手势标签优先判定。
def detect_thumbs_up(hands: list) -> bool:
    return any((hand.get("gesture") or "").lower() == "thumbs_up" for hand in hands)

# 工单18：检测微笑表情，依据嘴角宽度和嘴部纵向开合比近似判断。
def detect_smile(face: dict) -> bool:
    left_corner, right_corner = point(face, "mouth_left"), point(face, "mouth_right")
    upper_lip, lower_lip = point(face, "lip_top"), point(face, "lip_bottom")
    if not (visible(left_corner) and visible(right_corner) and visible(upper_lip) and visible(lower_lip)):
        return False
    mouth_width = abs(right_corner["x"] - left_corner["x"])
    mouth_open = abs(lower_lip["y"] - upper_lip["y"])
    return mouth_width > 0.06 and mouth_open < 0.06

# 工单18：对一帧关键点结果做综合行为识别。
def detect_behavior(payload: dict) -> dict:
    pose = payload.get("pose", {})
    hands = payload.get("hands", [])
    face = payload.get("face", {})
    if detect_thumbs_up(hands):
        return {"behavior": "thumbs_up", "confidence": 0.92, "source": "hand_gesture"}
    if detect_wave(pose):
        return {"behavior": "wave", "confidence": 0.88, "source": "pose_landmarks"}
    if detect_pointing(pose):
        return {"behavior": "point", "confidence": 0.85, "source": "pose_landmarks"}
    if detect_smile(face):
        return {"behavior": "smile", "confidence": 0.8, "source": "face_landmarks"}
    return {"behavior": "unknown", "confidence": 0.0, "source": "none"}

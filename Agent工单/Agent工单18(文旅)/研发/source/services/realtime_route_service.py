"""工单18：实时识别路由辅助模块，负责把实时摄像头识别结果转成自动互动回复。"""
# 工单18：导入实时视觉识别服务，用于解析前端上传的关键点结果。
from services.realtime_vision_service import detect_behavior
# 工单18：导入导览编排服务，用于把识别结果自动转成数字人回复。
from services.guide_service import handle_behavior_chat

# 工单18：处理实时摄像头识别请求，并在识别成功后自动生成导览互动结果。
def handle_realtime_behavior(settings: dict, payload: dict, language: str, messages: list) -> dict:
    # 工单18：先从关键点数据中识别当前最可能的行为。
    behavior_result = detect_behavior(payload)
    # 工单18：如果没有识别到明确动作，就返回轻量结果，不触发大模型。
    if behavior_result["behavior"] == "unknown":
        return {
            "detected": False,
            "behavior": "unknown",
            "confidence": behavior_result["confidence"],
            "source": behavior_result["source"],
            "subtitle": "暂未识别到明确动作，请继续保持在镜头前。",
            "answer": "暂未识别到明确动作，请继续保持在镜头前。",
            "references": [],
            "reference_text": "",
        }
    # 工单18：识别成功时，复用行为互动主链路生成数字人反馈。
    guide_result = handle_behavior_chat(settings, behavior_result["behavior"], language, messages)
    # 工单18：把识别结果元信息合并回最终返回体。
    guide_result.update({"detected": True, "confidence": behavior_result["confidence"], "source": behavior_result["source"]})
    # 工单18：返回完整结果给前端。
    return guide_result

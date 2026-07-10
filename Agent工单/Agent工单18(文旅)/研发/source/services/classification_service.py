"""工单18：图像分类服务 — ResNet/CLIP/YOLO 多模型文旅图像分类"""
import logging
import io
from PIL import Image
import numpy as np

logger = logging.getLogger("classification")

# 工单18：文旅场景分类标签（PDF要求：文物、动植物、建筑等）
CULTURAL_CATEGORIES = {
    "relic": {"cn": "文物", "desc": "历史文物、古董、展品"},
    "building": {"cn": "古建筑", "desc": "古城楼、寺庙、塔、传统建筑"},
    "plant": {"cn": "植物花卉", "desc": "花草树木、园林植物"},
    "board": {"cn": "展板指示牌", "desc": "文字展板、路牌、说明牌"},
    "inscription": {"cn": "碑文石刻", "desc": "石碑、刻字、铭文"},
    "landscape": {"cn": "自然风景", "desc": "山水、园林全景"},
    "animal": {"cn": "动物", "desc": "景区动物、鸟类"},
    "other": {"cn": "其他", "desc": "通用分类"},
}

# 工单18：YOLO11n 图像分类（基于预训练 ImageNet 标签映射到文旅类别）
_YOLO_CLASSIFIER = None

def _get_yolo_classifier():
    global _YOLO_CLASSIFIER
    if _YOLO_CLASSIFIER is None:
        from ultralytics import YOLO
        import os
        _P = os.path.dirname(os.path.abspath(__file__))
        for _ in range(3):
            _P = os.path.dirname(_P)
        _YOLO_CLASSIFIER = YOLO(os.path.join(_P, "yolo11n.pt"), verbose=False)
    return _YOLO_CLASSIFIER

# 工单18：YOLO标签→文旅类别映射（ImageNet-1k → 文旅场景）
IMAGENET_TO_CULTURAL = {
    "vase": "relic", "pottery": "relic", "plate": "relic", "cup": "relic",
    "temple": "building", "palace": "building", "castle": "building", "church": "building",
    "dome": "building", "mosque": "building", "altar": "building", "monastery": "building",
    "tree": "plant", "flower": "plant", "pot": "plant", "herb": "plant",
    "sign": "board", "board": "board", "screen": "board", "menu": "board",
    "stone": "inscription", "rock": "inscription", "monument": "inscription",
    "landscape": "landscape", "mountain": "landscape", "valley": "landscape",
    "bird": "animal", "animal": "animal", "insect": "animal", "fish": "animal",
}

def classify_with_yolo(image_bytes: bytes) -> dict:
    """YOLOv8 图像分类 — 识别图片中的文旅相关对象"""
    try:
        model = _get_yolo_classifier()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = model(img, verbose=False)

        if results and len(results) > 0 and results[0].probs is not None:
            probs = results[0].probs
            top5_idx = probs.top5
            top5_conf = probs.top5conf

            # 工单18：映射到文旅类别
            for i, idx in enumerate(top5_idx):
                label = model.names[int(idx)].lower()
                for key, cultural_cat in IMAGENET_TO_CULTURAL.items():
                    if key in label:
                        return {
                            "category": CULTURAL_CATEGORIES[cultural_cat]["cn"],
                            "category_key": cultural_cat,
                            "confidence": round(float(top5_conf[i]), 3),
                            "raw_label": label,
                        }

            # 工单18：无文旅匹配时返回通用top-1
            top_label = model.names[int(top5_idx[0])]
            return {
                "category": "其他",
                "category_key": "other",
                "confidence": round(float(top5_conf[0]), 3),
                "raw_label": top_label,
            }
    except Exception as e:
        logger.warning("YOLO分类失败: %s", e)

    return {"category": "未知", "category_key": "other", "confidence": 0, "raw_label": ""}


def classify_image(image_bytes: bytes) -> dict:
    """工单18：统一图像分类入口 — YOLO + CLIP 双模型融合"""
    # 先用YOLO快速分类
    yolo_result = classify_with_yolo(image_bytes)

    # 工单18：如果YOLO置信度低(<0.3)，尝试CLIP零样本分类
    if yolo_result["confidence"] < 0.3:
        try:
            from services.vector_rag_service import clip_zero_shot_classify
            clip_result = clip_zero_shot_classify(
                image_bytes,
                categories=["文物", "古建筑", "自然植物", "展板文字", "碑文石刻", "风景", "动物"]
            )
            if clip_result["confidence"] > yolo_result["confidence"]:
                return {
                    "category": clip_result["category"],
                    "category_key": "clip",
                    "confidence": clip_result["confidence"],
                    "raw_label": "CLIP零样本",
                    "all_scores": clip_result.get("all_scores", {}),
                }
        except Exception as e:
            logger.warning("CLIP分类降级失败: %s", e)

    return yolo_result

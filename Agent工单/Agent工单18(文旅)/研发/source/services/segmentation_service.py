"""工单18：图像分割服务 — OpenCV传统分割+FastSAM(可选)，分离感兴趣区域"""
import logging
import io
import numpy as np
from PIL import Image

logger = logging.getLogger("segmentation")

def _opencv_segment(image_bytes: bytes) -> dict:
    """工单18：OpenCV传统图像分割 — GrabCut + 轮廓检测，无需下载模型"""
    import cv2

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_np = np.array(img)
    h, w = img_np.shape[:2]
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    segments = []

    # 工单18：方法1 — 自适应阈值二值化 + 轮廓检测 (识别展板、碑文等)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 31, 11)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 工单18：方法2 — GrabCut 前景分割 (识别主体对象)
    rect = (int(w*0.1), int(h*0.1), int(w*0.8), int(h*0.8))
    mask = np.zeros(gray.shape, np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(img_np, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
        fg_mask = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
        fg_ratio = np.count_nonzero(fg_mask) / fg_mask.size * 100
        if fg_ratio > 5:
            segments.append({
                "id": 0, "area_pct": round(fg_ratio, 1),
                "type": "前景主体(GrabCut)",
                "bbox": {"x1": rect[0], "y1": rect[1], "x2": rect[0]+rect[2], "y2": rect[1]+rect[3]},
            })
    except Exception:
        pass

    # 工单18：方法3 — 显著轮廓区域
    min_area = w * h * 0.02  # 至少占2%面积
    for i, cnt in enumerate(contours[:15]):
        area = cv2.contourArea(cnt)
        if area > min_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            segments.append({
                "id": len(segments),
                "area_pct": round(area / (w*h) * 100, 1),
                "type": "轮廓区域",
                "bbox": {"x1": int(x), "y1": int(y), "x2": int(x+bw), "y2": int(y+bh)},
            })

    # 工单18：去重合并重叠区域
    segments = _merge_overlapping(segments)

    main_objects = sum(1 for s in segments if s["area_pct"] > 10)
    if segments:
        summary = f"检测到{len(segments)}个对象区域，{main_objects}个主要对象（OpenCV传统分割）"
    else:
        summary = "图像中未检测到显著对象区域"

    return {"segments": segments[:10], "segment_count": len(segments),
            "main_objects": main_objects, "summary": summary, "method": "opencv"}


def _merge_overlapping(segments: list) -> list:
    """合并重叠度过高的分割区域"""
    if len(segments) <= 1:
        return segments
    merged = []
    used = set()
    for i, s1 in enumerate(segments):
        if i in used:
            continue
        for j, s2 in enumerate(segments):
            if j <= i or j in used:
                continue
            b1, b2 = s1["bbox"], s2["bbox"]
            # 计算IoU
            ix1 = max(b1["x1"], b2["x1"]); iy1 = max(b1["y1"], b2["y1"])
            ix2 = min(b1["x2"], b2["x2"]); iy2 = min(b1["y2"], b2["y2"])
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2-ix1) * (iy2-iy1)
                area1 = (b1["x2"]-b1["x1"]) * (b1["y2"]-b1["y1"])
                area2 = (b2["x2"]-b2["x1"]) * (b2["y2"]-b2["y1"])
                iou = inter / min(area1, area2) if min(area1, area2) > 0 else 0
                if iou > 0.5:  # 重叠>50%，合并
                    s1["bbox"] = {
                        "x1": min(b1["x1"], b2["x1"]), "y1": min(b1["y1"], b2["y1"]),
                        "x2": max(b1["x2"], b2["x2"]), "y2": max(b1["y2"], b2["y2"]),
                    }
                    s1["area_pct"] = round(s1["area_pct"] + s2["area_pct"], 1)
                    used.add(j)
        merged.append(s1)
    return merged


def segment_image(image_bytes: bytes) -> dict:
    """工单18：统一图像分割入口 — 优先FastSAM，降级OpenCV"""
    # 先尝试FastSAM（需要下载模型，国内可能慢）
    try:
        from ultralytics import FastSAM
        model = FastSAM("FastSAM-s.pt")
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = model(img, device="cpu", imgsz=640, conf=0.25, iou=0.7, verbose=False)
        if results and len(results) > 0 and results[0].masks is not None:
            masks = results[0].masks
            segments = []
            img_np = np.array(img)
            for i in range(min(len(masks), 10)):
                mask = masks[i].data[0].cpu().numpy()
                bin_mask = (mask > 0.5)
                area_pct = bin_mask.sum() / bin_mask.size * 100
                ys, xs = np.where(bin_mask)
                if len(ys) > 0:
                    segments.append({
                        "id": i, "area_pct": round(area_pct, 1),
                        "type": "FastSAM",
                        "bbox": {"x1": int(xs.min()), "y1": int(ys.min()),
                                 "x2": int(xs.max()), "y2": int(ys.max())},
                    })
            if segments:
                main = sum(1 for s in segments if s["area_pct"] > 10)
                return {"segments": segments, "segment_count": len(segments),
                        "main_objects": main, "summary": f"FastSAM检测到{len(segments)}个对象",
                        "method": "fastsam"}
    except Exception as e:
        logger.info("FastSAM不可用，降级OpenCV: %s", e)

    # 降级：OpenCV传统分割（无需下载任何模型）
    return _opencv_segment(image_bytes)


def segment_and_highlight(image_bytes: bytes) -> dict:
    """工单18：分割+生成高亮结果"""
    seg = segment_image(image_bytes)
    hints = []
    for s in seg.get("segments", [])[:5]:
        if s["area_pct"] > 5:
            bx1, bx2 = s["bbox"]["x1"], s["bbox"]["x2"]
            pos = "中央" if 0.3 < (bx1+bx2)/2 < 0.7 else "侧边"
            hints.append(f"{pos}区域有{s['area_pct']}%占比的{s.get('type','对象')}")
    seg["content_hints"] = hints
    return seg

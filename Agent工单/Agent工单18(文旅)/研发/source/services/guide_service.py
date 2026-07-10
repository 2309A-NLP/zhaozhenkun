"""工单18：导览编排服务，负责组合向量RAG、图像分类、分割、OCR、视频分析与大模型生成最终回复。"""
from services.knowledge_service import search_spots, load_spots
from services.vector_rag_service import vector_search, image_vector_search
from services.llm_service import build_history_text, generate_answer
from services.ocr_service import extract_text_from_image
from services.vision_service import describe_image_in_detail
from services.behavior_service import analyze_behavior
from services.prompt_service import build_system_prompt, normalize_subtitle
from services.common_service import format_references, guess_mime_type, validate_image_bytes
from services.audio_service import synthesize_speech
from services.video_service import analyze_video
from services.classification_service import classify_image
from services.segmentation_service import segment_image

def build_knowledge_text(items: list) -> str:
    if not items:
        return ""
    lines = []
    for item in items:
        name = item.get("name", "")
        category = item.get("category", "")
        content = item.get("content", item.get("summary", ""))
        details = item.get("details", "")
        lines.append(f"景点：{name}｜类别：{category}｜内容：{content}｜详情：{details}")
    return "\n".join(lines)

def build_route_tip(items: list) -> str:
    names = [item.get("name", "") for item in items[:3] if item.get("name")]
    if not names:
        return "建议先从主入口区域开始，再根据兴趣选择文化展陈或自然景观路线。"
    return f"可参考路线：{' → '.join(names)}。"

def build_result(answer: str, references: list, extra: dict | None = None) -> dict:
    result = {"answer": answer, "subtitle": normalize_subtitle(answer), "references": references, "reference_text": format_references(references)}
    result.update(synthesize_speech(answer))
    if extra:
        result.update(extra)
    return result

def handle_text_chat(settings: dict, question: str, language: str, messages: list) -> dict:
    # 工单18：优先使用向量语义检索（工单17 RAG对接），降级为关键词检索
    vector_spots = vector_search(question, top_k=5)
    if vector_spots:
        spots = vector_spots
        knowledge_text = build_knowledge_text(spots)
    else:
        spots = search_spots(question)
        knowledge_text = build_knowledge_text([{"name": s["name"], "category": s["category"], "summary": s["summary"], "details": s["details"]} for s in spots])

    history_text = build_history_text(messages)
    system_prompt = build_system_prompt(language, "文本导览问答")
    route_tip = build_route_tip(spots)
    answer = generate_answer(settings, system_prompt, f"游客问题：{question}\n会话上下文：{history_text}\n知识库：{knowledge_text}\n路线建议：{route_tip}")
    refs = [item.get("name", item.get("name", "")) for item in spots]
    return build_result(answer, refs, {"route_tip": route_tip})

def handle_image_chat(settings: dict, question: str, language: str, messages: list, image_bytes: bytes) -> dict:
    error = validate_image_bytes(image_bytes)
    if error:
        return build_result(f"图片处理失败：{error}", [], {"image_summary": "", "ocr_text": ""})

    mime_type = guess_mime_type(image_bytes)

    # 工单18：图像分类 — 识别文物/建筑/植物等类别（PDF要求ResNet/CLIP）
    classification = classify_image(image_bytes)
    image_category = classification.get("category", "未知")

    # 工单18：图像分割 — 分离感兴趣对象（PDF要求SAM/Mask R-CNN）
    segmentation = segment_image(image_bytes)

    # 工单18：多模态视觉理解
    image_summary = describe_image_in_detail(settings, image_bytes, mime_type)

    # 工单18：OCR文字提取（PDF要求PaddleOCR）
    ocr_text = extract_text_from_image(image_bytes)

    # 工单18：向量语义检索（工单17 RAG对接）→ 降级关键词
    vector_spots = image_vector_search(image_summary, ocr_text, top_k=5)
    if vector_spots:
        spots = vector_spots
    else:
        spots = search_spots(" ".join([question or "", image_summary or "", ocr_text or ""]))

    knowledge_text = build_knowledge_text(spots)
    history_text = build_history_text(messages)
    system_prompt = build_system_prompt(language, "图片识别讲解")
    route_tip = build_route_tip(spots)

    # 工单18：构建完整上下文 → 分类+分割+摘要+OCR+知识库
    context_parts = [f"图片分类：{image_category}"]
    if segmentation.get("summary"):
        context_parts.append(f"分割结果：{segmentation['summary']}")
    if image_summary:
        context_parts.append(f"图片内容：{image_summary}")
    if ocr_text:
        context_parts.append(f"OCR文字：{ocr_text}")
    if knowledge_text:
        context_parts.append(f"相关知识：{knowledge_text}")

    prompt = f"游客补充问题：{question}\n会话上下文：{history_text}\n" + "\n".join(context_parts) + f"\n路线建议：{route_tip}\n请先说明图片里看到了什么（类别是{image_category}），再解释文化或景点信息。"

    answer = generate_answer(settings, system_prompt, prompt)
    refs = [item.get("name", "") for item in spots]
    return build_result(answer, refs, {
        "image_summary": image_summary,
        "ocr_text": ocr_text,
        "route_tip": route_tip,
        "image_category": image_category,
        "segmentation_summary": segmentation.get("summary", ""),
        "classification": classification,
    })

def handle_video_chat(settings: dict, question: str, language: str, messages: list, video_bytes: bytes, suffix: str) -> dict:
    video_result = analyze_video(settings, video_bytes, suffix)
    # 工单18：向量检索优先
    vector_spots = image_vector_search(video_result["frame_summary"], video_result["ocr_text"], top_k=5)
    if vector_spots:
        spots = vector_spots
    else:
        spots = search_spots(" ".join([question or "", video_result["frame_summary"], video_result["ocr_text"]]))
    knowledge_text = build_knowledge_text(spots)
    history_text = build_history_text(messages)
    route_tip = build_route_tip(spots)
    system_prompt = build_system_prompt(language, "视频内容讲解")
    prompt = f"游客问题：{question}\n会话上下文：{history_text}\n关键帧摘要：{video_result['frame_summary']}\n关键帧OCR：{video_result['ocr_text']}\n知识库：{knowledge_text}\n路线建议：{route_tip}\n请把这段视频理解成游客拍到的场景，先概括画面，再给导览讲解。"
    answer = generate_answer(settings, system_prompt, prompt)
    refs = [item.get("name", "") for item in spots]
    return build_result(answer, refs, {"video_summary": video_result["frame_summary"], "ocr_text": video_result["ocr_text"], "route_tip": route_tip})

def handle_behavior_chat(settings: dict, behavior: str, language: str, messages: list) -> dict:
    behavior_result = analyze_behavior(behavior)
    # 工单18：向量检索优先
    vector_spots = vector_search(behavior_result["summary"], top_k=5)
    if vector_spots:
        spots = vector_spots
    else:
        spots = search_spots(behavior_result["summary"])
    knowledge_text = build_knowledge_text(spots)
    history_text = build_history_text(messages)
    route_tip = build_route_tip(spots)
    system_prompt = build_system_prompt(language, "行为互动")
    prompt = f"会话上下文：{history_text}\n游客行为：{behavior_result['behavior']}\n行为说明：{behavior_result['summary']}\n知识库：{knowledge_text}\n路线建议：{route_tip}"
    answer = generate_answer(settings, system_prompt, prompt)
    refs = [item.get("name", "") for item in spots]
    return build_result(answer, refs, {"behavior": behavior_result["behavior"], "behavior_summary": behavior_result["summary"], "route_tip": route_tip})

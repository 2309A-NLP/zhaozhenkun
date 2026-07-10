"""工单18：图片理解服务，负责调用千问多模态接口分析游客上传图片。"""
import base64
import requests

# 工单18：把图片字节编码成data URL，供多模态模型读取。
def build_data_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

# 工单18：从千问返回结构中提取文本内容，兼容字符串和分片数组。
def parse_vision_content(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""

# 工单18：构造千问多模态请求体。
def build_payload(settings: dict, prompt: str, image_bytes: bytes, mime_type: str) -> dict:
    return {"model": settings["QWEN_MODEL"], "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": build_data_url(image_bytes, mime_type)}}]}]}

# 工单18：调用千问多模态模型提取图片内容摘要。
def describe_image(settings: dict, image_bytes: bytes, prompt: str, mime_type: str = "image/jpeg") -> str:
    if not settings.get("QWEN_API_KEY"):
        return "未配置千问多模态密钥，当前返回本地图片讲解占位结果。"
    url = settings["QWEN_BASE_URL"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings['QWEN_API_KEY']}", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=build_payload(settings, prompt, image_bytes, mime_type), timeout=45)
    response.raise_for_status()
    return parse_vision_content(response.json()["choices"][0]["message"])

# 工单18：用视觉提示词提取更结构化的图片信息，补强图片讲解质量。
def describe_image_in_detail(settings: dict, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    prompt = "请识别这张图片中的主体对象、类别、文字线索、场景环境、可能的文化或旅游相关信息，按自然语言简洁描述。"
    return describe_image(settings, image_bytes, prompt, mime_type)

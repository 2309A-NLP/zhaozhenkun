"""工单18：通用辅助服务，负责图片类型识别、文件限制和公共格式化逻辑。"""
# 工单18：导入标准库模块，用于根据文件头判断常见图片格式。
import struct

# 工单18：定义允许的图片类型集合，避免上传明显不合规文件。
ALLOWED_IMAGE_TYPES = {"jpeg", "png", "gif", "bmp", "webp"}
# 工单18：定义单张图片最大字节数，避免超大文件拖慢演示服务。
MAX_IMAGE_SIZE = 8 * 1024 * 1024

# 工单18：根据图片字节头部判断图片类型，兼容Python 3.13 去掉 imghdr 的情况。
def detect_image_type(image_bytes: bytes) -> str:
    # 工单18：如果字节为空，直接返回空字符串。
    if not image_bytes:
        return ""
    # 工单18：JPEG 文件头以 FF D8 开始。
    if image_bytes.startswith(b"\xff\xd8"):
        return "jpeg"
    # 工单18：PNG 文件头固定为 89 50 4E 47。
    if image_bytes.startswith(b"\x89PNG"):
        return "png"
    # 工单18：GIF 文件头通常是 GIF87a 或 GIF89a。
    if image_bytes[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif"
    # 工单18：BMP 文件头以 BM 开始。
    if image_bytes.startswith(b"BM"):
        return "bmp"
    # 工单18：WebP 文件头包含 RIFF 和 WEBP 标记。
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    # 工单18：无法识别时返回空字符串。
    return ""

# 工单18：根据图片字节猜测MIME类型，给多模态接口使用。
def guess_mime_type(image_bytes: bytes) -> str:
    # 工单18：识别图片类型，不识别时默认jpeg。
    image_type = detect_image_type(image_bytes) or "jpeg"
    # 工单18：返回标准MIME字符串。
    return f"image/{image_type}"

# 工单18：校验图片大小与格式，发现问题时返回错误信息。
def validate_image_bytes(image_bytes: bytes) -> str:
    # 工单18：如果图片为空，直接给出错误说明。
    if not image_bytes:
        return "图片内容为空"
    # 工单18：如果图片过大，提示用户换小一点的文件。
    if len(image_bytes) > MAX_IMAGE_SIZE:
        return "图片大小超过8MB限制"
    # 工单18：识别图片格式，过滤明显不支持的类型。
    image_type = detect_image_type(image_bytes)
    # 工单18：如果识别结果不在允许范围，给出格式错误提示。
    if image_type and image_type not in ALLOWED_IMAGE_TYPES:
        return f"暂不支持的图片类型：{image_type}"
    # 工单18：无错误时返回空字符串。
    return ""

# 工单18：把参考景点数组格式化为便于前端展示的字符串。
def format_references(items: list) -> str:
    # 工单18：去重并保留原有顺序，让展示更整洁。
    unique_items = list(dict.fromkeys(item for item in items if item))
    # 工单18：使用中文顿号拼接，符合导览文案习惯。
    return "、".join(unique_items)

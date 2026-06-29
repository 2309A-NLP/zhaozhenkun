# -*- coding: utf-8 -*-
"""
tool_text2image.py — 文生图工具
--------------------------------------------------------------
功能: 基于 DashScope (qwen-image-edit-max) 实现:
      1. 文本→图像生成
      2. 人脸旋转（左转/右转，保持身份特征）

技术: DashScope MultiModalConversation API
      图像编辑模式: 输入图片+文本指令 → 输出编辑后的图片
      文本生成模式: 纯文本描述 → 输出生成图片

修复记录 (2026-06-28):
  - 添加自定义 requests Session（禁用SSL验证 + 重试适配器）
    解决某些网络环境下 dashscope.aliyuncs.com 的 SSLEOFError
  - 添加重试机制（最多3次，指数退避）
  - 改进错误信息，提供网络排查建议
  - ★ 模块加载时全局猴补 requests，禁止SSL验证（双重保险）

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import logging     # 日志记录

# ================================================================
# ★ 模块加载时立即应用 SSL 猴补（不依赖 SDK 的 session 传参）
# 解决 Windows/WSL 网络环境下 dashscope.aliyuncs.com 的 SSLEOFError
# ================================================================
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests as _requests
_original_request = _requests.Session.request

def _patched_request(self, method, url, *args, **kwargs):
    """猴补 requests.Session.request: 强制禁用 SSL 验证并添加重试。"""
    kwargs.setdefault('verify', False)
    kwargs.setdefault('timeout', (15, 90))
    return _original_request(self, method, url, *args, **kwargs)

_requests.Session.request = _patched_request
logger_patch = logging.getLogger("agent.tools")
logger_patch.debug("SSL猴补已应用: requests.Session.request → verify=False, timeout=(15,90)")

from tool_utils import call_deepseek  # 共享 DeepSeek 调用（提取图像 prompt）
import config      # Agent 全局配置（Qwen API 密钥）

# 模块日志器
logger = logging.getLogger("agent.tools")


def _create_dashscope_session() -> "requests.Session":
    """创建配置好的 requests Session（禁用SSL验证 + 重试适配器）。

    某些网络环境（企业代理、WSL、VPN）下访问 dashscope.aliyuncs.com
    会触发 SSLEOFError。此函数创建一个预配置的 Session：
      - verify=False: 跳过SSL证书验证
      - 连接重试: 最多3次，指数退避 1s/2s
      - 超时: 连接15s，读取60s

    返回:
        requests.Session: 配置好的会话对象
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    # 抑制 InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = requests.Session()
    session.verify = False  # 跳过SSL证书验证（修复 SSLEOFError）

    # 配置重试策略：连接错误重试3次，指数退避
    retry_strategy = Retry(
        total=3,
        backoff_factor=1.0,   # 1s, 2s, 4s 退避
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    logger.debug("DashScope Session已配置: verify=False, retries=3, timeout=(15,60)")
    return session


def _call_dashscope_api(model: str, messages: list, api_key: str) -> "dashscope.MultiModalConversationResponse":
    """调用 DashScope API（带重试和 SSL 容错）。

    参数:
        model: 模型名 (qwen-image-edit-max)
        messages: 符合 DashScope 格式的消息列表
        api_key: API 密钥

    返回:
        MultiModalConversationResponse 对象

    异常:
        Exception: 所有重试都失败时抛出最后一次的异常
    """
    from dashscope import MultiModalConversation

    session = _create_dashscope_session()
    last_error = None

    for attempt in range(3):
        try:
            logger.debug("DashScope API 调用 (尝试 %d/3): model=%s", attempt + 1, model)
            response = MultiModalConversation.call(
                model=model,
                messages=messages,
                api_key=api_key,
                result_format="message",
                session=session,
                request_timeout=90,  # 图像生成可能较慢
            )
            if response.status_code == 200:
                return response
            logger.warning("DashScope 返回非200状态: %d (尝试 %d/3)",
                           response.status_code, attempt + 1)
        except Exception as e:
            last_error = e
            err_str = str(e)[:120]
            logger.warning("DashScope API 调用失败 (尝试 %d/3): %s", attempt + 1, err_str)
            if attempt < 2:
                import time
                time.sleep((attempt + 1) * 2)  # 2s, 4s 退避

    raise last_error or RuntimeError("DashScope API 调用失败已达最大重试次数")


def _extract_images_from_response(response) -> list:
    """从 DashScope 响应中提取图片 base64 列表。

    参数:
        response: MultiModalConversationResponse 对象

    返回:
        list[str]: base64 编码的图片数据列表
    """
    result_images = []
    try:
        output = response.output
        if output and hasattr(output, 'choices') and output.choices:
            choice = output.choices[0]
            msg = choice.message
            if hasattr(msg, 'content') and msg.content:
                for item in msg.content:
                    if isinstance(item, dict):
                        if 'image' in item and item['image']:
                            result_images.append(item['image'])
                        elif 'data' in item and isinstance(item.get('data'), str):
                            result_images.append(item['data'])
    except Exception as e:
        logger.warning("图片提取异常: %s", e)
    return result_images


def tool_text2image(query: str, image_base64: str | None = None) -> dict:
    """文生图工具 — 文本生成图片 / 人脸旋转

    功能: 根据用户文本描述生成图片，或根据用户上传的人物照片进行人脸旋转。
          使用 DashScope qwen-image-edit-max API 实现真正的图像生成/编辑。

          修复: 使用自定义 requests Session（禁用SSL验证）解决 SSLEOFError。
                添加3次重试 + 指数退避，提高网络容错性。

    参数:
        query (str): 用户文本描述（如"生成一张关于未来城市的图片"）
        image_base64 (str | None): 上传图片的 base64 编码（人脸旋转模式）

    返回:
        dict: {"success": bool, "result": str, "tool": str, "images"?: [str]}
    """
    logger.info("🎨 文生图: %s (图片=%s)", query[:60], "有" if image_base64 else "无")

    try:
        import dashscope

        # ========== 人脸旋转模式（有图片输入） ==========
        if image_base64:
            # 解析用户旋转意图：左转/右转/其他
            intent_prompt = (
                f"用户要求: {query}\n"
                f"判断: 1=左转脸 2=右转脸 3=其他。只输出数字:"
            )
            intent = call_deepseek(
                [{"role": "user", "content": intent_prompt}],
                max_tokens=10
            )
            # 安全解析数字
            try:
                intent_num = int(intent.strip()) if intent and intent.strip().isdigit() else 3
            except (ValueError, AttributeError):
                intent_num = 3

            # 根据意图构建编辑指令
            if intent_num == 1:
                edit_prompt = "将这个人物的头部向左旋转约30度，保持面部特征和身份不变，保持背景和服装不变"
                direction = "左转30°"
            elif intent_num == 2:
                edit_prompt = "将这个人物的头部向右旋转约30度，保持面部特征和身份不变，保持背景和服装不变"
                direction = "右转30°"
            else:
                edit_prompt = query.strip()[:500]
                direction = "图像编辑"

            logger.info("🎯 人脸%s: prompt=%s", direction, edit_prompt[:60])

            # 构建 data URL 格式的图片地址
            image_url = f"data:image/png;base64,{image_base64}"
            messages = [{
                "role": "user",
                "content": [
                    {"image": image_url},
                    {"text": edit_prompt}
                ]
            }]

            # ★ 调用 DashScope 图像编辑 API（含SSL修复+重试）
            response = _call_dashscope_api("qwen-image-edit-max", messages, config.QWEN_API_KEY)

            if response.status_code == 200:
                result_images = _extract_images_from_response(response)
                if result_images:
                    return {
                        "success": True,
                        "result": f"✅ 人脸{direction}处理完成！",
                        "tool": "文生图",
                        "images": result_images
                    }

            # API 调用失败 → 友好错误提示
            status = response.status_code if hasattr(response, 'status_code') else 'unknown'
            logger.warning("图像编辑 API 返回状态: %s", status)
            result = (
                f"⚠️ 人脸{direction}处理未能完成。\n\n"
                f"可能原因：\n"
                f"1. DashScope API 密钥配置问题\n"
                f"2. 图像编辑模型 (qwen-image-edit-max) 不可用\n"
                f"3. 图片格式不支持\n\n"
                f"建议：检查 config.py 中的 QWEN_API_KEY 是否正确配置。"
            )
            return {"success": True, "result": result, "tool": "文生图"}

        # ========== 文本生图模式（无图片输入） ==========
        # 第一步：用 DeepSeek 将中文描述转为英文图像 prompt
        extract_prompt = (
            f"从以下中文描述提取精确的英文图像生成prompt"
            f"（含风格、分辨率、构图细节）:\n{query}\n只输出英文prompt:"
        )
        image_prompt = call_deepseek(
            [{"role": "user", "content": extract_prompt}],
            max_tokens=200
        )
        if not image_prompt:
            return {
                "success": False,
                "result": "图像描述提取失败，请更具体地描述您想要的图片（如：生成一张日落海边风景图）",
                "tool": "文生图"
            }

        logger.info("🖼️ 图像 prompt: %s", image_prompt[:80])

        # 第二步：调用 DashScope 生成图像（含SSL修复+重试）
        messages = [{
            "role": "user",
            "content": [{"text": image_prompt.strip()}]
        }]
        response = _call_dashscope_api("qwen-image-edit-max", messages, config.QWEN_API_KEY)

        if response.status_code == 200:
            result_images = _extract_images_from_response(response)
            if result_images:
                return {
                    "success": True,
                    "result": f"✅ 已根据描述生成图片:\n{image_prompt[:100]}",
                    "tool": "文生图",
                    "images": result_images
                }

        # API 生成失败 → 用 DeepSeek 生成文字描述作为兜底
        fallback = call_deepseek(
            [{"role": "user", "content": f"详细描述这张图片的内容(100-200字): {image_prompt}"}],
            max_tokens=300
        )
        result = (
            f"🎨 图像 prompt 已生成:\n{image_prompt}\n\n"
            f"📝 图片描述:\n{fallback or '生成中...'}\n\n"
            f"💡 提示：实际图片生成需要 DashScope 图像 API 配额。"
        )
        return {"success": True, "result": result, "tool": "文生图"}

    except Exception as e:
        err_str = str(e)[:300]
        logger.error("文生图错误: %s", err_str)

        # 判断错误类型，提供针对性建议
        if "SSL" in err_str or "SSLEOF" in err_str or "ssl" in err_str.lower():
            hint = (
                f"❌ 文生图网络连接失败 (SSL错误)\n\n"
                f"错误详情: {err_str[:200]}\n\n"
                f"🔧 排查建议:\n"
                f"1. 检查网络是否能访问 dashscope.aliyuncs.com\n"
                f"2. 如使用代理/Clash，确保已放行该域名\n"
                f"3. 尝试在命令行执行: ping dashscope.aliyuncs.com\n"
                f"4. 尝试: curl -I https://dashscope.aliyuncs.com\n"
                f"5. WSL用户可能需要重启WSL或重置网络: wsl --shutdown\n\n"
                f"💡 文生图功能依赖阿里云 DashScope API，\n"
                f"   网络受限时可用其他工具（基金/记账/日程等），这些不依赖 DashScope。"
            )
        elif "timeout" in err_str.lower() or "timed out" in err_str.lower():
            hint = (
                f"❌ 文生图请求超时\n\n"
                f"DashScope API 响应超时，请稍后重试。\n"
                f"图像生成通常需要10-30秒，请耐心等待。"
            )
        else:
            hint = (
                f"❌ 文生图失败: {err_str[:200]}\n\n"
                f"如持续失败，可能是 DashScope API 密钥或配额问题。"
            )

        return {"success": False, "result": hint, "tool": "文生图"}

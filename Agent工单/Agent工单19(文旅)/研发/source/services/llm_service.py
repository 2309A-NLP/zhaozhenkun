# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""llm_service.py - DeepSeek 模型调用与结果回退模块。"""  # 说明当前文件职责。

import json  # 导入 JSON 处理模块。
import os  # 导入环境变量模块。
import time  # 导入时间模块。
from urllib import error  # 导入请求异常模块。
from urllib import request  # 导入 HTTP 请求模块。


def _base_url() -> str:  # 读取模型基础地址。
    return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")  # 返回去尾斜杠后的地址。


def _api_key() -> str:  # 读取模型密钥。
    return os.getenv("DEEPSEEK_API_KEY", "").strip()  # 返回去空白后的密钥。


def _model_name() -> str:  # 读取模型名称。
    return os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"  # 返回模型名称。


def _timeout_seconds() -> float:  # 读取模型请求超时时间。
    raw_value = os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "8").strip()  # 读取超时秒数配置。
    try:  # 尝试把字符串转换为浮点数。
        return max(1.0, float(raw_value))  # 返回不小于 1 秒的超时时间。
    except ValueError:  # 当超时配置非法时回退默认值。
        return 8.0  # 返回默认超时时间。


def _cooldown_seconds() -> float:  # 读取模型失败后的熔断时长。
    raw_value = os.getenv("DEEPSEEK_COOLDOWN_SECONDS", "60").strip()  # 读取熔断秒数配置。
    try:  # 尝试把字符串转换为浮点数。
        return max(1.0, float(raw_value))  # 返回不小于 1 秒的熔断时长。
    except ValueError:  # 当熔断配置非法时回退默认值。
        return 60.0  # 返回默认熔断时长。


DEEPSEEK_UNAVAILABLE_UNTIL = 0.0  # 记录模型临时不可用截止时间。


def deepseek_ready() -> bool:  # 判断模型配置是否可用。
    api_key = _api_key()  # 读取模型密钥。
    return bool(api_key and api_key != "your_api_key_here" and time.time() >= DEEPSEEK_UNAVAILABLE_UNTIL)  # 当存在真实密钥且未处于熔断期时返回可用。


def chat_text(user_prompt: str, system_prompt: str, temperature: float = 0.7) -> str:  # 调用 DeepSeek 生成文本。
    global DEEPSEEK_UNAVAILABLE_UNTIL  # 声明需要更新模型熔断状态。
    if not deepseek_ready():  # 当未配置密钥或处于熔断期时直接返回空字符串。
        return ""  # 返回空结果以触发上层回退。
    payload = {  # 构造请求体。
        "model": _model_name(),  # 写入模型名称。
        "messages": [  # 构造消息数组。
            {"role": "system", "content": system_prompt},  # 写入系统提示词。
            {"role": "user", "content": user_prompt},  # 写入用户提示词。
        ],  # 消息数组结束。
        "temperature": temperature,  # 写入采样温度。
        "stream": False,  # 关闭流式输出。
    }  # 请求体构造结束。
    req = request.Request(  # 创建 HTTP 请求对象。
        url=f"{_base_url()}/chat/completions",  # 组装 DeepSeek 接口地址。
        data=json.dumps(payload).encode("utf-8"),  # 写入 JSON 请求体。
        headers={  # 定义请求头。
            "Authorization": f"Bearer {_api_key()}",  # 写入 Bearer 鉴权头。
            "Content-Type": "application/json",  # 写入 JSON 类型头。
        },  # 请求头定义结束。
        method="POST",  # 指定请求方法为 POST。
    )  # HTTP 请求对象创建结束。
    try:  # 开始执行请求并解析响应。
        with request.urlopen(req, timeout=_timeout_seconds()) as response:  # 发起请求并设置超时。
            body = json.loads(response.read().decode("utf-8"))  # 读取并解析响应 JSON。
        DEEPSEEK_UNAVAILABLE_UNTIL = 0.0  # 清空熔断状态。
        choices = body.get("choices", [])  # 读取候选结果列表。
        if not choices:  # 当未返回候选内容时返回空字符串。
            return ""  # 返回空结果。
        message = choices[0].get("message", {})  # 读取首个消息对象。
        return str(message.get("content", "")).strip()  # 返回清洗后的文本结果。
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):  # 捕获网络与解析异常。
        DEEPSEEK_UNAVAILABLE_UNTIL = time.time() + _cooldown_seconds()  # 记录短期熔断截止时间。
        return ""  # 返回空结果以触发上层回退。

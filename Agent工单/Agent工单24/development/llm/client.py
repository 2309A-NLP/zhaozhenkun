"""该文件用于封装兼容 OpenAI 协议的大模型调用客户端。"""

# 导入 JSON 模块，用于解析模型返回结果中的结构化内容。
import json
# 导入类型工具，用于声明流式返回值类型。
from typing import Iterator
# 导入网络请求库，用于向兼容接口发送聊天请求。
import requests

# 导入应用配置类型，便于接收模型配置。
from development.core.config import ProviderConfig


# 定义聊天客户端，用于统一调用 DeepSeek 与千问兼容接口。
class ChatClient:
    # 初始化聊天客户端，并保存模型提供方配置。
    def __init__(self, provider: ProviderConfig) -> None:
        # 保存当前模型提供方配置。
        self.provider = provider

    # 发送聊天请求，并返回模型文本结果。
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        # 若未配置密钥，则返回本地占位结果，便于离线演示。
        if not self.provider.api_key:
            # 构造离线模式说明，提示用户补充真实密钥。
            return f"[{self.provider.name} 离线模式] {user_prompt}"
        # 拼接兼容接口的聊天完成地址。
        url = self._chat_url()
        # 发送普通聊天完成请求。
        response = requests.post(url, headers=self._headers(), json=self._payload(system_prompt, user_prompt), timeout=60)
        # 若响应状态异常，则直接抛出错误。
        response.raise_for_status()
        # 解析 JSON 数据，便于提取模型回复。
        data = response.json()
        # 返回首个候选结果文本。
        return data["choices"][0]["message"]["content"].strip()

    # 以流式方式发送聊天请求，并逐块返回模型输出。
    def stream_chat(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        # 若未配置密钥，则用本地内容模拟流式输出。
        if not self.provider.api_key:
            # 生成离线模式的完整占位文本。
            offline_text = f"[{self.provider.name} 离线模式] {user_prompt}"
            # 按固定长度切片返回，模拟流式效果。
            for index in range(0, len(offline_text), 24):
                yield offline_text[index:index + 24]
            return
        # 构造带流式参数的请求体。
        payload = self._payload(system_prompt, user_prompt)
        # 打开流式开关，要求服务端分块返回。
        payload["stream"] = True
        # 发起流式 POST 请求并迭代响应数据行。
        with requests.post(self._chat_url(), headers=self._headers(), json=payload, timeout=60, stream=True) as response:
            # 若响应状态异常，则直接抛出错误。
            response.raise_for_status()
            # 逐行遍历服务端推送的数据块。
            for line in response.iter_lines(decode_unicode=True):
                # 若当前行为空，则跳过继续读取。
                if not line:
                    continue
                # 若不是标准 data 行，则忽略该行。
                if not line.startswith("data: "):
                    continue
                # 提取 data 前缀后的真实负载文本。
                data_text = line[6:].strip()
                # 当服务端发送结束标记时停止迭代。
                if data_text == "[DONE]":
                    break
                # 尝试解析当前数据块的 JSON。
                try:
                    data = json.loads(data_text)
                except json.JSONDecodeError:
                    continue
                # 读取首个候选块数据。
                choice = data.get("choices", [{}])[0]
                # 提取增量文本字段。
                delta = choice.get("delta", {})
                # 获取本轮增量文本内容。
                content = delta.get("content", "") if isinstance(delta, dict) else ""
                # 若当前块包含正文内容，则向上游输出。
                if content:
                    yield str(content)

    # 请求模型输出 JSON，并在失败时降级返回字典。
    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        # 在系统提示中明确要求模型输出 JSON。
        prompt = system_prompt + "\n请严格返回 JSON 对象，不要输出额外解释。"
        # 调用普通聊天方法获取原始文本结果。
        raw_text = self.chat(prompt, user_prompt)
        # 尝试直接将文本解析为 JSON。
        try:
            # 返回解析成功后的字典对象。
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # 若解析失败，则返回带原文的安全降级结果。
            return {"content": raw_text}

    # 构造统一的聊天接口地址。
    def _chat_url(self) -> str:
        # 返回完整聊天完成接口地址。
        return f"{self.provider.base_url.rstrip('/')}/chat/completions"

    # 构造统一请求头，便于普通请求与流式请求复用。
    def _headers(self) -> dict[str, str]:
        # 返回包含鉴权信息的标准请求头。
        return {
            "Authorization": f"Bearer {self.provider.api_key}",
            "Content-Type": "application/json",
        }

    # 构造统一请求体，便于普通请求与流式请求复用。
    def _payload(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        # 返回兼容 OpenAI 协议的标准聊天请求体。
        return {
            "model": self.provider.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
        }

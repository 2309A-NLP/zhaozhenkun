# -*- coding: utf-8 -*-
"""
Ollama VLM客户端模块 — 调用Qwen2.5-VL:3b进行图片+文本问答。

功能说明：
- 通过Ollama API调用Qwen2.5-VL:3b视觉语言模型
- 支持纯文本问题和图片+文本问题两种模式
- 支持temperature、top_p等生成参数控制
- 包含错误重试和超时处理

用法:
  from vlm_client import OllamaVLM
  vlm = OllamaVLM()
  # 纯文本
  ans = vlm.ask("什么是淬火？")
  # 图文问答
  ans = vlm.ask("图中部件4相对于部件5的位置？", image_path="./images/xxx.png")
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import requests  # 导入requests，用于发送HTTP请求
import json  # 导入json模块，用于处理API响应
import base64  # 导入base64，用于编码图片数据
import time  # 导入time，用于重试延迟


class OllamaVLM:
    """
    Ollama视觉语言模型客户端。
    封装Ollama API，支持图片+文本多模态输入。
    """

    def __init__(self, model="qwen2.5vl:3b", base_url="http://localhost:11434",
                 timeout=300):
        """
        初始化Ollama VLM客户端。

        参数:
            model: Ollama中的模型名称（默认qwen2.5vl:3b）
            base_url: Ollama服务地址（默认本地11434端口）
            timeout: API超时时间（秒，默认300秒适应图片推理）
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_image_mb = 5  # 单张图片最大5MB，超过跳过
        self.chat_url = f"{self.base_url}/api/chat"  # 聊天API端点
        self.generate_url = f"{self.base_url}/api/generate"  # 生成API端点

    def ask(self, question, image_path=None, temperature=0.1, max_retries=2):
        """
        向VLM提问，支持图文输入。

        参数:
            question: 问题文本
            image_path: 图片路径（可选，为空则纯文本问答）
            temperature: 生成温度（越低越确定，默认0.1）
            max_retries: 失败重试次数

        返回:
            模型回答文本，失败返回None
        """
        # 构造消息体
        messages = [{"role": "user", "content": question}]

        # 如果提供了图片路径，将图片编码为base64并添加到消息
        has_image = False
        if image_path and self._check_image(image_path):
            try:
                with open(image_path, "rb") as f:
                    raw = f.read()
                image_base64 = base64.b64encode(raw).decode("utf-8")
                messages[0]["images"] = [image_base64]
                has_image = True
                logger.info(f"  🖼️ 图片已编码: {os.path.basename(image_path)} ({len(raw)//1024}KB)")
            except Exception as e:
                logger.warning(f"  ⚠️ 图片读取失败: {image_path} - {e}")

        # 图片请求使用更长超时
        request_timeout = min(self.timeout * 2, 600) if has_image else self.timeout

        # 构建API请求体
        payload = {
            "model": self.model,  # 模型名称
            "messages": messages,  # 消息列表
            "stream": False,  # 非流式输出
            "options": {
                "temperature": temperature,  # 温度参数
            }
        }

        # 带重试的API调用
        for attempt in range(max_retries + 1):
            try:
                # 发送POST请求到Ollama API（图片请求自动延长超时）
                resp = requests.post(
                    self.chat_url,
                    json=payload,
                    timeout=request_timeout
                )
                resp.raise_for_status()  # 检查HTTP状态码

                # 解析响应
                result = resp.json()
                answer = result.get("message", {}).get("content", "")

                if answer and answer.strip():
                    return answer.strip()  # 返回去除首尾空格的答案
                else:
                    logger.warning(f"  ⚠️ 模型返回空回答")
                    return "【无回答】"

            except requests.exceptions.ConnectionError:
                logger.error(f"  ❌ Ollama未运行！请在终端启动: ollama serve")
                return "【Ollama未运行】"

            except requests.exceptions.Timeout:
                logger.warning(f"  ⚠️ API超时 (尝试 {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    time.sleep(2)  # 重试前等待

            except Exception as e:
                logger.warning(f"  ⚠️ API错误: {e} (尝试 {attempt + 1}/{max_retries + 1})")
                if attempt < max_retries:
                    time.sleep(1)

        return "【API失败】"

    def _check_image(self, image_path):
        """
        检查图片文件是否存在、格式支持、且大小合理。

        返回:
            True=有效图片, False=无效
        """
        import os
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"  ⚠️ 图片不存在: {image_path}")
            return False

        # 检查文件大小
        size_mb = os.path.getsize(image_path) / (1024 * 1024)
        if size_mb > self.max_image_mb:
            logger.warning(f"  ⚠️ 图片过大 ({size_mb:.1f}MB > {self.max_image_mb}MB)，跳过图片输入")
            return False

        # 支持的图片格式
        valid_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
        if not str(image_path).lower().endswith(valid_exts):
            logger.warning(f"  ⚠️ 不支持的图片格式: {image_path}")
            return False

        return True

    def check_health(self):
        """
        检查Ollama服务和模型是否就绪。

        返回:
            (服务状态, 模型状态) 元组
        """
        try:
            # 检查Ollama服务
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False, "Ollama服务异常"

            # 检查模型是否已下载
            models = resp.json().get("models", [])
            model_names = [m["name"] for m in models]
            if self.model not in model_names:
                return True, f"模型 {self.model} 未下载"
            return True, "就绪"

        except requests.exceptions.ConnectionError:
            return False, "Ollama服务未运行"

        except Exception as e:
            return False, str(e)

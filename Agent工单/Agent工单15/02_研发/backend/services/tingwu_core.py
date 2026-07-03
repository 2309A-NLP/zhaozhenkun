"""
================================================================================
文件名:   tingwu_core.py
功能:     通义听悟客户端核心 —— Token 鉴权、实时 ASR 入口、单例管理
参考:     https://help.aliyun.com/zh/tingwu/websocket-protocol
所属项目: 医疗智能体-Agent 数字人项目
工单编号: 人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0

通义听悟 API 鉴权规范:
  实时转写（WebSocket Token 生成）:
    算法: Base64(AccessKeyId + ":" + HMAC-SHA1(AccessKeySecret, string_to_sign))
    string_to_sign: "tingwu-realtime-cn-beijing\n{expire_time}"
    有效期: 默认 3600 秒（1 小时）

  DashScope Bearer Token:
    取配置 DASHSCOPE_API_KEY，直接作为 Authorization: Bearer {key}

类结构（本模块）:
  TingwuClient
    ├── _generate_token()           # 生成 WebSocket Token（AK/SK HMAC-SHA1 签名）
    └── realtime_asr()              # 实时语音识别入口（委托 tingwu_ws._dashscope_ws_asr）

外部依赖（实现位于子模块）:
    tingwu_ws._dashscope_ws_asr()        —— DashScope WebSocket 协议处理
    tingwu_postprocess.create_task()     —— 离线转写任务创建
    tingwu_postprocess.get_task_info()   —— 离线转写任务查询
    tingwu_postprocess.process_transcript() —— DeepSeek 转录分析
    tingwu_postprocess.translate_text()  —— DeepSeek 翻译

单例:
    get_tingwu_client() → TingwuClient  全局唯一客户端实例
================================================================================
"""
import os
import time
import json
import base64
import logging
import asyncio
import hashlib
import hmac
import uuid
from typing import Optional, Dict, Any, AsyncGenerator

import httpx
from config import (
    DASHSCOPE_API_KEY,                                              # DashScope sk-xxx
    TINGWU_APP_KEY,                                                 # 通义听悟 AppKey
    ASR_SAMPLE_RATE,                                                # 音频采样率（默认 16000）
    ASR_LANGUAGE,                                                   # 识别语言（默认 zh）
)

# 导入子模块实现
from services.tingwu_ws import _dashscope_ws_asr                    # WebSocket 实时 ASR 协议实现
from services.tingwu_postprocess import (                           # 后处理独立函数
    create_task as _create_task_impl,
    get_task_info as _get_task_info_impl,
    process_transcript as _process_transcript_impl,
    translate_text as _translate_text_impl,
)

_log = logging.getLogger("medical_agent.tingwu")                    # 模块级 logger


class TingwuClient:
    """
    通义听悟客户端 —— 严格按照官方接口规范实现

    支持两种鉴权模式:
      1. DashScope sk- key     → 实时 ASR（WebSocket）+ 离线转写（HTTP）+ 后处理
      2. 通义听悟 AppKey + AK/SK → WebSocket 实时转写（HMAC-SHA1 签名）

    属性:
      api_key:            DashScope API Key（sk-xxx 格式）
      app_key:            通义听悟应用 AppKey
      access_key_id:      阿里云 AccessKey ID（用于 AK/SK 签名）
      access_key_secret:  阿里云 AccessKey Secret
      http:               httpx 同步客户端（连接池复用）
    """

    def __init__(self):
        """初始化通义听悟客户端，从环境变量和 config 加载凭证"""
        self.api_key = DASHSCOPE_API_KEY                            # DashScope API Key
        self.app_key = TINGWU_APP_KEY                               # 通义听悟应用 AppKey
        self.access_key_id = os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_ID", "")                      # 阿里云 AK
        self.access_key_secret = os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")                  # 阿里云 SK
        self.http = httpx.Client(timeout=httpx.Timeout(120))        # 同步 HTTP 客户端（120s 超时）

    # ================================================================
    # Token 生成（通义听悟 WebSocket 鉴权）
    # 参考: https://help.aliyun.com/zh/tingwu/websocket-protocol
    # ================================================================
    def _generate_token(self) -> str:
        """
        生成通义听悟 WebSocket Token

        算法:
          1. 构建签名字符串: "tingwu-realtime-cn-beijing\\n{expire_time}"
          2. HMAC-SHA1 签名: HMAC-SHA1(AccessKeySecret, string_to_sign)
          3. 组装: AccessKeyId:Base64(signature):expire_time
          4. Base64 编码: Base64(step3)

        有效期: 默认 1 小时（3600 秒）

        Returns:
          Base64 编码的 Token 字符串，未配置 AK/SK 时返回空字符串
        """
        # 读取 AK/SK（优先实例属性，其次环境变量）
        ak_id = self.access_key_id or os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_ID", "")
        ak_secret = self.access_key_secret or os.getenv(
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")

        # 未配置 AK/SK 时降级使用 DashScope Bearer Token
        if not ak_id or not ak_secret:
            _log.warning("未配置 AK/SK，使用 DashScope sk-key 作为备选鉴权方式")
            return ""

        # Step 1: 确定过期时间（当前时间 + 3600 秒）
        expire_time = str(int(time.time()) + 3600)                  # Unix 时间戳（秒）

        # Step 2: 构建待签名字符串
        string_to_sign = f"tingwu-realtime-cn-beijing\n{expire_time}"  # 通义听悟实时转写端点

        # Step 3: HMAC-SHA1 签名
        signature = hmac.new(
            ak_secret.encode("utf-8"),                               # SK 作为密钥
            string_to_sign.encode("utf-8"),                          # 待签名字符串
            hashlib.sha1                                             # SHA1 哈希算法
        ).digest()                                                   # 返回 bytes
        signature_b64 = base64.b64encode(signature).decode("utf-8")  # Base64 编码

        # Step 4: 组装并编码 Token
        token_raw = f"{ak_id}:{signature_b64}:{expire_time}"        # AK:签名:过期时间
        token = base64.b64encode(token_raw.encode("utf-8")).decode("utf-8")
        return token

    # ================================================================
    # 实时语音识别 —— DashScope WebSocket 流式 ASR ★核心入口★
    #   协议: https://help.aliyun.com/zh/model-studio/real-time-speech-recognition
    #   实现: 委托给 services.tingwu_ws._dashscope_ws_asr()
    # ================================================================
    async def realtime_asr(
            self,
            audio_chunks: AsyncGenerator[bytes, None],              # 异步音频帧生成器
            sample_rate: int = ASR_SAMPLE_RATE,                     # 采样率（默认 16000）
            language: str = ASR_LANGUAGE,                           # 语言（默认 zh）
    ) -> AsyncGenerator[dict, None]:
        """
        实时语音转写 —— DashScope WebSocket 流式识别

        流程（真正流式——边收边发、边识别边返回）:
          1. 生成唯一 task_id
          2. 校验 API Key
          3. 委托 tingwu_ws._dashscope_ws_asr() 建立 WebSocket 连接
          4. 并发执行音频发送 + 结果接收
          5. 实时 yield 识别结果给调用方

        Yields (异步生成器):
          {"type":"partial","text":"中间结果"}                     临时/不完整识别
          {"type":"final","text":"完整句子","begin_time":0,"end_time":2500,
           "sentence_id":N}                                        已确认的最终句子
          {"type":"done","task_id":"xxx","sentence_count":N}       识别完成
          {"type":"error","message":"..."}                         错误信息
        """
        task_id = uuid.uuid4().hex[:16]                             # 生成 16 位唯一任务 ID

        # 前置校验: 无 API Key 不能使用 DashScope 实时 ASR
        if not self.api_key:
            _log.warning("DashScope API Key 未配置")
            yield {"type": "error",
                   "message": "语音识别服务未配置 (DASHSCOPE_API_KEY)"}
            return

        # 委托给 tingwu_ws 模块处理 WebSocket 全双工协议
        #   _dashscope_ws_asr 负责: 连接、鉴权、发送音频、接收结果、错误处理
        async for result in _dashscope_ws_asr(
                api_key=self.api_key,                               # Bearer Token
                task_id=task_id,                                    # 任务 ID
                audio_chunks=audio_chunks,                          # 音频帧流
                sample_rate=sample_rate,                            # 采样率
                language=language,                                  # 语言
        ):
            yield result                                            # 透明转发所有事件

    # ================================================================
    # 后处理 —— 委托给 tingwu_postprocess 独立函数
    #   这些方法保留在类上以保证 API 兼容性，实际逻辑在独立模块中
    # ================================================================

    def create_task(self,
                    audio_url: str = "",
                    file_url: str = "",
                    source_language: str = "cn",
                    enable_summarization: bool = True,
                    enable_chapter: bool = True,
                    enable_keywords: bool = True,
                    enable_qa: bool = True,
                    callback_url: str = "") -> dict:
        """
        创建离线转写任务 —— 委托给 tingwu_postprocess.create_task()

        参数:
          audio_url:            音频文件公网 URL（与 file_url 二选一）
          file_url:             音频文件 OSS URL
          source_language:      语言代码 cn/en
          enable_summarization: 启用全文摘要
          enable_chapter:       启用章节速览
          enable_keywords:      启用关键词提取
          enable_qa:            启用问答提取
          callback_url:         异步回调 URL

        返回:
          {"success": True, "task_id": "xxx", "status": "NEW"}
          或 {"success": False, "error": "..."}
        """
        return _create_task_impl(
            api_key=self.api_key,
            http_client=self.http,
            audio_url=audio_url,
            file_url=file_url,
            source_language=source_language,
            enable_summarization=enable_summarization,
            enable_chapter=enable_chapter,
            enable_keywords=enable_keywords,
            enable_qa=enable_qa,
            callback_url=callback_url,
        )

    def get_task_info(self, task_id: str) -> dict:
        """
        查询离线转写任务状态 —— 委托给 tingwu_postprocess.get_task_info()

        状态流转: NEW → QUEUEING → RUNNING → SUCCESS (或 FAILED)

        参数:
          task_id: 任务唯一标识

        返回:
          {"success": True/False, "task_id": "xxx", "status": "...", ...}
        """
        return _get_task_info_impl(
            access_key_id=self.access_key_id,
            http_client=self.http,
            task_id=task_id,
        )

    def process_transcript(self, transcript: str) -> dict:
        """
        用 DeepSeek 分析转录文本 —— 委托给 tingwu_postprocess.process_transcript()

        生成通义听悟兼容结构: 摘要、章节、关键词、问答、待办

        参数:
          transcript: 完整转录文本

        返回:
          {"raw": "...", "summary": "...", "keywords": "...", ...}
        """
        return _process_transcript_impl(transcript)                 # 独立函数，无需传递 self

    def translate_text(self, text: str, target_lang: str = "英文") -> dict:
        """
        翻译文本 —— 委托给 tingwu_postprocess.translate_text()

        参数:
          text:        待翻译原文
          target_lang: 目标语言

        返回:
          {"success": True/False, "translation": "...", "error": "..."}
        """
        return _translate_text_impl(text, target_lang)              # 独立函数，无需传递 self


# ================================================================
# 全局单例 —— 线程安全的懒加载
# ================================================================

_tingwu: Optional[TingwuClient] = None                              # 模块级单例变量


def get_tingwu_client() -> TingwuClient:
    """
    获取通义听悟客户端全局单例

    懒加载模式: 首次调用时实例化 TLS 客户端，
    之后每次调用返回同一个实例，复用 HTTP 连接池。
    Python GIL 保证单次赋值的线程安全。

    返回:
      TingwuClient 全局唯一实例
    """
    global _tingwu
    if _tingwu is None:
        _tingwu = TingwuClient()                                    # 延迟实例化
    return _tingwu

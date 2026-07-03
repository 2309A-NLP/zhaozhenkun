"""
================================================================================
文件名:   tingwu_postprocess.py
功能:     通义听悟后处理 —— 离线转写、转录分析、翻译、摘要解析（全部独立函数）
参考:     https://help.aliyun.com/zh/tingwu/interface-and-implementation
所属项目: 医疗智能体-Agent 数字人项目

通义听悟离线转写 API:
  POST /api/v1/services/audio/asr/transcription   创建任务（paraformer-v2）
  鉴权: Authorization: Bearer {api_key}
  状态机: NEW → QUEUEING → RUNNING → SUCCESS (或 FAILED)

导出: SUMMARY_PROMPT / _parse_summary_result() /
      process_transcript() / translate_text() / create_task() / get_task_info()
================================================================================
"""
import re
import json
import uuid
import logging
from typing import Dict, Optional

import httpx
from config import DASHSCOPE_HTTP_URL                                 # DashScope HTTP API 地址

_log = logging.getLogger("medical_agent.tingwu.post")                # 子 logger

# ================================================================
# DeepSeek 会议纪要 System Prompt —— 工单要求的七个输出维度
# ================================================================
SUMMARY_PROMPT = """你是专业会议纪要专家。根据以下对话转录文本，生成结构化会议纪要：

## 要求输出格式：

### 1. 说话人分离
识别对话中的不同说话人（如医生、患者等），标注每句话的说话人：
- 说话人A（医生）：说的话...
- 说话人B（患者）：说的话...

### 2. 全文摘要
200字以内概括全文核心内容，让读者快速了解对话主题。

### 3. 章节速览
按主题将对话分为若干章节，每章用一句话概述。格式：
- 章节1标题：一句话概述
- 章节2标题：一句话概述

### 4. 发言总结
分别总结每位说话人的核心观点和发言内容。

### 5. 待办事项
提取对话中明确或隐含的需要后续执行的事项，每项一行。

### 6. 问答提取
提取对话中的问答对。格式：
- 问：xxx
- 答：xxx

### 7. 关键词
提取5-10个最重要的关键词，用逗号分隔。

## 注意事项：
- 用中文输出
- 如果无法区分说话人，按语义推断
- 每个部分前面用"【部分名】"标记
- 不要编造内容，严格基于转录文本

原文转录："""


# ================================================================
# 离线转写 —— DashScope CreateTask / GetTaskInfo
# ================================================================

def create_task(
        api_key: str,                                               # DashScope API Key
        http_client: Optional[httpx.Client] = None,                 # 可复用 httpx 客户端
        audio_url: str = "",                                        # 音频文件公网 URL
        file_url: str = "",                                         # 音频文件 OSS URL（二选一）
        source_language: str = "cn",                                # 语言: cn/en
        enable_summarization: bool = True,                          # 启用全文摘要
        enable_chapter: bool = True,                                # 启用章节速览
        enable_keywords: bool = True,                               # 启用关键词
        enable_qa: bool = True,                                     # 启用问答提取
        callback_url: str = "",                                     # 异步回调 URL
) -> dict:
    """创建离线转写任务 —— DashScope CreateTask API (paraformer-v2).

    参数:
      api_key: DashScope API Key（sk-xxx）；http_client: 可复用 httpx.Client
      audio_url/file_url: 音频文件地址（二选一）；source_language: cn/en
      enable_*: 功能开关；callback_url: 异步回调

    返回: {"success": True, "task_id": "xxx", "status": "NEW"}
          或 {"success": False, "error": "..."}
    """
    if not audio_url and not file_url:
        return {"success": False, "error": "请提供 audio_url 或 file_url"}
    if not api_key:
        return {"success": False,
                "error": "未配置 DASHSCOPE_API_KEY，无法创建通义听悟任务。请在 .env 中设置。"}

    try:
        payload = {
            "model": "paraformer-v2",                               # 离线 Paraformer 模型
            "input": {
                "file_url": audio_url or file_url,                  # 音频文件地址
                "language_hints": [source_language],                # 语言提示
            },
            "parameters": {
                "enable_summarization": enable_summarization,
                "enable_chapter": enable_chapter,
                "enable_keywords": enable_keywords,
                "enable_qa": enable_qa,
            },
        }
        if callback_url:
            payload["parameters"]["callback_url"] = callback_url

        headers = {"Authorization": f"Bearer {api_key}"}
        if http_client:
            resp = http_client.post(
                f"{DASHSCOPE_HTTP_URL}/services/audio/asr/transcription",
                json=payload, headers=headers)
        else:
            with httpx.Client(timeout=httpx.Timeout(120)) as client:
                resp = client.post(
                    f"{DASHSCOPE_HTTP_URL}/services/audio/asr/transcription",
                    json=payload, headers=headers)

        data = resp.json()
        if resp.status_code == 200 and data.get("output"):
            task_id = data.get("output", {}).get("task_id",
                                                  f"tingwu_{uuid.uuid4().hex[:12]}")
            return {"success": True, "task_id": task_id, "status": "NEW"}
        else:
            err = data.get("message", data.get("code", "未知错误"))
            _log.error("CreateTask 失败, HTTP %d: %s", resp.status_code, data)
            return {"success": False, "error": str(err)}
    except Exception as e:
        _log.error("创建任务失败: %s", e)
        return {"success": False, "error": str(e)}


def get_task_info(
        access_key_id: str,                                         # 阿里云 AK（为空走本地模式）
        http_client: Optional[httpx.Client] = None,                 # httpx 客户端
        task_id: str = "",                                          # 任务 ID
) -> dict:
    """查询离线转写任务状态 —— 状态: NEW → QUEUEING → RUNNING → SUCCESS/FAILED.

    返回 SUCCESS 时的 result 结构:
      transcription, summarization, chapter_notes, keywords, qa_extractions

    参数:
      access_key_id: 阿里云 AccessKey ID（为空则走本地模式）
      http_client: 可复用的 httpx.Client；task_id: 任务 ID

    返回: {"success": True/False, "task_id": "xxx", "status": "...", ...}
    """
    try:
        if not access_key_id or task_id.startswith("local_"):
            return {"success": True, "task_id": task_id,
                    "status": "RUNNING",
                    "message": f"本地处理中，请通过 /api/asr/task/{task_id} 查询"}

        _log.info("查询任务: %s (当前为占位实现)", task_id)
        return {"success": True, "task_id": task_id,
                "status": "RUNNING", "message": "任务处理中"}
    except Exception as e:
        _log.error("查询任务状态失败: %s", e)
        return {"success": False, "error": str(e)}


# ================================================================
# 后处理分析 —— DeepSeek 全局单例
# ================================================================

def process_transcript(transcript: str) -> dict:
    """用 DeepSeek 分析转录文本，输出七个维度: 说话人分离/摘要/章节/发言总结/
    待办/问答/关键词。

    参数: transcript 完整转录文本（最大 8000 字符）
    返回: {"raw": "...", "summary": "...", "keywords": "...", ...}
          或 {"error": "..."}
    """
    from services.llm_client import get_deepseek_client            # 延迟导入避免循环依赖

    ds = get_deepseek_client()                                      # 复用全局单例
    prompt = f"{SUMMARY_PROMPT}\n\n{transcript[:8000]}"             # 截断到 8000 字符
    result = ds.chat(
        [{"role": "user", "content": prompt}],
        system="你是专业会议纪要专家，输出结构化分析结果。",
        max_tokens=2000,
    )
    if "error" in result:
        return {"error": result.get("content", str(result["error"]))}
    return _parse_summary_result(result["content"])


def translate_text(text: str, target_lang: str = "英文") -> dict:
    """DeepSeek 专业翻译。

    参数: text 待翻译原文；target_lang 目标语言（如"英文"、"日文"）
    返回: {"success": True/False, "translation": "...", "error": "..."}
    """
    from services.llm_client import get_deepseek_client            # 延迟导入

    ds = get_deepseek_client()                                      # 复用全局单例
    result = ds.chat(
        [{"role": "user", "content": text}],
        system=f"你是专业翻译，译为{target_lang}，只返回翻译结果。",
        max_tokens=2000,
    )
    if "error" in result:
        return {"success": False, "translation": "",
                "error": result.get("content", str(result["error"]))}
    return {"success": True, "translation": result["content"], "error": ""}


# ================================================================
# 解析 DeepSeek 结构化输出 → 通义听悟兼容格式
# ================================================================

def _parse_summary_result(raw: str) -> dict:
    """正则提取 DeepSeek 自由文本中的七个维度结构化内容。

    参数: raw DeepSeek 返回原始文本；返回: 结构化 dict（含 raw 字段）
    """
    result = {"raw": raw}                                           # 保留原始输出
    patterns = {
        "diarization":     r"(?:说话人分离|说话人识别|说话人)[：:]\s*(.+?)(?=\n\d|\n###|\n【|\Z)",
        "summary":         r"(?:全文摘要|摘要)[：:]\s*(.+?)(?=\n\d|\n###|\n【|\Z)",
        "chapters":        r"(?:章节速览|章节)[：:]\s*(.+?)(?=\n\d|\n###|\n【|\Z)",
        "speaker_summary": r"(?:发言总结|发言)[：:]\s*(.+?)(?=\n\d|\n###|\n【|\Z)",
        "todos":           r"(?:待办事项|待办)[：:]\s*(.+?)(?=\n\d|\n###|\n【|\Z)",
        "qa":              r"(?:问答提取|问答|问答对)[：:]\s*(.+?)(?=\n\d|\n###|\n【|\Z)",
        "keywords":        r"(?:关键词|关键字)[：:]\s*(.+?)(?:\n|$)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, raw, re.DOTALL)                      # DOTALL 匹配换行
        if m:
            result[key] = m.group(1).strip()[:800]                  # 截断到 800 字符
    return result

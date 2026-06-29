# -*- coding: utf-8 -*-
"""
tool_utils.py — 工具集共享底层函数
--------------------------------------------------------------
功能: 提供 DeepSeek API 调用、SQL 清理、数据路径解析等公共能力。
      被所有工具模块 (tool_ledger, tool_schedule, tool_text2image,
      tool_fund, tool_prospectus) 共用。

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import json      # JSON 解析（解析 LLM 返回的 JSON 响应）
import time      # 时间等待（API 重试指数退避）
import logging   # 日志记录
import os        # 文件系统路径操作
import re        # 正则表达式（SQL 清理、文本匹配）
import requests  # HTTP 请求（调用 DeepSeek API）
from pathlib import Path  # 跨平台路径处理（替代 os.path）

import config  # Agent 全局配置（API 密钥/超时等）

# 模块级日志器（复用 agent.tools 命名空间）
logger = logging.getLogger("agent.tools")


def call_deepseek(messages: list, max_tokens: int = 2048) -> str | None:
    """调用 DeepSeek API — 兼容推理模型（含 reasoning_content 兜底提取）

    功能: 向 DeepSeek API 发送消息列表，获取模型回复。当推理模型将答案
          放在 reasoning_content 而非 content 时自动兜底提取。

    参数:
        messages (list): OpenAI 格式的消息列表 [{"role":"...", "content":"..."}]
        max_tokens (int): 最大输出 token 数，默认 2048

    返回:
        str | None: 模型回复的文本内容；所有重试均失败时返回 None
    """
    # 构造 API 请求 URL（配置中管理 base URL）
    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    # 请求头：认证 + 内容类型
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    # 请求体：模型名 + 消息 + 温度 + token 预算 + 非流式
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.0,          # 温度 0 确保输出稳定/确定性
        "max_tokens": max_tokens,
        "stream": False              # 非流式：一次返回完整结果
    }
    last_error = None  # 记录最后一次错误信息（用于最终日志）

    # 重试循环（最多 MAX_RETRIES 次，指数退避）
    for attempt in range(config.MAX_RETRIES):
        try:
            # 发送 POST 请求
            r = requests.post(
                url, headers=headers, json=payload,
                timeout=config.API_TIMEOUT
            )
            if r.status_code == 200:                     # HTTP 成功
                body = r.json()                          # 解析 JSON 响应体
                msg = body["choices"][0]["message"]      # 取第一候选消息
                content = (msg.get("content") or "").strip()  # 提取 content 字段

                # ★ 推理模型兜底: content 为空时从 reasoning_content 提取
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        logger.warning(
                            "推理模型 content 为空，使用 reasoning_content (%d 字)",
                            len(reasoning)
                        )
                        # 推理内容通常按双换行分段，最后一段最接近最终答案
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()

                if content:
                    return content  # 成功获取回复，返回

                # content 和 reasoning 都为空 → max_tokens 可能不够
                finish = body["choices"][0].get("finish_reason", "")
                logger.warning(
                    "DeepSeek 返回空 content (finish_reason=%s, max_tokens=%d)，加大预算重试",
                    finish, max_tokens
                )
                payload["max_tokens"] = max(max_tokens * 2, 4096)  # 翻倍 token 预算

            else:
                last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                logger.warning("DeepSeek API 错误 (尝试 %d/%d): %s",
                               attempt + 1, config.MAX_RETRIES, last_error)

        except Exception as e:
            last_error = str(e)[:200]
            logger.warning("DeepSeek 请求异常 (尝试 %d/%d): %s",
                           attempt + 1, config.MAX_RETRIES, last_error)

        # 指数退避等待：第 1 次等 2s，第 2 次等 4s …
        time.sleep((attempt + 1) * 2)

    # 所有重试均失败
    logger.error("DeepSeek 最终失败: %s", last_error or "未知错误")
    return None


def clean_sql(text: str) -> str:
    """清理 SQL 文本 — 去除 markdown 代码块包裹和注释行

    功能: LLM 经常在 SQL 外加 ```sql ... ``` 标记，或包含注释行。
          此函数将其剥离，返回纯 SQL。

    参数:
        text (str): LLM 返回的原始 SQL 文本

    返回:
        str: 纯净的 SQL 语句（去除包裹符和注释）
    """
    if not text:
        return ""  # 空输入直接返回

    text = text.strip()  # 去首尾空白

    # 去除 markdown 代码块标记（```sql / ```SQL / ```）
    for mark in ["```sql", "```SQL", "```"]:
        if text.startswith(mark):
            text = text[len(mark):].strip()  # 去掉开头标记
        if text.endswith("```"):
            text = text[:-3].strip()          # 去掉结尾标记

    # 过滤掉 SQL 注释行（以 -- 开头）
    lines = text.split("\n")
    lines = [line for line in lines if not line.strip().startswith("--")]
    return "\n".join(lines).strip()


def resolve_data_path(relative_path: str, env_var: str | None = None) -> str | None:
    """跨平台解析数据文件路径

    功能: 在不同操作系统（WSL/Windows/Linux）间自动查找数据文件。
          依次尝试: 环境变量 → 项目相对 → WSL → Windows → Home

    参数:
        relative_path (str): 相对于 bs_challenge_financial_14b_dataset 的相对路径
        env_var (str | None): 可选的环境变量名

    返回:
        str | None: 完整文件路径（存在时），否则 None
    """
    import sys as _sys  # 诊断用：打印平台信息

    dataset_name = "bs_challenge_financial_14b_dataset"

    # 优先级 0: 环境变量覆盖
    if env_var and os.environ.get(env_var):
        p = Path(os.environ[env_var]) / relative_path
        if p.exists():
            logger.info("数据路径(环境变量): %s", p)
            return str(p)

    # ★ 构建候选路径列表
    candidates = []
    checked_info = []  # 诊断记录

    # 候选1: 项目父目录
    try:
        project_dir = Path(__file__).resolve().parent  # 研发/
        parent = project_dir.parent                     # Agent工单9/
        candidates.append(("项目父目录", parent / dataset_name))
        candidates.append(("项目爷目录", parent.parent / dataset_name))
    except Exception:
        pass

    # 候选2: 当前工作目录
    candidates.append(("当前目录", Path.cwd() / dataset_name))

    # 候选3: WSL /mnt/c/Users/<name>/ 路径 (同时尝试多个用户名)
    for uname in ["31326", "zzy", os.environ.get("USER", ""), os.environ.get("USERNAME", "")]:
        if uname:
            p = Path(f"/mnt/c/Users/{uname}/{dataset_name}")
            candidates.append((f"WSL(/mnt/c/Users/{uname})", p))

    # 候选4: Windows 原生路径
    for uname in ["31326", os.environ.get("USERNAME", ""), os.environ.get("USER", "")]:
        if uname:
            p = Path(f"C:/Users/{uname}/{dataset_name}")
            candidates.append((f"Windows(C:/Users/{uname})", p))

    # 候选5: USERPROFILE 环境变量
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        candidates.append(("USERPROFILE", Path(userprofile) / dataset_name))

    # 候选6: Home 目录
    try:
        candidates.append(("Path.home()", Path.home() / dataset_name))
    except Exception:
        pass

    # ★ 去重后逐一检查（记录所有结果到日志）
    checked = set()
    for label, base in candidates:
        base_str = str(base)
        if base_str in checked:
            continue
        checked.add(base_str)
        p = base / relative_path
        exists = p.exists()
        checked_info.append(f"  {label}: {p} → {'✅' if exists else '❌'}")

        if exists:
            for info in checked_info:
                logger.info(info)
            logger.info("数据路径解析成功 → %s", p)
            return str(p)

    # 全部失败 → 打印完整诊断
    logger.error("❌ 数据路径解析失败！relative_path=%s, platform=%s, cwd=%s",
                 relative_path, _sys.platform, Path.cwd())
    for info in checked_info:
        logger.error(info)
    return None


# ============================================================
# 自测（直接运行此文件时触发）
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    # 测试 DeepSeek 调用
    test_msg = [{"role": "user", "content": "你好，请说 1+1=2"}]
    result = call_deepseek(test_msg, max_tokens=100)
    print(f"call_deepseek 测试: {result}")
    # 测试 SQL 清理
    dirty = "```sql\nSELECT * FROM test;\n```"
    print(f"clean_sql 测试: '{clean_sql(dirty)}'")
    # 测试路径解析
    print(f"resolve_data_path 测试: {resolve_data_path('pdf_txt_file')}")

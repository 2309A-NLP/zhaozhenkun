#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
研发 — Research Agent 配置管理模块
==============================================================================
功能: 集中管理所有配置项，包括 API 密钥、模型参数、Agent 行为参数等。
      支持从环境变量和 .env 文件加载配置。
说明: 所有可调参数集中在此模块，方便调试和部署时修改。
==============================================================================
"""
import os  # 操作系统接口，用于读取环境变量
from typing import Optional  # 类型注解

# ============================================================
# 一、DeepSeek API 配置
# ============================================================

DEEPSEEK_API_KEY = os.getenv(  # 从环境变量读取 API Key
    "DEEPSEEK_API_KEY",  # 环境变量名
    "sk-70c456e35e914eb88fa233a04856bcf4"  # 默认值（用户提供的密钥）
)

DEEPSEEK_BASE_URL = os.getenv(  # 从环境变量读取 API 地址
    "DEEPSEEK_BASE_URL",  # 环境变量名
    "https://api.deepseek.com"  # 默认 DeepSeek API 地址
)

DEEPSEEK_MODEL = os.getenv(  # 从环境变量读取模型名称
    "DEEPSEEK_MODEL",  # 环境变量名
    "deepseek-chat"  # 默认使用 deepseek-chat 模型
)

# ============================================================
# 二、SerpAPI 搜索工具配置
# ============================================================

SERPAPI_API_KEY = os.getenv(  # 从环境变量读取 SerpAPI Key
    "SERPAPI_API_KEY",  # 环境变量名
    ""  # 默认为空，需要用户自行配置
)

SERPAPI_BASE_URL = "https://serpapi.com/search"  # SerpAPI 搜索端点

SEARCH_NUM_RESULTS = 5  # 每次搜索返回的结果数量

# ============================================================
# 三、Agent 行为参数
# ============================================================

MAX_AGENT_TURNS = 5  # Agent 最大推理轮数（3-5轮足够，避免过度搜索）

LLM_TEMPERATURE = 0.3  # LLM 温度参数（0-1，越低越确定性）

LLM_MAX_TOKENS = 2000  # LLM 单次回复最大 token 数

REQUEST_TIMEOUT = 60  # HTTP 请求超时时间（秒）

FETCH_MAX_CHARS = 4000  # fetch 工具获取网页的最大字符数

# ============================================================
# 四、部署配置
# ============================================================

EAS_SERVICE_PORT = int(os.getenv("EAS_SERVICE_PORT", "8000"))  # EAS 服务端口

EAS_SERVICE_HOST = os.getenv("EAS_SERVICE_HOST", "0.0.0.0")  # EAS 服务主机地址

# ============================================================
# 五、日志配置
# ============================================================

VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"  # 是否打印详细日志

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"  # 日志格式

# ============================================================
# 六、配置验证函数
# ============================================================

def validate_config() -> bool:  # 验证关键配置是否完整
    """验证关键配置项是否已正确设置，返回 True/False。"""
    errors = []  # 错误信息列表

    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-"):  # API Key 格式基本检查
        pass  # 格式看起来正确
    else:  # API Key 格式异常
        errors.append("DEEPSEEK_API_KEY 格式可能不正确")  # 记录错误

    if not SERPAPI_API_KEY:  # SerpAPI Key 未设置
        errors.append("SERPAPI_API_KEY 未设置，搜索功能将使用备用方案")  # 警告但非致命

    if errors:  # 存在错误
        for e in errors:  # 遍历打印所有错误
            print(f"[配置警告] {e}")  # 打印警告信息

    return True  # 始终返回 True（警告不阻塞运行）


def print_config():  # 打印当前配置摘要（隐藏密钥）
    """打印当前配置摘要，密钥信息脱敏显示。"""
    print("=" * 50)  # 分隔线
    print("  Research Agent 配置")  # 标题
    print("=" * 50)  # 分隔线
    # 脱敏打印 API Key（只显示前后几位）
    if DEEPSEEK_API_KEY:  # API Key 存在
        masked = DEEPSEEK_API_KEY[:8] + "****" + DEEPSEEK_API_KEY[-4:]  # 脱敏处理
        print(f"  LLM API Key: {masked}")  # 打印脱敏后的 Key
    print(f"  LLM Base URL: {DEEPSEEK_BASE_URL}")  # 打印 API 地址
    print(f"  LLM Model: {DEEPSEEK_MODEL}")  # 打印模型名称
    print(f"  Max Turns: {MAX_AGENT_TURNS}")  # 打印最大轮数
    print(f"  Temperature: {LLM_TEMPERATURE}")  # 打印温度参数
    print(f"  Service Port: {EAS_SERVICE_PORT}")  # 打印服务端口
    print("=" * 50)  # 分隔线


# ============================================================
# 七、模块自检
# ============================================================
if __name__ == "__main__":  # 模块自检入口
    print_config()  # 打印配置摘要
    validate_config()  # 验证配置
    print("配置模块加载完成。")  # 自检完成

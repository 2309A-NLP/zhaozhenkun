# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""config.py - 工单18智能助教的配置与路径管理模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解支持。

import json  # 工单18：导入 JSON 处理模块。
import os  # 工单18：导入系统环境变量模块。
from pathlib import Path  # 工单18：导入路径处理类。

BASE_DIR = Path(__file__).resolve().parents[1]  # 工单18：定位研发目录。
PROJECT_DIR = BASE_DIR.parents[0]  # 工单18：定位项目根目录。
STATIC_DIR = BASE_DIR / "static"  # 工单18：定义静态资源目录。
DATA_DIR = BASE_DIR / "data"  # 工单18：定义数据存储目录。
DEPLOY_DIR = PROJECT_DIR / "部署"  # 工单18：定义部署资料目录。
STATE_FILE = DATA_DIR / "state.json"  # 工单18：定义状态数据文件路径。
SECRETS_FILE = DEPLOY_DIR / "model_secrets.local.json"  # 工单18：定义本地密钥文件路径。
APP_SECRET = os.getenv("EDU_AGENT_APP_SECRET", "edu-agent-workorder-18")  # 工单18：定义签名密钥。
HOST = os.getenv("EDU_AGENT_HOST", "127.0.0.1")  # 工单18：定义默认监听地址。
PORT = int(os.getenv("EDU_AGENT_PORT", "8018"))  # 工单18：定义默认监听端口。


def ensure_directories() -> None:  # 工单18：创建运行所需目录。
    DATA_DIR.mkdir(parents=True, exist_ok=True)  # 工单18：确保数据目录存在。
    STATIC_DIR.mkdir(parents=True, exist_ok=True)  # 工单18：确保静态目录存在。
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)  # 工单18：确保部署目录存在。


def load_model_secrets() -> dict:  # 工单18：加载双模型配置与密钥。
    ensure_directories()  # 工单18：先确保目录准备完成。
    default_config = {  # 工单18：准备默认模型配置。
        "deepseek": {"base_url": "https://api.deepseek.com", "api_key": "", "model": "deepseek-chat"},  # 工单18：定义 DeepSeek 默认配置。
        "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "", "model": "qwen-plus"},  # 工单18：定义千问默认配置。
    }  # 工单18：结束默认模型配置。
    if SECRETS_FILE.exists():  # 工单18：如果本地密钥文件存在则优先读取。
        return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))  # 工单18：返回本地密钥文件内容。
    return default_config  # 工单18：在密钥文件缺失时返回默认配置。


def get_provider_config(provider: str) -> dict:  # 工单18：读取指定模型服务商配置。
    providers = load_model_secrets()  # 工单18：加载全部模型配置。
    return providers.get(provider, providers["deepseek"])  # 工单18：缺省回退到 DeepSeek 配置。


def now_text() -> str:  # 工单18：生成当前时间字符串。
    from datetime import datetime  # 工单18：局部导入时间模块以减少启动耦合。

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 工单18：返回格式化时间文本。


def public_origin_list() -> list[str]:  # 工单18：返回允许的跨域来源列表。
    return [  # 工单18：输出开发期本地来源。
        f"http://127.0.0.1:{PORT}",  # 工单18：允许当前运行端口访问。
        f"http://localhost:{PORT}",  # 工单18：允许 localhost 当前运行端口访问。
        "http://127.0.0.1:5500",  # 工单18：允许静态调试端口访问。
        "http://localhost:5500",  # 工单18：允许 localhost 静态调试访问。
    ]  # 工单18：结束来源列表。

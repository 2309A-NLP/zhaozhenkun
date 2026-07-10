# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""settings.py - 项目运行配置加载模块。"""  # 说明当前文件职责。

import os  # 导入系统环境变量模块。
from pathlib import Path  # 导入路径处理工具。


def _load_env_file(env_path: Path):  # 读取并加载本地环境变量文件。
    if not env_path.exists():  # 当环境文件不存在时直接跳过。
        return  # 结束当前函数。
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():  # 逐行读取环境文件内容。
        line = raw_line.strip()  # 清洗单行文本。
        if not line or line.startswith("#") or "=" not in line:  # 跳过空行、注释和非法行。
            continue  # 继续处理下一行。
        key, value = line.split("=", 1)  # 按首个等号拆分键值。
        os.environ.setdefault(key.strip(), value.strip())  # 仅在环境变量不存在时写入。


def _to_bool(value: str, default: bool = False) -> bool:  # 把字符串转换为布尔值。
    text = str(value or "").strip().lower()  # 统一清洗输入值。
    if not text:  # 当输入为空时使用默认值。
        return default  # 返回默认布尔值。
    return text in {"1", "true", "yes", "on"}  # 返回转换结果。


def load_settings() -> dict:  # 加载并返回项目配置字典。
    source_dir = Path(__file__).resolve().parent.parent  # 获取源码主目录。
    project_dir = source_dir.parent  # 获取研发目录。
    data_dir = project_dir / "data"  # 计算数据目录路径。
    deploy_dir = project_dir.parent / "部署"  # 计算部署目录路径。
    _load_env_file(deploy_dir / ".env")  # 加载部署目录中的环境变量文件。
    return {  # 返回完整配置。
        "APP_TITLE": os.getenv("APP_TITLE", "文旅Agent工单19"),  # 应用标题。
        "DEBUG": _to_bool(os.getenv("DEBUG", "true"), True),  # 调试开关。
        "HOST": os.getenv("HOST", "127.0.0.1"),  # 默认监听地址。
        "PORT": int(os.getenv("PORT", "5050")),  # 默认监听端口。
        "SECRET_KEY": os.getenv("SECRET_KEY", "agent-ticket-19-demo-key"),  # Flask 密钥。
        "DEFAULT_LANGUAGE": os.getenv("DEFAULT_LANGUAGE", "zh"),  # 默认语言。
        "MAX_HISTORY": int(os.getenv("MAX_HISTORY", "8")),  # 会话保留条数。
        "KNOWLEDGE_PATH": str(data_dir / "tourism_knowledge.json"),  # 知识库路径。
        "DEFAULT_CITY": os.getenv("DEFAULT_CITY", "北京"),  # 默认城市。
        "DEFAULT_THEME": os.getenv("DEFAULT_THEME", "文化体验"),  # 默认主题。
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),  # DeepSeek 基础地址。
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),  # DeepSeek 模型名称。
        "AMAP_WEB_KEY": os.getenv("AMAP_WEB_KEY", ""),  # 高德地图 Web Key。
        "AMAP_SECURITY_CODE": os.getenv("AMAP_SECURITY_CODE", ""),  # 高德地图安全密钥。
        "MAP_DEFAULT_ZOOM": int(os.getenv("MAP_DEFAULT_ZOOM", "5")),  # 地图默认缩放级别。
    }  # 配置字典结束。

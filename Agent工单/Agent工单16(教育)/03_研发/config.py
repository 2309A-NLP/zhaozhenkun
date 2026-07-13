# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""config.py - 教育 Agent 项目的配置加载模块。"""  # 说明当前文件职责。

from pathlib import Path  # 导入路径处理工具。
import os  # 导入环境变量读取工具。


BASE_DIR = Path(__file__).resolve().parent  # 定位研发目录。
PROJECT_ROOT = BASE_DIR.parent  # 定位工单根目录。
DEPLOY_DIR = PROJECT_ROOT / "00_部署"  # 定位部署目录。


def _read_env_file(env_path: Path) -> dict:  # 读取本地 .env 配置文件。
    env_map = {}  # 初始化环境变量映射表。
    if not env_path.exists():  # 当配置文件不存在时直接返回空映射。
        return env_map  # 返回空结果。
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():  # 逐行读取配置内容。
        line = raw_line.strip()  # 去除首尾空白字符。
        if not line or line.startswith("#") or "=" not in line:  # 跳过空行、注释与非法行。
            continue  # 继续处理下一行。
        key, value = line.split("=", 1)  # 以第一个等号拆分键值。
        env_map[key.strip()] = value.strip().strip('"').strip("'")  # 写入清洗后的键值。
    return env_map  # 返回解析后的环境变量映射。


def _pick(env_map: dict, key: str, default: str = "") -> str:  # 优先从系统环境读取配置项。
    return os.getenv(key, env_map.get(key, default))  # 返回系统环境或 .env 中的配置值。


def load_settings() -> dict:  # 加载项目运行所需的全部配置。
    env_map = _read_env_file(DEPLOY_DIR / ".env")  # 读取部署目录下的 .env 文件。
    data_dir = BASE_DIR / "data"  # 指定本地数据目录。
    upload_dir = BASE_DIR / "uploads"  # 指定上传文件目录。
    return {  # 返回统一的配置字典。
        "APP_NAME": _pick(env_map, "APP_NAME", "EduAgent Studio"),  # 设置应用名称。
        "HOST": _pick(env_map, "HOST", "127.0.0.1"),  # 设置监听地址。
        "PORT": int(_pick(env_map, "PORT", "5056")),  # 设置监听端口。
        "DEBUG": _pick(env_map, "DEBUG", "true").lower() == "true",  # 设置调试开关。
        "SECRET_KEY": _pick(env_map, "SECRET_KEY", "edu-agent-demo-secret"),  # 设置应用密钥。
        "MAX_UPLOAD_MB": int(_pick(env_map, "MAX_UPLOAD_MB", "5")),  # 设置上传大小限制。
        "DATA_DIR": str(data_dir),  # 写入数据目录路径。
        "UPLOAD_DIR": str(upload_dir),  # 写入上传目录路径。
        "COURSES_PATH": str(data_dir / "courses.json"),  # 配置课程数据文件路径。
        "KNOWLEDGE_PATH": str(data_dir / "knowledge_base.json"),  # 配置知识库文件路径。
        "STUDENTS_PATH": str(data_dir / "students.json"),  # 配置学生数据文件路径。
        "SESSIONS_PATH": str(data_dir / "sessions.json"),  # 配置会话数据文件路径。
        "ARTIFACTS_PATH": str(data_dir / "artifacts.json"),  # 配置产出记录文件路径。
        "DEEPSEEK_BASE_URL": _pick(env_map, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),  # 配置 DeepSeek 接口地址。
        "DEEPSEEK_API_KEY": _pick(env_map, "DEEPSEEK_API_KEY", ""),  # 读取 DeepSeek 密钥。
        "DEEPSEEK_MODEL": _pick(env_map, "DEEPSEEK_MODEL", ""),  # 读取 DeepSeek 模型名。
        "DEEPSEEK_VISION_MODEL": _pick(env_map, "DEEPSEEK_VISION_MODEL", ""),  # 读取 DeepSeek 多模态模型名。
        "DASHSCOPE_BASE_URL": _pick(env_map, "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),  # 配置千问兼容接口地址。
        "DASHSCOPE_API_KEY": _pick(env_map, "DASHSCOPE_API_KEY", ""),  # 读取千问密钥。
        "DASHSCOPE_TEXT_MODEL": _pick(env_map, "DASHSCOPE_TEXT_MODEL", ""),  # 读取千问文本模型名。
        "DASHSCOPE_VISION_MODEL": _pick(env_map, "DASHSCOPE_VISION_MODEL", ""),  # 读取千问多模态模型名。
        "DEFAULT_MODEL_PROVIDER": _pick(env_map, "DEFAULT_MODEL_PROVIDER", "deepseek"),  # 读取默认模型服务商。
    }  # 完成配置装载。

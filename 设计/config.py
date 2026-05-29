"""
config — ADSD 项目在线模块配置文件。

功能说明：
- 加载 .env 环境变量文件中的配置项
- 提供所有后端服务（Kimi API、BGE模型、Milvus、Redis、MySQL）的连接配置
- 定义预设的角色（Avatar）配置字典（医生、心理医生、营销专家、语文老师）
- 提供设备自动检测（GPU/CPU）和模拟模式开关
"""
# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

import os
# 导入os模块，用于与操作系统交互（如读取环境变量、文件路径操作）

from pathlib import Path
# 从pathlib导入Path类，用于更简洁、面向对象的路径操作

try:
    import torch
except Exception:
    torch = None
# 尝试导入PyTorch库，如果失败（比如未安装），则将torch设为None，避免程序崩溃

BASE_DIR = Path(__file__).resolve().parent.parent
# 获取当前文件所在目录的绝对路径（__file__是当前文件，resolve()解析符号链接，parent取父目录）

ENV_FILE = BASE_DIR / ".env"
# 拼接路径：当前目录下的.env文件，用于存储环境变量

USER_DATA_FILE = BASE_DIR / "runtime_data" / "user_accounts.json"
# 拼接路径：用户账号数据存储的JSON文件位置

API_DOCS_FILE = BASE_DIR / "API_DOCS.md"
# 拼接路径：API文档Markdown文件位置


def load_env_file(env_path: Path) -> None:
    # 定义函数：从指定路径加载.env文件内容到环境变量，参数是Path对象，无返回值

    if not env_path.exists():
        # 如果.env文件不存在
        return
        # 直接返回，不做任何操作

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        # 以UTF-8编码读取.env文件内容，按换行符分割成行，逐行遍历

        line = raw_line.strip()
        # 去除每行首尾的空白字符（空格、制表符、换行符等）

        if not line or line.startswith("#") or "=" not in line:
            # 如果行是空的，或者以#开头（注释），或者不包含等号（不是有效的键值对）
            continue
            # 跳过这一行，继续处理下一行

        key, value = line.split("=", 1)
        # 以等号分割字符串，最多分割一次，得到键和值两部分

        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        # 将键值对设置到环境变量中：
        # key.strip() 去除键两端的空白
        # value.strip() 去除值两端的空白
        # .strip('"').strip("'") 去除值两端可能存在的双引号或单引号
        # setdefault 表示如果该环境变量尚未设置，则设置它；如果已存在，则保留原值


load_env_file(ENV_FILE)
# 调用上面的函数，加载.env文件中的配置到系统环境变量

KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
# 从环境变量获取Kimi API密钥，如果不存在则默认为空字符串

KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
# 获取Kimi API基础URL，默认值为Moonshot的官方API地址

KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k")
# 获取使用的Kimi模型名称，默认是moonshot-v1-8k（上下文8千token的版本）

SECRET_KEY = os.getenv("SECRET_KEY", "rag_chat_secret_key_2024")
# 获取会话加密密钥，用于加密或签名，默认值是一个示例密钥

SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "604800"))
# 获取会话超时时间（秒），默认604800秒等于7天

USE_MOCK_MODE = not bool(KIMI_API_KEY)
# 如果KIMI_API_KEY为空（未配置），则进入模拟模式（使用假数据），否则使用真实API

# ============================================================
# 修改处：BGE模型路径改为相对路径（相对于项目根目录下的models文件夹）
# ============================================================
BGE_M3_PATH = os.getenv("BGE_M3_PATH", str(BASE_DIR / "models" / "bge-m3"))
# 获取BGE-M3嵌入模型的本地路径，默认指向项目根目录下的 models/bge-m3 文件夹

BGE_RERANKER_PATH = os.getenv("BGE_RERANKER_PATH", str(BASE_DIR / "models" / "bge-reranker-base"))
# 获取BGE重排序模型的本地路径，默认指向项目根目录下的 models/bge-reranker-base 文件夹
# ============================================================

MILVUS_HOSTS = [
    host.strip()
    for host in os.getenv("MILVUS_HOSTS", os.getenv("MILVUS_HOST", "localhost,127.0.0.1")).split(",")
    if host.strip()
]
# 获取Milvus向量数据库的主机地址列表：
# 优先取MILVUS_HOSTS环境变量，如果没有则取MILVUS_HOST，都为空则默认"localhost,127.0.0.1"
# 然后用逗号分割成列表，去除每个地址两端的空白，并过滤掉空字符串

MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
# 获取Milvus服务端口，默认19530（Milvus默认端口）

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# 获取Redis主机地址，默认localhost

REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
# 获取Redis端口号，默认6379（Redis默认端口），转换为整数

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
# 获取Redis密码，默认空字符串（无密码）

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
# 获取MySQL主机地址，默认localhost

try:
    mysql_port_str = str(os.getenv("MYSQL_PORT", "3306")).strip().rstrip(",")
    # 获取MySQL端口号，默认为"3306"，转为字符串，去除两端空白，再去除右侧可能多余的逗号
    MYSQL_PORT = int(mysql_port_str) if mysql_port_str else 3306
    # 如果处理后的字符串非空，转为整数；否则使用默认值3306
except ValueError:
    MYSQL_PORT = 3306
# 如果转换失败（比如端口号不是数字），则使用默认值3306

MYSQL_USER = os.getenv("MYSQL_USER", "root")
# 获取MySQL用户名，默认root

MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
# 获取MySQL密码，默认空字符串

MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "rag_chat_system")
# 获取要使用的MySQL数据库名，默认rag_chat_system

MYSQL_ENABLED = os.getenv("MYSQL_ENABLED", "false").lower() == "true"
# 是否启用MySQL功能：
# 获取MYSQL_ENABLED环境变量，默认"false"，转为小写，如果等于"true"则启用，否则禁用

DEVICE = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
# 设置PyTorch运行设备：
# 如果torch已成功导入并且CUDA（GPU）可用，则使用"cuda"，否则使用"cpu"

AVATARS = {
    # 定义角色头像/配置字典，包含四种预设角色
    "doctor": {
        # 医生角色配置开始
        "name": "医生",  # 角色显示名称
        "icon": "医",    # 图标文字（或emoji）
        "color": "#0f766e",  # UI主题色（深青色）
        "desc": "健康建议、日常问诊、症状分析",  # 角色描述
        "welcome": "你好，我是医生角色。你可以告诉我你的症状、持续时间和顾虑。",  # 欢迎语
        "prompt": "你是一位专业医生。请围绕用户当前的健康问题给出清晰、谨慎、易懂的建议，必要时提醒线下就医。",  # 系统提示词（指导AI行为）
        "suggestions": [  # 示例问题列表
            "我最近总头痛怎么缓解",
            "感冒发烧需要注意什么",
            "熬夜后心慌正常吗",
        ],
    },
    "psychologist": {
        # 心理医生角色配置
        "name": "心理医生",
        "icon": "心",
        "color": "#f97316",  # 橙色
        "desc": "情绪疏导、压力陪伴、关系沟通",
        "welcome": "你好，我是心理医生角色。你可以和我聊压力、焦虑、低落或关系问题。",
        "prompt": "你是一位温和、专业的心理咨询型助手。请保持共情、具体、简洁，不做医学诊断。",
        "suggestions": [
            "最近总是焦虑睡不着怎么办",
            "我和朋友关系变差了很难受",
            "情绪很低落时怎么先稳住自己",
        ],
    },
    "marketer": {
        # 营销专家角色配置
        "name": "营销专家",
        "icon": "营",
        "color": "#111827",  # 深灰色/黑色
        "desc": "品牌增长、内容策划、转化优化",
        "welcome": "你好，我是营销专家角色。你可以问我增长、定位、内容或转化问题。",
        "prompt": "你是一位懂增长和品牌策略的营销专家。请只回答用户当前营销问题，并给出可执行建议。",
        "suggestions": [
            "新品牌冷启动第一步怎么做",
            "短视频账号如何提高转化",
            "线下活动怎么做传播闭环",
        ],
    },
    "chinese_teacher": {
        # 语文老师角色配置
        "name": "语文老师",
        "icon": "文",
        "color": "#7c3aed",  # 紫色
        "desc": "课文讲解、文言文分析、阅读与写作指导",
        "welcome": "你好，我是语文老师。你可以问我课文内容、人物形象、主旨、写作手法或文言词句。",
        "prompt": "你是一位严谨、耐心的高中语文老师。请优先依据教材内容回答，语言清楚，先给结论，再给要点；涉及课文时尽量点出篇名、主旨、写作特点和依据。",
        "suggestions": [
            "《屈原列传》的主要内容和人物形象是什么",
            "《记念刘和珍君》的情感线索怎么理解",
            "《过秦论》的中心论点是什么",
        ],
    },
}
# 结束AVATARS字典定义

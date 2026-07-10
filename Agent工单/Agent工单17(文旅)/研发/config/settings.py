# 这里负责读取环境变量配置。
import os
from pathlib import Path


# 这里定义项目根目录。
BASE_DIR = Path(__file__).resolve().parent.parent
# 这里定义数据文件路径。
DATA_FILE = BASE_DIR / "data" / "spots.json"
# 这里定义静态页面目录。
STATIC_DIR = BASE_DIR / "static"
# 这里定义首页文件名。
INDEX_FILE = "index.html"
# 这里读取 DeepSeek 接口地址。
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# 这里读取 DeepSeek API 密钥。
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
# 这里读取 DeepSeek 模型名。
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
# 这里读取千问兼容接口地址。
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
# 这里读取千问 API 密钥。
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
# 这里读取千问模型名。
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-vl-max")
# 这里读取 Flask 启动端口。
FLASK_PORT = int(os.getenv("FLASK_PORT", "5057"))

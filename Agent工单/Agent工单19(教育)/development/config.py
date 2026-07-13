"""工单19：教育智能体个性化学习推荐项目的配置模块。"""

# 工单19：定义项目的基础配置。
from pathlib import Path
import os

# 工单19：导入本地环境变量加载器，支持安全接入真实模型。
from development.local_env import load_local_env

# 工单19：优先加载项目根目录中的 .env.local。
load_local_env()

# 工单19：定位研发目录，便于拼接数据库文件路径。
BASE_DIR = Path(__file__).resolve().parent

# 工单19：定位数据目录，统一存放 SQLite 数据文件。
DATA_DIR = BASE_DIR / "data"

# 工单19：定义默认数据库文件路径，并允许测试环境通过变量覆盖。
DEFAULT_DATABASE_PATH = Path(os.getenv("APP_DATABASE_PATH", str(DATA_DIR / "learning_recommendation.db")))

# 工单19：定义首选模型供应商。
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "deepseek").strip().lower()

# 工单19：定义 DeepSeek 兼容接口地址环境变量。
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# 工单19：定义 DeepSeek 接口密钥环境变量。
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 工单19：定义 DeepSeek 模型名称环境变量。
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 工单19：定义千问兼容接口地址环境变量。
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# 工单19：定义千问接口密钥环境变量。
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

# 工单19：定义千问模型名称环境变量。
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# 工单19：定义 Flask 调试开关。
DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

# 工单19：定义默认学生编号。
DEFAULT_STUDENT_ID = 1

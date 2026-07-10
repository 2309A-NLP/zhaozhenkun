"""工单18：集中加载项目配置，包含DeepSeek、千问和服务端口设置。"""
# 工单18：导入环境变量访问模块，用于读取外部配置。
import os
# 工单18：导入路径工具，用于定位项目根目录下的环境文件。
from pathlib import Path
# 工单18：导入dotenv加载函数，便于本地开发时自动读取环境变量文件。
from dotenv import load_dotenv

# 工单18：定义配置加载函数，统一返回后端需要的全部设置项。
def load_settings() -> dict:
    # 工单18：根据当前文件位置反推到项目根目录。
    project_root = Path(__file__).resolve().parents[3]
    # 工单18：优先加载部署目录中的环境变量模板或实际.env文件。
    load_dotenv(project_root / "部署" / ".env")
    # 工单18：组装统一配置字典，给Flask和服务模块直接使用。
    return {
        "APP_HOST": os.getenv("APP_HOST", "127.0.0.1"),
        "APP_PORT": int(os.getenv("APP_PORT", "5050")),
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "QWEN_BASE_URL": os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "QWEN_API_KEY": os.getenv("QWEN_API_KEY", ""),
        "QWEN_MODEL": os.getenv("QWEN_MODEL", "qwen-vl-max-latest"),
        "PROJECT_ROOT": str(project_root),
    }

# 工单20：本文件用于加载面试AI复盘项目的运行配置。
# 工单20：导入路径处理工具。
from pathlib import Path  # 工单20：代码语句。
# 工单20：导入环境变量访问工具。
import os  # 工单20：代码语句。

# 工单20：定义项目根目录。
BASE_DIR = Path(__file__).resolve().parent  # 工单20：代码语句。
# 工单20：定义部署目录。
DEPLOY_DIR = BASE_DIR.parent / "部署"  # 工单20：代码语句。
# 工单20：定义数据目录。
DATA_DIR = BASE_DIR / "data"  # 工单20：代码语句。
# 工单20：定义上传目录。
UPLOAD_DIR = BASE_DIR / "uploads"  # 工单20：代码语句。
# 工单20：定义运行目录。
RUNTIME_DIR = BASE_DIR / "runtime"  # 工单20：代码语句。

# 工单20：定义布尔值解析函数。
def _to_bool(raw_value: str, default: bool = False) -> bool:  # 工单20：代码语句。
    # 工单20：空值时返回默认值。
    if raw_value is None:  # 工单20：代码语句。
        return default  # 工单20：代码语句。
    # 工单20：统一处理大小写后判断真假。
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}  # 工单20：代码语句。

# 工单20：定义本地环境文件读取函数。
def _read_env_file() -> dict:  # 工单20：代码语句。
    # 工单20：准备候选环境文件列表。
    candidates = [DEPLOY_DIR / ".env.example", DEPLOY_DIR / ".env.local"]  # 工单20：代码语句。
    # 工单20：初始化结果字典。
    env_map = {}  # 工单20：代码语句。
    # 工单20：遍历候选环境文件。
    for env_path in candidates:  # 工单20：代码语句。
        # 工单20：跳过不存在的环境文件。
        if not env_path.exists():  # 工单20：代码语句。
            continue  # 工单20：代码语句。
        # 工单20：按行读取环境文件内容。
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():  # 工单20：代码语句。
            # 工单20：清理每行首尾空格。
            line = raw_line.strip()  # 工单20：代码语句。
            # 工单20：跳过空行和注释行。
            if not line or line.startswith("#") or "=" not in line:
                continue  # 工单20：代码语句。
            # 工单20：拆分键值对。
            key, value = line.split("=", 1)  # 工单20：代码语句。
            # 工单20：写入配置字典。
            env_map[key.strip()] = value.strip()  # 工单20：代码语句。
    # 工单20：返回读取结果。
    return env_map  # 工单20：代码语句。

# 工单20：定义配置加载函数。
def load_settings() -> dict:  # 工单20：代码语句。
    # 工单20：读取环境文件中的配置。
    env_map = _read_env_file()  # 工单20：代码语句。
    # 工单20：定义读取优先级函数。
    def pick(key: str, default: str = "") -> str:  # 工单20：代码语句。
        # 工单20：优先读取真实环境变量，其次读取本地文件。
        return os.getenv(key, env_map.get(key, default))  # 工单20：代码语句。
    # 工单20：确保运行目录存在。
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # 工单20：代码语句。
    # 工单20：确保缓存目录存在。
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)  # 工单20：代码语句。
    # 工单20：返回完整配置字典。
    return {  # 工单20：代码语句。
        "app_name": pick("APP_NAME", "面试AI复盘工单20"),  # 工单20：代码语句。
        "host": pick("APP_HOST", "127.0.0.1"),  # 工单20：代码语句。
        "port": int(pick("APP_PORT", "5020")),  # 工单20：代码语句。
        "debug": _to_bool(pick("DEBUG", "true"), True),  # 工单20：代码语句。
        "default_provider": pick("DEFAULT_PROVIDER", "deepseek"),  # 工单20：代码语句。
        "deepseek_base_url": pick("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),  # 工单20：代码语句。
        "deepseek_api_key": pick("DEEPSEEK_API_KEY", ""),  # 工单20：代码语句。
        "deepseek_model": pick("DEEPSEEK_MODEL", "deepseek-chat"),  # 工单20：代码语句。
        "qwen_base_url": pick("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),  # 工单20：代码语句。
        "qwen_api_key": pick("QWEN_API_KEY", ""),  # 工单20：代码语句。
        "qwen_text_model": pick("QWEN_TEXT_MODEL", "qwen-plus"),  # 工单20：代码语句。
        "qwen_asr_model": pick("QWEN_ASR_MODEL", "qwen3-asr-flash"),  # 工单20：代码语句。
        "max_upload_mb": int(pick("MAX_UPLOAD_MB", "20")),  # 工单20：代码语句。
        "data_dir": str(DATA_DIR),  # 工单20：代码语句。
        "upload_dir": str(UPLOAD_DIR),  # 工单20：代码语句。
        "runtime_dir": str(RUNTIME_DIR),  # 工单20：代码语句。
    }  # 工单20：代码语句。

"""工单19：加载本地环境变量文件，支持安全接入真实模型。"""

# 工单19：导入环境变量工具，用于写入当前进程配置。
import os

# 工单19：导入路径工具，用于定位项目根目录下的本地配置文件。
from pathlib import Path


# 工单19：定位项目根目录，默认从这里读取 .env.local。
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 工单19：解析单行环境变量，兼容注释与单双引号。
def parse_env_line(line):
    if not line or line.startswith("#") or "=" not in line:
        return None, None
    key, value = line.split("=", 1)
    parsed_key = key.strip()
    parsed_value = value.strip().strip('"').strip("'")
    return parsed_key, parsed_value


# 工单19：加载本地环境变量文件，但不覆盖系统中已存在的值。
def load_local_env(env_path=None):
    target_path = Path(env_path or PROJECT_ROOT / ".env.local")
    if not target_path.exists():
        return False
    for raw_line in target_path.read_text(encoding="utf-8").splitlines():
        key, value = parse_env_line(raw_line.strip())
        if key and key not in os.environ:
            os.environ[key] = value
    return True

"""该文件用于读取环境变量并生成模型与应用配置。"""

# 导入系统环境变量模块，用于读取密钥与运行参数。
import os
# 导入路径工具，用于定位项目根目录下的配置文件。
from pathlib import Path
# 导入数据类装饰器，用于组织配置对象。
from dataclasses import dataclass


# 定义模型提供方配置对象，用于保存单个模型平台参数。
@dataclass(slots=True)
class ProviderConfig:
    # 保存提供方名称，例如 deepseek 或 qwen。
    name: str
    # 保存基础接口地址。
    base_url: str
    # 保存模型名称。
    model: str
    # 保存访问接口所需的密钥。
    api_key: str


# 定义应用配置对象，用于集中保存当前应用设置。
@dataclass(slots=True)
class AppConfig:
    # 保存当前启用的模型提供方配置。
    provider: ProviderConfig
    # 保存服务默认监听主机。
    host: str
    # 保存服务默认监听端口。
    port: int


# 定义默认模型名称映射，便于缺省情况下直接启用。
DEFAULT_MODELS = {
    # 为 DeepSeek 指定默认聊天模型。
    "deepseek": "deepseek-chat",
    # 为千问兼容接口指定默认模型。
    "qwen": "qwen-plus",
}

# 定义默认基础地址映射，便于自动装配接口地址。
DEFAULT_BASE_URLS = {
    # 设置 DeepSeek 兼容接口基础地址。
    "deepseek": "https://api.deepseek.com",
    # 设置千问兼容接口基础地址。
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


# 定义环境文件加载函数，用于把本地 .env 注入当前进程环境变量。
def load_env_file() -> None:
    # 定位项目根目录，便于查找根目录下的 .env 文件。
    project_root = Path(__file__).resolve().parents[2]
    # 定义按优先级读取的环境文件列表。
    env_files = [project_root / ".env", project_root / "deploy" / ".env"]
    # 依次尝试读取每个环境文件。
    for env_file in env_files:
        # 若当前环境文件不存在，则跳过继续处理下一个。
        if not env_file.exists():
            continue
        # 按行读取文件内容，准备解析键值对。
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            # 去除当前行前后空白，降低解析噪声。
            line = raw_line.strip()
            # 跳过空行、注释行与非法格式行。
            if not line or line.startswith("#") or "=" not in line:
                continue
            # 仅按首个等号切分环境变量名称和值。
            key, value = line.split("=", 1)
            # 去除名称和值两端的多余空白与引号。
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 仅在系统环境未显式设置时写入文件中的默认值。
            os.environ.setdefault(key, value)


# 定义配置加载函数，用于从环境变量构建完整配置。
def load_config(provider_name: str | None = None) -> AppConfig:
    # 先尝试读取本地 .env 文件，确保直接运行项目时也能拿到密钥。
    load_env_file()
    # 读取用户显式传入的提供方，或回退到环境变量默认值。
    active_provider = (provider_name or os.getenv("AGENT_PROVIDER", "deepseek")).strip().lower()
    # 校验提供方是否合法，避免读取不存在的配置。
    if active_provider not in DEFAULT_MODELS:
        # 当提供方非法时，抛出明确错误提示。
        raise ValueError(f"不支持的模型提供方: {active_provider}")
    # 构造大写前缀，便于拼接环境变量名。
    env_prefix = active_provider.upper()
    # 读取基础地址，若未提供则使用项目默认值。
    base_url = os.getenv(f"{env_prefix}_BASE_URL", DEFAULT_BASE_URLS[active_provider]).strip()
    # 读取模型名称，若未提供则使用项目默认值。
    model = os.getenv(f"{env_prefix}_MODEL", DEFAULT_MODELS[active_provider]).strip()
    # 读取 API Key，允许为空，以便本地离线测试。
    api_key = os.getenv(f"{env_prefix}_API_KEY", "").strip()
    # 组装当前提供方配置对象。
    provider = ProviderConfig(
        name=active_provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
    )
    # 返回完整应用配置对象。
    return AppConfig(
        provider=provider,
        host=os.getenv("AGENT_HOST", "127.0.0.1").strip(),
        port=int(os.getenv("AGENT_PORT", "8000")),
    )

"""文件功能：集中定义项目路径、环境变量、运行参数，并初始化运行目录。"""

from __future__ import annotations  # 启用延后类型注解支持。

import os  # 读取系统环境变量。
from dataclasses import dataclass  # 定义配置数据类。
from pathlib import Path  # 处理项目目录和文件路径。
from typing import Optional  # 描述可选路径字段。


def _project_root() -> Path:  # 返回项目根目录。
    return Path(__file__).resolve().parent.parent  # 从当前文件反推项目根目录。


def _read_env_file(env_file: Path) -> dict[str, str]:  # 读取本地环境变量文件。
    values: dict[str, str] = {}  # 初始化环境变量字典。
    if not env_file.exists():  # 如果环境变量文件不存在。
        return values  # 直接返回空字典。
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():  # 逐行读取配置内容。
        line = raw_line.strip()  # 去除首尾空白字符。
        if not line or line.startswith("#") or "=" not in line:  # 跳过空行、注释行和非法行。
            continue  # 继续处理下一行。
        key, value = line.split("=", 1)  # 按第一个等号切分键和值。
        values[key.strip()] = value.strip().strip('"').strip("'")  # 保存清理后的键值。
    return values  # 返回解析后的环境变量字典。


def _pick(env_map: dict[str, str], key: str, default: str = "") -> str:  # 获取配置值。
    return os.getenv(key, env_map.get(key, default))  # 优先读取系统环境变量，再读取本地文件。


def _read_bool(value: str, default: bool) -> bool:  # 把字符串转换为布尔值。
    if not value:  # 如果没有传入有效值。
        return default  # 返回默认值。
    return value.strip().lower() in {"1", "true", "yes", "on"}  # 统一转换常见真值。


def _read_int(value: str, default: int) -> int:  # 把字符串转换为整数值。
    if not value:  # 如果没有传入有效值。
        return default  # 返回默认值。
    return int(value)  # 转换为整数。


@dataclass(slots=True)  # 使用紧凑槽位定义配置对象。
class AppSettings:  # 定义全局配置数据类。
    project_root: Path  # 保存项目根目录。
    design_dir: Path  # 保存设计层目录。
    develop_dir: Path  # 保存研发层目录。
    optimize_dir: Path  # 保存优化层目录。
    test_dir: Path  # 保存测试层目录。
    deploy_dir: Path  # 保存部署层目录。
    runtime_dir: Path  # 保存运行时目录。
    data_dir: Path  # 保存数据目录。
    uploads_dir: Path  # 保存上传文件目录。
    output_dir: Path  # 保存输出文件目录。
    app_name: str  # 保存应用名称。
    host: str  # 保存服务监听地址。
    port: int  # 保存服务监听端口。
    request_timeout: int  # 保存外部请求超时时间。
    top_k_assets: int  # 保存知识召回条数。
    max_history_messages: int  # 保存会话历史条数。
    max_context_chars: int  # 保存上下文最大字符数。
    max_upload_bytes: int  # 保存上传文件大小限制。
    use_mock_response: bool  # 标记是否使用本地模拟响应。
    ultralight_profile: str  # 保存数字人管线配置名。
    deepseek_base_url: str  # 保存 DeepSeek 接口地址。
    deepseek_model: str  # 保存 DeepSeek 模型名称。
    deepseek_api_key: str  # 保存 DeepSeek 密钥。
    qwen_base_url: str  # 保存 Qwen 接口地址。
    qwen_model: str  # 保存 Qwen 模型名称。
    qwen_api_key: str  # 保存 Qwen 密钥。
    ultralight_root: Optional[Path]  # 保存 Ultralight 官方仓库根目录。
    ultralight_python: str  # 保存 Ultralight 命令使用的 Python 启动串。
    ultralight_asr: str  # 保存 Ultralight 音频特征模式。
    ultralight_train_epochs: int  # 保存 Ultralight 训练轮数。
    ultralight_batch_size: int  # 保存 Ultralight 训练批大小。
    ultralight_audio_wav: str  # 保存固定推理音频路径。
    external_tts_command: str  # 保存外部 TTS 命令模板。

    @property  # 暴露 DeepSeek 是否可用的属性。
    def has_deepseek_credentials(self) -> bool:  # 判断 DeepSeek 凭证是否完整。
        return bool(self.deepseek_api_key and self.deepseek_base_url and self.deepseek_model)  # 返回判断结果。

    @property  # 暴露 Qwen 是否可用的属性。
    def has_qwen_credentials(self) -> bool:  # 判断 Qwen 凭证是否完整。
        return bool(self.qwen_api_key and self.qwen_base_url and self.qwen_model)  # 返回判断结果。


def load_settings() -> AppSettings:  # 加载全局配置对象。
    project_root = _project_root()  # 计算项目根目录。
    deploy_dir = project_root / "部署"  # 计算部署目录路径。
    env_map = _read_env_file(deploy_dir / ".env")  # 读取部署目录下的环境变量文件。
    runtime_root = _pick(env_map, "RUNTIME_DIR", str(deploy_dir / "runtime"))  # 读取或计算运行时目录路径。
    runtime_dir = Path(runtime_root)  # 把运行时目录转换为路径对象。
    settings = AppSettings(  # 构建完整配置对象。
        project_root=project_root,  # 保存项目根目录。
        design_dir=project_root / "设计",  # 保存设计层目录。
        develop_dir=project_root / "研发",  # 保存研发层目录。
        optimize_dir=project_root / "优化",  # 保存优化层目录。
        test_dir=project_root / "测试",  # 保存测试层目录。
        deploy_dir=deploy_dir,  # 保存部署层目录。
        runtime_dir=runtime_dir,  # 保存运行时目录。
        data_dir=runtime_dir / "data",  # 保存数据目录。
        uploads_dir=runtime_dir / "uploads",  # 保存上传目录。
        output_dir=runtime_dir / "output",  # 保存输出目录。
        app_name=_pick(env_map, "APP_NAME", "Ultralight Personal Digital Human"),  # 读取应用名称。
        host=_pick(env_map, "APP_HOST", "127.0.0.1"),  # 读取服务地址。
        port=_read_int(_pick(env_map, "APP_PORT", "8000"), 8000),  # 读取服务端口。
        request_timeout=_read_int(_pick(env_map, "REQUEST_TIMEOUT", "60"), 60),  # 读取超时时间。
        top_k_assets=_read_int(_pick(env_map, "TOP_K_ASSETS", "4"), 4),  # 读取召回条数。
        max_history_messages=_read_int(_pick(env_map, "MAX_HISTORY_MESSAGES", "8"), 8),  # 读取历史条数。
        max_context_chars=_read_int(_pick(env_map, "MAX_CONTEXT_CHARS", "2400"), 2400),  # 读取上下文长度。
        max_upload_bytes=_read_int(_pick(env_map, "MAX_UPLOAD_BYTES", "15728640"), 15728640),  # 读取上传限制。
        use_mock_response=_read_bool(_pick(env_map, "USE_MOCK_RESPONSE", "true"), True),  # 读取模拟模式。
        ultralight_profile=_pick(env_map, "ULTRALIGHT_PROFILE", "default"),  # 读取数字人配置名。
        deepseek_base_url=_pick(env_map, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),  # 读取 DeepSeek 地址。
        deepseek_model=_pick(env_map, "DEEPSEEK_MODEL", "deepseek-chat"),  # 读取 DeepSeek 模型名。
        deepseek_api_key=_pick(env_map, "DEEPSEEK_API_KEY", ""),  # 读取 DeepSeek 密钥。
        qwen_base_url=_pick(env_map, "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),  # 读取 Qwen 地址。
        qwen_model=_pick(env_map, "QWEN_MODEL", "qwen-vl-max"),  # 读取 Qwen 模型名。
        qwen_api_key=_pick(env_map, "QWEN_API_KEY", ""),  # 读取 Qwen 密钥。
        ultralight_root=Path(_pick(env_map, "ULTRALIGHT_ROOT", "")).expanduser() if _pick(env_map, "ULTRALIGHT_ROOT", "") else None,  # 读取 Ultralight 官方仓库根目录。
        ultralight_python=_pick(env_map, "ULTRALIGHT_PYTHON", "py -3"),  # 读取 Ultralight 命令的 Python 启动串。
        ultralight_asr=_pick(env_map, "ULTRALIGHT_ASR", "hubert"),  # 读取 Ultralight 音频特征模式。
        ultralight_train_epochs=_read_int(_pick(env_map, "ULTRALIGHT_TRAIN_EPOCHS", "20"), 20),  # 读取训练轮数。
        ultralight_batch_size=_read_int(_pick(env_map, "ULTRALIGHT_BATCH_SIZE", "16"), 16),  # 读取训练批大小。
        ultralight_audio_wav=_pick(env_map, "ULTRALIGHT_AUDIO_WAV", ""),  # 读取固定驱动音频路径。
        external_tts_command=_pick(env_map, "EXTERNAL_TTS_COMMAND", ""),  # 读取外部 TTS 命令模板。
    )  # 完成配置对象构建。
    return settings  # 返回配置对象。


def prepare_runtime_dirs(settings: AppSettings) -> None:  # 初始化运行所需目录。
    for path in [settings.runtime_dir, settings.data_dir, settings.uploads_dir, settings.output_dir]:  # 遍历目录列表。
        path.mkdir(parents=True, exist_ok=True)  # 确保目录存在。

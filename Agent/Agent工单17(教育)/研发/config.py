import json
import os
from functools import lru_cache
from typing import Optional, get_origin

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    SettingsConfigDict = None
    try:
        from pydantic import BaseSettings
    except Exception:
        from pydantic import BaseModel

        def _read_env_file() -> dict:
            env_path = os.path.join(_BASE_DIR, ".env")
            if not os.path.exists(env_path):
                return {}
            values = {}
            with open(env_path, "r", encoding="utf-8") as env_file:
                for raw_line in env_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
            return values

        def _normalize_settings_values(settings_cls, values: dict) -> dict:
            normalized = {}
            annotations = getattr(settings_cls, "__annotations__", {})
            for key, value in values.items():
                if key not in annotations:
                    continue
                if isinstance(value, str) and get_origin(annotations[key]) is list:
                    if value.startswith("["):
                        normalized[key] = json.loads(value)
                    else:
                        normalized[key] = [item.strip() for item in value.split(",") if item.strip()]
                else:
                    normalized[key] = value
            return normalized

        class BaseSettings(BaseModel):
            def __init__(self, **data):
                merged = _read_env_file()
                merged.update({key: value for key, value in os.environ.items() if key in self.__class__.__annotations__})
                merged.update(data)
                super().__init__(**_normalize_settings_values(self.__class__, merged))


class Settings(BaseSettings):
    APP_NAME: str = "教育Agent智能备课系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    DATABASE_URL: str = f"sqlite:///{os.path.join(_BASE_DIR, 'data', 'lesson_prep.db')}"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    JWT_SECRET_KEY: str = "edu-agent-lesson-prep-dev-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_MAX_TOKENS: int = 4096
    DEEPSEEK_TEMPERATURE: float = 0.7

    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_API_KEY: str = ""
    QWEN_MODEL: str = "qwen-vl-plus"
    QWEN_TEXT_MODEL: str = "qwen-plus"

    FAISS_INDEX_PATH: str = os.path.join(_BASE_DIR, "data", "faiss_index")
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1024
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    KNOWLEDGE_BASE_DIR: str = os.path.join(_BASE_DIR, "data", "knowledge_base")
    UPLOAD_DIR: str = os.path.join(_BASE_DIR, "data", "uploads")
    EXPORT_DIR: str = os.path.join(_BASE_DIR, "data", "exports")
    MAX_UPLOAD_SIZE_MB: int = 50

    REDIS_URL: Optional[str] = None
    CACHE_TTL_SECONDS: int = 3600

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = os.path.join(_BASE_DIR, "logs")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    CORS_ORIGINS: list = ["*"]
    RATE_LIMIT_PER_MINUTE: int = 60
    MAX_CONTENT_SIZE_MB: int = 10

    WS_HEARTBEAT_INTERVAL: int = 30
    MAX_COLLABORATORS: int = 10

    WORK_ORDER_ID: str = "人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课"
    BASE_STATIC_DIR: str = os.path.join(_BASE_DIR, "研发", "static")

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=os.path.join(_BASE_DIR, ".env"),
            env_file_encoding="utf-8",
            case_sensitive=True,
        )
    else:
        class Config:
            env_file = os.path.join(_BASE_DIR, ".env")
            env_file_encoding = "utf-8"
            case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_data_dirs() -> None:
    settings = get_settings()
    for dir_path in [
        os.path.join(_BASE_DIR, "data"),
        settings.FAISS_INDEX_PATH,
        settings.KNOWLEDGE_BASE_DIR,
        settings.UPLOAD_DIR,
        settings.EXPORT_DIR,
        settings.LOG_DIR,
    ]:
        os.makedirs(dir_path, exist_ok=True)

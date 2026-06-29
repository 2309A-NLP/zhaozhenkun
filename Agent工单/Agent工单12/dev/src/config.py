"""
src/config.py - 配置管理模块
功能: 从 YAML 文件和命令行加载系统配置，提供类型安全的配置容器。
      包括 LLM 参数、Neo4j 连接、知识图谱路径和 API 服务配置。
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import os
import yaml
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 配置数据类 — 类型安全的配置容器
# ============================================================

@dataclass
class LLMConfig:
    """大语言模型配置，对接 DeepSeek API。"""
    # API 密钥（优先从环境变量读取）
    api_key: str = ""
    # API 基础地址
    api_base: str = "https://api.deepseek.com"
    # 模型名称
    model: str = "deepseek-v4-flash"
    # 最大生成 token 数
    max_tokens: int = 1024
    # 生成温度（0-1，越低越确定）
    temperature: float = 0.1
    # 是否使用流式输出
    streaming: bool = False


@dataclass
class Neo4jConfig:
    """Neo4j 图数据库连接配置。"""
    # Neo4j 服务地址
    uri: str = "bolt://localhost:7687"
    # 用户名
    user: str = "neo4j"
    # 密码
    password: str = "12345678"
    # 数据库名
    database: str = "neo4j"


@dataclass
class KGConfig:
    """知识图谱配置。"""
    # 医疗数据 JSONL 文件路径
    data_file: str = "medical.json"
    # 批量导入大小（每批导入的疾病数）
    batch_size: int = 500


@dataclass
class ServerConfig:
    """API 服务配置。"""
    # 监听地址
    host: str = "0.0.0.0"
    # 监听端口
    port: int = 8003


@dataclass
class AppConfig:
    """应用总配置，聚合所有子模块配置。"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    kg: KGConfig = field(default_factory=KGConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


# ============================================================
# 配置加载函数
# ============================================================

def _get_env_api_key() -> str:
    """从环境变量读取 API Key，支持多个变量名。"""
    # 按优先级尝试多个环境变量名
    for env_name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"):
        key = os.environ.get(env_name, "")
        if key:
            return key
    return ""


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    从 YAML 文件和环境变量加载完整配置。

    参数:
        config_path: YAML 配置文件路径

    返回:
        完整的 AppConfig 实例
    """
    # 1. 读取 YAML 文件
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    # 2. 构建 LLM 配置（API Key 从环境变量优先）
    llm_cfg = cfg.get("llm", {})
    api_key = _get_env_api_key() or llm_cfg.get("api_key", "")
    if not api_key:
        logger.warning("未检测到 API Key，请设置 DEEPSEEK_API_KEY 环境变量")

    # 3. Neo4j 连接 — 环境变量可覆盖 YAML 配置（Docker 中需用服务名）
    neo4j_cfg = cfg.get("neo4j", {})
    neo4j_uri = os.environ.get("NEO4J_URI") or neo4j_cfg.get("uri", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER") or neo4j_cfg.get("user", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD") or neo4j_cfg.get("password", "12345678")
    neo4j_database = os.environ.get("NEO4J_DATABASE") or neo4j_cfg.get("database", "neo4j")

    # 4. 组装完整配置
    return AppConfig(
        llm=LLMConfig(
            api_key=api_key,
            api_base=llm_cfg.get("api_base", "https://api.deepseek.com"),
            model=llm_cfg.get("model", "deepseek-v4-flash"),
            max_tokens=llm_cfg.get("max_tokens", 1024),
            temperature=llm_cfg.get("temperature", 0.1),
            streaming=llm_cfg.get("streaming", False),
        ),
        neo4j=Neo4jConfig(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
            database=neo4j_database,
        ),
        kg=KGConfig(
            data_file=cfg.get("kg", {}).get("data_file", "medical.json"),
            batch_size=cfg.get("kg", {}).get("batch_size", 500),
        ),
        server=ServerConfig(
            host=cfg.get("server", {}).get("host", "0.0.0.0"),
            port=cfg.get("server", {}).get("port", 8003),
        ),
    )

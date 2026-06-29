"""
src/graph_query.py - Neo4j 图谱查询模块
功能: 执行 Cypher 查询语句，从 Neo4j 医疗知识图谱中检索数据。
      封装连接管理、查询执行和结果格式化。
      验收标准: 响应时间 < 500ms
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import logging
import time
from typing import Optional

from neo4j import GraphDatabase, Driver  # Neo4j Python 驱动
from neo4j.exceptions import ServiceUnavailable  # 连接异常

from src.config import Neo4jConfig  # Neo4j 配置

logger = logging.getLogger(__name__)


class GraphQueryExecutor:
    """
    Neo4j 图谱查询执行器。

    管理 Neo4j 连接池，执行 Cypher 查询并返回格式化结果。
    支持连接重试和超时处理。
    """

    def __init__(self, config: Neo4jConfig):
        """
        初始化查询执行器。

        参数:
            config: Neo4j 连接配置
        """
        self.config = config  # Neo4j 配置
        # Neo4j 驱动（延迟初始化）
        self._driver: Optional[Driver] = None
        # 连通性标志（避免每次查询都重试60秒）
        self._available = True  # 假设可用，首次失败后标记为不可用

    def check_connectivity(self) -> bool:
        """
        快速检查 Neo4j 是否可用（5秒超时）。
        用于决定走图谱查询还是本地 JSONL 降级。
        """
        if not self._available:
            return False  # 已标记不可用，直接返回
        try:
            driver = self._get_driver()
            driver.verify_connectivity()  # 快速验证
            self._available = True
            return True
        except Exception:
            self._available = False  # 标记不可用
            logger.info("Neo4j 不可用，启用本地 JSONL 降级检索")
            return False

    def _get_driver(self) -> Driver:
        """获取或创建 Neo4j 驱动连接。"""
        if self._driver is None:
            nc = self.config  # 配置简写
            # 创建 Neo4j 驱动
            self._driver = GraphDatabase.driver(
                nc.uri,  # bolt://localhost:7687
                auth=(nc.user, nc.password),  # 认证
                # 连接池配置：最大连接数
                max_connection_lifetime=3600,  # 1小时
                max_connection_pool_size=10,  # 最大10个连接
                connection_acquisition_timeout=10,  # 获取连接超时10秒
            )
            # 验证连接
            self._driver.verify_connectivity()
            logger.info(f"Neo4j 连接池就绪: {nc.uri}")
        return self._driver

    def close(self) -> None:
        """关闭 Neo4j 驱动，释放连接资源。"""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j 连接已关闭")

    def query(self, cypher: str, disease: str) -> list:
        """
        执行 Cypher 查询并返回结果列表。

        参数:
            cypher: Cypher 查询语句（使用 $disease 参数）
            disease: 疾病名称（绑定到查询参数）

        返回:
            查询结果列表，每条记录为一个字典；失败时返回空列表
        """
        if not cypher or not disease:
            return []  # 参数无效时返回空
        # 确保疾病名不为空
        disease = disease.strip()
        if not disease:
            return []
        start_time = time.time()  # 计时开始
        try:
            driver = self._get_driver()  # 获取驱动
            # 在只读事务中执行查询
            with driver.session(database=self.config.database) as session:
                result = session.execute_read(
                    self._do_query,  # 查询函数
                    cypher,  # Cypher 语句
                    disease,  # 疾病参数
                )
            elapsed = (time.time() - start_time) * 1000  # 耗时毫秒
            logger.debug(f"图谱查询: {len(result)} 条结果 ({elapsed:.0f}ms)")
            return result  # 返回结果列表
        except ServiceUnavailable:
            # Neo4j 服务不可用
            logger.error("Neo4j 服务不可用，请检查 Neo4j 是否已启动")
            return []
        except Exception as e:
            # 其他查询异常
            logger.error(f"图谱查询失败: {e}")
            return []

    @staticmethod
    def _do_query(tx, cypher: str, disease: str) -> list:
        """
        在事务中执行单条 Cypher 查询。

        参数:
            tx: Neo4j 事务对象
            cypher: Cypher 语句
            disease: 疾病名称参数

        返回:
            查询结果字典列表
        """
        # 标准化 Cypher 参数名：统一使用 $disease
        import re
        cypher = re.sub(r'\$name\b', '$disease', cypher)
        cypher = re.sub(r'\$diseaseName\b', '$disease', cypher)
        # 执行查询（绑定 $disease 参数）
        result = tx.run(cypher, disease=disease)
        # 将 Neo4j Record 对象转为普通字典列表
        records = []
        for record in result:
            row = {}
            for key, value in record.items():
                row[key] = GraphQueryExecutor._neo4j_to_python(value)
            records.append(row)
        return records

    @staticmethod
    def _neo4j_to_python(value):
        """递归转换 Neo4j 类型为 Python 原生类型。"""
        if value is None:
            return ""
        # Neo4j Node → dict of properties
        if hasattr(value, 'items') and hasattr(value, 'get') and not isinstance(value, (dict, str)):
            result = {}
            for k, v in value.items():
                result[k] = GraphQueryExecutor._neo4j_to_python(v)
            return result
        # list → list of converted items
        if isinstance(value, list):
            return [GraphQueryExecutor._neo4j_to_python(v) for v in value]
        # primitive types
        return value


# ============================================================
# 快捷函数 — 用于无 Neo4j 时的本地模拟查询（测试用）
# ============================================================

def mock_query(disease: str, category: str) -> str:
    """
    当 Neo4j 不可用时，从 medical.json 直接检索的模拟查询。
    用于开发和测试阶段的快速验证。

    参数:
        disease: 疾病名称
        category: 查询类别

    返回:
        模拟的查询结果文本
    """
    # 加载 JSONL 数据
    import json
    import os

    # 查找 medical.json 文件路径（兼容 Docker /app/ 和本地 Agent工单12/ 结构）
    src_dir = os.path.dirname(os.path.abspath(__file__))  # src/
    candidates = [
        os.path.join(os.path.dirname(src_dir), "medical.json"),       # dev/ or /app/
        os.path.join(os.path.dirname(os.path.dirname(src_dir)), "medical.json"),  # project root
        os.path.join(src_dir, "medical.json"),
    ]
    data_file = ""
    for c in candidates:
        if os.path.exists(c):
            data_file = c
            break
    if not data_file:
        return ""

    # 逐行搜索匹配的疾病
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # 疾病名匹配
            if obj.get("name", "") == disease:
                # 根据类别返回对应字段
                field_map = {
                    "病原体": obj.get("cause", ""),
                    "传播途径": obj.get("get_way", ""),
                    "症状": str(obj.get("symptom", "")),
                    "药物": (
                        f"药品: {obj.get('drug', '')}; "
                        f"治疗详情: {obj.get('treat_detail', '')[:1500]}"
                    ),
                    "并发症": str(obj.get("neopathy", "")),
                    "治疗": (
                        f"治疗方案: {obj.get('treat', '')}; "
                        f"治疗详情: {obj.get('treat_detail', '')[:2000]}"
                    ),
                    "预防": (
                        f"预防: {obj.get('prevent', '')}; "
                        f"护理/隔离: {obj.get('nursing', '')}"
                    ),
                    "护理": obj.get("nursing", ""),
                    "饮食": f"宜: {obj.get('can_eat', '')}; 忌: {obj.get('not_eat', '')}",
                    "科室": str(obj.get("cure_dept", "")),
                    "费用": obj.get("treat_cost", ""),
                    "周期": obj.get("treat_period", ""),
                    "概率": obj.get("treat_prob", ""),
                    "概述": obj.get("intro", ""),
                    "诊断": (
                        f"症状: {obj.get('symptom', '')}; "
                        f"简介: {obj.get('intro', '')[:500]}; "
                        f"治疗详情: {obj.get('treat_detail', '')[:1500]}"
                    ),
                }
                return field_map.get(category, obj.get("intro", ""))
    return ""

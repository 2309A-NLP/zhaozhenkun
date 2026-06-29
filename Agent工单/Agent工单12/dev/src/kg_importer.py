"""
src/kg_importer.py - Neo4j 知识图谱导入模块
功能: 将解析后的疾病实体批量导入 Neo4j 图数据库。
      创建节点约束、索引，批量写入 Disease 节点及关联实体。
      从 src/kg_builder.py 拆出，控制单文件 ≤300 行。
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import logging, time
from typing import Optional
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable
from src.models import DiseaseEntity
from src.config import AppConfig
from src.kg_builder import parse_medical_jsonl
logger = logging.getLogger(__name__)
class MedicalGraphBuilder:
    """
    医疗知识图谱构建器。
    负责连接 Neo4j、创建约束和索引、批量创建疾病节点及关联实体，
    构建完整的医疗知识图谱。
    """
    def __init__(self, config: AppConfig):
        """初始化构建器，保存配置并创建 Neo4j 驱动。"""
        self.config = config  # 应用配置
        # 创建 Neo4j 驱动（用于执行 Cypher 语句）
        self._driver: Optional[Driver] = None

    # ---- Neo4j 连接管理 ----

    def _get_driver(self) -> Driver:
        """获取或创建 Neo4j 驱动（延迟初始化）。"""
        if self._driver is None:
            nc = self.config.neo4j  # Neo4j 配置
            # 创建加密的 Neo4j 驱动连接
            self._driver = GraphDatabase.driver(
                nc.uri,  # bolt://localhost:7687
                auth=(nc.user, nc.password),  # 用户名密码认证
            )
            # 验证连接可用性
            self._driver.verify_connectivity()
            logger.info(f"Neo4j 连接成功: {nc.uri}")
        return self._driver

    def close(self) -> None:
        """关闭 Neo4j 驱动连接。"""
        if self._driver:
            self._driver.close()
            self._driver = None

    # ---- 索引和约束创建 ----

    def _create_constraints(self) -> None:
        """
        创建图数据库约束和索引，提升查询性能。

        为每个实体类型创建唯一性约束（基于 name 属性），
        确保相同名称的实体不会重复创建。
        """
        # 需要创建约束的实体标签列表
        labels = ["Disease", "Department", "Drug", "Complication",
                   "Treatment", "Symptom", "Food", "Prevention", "Nursing"]
        driver = self._get_driver()
        # 使用 execute_write 在写事务中执行
        with driver.session(database=self.config.neo4j.database) as session:
            for label in labels:
                try:
                    # 创建唯一性约束：确保每个标签的 name 属性唯一
                    session.execute_write(
                        lambda tx, lb=label: tx.run(
                            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{lb}) "
                            f"REQUIRE n.name IS UNIQUE"
                        )
                    )
                except Exception as e:
                    # 约束可能已存在，记录警告但继续
                    logger.debug(f"约束 {label} 创建: {e}")
        logger.info("索引和约束创建完成")

    # ---- 图谱清理 ----

    def clear_graph(self) -> None:
        """清空图中所有节点和关系（用于重建）。"""
        driver = self._get_driver()
        with driver.session(database=self.config.neo4j.database) as session:
            # DETACH DELETE 先删除关系再删除节点
            session.execute_write(
                lambda tx: tx.run("MATCH (n) DETACH DELETE n")
            )
        logger.info("图谱已清空")

    # ---- 批量导入 ----

    def build_from_file(self, file_path: str, clear_first: bool = True) -> int:
        """
        从 medical.json 文件构建完整的医疗知识图谱。

        参数:
            file_path: JSONL 数据文件路径
            clear_first: 是否先清空已有图谱

        返回:
            导入的疾病数量
        """
        start_time = time.time()  # 计时开始
        # 1. 解析 JSONL 数据
        diseases = parse_medical_jsonl(file_path)
        if not diseases:
            logger.error("未解析到任何疾病数据")
            return 0
        # 2. 清空旧图谱（可选）
        if clear_first:
            self.clear_graph()
        # 3. 创建约束和索引
        self._create_constraints()
        # 4. 批量导入疾病节点
        batch_size = self.config.kg.batch_size  # 每批500条
        driver = self._get_driver()
        total = len(diseases)
        for i in range(0, total, batch_size):
            batch = diseases[i:i + batch_size]  # 取一批数据
            with driver.session(database=self.config.neo4j.database) as session:
                session.execute_write(self._import_batch, batch)
            # 输出进度
            progress = min(i + batch_size, total)
            logger.info(f"导入进度: {progress}/{total} ({100*progress//total}%)")
        # 5. 输出统计
        elapsed = time.time() - start_time
        logger.info(f"图谱构建完成: {total} 种疾病, 耗时 {elapsed:.1f}s")
        return total

    @staticmethod
    def _import_batch(tx, batch: list[DiseaseEntity]) -> None:
        """
        在单个写事务中导入一批疾病及其关联实体。

        每个疾病创建 Disease 节点，并关联到对应的
        Department/Drug/Complication/Treatment/Food 等节点。

        参数:
            tx: Neo4j 事务对象
            batch: DiseaseEntity 列表
        """
        for disease in batch:
            # 跳过空名称的疾病
            if not disease.name:
                continue
            # ---- 步骤1: 创建 Disease 主节点 ----
            tx.run("""
                MERGE (d:Disease {name: $name})
                SET d.disease_id = $disease_id,
                    d.intro = $intro,
                    d.cause = $cause,
                    d.symptom = $symptom,
                    d.get_way = $get_way,
                    d.easy_get = $easy_get,
                    d.get_prob = $get_prob,
                    d.treat_prob = $treat_prob,
                    d.treat_period = $treat_period,
                    d.treat_cost = $treat_cost,
                    d.treat_detail = $treat_detail,
                    d.insurance = $insurance,
                    d.prevent = $prevent,
                    d.nursing = $nursing,
                    d.can_eat = $can_eat,
                    d.not_eat = $not_eat
            """, {
                "name": disease.name,
                "disease_id": disease.disease_id,
                "intro": disease.intro[:3000] if disease.intro else "",
                "cause": disease.cause[:5000] if disease.cause else "",
                "symptom": disease.symptom[:50] if disease.symptom else [],
                "get_way": disease.get_way,
                "easy_get": disease.easy_get,
                "get_prob": disease.get_prob,
                "treat_prob": disease.treat_prob,
                "treat_period": disease.treat_period,
                "treat_cost": disease.treat_cost,
                "treat_detail": disease.treat_detail[:5000] if disease.treat_detail else "",
                "insurance": disease.insurance,
                "prevent": disease.prevent[:1000] if disease.prevent else "",
                "nursing": disease.nursing[:1000] if disease.nursing else "",
                "can_eat": str(disease.can_eat)[:500] if disease.can_eat else "",
                "not_eat": str(disease.not_eat)[:500] if disease.not_eat else "",
            })

            # ---- 步骤2: 创建关联实体节点和关系 ----
            # 每种关联类型：遍历列表 → MERGE 目标节点 → MERGE 关系
            _merge_relations(tx, disease.name, disease.cure_dept,
                             "Department", "TREATED_BY")
            _merge_relations(tx, disease.name, disease.drug,
                             "Drug", "USES_DRUG")
            _merge_relations(tx, disease.name, disease.treat,
                             "Treatment", "TREATED_WITH")
            _merge_relations(tx, disease.name, disease.neopathy,
                             "Complication", "HAS_COMPLICATION")

            # ---- 步骤3: 症状节点 — symptom 始终为 list，逐条创建 ----
            if disease.symptom:
                for symptom_item in disease.symptom:
                    symptom_text = str(symptom_item).strip()[:200]
                    if not symptom_text:
                        continue
                    tx.run("""
                        MERGE (s:Symptom {name: $symptom_name})
                        WITH s
                        MATCH (d:Disease {name: $disease_name})
                        MERGE (d)-[:HAS_SYMPTOM]->(s)
                    """, {"symptom_name": symptom_text,
                          "disease_name": disease.name})

            # ---- 步骤4: 预防和护理（长文本字段）- ---
            if disease.prevent:
                tx.run("""
                    MERGE (p:Prevention {name: $prevent})
                    WITH p
                    MATCH (d:Disease {name: $disease_name})
                    MERGE (d)-[:HAS_PREVENTION]->(p)
                """, {"prevent": disease.prevent[:500],
                      "disease_name": disease.name})

            if disease.nursing:
                tx.run("""
                    MERGE (n:Nursing {name: $nursing})
                    WITH n
                    MATCH (d:Disease {name: $disease_name})
                    MERGE (d)-[:HAS_NURSING]->(n)
                """, {"nursing": disease.nursing[:500],
                      "disease_name": disease.name})

            # ---- 步骤5: 饮食建议 ----
            if disease.can_eat:
                _merge_food(tx, disease.name, disease.can_eat, "CAN_EAT")
            if disease.not_eat:
                _merge_food(tx, disease.name, disease.not_eat, "AVOID_EAT")


# ============================================================
# 辅助函数 — 关系和食物节点创建
# ============================================================

def _merge_relations(tx, disease_name: str, items: list,
                     label: str, rel_type: str) -> None:
    """
    批量创建 Disease 到目标实体的关系。

    参数:
        tx: Neo4j 事务
        disease_name: 疾病名称
        items: 目标实体名称列表
        label: 目标实体标签（如 Department/Drug）
        rel_type: 关系类型（如 TREATED_BY/USES_DRUG）
    """
    # 去重并过滤空值
    unique_items = list(set(i for i in items if i))
    for item_name in unique_items:
        # 截断过长的名称（Neo4j 属性值限制）
        safe_name = item_name[:200]
        # Cypher: 如果目标节点不存在则创建，然后建立关系
        tx.run(f"""
            MERGE (target:{label} {{name: $item_name}})
            WITH target
            MATCH (d:Disease {{name: $disease_name}})
            MERGE (d)-[:{rel_type}]->(target)
        """, {"item_name": safe_name, "disease_name": disease_name})


def _merge_food(tx, disease_name: str, food_text: str, rel_type: str) -> None:
    """
    创建食物节点并与疾病关联。

    参数:
        tx: Neo4j 事务
        disease_name: 疾病名称
        food_text: 食物描述文本（可能包含多个食物名称）
        rel_type: CAN_EAT 或 AVOID_EAT
    """
    # 如果食物文本包含多个食物名，取前200字符作为整体
    safe_food = food_text[:200]
    tx.run(f"""
        MERGE (f:Food {{name: $food}})
        SET f.type = $rel_type
        WITH f
        MATCH (d:Disease {{name: $disease_name}})
        MERGE (d)-[:{rel_type}]->(f)
    """, {"food": safe_food, "disease_name": disease_name,
          "rel_type": rel_type})

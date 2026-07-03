"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
Neo4j 知识图谱客户端 —— 核心连接与图谱构建
================================================================================
功能：
  1. 连接 Neo4j 图数据库
  2. 从 medical.json 自动构建知识图谱（疾病→症状/药物/科室/并发症等关系）
  3. 离线模式降级支持

图模型设计:
  节点类型:
    - Disease    疾病（name, intro, cause, prevent...）
    - Symptom    症状（name）
    - Drug       药物（name）
    - Department 科室（name）
    - Complication 并发症（name）
    - Food       食物（name, type: can_eat/not_eat）

  关系类型:
    - [:HAS_SYMPTOM]     疾病→症状
    - [:TREATED_WITH]    疾病→药物
    - [:BELONGS_TO]      疾病→科室
    - [:HAS_COMPLICATION] 疾病→并发症
    - [:CAUSED_BY]       疾病→病原体
    - [:TRANSMITTED_BY]  疾病→传播途径
    - [:PREVENTED_BY]    疾病→预防措施
    - [:CAN_EAT]         疾病→宜吃食物
    - [:AVOID_EAT]       疾病→忌吃食物
    - [:NEEDS_NURSING]   疾病→护理要点
    - [:DIAGNOSED_BY]    疾病→诊断方法
================================================================================
"""
import os, json, re, logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

_log = logging.getLogger("medical_agent.kg.neo4j")

# ============================================================
# Neo4j 连接配置
# ============================================================
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# medical.json 路径
_KG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "medical.json"

class Neo4jClient:
    """
    Neo4j 医疗知识图谱客户端

    支持两种模式:
      1. 连接真实 Neo4j 实例（需 NEO4J_URI 环境变量）
      2. 离线模式（使用内存中的 Python 字典模拟图查询）
    """

    def __init__(self):
        self._driver = None
        self._connected = False
        self._offline_data: Dict[str, Dict] = {}  # 离线模式下的疾病索引
        self._init_connection()

    def _init_connection(self):
        """尝试连接 Neo4j，失败则降级为离线模式"""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            # 验证连接
            with self._driver.session(database=NEO4J_DATABASE) as session:
                session.run("RETURN 1")
            self._connected = True
            _log.info("✅ Neo4j 已连接: %s", NEO4J_URI)
        except ImportError:
            _log.warning("⚠ neo4j 驱动未安装，使用离线模式。安装: pip install neo4j")
            self._load_offline()
        except Exception as e:
            _log.warning("⚠ Neo4j 连接失败 (%s)，使用离线模式", e)
            self._load_offline()

    def _load_offline(self):
        """离线模式：从 medical.json 加载数据到内存索引"""
        if self._offline_data:
            return
        if _KG_PATH.exists():
            with open(_KG_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            self._offline_data[d.get("name", "")] = d
                        except json.JSONDecodeError:
                            pass
            _log.info("离线模式已加载 %d 种疾病", len(self._offline_data))

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ================================================================
    # 知识图谱构建（从 medical.json 导入 Neo4j）
    # ================================================================
    def build_graph(self, force: bool = False) -> Dict:
        """从 medical.json 构建 Neo4j 知识图谱，返回 {"success": bool, "stats": dict}"""
        if not self._connected:
            return {"success": False, "error": "Neo4j 未连接，无法构建图谱。请先配置 NEO4J_URI 环境变量。"}

        if not _KG_PATH.exists():
            return {"success": False, "error": f"medical.json 不存在: {_KG_PATH}"}

        stats = {"diseases": 0, "symptoms": 0, "drugs": 0, "departments": 0,
                 "complications": 0, "relations": 0}

        with self._driver.session(database=NEO4J_DATABASE) as session:
            # 清空旧数据（如果 force=True）
            if force:
                session.run("MATCH (n) DETACH DELETE n")

            # 创建约束
            for label in ["Disease", "Symptom", "Drug", "Department",
                          "Complication", "Pathogen", "Transmission",
                          "Prevention", "Nursing", "Food", "Diagnosis"]:
                try:
                    session.run(f"CREATE CONSTRAINT IF NOT EXISTS "
                                f"FOR (n:{label}) REQUIRE n.name IS UNIQUE")
                except Exception:
                    pass  # 约束可能已存在

            # 解析并导入数据
            with open(_KG_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    name = d.get("name", "")
                    if not name:
                        continue
                    stats["diseases"] += 1

                    # 创建 Disease 节点（含属性）
                    session.run("""
                        MERGE (d:Disease {name: $name})
                        SET d.intro = $intro, d.cause = $cause, d.prevent = $prevent,
                            d.treat = $treat, d.treat_detail = $treat_detail,
                            d.treat_period = $treat_period, d.get_prob = $get_prob,
                            d.insurance = $insurance
                    """, name=name,
                        intro=d.get("intro", ""),
                        cause=d.get("cause", ""),
                        prevent=d.get("prevent", ""),
                        treat=d.get("treat", ""),
                        treat_detail=d.get("treat_detail", ""),
                        treat_period=d.get("treat_period", ""),
                        get_prob=d.get("get_prob", ""),
                        insurance=d.get("insurance", ""))

                    for s in self._split_value(d.get("symptom", "")):
                        session.run("""
                            MERGE (s:Symptom {name: $sname})
                            WITH s
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:HAS_SYMPTOM]->(s)
                        """, sname=s, dname=name)
                        stats["symptoms"] += 1; stats["relations"] += 1

                    for dr in self._split_value(d.get("drug", "")):
                        session.run("""
                            MERGE (dr:Drug {name: $drname})
                            WITH dr
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:TREATED_WITH]->(dr)
                        """, drname=dr, dname=name)
                        stats["drugs"] += 1; stats["relations"] += 1

                    dept = d.get("cure_dept", "")
                    if dept:
                        session.run("""
                            MERGE (dept:Department {name: $dept})
                            WITH dept
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:BELONGS_TO]->(dept)
                        """, dept=dept, dname=name)
                        stats["departments"] += 1; stats["relations"] += 1

                    for c in self._split_value(d.get("neopathy", "")):
                        session.run("""
                            MERGE (c:Complication {name: $cname})
                            WITH c
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:HAS_COMPLICATION]->(c)
                        """, cname=c, dname=name)
                        stats["complications"] += 1; stats["relations"] += 1

                    cause = d.get("cause", "")
                    if cause:
                        session.run("""
                            MERGE (p:Pathogen {name: $cause})
                            WITH p
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:CAUSED_BY]->(p)
                        """, cause=cause, dname=name)
                        stats["relations"] += 1

                    get_way = d.get("get_way", "")
                    if get_way:
                        session.run("""
                            MERGE (t:Transmission {name: $way})
                            WITH t
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:TRANSMITTED_BY]->(t)
                        """, way=get_way, dname=name)
                        stats["relations"] += 1

                    for p in self._split_value(d.get("prevent", "")):
                        session.run("""
                            MERGE (pr:Prevention {name: $pname})
                            WITH pr
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:PREVENTED_BY]->(pr)
                        """, pname=p, dname=name)
                        stats["relations"] += 1

                    for n in self._split_value(d.get("nursing", "")):
                        session.run("""
                            MERGE (nu:Nursing {name: $nname})
                            WITH nu
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:NEEDS_NURSING]->(nu)
                        """, nname=n, dname=name)
                        stats["relations"] += 1

                    for food in self._split_value(d.get("can_eat", "")):
                        session.run("""
                            MERGE (f:Food {name: $food, type: 'can_eat'})
                            WITH f
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:CAN_EAT]->(f)
                        """, food=food, dname=name)
                        stats["relations"] += 1
                    for food in self._split_value(d.get("not_eat", "")):
                        session.run("""
                            MERGE (f:Food {name: $food, type: 'not_eat'})
                            WITH f
                            MATCH (d:Disease {name: $dname})
                            MERGE (d)-[:AVOID_EAT]->(f)
                        """, food=food, dname=name)
                        stats["relations"] += 1

        _log.info("知识图谱构建完成: %s", stats)
        return {"success": True, "stats": stats}

    # ================================================================
    # 工具函数
    # ================================================================
    @staticmethod
    def _split_value(val) -> List[str]:
        """将字符串/列表/dict 拆分为列表（处理 medical.json 的多种格式）"""
        if isinstance(val, str):
            # 按常见分隔符拆分
            parts = re.split(r'[,;；，、\n]+', val)
            return [p.strip() for p in parts if len(p.strip()) >= 2]
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        if isinstance(val, dict):
            return [str(v).strip() for v in val.values() if str(v).strip()]
        return []

    def close(self):
        """关闭 Neo4j 连接"""
        if self._driver:
            self._driver.close()
            self._connected = False

# ================================================================
# 全局单例
# ================================================================
_neo4j: Optional[Neo4jClient] = None

def get_neo4j_client() -> Neo4jClient:
    """获取 Neo4j 客户端单例"""
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
    return _neo4j

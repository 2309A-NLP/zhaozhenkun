"""
实体关系提取模块（LightRAG 核心）
功能：使用 LLM 从文本块中提取结构化实体和关系，支持增量合并去重
完成：分批调用 MiMo API，提取实体类型/名称/描述和关系类型/描述
"""
import logging
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json  # JSON 处理

from llm_client import call_llm_json  # LLM JSON 调用
import config  # 批处理参数

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


# ======================== 招股说明书专用实体/关系类型体系 ========================
# 根据 PDF 工单要求：针对招股说明书内容优化实体和关系类型，
# 抽取出准确的实体类型和关系类型

# 实体类型细化（金融/IPO 招股书专用）：
#   公司/机构类：发行人、控股股东、实际控制人、保荐机构、会计师事务所、
#               律师事务所、资产评估机构、子公司、参股公司、竞争对手
#   人物类：董事、监事、高管、核心技术人才、法定代表人
#   产品/业务类：主营产品、核心技术、业务板块、募投项目
#   财务类：营业收入、净利润、资产负债率、每股收益、募集资金、
#            发行股数、注册资本、研发投入
#   行业类：上下游行业、目标市场、应用领域
#   标准/法规类：行业标准、技术规范、法律法规、资质认证
#   地点类：注册地、生产基地、销售区域
#   事件/项目类：募投项目、研发项目、获奖工程、参股事件

# 关系类型细化（金融/IPO 招股书专用）：
#   股权类：控股、参股、持有股份、一致行动、实际控制
#   人事类：担任职务、委派、聘任
#   业务类：供应、采购、销售、合作、竞争、服务
#   财务类：募投、审计、评估、验资、发行、承销保荐
#   法律类：法律顾问、合规审查、法规适用
#   技术类：参与制定、自主研发、技术授权、专利权属
#   归属类：属于（行业/领域）、位于（地点）、构成（组织结构）
#   制度类：制定标准、遵循法规、获得认证

SYSTEM_PROMPT = """你是一个专业的IPO招股说明书实体关系提取专家。
从招股说明书文本中提取所有重要实体及关系。

实体类型（请根据招股书内容精确分类）：
- 发行人：拟上市的公司主体
- 控股股东/实际控制人：控制发行人的主体或个人
- 关联方/子公司/参股公司：与发行人存在股权或业务关系的企业
- 中介机构：保荐机构、会计师事务所、律师事务所、资产评估机构等
- 高管/核心人员：董事、监事、高管、核心技术人才、法定代表人
- 主营业务/产品：发行人的主营产品或服务
- 核心技术/专利：发行人拥有的核心技术、专利、商标
- 募投项目：本次发行募集资金拟投资的项目
- 财务指标：营业收入、净利润、每股收益、募集资金金额、发行股数、注册资本
- 行业/市场：发行人所属的行业、上下游行业、目标市场、应用领域
- 标准/资质：行业标准、技术规范、资质认证、法律法规
- 地点/区域：注册地、生产基地、销售区域
- 获奖/荣誉：公司获得的奖项、荣誉称号、重大工程参与

关系类型（请根据招股书内容精确分类）：
- 控股/实际控制：股权控制关系
- 参股/持有股份：非控制的持股关系
- 一致行动：一致行动协议关系
- 关联关系：关联方关系
- 担任职务：人在公司中的任职关系
- 保荐/承销：中介机构对发行人的保荐承销服务
- 审计/评估/验资：中介机构提供的专业服务
- 法律顾问：律师事务所提供的法律服务
- 供应/采购：业务上下游供应采购关系
- 销售/客户：销售渠道和客户关系
- 合作/竞争：业务合作或竞争关系
- 募投：募集资金与投资项目的关系
- 所属行业/领域：企业归属的行业或领域
- 位于/注册：公司或机构的地点归属
- 构成/下属：组织结构的层级关系
- 参与制定：参与技术标准制定
- 获得/拥有：获得奖项、资质、认证或拥有专利
- 发行：股票发行相关关系

返回 JSON 格式：
{
  "entities": [{"name": "实体全名", "type": "实体类型", "description": "在招股书中的角色描述"}],
  "relations": [{"source": "源实体全名", "target": "目标实体全名", "type": "关系类型", "description": "关系的具体说明"}]
}

关键规则：
1. 实体名称必须完整准确，如"武汉力源信息技术股份有限公司"不能简写为"力源信息"
2. 关系必须是文本中明确提到的，不要编造
3. 实体类型和关系类型必须从上述分类中选择
4. 如果出现不属于上述分类但确实重要的实体/关系，可以标注为"其他"
5. 每个实体需要给出描述说明其在招股书中的角色"""

# 批量提取系统提示词：一次处理多个文本块
BATCH_SYSTEM_PROMPT = """你是一个专业的IPO招股说明书实体关系提取专家。
下面给你多个文本块（每个有编号），请逐个提取其中的实体和关系。

实体类型（请根据招股书内容精确分类）：
- 发行人：拟上市的公司主体
- 控股股东/实际控制人：控制发行人的主体或个人
- 关联方/子公司/参股公司：与发行人存在股权或业务关系的企业
- 中介机构：保荐机构、会计师事务所、律师事务所、资产评估机构等
- 高管/核心人员：董事、监事、高管、核心技术人才、法定代表人
- 主营业务/产品：发行人的主营产品或服务
- 核心技术/专利：发行人拥有的核心技术、专利、商标
- 募投项目：本次发行募集资金拟投资的项目
- 财务指标：营业收入、净利润、每股收益、募集资金金额、发行股数、注册资本
- 行业/市场：发行人所属的行业、上下游行业、目标市场、应用领域
- 标准/资质：行业标准、技术规范、资质认证、法律法规
- 地点/区域：注册地、生产基地、销售区域
- 获奖/荣誉：公司获得的奖项、荣誉称号、重大工程参与

关系类型：
- 控股/实际控制、参股/持有股份、一致行动、关联关系、担任职务
- 保荐/承销、审计/评估/验资、法律顾问
- 供应/采购、销售/客户、合作/竞争
- 募投、所属行业/领域、位于/注册、构成/下属
- 参与制定、获得/拥有、发行

返回 JSON 格式（按文本块编号组织）：
{
  "batch_0": {"entities": [...], "relations": [...]},
  "batch_1": {"entities": [...], "relations": [...]},
  ...
}

关键规则：
1. 实体名称必须完整准确，不能简写
2. 关系必须是文本中明确提到的，不要编造
3. 实体类型和关系类型必须从上述分类中选择
4. 每个文本块独立提取"""


def extract_from_chunk(chunk: dict) -> dict:
    """
    从单个文本块中提取实体和关系
    参数：
        chunk: {"chunk_id", "text", "source_pdf", "page_num"}
    返回：
        {"chunk_id", "entities": [...], "relations": [...]}
    """
    prompt = (
        f"来源：{chunk['source_pdf']} 第{chunk['page_num']}页\n\n"
        f"文本：\n{chunk['text']}"
    )
    try:
        result = call_llm_json(prompt, SYSTEM_PROMPT, temperature=0.1)
    except Exception as e:
        print(f"  ⚠️ chunk[{chunk['chunk_id']}] 提取失败: {e}")
        result = {"entities": [], "relations": []}

    return {
        "chunk_id": chunk["chunk_id"],
        "entities": result.get("entities", []),
        "relations": result.get("relations", [])
    }


def extract_batch_chunks(batch_chunks: list[dict]) -> list[dict]:
    """
    批量提取：多个 chunk 合并到一次 API 调用
    参数：
        batch_chunks: 文本块列表（建议 3【报错】~5 个）
    返回：
        提取结果列表，与 extract_from_chunk 同格式
    """
    # 构建批量 prompt：每个 chunk 带编号
    parts = []
    for i, ch in enumerate(batch_chunks):
        parts.append(
            f"[batch_{i}] 来源：{ch['source_pdf']} 第{ch['page_num']}页\n"
            f"文本：\n{ch['text']}\n"
        )
    prompt = "\n---\n".join(parts)

    try:
        result = call_llm_json(prompt, BATCH_SYSTEM_PROMPT, temperature=0.1)
    except Exception as e:
        print(f"  ⚠️ 批次提取失败: {e}")
        result = {}

    # 解析批量结果
    outputs = []
    for i, ch in enumerate(batch_chunks):
        key = f"batch_{i}"
        batch_data = result.get(key, {})
        outputs.append({
            "chunk_id": ch["chunk_id"],
            "entities": batch_data.get("entities", []),
            "relations": batch_data.get("relations", [])
        })
    return outputs


def extract_all_chunks(chunks: list[dict], max_chunks: int = 0) -> list[dict]:
    """
    批量提取所有 chunk 的实体和关系
    参数：
        chunks: 文本块列表
        max_chunks: 最多处理数（0=全部）
    返回：提取结果列表
    """
    if max_chunks > 0:
        chunks = chunks[:max_chunks]

    results = []
    total = len(chunks)
    batch_size = config.ENTITY_BATCH_SIZE
    print(f"🔍 提取 {total} 个 chunk 的实体/关系...")

    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  批次 {batch_num}/{(total + batch_size - 1)//batch_size}")

        # 使用批量提取（一次 API 调用处理多个 chunk）
        batch_results = extract_batch_chunks(batch)
        results.extend(batch_results)

    entities = sum(len(r["entities"]) for r in results)
    relations = sum(len(r["relations"]) for r in results)
    print(f"✅ 提取完成: {entities} 实体, {relations} 关系")
    return results


def merge_extractions(extractions: list[dict]) -> dict:
    """
    合并所有提取结果，去重
    返回：{"entities": [...], "relations": [...]}
    """
    # 以名称为 key 去重实体（兼容字符串和字典两种格式）
    entity_dict = {}
    for ext in extractions:
        for ent in ext["entities"]:
            # 处理实体可能是字符串的情况（API 返回格式不稳定）
            if isinstance(ent, str):
                name = ent.strip()
                ent_type = "未知"
                desc = ""
            else:
                name = ent.get("name", "").strip()
                ent_type = ent.get("type", "未知")
                desc = ent.get("description", "")
            if name and name not in entity_dict:
                entity_dict[name] = {
                    "name": name,
                    "type": ent_type,
                    "description": desc
                }

    # 以 (source, target, type) 去重关系（兼容列表和字典格式）
    seen = set()
    unique_relations = []
    for ext in extractions:
        for rel in ext["relations"]:
            # 跳过非字典非列表的异常数据
            if isinstance(rel, str):
                continue
            # 处理关系可能是列表的情况
            if isinstance(rel, list):
                src = str(rel[0]) if len(rel) > 0 else ""
                tgt = str(rel[1]) if len(rel) > 1 else ""
                rtype = str(rel[2]) if len(rel) > 2 else "相关"
                desc = str(rel[3]) if len(rel) > 3 else ""
                rel = {"source": src, "target": tgt, "type": rtype, "description": desc}
            key = (rel.get("source", ""), rel.get("target", ""), rel.get("type", ""))
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)

    print(f"📊 合并后: {len(entity_dict)} 唯一实体, {len(unique_relations)} 唯一关系")
    return {"entities": list(entity_dict.values()), "relations": unique_relations}

"""
entity_graph_builder.py - RAG工单8 实体提取与知识图谱构建模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 使用DeepSeek从CCF年报文本中提取金融实体(公司/人物/指标等)
      和关系，构建NetworkX知识图谱用于GraphRAG检索
"""

import logging, json, time, re
from collections import defaultdict
from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_ENTITY_MODEL, \
    OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("entity_graph_builder")

# API调用缓存，避免重复提取相同文本
_extraction_cache = {}


def extract_entities_relations(text, chunk_index=0):
    """
    使用DeepSeek从文本块中提取实体和关系
    Args:
        text: 文本块内容
        chunk_index: 文本块索引(用于追踪来源)
    Returns:
        dict: {"entities": [{"name","type","chunk_index"}],
               "relations": [{"source","target","relation","chunk_index"}]}
    """
    cache_key = text[:100]
    if cache_key in _extraction_cache:
        return _extraction_cache[cache_key]

    prompt = f"""从以下金融年报文本中提取具体的金融实体和关系。
实体类型: 公司(如平安银行、招商银行), 人物(如董事长、CEO姓名), 产品(如信用卡、理财产品), 指标(如营业收入、净利润、不良贷款率)
关系类型: 属于, 担任, 发布, 增长, 下降, 投资, 合作, 控股

注意:
- 只提取有具体名称的实体，不要提取"释义""目录"等通用词
- 公司名要完整，如"平安银行股份有限公司"简称"平安银行"
- 数值型指标请标注具体数字，如"营业收入1379.58亿元"

返回JSON格式(不要其他文字):
{{"entities":[{{"name":"具体实体名","type":"公司|人物|产品|指标"}}],
  "relations":[{{"source":"实体名","relation":"关系类型","target":"实体名"}}]}}

文本:{text[:1500]}"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL)
        resp = client.chat.completions.create(
            model=MIMO_ENTITY_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=1000)
        msg = resp.choices[0].message
        result_text = (msg.content or msg.reasoning_content or "").strip()
        if '{' in result_text:
            try:
                result_text = result_text[result_text.index('{'):result_text.rindex('}') + 1]
                data = json.loads(result_text)
                # 检测模板回显：如果实体名包含占位符则视为失败
                entities = data.get("entities", [])
                if any("实体名" in e.get("name", "") or "关系类型" in e.get("name", "") for e in entities):
                    data = {"entities": [], "relations": []}
            except Exception:
                data = {"entities": [], "relations": []}
        else:
            data = {"entities": [], "relations": []}
    except Exception as e:
        logger.warning(f"提取失败(chunk{chunk_index}): {e}")
        data = {"entities": [], "relations": []}

    for e in data.get("entities", []):
        e["chunk_index"] = chunk_index
    for r in data.get("relations", []):
        r["chunk_index"] = chunk_index

    _extraction_cache[cache_key] = data
    return data


class GraphBuilder:
    """基于NetworkX的金融知识图谱构建器"""

    def __init__(self):
        self.graph = None  # NetworkX图对象
        self.entity_to_chunks = defaultdict(set)  # 实体→所属chunk索引
        self._built = False

    def build_from_chunks(self, chunks, max_chunks=30):
        """
        从文本块中提取实体关系并构建知识图谱
        智能采样：跳过目录/释义等模板内容，从多个PDF中均匀采样
        Args:
            chunks: 文本块列表
            max_chunks: 最大处理块数(控制API消耗)
        """
        import networkx as nx
        self.graph = nx.Graph()
        # 智能采样：跳过每个PDF的前10个chunk（通常是目录/释义）
        # 优先选取包含数字和较长文本的chunk（更可能含金融实体）
        from collections import defaultdict as dd
        pdf_chunks = dd(list)
        for c in chunks:
            pdf_chunks[c.get("source_pdf", "")].append(c)
        candidates = []
        for pdf_name, pdf_c in pdf_chunks.items():
            # 跳过前10个chunk（目录/释义/封面）
            for c in pdf_c[10:]:
                text = c["content"]
                # 优先选含数字的chunk（更可能有财务数据）
                score = len(text) + text.count("亿") * 100 + text.count("万") * 50
                candidates.append((score, c))
        # 按分数降序，取前max_chunks个
        candidates.sort(key=lambda x: x[0], reverse=True)
        selected = [c for _, c in candidates[:max_chunks]]
        logger.info(f"构建知识图谱(智能采样{len(selected)}/共{len(chunks)}块)...")
        for chunk in selected:
            text = chunk["content"]
            data = extract_entities_relations(text, chunk["index"])
            for ent in data.get("entities", []):
                name = ent["name"].strip()
                # 过滤掉太短或太通用的实体名
                if not name or len(name) < 2:
                    continue
                etype = ent.get("type", "未知")
                self.graph.add_node(name, type=etype, source_pdf=chunk.get("source_pdf", ""))
                self.entity_to_chunks[name].add(chunk["index"])
            for rel in data.get("relations", []):
                src = rel.get("source", "").strip()
                tgt = rel.get("target", "").strip()
                rtype = rel.get("relation", "相关")
                if src and tgt and len(src) >= 2 and len(tgt) >= 2:
                    self.graph.add_edge(src, tgt, relation=rtype)
        self._built = True
        logger.info(f"图谱构建完成! {self.graph.number_of_nodes()}节点, "
                     f"{self.graph.number_of_edges()}条边")

    def save(self):
        """保存图结构和实体映射到文件"""
        if not self._built:
            return
        nodes = [{"name": n, "type": d.get("type", "未知"),
                  "source_pdf": d.get("source_pdf", "")}
                 for n, d in self.graph.nodes(data=True)]
        edges = [{"source": u, "target": v, "relation": d.get("relation", "相关")}
                 for u, v, d in self.graph.edges(data=True)]
        data = {"nodes": nodes, "edges": edges,
                "entity_to_chunks": {k: list(v) for k, v in self.entity_to_chunks.items()}}
        path = OUTPUT_DIR / "knowledge_graph.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"知识图谱已保存: {path}")

    def get_related_entities(self, entity_name, max_hops=2):
        """
        获取实体的关联实体(子图扩展)
        Args:
            entity_name: 实体名称
            max_hops: 最多扩展跳数
        Returns:
            list: 关联实体名称列表
        """
        if not self._built or entity_name not in self.graph:
            return []
        visited = {entity_name}
        queue = [(entity_name, 0)]
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_hops:
                continue
            for neighbor in self.graph.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return list(visited)

    def get_graph_data(self):
        """返回前端可用的图谱数据"""
        if not self._built:
            return {"nodes": [], "edges": [], "entity_to_chunks": {}}
        nodes = [{"name": n, "type": d.get("type", "未知"),
                  "source_pdf": d.get("source_pdf", "")}
                 for n, d in self.graph.nodes(data=True)]
        edges = [{"source": u, "target": v, "relation": d.get("relation", "相关")}
                 for u, v, d in self.graph.edges(data=True)]
        return {"nodes": nodes, "edges": edges,
                "entity_to_chunks": {k: list(v) for k, v in self.entity_to_chunks.items()}}


if __name__ == "__main__":
    """单独测试实体提取和图谱构建"""
    test_text = "平安银行2019年实现营业收入1379亿元，董事长谢永林出席发布会。"
    data = extract_entities_relations(test_text)
    print(json.dumps(data, ensure_ascii=False, indent=2))

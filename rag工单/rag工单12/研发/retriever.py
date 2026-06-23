"""
双模式检索模块（RAG vs LightRAG — 研发层核心）
功能：实现 RAG（纯向量余弦检索）和 LightRAG（向量+图谱增强）两种检索策略
完成：RAG 纯向量 top_k、LightRAG 局部向量+全局图谱 BFS 扩展混合检索、关键词匹配
"""
import logging
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # 向量运算（余弦相似度、top_k 排序）

from embedder import cosine_similarity                          # 余弦相似度计算
from graph_builder import find_entity, expand_neighbors         # 图谱查询 + BFS 扩展

import config  # 检索参数（top_k / hops）

logger = logging.getLogger(__name__)
logger.info("检索模块加载")

logger = logging.getLogger(__name__)


def rag_retrieve(
    query_vec: np.ndarray,
    vectors: np.ndarray,
    chunk_meta: list[dict],
    top_k: int = None
) -> list[dict]:
    """
    RAG 模式：纯向量余弦相似度检索（Baseline 对照）
    参数：
        query_vec:  查询问题的 BGE-M3 向量 (hidden_dim,)
        vectors:    所有文本块的向量矩阵 (N, hidden_dim)
        chunk_meta: 每个向量对应的元数据 [{"chunk_id", "source_pdf", "page_num"}, ...]
        top_k:      返回前 k 个最相似结果（默认从 config 读取）
    返回：
        [{"chunk_id", "source_pdf", "page_num", "text", "score"}, ...]
        score 为余弦相似度（归一化后等价于点积）
    """
    if top_k is None:
        top_k = config.VECTOR_TOP_K  # 默认取配置值

    # 计算查询向量与所有文档向量的余弦相似度（向量已归一化，直接点积）
    scores = cosine_similarity(query_vec, vectors)

    # 获取 top_k 的索引（按分数降序排列）
    top_indices = np.argsort(scores)[::-1][:top_k]

    # 组装检索结果（text 字段由调用者后续填充）
    results = []
    for idx in top_indices:
        results.append({
            "chunk_id": chunk_meta[idx]["chunk_id"],     # 文本块 ID
            "source_pdf": chunk_meta[idx]["source_pdf"], # 来源 PDF 文件名
            "page_num": chunk_meta[idx]["page_num"],     # 页码
            "text": "",                                   # text 字段留空（调用者填充）
            "score": float(scores[idx])                   # 相似度分数（float 便于 JSON 序列化）
        })
    return results


def lightrag_retrieve(
    query_vec: np.ndarray,
    vectors: np.ndarray,
    chunk_meta: list[dict],
    chunks: list[dict],
    graph: "nx.DiGraph",
    query_text: str,
    top_k_local: int = None,
    top_k_global: int = None
) -> list[dict]:
    """
    LightRAG 模式：局部向量检索 + 全局图谱增强检索（双通路混合）
    参数：
        query_vec:     查询向量
        vectors:       所有文本块向量矩阵
        chunk_meta:    向量元数据
        chunks:        完整文本块列表（含 text 字段，用于图谱匹配后检索原文）
        graph:         NetworkX 知识图谱
        query_text:    原始查询文本（用于在图谱中匹配实体关键词）
        top_k_local:   局部向量检索返回数（默认 config.LIGHTRAG_LOCAL_K）
        top_k_global:  全局图谱检索返回数（默认 config.LIGHTRAG_GLOBAL_K）
    返回：
        去重且按分数排序的检索结果列表（每条含 source 标记：local_vector / global_graph）
    """
    if top_k_local is None:
        top_k_local = config.LIGHTRAG_LOCAL_K
    if top_k_global is None:
        top_k_global = config.LIGHTRAG_GLOBAL_K

    # ======== 通路一：局部检索（纯向量相似度） ========
    local_scores = cosine_similarity(query_vec, vectors)       # 全部相似度分数
    local_indices = np.argsort(local_scores)[::-1][:top_k_local]  # top_k 索引

    local_chunk_ids = set()  # 已选中的 chunk_id（用于后续去重）
    local_results = []       # 局部检索结果

    for idx in local_indices:
        chunk_id = chunk_meta[idx]["chunk_id"]
        local_chunk_ids.add(chunk_id)  # 记录已选
        # 从完整 chunks 中匹配文本内容
        text = _find_chunk_text(chunks, chunk_id)
        local_results.append({
            "chunk_id": chunk_id,
            "source_pdf": chunk_meta[idx]["source_pdf"],
            "page_num": chunk_meta[idx]["page_num"],
            "text": text,
            "score": float(local_scores[idx]),   # 余弦相似度
            "source": "local_vector"              # 标记为局部检索来源
        })

    # ======== 通路二：全局检索（知识图谱扩展） ========
    # 从查询文本中匹配图谱实体关键词
    matched_entities = _extract_keywords_from_query(query_text, graph)

    global_results = []  # 全局检索结果
    if matched_entities:
        # BFS 扩展邻居：从匹配实体出发沿关系扩散
        expanded = expand_neighbors(graph, matched_entities,
                                    hops=config.GRAPH_EXPAND_HOPS)

        # 收集扩展后所有实体的名称集合
        expanded_names = set()
        for nid in expanded:
            node_data = graph.nodes[nid]
            expanded_names.add(node_data.get("name", ""))

        # 在所有 chunk 中查找包含这些实体名称的文本块
        for ch in chunks:
            if ch["chunk_id"] in local_chunk_ids:
                continue  # 跳过局部检索已覆盖的块
            text = ch["text"]
            for name in expanded_names:
                if name and name in text:  # 实体名称出现在文本中
                    global_results.append({
                        "chunk_id": ch["chunk_id"],
                        "source_pdf": ch["source_pdf"],
                        "page_num": ch["page_num"],
                        "text": text[:config.CHUNK_SIZE],  # 截取分块大小
                        "score": 0.5,                       # 图谱匹配基准分
                        "source": "global_graph",           # 标记为全局图谱来源
                        "matched_entity": name              # 匹配到的实体名（调试用）
                    })
                    break  # 一个 chunk 只加入一次

        # 全局结果按分数排序后截取 top_k
        global_results.sort(key=lambda x: x["score"], reverse=True)
        global_results = global_results[:top_k_global]

    # ======== 合并两个通路的检索结果 ========
    all_results = local_results + global_results
    all_results.sort(key=lambda x: x["score"], reverse=True)  # 按分数降序

    print(f"📡 LightRAG检索: 局部={len(local_results)}条, "
          f"全局={len(global_results)}条, "
          f"合并={len(all_results)}条")
    return all_results


def _find_chunk_text(chunks: list[dict], chunk_id: int) -> str:
    """
    根据 chunk_id 从 chunks 列表中查找完整文本内容
    参数：chunks - 文本块列表, chunk_id - 目标块 ID
    返回：文本字符串，未找到返回空串
    """
    for ch in chunks:
        if ch["chunk_id"] == chunk_id:
            return ch["text"]
    return ""


def _extract_keywords_from_query(
    query: str, graph: "nx.DiGraph"
) -> list[str]:
    """
    从查询文本中提取在图谱中可能存在的实体关键词
    策略：遍历图谱所有实体名，检查是否出现在查询文本中
    参数：
        query: 用户原始查询文本
        graph: NetworkX 知识图谱
    返回：
        匹配到的实体节点 ID 列表
    """
    matched = []  # 匹配的节点 ID 列表
    for node_id, data in graph.nodes(data=True):
        name = data.get("name", "")
        # 实体名称出现在查询文本中 → 视为匹配
        if name and name in query:
            matched.append(node_id)
    return matched

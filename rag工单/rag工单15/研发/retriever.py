# -*- coding: utf-8 -*-
"""
混合检索模块 — 实现文本检索和图像增强检索的双路召回+RRF融合。

功能说明：
- 文本检索：使用原始问题编码向量，在知识库中搜索相似文本块
- 图像增强检索：使用增强查询（含图纸描述）编码向量，搜索包含图表的页面
- RRF融合：将两路检索结果按倒数排名融合算法合并排序
- 返回最终Top-K结果供下游重排和问答使用
"""
import logging
import numpy as np  # 导入numpy，用于向量运算
from embedder import embed_texts, cosine_similarity  # 导入嵌入模块

logger = logging.getLogger(__name__)
logger.info("retriever 模块加载")



def build_vector_index(knowledge_base):
    """
    为知识库构建向量索引（编码所有文本块）。

    参数:
        knowledge_base: 知识库列表，每个元素包含content字段

    返回:
        vectors: 所有文本块的向量矩阵
        texts: 文本块列表（与向量一一对应）
    """
    # 提取所有文本块内容
    texts = [item["content"] for item in knowledge_base]
    print(f"  📚 知识库共 {len(texts)} 个文本块")  # 打印知识库大小
    return texts  # 返回文本列表（向量在检索时实时计算）


def retrieve_text(bge_model, query, texts, kb_items, top_k=10):
    """
    文本检索：使用原始问题在知识库中搜索。

    参数:
        bge_model: BGE-M3 模型
        query: 原始问题文本
        texts: 知识库文本列表
        kb_items: 知识库条目列表
        top_k: 返回前K个结果

    返回:
        带分数的检索结果列表，按相似度降序排列
    """
    # 编码查询文本
    query_vec = embed_texts(bge_model, [query], batch_size=1)[0]
    # 编码知识库文本
    doc_vecs = embed_texts(bge_model, texts, batch_size=2)
    # 计算余弦相似度
    scores = cosine_similarity(query_vec, doc_vecs)

    # 构建结果列表（文本检索结果）
    results = []
    for i, score in enumerate(scores):  # 遍历每个文本块
        results.append({
            "id": kb_items[i]["id"],  # 文本块ID
            "page_num": kb_items[i]["page_num"],  # 页码
            "content": texts[i],  # 文本内容
            "has_figure": kb_items[i]["has_figure"],  # 是否含图
            "figure_ref": kb_items[i]["figure_ref"],  # 图表引用
            "score": float(score),  # 相似度分数
            "source": "text_retrieval",  # 来源标记（文本检索）
        })

    # 按分数降序排列
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]  # 返回TopK


def retrieve_image_enhanced(bge_model, enhanced_query, texts, kb_items, top_k=10):
    """
    图像增强检索：使用增强查询搜索包含图表信息的知识块。

    参数:
        bge_model: BGE-M3 模型
        enhanced_query: 增强查询（含图纸描述）
        texts: 知识库文本列表
        kb_items: 知识库条目列表
        top_k: 返回前K个结果

    返回:
        带分数的检索结果列表
    """
    # 编码增强查询
    query_vec = embed_texts(bge_model, [enhanced_query], batch_size=1)[0]
    # 编码知识库文本
    doc_vecs = embed_texts(bge_model, texts, batch_size=2)
    # 计算余弦相似度
    scores = cosine_similarity(query_vec, doc_vecs)

    # 构建结果列表（图像增强检索结果）
    results = []
    for i, score in enumerate(scores):  # 遍历每个文本块
        # 对包含图表的页面额外加分（提高图文页面的排序位置）
        figure_boost = 0.15 if kb_items[i]["has_figure"] else 0.0
        final_score = float(score) + figure_boost  # 加入图表加成

        results.append({
            "id": kb_items[i]["id"],  # 文本块ID
            "page_num": kb_items[i]["page_num"],  # 页码
            "content": texts[i],  # 文本内容
            "has_figure": kb_items[i]["has_figure"],  # 是否含图
            "figure_ref": kb_items[i]["figure_ref"],  # 图表引用
            "score": final_score,  # 最终分数（含图表加成）
            "source": "image_enhanced",  # 来源标记（图像增强检索）
        })

    # 按分数降序排列
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def rrf_fusion(text_results, image_results, k=60, top_k=10):
    """
    RRF（倒数排名融合）合并两路检索结果。

    参数:
        text_results: 文本检索结果列表
        image_results: 图像增强检索结果列表
        k: RRF常数，控制排名衰减速度
        top_k: 最终返回前K个结果

    返回:
        融合后的结果列表，按RRF分数降序排列
    """
    # 使用字典聚合相同文本块的RRF分数
    fusion_scores = {}  # 融合分数字典，key为文本块ID

    # 处理文本检索结果的排名
    for rank, item in enumerate(text_results):  # 遍历文本检索结果
        idx = item["id"]  # 文本块ID
        if idx not in fusion_scores:  # 如果首次出现
            fusion_scores[idx] = {
                "id": idx, "page_num": item["page_num"],
                "content": item["content"],
                "has_figure": item["has_figure"],
                "figure_ref": item["figure_ref"],
                "rrf_score": 0.0,  # RRF分数初始为0
                "text_score": item["score"],  # 文本检索分数
                "image_score": 0.0,  # 图像检索分数
            }
        # RRF公式: 1 / (k + rank)，rank从1开始
        fusion_scores[idx]["rrf_score"] += 1.0 / (k + rank + 1)
        fusion_scores[idx]["text_score"] = item["score"]  # 更新文本分数

    # 处理图像增强检索结果的排名
    for rank, item in enumerate(image_results):  # 遍历图像检索结果
        idx = item["id"]  # 文本块ID
        if idx not in fusion_scores:  # 如果首次出现
            fusion_scores[idx] = {
                "id": idx, "page_num": item["page_num"],
                "content": item["content"],
                "has_figure": item["has_figure"],
                "figure_ref": item["figure_ref"],
                "rrf_score": 0.0,
                "text_score": 0.0,
                "image_score": item["score"],
            }
            fusion_scores[idx]["rrf_score"] = 0.0  # 初始化RRF分数
        # RRF公式: 1 / (k + rank)
        fusion_scores[idx]["rrf_score"] += 1.0 / (k + rank + 1)
        fusion_scores[idx]["image_score"] = item["score"]  # 更新图像分数

    # 按RRF分数降序排列
    fused = sorted(fusion_scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    return fused[:top_k]  # 返回TopK

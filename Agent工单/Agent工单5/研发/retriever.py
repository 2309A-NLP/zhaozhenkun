# -*- coding: utf-8 -*-
"""
retriever.py — 招股书文本检索器
功能：公司名映射定位文件 → 分段TF-IDF检索最相关文本块 → 返回上下文
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
"""

import re  # 正则提取公司名
import logging  # 日志
import numpy as np  # 数值计算
from sklearn.metrics.pairwise import cosine_similarity  # 余弦相似度
import config  # 配置文件

logger = logging.getLogger(__name__)  # 模块日志器


def extract_company_name(question):
    """从问题中提取公司名（中文分词后取长词组）"""
    stop = r'[的了是而在如何什么哪该请帮查询计算报告期内分别多少负责具体主要以及来自变更设立作为发起人法人\.\?\？\。\，\、\s]+'  # 分隔符
    words = [w.strip() for w in re.split(stop, question) if len(w.strip()) >= 4]  # >=4字词
    names = [w for w in words if len(w) >= 6]  # >=6字优先
    if not names:  # 没有长词
        names = [w for w in words if len(w) >= 4]  # >=4字
    return names  # 返回公司名候选


def _build_file_index(chunk_metadata, all_chunks):
    """构建 文件名→chunk索引列表 的映射"""
    file_chunks = {}  # 文件名 → chunk全局索引列表
    for i, meta in enumerate(chunk_metadata):  # 遍历元数据
        fname = meta["source"]  # 文件名
        if fname not in file_chunks:  # 新文件
            file_chunks[fname] = []  # 初始化
        file_chunks[fname].append(i)  # 添加索引
    return file_chunks  # 返回映射


def _find_file_by_company(companies, chunk_metadata, all_chunks):
    """在全部chunk中搜索公司名（扫每个文件前50块）"""
    file_chunks = _build_file_index(chunk_metadata, all_chunks)  # 文件索引
    matched = []  # 命中文件
    for fname, indices in file_chunks.items():  # 遍历每个文件
        for gi in indices[:50]:  # 只看前50块
            if any(name in all_chunks[gi] for name in companies):  # 公司名命中
                matched.append(fname)  # 收录
                break  # 找到即停
    return matched  # 返回命中文件


def search(question, vectorizer, chunk_vectors, all_chunks, chunk_metadata, top_k=5, company_map=None):
    """公司名优先检索：映射定位文件 → 分段TF-IDF搜索"""
    companies = extract_company_name(question)  # 提取公司名
    logger.debug("公司名: %s", companies)  # 调试日志
    target_indices = list(range(len(all_chunks)))  # 默认全搜索
    matched_files = []  # 命中文件
    map_hit = False  # 映射命中标记
    # 优先用公司名映射定位
    if companies and company_map:  # 有公司名+映射
        for name in companies:  # 遍历候选
            if name in company_map:  # 全名命中
                matched_files.append(company_map[name])  # 定位
                map_hit = True  # 标记
                logger.debug("映射精确命中: %s → %s", name, company_map[name][:40])  # 日志
                break  # 找到
            for cm_key, cm_file in company_map.items():  # 遍历映射
                if len(cm_key) >= 10 and cm_key in name:  # 长key包含匹配
                    matched_files.append(cm_file)  # 定位
                    map_hit = True  # 标记
                    logger.debug("映射包含命中: %s ⊂ %s → %s", cm_key, name, cm_file[:40])  # 日志
                    break  # 找到
            if matched_files:  # 已找到
                break  # 停止
    # 映射未命中则采样搜索
    if not matched_files and companies:  # 映射未命中
        matched_files = _find_file_by_company(companies, chunk_metadata, all_chunks)  # 采样搜索
        if matched_files:  # 采样命中
            logger.debug("采样命中文件: %s", matched_files[0][:40])  # 日志
    # 限定搜索范围
    if matched_files:  # 找到目标文件
        logger.info("定位文件: %s (映射=%s)", matched_files[0][:50], '✓' if map_hit else '采样')  # 日志
        target_indices = []  # 限定范围
        fc = _build_file_index(chunk_metadata, all_chunks)  # 文件索引
        for fname in matched_files:  # 遍历文件
            target_indices.extend(fc[fname])  # 加入所有块
    # 分段检索
    question_vec = vectorizer.transform([question])  # 问题向量
    candidate_vecs = chunk_vectors[target_indices]  # 候选向量
    sims = cosine_similarity(question_vec, candidate_vecs).flatten()  # 相似度
    if matched_files:  # 公司名命中→分段检索覆盖全文
        n_total = len(target_indices)  # 总块数
        n_segments = 5  # 5段
        seg_size = max(1, n_total // n_segments)  # 每段大小
        top_local = set()  # 用set去重
        for seg in range(n_segments):  # 遍历每段
            start = seg * seg_size  # 段起始
            end = start + seg_size if seg < n_segments - 1 else n_total  # 段结束
            seg_sims = sims[start:end]  # 段内相似度
            seg_top = list(np.argsort(seg_sims)[::-1][:8])  # 每段top8
            for st in seg_top:  # 加入
                top_local.add(start + st)  # 转全局
        top_local = list(top_local)  # 转列表
    else:  # 全搜索模式
        top_k_eff = min(top_k, len(target_indices))  # top_k
        top_local = list(np.argsort(sims)[::-1][:top_k_eff])  # 排序取top
    # 收集结果
    retrieved_chunks, retrieved_metadata, retrieved_scores = [], [], []  # 结果
    for li in top_local:  # 遍历索引
        gi = target_indices[li]  # 全局索引
        score = float(sims[li]) if li < len(sims) else 0.0  # 分数
        if score >= 0:  # 收录
            retrieved_chunks.append(all_chunks[gi])  # 文本
            retrieved_metadata.append(chunk_metadata[gi])  # 元数据
            retrieved_scores.append(score)  # 分数
    logger.debug("检索到 %d 个块", len(retrieved_chunks))  # 日志
    return retrieved_chunks, retrieved_metadata, retrieved_scores  # 返回


def format_retrieved_context(retrieved_chunks, retrieved_metadata, retrieved_scores):
    """将检索到的文本块格式化为LLM可读的上下文文本"""
    parts = []  # 存储格式化片段
    for i, (chunk, meta, score) in enumerate(zip(retrieved_chunks, retrieved_metadata, retrieved_scores), 1):  # 遍历
        header = f"【来源{i}】文件: {meta['source']} | 相关度: {score:.3f}"  # 头部
        parts.append(header + "\n" + chunk)  # 头部+内容
    return "\n\n---\n\n".join(parts)  # 分隔连接


def get_top_chunk_texts(question, vectorizer, chunk_vectors, all_chunks, chunk_metadata, top_k=None, company_map=None):
    """检索并返回最相关文本块的纯文本列表"""
    if top_k is None:  # 未指定
        top_k = config.TOP_K  # 默认
    chunks, meta, scores = search(question, vectorizer, chunk_vectors, all_chunks, chunk_metadata, top_k, company_map)
    return chunks  # 返回文本块


if __name__ == "__main__":  # 测试
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")  # 日志配置
    from indexer import get_or_build_index  # 索引器
    idx = get_or_build_index(config.PDF_TXT_DIR, config.INDEX_CACHE_DIR, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    vec, cv, chunks, meta, cmap = idx  # 解包
    q = "湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些？"  # 测试问题
    results, rmeta, rscores = search(q, vec, cv, chunks, meta, top_k=3, company_map=cmap)  # 检索
    logger.info("问题: %s", q)  # 打印
    for i, (c, m, s) in enumerate(zip(results, rmeta, rscores)):  # 遍历
        logger.info("  #%d [%s] 得分=%.3f | %s...", i+1, m['source'][:20], s, c[:100])  # 打印

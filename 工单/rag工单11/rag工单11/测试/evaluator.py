"""
评估模块（测试层）
功能：微调前后模型效果对比——三元组指标 + RAG检索评估双体系
完成：Recall@K / MRR / 相似度分离度 + 真实RAG检索评估 + JSON对比报告
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""
import logging
import json                              # JSON读写
import time                              # 计时
from typing import List, Dict, Tuple     # 类型注解
import torch                             # PyTorch张量运算
import numpy as np                       # 数值计算
from config import EVAL_CONFIG, EVAL_DIR, RAG_TEST_QUESTIONS, ensure_dirs  # 评估配置

logger = logging.getLogger(__name__)
logger.info("评估模块加载")


def recall_at_k(query_emb, corpus_emb, relevant_indices, k):
    """
    计算 Recall@K：前K个检索结果中相关文档出现的比例
    参数：query_emb-查询向量, corpus_emb-文档向量矩阵, relevant_indices-相关文档索引, k-topK
    """
    sim = torch.mm(query_emb, corpus_emb.T)                        # 余弦相似度矩阵
    topk = torch.topk(sim, k=k, dim=1).indices                     # 每行取topK索引
    hits = sum(1 for q_idx, rels in enumerate(relevant_indices)    # 统计命中数
               if any(r in set(topk[q_idx].tolist()) for r in rels))
    return hits / len(query_emb)                                    # 归一化为比例


def mean_reciprocal_rank(query_emb, corpus_emb, relevant_indices):
    """
    计算 MRR：第一个相关文档排名的倒数均值
    参数同上
    """
    sim = torch.mm(query_emb, corpus_emb.T)                        # 相似度矩阵
    sorted_idx = torch.argsort(sim, dim=1, descending=True)        # 按降序排列
    rrs = []                                                        # 每个查询的RR
    for q_idx, rels in enumerate(relevant_indices):
        rel_set = set(rels)                                         # 相关文档索引集
        rank = next((pos + 1 for pos, doc in                      # 找第一个相关文档的排名
                     enumerate(sorted_idx[q_idx].tolist()) if doc in rel_set), None)
        rrs.append(1.0 / rank if rank else 0.0)                    # 倒数排名
    return float(np.mean(rrs))                                      # 平均MRR


def compute_similarity_stats(query_emb, corpus_emb, relevant_indices):
    """
    计算正例/负例相似度分布统计（分离度越大微调效果越好）
    返回：{正例相似度均值, 负例相似度均值, 正负例分离度, 样本数}
    """
    sim = torch.mm(query_emb, corpus_emb.T)                        # 全部相似度
    pos, neg = [], []                                               # 正例/负例相似度收集
    for q_idx, rels in enumerate(relevant_indices):
        rel_set = set(rels)                                         # 相关文档
        for d_idx in range(corpus_emb.size(0)):                    # 遍历所有文档
            s = sim[q_idx, d_idx].item()                           # 相似度值
            (pos if d_idx in rel_set else neg).append(s)           # 分类收集
    pm = float(np.mean(pos)) if pos else 0                         # 正例均值
    nm = float(np.mean(neg)) if neg else 0                         # 负例均值
    return {"正例相似度均值": round(pm, 4),
            "负例相似度均值": round(nm, 4),
            "正负例分离度": round(pm - nm, 4),                     # 关键指标
            "正例样本数": len(pos), "负例样本数": len(neg)}


def build_eval_corpus(eval_data):
    """
    从评估三元组构建检索评估数据集
    参数：eval_data-三元组列表 [{"anchor","positive","negative"},...]
    返回：(queries, relevant_indices, corpus_texts)
    """
    all_texts = set()                                  # 去重收集所有文本
    q_to_rel = {}                                      # 查询→相关文档映射
    for item in eval_data:
        for k in ["anchor", "positive", "negative"]:
            all_texts.add(item[k])                     # 添加anchor/positive/negative
        q_to_rel.setdefault(item["anchor"], []).append(item["positive"])
    texts_list = list(all_texts)                       # 去重后的文档列表
    t2i = {t: i for i, t in enumerate(texts_list)}     # 文本→索引映射
    queries, rel_indices = [], []
    for anchor, positives in q_to_rel.items():
        queries.append(anchor)                         # anchor作为查询
        rel_indices.append([t2i[p] for p in positives]) # positive作为相关文档
    test_size = min(EVAL_CONFIG["test_size"], len(queries))
    queries, rel_indices = queries[:test_size], rel_indices[:test_size]
    print(f"  [评估集] {test_size}查询, {len(texts_list)}候选文档")
    return queries, rel_indices, texts_list


class EmbeddingEvaluator:
    """
    Embedding模型评估器
    支持：三元组指标评估 + RAG检索评估 + 微调前后对比
    """

    def __init__(self):
        self.results = {}          # {模型名: 评估指标} 缓存
        self.rag_results = {}      # {模型名: RAG检索指标} 缓存

    def evaluate(self, model, model_name, eval_data):
        """
        三元组指标评估：Recall@K + MRR + 相似度分离度
        参数：model-微调器实例, model_name-模型标识, eval_data-评估三元组
        """
        print(f"\n{'='*40}\n[三元组评估] {model_name}\n{'='*40}")
        queries, rel_indices, corpus = build_eval_corpus(eval_data)  # 构建评估集

        print("  编码查询...", end=" ", flush=True)
        t0 = time.time()
        q_emb = model.encode(queries).float()                        # 查询向量
        print(f"{time.time()-t0:.1f}秒")
        print("  编码语料...", end=" ", flush=True)
        t0 = time.time()
        c_emb = model.encode(corpus).float()                         # 文档向量
        print(f"{time.time()-t0:.1f}秒")

        metrics = {}
        for k in EVAL_CONFIG["top_k"]:                               # 各K值的Recall
            metrics[f"Recall@{k}"] = round(
                recall_at_k(q_emb, c_emb, rel_indices, k), 4)
        metrics["MRR"] = round(mean_reciprocal_rank(q_emb, c_emb, rel_indices), 4)
        metrics["相似度分析"] = compute_similarity_stats(q_emb, c_emb, rel_indices)

        # 打印结果
        print(f"\n  --- {model_name} ---")
        for k in EVAL_CONFIG["top_k"]:
            print(f"    Recall@{k}: {metrics[f'Recall@{k}']:.4f}")
        print(f"    MRR:      {metrics['MRR']:.4f}")
        sa = metrics["相似度分析"]
        print(f"    分离度:   {sa['正负例分离度']:.4f}")
        self.results[model_name] = metrics                           # 缓存结果
        return metrics

    def evaluate_rag_retrieval(self, model, model_name, chunks, answer_chunks):
        """
        RAG检索评估：用测试问题做真实检索，评估微调后Embedding在RAG中的效果
        参数：model-微调器, model_name-名称, chunks-所有文本块, answer_chunks-含答案的块索引
        返回：{Recall@K, MRR, 命中率}
        """
        print(f"\n{'='*40}\n[RAG检索评估] {model_name}\n{'='*40}")
        if not RAG_TEST_QUESTIONS:
            print("  [跳过] 无测试问题")
            return {}

        # 编码所有文本块为向量
        print(f"  编码{len(chunks)}个文档块...", end=" ", flush=True)
        t0 = time.time()
        doc_emb = model.encode(chunks).float()                       # 文档向量矩阵
        print(f"{time.time()-t0:.1f}秒")

        # 编码测试问题
        print(f"  编码{len(RAG_TEST_QUESTIONS)}个测试问题...", end=" ", flush=True)
        t0 = time.time()
        q_emb = model.encode(RAG_TEST_QUESTIONS).float()             # 问题向量
        print(f"{time.time()-t0:.1f}秒")

        # 检索评估
        sim = torch.mm(q_emb, doc_emb.T)                             # 相似度矩阵
        metrics = {}
        for k in EVAL_CONFIG["top_k"]:
            topk = torch.topk(sim, k=k, dim=1).indices               # 每问题topK
            hits = sum(1 for i in range(len(RAG_TEST_QUESTIONS))     # 统计命中
                       if any(idx in answer_chunks[i] for idx in topk[i].tolist())
                       if i < len(answer_chunks))
            metrics[f"RAG_Recall@{k}"] = round(hits / len(RAG_TEST_QUESTIONS), 4)
        # RAG MRR
        sorted_idx = torch.argsort(sim, dim=1, descending=True)
        rrs = []
        for i in range(len(RAG_TEST_QUESTIONS)):
            if i >= len(answer_chunks):
                continue
            for pos, doc in enumerate(sorted_idx[i].tolist()):
                if doc in answer_chunks[i]:
                    rrs.append(1.0 / (pos + 1)); break
            else:
                rrs.append(0.0)
        metrics["RAG_MRR"] = round(float(np.mean(rrs)), 4) if rrs else 0

        # 打印
        print(f"\n  --- RAG检索: {model_name} ---")
        for k in EVAL_CONFIG["top_k"]:
            print(f"    RAG_Recall@{k}: {metrics[f'RAG_Recall@{k}']:.4f}")
        print(f"    RAG_MRR: {metrics['RAG_MRR']:.4f}")
        self.rag_results[model_name] = metrics
        return metrics

    def compare(self):
        """
        对比微调前后各指标（三元组 + RAG检索）
        返回：完整对比dict
        """
        if len(self.results) < 2:
            print("[对比] 需要至少两组结果")
            return {}
        names = list(self.results.keys())
        before, after = self.results[names[-2]], self.results[names[-1]]
        print(f"\n{'='*40}\n微调前后对比\n{'='*40}")
        print(f"  指标          | 微调前   | 微调后   | 变化")
        print(f"  {'-'*40}")

        comparison = {}
        # 三元组指标对比
        for k in EVAL_CONFIG["top_k"]:
            b, a = before[f"Recall@{k}"], after[f"Recall@{k}"]
            ch = round(a - b, 4)
            comparison[f"Recall@{k}"] = {"before": b, "after": a, "change": ch}
            arrow = "↑" if ch > 0 else ("↓" if ch < 0 else "→")
            print(f"  Recall@{k:<4} | {b:.4f}   | {a:.4f}   | {arrow}{ch:+.4f}")
        bm, am = before["MRR"], after["MRR"]
        chm = round(am - bm, 4)
        comparison["MRR"] = {"before": bm, "after": am, "change": chm}
        print(f"  MRR         | {bm:.4f}   | {am:.4f}   | {'↑' if chm>0 else '↓'}{chm:+.4f}")
        bs = before["相似度分析"]["正负例分离度"]
        as_ = after["相似度分析"]["正负例分离度"]
        chs = round(as_ - bs, 4)
        comparison["分离度"] = {"before": bs, "after": as_, "change": chs}
        print(f"  分离度       | {bs:.4f}   | {as_:.4f}   | {'↑' if chs>0 else '↓'}{chs:+.4f}")

        # RAG检索指标对比（如有）
        if len(self.rag_results) >= 2:
            rb, ra = self.rag_results[names[-2]], self.rag_results[names[-1]]
            print(f"\n  --- RAG检索指标对比 ---")
            for k in ["RAG_Recall@5", "RAG_Recall@10", "RAG_MRR"]:
                if k in rb and k in ra:
                    bv, av = rb[k], ra[k]
                    cv = round(av - bv, 4)
                    comparison[k] = {"before": bv, "after": av, "change": cv}
                    arrow = "↑" if cv > 0 else ("↓" if cv < 0 else "→")
                    print(f"  {k:<14} | {bv:.4f}   | {av:.4f}   | {arrow}{cv:+.4f}")
        return comparison

    def save_report(self, comparison, filename="eval_report.json"):
        """保存完整评估报告为JSON"""
        ensure_dirs()
        path = EVAL_DIR / filename
        # 生成结论
        imp = [f"{m}: +{v['change']:.4f}" for m, v in comparison.items()
               if isinstance(v, dict) and v.get("change", 0) > 0]
        deg = [f"{m}: {v['change']:.4f}" for m, v in comparison.items()
               if isinstance(v, dict) and v.get("change", 0) < 0]
        conclusion = "微调有效" if len(imp) >= len(deg) else "微调效果不显著"
        if imp:
            conclusion += " (提升: " + ", ".join(imp) + ")"
        if deg:
            conclusion += " (下降: " + ", ".join(deg) + ")"
        report = {
            "配置": {"top_k": EVAL_CONFIG["top_k"],
                     "测试查询数": EVAL_CONFIG["test_size"]},
            "三元组指标": self.results,
            "RAG检索指标": self.rag_results if self.rag_results else {},
            "对比结果": comparison,
            "结论": conclusion
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[报告] → {path}")
        return path

"""
优化层模块
功能：参数调优、缓存策略管理、分块/实体提取参数优化、图谱质量分析
完成：自动调参建议、缓存有效性验证、全流程耗时统计、图谱密度分析
"""
import logging

logger = logging.getLogger(__name__)
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json      # 缓存文件读写
import time      # 耗时统计
import os        # 文件存在性检查

import config    # 全局配置（可调参数）


def validate_cache() -> dict:
    """
    验证所有缓存文件的完整性和有效性
    返回：
        {"valid": bool, "files": {path: {"exists": bool, "size_kb": float}}, "issues": [str]}
    """
    # 需要检查的所有缓存文件路径
    cache_files = {
        "parsed_pages": os.path.join(config.CACHE_DIR, "parsed_pages.json"),
        "chunks": config.CHUNKS_CACHE,
        "vectors": config.VECTORS_CACHE,
        "embeddings_meta": config.EMBEDDINGS_META,
        "graph": config.GRAPH_CACHE,
        "entity_extractions": os.path.join(config.CACHE_DIR, "entity_extractions.json"),
    }
    result = {"valid": True, "files": {}, "issues": []}  # 验证结果
    for name, path in cache_files.items():
        exists = os.path.exists(path)  # 文件是否存在
        size = os.path.getsize(path) / 1024 if exists else 0  # 文件大小(KB)
        result["files"][name] = {"exists": exists, "size_kb": round(size, 1)}
        if not exists:
            result["valid"] = False  # 缺失任一文件即无效
            result["issues"].append(f"缺少: {path}")
        elif size == 0:
            result["valid"] = False
            result["issues"].append(f"空文件: {path}")
    return result


def suggest_chunk_params(total_chars: int, avg_page_chars: int) -> dict:
    """
    根据文档内容统计自动建议分块参数
    参数：
        total_chars:      文档总字符数
        avg_page_chars:   平均每页字符数
    返回：
        {"chunk_size": int, "chunk_overlap": int, "estimated_chunks": int, "reason": str}
    """
    if avg_page_chars < 200:
        # 短页面：用小分块避免信息稀释
        chunk_size = 200
        overlap = 30
    elif avg_page_chars < 500:
        # 中等页面：平衡执行
        chunk_size = 300
        overlap = 50
    else:
        # 长页面：适当增大分块减少 API 调用
        chunk_size = 500
        overlap = 80
    estimated = max(1, total_chars // (chunk_size - overlap))  # 估计分块数
    return {
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "estimated_chunks": estimated,
        "reason": f"每页均 {avg_page_chars} 字符 → chunk_size={chunk_size}"
    }


def analyze_graph_quality(graph) -> dict:
    """
    分析知识图谱的质量指标
    参数：graph - NetworkX 有向图
    返回：
        {"density": float, "avg_degree": float, "isolated_nodes": int,
         "component_count": int, "quality_level": str}
    """
    import networkx as nx  # 图分析算法


    n = graph.number_of_nodes()
    e = graph.number_of_edges()
    # 图密度：实际边数 / 可能最大边数（有向图中为 n*(n-1)）
    density = e / (n * (n - 1)) if n > 1 else 0
    # 平均度数：总度数（入+出）/ 节点数
    avg_degree = sum(d for _, d in graph.degree()) / n if n > 0 else 0
    # 孤立节点数：度数为 0 的节点
    isolated = sum(1 for _, d in graph.degree() if d == 0)
    # 弱连通分量数
    components = nx.number_weakly_connected_components(graph)
    # 质量等级判断
    if density > 0.05 and isolated / max(n, 1) < 0.2:
        quality = "优秀"  # 密度高且孤立节点少
    elif density > 0.02:
        quality = "良好"  # 密度尚可
    else:
        quality = "待优化"  # 图谱稀疏，需增加实体提取量或优化 prompt
    return {
        "density": round(density, 4),
        "avg_degree": round(avg_degree, 1),
        "isolated_nodes": isolated,
        "component_count": components,
        "quality_level": quality
    }


def estimate_pipeline_time(chunk_count: int, test_mode: bool = False) -> dict:
    """
    预估全流程耗时
    参数：
        chunk_count: 文本块总数
        test_mode:   是否测试模式
    返回：各阶段预估时间 dict（单位：秒）
    """
    # 经验参数（基于 RTX 5060 8GB 实测）
    embed_time_per_chunk = 0.05       # BGE-M3 编码：约 0.05s/块
    extract_time_per_batch = 8.0      # LLM 实体提取：约 8s/批次
    gen_time_per_question = 3.0       # LLM 问答生成：约 3s/题
    batch_size = config.ENTITY_BATCH_SIZE  # 每批次 chunk 数
    # 计算各阶段时间
    batches = max(1, chunk_count // batch_size)
    question_count = config.TEST_MODE_QUESTIONS if test_mode else len(config.TEST_QUESTIONS)
    return {
        "embedding": round(chunk_count * embed_time_per_chunk, 1),
        "entity_extraction": round(batches * extract_time_per_batch, 1),
        "qa_generation": round(question_count * 2 * gen_time_per_question, 1),
        "total_estimated": round(
            chunk_count * embed_time_per_chunk +
            batches * extract_time_per_batch +
            question_count * 2 * gen_time_per_question, 1
        )
    }


class PipelineTimer:
    """
    全流程耗时统计器
    用法：
        timer = PipelineTimer()
        with timer.step("PDF解析"): ...
        timer.print_summary()
    """
    def __init__(self):
        self.steps = {}     # {步骤名: 耗时秒}
        self._current = None  # 当前步骤名
        self._start = None    # 当前步骤开始时间

    def start(self, name: str):
        """开始计时一个步骤"""
        self._current = name
        self._start = time.time()

    def stop(self):
        """停止当前步骤计时并记录"""
        if self._current and self._start:
            self.steps[self._current] = round(time.time() - self._start, 1)
            self._current = None
            self._start = None

    def print_summary(self):
        """打印所有步骤耗时汇总"""
        total = sum(self.steps.values())
        print(f"\n⏱️  全流程耗时统计（总计 {total:.1f}s）:")
        for name, sec in self.steps.items():
            pct = sec / total * 100 if total > 0 else 0  # 占比
            bar = "█" * int(pct / 5)  # 简易条形图
            print(f"  {name:12s}: {sec:6.1f}s ({pct:4.1f}%) {bar}")


if __name__ == "__main__":
    """命令行测试：验证缓存 + 预估耗时"""
    print("🔧 优化层 — 缓存验证")
    v = validate_cache()
    print(f"  缓存有效: {v['valid']}")
    for name, info in v["files"].items():
        status = "✅" if info["exists"] else "❌"
        print(f"  {status} {name}: {info['size_kb']} KB")
    if v["issues"]:
        for issue in v["issues"]:
            print(f"  ⚠️ {issue}")

    # 从缓存加载 chunks 做预估
    if os.path.exists(config.CHUNKS_CACHE):
        with open(config.CHUNKS_CACHE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        est = estimate_pipeline_time(len(chunks))
        print(f"\n📊 预估 {len(chunks)} chunks 耗时: {est['total_estimated']}s")

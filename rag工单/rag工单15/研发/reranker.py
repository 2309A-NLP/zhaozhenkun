# -*- coding: utf-8 -*-
"""
跨模态重排模块 — 对检索结果进行精细化排序。

功能说明：
- 对RRF融合后的结果进行二次排序
- 优先提升包含图表信息的页面排名
- 对图文混合查询，加重图表页面的权重
- 对纯文本查询，保持原顺序
"""
import logging
from copy import deepcopy  # 导入深拷贝，避免修改原数据

logger = logging.getLogger(__name__)
logger.info("reranker 模块加载")


def rerank(query_type, results, query_analysis=None):
    """
    跨模态重排：根据查询类型对检索结果重新排序。

    参数:
        query_type: 查询类型（text 或 image_text）
        results: RRF融合后的结果列表
        query_analysis: 查询分析结果（包含引用的页码、图表等）

    返回:
        重排后的结果列表
    """
    if not results:  # 如果结果为空
        return []  # 直接返回

    print(f"  🔄 执行跨模态重排（查询类型: {query_type}）")  # 打印重排提示

    # 深拷贝结果，避免修改原始数据
    reranked = deepcopy(results)

    if query_type == "image_text":  # 如果是图文混合查询
        # ----- 策略1：图表页面优先 -----
        # 对包含图表（has_figure=True）的页面加分
        for item in reranked:  # 遍历所有结果
            if item.get("has_figure"):  # 如果包含图表
                # 图表匹配加分：基于RRF分数增加20%
                item["rerank_score"] = item["rrf_score"] * 1.2
            else:  # 如果不含图表
                item["rerank_score"] = item["rrf_score"] * 1.0  # 保持原分

        # ----- 策略2：精确页码匹配 -----
        # 如果查询分析中指定了具体页码，精确匹配的页面再加分
        if query_analysis and query_analysis.get("pages"):  # 如果有页码引用
            target_pages = []  # 目标页码列表
            for p_str in query_analysis["pages"]:  # 遍历页码引用
                # 提取数字部分，如"第11页" → 11
                import re

                nums = re.findall(r'\d+', p_str)
                if nums:
                    target_pages.append(int(nums[0]))

            for item in reranked:  # 遍历结果
                if item.get("page_num") in target_pages:  # 如果页码匹配
                    # 精确页码匹配再加分
                    item["rerank_score"] = item.get("rerank_score", 0) * 1.3

        # ----- 策略3：部件编号匹配 -----
        # 如果查询中包含部件编号，提升包含部件关系描述的页面
        if query_analysis and query_analysis.get("parts"):  # 如果有部件引用
            for item in reranked:  # 遍历结果
                content = item.get("content", "")  # 获取页面描述
                # 检查页面描述是否包含部件编号关键字
                if "部件" in content or "编号" in content:
                    # 包含部件描述的页面略微加分
                    item["rerank_score"] = item.get("rerank_score", 0) * 1.1

    else:  # 纯文本查询
        # 纯文本查询直接使用RRF分数，不做特殊处理
        for item in reranked:  # 遍历结果
            item["rerank_score"] = item["rrf_score"]  # 直接使用RRF分数

    # 按重排分数降序排列
    reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

    # 在结果中标记排名变化
    for rank, item in enumerate(reranked):  # 遍历重排后的结果
        item["final_rank"] = rank + 1  # 最终排名（从1开始）
        # 计算与原始RRF排名的差异
        orig_rank = rank  # 近似原始排名
        diff = orig_rank - (rank)  # 排名变化
        if diff > 0:  # 排名上升
            item["rank_change"] = f"↑{diff}"
        elif diff < 0:  # 排名下降
            item["rank_change"] = f"↓{abs(diff)}"
        else:  # 排名不变
            item["rank_change"] = "="

    print(f"  ✅ 重排完成，Top-1: {reranked[0]['id']}（得分: {reranked[0]['rerank_score']:.4f}）")
    return reranked  # 返回重排结果

def print_reranked(results):
    """
    打印重排后的结果，便于调试查看。

    参数:
        results: rerank函数返回的重排结果列表
    """
    print(f"\n  📊 重排后Top-K结果:")  # 打印标题
    for item in results[:5]:  # 只显示前5个
        # 标记是否包含图表
        fig_mark = "📷" if item.get("has_figure") else "📝"
        # 打印单条结果
        print(f"    #{item['final_rank']} {fig_mark} {item['id']} | "
              f"得分: {item['rerank_score']:.4f} | "
              f"{item['content'][:50]}...")

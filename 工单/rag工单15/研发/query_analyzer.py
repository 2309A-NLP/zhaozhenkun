# -*- coding: utf-8 -*-
"""
查询理解模块 — 自动识别问题中的视觉引用（图、页码、部件编号）。

功能说明：
- 检测问题中是否包含"图"、"页"等视觉引用关键词
- 提取具体的图表编号（图3）和页码（第11页）
- 提取部件编号（编号13、部件14等）
- 构建增强查询：原始文本 + 提取的视觉引用描述
- 判断问题类型：纯文本 vs 图文混合
"""
import logging
import re  # 导入正则表达式模块，用于模式匹配

logger = logging.getLogger(__name__)
logger.info("query_analyzer 模块加载")



def analyze_query(question):
    """
    分析问题，检测其中的视觉引用和部件编号。

    参数:
        question: 用户输入的问题文本

    返回:
        分析结果字典，包含视觉引用信息和增强查询
    """
    # 初始化分析结果
    result = {
        "original": question,  # 原始问题
        "has_visual_ref": False,  # 是否包含视觉引用
        "has_figure_ref": False,  # 是否引用图表
        "has_page_ref": False,  # 是否引用页码
        "has_part_ref": False,  # 是否引用部件
        "figures": [],  # 引用的图表列表
        "pages": [],  # 引用的页码列表
        "parts": [],  # 引用的部件编号列表
        "query_type": "text",  # 查询类型：text(文本) 或 image_text(图文)
        "enhanced_query": question,  # 增强后的查询（用于检索）
    }

    # ===== 检测图表引用 =====
    # 匹配 "图3"、"图 3"、"图三" 等模式
    figure_pattern = r'图\s*(\d+|[一二三四五六七八九十]+)'  # 图表编号的正则
    figures = re.findall(figure_pattern, question)  # 查找所有匹配
    if figures:  # 如果找到图表引用
        result["has_visual_ref"] = True  # 标记有视觉引用
        result["has_figure_ref"] = True  # 标记有图表引用
        # 将中文数字转换为阿拉伯数字
        cn_nums = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
        for f in figures:  # 遍历找到的图表编号
            if f in cn_nums:  # 如果是中文数字
                result["figures"].append(f"图{cn_nums[f]}")  # 转阿拉伯数字
            else:
                result["figures"].append(f"图{f}")  # 直接使用

    # ===== 检测页码引用 =====
    # 匹配 "第11页"、"第 11 页" 等模式
    page_pattern = r'第\s*(\d+)\s*页'  # 页码的正则
    pages = re.findall(page_pattern, question)  # 查找所有匹配
    if pages:  # 如果找到页码引用
        result["has_visual_ref"] = True  # 标记有视觉引用
        result["has_page_ref"] = True  # 标记有页码引用
        result["pages"] = [f"第{p}页" for p in pages]  # 记录页码

    # ===== 检测部件编号引用 =====
    # 匹配 "编号13"、"部件14"、"编号 13" 等模式
    part_pattern = r'(?:编号|部件)\s*(\d+)'  # 部件编号的正则
    parts = re.findall(part_pattern, question)  # 查找所有匹配
    if parts:  # 如果找到部件引用
        result["has_part_ref"] = True  # 标记有部件引用
        result["parts"] = [f"编号{p}" for p in parts]  # 记录部件编号

    # ===== 判断问题类型 =====
    if result["has_visual_ref"]:  # 如果包含视觉引用
        result["query_type"] = "image_text"  # 标记为图文混合查询

    # ===== 构建增强查询 =====
    # 增强查询 = 原始问题 + 视觉引用描述，用于提高检索命中率
    enhancements = []  # 收集增强信息
    if result["figures"]:  # 如果有图表引用
        figs = "、".join(result["figures"])  # 拼接图表编号
        enhancements.append(f"涉及{figs}的技术图纸信息")  # 添加图纸描述
    if result["pages"]:  # 如果有页码引用
        pgs = "、".join(result["pages"])  # 拼接页码
        enhancements.append(f"位于{pgs}的图纸说明")  # 添加位置描述
    if result["parts"]:  # 如果有部件引用
        pts = "、".join(result["parts"])  # 拼接部件编号
        enhancements.append(f"涉及部件{pts}的位置关系描述")  # 添加部件描述

    if enhancements:  # 如果有增强信息
        # 增强查询 = 原始问题 + "【图文检索】" + 增强描述
        result["enhanced_query"] = question + "【图文检索】" + "；".join(enhancements)

    return result  # 返回分析结果


def print_analysis(result):
    """
    打印查询分析结果，方便调试查看。

    参数:
        result: analyze_query返回的分析结果字典
    """
    print(f"\n🔍 查询分析:")  # 打印分析标题
    print(f"  原始问题: {result['original']}")  # 显示原始问题
    print(f"  查询类型: {'📷 图文混合' if result['query_type']=='image_text' else '📝 纯文本'}")  # 显示类型
    if result["has_visual_ref"]:  # 如果有视觉引用
        print(f"  📄 图表引用: {result['figures']}")  # 显示图表
        print(f"  📄 页码引用: {result['pages']}")  # 显示页码
        print(f"  🔧 部件引用: {result['parts']}")  # 显示部件
    print(f"  增强查询: {result['enhanced_query'][:100]}...")  # 显示增强查询（截断）

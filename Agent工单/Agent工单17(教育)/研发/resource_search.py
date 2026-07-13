# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：资源检索与引用服务 - 知识库检索、网络资源搜索、引用标注
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import re  # 正则表达式库
from typing import List, Optional, Dict  # 类型提示
from datetime import datetime  # 时间处理
from config import get_settings  # 系统配置
from knowledge_base import knowledge_base_service  # 知识库服务


class ResourceSearchService:
    """资源检索服务类 - 统一的知识库和外部资源检索入口"""

    def __init__(self):
        """初始化检索服务 - 加载配置和知识库引用"""
        self.settings = get_settings()  # 获取系统配置
        self.knowledge_base = knowledge_base_service  # 知识库服务引用

    def search_all_sources(self, query: str, max_results: int = 10,
                           resource_types: Optional[List[str]] = None) -> Dict:
        """综合检索 - 同时检索知识库并在结果中标注来源"""
        results = {"query": query, "timestamp": str(datetime.now()), "sources": []}  # 初始化结果结构
        # 调用知识库执行语义检索
        kb_results = self.knowledge_base.search(query, top_k=max_results, resource_types=resource_types)
        if kb_results:  # 检索到知识库结果
            kb_source = {"source_type": "knowledge_base", "source_name": "校本知识库",
                         "total_found": len(kb_results), "items": kb_results}  # 构建来源信息
            results["sources"].append(kb_source)  # 添加到结果
        # 本地资源库检索（模拟）
        local_results = self._search_local_repository(query, max_results // 2)  # 检索本地资源库
        if local_results:  # 检索到本地资源
            local_source = {"source_type": "local_repository", "source_name": "本地教材库",
                            "total_found": len(local_results), "items": local_results}  # 构建来源信息
            results["sources"].append(local_source)  # 添加到结果
        results["total_found"] = sum(s["total_found"] for s in results["sources"])  # 汇总总数
        return results  # 返回综合检索结果

    def _search_local_repository(self, query: str, max_results: int = 5) -> List[Dict]:
        """本地资源库检索 - 在预置教材库中匹配关键词"""
        # 本地教材资源库（模拟数据）
        local_books = [
            {"title": "Python程序设计（第3版）", "author": "董付国",
             "description": "全面介绍Python语言基础、面向对象、文件操作、异常处理等核心内容。包含大量教学案例和练习题。",
             "publisher": "清华大学出版社", "chapters": "函数与模块、面向对象编程、文件操作"},
            {"title": "机器学习实战", "author": "Peter Harrington",
             "description": "讲解机器学习核心算法及其Python实现，包括分类、回归、聚类、降维等。配有丰富的实践案例。",
             "publisher": "人民邮电出版社", "chapters": "决策树、SVM、KNN、K-Means"},
            {"title": "深度学习入门", "author": "斋藤康毅",
             "description": "从零开始讲解深度学习和神经网络的基本原理，包括CNN、RNN、GAN等网络结构。",
             "publisher": "人民邮电出版社", "chapters": "卷积神经网络、循环神经网络"},
            {"title": "人工智能导论", "author": "李德毅",
             "description": "系统介绍人工智能的基本概念、方法和技术，涵盖知识表示、搜索推理、机器学习等主题。",
             "publisher": "中国科学技术出版社", "chapters": "AI概述、知识表示、搜索策略"},
        ]
        query_lower = query.lower()  # 查询词转小写
        matched = []  # 匹配结果列表
        for book in local_books:  # 遍历教材库
            # 在书名、描述、章节中匹配关键词
            text_to_search = f"{book['title']} {book['description']} {book['chapters']} {book['author']}"
            if any(term in text_to_search.lower() for term in query_lower.split()):  # 任一关键词匹配
                matched.append({"resource_id": f"local_{hash(book['title']) & 0x7FFFFFFF}",  # 生成ID
                                "title": book["title"], "snippet": book["description"][:200],
                                "resource_type": "textbook", "relevance_score": 0.75,
                                "source_url": "", "author": book["author"],
                                "publisher": book["publisher"]})  # 构建匹配条目
                if len(matched) >= max_results:  # 达到最大结果数
                    break  # 停止匹配
        return matched  # 返回匹配结果

    def generate_citation(self, resource_title: str, resource_type: str,
                          source_url: Optional[str] = None) -> str:
        """生成引用标注 - 根据资源类型生成规范的引用格式文本"""
        current_year = str(datetime.now().year)  # 当前年份
        if resource_type == "textbook":  # 教材引用格式
            return f"[{current_year}] {resource_title}[M]. 教材参考资料."
        elif resource_type == "school_based":  # 校本资源引用格式
            return f"[{current_year}] {resource_title}[Z]. 校本教学资源."
        elif resource_type == "network":  # 网络资源引用格式
            url_part = f" {source_url}" if source_url else ""  # URL部分
            return f"[{current_year}] {resource_title}[EB/OL]. 网络资源.{url_part}"
        else:  # 通用引用格式
            return f"[{current_year}] {resource_title}[R]. 教学参考资料."

    def insert_citation_into_content(self, content: str, citation_text: str,
                                     position: Optional[int] = None) -> str:
        """在内容中插入引用 - 将引用标注插入到文档的适当位置"""
        citation_marker = f"\n\n> **引用标注：** {citation_text}\n"  # 引用标注格式（Markdown引用块）
        if position is not None and 0 <= position < len(content):  # 指定了有效位置
            return content[:position] + citation_marker + content[position:]  # 在指定位置插入
        return content + citation_marker  # 默认追加到末尾


class CitationFormatter:
    """引用格式化工类 - 管理引用的格式化和样式"""

    FORMATS = {  # 不同格式的模板
        "apa": "{authors} ({year}). {title}. {source}.",  # APA格式
        "gb7714": "{authors}. {title}[{doc_type}]. {source}, {year}.",  # GB/T 7714格式
        "simple": "📖 **{title}** - {source}",  # 简易格式
    }

    @classmethod
    def format_citation(cls, title: str, source: str = "教学参考资料",
                        authors: str = "教学团队", year: Optional[int] = None,
                        doc_type: str = "M", style: str = "gb7714") -> str:
        """格式化引用文本 - 按指定格式样式生成引用"""
        if year is None:  # 未指定年份
            year = datetime.now().year  # 使用当前年份
        template = cls.FORMATS.get(style, cls.FORMATS["simple"])  # 获取格式模板
        return template.format(  # 填充模板
            title=title, source=source, authors=authors,
            year=year, doc_type=doc_type)


# 全局资源检索服务单例
resource_search_service = ResourceSearchService()  # 创建全局唯一的检索服务实例

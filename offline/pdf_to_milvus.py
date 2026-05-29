# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
"""
PDF数据处理管道模块。

本模块提供完整的PDF数据处理流程：
1. PDF清洗：使用pdfplumber或pypdf/PyPDF2提取文本，去除页眉页脚、页码等无关内容
2. 表格提取：检测并提取PDF中的表格内容，转换为文本段落
3. 知识JSON生成：根据课文配置构建问答对（avatar knowledge），各篇课文生成摘要和分块问答
4. 向量化入库（可选）：使用BGE-M3模型生成语义向量，插入Milvus向量数据库

包含ChineseTeacherPDFPipeline主处理类，支持多种PDF解析器自动降级。
"""

from __future__ import annotations   # 允许在类型注解中使用当前类的字符串引用

import argparse   # 导入命令行参数解析模块
import hashlib   # 导入哈希库，用于生成ID和降级向量
import json   # 导入JSON处理模块
import math   # 导入数学函数库，用于向量归一化计算
import re   # 导入正则表达式模块，用于文本清洗
from dataclasses import dataclass   # 从dataclasses导入dataclass装饰器，用于创建数据类
from datetime import datetime   # 导入datetime类，用于生成时间戳
from pathlib import Path   # 导入Path类，用于跨平台路径操作
from typing import Dict, Iterable, List, Optional, Sequence, Tuple   # 导入类型注解

try:
    import pdfplumber  # type: ignore   # 尝试导入pdfplumber库（精确PDF解析）
except Exception:   # 如果导入失败
    pdfplumber = None   # 设置为None，表示不可用

try:
    from pypdf import PdfReader  # type: ignore   # 尝试从pypdf导入PdfReader
except Exception:   # 如果导入失败
    try:
        from PyPDF2 import PdfReader  # type: ignore   # 尝试从PyPDF2导入PdfReader（旧版兼容）
    except Exception:   # 如果都失败
        PdfReader = None   # 设置为None

try:
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility  # type: ignore
    # 导入Milvus向量数据库相关组件：集合、集合Schema、数据类型、字段Schema、连接管理、工具函数
except Exception:   # 如果导入失败
    Collection = None   # 以下全部设置为None
    CollectionSchema = None
    DataType = None
    FieldSchema = None
    connections = None
    utility = None

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    # 导入sentence_transformers库，用于加载BGE-M3等嵌入模型
except Exception:   # 如果导入失败
    SentenceTransformer = None   # 设置为None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 获取项目根目录：当前文件所在目录的上级目录（resolve解析符号链接，parent获取父目录，两次parent）

try:
    from online.config import BGE_M3_PATH, DEVICE, MILVUS_HOSTS, MILVUS_PORT
    # 尝试从online.config模块导入配置：BGE-M3模型路径、设备、Milvus主机列表、端口
except Exception:   # 如果导入失败（配置不存在）
    BGE_M3_PATH = str(PROJECT_ROOT / "models" / "bge-m3")   # 默认模型路径
    DEVICE = "cpu"   # 默认使用CPU
    MILVUS_HOSTS = ["localhost", "127.0.0.1"]   # 默认Milvus主机列表
    MILVUS_PORT = "19530"   # 默认Milvus端口


@dataclass(frozen=True)   # 装饰器：创建不可变数据类（frozen=True表示只读）
class ArticleConfig:   # 定义ArticleConfig类，用于存储课文配置信息
    title: str   # 课文标题
    start_page: int   # 起始页码
    end_page: int   # 结束页码
    author: str   # 作者
    category: str   # 文体类别（如论述文、小说等）


@dataclass   # 装饰器：创建可变数据类
class ExtractedPage:   # 定义ExtractedPage类，存储提取的单页内容
    page_no: int   # 页码
    body_lines: List[str]   # 正文行列表
    table_blocks: List[str]   # 表格块列表
    headers: List[str]   # 页眉列表
    footers: List[str]   # 页脚列表


ARTICLE_CONFIGS: List[ArticleConfig] = [   # 定义课文配置列表，包含22篇课文
    ArticleConfig("社会历史的决定性基础", 7, 11, "恩格斯", "论述文"),   # 第1篇
    ArticleConfig("改造我们的学习", 12, 16, "毛泽东", "论述文"),   # 第2篇
    ArticleConfig("人的正确思想是从哪里来的？", 17, 17, "毛泽东", "论述文"),   # 第3篇
    ArticleConfig("实践是检验真理的唯一标准", 18, 22, "《光明日报》特约评论员", "论述文"),   # 第4篇
    ArticleConfig("修辞立其诚", 23, 25, "张岱年", "论述文"),   # 第5篇
    ArticleConfig("怜悯是人的天性", 26, 30, "卢梭", "论述文"),   # 第6篇
    ArticleConfig("人应当坚持正义", 31, 35, "柏拉图", "论述文"),   # 第7篇
    ArticleConfig("记念刘和珍君", 38, 42, "鲁迅", "纪念性散文"),   # 第8篇
    ArticleConfig("为了忘却的记念", 43, 50, "鲁迅", "纪念性散文"),   # 第9篇
    ArticleConfig("包身工", 52, 60, "夏衍", "报告文学"),   # 第10篇
    ArticleConfig("荷花淀", 61, 65, "孙犁", "小说"),   # 第11篇
    ArticleConfig("小二黑结婚（节选）", 66, 70, "赵树理", "小说"),   # 第12篇
    ArticleConfig("党费", 71, 79, "王愿坚", "小说"),   # 第13篇
    ArticleConfig("屈原列传", 82, 86, "司马迁", "文言文"),   # 第14篇
    ArticleConfig("苏武传", 87, 92, "班固", "文言文"),   # 第15篇
    ArticleConfig("过秦论", 93, 95, "贾谊", "文言文"),   # 第16篇
    ArticleConfig("五代史伶官传序", 96, 99, "欧阳修", "文言文"),   # 第17篇
    ArticleConfig("玩偶之家（节选）", 102, 116, "易卜生", "戏剧"),   # 第18篇
    ArticleConfig("迷娘（之一）", 117, 118, "歌德", "诗歌"),   # 第19篇
    ArticleConfig("致大海", 122, 124, "普希金", "诗歌"),   # 第20篇
    ArticleConfig("自己之歌（节选）", 123, 123, "惠特曼", "诗歌"),   # 第21篇
    ArticleConfig("树和天空", 124, 124, "特朗斯特罗姆", "诗歌"),   # 第22篇
    ArticleConfig("燕歌行并序", 128, 129, "高适", "古诗词"),   # 第23篇
    ArticleConfig("李凭箜篌引", 129, 129, "李贺", "古诗词"),   # 第24篇
    ArticleConfig("锦瑟", 130, 130, "李商隐", "古诗词"),   # 第25篇
    ArticleConfig("书愤", 131, 131, "陆游", "古诗词"),   # 第26篇
]


class ChineseTeacherPDFPipeline:   # 定义语文教师PDF处理管道主类
    def __init__(   # 构造函数，初始化处理管道
        self,
        pdf_path: Path,   # PDF文件路径
        raw_text_path: Path,   # 预抽取的原始文本文件路径（降级使用）
        avatar_output_path: Path,   # 角色知识JSON输出路径
        vector_output_dir: Path,   # 向量数据输出目录
        cleaned_text_output: Path,   # 清洗后的纯文本输出路径
    ) -> None:   # 返回类型为None
        self.pdf_path = pdf_path   # 保存PDF路径
        self.raw_text_path = raw_text_path   # 保存原始文本路径
        self.avatar_output_path = avatar_output_path   # 保存角色知识输出路径
        self.vector_output_dir = vector_output_dir   # 保存向量输出目录
        self.cleaned_text_output = cleaned_text_output   # 保存清洗文本输出路径
        self.avatar_output_path.parent.mkdir(parents=True, exist_ok=True)   # 创建角色知识输出目录（递归创建，存在时不报错）
        self.vector_output_dir.mkdir(parents=True, exist_ok=True)   # 创建向量输出目录
        self.cleaned_text_output.parent.mkdir(parents=True, exist_ok=True)   # 创建清洗文本输出目录
        self.vector_dim = 1024   # 初始化向量维度为1024（BGE-M3默认维度）
        self.bge_model = None   # 初始化BGE模型为None，延迟加载

    def run(self, skip_vector: bool = False) -> Dict[str, object]:   # 主运行方法，skip_vector跳过向量化和Milvus入库
        extracted_pages = self.load_pages()   # 加载PDF所有页面，返回ExtractedPage列表
        self.save_cleaned_pages(extracted_pages)   # 保存清洗后的页面文本
        avatar_records = self.build_avatar_records(extracted_pages)   # 构建角色知识记录（问答对）
        vector_records = self.build_vector_records(avatar_records)   # 构建向量入库记录（添加元数据）
        self.save_avatar_records(avatar_records)   # 保存角色知识JSON文件
        self.save_vector_records(vector_records)   # 保存向量记录文件（JSON和JSONL格式）

        inserted = 0   # 初始化插入计数器
        if not skip_vector:   # 如果不是跳过向量模式
            inserted = self.insert_into_milvus(vector_records)   # 将向量记录插入Milvus数据库

        return {   # 返回处理结果摘要
            "pages": len(extracted_pages),   # 处理的总页数
            "avatar_records": len(avatar_records),   # 生成的角色知识条数
            "vector_records": len(vector_records),   # 生成的向量记录条数
            "inserted": inserted,   # 实际插入Milvus的条数
            "cleaned_text_output": str(self.cleaned_text_output),   # 清洗文本输出路径
            "avatar_output": str(self.avatar_output_path),   # 角色知识输出路径
            "vector_output_dir": str(self.vector_output_dir),   # 向量输出目录
            "collection": "qa_embeddings",   # Milvus集合名称
        }

    def load_pages(self) -> List[ExtractedPage]:   # 加载PDF页面，支持多种解析器降级
        if self.pdf_path.exists() and pdfplumber is not None:   # 如果PDF存在且pdfplumber可用
            try:   # 尝试使用pdfplumber解析
                pages = self.extract_pages_with_pdfplumber()   # 调用pdfplumber提取方法
                if pages:   # 如果成功提取到页面
                    print(f"[OK] 已使用 pdfplumber 解析 PDF: {self.pdf_path.name} | 页数: {len(pages)}")   # 打印成功信息
                    return pages   # 返回提取的页面
            except Exception as exc:   # 如果解析出错
                print(f"[WARN] pdfplumber 解析失败，回退到普通文本抽取: {exc}")   # 打印警告信息

        if self.pdf_path.exists() and PdfReader is not None:   # 如果PDF存在且基础PDF阅读器可用
            try:   # 尝试使用基础PDF阅读器解析
                pages = self.extract_pages_with_basic_reader()   # 调用基础阅读器提取方法
                if pages:   # 如果成功提取到页面
                    print(f"[OK] 已使用基础 PDF Reader 解析 PDF: {self.pdf_path.name} | 页数: {len(pages)}")   # 打印成功信息
                    return pages   # 返回提取的页面
            except Exception as exc:   # 如果解析出错
                print(f"[WARN] 基础 PDF Reader 解析失败，回退到文本文件: {exc}")   # 打印警告信息

        if self.raw_text_path.exists():   # 如果预抽取的原始文本文件存在
            pages = self.extract_pages_from_raw_text()   # 从原始文本文件加载页面
            print(f"[OK] 已加载预抽取文本: {self.raw_text_path.name} | 页数: {len(pages)}")   # 打印成功信息
            return pages   # 返回提取的页面

        raise FileNotFoundError(   # 所有方式都失败，抛出文件未找到异常
            f"未找到可用输入。请确认 PDF 或回退文本存在: {self.pdf_path} / {self.raw_text_path}"
        )

    def extract_pages_with_pdfplumber(self) -> List[ExtractedPage]:   # 使用pdfplumber提取页面
        pages: List[ExtractedPage] = []   # 初始化页面列表
        with pdfplumber.open(str(self.pdf_path)) as pdf:   # 使用pdfplumber打开PDF文件
            for idx, page in enumerate(pdf.pages, start=1):   # 遍历每一页，从1开始编号
                body_lines, headers, footers = self.extract_body_lines_pdfplumber(page)   # 提取正文行、页眉、页脚
                table_blocks = self.extract_table_blocks_pdfplumber(page)   # 提取表格块
                pages.append(   # 将提取的内容添加到页面列表
                    ExtractedPage(   # 创建ExtractedPage对象
                        page_no=idx,   # 页码
                        body_lines=body_lines,   # 正文行
                        table_blocks=table_blocks,   # 表格块
                        headers=headers,   # 页眉
                        footers=footers,   # 页脚
                    )
                )
        return pages   # 返回提取的页面列表

    def extract_body_lines_pdfplumber(self, page) -> Tuple[List[str], List[str], List[str]]:
        # 使用pdfplumber提取页面正文、页眉、页脚
        page_height = float(page.height or 0)   # 获取页面高度，如果为None则用0
        header_limit = page_height * 0.10   # 页眉区域：页面顶部10%
        footer_limit = page_height * 0.90   # 页脚区域：页面底部10%

        words = page.extract_words(   # 提取页面中的所有单词（带位置信息）
            x_tolerance=2,   # 水平方向容差2像素
            y_tolerance=3,   # 垂直方向容差3像素
            keep_blank_chars=False,   # 不保留空白字符
            use_text_flow=True,   # 使用文本流顺序
        ) or []   # 如果提取失败则使用空列表

        rows: Dict[int, List[Tuple[float, str, float]]] = {}   # 按Y坐标分组的行字典
        headers: List[str] = []   # 页眉行列表
        footers: List[str] = []   # 页脚行列表

        for word in words:   # 遍历每个单词
            text = self.normalize_line(word.get("text", ""))   # 标准化单词文本
            if not text:   # 如果文本为空则跳过
                continue

            top = float(word.get("top", 0))   # 获取单词顶部Y坐标
            x0 = float(word.get("x0", 0))   # 获取单词左侧X坐标
            row_key = int(round(top / 3.0) * 3)   # 将Y坐标按3像素分组，作为行键
            rows.setdefault(row_key, []).append((x0, text, top))   # 将单词添加到对应行

        body_lines: List[str] = []   # 正文行列表
        for row_key in sorted(rows):   # 按行键排序遍历
            items = sorted(rows[row_key], key=lambda item: item[0])   # 按X坐标排序单词
            line = self.normalize_line(" ".join(item[1] for item in items))   # 合并单词成行并标准化
            if not line:   # 如果行为空则跳过
                continue

            top = items[0][2]   # 获取该行第一个单词的Y坐标
            if top <= header_limit:   # 如果在页眉区域
                headers.append(line)   # 添加到页眉
                continue
            if top >= footer_limit:   # 如果在页脚区域
                footers.append(line)   # 添加到页脚
                continue
            if self.should_drop_line(line):   # 如果该行应该被过滤
                continue
            body_lines.append(line)   # 添加到正文行

        return self.deduplicate_neighbor_lines(body_lines), headers, footers   # 返回去重后的正文、页眉、页脚

    def extract_table_blocks_pdfplumber(self, page) -> List[str]:   # 使用pdfplumber提取表格块
        tables = page.extract_tables(   # 提取页面中的表格
            table_settings={   # 表格检测设置
                "vertical_strategy": "lines",   # 垂直策略：基于线条
                "horizontal_strategy": "lines",   # 水平策略：基于线条
                "snap_tolerance": 3,   # 对齐容差3像素
                "join_tolerance": 3,   # 连接容差3像素
                "intersection_tolerance": 3,   # 交叉点容差3像素
            }
        ) or []   # 如果提取失败则用空列表
        blocks: List[str] = []   # 表格块列表
        for table in tables:   # 遍历每个表格
            rows = []   # 表格行列表
            for row in table or []:   # 遍历表格中的每一行
                cells = [self.normalize_cell(cell) for cell in (row or [])]   # 标准化每个单元格
                if not any(cells):   # 如果整行都没有有效内容则跳过
                    continue
                rows.append(" | ".join(cells))   # 用竖线连接单元格形成行字符串
            if rows:   # 如果有有效行
                blocks.append("[TABLE]\n" + "\n".join(rows))   # 添加表格块标记和表格内容
        return blocks   # 返回表格块列表

    def extract_pages_with_basic_reader(self) -> List[ExtractedPage]:   # 使用基础PDF阅读器提取页面
        reader = PdfReader(str(self.pdf_path))   # 创建PDF阅读器对象
        pages: List[ExtractedPage] = []   # 初始化页面列表
        for idx, page in enumerate(reader.pages, start=1):   # 遍历每一页
            text = page.extract_text() or ""   # 提取页面的原始文本
            body_lines = [line for line in (self.normalize_line(x) for x in text.splitlines()) if line and not self.should_drop_line(line)]
            # 逐行标准化，过滤掉空行和需要删除的行
            pages.append(   # 添加到页面列表
                ExtractedPage(
                    page_no=idx,   # 页码
                    body_lines=self.deduplicate_neighbor_lines(body_lines),   # 去重后的正文行
                    table_blocks=[],   # 无表格提取能力，设为空列表
                    headers=[],   # 无页眉提取能力，设为空列表
                    footers=[],   # 无页脚提取能力，设为空列表
                )
            )
        return pages   # 返回页面列表

    def extract_pages_from_raw_text(self) -> List[ExtractedPage]:   # 从预抽取的原始文本文件加载页面
        pages: List[ExtractedPage] = []   # 初始化页面列表
        raw_pages = self.raw_text_path.read_text(encoding="utf-8").split("\f")   # 读取文件，按换页符\f分割
        for idx, page_text in enumerate(raw_pages, start=1):   # 遍历每一页
            lines = [self.normalize_line(x) for x in page_text.splitlines()]   # 逐行标准化
            body_lines = [line for line in lines if line and not self.should_drop_line(line)]   # 过滤空行和需要删除的行
            pages.append(   # 添加到页面列表
                ExtractedPage(
                    page_no=idx,   # 页码
                    body_lines=self.deduplicate_neighbor_lines(body_lines),   # 去重后的正文行
                    table_blocks=[],   # 无表格提取能力，设为空列表
                    headers=[],   # 无页眉提取能力，设为空列表
                    footers=[],   # 无页脚提取能力，设为空列表
                )
            )
        return pages   # 返回页面列表

    def save_cleaned_pages(self, pages: Sequence[ExtractedPage]) -> None:   # 保存清洗后的页面文本
        output_pages = []   # 输出页列表
        for page in pages:   # 遍历每一页
            lines = list(page.body_lines)   # 复制正文行
            if page.table_blocks:   # 如果有表格块
                lines.extend(page.table_blocks)   # 将表格块追加到行列表
            output_pages.append("\n".join(lines).strip())   # 用换行符连接行，去除首尾空白
        self.cleaned_text_output.write_text("\f".join(output_pages), encoding="utf-8")   # 用换页符连接各页并写入文件
        print(f"[OK] 已输出去页眉页脚/去图片后的清洗文本: {self.cleaned_text_output}")   # 打印成功信息

    def build_avatar_records(self, pages: Sequence[ExtractedPage]) -> List[Dict[str, str]]:   # 构建角色知识记录
        records: List[Dict[str, str]] = []   # 初始化记录列表

        for article in ARTICLE_CONFIGS:   # 遍历每篇课文的配置
            article_pages = [pages[index - 1] for index in range(article.start_page, article.end_page + 1) if 0 < index <= len(pages)]
            # 根据页码范围提取对应的页面（索引转换：页码-1）
            if not article_pages:   # 如果没有提取到页面则跳过
                continue

            lines: List[str] = []   # 正文行列表
            table_blocks: List[str] = []   # 表格块列表
            for page in article_pages:   # 遍历课文的所有页面
                lines.extend(page.body_lines)   # 追加正文行
                table_blocks.extend(page.table_blocks)   # 追加表格块

            article_lines = self.trim_to_title(lines, article.title)   # 截取标题之后的内容
            paragraphs = self.merge_lines(article_lines)   # 将行合并为段落
            normalized_paragraphs = self.normalize_paragraphs(paragraphs, article)   # 标准化段落

            if table_blocks:   # 如果有表格块
                normalized_paragraphs.extend(self.convert_table_blocks_to_paragraphs(table_blocks, article))   # 将表格转换为段落

            if not normalized_paragraphs:   # 如果没有有效段落则跳过
                continue

            records.extend(self.build_article_records(article, normalized_paragraphs))   # 为课文构建问答记录并添加到列表

        return records   # 返回记录列表

    def convert_table_blocks_to_paragraphs(self, table_blocks: Sequence[str], article: ArticleConfig) -> List[str]:
        # 将表格块转换为文本段落
        paragraphs: List[str] = []   # 初始化段落列表
        for idx, table in enumerate(table_blocks, start=1):   # 遍历每个表格，从1开始编号
            lines = [self.normalize_line(line) for line in table.splitlines() if self.normalize_line(line)]   # 标准化表格的每一行
            if not lines:   # 如果没有有效行则跳过
                continue
            payload = "；".join(line for line in lines if line != "[TABLE]")   # 用分号连接非标记行
            if not payload:   # 如果没有有效内容则跳过
                continue
            paragraphs.append(f"{article.title}相关表格{idx}：{payload}")   # 添加带标题和编号的段落
        return paragraphs   # 返回段落列表

    def build_vector_records(self, avatar_records: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
        # 从角色知识记录构建向量入库记录
        vector_records: List[Dict[str, str]] = []   # 初始化向量记录列表
        created_at = datetime.now().isoformat()   # 生成当前时间戳ISO格式

        for item in avatar_records:   # 遍历每条角色知识记录
            context_payload = {   # 构建上下文字段字典
                "avatar_id": item.get("avatar_id", ""),   # 角色ID
                "role": item.get("role", ""),   # 角色名称
                "section_title": item.get("section_title", ""),   # 章节标题
                "author": item.get("author", ""),   # 作者
                "category": item.get("category", ""),   # 文体类别
                "tag": item.get("tag", ""),   # 标签
            }
            question = item.get("question", "").strip()   # 获取并清洗问题文本
            answer = item.get("answer", "").strip()   # 获取并清洗回答文本
            if not question or not answer:   # 如果问题或回答为空则跳过
                continue
            vector_records.append(   # 添加向量记录
                {
                    "id": item["id"],   # 唯一标识
                    "source": item.get("source", "教师(语文).pdf"),   # 来源文件
                    "question": question,   # 问题
                    "answer": answer,   # 回答
                    "context": json.dumps({k: v for k, v in context_payload.items() if v}, ensure_ascii=False),   # 上下文JSON字符串
                    "text_length": len(question) + len(answer),   # 文本总长度
                    "created_at": created_at,   # 创建时间
                }
            )
        return vector_records   # 返回向量记录列表

    def save_avatar_records(self, records: Sequence[Dict[str, str]]) -> None:   # 保存角色知识JSON文件
        self.avatar_output_path.write_text(json.dumps(list(records), ensure_ascii=False, indent=2), encoding="utf-8")
        # 将记录列表转为JSON格式（保持中文，缩进2空格）并写入文件
        print(f"[OK] 已生成角色知识 JSON: {self.avatar_output_path} | 条数: {len(records)}")   # 打印成功信息

    def save_vector_records(self, records: Sequence[Dict[str, str]]) -> None:   # 保存向量记录文件
        records = list(records)   # 转为列表
        json_path = self.vector_output_dir / "chinese_teacher_vector_records.json"   # JSON文件路径
        jsonl_path = self.vector_output_dir / "chinese_teacher_vector_records.jsonl"   # JSONL文件路径
        json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")   # 写入JSON文件
        with jsonl_path.open("w", encoding="utf-8") as handle:   # 打开JSONL文件
            for item in records:   # 遍历每条记录
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")   # 写入一行JSON
        print(f"[OK] 已生成向量入库中间文件: {json_path}")   # 打印成功信息
        print(f"[OK] 已生成向量入库 JSONL: {jsonl_path}")   # 打印成功信息

    def insert_into_milvus(self, records: Sequence[Dict[str, str]]) -> int:   # 将向量记录插入Milvus数据库
        records = list(records)   # 转为列表
        if not records:   # 如果没有记录
            print("[WARN] 没有可入库的数据，跳过向量化与 Milvus 入库")   # 打印警告
            return 0   # 返回0

        if Collection is None or connections is None or utility is None:   # 如果pymilvus未安装
            print("[WARN] 未安装 pymilvus，已跳过 Milvus 入库")   # 打印警告
            return 0   # 返回0

        self.load_bge_model()   # 加载BGE-M3嵌入模型
        collection = self.ensure_collection("qa_embeddings")   # 确保Milvus集合存在
        existing_ids = self.fetch_existing_ids(collection, [item["id"] for item in records])   # 查询已存在的ID
        pending = [item for item in records if item["id"] not in existing_ids]   # 筛选需要插入的记录

        if not pending:   # 如果没有需要插入的记录
            print("[OK] Milvus 中已存在这批 PDF 知识，无需重复插入")   # 打印信息
            return 0   # 返回0

        inserted = 0   # 初始化插入计数器
        batch_size = 64   # 批量大小
        for start in range(0, len(pending), batch_size):   # 按批次遍历
            batch = pending[start:start + batch_size]   # 获取当前批次
            ids, sources, questions, answers, contexts, text_lengths, embeddings = [], [], [], [], [], [], []   # 初始化各字段列表
            for item in batch:   # 遍历批次中的每条记录
                text = f"{item['question']} {item['answer']}"   # 将问题和回答拼接作为编码文本
                ids.append(item["id"])   # 添加ID
                sources.append(item["source"][:50])   # 添加来源（截取前50字符）
                questions.append(item["question"][:2000])   # 添加问题（截取前2000字符）
                answers.append(item["answer"][:2000])   # 添加回答（截取前2000字符）
                contexts.append(item.get("context", "")[:2000])   # 添加上下文（截取前2000字符）
                text_lengths.append(int(item["text_length"]))   # 添加文本长度
                embeddings.append(self.embed(text))   # 生成文本向量并添加

            collection.insert([ids, sources, questions, answers, contexts, text_lengths, embeddings])   # 插入到Milvus
            inserted += len(batch)   # 累加插入数量
            print(f"[OK] 已写入 Milvus: {inserted}/{len(pending)}")   # 打印进度

        collection.flush()   # 刷新缓存，确保持久化
        try:
            collection.load()   # 加载集合到内存
        except Exception:   # 如果加载失败则忽略
            pass

        print(f"[OK] 已完成 Milvus 入库 | 新增条数: {inserted}")   # 打印完成信息
        return inserted   # 返回插入数量

    def load_bge_model(self) -> None:   # 加载BGE-M3嵌入模型
        if self.bge_model is not None:   # 如果模型已加载则直接返回
            return
        if SentenceTransformer is None:   # 如果sentence_transformers未安装
            print("[WARN] 未安装 sentence-transformers，将使用哈希向量作为降级方案")   # 打印警告
            return
        try:   # 尝试加载模型
            self.bge_model = SentenceTransformer(BGE_M3_PATH, device=DEVICE)   # 加载BGE-M3模型
            self.vector_dim = int(self.bge_model.get_sentence_embedding_dimension())   # 获取模型输出维度
            print(f"[OK] BGE-M3 加载成功 | 维度: {self.vector_dim} | 设备: {DEVICE}")   # 打印成功信息
        except Exception as exc:   # 如果加载失败
            self.bge_model = None   # 模型设为None
            self.vector_dim = 1024   # 使用默认维度1024
            print(f"[WARN] BGE-M3 加载失败，将使用哈希向量降级: {exc}")   # 打印警告

    def embed(self, text: str) -> List[float]:   # 将文本转换为向量
        if self.bge_model is not None:   # 如果BGE模型可用
            try:   # 尝试使用BGE模型编码
                return self.bge_model.encode(text, normalize_embeddings=True).tolist()   # 编码并归一化，转为Python列表
            except Exception as exc:   # 如果编码失败
                print(f"[WARN] BGE 编码失败，回退哈希向量: {exc}")   # 打印警告
        return self.hash_embedding(text, self.vector_dim)   # 使用哈希方法生成降级向量

    @staticmethod   # 静态方法装饰器
    def hash_embedding(text: str, dimension: int) -> List[float]:   # 使用哈希生成确定性向量（降级方案）
        digest = hashlib.md5(text.encode("utf-8")).digest()   # 计算文本的MD5哈希值（16字节）
        vector = [((digest[index % 16] * (index + 1)) % 256) / 255.0 for index in range(dimension)]
        # 生成dimension维向量：用哈希字节循环乘以索引位置，取模256后归一化到[0,1]
        norm = math.sqrt(sum(value * value for value in vector))   # 计算向量的L2范数
        if norm <= 0:   # 如果范数为0或负数
            return vector   # 直接返回（避免除零）
        return [value / norm for value in vector]   # 归一化向量

    def connect_milvus(self) -> None:   # 连接到Milvus数据库
        last_error: Optional[Exception] = None   # 记录最后一个错误
        for host in MILVUS_HOSTS:   # 遍历主机列表
            try:   # 尝试连接
                connections.connect(alias="default", host=host, port=MILVUS_PORT, timeout=5)   # 建立连接
                print(f"[OK] 已连接 Milvus: {host}:{MILVUS_PORT}")   # 打印成功信息
                return   # 成功则返回
            except Exception as exc:   # 如果连接失败
                last_error = exc   # 记录错误
                print(f"[WARN] Milvus 连接失败: {host}:{MILVUS_PORT} | {exc}")   # 打印警告
        if last_error is not None:   # 如果所有主机都失败
            raise last_error   # 抛出最后一个错误

    def ensure_collection(self, collection_name: str) -> "Collection":   # 确保Milvus集合存在
        self.connect_milvus()   # 先连接Milvus
        if utility.has_collection(collection_name):   # 如果集合已存在
            collection = Collection(collection_name)   # 获取集合对象
            try:
                collection.load()   # 尝试加载集合到内存
            except Exception:   # 如果加载失败则忽略
                pass
            return collection   # 返回集合

        fields = [   # 定义集合字段Schema
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),   # ID字段，变长字符串，最大64，主键
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50),   # 来源字段，变长字符串，最大50
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2000),   # 问题字段，变长字符串，最大2000
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=2000),   # 回答字段，变长字符串，最大2000
            FieldSchema(name="context", dtype=DataType.VARCHAR, max_length=2000),   # 上下文字段，变长字符串，最大2000
            FieldSchema(name="text_length", dtype=DataType.INT64),   # 文本长度字段，64位整数
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim),   # 向量字段，浮点数向量，维度为vector_dim
        ]
        schema = CollectionSchema(fields, description="QA embeddings with chinese teacher PDF knowledge")   # 创建集合Schema
        collection = Collection(collection_name, schema)   # 创建集合
        collection.create_index(   # 为向量字段创建索引
            "embedding",
            {"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}},   # 使用内积距离、IVF_FLAT索引类型
        )
        print(f"[OK] 已创建 Milvus 集合: {collection_name}")   # 打印成功信息
        return collection   # 返回集合

    def fetch_existing_ids(self, collection: "Collection", ids: Sequence[str]) -> set[str]:   # 查询已存在的ID
        existing: set[str] = set()   # 初始化已有ID集合
        batch_size = 64   # 批量大小
        for start in range(0, len(ids), batch_size):   # 按批次遍历
            batch = ids[start:start + batch_size]   # 获取当前批次
            expr = "id in [" + ", ".join(f'"{item}"' for item in batch) + "]"   # 构造查询表达式
            try:   # 尝试查询
                rows = collection.query(expr=expr, output_fields=["id"])   # 执行查询，只返回id字段
            except Exception:   # 如果查询失败
                rows = []   # 使用空列表
            for row in rows:   # 遍历查询结果
                value = row.get("id")   # 获取id值
                if value:   # 如果存在
                    existing.add(value)   # 添加到集合
        return existing   # 返回已有ID集合

    @staticmethod   # 静态方法
    def normalize_cell(value: Optional[str]) -> str:   # 标准化表格单元格内容
        if value is None:   # 如果值为None
            return ""   # 返回空字符串
        return " ".join(str(value).replace("\n", " ").split()).strip()   # 移除换行、多余空格后返回

    @staticmethod   # 静态方法
    def normalize_line(line: str) -> str:   # 标准化行文本
        line = line.replace("\u0007", "").replace("\u3000", " ").replace("\xa0", " ")   # 移除响铃符，替换全角空格和不断行空格
        line = re.sub(r"[ \t]+", " ", line)   # 将多个空格或制表符替换为单个空格
        return line.strip()   # 去除首尾空白后返回

    @staticmethod   # 静态方法
    def deduplicate_neighbor_lines(lines: Sequence[str]) -> List[str]:   # 去重相邻的重复行
        output: List[str] = []   # 初始化输出列表
        previous = None   # 记录上一行
        for line in lines:   # 遍历每一行
            if not line:   # 如果行为空则跳过
                continue
            if previous == line:   # 如果与上一行相同
                continue   # 跳过重复
            output.append(line)   # 添加到输出
            previous = line   # 更新上一行
        return output   # 返回去重后的列表

    @staticmethod   # 静态方法
    def should_drop_line(line: str) -> bool:   # 判断某行是否应该被丢弃
        if not line:   # 如果行为空
            return True   # 丢弃
        fixed_markers = (   # 固定标记列表
            "普通高中教科书",
            "选择性必修",
            "学习提示",
            "单元研习任务",
            "目录",
            "绿色印刷产品",
            "定价",
            "作者简介",
        )
        if any(marker in line for marker in fixed_markers):   # 如果包含任意固定标记
            return True   # 丢弃
        if re.fullmatch(r"\d+", line):   # 如果整行只有数字
            return True   # 丢弃（页码）
        if len(line) <= 1:   # 如果长度小于等于1
            return True   # 丢弃
        if line.startswith("第") and "单元" in line:   # 如果以"第"开头且包含"单元"
            return True   # 丢弃（单元标题）
        return False   # 其他情况保留

    @staticmethod   # 静态方法
    def trim_to_title(lines: Sequence[str], title: str) -> List[str]:   # 截取标题之后的内容
        title_candidates = {   # 标题候选集
            title,   # 原标题
            title.replace("（节选）", ""),   # 去掉"（节选）"
            title.replace("（之一）", ""),   # 去掉"（之一）"
        }
        lines = list(lines)   # 转为列表
        for index, line in enumerate(lines):   # 遍历每一行
            normalized = line.replace(" ", "")   # 移除空格便于匹配
            if any(candidate.replace(" ", "") in normalized for candidate in title_candidates):   # 如果找到标题
                return lines[index + 1:]   # 返回标题之后的行
        return lines   # 如果没找到标题，返回全部行

    @staticmethod   # 静态方法
    def merge_lines(lines: Iterable[str]) -> List[str]:   # 将行合并为段落
        paragraphs: List[str] = []   # 段落列表
        buffer = ""   # 缓冲区

        for line in lines:   # 遍历每一行
            if not line:   # 如果行是空行
                if buffer:   # 如果缓冲区不为空
                    paragraphs.append(buffer)   # 将缓冲区内容作为一个段落
                    buffer = ""   # 清空缓冲区
                continue   # 继续下一行

            if not buffer:   # 如果缓冲区为空
                buffer = line   # 将当前行放入缓冲区
                continue   # 继续下一行

            should_split = (   # 判断是否应该分割（新段落的开始）
                buffer.endswith(("。", "！", "？", "；", "”", "）"))   # 缓冲区以句子结束符结尾
                or line.startswith(("一、", "二、", "三、", "四、", "五、", "（", "("))   # 或者新行以序号开始
                or (line.startswith("第") and any(token in line for token in ("章", "节", "幕", "部")))   # 或者新行以章节开始
            )
            if should_split:   # 如果需要分割
                paragraphs.append(buffer)   # 将缓冲区作为段落
                buffer = line   # 新段落从当前行开始
            else:   # 如果不需要分割
                buffer += line   # 将当前行追加到缓冲区

        if buffer:   # 如果最后缓冲区不为空
            paragraphs.append(buffer)   # 添加最后一个段落

        return paragraphs   # 返回段落列表

    def normalize_paragraphs(self, paragraphs: Sequence[str], article: ArticleConfig) -> List[str]:
        # 标准化段落，过滤无效内容
        cleaned: List[str] = []   # 清洗后的段落列表
        dropped_values = {   # 需要丢弃的值集合
            article.title,   # 文章标题
            article.author,   # 作者名
            "（节选）",   # 节选标记
            "（之一）",   # 之一标记
        }
        for paragraph in paragraphs:   # 遍历每个段落
            text = self.clean_inline_text(paragraph)   # 清洗段落内文本
            if not text or text in dropped_values:   # 如果为空或是需丢弃的值
                continue
            if len(text) < 18:   # 如果长度小于18个字符
                continue   # 跳过短文本
            cleaned.append(text)   # 添加到清洗后列表
        return cleaned   # 返回清洗后的段落列表

    @staticmethod   # 静态方法
    def clean_inline_text(text: str) -> str:   # 清洗段落内文本
        compact = text.replace(" ", "").strip()   # 移除所有空格并去除首尾空白
        skip_prefixes = (   # 需要跳过的前缀列表
            "普通高中教科书",
            "选择性必修",
            "学习提示",
            "单元研习任务",
            "作者简介",
            "选自",
        )
        for prefix in skip_prefixes:   # 遍历每个前缀
            if compact.startswith(prefix):   # 如果文本以此前缀开头
                return ""   # 返回空字符串
        return compact   # 返回清洗后的文本

    def build_article_records(self, article: ArticleConfig, paragraphs: Sequence[str]) -> List[Dict[str, str]]:
        # 为单篇课文构建问答记录
        joined = "\n".join(paragraphs).strip()   # 将所有段落连接为一个字符串
        summary_seed = "".join(paragraphs[: min(4, len(paragraphs))]) or joined   # 摘要种子：最多取前4段
        summary = self.summarize(summary_seed, max_length=220)   # 生成摘要（最多220字）
        section_title = f"{article.title}（{article.author}）"   # 构建带作者的章节标题

        base_records = [   # 基础问答记录（3条）
            {
                "question": f"{article.title}的主要内容是什么？",   # 问题：主要内容
                "answer": f"{section_title}是一篇{article.category}。教材正文可概括为：{summary}",   # 回答：体裁+摘要
                "tag": "summary",   # 标签
            },
            {
                "question": f"{article.title}的主旨是什么？",   # 问题：主旨
                "answer": f"结合教材内容，{section_title}的核心可从正文理解为：{summary}",   # 回答：摘要
                "tag": "theme",   # 标签
            },
            {
                "question": f"{article.title}有哪些写作特点？",   # 问题：写作特点
                "answer": f"{section_title}可结合教材文本从语言、结构、人物或意象塑造与表达方式上分析。正文关键内容为：{summary}",   # 回答
                "tag": "features",   # 标签
            },
        ]

        chunk_records = []   # 分块问答记录
        for index, content in enumerate(paragraphs, start=1):   # 遍历每个段落
            if len(content) > 420:   # 如果段落长度超过420字符
                pieces = [content[offset:offset + 220] for offset in range(0, len(content), 220)]   # 按220字符切分
                for piece_index, piece in enumerate(pieces, start=1):   # 遍历每个片段
                    if len(piece) < 25:   # 如果片段长度小于25字符
                        continue   # 跳过过短片段
                    chunk_records.append(   # 添加片段问答
                        {
                            "question": f"{article.title}第{index}段第{piece_index}部分讲了什么？",   # 问题
                            "answer": piece,   # 回答：片段内容
                            "tag": f"chunk_{index}_{piece_index}",   # 标签
                        }
                    )
                continue   # 继续处理下一个段落

            if len(content) >= 25:   # 如果段落长度不小于25字符
                chunk_records.append(   # 添加段落问答
                    {
                        "question": f"{article.title}第{index}段讲了什么？",   # 问题
                        "answer": content,   # 回答：段落内容
                        "tag": f"chunk_{index}",   # 标签
                    }
                )

        source = f"教师(语文).pdf#{article.title}"   # 来源字符串
        output = []   # 输出记录列表
        for item in [*base_records, *chunk_records]:   # 遍历基础记录和分块记录
            record_id = self.sha1(f"{item['question']}|{item['answer']}|{source}")   # 生成唯一ID（SHA1哈希）
            output.append(   # 添加完整记录
                {
                    "id": record_id,   # 唯一标识
                    "avatar_id": "chinese_teacher",   # 角色ID
                    "role": "语文老师教材知识",   # 角色名称
                    "question": item["question"],   # 问题
                    "answer": item["answer"],   # 回答
                    "source": source,   # 来源
                    "section_title": article.title,   # 章节标题
                    "author": article.author,   # 作者
                    "category": article.category,   # 文体类别
                    "tag": item["tag"],   # 标签
                }
            )
        return output   # 返回记录列表

    @staticmethod   # 静态方法
    def summarize(text: str, max_length: int = 220) -> str:   # 生成文本摘要
        compact = text.replace("\n", "").strip()   # 移除换行符并去除首尾空白
        if len(compact) <= max_length:   # 如果长度不超过限制
            return compact   # 直接返回
        return compact[:max_length] + "……"   # 截取并添加省略号

    @staticmethod   # 静态方法
    def sha1(text: str) -> str:   # 计算SHA1哈希值
        return hashlib.sha1(text.encode("utf-8")).hexdigest()   # 返回十六进制字符串


def build_parser() -> argparse.ArgumentParser:   # 构建命令行参数解析器
    parser = argparse.ArgumentParser(description="Clean PDF, extract tables, build JSON and optionally insert vectors into Milvus.")
    # 创建参数解析器，带描述信息
    parser.add_argument("--pdf", default=str(PROJECT_ROOT / "教师(语文).pdf"), help="PDF path")   # PDF路径参数
    parser.add_argument("--raw-text", default=str(PROJECT_ROOT / "teacher_chinese_raw.txt"), help="Fallback extracted text path")
    # 降级文本路径参数
    parser.add_argument(
        "--avatar-output",
        default=str(PROJECT_ROOT / "processed_data" / "avatar_knowledge" / "chinese_teacher.json"),
        help="Avatar knowledge JSON output path",   # 角色知识JSON输出路径
    )
    parser.add_argument(
        "--vector-output-dir",
        default=str(PROJECT_ROOT / "processed_data"),
        help="Directory for normalized vector records",   # 向量记录输出目录
    )
    parser.add_argument(
        "--cleaned-text-output",
        default=str(PROJECT_ROOT / "processed_data" / "teacher_chinese_cleaned.txt"),
        help="Cleaned text output path",   # 清洗后文本输出路径
    )
    parser.add_argument("--skip-vector", action="store_true", help="Only generate cleaned text and JSON, skip BGE/Milvus")
    # 跳过向量化标志
    return parser   # 返回解析器


def main() -> None:   # 主函数
    args = build_parser().parse_args()   # 解析命令行参数
    pipeline = ChineseTeacherPDFPipeline(   # 创建处理管道实例
        pdf_path=Path(args.pdf),   # PDF路径
        raw_text_path=Path(args.raw_text),   # 降级文本路径
        avatar_output_path=Path(args.avatar_output),   # 角色知识输出路径
        vector_output_dir=Path(args.vector_output_dir),   # 向量输出目录
        cleaned_text_output=Path(args.cleaned_text_output),   # 清洗文本输出路径
    )
    result = pipeline.run(skip_vector=args.skip_vector)   # 运行管道
    print(json.dumps(result, ensure_ascii=False, indent=2))   # 打印结果JSON


if __name__ == "__main__":   # 如果直接运行此脚本
    main()   # 调用主函数
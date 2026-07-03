"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
初始化 RAG 知识库 —— 将生成的医学数据集导入向量数据库
"""

import json  # 导入JSON模块，用于解析JSON格式数据集文件
import os  # 导入操作系统接口模块，用于环境变量和路径操作
import sys  # 导入系统模块，用于修改Python搜索路径
import logging  # 导入日志模块，用于记录初始化进度和状态
from pathlib import Path  # 导入Path用于跨平台文件路径处理

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 将backend目录添加到Python搜索路径，确保能导入项目模块

from rag.vector_store import get_vector_store  # 从RAG模块导入向量存储单例工厂函数
from config import KNOWLEDGE_DIR  # 从项目配置导入知识库数据目录路径

_log = logging.getLogger("medical_agent.rag.init_knowledge")  # 创建模块级日志记录器，标识为"medical_agent.rag.init_knowledge"


def load_json_dataset(filepath: str) -> list:  # 加载JSON数据集文件的函数
    with open(filepath, "r", encoding="utf-8") as f:  # 以UTF-8编码打开JSON文件（只读模式）
        return json.load(f)  # 解析并返回JSON内容（列表或字典形式）


def init_from_vqa_dataset(data: list):  # 初始化VQA（视觉问答）数据集到向量数据库
    vs = get_vector_store()  # 获取向量存储单例
    docs, metadatas = [], []  # 初始化文档内容列表和元数据列表为空
    for item in data:  # 遍历数据集中的每条记录
        content = f"问题：{item.get('question', '')}\n回答：{item.get('answer', '')}"  # 构建文档内容：将问题和回答拼接为一条知识条目
        docs.append(content)  # 将构建的文档内容添加到列表
        metadatas.append({  # 构建元数据字典并添加到列表
            "source": "VQA数据集", "data_type": "vqa",  # 来源标记为VQA数据集，数据类型为vqa
            "image_type": item.get("image_type", ""),  # 影像类型（如X光、CT、MRI等）
            "body_part": item.get("body_part", ""),  # 身体部位（如胸部、头部等）
            "difficulty": item.get("difficulty", ""),  # 问题难度等级
        })
    if docs:  # 如果有待入库的文档
        count = vs.add_documents(docs, metadatas)  # 将文档和元数据批量写入向量数据库
        _log.info("VQA 数据集入库: %d 条", count)  # 记录入库数量日志
    return len(docs)  # 返回处理的文档总数


def init_from_mrg_dataset(data: list):  # 初始化MRG（医学报告生成）数据集到向量数据库
    vs = get_vector_store()  # 获取向量存储单例
    docs, metadatas = [], []  # 初始化文档内容列表和元数据列表为空
    for item in data:  # 遍历MRG数据集中的每条记录
        content = (  # 构建多字段拼接的文档内容
            f"检查项目：{item.get('examination', '')}\n"  # 检查项目名称
            f"临床指征：{item.get('clinical_indication', '')}\n"  # 临床指征（为什么做这个检查）
            f"检查技术：{item.get('technique', '')}\n"  # 检查技术/方法
            f"影像所见：{item.get('findings', '')}\n"  # 影像学发现
            f"诊断印象：{item.get('impression', '')}\n"  # 诊断印象/结论
            f"建议：{item.get('recommendations', '')}"  # 进一步建议
        )
        docs.append(content)  # 将拼接好的报告内容添加到列表
        metadatas.append({  # 构建元数据字典
            "source": "MRG数据集", "data_type": "mrg",  # 来源为MRG数据集，数据类型为mrg
            "report_type": item.get("report_type", ""),  # 报告类型
            "urgency": item.get("urgency", ""),  # 紧急程度
        })
    if docs:  # 如果有待入库的文档
        count = vs.add_documents(docs, metadatas)  # 将文档和元数据写入向量数据库
        _log.info("MRG 数据集入库: %d 条", count)  # 记录入库数量日志
    return len(docs)  # 返回处理的文档总数


def init_from_rag_dataset(data: list):  # 初始化RAG（检索增强生成）知识库数据集
    vs = get_vector_store()  # 获取向量存储单例
    docs, metadatas = [], []  # 初始化文档内容列表和元数据列表为空
    for item in data:  # 遍历RAG知识库中的每条记录
        docs.append(item.get("content", ""))  # 直接使用content字段作为文档内容
        metadatas.append({  # 构建元数据字典
            "source": "RAG知识库", "data_type": "rag",  # 来源标记为RAG知识库
            "category": item.get("category", ""),  # 知识分类（如疾病知识、药物知识等）
            "title": item.get("title", ""),  # 知识条目标题
            "keywords": ",".join(item.get("keywords", [])),  # 关键词列表转为逗号分隔字符串
            "source_type": item.get("source_type", ""),  # 来源类型（如教科书、论文、指南等）
        })
    if docs:  # 如果有待入库的文档
        count = vs.add_documents(docs, metadatas)  # 写入向量数据库
        _log.info("RAG 知识库入库: %d 条", count)  # 记录入库数量日志
    return len(docs)  # 返回处理的文档总数


def init_from_slake(data: list):  # 初始化SLAKE（开源医学VQA数据集）到向量数据库
    vs = get_vector_store()  # 获取向量存储单例
    docs, metadatas = [], []  # 初始化文档内容列表和元数据列表为空
    for item in data:  # 遍历SLAKE数据集中的每条记录
        question = item.get("question", "")  # 提取问题字段
        answer = item.get("answer", "")  # 提取答案字段
        if question and answer:  # 仅处理同时包含问题和答案的有效记录
            docs.append(f"问题：{question}\n回答：{answer}")  # 将问题和答案拼接为文档内容
            metadatas.append({  # 构建元数据字典
                "source": "SLAKE公开数据集", "data_type": "slake_vqa",  # 来源为SLAKE公开数据集
                "modality": item.get("modality", ""),  # 影像模态（CT、MRI、X-ray等）
                "location": item.get("location", ""),  # 身体部位/位置信息
                "content_type": item.get("content_type", ""),  # 内容类型
                "answer_type": item.get("answer_type", ""),  # 答案类型（是否判断题/开放式/封闭式）
            })
    if docs:  # 如果有有效记录
        count = vs.add_documents(docs, metadatas)  # 写入向量数据库
        _log.info("SLAKE 数据集入库: %d 条", count)  # 记录入库数量日志
    return len(docs)  # 返回处理的文档总数


def main(data_dir: str = None):  # 主函数：执行完整知识库初始化流程
    _log.info("=" * 50)  # 打印分隔线
    _log.info("初始化 RAG 医学知识库")  # 记录开始初始化日志
    _log.info("工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0")  # 记录工单编号
    _log.info("=" * 50)  # 打印分隔线

    total = 0  # 初始化总入库计数器为0
    if data_dir:  # 如果通过参数指定了数据目录
        base = Path(data_dir)  # 使用指定目录作为基路径
    else:  # 否则使用默认路径推断
        base = Path(os.getenv("MEDICAL_DATA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent)))  # 从环境变量读取数据目录，默认通过文件路径向上4层推断

    synthetic_dir = base / "medical_imaging_dataset"  # 构造合成医学影像数据集目录路径
    public_dir = base / "public_medical_datasets"  # 构造公开医学数据集目录路径

    synthetic_files = {  # 建立合成数据集文件名到初始化函数的映射字典
        "vqa_dataset.json": init_from_vqa_dataset,  # VQA数据集→init_from_vqa_dataset
        "mrg_dataset.json": init_from_mrg_dataset,  # MRG数据集→init_from_mrg_dataset
        "rag_knowledge_base.json": init_from_rag_dataset,  # RAG知识库→init_from_rag_dataset
    }

    for fname, init_func in synthetic_files.items():  # 遍历合成数据集的映射字典
        fpath = synthetic_dir / fname  # 拼接完整的文件路径
        if fpath.exists():  # 如果文件存在
            _log.info("处理: %s", fname)  # 记录正在处理的文件名
            data = load_json_dataset(str(fpath))  # 加载JSON数据集
            total += init_func(data)  # 调用对应的初始化函数处理数据，累加处理数量
        else:  # 如果文件不存在
            _log.warning("文件不存在: %s", fpath)  # 记录警告日志

    slake_dir = public_dir / "SLAKE"  # 构造SLAKE公开数据集目录路径
    for fname in ["slake_train.json", "slake_validation.json", "slake_test.json"]:  # 遍历SLAKE的三个子数据集（训练集、验证集、测试集）
        fpath = slake_dir / fname  # 拼接完整文件路径
        if fpath.exists():  # 如果文件存在
            _log.info("处理: SLAKE/%s", fname)  # 记录正在处理的SLAKE文件名
            data = load_json_dataset(str(fpath))  # 加载JSON数据集
            total += init_from_slake(data)  # 调用SLAKE初始化函数，累加处理数量

    medqa_path = public_dir / "Medical-Meadow-MedQA" / "medqa_train.json"  # 构造MedQA医学问答数据集训练集路径
    if medqa_path.exists():  # 如果MedQA训练集文件存在
        _log.info("处理: MedQA/medqa_train.json")  # 记录正在处理MedQA
        data = load_json_dataset(str(medqa_path))  # 加载JSON数据集
        vs = get_vector_store()  # 获取向量存储单例
        docs, metadatas = [], []  # 初始化文档和元数据列表
        for item in data[:5000]:  # 只处理前5000条记录（防止数据量过大导致内存溢出）
            inp, outp = item.get("input", ""), item.get("output", "")  # 提取输入（问题）和输出（答案）字段
            if inp and outp:  # 仅处理同时有输入和输出的有效记录
                docs.append(f"{inp}\n{outp}")  # 将问题和答案拼接为一条文档
                metadatas.append({"source": "MedQA公开数据集", "data_type": "medqa"})  # 添加元数据：来源为MedQA公开数据集
        if docs:  # 如果有有效记录
            count = vs.add_documents(docs, metadatas)  # 批量写入向量数据库
            total += count  # 累加到总数
            _log.info("MedQA 数据集入库: %d 条", count)  # 记录MedQA入库数量

    _log.info("=" * 50)  # 打印分隔线
    _log.info("知识库初始化完成！共导入 %d 条知识", total)  # 记录初始化完成，输出导入总数
    _log.info("当前知识库文档数: %d", get_vector_store().count())  # 查询并记录当前向量数据库中的文档总数
    _log.info("=" * 50)  # 打印分隔线


if __name__ == "__main__":  # 如果脚本作为主程序直接运行（而非作为模块导入）
    import argparse  # 导入命令行参数解析模块
    parser = argparse.ArgumentParser(description="初始化 RAG 医学知识库")  # 创建参数解析器，设置描述文字
    parser.add_argument("--data-dir", help="数据目录路径")  # 添加--data-dir可选参数，用于指定数据目录
    args = parser.parse_args()  # 解析命令行参数
    main(data_dir=args.data_dir)  # 调用主函数，传入数据目录参数（可能为None）

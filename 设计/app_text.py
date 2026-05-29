"""
app_text — ADSD 项目在线模块文本处理与角色配置。

功能说明：
- 定义默认查询问题、乱码检测标记和备用角色配置
- 提供文本乱码修复函数 repair_text()（GBK→UTF-8 转换修复）
- 构建角色目录 catalog（合并 config.AVATARS 与 FALLBACK_AVATARS）
- 加载本地知识库文档（JSONL/JSON 格式）
- 加载角色专属知识库文档
"""
# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

import json
# 导入json模块，用于解析和生成JSON数据
import logging
# 导入logging模块，用于输出日志信息
from pathlib import Path
# 从pathlib导入Path，用于跨平台路径操作

from 设计.config import AVATARS
# 从配置模块导入预设的角色配置字典
from 研发.utils import generate_doc_id
# 从工具模块导入文档ID生成函数

logger = logging.getLogger(__name__)
# 获取当前模块的日志记录器实例

# 获取当前文件所在目录的绝对路径
BASE_DIR = Path(__file__).resolve().parent.parent

# 默认查询问题（用于演示或测试场景）
DEFAULT_QUERY = "兰蔻小黑瓶具备哪些基础功能？"

# 乱码检测标记（常见于GBK误读为UTF-8时出现的特征字符）
MOJIBAKE_MARKERS = ("鍖", "鐧", "璇", "锛", "銆", "鎴", "浣", "鍙", "鐩", "鏄", "绯")

# 默认角色配置（当config.AVATARS中缺少配置时使用）
FALLBACK_AVATARS = {
    "doctor": {
        # 医生角色的默认配置
        "name": "医生",
        # 角色显示名称
        "icon": "医",
        # 图标文字
        "color": "#0f766e",
        # 主题颜色（深青色）
        "desc": "健康咨询、症状分析、日常护理建议",
        # 角色描述
        "welcome": "你好，我是医生助手。请描述你的问题、持续时间和担忧点。",
        # 欢迎语
        "prompt": "你是一位专业、谨慎、简洁的医生助手。请基于上下文给出清晰建议，必要时提醒线下就医。",
        # 系统提示词
        "suggestions": [
            # 示例问题列表
            "最近总头痛怎么缓解",
            "感冒发烧需要注意什么",
            "熬夜后心慌正常吗",
        ],
    },
    "psychologist": {
        # 心理顾问角色的默认配置
        "name": "心理顾问",
        "icon": "心",
        "color": "#f97316",
        "desc": "情绪疏导、压力陪伴、关系沟通建议",
        "welcome": "你好，我是心理顾问助手。你可以跟我聊焦虑、压力、低落或关系问题。",
        "prompt": "你是一位温和、有共情、具体务实的心理支持助手。避免做医学诊断，优先提供可执行建议。",
        "suggestions": [
            "最近很焦虑睡不着怎么办",
            "和朋友关系变差后很难受",
            "情绪低落时怎么先稳住自己",
        ],
    },
    "marketer": {
        # 营销专家角色的默认配置
        "name": "营销专家",
        "icon": "营",
        "color": "#111827",
        "desc": "品牌增长、内容策略、转化优化",
        "welcome": "你好，我是营销专家助手。你可以问我品牌定位、增长策略、内容或转化问题。",
        "prompt": "你是一位懂增长和品牌策略的营销专家。请给出结构化、可执行、避免空话的方案。",
        "suggestions": [
            "新品牌冷启动第一步怎么做",
            "短视频账号如何提高转化",
            "线下活动怎么做传播闭环",
        ],
    },
    "chinese_teacher": {
        # 语文老师角色的默认配置
        "name": "语文老师",
        "icon": "文",
        "color": "#7c3aed",
        "desc": "课文讲解、文言文分析、阅读与写作指导",
        "welcome": "你好，我是语文老师助手。你可以问我课文内容、主旨、写法、文言词句或答题思路。",
        "prompt": "你是一位严谨、耐心、表达清楚的高中语文老师。请优先依据教材内容回答，必要时分点说明，并结合篇名、主旨和写作特点作答。",
        "suggestions": [
            "《屈原列传》的主要内容是什么",
            "《荷花淀》的艺术特色有哪些",
            "《锦瑟》表达了怎样的情感",
        ],
    },
}


def repair_text(value):
    # 定义函数：修复文本乱码（将GBK误读为UTF-8导致的乱码恢复为正常中文）

    """
    修复文本乱码（将GBK误读为UTF-8导致的乱码恢复为正常中文）

    参数:
        value: 待修复的文本（可以是字符串或其他类型）

    返回:
        修复后的文本，如果无需修复则返回原值
    """
    if not isinstance(value, str) or not value:
        # 如果不是字符串或者为空值（None/空字符串）
        return value
        # 直接返回原值，不做任何处理

    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        # 检查文本中是否包含乱码特征字符
        return value
        # 如果没有乱码特征，直接返回原值，避免不必要的开销

    try:
        repaired = value.encode("gbk", errors="ignore").decode("utf-8", errors="ignore").strip()
        # 尝试修复乱码：先将字符串按GBK编码（忽略错误字符），再按UTF-8解码（忽略错误字符）
        if repaired:
            # 如果修复后非空
            return repaired
            # 返回修复后的文本
    except Exception:
        # 捕获任何编码/解码异常
        return value
        # 修复失败时返回原值

    return value
    # 兜底返回原值


def build_avatar_catalog():
    # 定义函数：构建完整的角色目录（合并配置文件中的AVATARS和本模块的FALLBACK_AVATARS）

    """
    构建角色目录（合并配置文件和默认配置）

    返回:
        dict: 完整的角色配置字典
    """
    catalog = {}
    # 初始化空字典，用于存储构建好的角色目录

    for avatar_id, fallback in FALLBACK_AVATARS.items():
        # 遍历FALLBACK_AVATARS中的每个角色（以fallback为基准）
        raw = AVATARS.get(avatar_id, {})
        # 从config.AVATARS中获取该角色的配置，没有则返回空字典

        catalog[avatar_id] = {
            # 构建该角色的最终配置，优先使用config中的值（raw），否则使用fallback中的值
            "name": repair_text(raw.get("name", fallback["name"])) or fallback["name"],
            # 角色名称：config > fallback，并修复乱码
            "icon": repair_text(raw.get("icon", fallback["icon"])) or fallback["icon"],
            # 图标：config > fallback
            "color": raw.get("color", fallback["color"]) or fallback["color"],
            # 主题颜色：config > fallback
            "desc": repair_text(raw.get("desc", fallback["desc"])) or fallback["desc"],
            # 角色描述：config > fallback
            "welcome": repair_text(raw.get("welcome", fallback["welcome"])) or fallback["welcome"],
            # 欢迎语：config > fallback
            "prompt": repair_text(raw.get("prompt", fallback["prompt"])) or fallback["prompt"],
            # 系统提示词：config > fallback
            "suggestions": [
                # 示例问题列表：config > fallback，每个问题都进行乱码修复
                repair_text(item) or fallback["suggestions"][0]
                # 如果修复后为空，使用fallback的第一个示例问题
                for item in raw.get("suggestions", fallback["suggestions"])
            ] or fallback["suggestions"],
            # 如果列表整体为空，使用fallback
        }

    for avatar_id, raw in AVATARS.items():
        # 遍历config.AVATARS中的每个角色，找出fallback中不存在的角色
        if avatar_id in catalog:
            # 如果已经在catalog中（之前已处理）
            continue
            # 跳过，不再重复处理

        catalog[avatar_id] = {
            # 为新增的角色构建配置（仅使用config中的值，没有fallback）
            "name": repair_text(raw.get("name", avatar_id)) or avatar_id,
            # 角色名称，默认使用avatar_id
            "icon": repair_text(raw.get("icon", "AI")) or "AI",
            # 图标，默认"AI"
            "color": raw.get("color", "#0f766e") or "#0f766e",
            # 颜色，默认深青色
            "desc": repair_text(raw.get("desc", "智能助手")) or "智能助手",
            # 描述，默认"智能助手"
            "welcome": repair_text(raw.get("welcome", "你好，请描述你的问题。")) or "你好，请描述你的问题。",
            # 欢迎语
            "prompt": repair_text(raw.get("prompt", "你是一位专业 AI 助手。")) or "你是一位专业 AI 助手。",
            # 系统提示词
            "suggestions": [repair_text(item) or "给我一个可执行建议" for item in raw.get("suggestions", [])],
            # 示例问题列表，每个问题都修复乱码
        }

    return catalog
    # 返回构建好的完整角色目录


# 全局变量：经过清理和合并的角色配置字典（模块加载时构建一次）
SANITIZED_AVATARS = build_avatar_catalog()


def load_local_documents(base_dir=None):
    # 定义函数：加载本地知识库文档

    """
    加载本地知识库文档

    参数:
        base_dir: 基础目录路径（默认为当前文件所在目录）

    返回:
        list: 文档列表，每个文档包含 doc_id, question, answer, source 字段
    """
    base_dir = Path(base_dir or BASE_DIR)
    # 确定基础目录：使用传入的base_dir或默认的BASE_DIR

    candidates = [
        # 可能的知识库文件路径列表（按优先级排序）
        base_dir / "vector_index" / "all_data.jsonl",
        # 向量索引目录下的jsonl文件
        base_dir / "vector_index" / "vector_index" / "all_data.jsonl",
        # 嵌套vector_index目录
        base_dir / "processed_data" / "all_data_merged.json",
        # 处理后的json文件
        base_dir / "vector_index" / "processed_data" / "all_data_merged.json",
        # 向量索引下的json文件
    ]

    for path in candidates:
        # 遍历候选路径，找到第一个存在的文件
        if not path.exists():
            # 如果文件不存在
            continue
            # 尝试下一个候选路径

        try:
            documents = []
            # 初始化空列表，用于存储解析后的文档

            if path.suffix == ".jsonl":
                # 根据文件扩展名判断：如果是.jsonl文件
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    # 以UTF-8编码读取文件内容，按行分割
                    line = raw_line.strip()
                    # 去除每行的首尾空白
                    if not line:
                        # 如果是空行
                        continue
                        # 跳过

                    payload = json.loads(line)
                    # 解析JSON行

                    question = repair_text(payload.get("question", ""))
                    # 提取问题文本并修复乱码
                    answer = repair_text(payload.get("answer", ""))
                    # 提取答案文本并修复乱码
                    source = repair_text(payload.get("source", ""))
                    # 提取来源信息并修复乱码

                    doc_id = payload.get("id") or generate_doc_id(question, answer, source)
                    # 生成文档ID：优先使用文件中已有的id，否则根据内容生成

                    documents.append(
                        # 将文档添加到列表
                        {
                            "doc_id": doc_id,
                            # 文档唯一标识
                            "question": question,
                            # 问题文本
                            "answer": answer,
                            # 答案文本
                            "source": source,
                            # 来源信息
                        }
                    )
            else:
                # 如果是.json文件（JSON数组格式）
                for payload in json.loads(path.read_text(encoding="utf-8")):
                    # 解析整个JSON文件（期望是一个数组），遍历每个元素

                    question = repair_text(payload.get("question", ""))
                    # 提取并修复问题文本
                    answer = repair_text(payload.get("answer", ""))
                    # 提取并修复答案文本
                    source = repair_text(payload.get("source", ""))
                    # 提取并修复来源信息

                    doc_id = payload.get("id") or generate_doc_id(question, answer, source)
                    # 生成文档ID

                    documents.append(
                        # 添加到文档列表
                        {
                            "doc_id": doc_id,
                            "question": question,
                            "answer": answer,
                            "source": source,
                        }
                    )

            if documents:
                # 如果成功解析到文档
                logger.info("已加载本地知识库: %s | 文档数: %s", path, len(documents))
                # 记录成功日志
                return documents
                # 返回文档列表

        except Exception as exc:
            # 捕获解析过程中的任何异常
            logger.warning("加载知识库失败: %s | %s", path, exc)
            # 记录警告日志，继续尝试下一个路径

    logger.warning("未加载到可用知识库文件")
    # 所有候选路径都失败，记录警告
    return []
    # 返回空列表


def load_avatar_documents(base_dir=None):
    # 定义函数：加载角色专属知识库文档

    """
    加载角色专属知识库文档

    参数:
        base_dir: 基础目录路径（默认为当前文件所在目录）

    返回:
        dict: {avatar_id: [document, ...]}
    """
    base_dir = Path(base_dir or BASE_DIR)
    # 确定基础目录
    avatar_documents = {}
    # 初始化空字典，用于存储各角色的文档列表

    candidates = [
        # 可能的角色知识库文件夹路径列表
        base_dir / "processed_data" / "avatar_knowledge",
        # 处理后的数据目录下的avatar_knowledge文件夹
        base_dir / "vector_index" / "processed_data" / "avatar_knowledge",
        # 向量索引目录下的avatar_knowledge文件夹
    ]

    for folder in candidates:
        # 遍历候选文件夹
        if not folder.exists() or not folder.is_dir():
            # 如果文件夹不存在或不是目录
            continue
            # 跳过

        for path in sorted(folder.glob("*.json")):
            # 遍历文件夹下所有.json文件（按名称排序）
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                # 以UTF-8编码读取JSON文件内容并解析
            except Exception as exc:
                # 如果解析失败
                logger.warning("加载角色知识库失败: %s | %s", path, exc)
                # 记录警告日志
                continue
                # 跳过该文件，继续处理下一个

            if not isinstance(payload, list):
                # 如果解析结果不是数组格式
                logger.warning("角色知识库格式无效: %s", path)
                # 记录警告日志
                continue
                # 跳过

            documents = []
            # 初始化空列表，用于存储该角色的文档
            avatar_id = path.stem
            # 从文件名（不含扩展名）获取角色ID

            for item in payload:
                # 遍历数组中的每个文档项
                if not isinstance(item, dict):
                    # 如果项不是字典格式
                    continue
                    # 跳过

                question = repair_text(item.get("question", ""))
                # 提取并修复问题文本
                answer = repair_text(item.get("answer", ""))
                # 提取并修复答案文本
                source = repair_text(item.get("source", path.name))
                # 提取来源信息，缺省使用文件名
                doc_avatar_id = item.get("avatar_id", avatar_id) or avatar_id
                # 获取文档关联的角色ID，缺省使用文件名对应的角色ID

                if not question and not answer:
                    # 如果问题和答案都为空
                    continue
                    # 跳过无效文档

                documents.append(
                    # 将文档添加到该角色的文档列表
                    {
                        "doc_id": item.get("id") or generate_doc_id(question, answer, source),
                        # 文档ID
                        "question": question,
                        # 问题
                        "answer": answer,
                        # 答案
                        "source": source,
                        # 来源
                        "avatar_id": doc_avatar_id,
                        # 关联的角色ID
                        "section_title": repair_text(item.get("section_title", "")),
                        # 章节标题（如果有）
                    }
                )

            if documents:
                # 如果该文件解析到文档
                avatar_documents[avatar_id] = documents
                # 存入字典，键为角色ID，值为文档列表
                logger.info("已加载角色知识库: %s | 角色: %s | 文档数: %s", path, avatar_id, len(documents))
                # 记录成功日志

        if avatar_documents:
            # 如果已经加载到角色文档
            break
            # 停止继续搜索其他文件夹

    if not avatar_documents:
        # 如果没有加载到任何角色文档
        logger.info("未加载到角色专属知识库文件")
        # 记录信息日志

    return avatar_documents
    # 返回角色文档字典

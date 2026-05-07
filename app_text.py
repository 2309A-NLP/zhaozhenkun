# -*- coding: utf-8 -*-
import json
import logging
from pathlib import Path

from config import AVATARS  # 从配置模块导入角色配置
from utils import generate_doc_id  # 导入文档ID生成工具函数

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器

# 获取当前文件所在目录的绝对路径
BASE_DIR = Path(__file__).resolve().parent

# 默认查询问题（用于演示或测试场景）
DEFAULT_QUERY = "兰蔻小黑瓶具备哪些基础功能？"

# 乱码检测标记（常见于GBK误读为UTF-8时出现的特征字符）
MOJIBAKE_MARKERS = ("鍖", "鐧", "璇", "锛", "銆", "鎴", "浣", "鍙", "鐩", "鏄", "绯")

# 默认角色配置（当config.AVATARS中缺少配置时使用）
FALLBACK_AVATARS = {
    "doctor": {  # 医生角色
        "name": "医生",  # 角色显示名称
        "icon": "医",  # 图标文字
        "color": "#0f766e",  # 主题颜色
        "desc": "健康咨询、症状分析、日常护理建议",  # 角色描述
        "welcome": "你好，我是医生助手。请描述你的问题、持续时间和担忧点。",  # 欢迎语
        "prompt": "你是一位专业、谨慎、简洁的医生助手。请基于上下文给出清晰建议，必要时提醒线下就医。",  # 系统提示词
        "suggestions": [  # 示例问题列表
            "最近总头痛怎么缓解",
            "感冒发烧需要注意什么",
            "熬夜后心慌正常吗",
        ],
    },
    "psychologist": {  # 心理顾问角色
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
    "marketer": {  # 营销专家角色
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
}


def repair_text(value):
    """
    修复文本乱码（将GBK误读为UTF-8导致的乱码恢复为正常中文）

    参数:
        value: 待修复的文本（可以是字符串或其他类型）

    返回:
        修复后的文本，如果无需修复则返回原值
    """
    # 如果不是字符串或为空，直接返回原值
    if not isinstance(value, str) or not value:
        return value

    # 如果没有乱码特征标记，直接返回原值（避免不必要的处理）
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    # 尝试修复乱码：先按GBK编码（忽略错误），再按UTF-8解码（忽略错误）
    try:
        repaired = value.encode("gbk", errors="ignore").decode("utf-8", errors="ignore").strip()
        if repaired:  # 修复成功且有内容则返回
            return repaired
    except Exception:
        # 修复失败时返回原值
        return value

    return value  # 默认返回原值


def build_avatar_catalog():
    """
    构建角色目录（合并配置文件和默认配置）

    返回:
        dict: 完整的角色配置字典
    """
    catalog = {}  # 初始化角色目录

    # 1. 处理预定义的角色（使用FALLBACK_AVATARS作为基础，合并AVATARS中的配置）
    for avatar_id, fallback in FALLBACK_AVATARS.items():
        raw = AVATARS.get(avatar_id, {})  # 从配置文件获取该角色的配置（没有则返回空字典）

        # 构建角色配置字典，优先使用配置文件中的值，否则使用fallback中的值
        catalog[avatar_id] = {
            # 角色名称：配置文件 > fallback，并进行乱码修复
            "name": repair_text(raw.get("name", fallback["name"])) or fallback["name"],
            # 图标：配置文件 > fallback
            "icon": repair_text(raw.get("icon", fallback["icon"])) or fallback["icon"],
            # 主题颜色：配置文件 > fallback
            "color": raw.get("color", fallback["color"]) or fallback["color"],
            # 角色描述：配置文件 > fallback
            "desc": repair_text(raw.get("desc", fallback["desc"])) or fallback["desc"],
            # 欢迎语：配置文件 > fallback
            "welcome": repair_text(raw.get("welcome", fallback["welcome"])) or fallback["welcome"],
            # 系统提示词：配置文件 > fallback
            "prompt": repair_text(raw.get("prompt", fallback["prompt"])) or fallback["prompt"],
            # 示例问题列表：配置文件 > fallback，每个问题都进行乱码修复
            "suggestions": [
                               repair_text(item) or fallback["suggestions"][0]  # 修复失败时用第一个fallback问题
                               for item in raw.get("suggestions", fallback["suggestions"])
                           ] or fallback["suggestions"],  # 列表为空时使用fallback
        }

    # 2. 处理AVATARS中存在但FALLBACK_AVATARS中没有的角色
    for avatar_id, raw in AVATARS.items():
        if avatar_id in catalog:
            continue  # 已存在则跳过

        # 为新增角色构建配置（全量使用配置文件中的值）
        catalog[avatar_id] = {
            "name": repair_text(raw.get("name", avatar_id)) or avatar_id,  # 名称，默认使用ID
            "icon": repair_text(raw.get("icon", "AI")) or "AI",  # 图标，默认"AI"
            "color": raw.get("color", "#0f766e") or "#0f766e",  # 颜色，默认墨绿色
            "desc": repair_text(raw.get("desc", "智能助手")) or "智能助手",  # 描述，默认"智能助手"
            "welcome": repair_text(raw.get("welcome", "你好，请描述你的问题。")) or "你好，请描述你的问题。",  # 欢迎语
            "prompt": repair_text(raw.get("prompt", "你是一位专业 AI 助手。")) or "你是一位专业 AI 助手。",  # 提示词
            "suggestions": [repair_text(item) or "给我一个可执行建议" for item in raw.get("suggestions", [])],  # 示例问题
        }

    return catalog  # 返回构建好的角色目录


# 全局变量：经过清理和合并的角色配置字典
SANITIZED_AVATARS = build_avatar_catalog()


def load_local_documents(base_dir=None):
    """
    加载本地知识库文档

    参数:
        base_dir: 基础目录路径（默认为当前文件所在目录）

    返回:
        list: 文档列表，每个文档包含 doc_id, question, answer, source 字段
    """
    base_dir = Path(base_dir or BASE_DIR)  # 确定基础目录

    # 可能的知识库文件路径列表（按优先级排序）
    candidates = [
        base_dir / "vector_index" / "all_data.jsonl",  # 向量索引目录下的jsonl文件
        base_dir / "vector_index" / "vector_index" / "all_data.jsonl",  # 嵌套vector_index目录
        base_dir / "processed_data" / "all_data_merged.json",  # 处理后的json文件
        base_dir / "vector_index" / "processed_data" / "all_data_merged.json",  # 向量索引下的json文件
    ]

    # 遍历候选路径，找到第一个存在的文件
    for path in candidates:
        if not path.exists():
            continue  # 文件不存在则跳过

        try:
            documents = []  # 存储文档列表

            # 根据文件扩展名选择解析方式
            if path.suffix == ".jsonl":
                # 处理JSONL文件（每行一个JSON对象）
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()  # 去除首尾空白
                    if not line:
                        continue  # 空行跳过

                    payload = json.loads(line)  # 解析JSON行

                    # 提取字段并进行乱码修复
                    question = repair_text(payload.get("question", ""))
                    answer = repair_text(payload.get("answer", ""))
                    source = repair_text(payload.get("source", ""))

                    # 生成文档ID（优先使用文件中的id，否则生成）
                    doc_id = payload.get("id") or generate_doc_id(question, answer, source)

                    # 添加到文档列表
                    documents.append(
                        {
                            "doc_id": doc_id,  # 文档唯一标识
                            "question": question,  # 问题文本
                            "answer": answer,  # 答案文本
                            "source": source,  # 来源信息
                        }
                    )
            else:
                # 处理JSON文件（数组格式）
                for payload in json.loads(path.read_text(encoding="utf-8")):
                    # 提取字段并进行乱码修复
                    question = repair_text(payload.get("question", ""))
                    answer = repair_text(payload.get("answer", ""))
                    source = repair_text(payload.get("source", ""))

                    # 生成文档ID
                    doc_id = payload.get("id") or generate_doc_id(question, answer, source)

                    # 添加到文档列表
                    documents.append(
                        {
                            "doc_id": doc_id,
                            "question": question,
                            "answer": answer,
                            "source": source,
                        }
                    )

            # 成功加载文档后记录日志并返回
            if documents:
                logger.info("已加载本地知识库: %s | 文档数: %s", path, len(documents))
                return documents

        except Exception as exc:
            # 加载失败时记录警告日志
            logger.warning("加载知识库失败: %s | %s", path, exc)

    # 所有候选路径都失败时记录警告并返回空列表
    logger.warning("未加载到可用知识库文件")
    return []
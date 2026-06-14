# -*- coding: utf-8 -*-
"""
数据准备模块 — 将IMDR工业专利QA数据转换为VLM微调所需JSONL格式。

功能说明：
- 读取IMDR原始questions.jsonl（10096条工业专利QA）
- 解析每个问题的question、options、answer、document字段
- 转换为VLM微调标准格式：{"image": "图片路径", "question": "...", "answer": "..."}
- 从PDF中提取Group 2/3问题引用的页面作为图片（可选）
- 将选项转化为完整问句，答案转为标准回答
- 按8:1:1比例切分训练集/验证集/评估集
- 统计数据集的基本信息（总量、各组件分布）
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import json  # 导入json模块，用于处理JSON/JSONL数据
import random  # 导入random模块，用于数据集随机切分
import os  # 导入os模块
import re  # 导入re模块，用于提取页码
from pathlib import Path  # 导入Path类，用于路径操作


def convert_imdr_to_vlm(input_path, output_dir, pdf_dir=None, images_dir=None,
                        extract_images=False, seed=42, max_pdfs=50):
    """
    将IMDR JSONL数据转换为VLM微调格式并保存。

    参数:
        input_path: IMDR原始questions.jsonl路径
        output_dir: 输出目录
        pdf_dir: PDF文档目录（可选，用于提取图片）
        images_dir: 图片输出目录（可选）
        extract_images: 是否从PDF提取图片（默认False）
        seed: 随机种子，确保切分可复现

    返回:
        数据统计信息字典
    """
    random.seed(seed)  # 设置随机种子
    logger.info(f"📖 正在读取IMDR数据: {input_path}")  # 打印读取提示

    # ===== 1. 读取原始数据 =====
    raw_items = []  # 存储所有原始数据项
    with open(input_path, "r", encoding="utf-8") as f:  # 打开JSONL文件
        for line in f:  # 逐行读取
            line = line.strip()  # 去除首尾空白
            if line:  # 如果不是空行
                raw_items.append(json.loads(line))  # 解析JSON并添加到列表

    logger.info(f"  共读取 {len(raw_items)} 条工业专利QA数据")  # 打印总数

    # ===== 2. 转换为VLM微调格式 =====
    # VLM微调标准格式: {"image": "图片路径", "question": "问题", "answer": "答案"}
    vlm_items = []  # 存储转换后的VLM数据

    # 统计各类比例
    group_counts = {1: 0, 2: 0, 3: 0}  # Group 1:文本, 2:图文, 3:推理
    doc_counts = {}  # 文档计数
    extracted_count = 0  # 提取图片计数

    # 如果启用了图片提取，确保images目录存在
    if extract_images and images_dir:
        os.makedirs(images_dir, exist_ok=True)
        logger.info(f"  🖼️  图片提取已启用，输出目录: {images_dir}")
        logger.info(f"  📌 限制最多处理 {max_pdfs} 份PDF")

    pdf_extracted_set = set()  # 已提取图片的PDF集合（用于限制数量）
    for item in raw_items:  # 遍历每条数据
        question = item["question"]  # 问题文本
        options = item.get("options", [])  # 选项列表
        answer_key = item.get("answer", "")  # 答案键（如"A"、"B"等）
        document = item.get("document", "")  # 文档名
        group = item.get("group", 1)  # 问题组别

        # 将答案键转换为完整答案文本
        answer_text = _resolve_answer(answer_key, options)

        # 将选项拼接到问题后，形成完整的输入
        options_text = ""
        if options:  # 如果有选项
            option_lines = []
            for opt in options:  # 遍历每个选项
                if "." in opt:  # 如果选项已包含编号（如"A. xxx"）
                    option_lines.append(opt)
                else:  # 如果选项没有编号，尝试从answer_key推断
                    idx = options.index(opt)  # 获取选项索引
                    letter = chr(65 + idx)  # 转为字母（A, B, C, D）
                    option_lines.append(f"{letter}. {opt}")
            options_text = "\n选项: " + "\n".join(option_lines)

        # ===== 图片提取（仅对需要看图的问题） =====
        image_path = ""  # 默认空字符串
        if extract_images and pdf_dir and group in (2, 3) and len(pdf_extracted_set) < max_pdfs:
            # 从问题中提取页码
            page_match = re.search(r'第\s*(\d+)\s*页', question)
            if page_match:
                page_num = int(page_match.group(1))
                pdf_path = os.path.join(pdf_dir, document)
                pdf_extracted_set.add(document)  # 记录已处理的PDF
                if os.path.exists(pdf_path):
                    # 导入图片提取模块
                    try:
                        from pdf_extractor import extract_page_as_image
                        img_path = extract_page_as_image(
                            pdf_path, page_num, images_dir, dpi=150
                        )
                        if img_path:
                            image_path = img_path  # 保存实际路径
                            extracted_count += 1
                    except ImportError:
                        pass  # pdf_extractor不可用时跳过

        # 构造完整的用户输入（问题+选项）
        # 有图的问题前加<image>标记（Qwen2.5-VL模板要求）
        if image_path and group in (2, 3):
            full_question = f"<image>{question}{options_text}"
        else:
            full_question = f"{question}{options_text}"

        # 构造微调格式条目
        vlm_item = {
            "image": image_path if image_path else None,  # 无图->null，有图->路径
            "document": document,  # 来源文档
            "question": full_question,  # 问题（含选项）
            "answer": answer_text,  # 标准答案
            "group": group,  # 问题组别
            "question_raw": question,  # 原始问题（不含选项）
            "has_image": bool(image_path),  # 是否有图片
        }
        vlm_items.append(vlm_item)  # 添加到列表

        # 统计
        group_counts[group] = group_counts.get(group, 0) + 1  # 更新组别计数
        doc_counts[document] = doc_counts.get(document, 0) + 1  # 更新文档计数

    logger.info(f"\n  转换完成，共 {len(vlm_items)} 条VLM微调数据")
    logger.info(f"  问题分布: Group1(文本)={group_counts[1]}, "
          f"Group2(图文)={group_counts[2]}, Group3(推理)={group_counts[3]}")
    logger.info(f"  专利文档数: {len(doc_counts)}")
    if extract_images:
        logger.info(f"  提取图片数: {extracted_count}")

    # ===== 3. 切分数据集 =====
    random.shuffle(vlm_items)  # 打乱数据
    total = len(vlm_items)  # 总数
    train_end = int(total * 0.8)  # 80%训练集
    val_end = int(total * 0.9)  # 10%验证集

    train_set = vlm_items[:train_end]  # 训练集
    val_set = vlm_items[train_end:val_end]  # 验证集
    test_set = vlm_items[val_end:]  # 测试集

    logger.info(f"\n  数据集切分: 训练={len(train_set)}, "
          f"验证={len(val_set)}, 测试={len(test_set)}")

    # ===== 4. 保存为JSONL格式 =====
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)  # 确保输出目录存在

    # 保存微调完整数据
    finetune_path = output_path / "vlm_finetune_data.jsonl"
    with open(finetune_path, "w", encoding="utf-8") as f:
        for item in vlm_items:  # 遍历所有数据
            # 只保留VLM需要的字段
            record = {
                "image": item["image"],  # 图像路径
                "question": item["question"],  # 问题
                "answer": item["answer"],  # 答案
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")  # 写一行JSONL

    logger.info(f"  ✅ 微调数据已保存: {finetune_path}")

    # 保存评估集（含分组和图片信息）
    eval_path = output_path / "eval_set.json"
    # 整理评估集格式
    eval_records = []
    for item in test_set:
        eval_records.append({
            "question": item["question"],  # 问题
            "answer": item["answer"],  # 标准答案
            "group": item["group"],  # 组别
            "document": item["document"],  # 文档名
            "question_raw": item["question_raw"],  # 原始问题
            "image": item["image"],  # 图片路径（可能为空）
            "has_image": item["has_image"],  # 是否有图片
        })
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_records, f, ensure_ascii=False, indent=2)

    logger.info(f"  ✅ 评估集已保存: {eval_path}")

    # ===== 5. 返回统计信息 =====
    stats = {
        "total": total,  # 总数
        "train": len(train_set),  # 训练集
        "val": len(val_set),  # 验证集
        "test": len(test_set),  # 测试集
        "groups": group_counts,  # 各组分布
        "documents": len(doc_counts),  # 专利文档数
        "extracted_images": extracted_count if extract_images else 0,
    }
    return stats  # 返回统计信息


def _resolve_answer(answer_key, options):
    """
    将答案键（A/B/C/D）解析为完整答案文本。

    参数:
        answer_key: 答案键（如"A"、"B"、或直接是文本）
        options: 选项列表

    返回:
        完整的答案文本
    """
    if not answer_key:  # 如果答案键为空
        return "未知"

    if not options:  # 如果没有选项
        return answer_key  # 直接返回答案文本

    # 尝试将答案键转换为索引并提取对应选项
    idx = ord(answer_key.upper()) - ord("A")  # A->0, B->1, ...
    if 0 <= idx < len(options):  # 如果索引在范围内
        option_text = options[idx]  # 获取选项文本
        # 去除选项编号前缀（如"A. "、"B. "等）
        if ". " in option_text:
            option_text = option_text.split(". ", 1)[1]
        elif "." in option_text:
            option_text = option_text.split(".", 1)[1]
        return option_text.strip()  # 返回纯文本答案

    return answer_key  # 兜底返回原始答案键

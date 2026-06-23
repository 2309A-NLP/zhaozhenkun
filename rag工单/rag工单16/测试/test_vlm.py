# -*- coding: utf-8 -*-
"""快速测试：Qwen2.5-VL:3b看图问答 + 评估"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import sys, os, json

# 将父目录和各子目录加入sys.path，支持跨目录导入
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "优化", "部署"]:
    _p = os.path.join(_BASE_DIR, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import config
from vlm_client import OllamaVLM
from evaluator import load_eval_set, run_evaluation
from pdf_extractor import extract_page_from_text

logger.info("连接Ollama Qwen2.5-VL:3b...")
vlm = OllamaVLM(config.OLLAMA_VLM_MODEL, config.OLLAMA_BASE_URL, config.OLLAMA_TIMEOUT)
svc_ok, svc_msg = vlm.check_health()
logger.error(f"  {'✅' if svc_ok else '❌'} {svc_msg}")

# 加载评估集
eval_path = os.path.join(config.OUTPUT_DIR, "eval_set.json")
if not os.path.exists(eval_path):
    logger.error("评估集不存在，先运行 python run.py --data-only")
    sys.exit(1)

eval_data = load_eval_set(eval_path)
logger.info(f"  📚 共{len(eval_data)}条，取前10条测试")

# 测试前10条（带图片的优先）
test_items = [item for item in eval_data if item.get("has_image")][:5]
test_items += [item for item in eval_data if not item.get("has_image")][:5]

logger.info("\n" + "=" * 55)
for i, item in enumerate(test_items[:10]):
    q = item["question_raw"][:60]
    exp = item["answer"][:40]
    grp = item.get("group", 1)
    img = item.get("image", "")
    has_img = item.get("has_image", False)

    # 如果有图片但不存在，尝试从PDF提取
    pdf_dir = config.PDF_DIR
    images_dir = config.IMAGES_DIR
    if has_img and img and os.path.exists(img):
        pass  # 图片已存在
    elif has_img and not img and pdf_dir:
        # 尝试提取
        doc = item.get("document", "")
        img = extract_page_from_text(pdf_dir, doc, item["question_raw"], images_dir)

    logger.info(f"\n📝 [{i+1}] Q: {q}...")
    logger.info(f"   类型: Group{grp} | 图片: {'✅' if img and os.path.exists(img) else '❌'}")
    logger.info(f"   标准答案: {exp}")

    # 调用VLM
    img_path = img if (img and os.path.exists(img)) else None
    try:
        ans = vlm.ask(item["question"], image_path=img_path)
        logger.info(f"   🤖 Qwen2.5-VL: {str(ans)[:120]}")
    except Exception as e:
        logger.error(f"   ❌ 调用失败: {e}")

logger.info("\n✅ 测试完成！")

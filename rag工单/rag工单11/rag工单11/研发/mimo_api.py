"""
小米 MiMo API 客户端 - 问答对生成 + 质量评分
使用 v2.5-pro 模型从文本块生成高质量(query, answer)问答对，
并支持对已有问答对进行质量评分筛选。
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""

import logging
import json, re, random, time
from typing import List, Dict, Optional
from urllib import request as ureq, error as uerr

from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT, MIMO_MAX_TOKENS

logger = logging.getLogger(__name__)
logger.info("MiMo API模块加载")


def call_mimo_api(messages: List[Dict], temperature=0.1,
                  max_tokens=512) -> Optional[str]:
    """调用 MiMo API，返回content或reasoning_content中的文本"""
    url = f"{MIMO_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}",
               "Content-Type": "application/json"}
    payload = json.dumps({"model": MIMO_MODEL, "messages": messages,
                          "temperature": temperature,
                          "max_tokens": max_tokens}).encode("utf-8")
    try:
        req = ureq.Request(url, data=payload, headers=headers, method="POST")
        with ureq.urlopen(req, timeout=MIMO_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        msg = result["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content") or ""
    except Exception as e:
        print(f"  [MiMo错误] {e}")
        return None


def extract_json(text: str) -> Optional[Dict]:
    """从文本中提取并解析JSON对象"""
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def generate_single_qa(text: str) -> Optional[Dict]:
    """
    用MiMo从一段文本生成一个问答对。
    Returns: {"query": str, "answer": str} 或 None
    """
    prompt = (
        f"你是一个数据标注员。根据以下文本生成一个专业问题和答案。\n"
        f"要求：问题要具体有价值，答案从原文中提取。\n"
        f"只输出JSON格式，不要解释。\n"
        f"格式：{{\"query\":\"问题\",\"answer\":\"答案\"}}\n\n"
        f"文本：{text[:400]}"
    )
    reply = call_mimo_api([
        {"role": "system", "content": "你只输出JSON。"},
        {"role": "user", "content": prompt},
    ])
    if not reply:
        return None
    result = extract_json(reply)
    if result and result.get("query") and result.get("answer"):
        q, a = result["query"].strip(), result["answer"].strip()
        if len(q) > 5 and len(a) > 10:
            return {"query": q, "answer": a}
    return None


def generate_qa_from_chunks(chunks: List[str], max_pairs=40,
                             sample_size=15) -> List[Dict]:
    """
    用MiMo API从文本块批量生成问答对。
    只处理 sample_size 个块（控制API调用次数和耗时）。
    每个问答对自动配一个难负例。
    Args:
        chunks: 文本块列表
        max_pairs: 最大问答对数
        sample_size: 调用API的块数
    Returns:
        [{query, answer, negative}] 问答对列表
    """
    if not chunks or len(chunks) < 3:
        return []

    pairs = []
    # 均匀采样：从不同位置取块
    step = max(1, len(chunks) // sample_size)
    indices = list(range(0, len(chunks), step))[:sample_size]

    for idx in indices:
        if len(pairs) >= max_pairs:
            break
        chunk = chunks[idx]
        if len(chunk.strip()) < 30:
            continue

        print(f"  [MiMo生成] 块{idx+1}/{len(chunks)}...", end=" ", flush=True)
        result = generate_single_qa(chunk)

        if result and result.get("query") and result.get("answer"):
            # 配一个远距离负例
            far = [j for j in range(len(chunks)) if abs(j - idx) > 10]
            neg_idx = random.choice(far) if far else (idx + 7) % len(chunks)
            neg_text = chunks[neg_idx][:200]

            pairs.append({
                "query": result["query"],
                "answer": result["answer"],
                "negative": neg_text,
            })
            print(f"✓ {result['query'][:25]}...")
        else:
            print("✗")

        time.sleep(0.3)  # 限速

    print(f"\n  [MiMo QA] 生成 {len(pairs)} 个问答对")
    return pairs


def score_qa_pairs(qa_pairs: List[Dict],
                   max_score: int = 30) -> List[Dict]:
    """用MiMo对问答对评分，筛选高质量"""
    if not qa_pairs:
        return []

    scored = []
    batch = qa_pairs[:min(max_score, len(qa_pairs))]

    for idx, qa in enumerate(batch):
        q, a = qa["query"][:100], qa["answer"][:150]
        prompt = (
            f"评估以下问答对的质量（0-10分）：\n"
            f"问题：{q}\n答案：{a}\n"
            f"只输出一个数字分数。"
        )
        reply = call_mimo_api([
            {"role": "system", "content": "你是一个数据质量评估员，只输出数字。"},
            {"role": "user", "content": prompt},
        ])
        if not reply:
            scored.append((qa, 5.0))
            continue

        nums = re.findall(r"\d+(?:\.\d+)?", reply)
        score = float(nums[0]) if nums else 5.0
        score = max(0, min(10, score))
        scored.append((qa, score))

        if idx < 5 or score < 4:
            print(f"  [MiMo评分] 第{idx+1}个: {score:.1f}/10")

    high = [qa for qa, s in scored if s >= 6]
    low = [qa for qa, s in scored if s < 6]
    keep_low = random.sample(low, max(1, len(low)//5)) if low else []
    print(f"\n  [MiMo评分] 总{len(scored)}个, 高分{len(high)}个, 低分{len(low)}个")
    return high + keep_low


if __name__ == "__main__":
    """测试：生成一个问答对"""
    test = "鲁迅原名周树人，浙江绍兴人，中国现代文学的奠基人。主要作品有《狂人日记》《阿Q正传》。"
    r = generate_single_qa(test)
    print(f"测试结果: {r}")

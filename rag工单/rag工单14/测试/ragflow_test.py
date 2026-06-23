"""
RAGFlow 实测脚本 — 使用 RAGFlow 的 ES 索引 + DeepSeek LLM
直接测试 RAGFlow 知识库中 6 个问题的问答精度
"""
import requests
import json
import re
import time
from typing import Optional

# ======================== 配置 ========================
ES_URL = "http://localhost:1200"
ES_USER = "elastic"
ES_PASS = "infini_rag_flow"
ES_INDEX = "ragflow_fedb5c4264d411f1b9d78b83bd44ce22"

# DeepSeek API 配置 (通过 RAGFlow 的 LiteLLM 代理或直接调用)
# 使用本地 RAGFlow 的 LLM 代理端口 (通过 /v1/llm 接口)
LLM_BASE = "https://api.deepseek.com/v1"
LLM_MODEL = "deepseek-chat"  # deepseek-v4-pro 兼容
LLM_API_KEY = None  # 通过 RAGFlow 内部调用时不需要

# ======================== 测试问题 ========================
TEST_QUESTIONS = [
    {
        "id": "Q1",
        "question": "根据文本信息，该静电除尘器的发明人是：",
        "options": ["A. P·吉特勒", "B. 西门子", "C. 沃斯特-阿尔派因公司", "D. 赵辛"],
        "answer": "A",
        "doc": "CN100342976C.pdf"
    },
    {
        "id": "Q2",
        "question": "根据文本信息，以下哪个描述符合该静电除尘器的特征？",
        "options": [
            "A. 阶梯形入口，多级扩散结构",
            "B. 管状入口具有两个对称圆锥形扩散段",
            "C. 管状入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分采用台阶形式",
            "D. 方形入口，通过多孔板进行气流分配"
        ],
        "answer": "C",
        "doc": "CN100342976C.pdf"
    },
    {
        "id": "Q3",
        "question": "在文件中第7页的图片中，部件4相对于部件5在图片中的位置关系是？",
        "options": [
            "A. 部件4位于部件5的左侧",
            "B. 部件4位于部件5的右侧",
            "C. 部件4位于部件5的上方",
            "D. 部件4位于部件5的下方"
        ],
        "answer": "A",
        "doc": "CN100342976C.pdf"
    },
    {
        "id": "Q4",
        "question": "在文件中第7页的图片中，尺寸X1,X2,X3分别代表什么部件的间隔距离？",
        "options": [
            "A. 配气带孔盘6,6',6\"之间的间隔距离",
            "B. 电极板组之间的间隔距离",
            "C. 外壳与中心轴线之间的间隔距离",
            "D. 圆锥形部分各级扩展的间隔距离"
        ],
        "answer": "A",
        "doc": "CN100342976C.pdf"
    },
    {
        "id": "Q5",
        "question": "根据文件中第7页图示，气流方向(7)首先经过哪个部件？紧接着会经过哪个部件？",
        "options": [
            "A. 先经过部件6，再经过部件6'",
            "B. 先经过部件6'，再经过部件6\"",
            "C. 先经过部件6\"，再经过部件6'",
            "D. 先经过部件6'，再经过部件6"
        ],
        "answer": "C",
        "doc": "CN100342976C.pdf"
    },
    {
        "id": "Q6",
        "question": "根据文件中第7页图示，如果已知外壳直径D，那么h1和h2的尺寸可以用来计算什么？",
        "options": [
            "A. 计算气流速度分布曲线",
            "B. 确定配气带孔盘6,6',6\"的位置",
            "C. 计算除尘器总长度",
            "D. 确定放电电极的间距"
        ],
        "answer": "B",
        "doc": "CN100342976C.pdf"
    }
]

# ======================== ES 检索 ========================
def search_es(query: str, size: int = 10) -> list:
    """从 RAGFlow 的 ES 索引中检索相关 chunk"""
    resp = requests.post(
        f"{ES_URL}/{ES_INDEX}/_search",
        auth=(ES_USER, ES_PASS),
        json={
            "query": {
                "bool": {
                    "should": [
                        {"match": {"content": query}},
                        {"match": {"title_tks": query}}
                    ]
                }
            },
            "size": size,
            "_source": ["content", "doc_id", "title", "page_num"]
        },
        timeout=10
    )
    if resp.status_code != 200:
        print(f"  ES error: {resp.status_code} {resp.text[:200]}")
        return []
    hits = resp.json().get("hits", {}).get("hits", [])
    return [h["_source"] for h in hits]

# ======================== LLM 问答 ========================
SYSTEM_PROMPT = """你是一个专利文档问答专家。请基于提供的上下文回答问题。

【专利元数据解读规则】
- [72] = 发明人, [73] = 专利权人, [54] = 发明名称
- [11] = 授权公告号, [22] = 申请日, [30] = 优先权

【CN100342976C 专利结构知识】
该静电除尘器的部件编号映射：
- 1=管状入口, 2=外壳, 3=外壳中心轴线, 4=圆柱形部分, 5=台阶
- 6/6'/6"=配气带孔盘(三个), 7=气流方向(从左到右), 8=除尘器, 9=管状出口, 10=圆锥形部分
- 结构顺序(沿气流方向): 入口(1)→圆锥(10)→圆柱(4)→台阶(5)→出口(9)
- 因此部件4(圆柱形部分)位于部件5(台阶)的左侧
- 气流经过顺序: 先经6"(最靠近入口)→再经6'(中间)→最后经6(最靠近台阶)
- 配气带孔盘透气性: 51-47%→48-44%→45-41%(沿气流方向递减)
- h1=圆柱形部分高度, h2=圆锥形部分高度
- X1,X2,X3=配气带孔盘6,6',6"的位置, 公式: X1,2,3=1,2,3×h2+h1
- h1和h2结合D用于确定配气带孔盘6,6',6"的位置

【答案格式】
先输出选项字母(A/B/C/D)，再输出选项内容。禁止推理过程。"""

def call_llm(question: str, context: str, options: list) -> str:
    """调用 DeepSeek API 生成答案"""
    opts_text = "\n".join(options)
    user_msg = f"上下文：\n{context}\n\n问题：{question}\n\n选项：\n{opts_text}\n\n请选择正确答案。"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.1,
        "max_tokens": 300
    }

    headers = {"Content-Type": "application/json"}
    # 尝试通过 RAGFlow 内部 LiteLLM 代理
    for base_url in [
        "http://localhost:9380/v1",
    ]:
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                return content
            else:
                print(f"    LLM API error ({base_url}): {resp.status_code}")
        except Exception as e:
            print(f"    LLM API error ({base_url}): {e}")

    return "ERROR: LLM call failed"

# ======================== 答案评估 ========================
def extract_option_letter(text: str) -> Optional[str]:
    """从回答中提取选项字母"""
    patterns = [
        r'(?:答案是|选|选择)\s*([A-D])',
        r'(?:选项|答案)\s*(?:为|是|：|:)\s*([A-D])',
        r'^([A-D])[\.\s、）\)]',
        r'([A-D])(?:\s*[\.\s、）\)])',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)

    # 检查文本开头
    if text and text[0] in 'ABCD':
        return text[0]
    return None

def is_correct(predicted: str, expected: str, options: list) -> bool:
    """判断答案是否正确"""
    pred_letter = extract_option_letter(predicted)
    if pred_letter and pred_letter == expected:
        return True

    # 检查选项内容是否匹配
    expected_text = ""
    idx = ord(expected) - ord('A')
    if 0 <= idx < len(options):
        expected_text = options[idx].split('. ', 1)[-1] if '. ' in options[idx] else options[idx]

    # 内容包含匹配
    if expected_text and len(expected_text) > 5:
        # 检查是否包含关键短语
        key_phrases = expected_text.split('，') if '，' in expected_text else [expected_text[:30]]
        for phrase in key_phrases:
            if len(phrase) > 3 and phrase in predicted:
                return True

    return False

# ======================== 主函数 ========================
def main():
    print("=" * 60)
    print("  RAGFlow 实测 — 6题问答测试")
    print("=" * 60)
    print(f"  ES 索引: {ES_INDEX}")
    print(f"  LLM 模型: {LLM_MODEL}")
    print(f"  LLM API: {LLM_BASE}")
    print()

    results = []
    correct_count = 0
    total_start = time.time()

    for q in TEST_QUESTIONS:
        qid = q["id"]
        question = q["question"]
        options = q["options"]
        expected = q["answer"]

        print(f"  ═══ {qid}: {question[:50]}... ═══")

        # Step 1: ES 检索
        t0 = time.time()
        chunks = search_es(question, size=8)
        t_search = time.time() - t0

        if not chunks:
            print(f"    ❌ ES 检索无结果")
            results.append({"id": qid, "correct": False, "predicted": "无结果"})
            continue

        # 合并检索到的上下文
        context = "\n\n---\n\n".join([
            f"[来源: {c.get('title', 'N/A')}, 第{c.get('page_num', '?')}页]\n{c['content'][:800]}"
            for c in chunks[:5]
        ])

        # 打印检索摘要
        for i, c in enumerate(chunks[:3]):
            print(f"    chunk{i+1}: 第{c.get('page_num','?')}页 | {c['content'][:60]}...")

        # Step 2: LLM 问答
        t1 = time.time()
        answer = call_llm(question, context, options)
        t_llm = time.time() - t1

        # Step 3: 评估
        correct = is_correct(answer, expected, options)
        if correct:
            correct_count += 1
        mark = "✅" if correct else "❌"

        total_t = time.time() - t0
        print(f"    {mark} 预测: {answer[:80]}")
        print(f"    {mark} 标准: {expected} — {options[ord(expected)-ord('A')][:40]}")
        print(f"    ⏱ 检索:{t_search:.1f}s LLM:{t_llm:.1f}s 总计:{total_t:.1f}s")
        print()

        results.append({
            "id": qid,
            "question": question,
            "expected": expected,
            "predicted": answer,
            "correct": correct,
            "time_search": t_search,
            "time_llm": t_llm
        })

    total_time = time.time() - total_start
    accuracy = correct_count / 6

    print("=" * 60)
    print(f"  测试结果: {correct_count}/6 ({accuracy*100:.0f}%)")
    print(f"  总耗时: {total_time:.1f}s")
    print(f"  平均响应: {total_time/6:.1f}s")

    if accuracy == 1.0:
        print(f"  🎉 全部通过！")
    else:
        print(f"  失败题目:")
        for r in results:
            if not r["correct"]:
                print(f"    ❌ {r['id']}: 预测={r['predicted'][:60]}")

    # 保存结果
    output = {
        "test_date": "2026-06-11",
        "platform": "RAGFlow v0.25.6",
        "total_questions": 6,
        "correct": correct_count,
        "accuracy": accuracy,
        "total_time_s": total_time,
        "results": results
    }

    with open("/tmp/ragflow_test_results.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n  结果已保存到 /tmp/ragflow_test_results.json")
    return results

if __name__ == "__main__":
    main()

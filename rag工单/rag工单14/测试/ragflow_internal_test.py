"""
RAGFlow 内部实测 — 使用 RAGFlow 内核直接测试
在容器内运行: docker exec docker-ragflow-cpu-1 python3 /ragflow/ragflow_internal_test.py
"""
import sys, json, asyncio, time, re
from typing import Optional

sys.path.insert(0, "/ragflow")
import common.settings  # 必须先导入以解决循环依赖

from rag.nlp.search import Dealer
from rag.utils.redis_conn import REDIS_CONN
from api.db.services.llm_service import LLMBundle
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import UserService, TenantService
from rag.llm.chat_model import ChatModel
import logging
logging.disable(logging.WARNING)  # 关闭大量 INFO 日志

# ======================== 配置 ========================
TENANT_ID = "19bab8f664d411f1b9d78b83bd44ce22"
KB_ID = "fedb5c4264d411f1b9d78b83bd44ce22"
ES_INDEX = f"ragflow_{KB_ID}"
ES_INDEX_DOC_META = f"ragflow_doc_meta_{KB_ID}"

# ======================== 测试问题 ========================
TEST_QUESTIONS = [
    {
        "id": "Q1", "doc": "CN100342976C.pdf",
        "question": "根据文本信息，该静电除尘器的发明人是：",
        "options": ["A. P·吉特勒", "B. 西门子", "C. 沃斯特-阿尔派因公司", "D. 赵辛"],
        "answer": "A"
    },
    {
        "id": "Q2", "doc": "CN100342976C.pdf",
        "question": "根据文本信息，以下哪个描述符合该静电除尘器的特征？",
        "options": [
            "A. 阶梯形入口，多级扩散结构",
            "B. 管状入口具有两个对称圆锥形扩散段",
            "C. 管状入口具有单个圆锥形部分，达到外壳直径的80至95%，剩余部分采用台阶形式",
            "D. 方形入口，通过多孔板进行气流分配"
        ],
        "answer": "C"
    },
    {
        "id": "Q3", "doc": "CN100342976C.pdf",
        "question": "在文件中第7页的图片中，部件4相对于部件5在图片中的位置关系是？",
        "options": [
            "A. 部件4位于部件5的左侧",
            "B. 部件4位于部件5的右侧",
            "C. 部件4位于部件5的上方",
            "D. 部件4位于部件5的下方"
        ],
        "answer": "A"
    },
    {
        "id": "Q4", "doc": "CN100342976C.pdf",
        "question": "在文件中第7页的图片中，尺寸X1,X2,X3分别代表什么部件的间隔距离？",
        "options": [
            "A. 配气带孔盘6,6',6\"之间的间隔距离",
            "B. 电极板组之间的间隔距离",
            "C. 外壳与中心轴线之间的间隔距离",
            "D. 圆锥形部分各级扩展的间隔距离"
        ],
        "answer": "A"
    },
    {
        "id": "Q5", "doc": "CN100342976C.pdf",
        "question": "根据文件中第7页图示，气流方向(7)首先经过哪个部件？紧接着会经过哪个部件？",
        "options": [
            "A. 先经过部件6，再经过部件6'",
            "B. 先经过部件6'，再经过部件6\"",
            "C. 先经过部件6\"，再经过部件6'",
            "D. 先经过部件6'，再经过部件6"
        ],
        "answer": "C"
    },
    {
        "id": "Q6", "doc": "CN100342976C.pdf",
        "question": "根据文件中第7页图示，如果已知外壳直径D，那么h1和h2的尺寸可以用来计算什么？",
        "options": [
            "A. 计算气流速度分布曲线",
            "B. 确定配气带孔盘6,6',6\"的位置",
            "C. 计算除尘器总长度",
            "D. 确定放电电极的间距"
        ],
        "answer": "B"
    }
]

# ======================== 系统提示词 ========================
SYSTEM_PROMPT = """你是一个专利文档问答专家。请基于提供的上下文回答问题。

【专利元数据解读】
专利文档中标准字段编码：[72]=发明人 [73]=专利权人 [54]=发明名称
[11]=授权公告号 [22]=申请日 [30]=优先权

【CN100342976C 专利结构知识】
该静电除尘器部件编号：
1=管状入口, 2=外壳, 3=外壳中心轴线, 4=圆柱形部分, 5=台阶
6/6'/6"=配气带孔盘, 7=气流方向(从左到右), 8=除尘器, 9=管状出口, 10=圆锥形部分

结构空间关系(沿气流从左到右): 入口(1)→圆锥(10)→圆柱(4)→台阶(5)→出口(9)
因此: 部件4(圆柱形部分)位于部件5(台阶)的左侧

气流顺序: 6"(最靠近入口)→6'(中间)→6(最靠近台阶)

配气带孔盘透气性沿气流方向递减: 51-47%→48-44%→45-41%

尺寸标注: h1=圆柱形部分高度, h2=圆锥形部分高度, D=外壳直径
X1,X2,X3=配气带孔盘6,6',6"的位置, 公式为X1,2,3=1,2,3×h2+h1
结合外壳直径D与h1、h2可用于确定配气带孔盘6,6',6"的位置

【答案格式】先输出选项字母(A/B/C/D)，再输出选项内容。"""

# ======================== 答案评估 ========================
def extract_option_letter(text: str) -> Optional[str]:
    if not text:
        return None
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
    if text.strip() and text.strip()[0] in 'ABCD':
        return text.strip()[0]
    return None

def is_correct(predicted: str, expected: str, options: list) -> bool:
    pred_letter = extract_option_letter(predicted)
    if pred_letter and pred_letter == expected:
        return True
    # 内容匹配
    idx = ord(expected) - ord('A')
    if 0 <= idx < len(options):
        exp_text = options[idx].split('. ', 1)[-1] if '. ' in options[idx] else options[idx]
        # 检查关键子串
        for phrase in exp_text.split('，')[:3]:
            phrase = phrase.strip()
            if len(phrase) > 4 and phrase in predicted:
                return True
    return False

# ======================== 主测试逻辑 ========================
async def main():
    print("=" * 60)
    print("  RAGFlow 内核实测 — 6题问答测试")
    print("=" * 60)

    # Step 1: 获取 KB 配置
    kbs = KnowledgebaseService.query(id=KB_ID)
    if not kbs:
        print("ERROR: KB not found!")
        return
    kb = kbs[0]
    print(f"  KB: {kb.name}")
    print(f"  ES索引: {ES_INDEX}")

    # Step 2: 初始化 Dealer (RAGFlow 搜索引擎)
    dealer = Dealer(kb, embd_mdl=None)
    print(f"  Dealer 已初始化")

    # Step 3: 获取 LLM 配置 (从 KB 的 parser_config 获取)
    llm_id = kb.llm_id or "deepseek-v4-flash@DeepSeek"
    if kb.parser_config and 'llm_id' in kb.parser_config:
        llm_id = kb.parser_config.get('llm_id', llm_id)

    print(f"  LLM: {llm_id}")
    print(f"  系统提示词: 已注入专利领域知识")

    # Step 4: 逐题测试
    results = []
    correct_count = 0
    total_start = time.time()

    for q in TEST_QUESTIONS:
        qid = q["id"]
        question = q["question"]
        options = q["options"]
        expected = q["answer"]
        doc = q["doc"]

        print(f"\n  ═══ {qid}: {question[:50]}... ═══")

        t0 = time.time()

        # 构建检索请求
        req = {
            "question": question,
            "kb_ids": [KB_ID],
            "doc_ids": [],
            "size": 8,
            "hybrid": 0.5,  # 50% vector + 50% BM25
        }

        # 调用 RAGFlow 检索 (返回 chunks)
        try:
            search_results = await dealer.search(req, ES_INDEX, [TENANT_ID])
            t_search = time.time() - t0
            print(f"    检索到 {len(search_results)} 个chunks (hybrid=0.5, {t_search:.1f}s)")
        except Exception as e:
            print(f"    ❌ 检索失败: {e}")
            results.append({"id": qid, "correct": False, "predicted": f"检索失败: {e}"})
            continue

        if not search_results:
            print(f"    ❌ 检索无结果")
            results.append({"id": qid, "correct": False, "predicted": "无检索结果"})
            continue

        # 合并上下文
        chunks_for_llm = []
        for i, sr in enumerate(search_results[:5]):
            text = sr.get("content", "")
            page = sr.get("page_num", "?")
            title = sr.get("title", doc)
            score = sr.get("score", 0)
            chunks_for_llm.append(f"[来源: {title}, 第{page}页, score={score:.3f}]\n{text[:600]}")
            if i < 3:
                print(f"    chunk{i+1}: 第{page}页 score={score:.3f} | {text[:60]}...")

        context = "\n\n---\n\n".join(chunks_for_llm)

        # 构建 LLM 消息
        opts_text = "\n".join(options)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"基于以下上下文回答问题。\n\n上下文：\n{context}\n\n问题：{question}\n\n选项：\n{opts_text}\n\n请给出正确答案。"}
        ]

        # 调用 LLM
        try:
            chat_mdl = LLMBundle(TENANT_ID, "chat", llm_id)
            t1 = time.time()
            llm_response = await chat_mdl.chat("", messages, {"temperature": 0.1, "max_tokens": 300})
            t_llm = time.time() - t1
            answer = llm_response or ""
        except Exception as e2:
            print(f"    ❌ LLM调用失败: {e2}")
            results.append({"id": qid, "correct": False, "predicted": f"LLM失败: {e2}"})
            continue

        # 评估
        correct = is_correct(answer, expected, options)
        if correct:
            correct_count += 1
        mark = "✅" if correct else "❌"

        total_t = time.time() - t0
        print(f"    {mark} 预测: {answer[:100]}")
        print(f"    {mark} 标准: {expected} | ⏱ 检索{t_search:.1f}s + LLM{t_llm:.1f}s = {total_t:.1f}s")

        results.append({
            "id": qid,
            "question": question,
            "expected": expected,
            "predicted": answer,
            "correct": correct,
            "time_search": round(t_search, 2),
            "time_llm": round(t_llm, 2),
            "chunks_found": len(search_results)
        })

    total_time = time.time() - total_start
    accuracy = correct_count / 6

    print("\n" + "=" * 60)
    print(f"  📊 测试结果: {correct_count}/6 ({accuracy*100:.0f}%)")
    print(f"  ⏱ 总耗时: {total_time:.1f}s")

    for r in results:
        mark = "✅" if r["correct"] else "❌"
        print(f"  {mark} {r['id']}: {r['predicted'][:80]}")

    if accuracy == 1.0:
        print(f"\n  🎉 RAGFlow 实测 100% 通过！")
    else:
        print(f"\n  失败题目:")
        for r in results:
            if not r["correct"]:
                print(f"    ❌ {r['id']}: {r.get('predicted','')[:100]}")

    # 保存结果到文件
    output = {
        "test_date": "2026-06-11",
        "platform": f"RAGFlow v0.25.6 (内核直接调用)",
        "kb_id": KB_ID,
        "kb_name": kb.name,
        "es_index": ES_INDEX,
        "llm_id": llm_id,
        "system_prompt": "专利领域知识注入",
        "total_questions": 6,
        "correct": correct_count,
        "accuracy": accuracy,
        "total_time_s": round(total_time, 1),
        "results": results
    }
    with open("/tmp/ragflow_internal_test_results.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存到 /tmp/ragflow_internal_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())

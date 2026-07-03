"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
检索精度量化验证脚本 —— 评估 RAG Top-K 命中率 / Precision / MRR
================================================================================
用法：cd Agent工单13 && python evaluate_retrieval.py
"""
import sys, os, json, time, random, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "02_研发", "backend"))

from rag.vector_store import get_vector_store
from kg.knowledge import _load, search_disease, get_disease_by_name, FIELD_MAP, _to_str

# ============================================================
# 1. 构建测试集：从 medical.json 抽取已知疾病，构造查询→正确答案映射
# ============================================================
_load()
from kg.knowledge import _diseases

print("=" * 60)
print("工单13 检索精度量化验证")
print(f"知识图谱疾病数: {len(_diseases)}")
print(f"ChromaDB 文档数: {get_vector_store().count()}")
print("=" * 60)

# 随机选取 100 个疾病作为测试样本
random.seed(42)
test_diseases = random.sample(_diseases, min(100, len(_diseases)))

# 为每个疾病构造 3 类查询
test_queries = []
for d in test_diseases:
    name = d.get("name", "")
    if not name:
        continue

    # Q1: 症状查询 — "XX症状是什么病"
    symptoms = _to_str(d.get("symptom", ""))
    if symptoms and len(symptoms) > 5:
        kw = symptoms[:30]
        test_queries.append({
            "query": f"{kw}可能是什么病",
            "expected_disease": name,
            "type": "症状→疾病"
        })

    # Q2: 疾病名查询 — 精确查某疾病
    test_queries.append({
        "query": f"{name}的病因是什么",
        "expected_disease": name,
        "type": "疾病→病因"
    })

    # Q3: 并发症查询
    neopathy = _to_str(d.get("neopathy", ""))
    if neopathy and len(neopathy) > 3:
        test_queries.append({
            "query": f"{name}会引起哪些并发症",
            "expected_disease": name,
            "type": "疾病→并发症"
        })

print(f"\n测试查询总数: {len(test_queries)}")

# ============================================================
# 2. 运行检索评估
# ============================================================
vs = get_vector_store()

results = {
    "total": 0,
    "hit@1": 0,    # 第一名命中
    "hit@3": 0,    # Top-3 命中
    "hit@5": 0,    # Top-5 命中
    "mrr": [],     # 倒数排名（MRR）
    "latencies": [],
    "failures": [],
    "by_type": {},
}

for i, tq in enumerate(test_queries):
    query = tq["query"]
    expected = tq["expected_disease"]
    qtype = tq["type"]

    # 1) ChromaDB 向量检索
    t0 = time.time()
    docs = vs.search(query, top_k=5)
    lat = (time.time() - t0) * 1000
    results["latencies"].append(lat)

    # 2) 知识图谱关键词检索（作为对照）
    kg_results = search_disease(query, top_k=5)

    # 3) 判断命中
    hit_rank = None
    for rank, doc in enumerate(docs):
        if expected in doc["content"]:
            hit_rank = rank + 1
            break

    # KG 命中
    kg_hit_rank = None
    for rank, kr in enumerate(kg_results):
        if kr["disease"].get("name") == expected:
            kg_hit_rank = rank + 1
            break

    results["total"] += 1

    if hit_rank:
        if hit_rank <= 1: results["hit@1"] += 1
        if hit_rank <= 3: results["hit@3"] += 1
        if hit_rank <= 5: results["hit@5"] += 1
        results["mrr"].append(1.0 / hit_rank)
    else:
        results["mrr"].append(0.0)

    # 按查询类型统计
    if qtype not in results["by_type"]:
        results["by_type"][qtype] = {"total": 0, "hit": 0, "kg_hit": 0}
    results["by_type"][qtype]["total"] += 1
    if hit_rank: results["by_type"][qtype]["hit"] += 1
    if kg_hit_rank: results["by_type"][qtype]["kg_hit"] += 1

    # 记录失败案例
    if not hit_rank and i < 20:
        results["failures"].append({
            "query": query,
            "expected": expected,
            "retrieved": [d["content"][:80] for d in docs[:3]],
            "kg_retrieved": [kr["disease"].get("name","") for kr in kg_results[:3]]
        })

# ============================================================
# 3. 输出结果
# ============================================================
print("\n" + "=" * 60)
print("📊 检索精度评估结果")
print("=" * 60)

total = results["total"]
print(f"\n{'指标':<25} {'数值':>10} {'达标(≥80%)':>12}")
print("-" * 50)
print(f"{'测试查询数':<25} {total:>10}")
print(f"{'Hit@1 (首位命中)':<25} {results['hit@1']/total*100:>9.1f}% {'✅' if results['hit@1']/total>=0.8 else '❌':>12}")
print(f"{'Hit@3 (前三命中)':<25} {results['hit@3']/total*100:>9.1f}% {'✅' if results['hit@3']/total>=0.8 else '❌':>12}")
print(f"{'Hit@5 (前五命中)':<25} {results['hit@5']/total*100:>9.1f}% {'✅' if results['hit@5']/total>=0.8 else '❌':>12}")
print(f"{'MRR (平均倒数排名)':<25} {statistics.mean(results['mrr']):>9.4f}")
print(f"{'平均检索延迟':<25} {statistics.mean(results['latencies']):>8.1f} ms")
print(f"{'P50 延迟':<25} {statistics.median(results['latencies']):>8.1f} ms")
print(f"{'P95 延迟':<25} {sorted(results['latencies'])[int(total*0.95)] if total>0 else 0:>8.1f} ms")

print(f"\n{'查询类型':<20} {'数量':>6} {'ChromaDB命中':>12} {'KG命中':>10}")
print("-" * 50)
for qtype, stats in sorted(results["by_type"].items()):
    cr = stats["hit"]/stats["total"]*100 if stats["total"]>0 else 0
    kr = stats["kg_hit"]/stats["total"]*100 if stats["total"]>0 else 0
    print(f"{qtype:<20} {stats['total']:>6} {cr:>11.1f}% {kr:>9.1f}%")

# 失败案例
if results["failures"]:
    print(f"\n📋 部分未命中案例 (前{len(results['failures'])}个):")
    for f in results["failures"]:
        print(f"  ❓ {f['query'][:50]}...")
        print(f"     期望: {f['expected']}")
        print(f"     ChromaDB: {[d[:40] for d in f['retrieved']]}")
        print(f"     KG: {f['kg_retrieved']}")

# 最终判定
hit5_pct = results["hit@5"] / total * 100
print("\n" + "=" * 60)
if hit5_pct >= 80:
    print(f"✅ 检索精度 Hit@5 = {hit5_pct:.1f}% ≥ 80% — 达标！")
elif hit5_pct >= 70:
    print(f"⚠️ 检索精度 Hit@5 = {hit5_pct:.1f}% — 接近但未达 80% 标准")
else:
    print(f"❌ 检索精度 Hit@5 = {hit5_pct:.1f}% < 80% — 未达标")
print("=" * 60)

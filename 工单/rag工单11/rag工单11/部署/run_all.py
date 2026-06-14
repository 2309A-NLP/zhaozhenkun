"""
总入口模块（部署层） — 一键运行Embedding微调全流程
功能：调用全部 6 个子模块（config→data_prep→mimo_api→losses→trainer→evaluator）
完成：PDF解析→三元组→MiMo问答对→基线评估→LoRA微调→微调后评估→对比报告
用法：python run_all.py [--step 1|2|3|4|5]
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""
import logging
import sys, time, json, random                  # 系统/时间/JSON/随机
import torch                                     # PyTorch
from config import (setup_logging, ensure_dirs, OUTPUT_DIR, MODEL_DIR, DATA_DIR, EVAL_DIR,
                     PDF_PATHS, LORA_CONFIG, TRAIN_CONFIG, normalize_path)
from data_prep import (prepare_training_data, chunk_text,
                        parse_pdf, split_train_eval)
from losses import get_loss_function             # 损失函数（根据配置自动选择）
from trainer import EmbeddingFineTuner           # LoRA微调器
from evaluator import EmbeddingEvaluator          # 评估器
from mimo_api import score_qa_pairs, generate_qa_from_chunks  # MiMo问答对

setup_logging()
logger = logging.getLogger(__name__)
logger.info("RAG工单11 启动")


def save_json(data, path):
    """保存数据为JSON文件"""
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  [保存] {path}")


def gen_qa(chunks, max_pairs=150):
    """
    规则法从文本块提取问答对（作为MiMo生成前的兜底）
    策略：从带问号的句子提取问题，相邻块做正例，远块做负例
    """
    pairs = []
    for i in range(1, len(chunks) - 1):
        if len(pairs) >= max_pairs:
            break
        c = chunks[i]
        if len(c.strip()) < 20:
            continue                                                # 跳过太短的块
        lines = c.strip().split("\n")                              # 按行拆分
        q = next((l[:80] for l in lines if "?" in l or "？" in l), None)  # 找含问号的行
        if not q:
            q = next((l[:80] for l in lines if len(l) > 10
                      and not l.startswith("第")), c[:80])           # 兜底取首行
        far = [j for j in range(len(chunks)) if abs(j - i) > 10]   # 远距离块索引
        neg = chunks[random.choice(far)][:200] if far else chunks[(i + 5) % len(chunks)][:200]
        pairs.append({"query": q.strip(), "answer": c, "negative": neg})
    print(f"  [规则QA] {len(pairs)}个")
    return pairs


def merge_qas(train_trip, eval_trip, qas):
    """将问答对转为三元组并合并到训练/评估集中"""
    if not qas:
        return train_trip, eval_trip
    qa_trip = [{"anchor": q["query"], "positive": q["answer"],
                "negative": q["negative"]} for q in qas]
    qa_tr, qa_ev = split_train_eval(qa_trip)                       # 划分
    tr = train_trip + qa_tr
    ev = eval_trip + qa_ev
    random.shuffle(tr)
    random.shuffle(ev)
    print(f"  [合并] 训练{len(tr)} 评估{len(ev)}")
    return tr, ev


def step1():
    """
    Step 1: 数据准备
    PDF解析→文本切分→三元组构造→规则QA→MiMo问答对生成→MiMo评分筛选→合并
    """
    logger.info("=== Step 1/5: 数据准备 ===")
    print("\n" + "=" * 50 + "\nStep 1/5: 数据准备\n" + "=" * 50)
    tr, ev = prepare_training_data()                                # 基础三元组
    all_text = "".join(parse_pdf(normalize_path(p)) + "\n\n"       # 合并所有PDF文本
                      for p in PDF_PATHS)
    chunks = chunk_text(all_text)                                   # 文本分块
    qas = gen_qa(chunks)                                            # 规则问答对
    save_json(qas, str(DATA_DIR / "qa_triplets.json"))

    # MiMo API 生成高质量问答对
    print("\n[MiMo问答对生成]")
    try:
        mimo_qas = generate_qa_from_chunks(chunks, max_pairs=30, sample_size=10)
        if mimo_qas:
            save_json(mimo_qas, str(DATA_DIR / "qa_mimo_generated.json"))
            qas = qas + mimo_qas                                   # 合并
    except Exception as ex:
        print(f"  [MiMo生成跳过] {ex}")

    # MiMo API 质量评分筛选
    if qas:
        print("\n[MiMo评分]")
        try:
            hq = score_qa_pairs(qas, max_score=10)
            save_json(hq, str(DATA_DIR / "qa_high_quality.json"))
        except Exception as ex:
            print(f"  [MiMo评分跳过] {ex}")
            hq = qas                                                # 失败则全部保留
    else:
        hq = []
    return merge_qas(tr, ev, hq)


def step2(ev):
    """
    Step 2: 微调前基线评估
    加载原始BGE-M3→三元组指标评估→RAG检索评估
    """
    logger.info("=== Step 2/5: 基线评估 ===")
    print("\n" + "=" * 50 + "\nStep 2/5: 基线评估\n" + "=" * 50)
    t = EmbeddingFineTuner()
    t.load_model()                                                  # 加载原始BGE-M3
    e = EmbeddingEvaluator()
    e.evaluate(t, "微调前(Baseline)", ev)                           # 三元组评估
    # RAG检索评估：用招股书文本验证检索效果
    try:
        all_text = "".join(parse_pdf(normalize_path(p)) + "\n\n" for p in PDF_PATHS)
        chunks = chunk_text(all_text)[:200]                         # 取前200块
        # 构造简单答案集（每块本身即为答案）
        answer_chunks = [[i] for i in range(len(chunks))]
        e.evaluate_rag_retrieval(t, "微调前(Baseline)", chunks, answer_chunks)
    except Exception as ex:
        print(f"  [RAG评估跳过] {ex}")
    save_json(e.results, str(EVAL_DIR / "eval_results_cache.json"))
    return t, e


def step3(t, tr, ev):
    """
    Step 3: LoRA 微调训练
    使用选定的损失函数和训练参数执行LoRA微调
    """
    logger.info("=== Step 3/5: LoRA微调 ===")
    print("\n" + "=" * 50 + "\nStep 3/5: LoRA微调\n" + "=" * 50)
    loss_fn = get_loss_function()                                   # 根据配置选择损失
    print(f"  损失函数: {TRAIN_CONFIG['loss_type']}")
    print(f"  LoRA rank: {LORA_CONFIG['r']}")
    t.load_model()                                                  # 重新加载（确保干净状态）
    t.train(tr, ev)                                                 # 执行训练
    return t.save_final_model()                                     # 保存LoRA权重


def step4(e, ev):
    """
    Step 4: 微调后评估
    加载微调后的LoRA权重→三元组评估→RAG检索评估→对比
    """
    logger.info("=== Step 4/5: 微调后评估 ===")
    print("\n" + "=" * 50 + "\nStep 4/5: 微调后评估\n" + "=" * 50)
    final = MODEL_DIR / "final"
    if not final.exists():
        print("[错误] 微调模型不存在，请先运行step3")
        return
    # 恢复step2的基线评估结果
    cache = EVAL_DIR / "eval_results_cache.json"
    if cache.exists():
        e.results = json.load(open(cache, encoding="utf-8"))
    # 加载微调后的模型（基础模型+LoRA adapter）
    from peft import PeftModel
    from transformers import AutoModel, AutoTokenizer
    from config import setup_logging, get_model_path
    base = AutoModel.from_pretrained(get_model_path(),
                                      trust_remote_code=True,
                                      torch_dtype=torch.float16)
    tuned = EmbeddingFineTuner()
    tuned.model = PeftModel.from_pretrained(base, final)             # 加载LoRA权重
    tuned.tokenizer = AutoTokenizer.from_pretrained(get_model_path())
    tuned.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tuned.model.to(tuned.device)
    e.evaluate(tuned, "微调后(Fine-tuned)", ev)                     # 三元组评估
    # RAG检索评估（同样数据）
    try:
        all_text = "".join(parse_pdf(normalize_path(p)) + "\n\n" for p in PDF_PATHS)
        chunks = chunk_text(all_text)[:200]
        answer_chunks = [[i] for i in range(len(chunks))]
        e.evaluate_rag_retrieval(tuned, "微调后(Fine-tuned)", chunks, answer_chunks)
    except Exception as ex:
        print(f"  [RAG评估跳过] {ex}")
    save_json(e.results, str(EVAL_DIR / "eval_results_cache.json"))
    print("  [缓存] evaluator结果已保存")


def step5(e=None):
    """
    Step 5: 生成对比报告
    汇总微调前后全部指标→输出JSON报告和控制台摘要
    """
    logger.info("=== Step 5/5: 对比报告 ===")
    print("\n" + "=" * 50 + "\nStep 5/5: 对比报告\n" + "=" * 50)
    if e is None:
        cache = EVAL_DIR / "eval_results_cache.json"
        if not cache.exists():
            print("[错误] 请先运行step4")
            return
        e = EmbeddingEvaluator()
        e.results = json.load(open(str(cache), encoding="utf-8"))
    return e.save_report(e.compare())


def run_all():
    """
    完整流水线：一键运行全部5步
    产出自動保存到 output/data/ + output/models/ + output/eval/
    """
    t0 = time.time()
    print("\n" + "★" * 50 + "\nEmbedding模型微调 - 完整流水线\n" + "★" * 50)
    print(f"  BGE-M3 | LoRA r={LORA_CONFIG['r']} | "
          f"epochs={TRAIN_CONFIG['epochs']} | loss={TRAIN_CONFIG['loss_type']}")
    tr, ev = step1()                                               # 数据准备
    if not tr:
        print("[终止] 数据准备失败")
        return
    tu, eva = step2(ev)                                            # 基线评估
    step3(tu, tr, ev)                                              # 微调训练
    step4(eva, ev)                                                 # 微调后评估
    step5(eva)                                                     # 对比报告
    print(f"\n[总计] {time.time()-t0:.0f}秒 | 产出: {OUTPUT_DIR}")


if __name__ == "__main__":
    ensure_dirs()
    if len(sys.argv) == 1:
        run_all()                                                   # 无参数：完整流水线
    elif len(sys.argv) == 3 and sys.argv[1] == "--step":
        s = sys.argv[2]
        tp = DATA_DIR / "train_triplets.json"
        ep = DATA_DIR / "eval_triplets.json"
        tr = json.load(open(tp, encoding="utf-8")) if tp.exists() else []
        ev = json.load(open(ep, encoding="utf-8")) if ep.exists() else []
        # 步骤分发映射
        actions = {
            "1": lambda: step1(),
            "2": lambda: step2(ev),
            "3": lambda: step3(EmbeddingFineTuner(), tr, ev),
            "4": lambda: step4(EmbeddingEvaluator(), ev),
            "5": lambda: step5()
        }
        if s in actions:
            if s in ("2", "3", "4") and not ev:
                print("[错误] 缺少评估数据，请先运行step1")
            else:
                actions[s]()
        else:
            print("用法: python run_all.py [--step 1|2|3|4|5]")
    else:
        print("用法: python run_all.py          # 完整流水线")
        print("      python run_all.py --step N  # 单独运行步骤N")

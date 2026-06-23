# -*- coding: utf-8 -*-
"""
debug_test.py — RAG系统诊断调试脚本
功能：逐步测试检索+生成流水线，所有日志同时输出到控制台和 debug.log 文件
运行方式: python debug_test.py
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
"""

import logging, sys, time, os  # 标准库

# ============================================================
# 日志配置：同时输出到控制台 + debug.log 文件
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")  # 日志文件路径
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"  # 格式
LOG_DATE_FORMAT = "%H:%M:%S"  # 时间格式

# 根日志器配置
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG级别捕获所有信息
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),  # 控制台输出
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')  # 文件输出（覆盖模式）
    ]
)
logger = logging.getLogger("debug")  # 调试日志器

# 第三方库降噪
for lib in ["werkzeug", "sklearn", "urllib3", "requests"]:  # 降噪列表
    logging.getLogger(lib).setLevel(logging.WARNING)  # 只显示警告以上


def test_step1_load_index():
    """步骤1：加载索引"""
    logger.info("=" * 60)
    logger.info("步骤1: 加载招股书索引")
    logger.info("=" * 60)
    from indexer import get_or_build_index  # 索引器
    import config  # 配置
    t0 = time.time()  # 计时
    idx = get_or_build_index(config.PDF_TXT_DIR, config.INDEX_CACHE_DIR,
                              config.CHUNK_SIZE, config.CHUNK_OVERLAP)  # 加载
    logger.info("索引加载完成，耗时 %.1f 秒", time.time() - t0)  # 时间
    vec, cv, chunks, meta, cmap = idx  # 解包
    logger.info("索引详情: %d 块 | %d TF-IDF词汇 | %d 家公司映射",
                len(chunks), len(vec.vocabulary_), len(cmap))  # 详情
    # 打印前5个公司映射
    logger.info("公司映射示例（前5条）:")
    for i, (k, v) in enumerate(list(cmap.items())[:5]):  # 前5条
        logger.info("  [%d字] %s → %s", len(k), k, v[:50])  # 打印
    return idx  # 返回索引


def test_step2_company_matching(cmap):
    """步骤2：测试公司名提取和映射匹配"""
    logger.info("=" * 60)
    logger.info("步骤2: 公司名提取 & 映射匹配")
    logger.info("=" * 60)
    from retriever import extract_company_name  # 公司名提取
    test_qs = [  # 测试问题列表
        "报告期内武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少",
        "云南沃森生物技术股份有限公司负责产品研发的是什么部门",
        "湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些",
    ]
    for q in test_qs:  # 遍历测试
        logger.info("---")
        logger.info("问题: %s", q)  # 打印问题
        companies = extract_company_name(q)  # 提取公司名
        logger.info("提取公司名: %s", companies)  # 打印公司名
        matched = False  # 匹配标记
        for name in companies:  # 遍历
            if name in cmap:  # 精确命中
                logger.info("✅ 全名精确命中: %s → %s", name, cmap[name])  # 命中
                matched = True  # 标记
                break  # 找到
            for cm_key, cm_file in cmap.items():  # 遍历映射
                if len(cm_key) >= 10 and cm_key in name:  # 长key包含
                    logger.info("✅ 长key包含命中: [%s] ⊂ [%s] → %s", cm_key, name, cm_file)  # 命中
                    matched = True  # 标记
                    break  # 找到
        if not matched:  # 全部未命中
            logger.warning("❌ 未命中！公司名: %s", companies)  # 未命中
            logger.warning("   映射中的相关key: %s",
                           [k for k in cmap if any(c in k or k in c for c in companies)][:5])  # 相关key


def test_step3_retrieval(idx, question):
    """步骤3：测试检索流程"""
    logger.info("=" * 60)
    logger.info("步骤3: 检索流程")
    logger.info("=" * 60)
    vec, cv, chunks, meta, cmap = idx  # 解包
    from retriever import search, extract_company_name, _build_file_index, _find_file_by_company
    # 公司名提取
    companies = extract_company_name(question)  # 提取
    logger.info("问题: %s", question)  # 问题
    logger.info("公司名: %s", companies)  # 公司名
    # 映射匹配
    matched_files = []  # 命中文件
    if companies and cmap:  # 有映射
        for name in companies:  # 遍历
            if name in cmap:  # 精确
                matched_files.append(cmap[name])  # 定位
                logger.info("映射命中: %s → %s", name, cmap[name])  # 日志
                break  # 找到
            for cm_key, cm_file in cmap.items():  # 遍历
                if len(cm_key) >= 10 and cm_key in name:  # 包含
                    matched_files.append(cm_file)  # 定位
                    logger.info("包含命中: %s ⊂ %s → %s", cm_key, name, cm_file)  # 日志
                    break  # 找到
    # 采样兜底
    if not matched_files:  # 映射未命中
        matched_files = _find_file_by_company(companies, meta, chunks)  # 采样
        logger.info("采样搜索结果: %s", matched_files)  # 日志
    logger.info("最终命中文件数: %d", len(matched_files))  # 文件数
    # 检索
    results, rmeta, rscores = search(question, vec, cv, chunks, meta, top_k=10, company_map=cmap)  # 检索
    logger.info("检索到 %d 个文本块", len(results))  # 块数
    # 检查是否包含关键数据
    for i, (c, m, s) in enumerate(zip(results, rmeta, rscores)):  # 遍历
        if '军用' in c and '万元' in c and any(d in c for d in ['6,464', '14,414', '18,780', '4,627']):  # 收入数据
            logger.info("✅ 第%d块包含军用收入数据 (得分=%.3f, 文件=%s)", i+1, s, m['source'][:40])  # 命中
            break  # 找到
    else:  # 未找到
        logger.warning("❌ 检索结果中未找到军用收入数据！")  # 未找到
        logger.warning("检索到的文件: %s", list(set(m['source'] for m in rmeta)))  # 文件列表
    return results, rmeta, rscores  # 返回


def test_step4_generation(idx, question, results, rmeta, rscores):
    """步骤4：测试LLM答案生成"""
    logger.info("=" * 60)
    logger.info("步骤4: LLM答案生成")
    logger.info("=" * 60)
    from generator import build_rag_prompt, call_deepseek  # 生成器
    messages = build_rag_prompt(question, results, rmeta, rscores)  # 构建Prompt
    logger.info("Prompt长度: system=%d, user=%d", len(messages[0]['content']), len(messages[1]['content']))  # 长度
    t0 = time.time()  # 计时
    answer = call_deepseek(messages)  # 调用LLM
    logger.info("LLM耗时: %.1f 秒", time.time() - t0)  # 耗时
    logger.info("LLM答案:\n%s", answer)  # 答案
    return answer  # 返回


def main():
    """主诊断流程"""
    logger.info("RAG系统诊断调试开始")
    logger.info("日志文件: %s", LOG_FILE)
    logger.info("")

    # 步骤1: 加载索引
    idx = test_step1_load_index()  # 加载
    vec, cv, chunks, meta, cmap = idx  # 解包

    # 步骤2: 公司名匹配
    test_step2_company_matching(cmap)  # 匹配

    # 步骤3&4: 测试兴图新科问题
    q = "报告期内武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少"  # 测试问题
    results, rmeta, rscores = test_step3_retrieval(idx, q)  # 检索
    if results:  # 有结果
        answer = test_step4_generation(idx, q, results, rmeta, rscores)  # 生成

    # 总结
    logger.info("=" * 60)
    logger.info("诊断完成！完整日志已保存到: %s", LOG_FILE)
    logger.info("=" * 60)


if __name__ == "__main__":  # 直接运行
    main()  # 启动诊断

# -*- coding: utf-8 -*-
"""
tool_prospectus.py — 招股书问答工具（阶段1-2: 公司名提取 + 文件匹配）
--------------------------------------------------------------
功能: 在80+份招股书文本中定位与用户问题最相关的文件。
      多策略公司名提取（后缀匹配 + ngram）+ 分层文件打分（后缀/ngram/内容词）。
      最终将最佳匹配文件传递给 RAG 阶段进行段落提取和问答。

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import os          # 文件系统操作
import re          # 正则表达式
import logging     # 日志记录
import sys as _sys  # 诊断：平台信息

from tool_prospectus_rag import prospectus_rag_answer  # 段落提取 + RAG 问答

logger = logging.getLogger("agent.tools")


def _find_data_dir(relative_path: str) -> str | None:
    """【直接嵌入版】跨平台查找 bs_challenge_financial_14b_dataset 数据目录。

    不依赖 tool_utils.resolve_data_path（避免导入缓存导致旧代码被执行）。
    优先级: 环境变量 → 候选硬路径 → Path.home()

    返回: 完整路径(str) 或 None
    """
    dataset = "bs_challenge_financial_14b_dataset"

    # 0. 环境变量
    env_val = os.environ.get("PROSPECTUS_PDF_DIR") or os.environ.get("FUND_DB_DIR")
    if env_val:
        p = os.path.join(env_val, relative_path)
        if os.path.isdir(p) or os.path.isfile(p):
            logger.info("✅ 数据(环境变量): %s", p)
            return p

    # 1. 构建候选 bs_challenge_financial_14b_dataset 根目录
    candidates = []

    # 从当前文件定位项目目录
    _here = os.path.dirname(os.path.abspath(__file__))          # .../Agent工单9/研发
    _proj = os.path.dirname(_here)                               # .../Agent工单9
    _desktop = os.path.dirname(_proj)                            # .../Desktop

    # Windows 硬路径（覆盖多个用户名）
    for user in ["31326", os.environ.get("USERNAME", ""), os.environ.get("USER", "")]:
        if user:
            candidates.append(f"C:\\Users\\{user}\\{dataset}")
            candidates.append(f"C:/Users/{user}/{dataset}")

    # WSL 路径
    candidates.append(f"/mnt/c/Users/31326/{dataset}")

    # 项目相对路径
    candidates.append(os.path.join(_proj, dataset))
    candidates.append(os.path.join(_desktop, dataset))

    # 当前目录
    candidates.append(os.path.join(os.getcwd(), dataset))
    candidates.append(os.path.join(os.path.dirname(os.getcwd()), dataset))

    # USERPROFILE
    up = os.environ.get("USERPROFILE", "")
    if up:
        candidates.append(os.path.join(up, dataset))

    # Home
    candidates.append(os.path.join(os.path.expanduser("~"), dataset))

    # 逐一检查（去重）
    seen = set()
    for i, c in enumerate(candidates):
        c = os.path.normpath(c)
        if c in seen:
            continue
        seen.add(c)
        target = os.path.join(c, relative_path)
        if os.path.isdir(target) or os.path.isfile(target):
            logger.info("✅ 数据找到[%d]: %s", i, target)
            return target
        else:
            logger.debug("  候选[%d]❌: %s", i, target)

    # 全线失败 → 打完整诊断
    logger.error("❌ 数据目录未找到! relative=%s platform=%s cwd=%s 检查了%d个路径",
                 relative_path, _sys.platform, os.getcwd(), len(seen))
    for i, c in enumerate(seen):
        logger.error("  路径%d: %s", i, c)
    return None


def tool_prospectus_qa(query: str) -> dict:
    """招股书问答工具 — 公司名定位 + 文件匹配 + RAG 问答

    四阶段流水线:
      阶段1: 公司名提取（后缀模式 + ≥6字中文片段）
      阶段2: 文件匹配（分层打分: 后缀>ngram>内容词，含文件名回退）
      阶段3-4: 委托 tool_prospectus_rag. prospectus_rag_answer 完成段落提取和 RAG

    参数:
        query (str): 用户自然语言查询

    返回:
        dict: {"success": bool, "result": str, "tool": str}
    """
    logger.info("📄 招股书: %s", query[:60])

    try:
        # ================================================================
        # 阶段0: 数据目录定位（使用直接嵌入版，不依赖 tool_utils）
        # ================================================================
        pdf_dir = _find_data_dir("pdf_txt_file")
        if not pdf_dir:
            return {
                "success": False,
                "result": (
                    "❌ 招股书数据目录未找到。\n\n"
                    f"平台: {_sys.platform}\n"
                    f"工作目录: {os.getcwd()}\n\n"
                    "请确认 bs_challenge_financial_14b_dataset 已下载到以下任一位置:\n"
                    f"  • {os.path.join(os.path.expanduser('~'), 'bs_challenge_financial_14b_dataset')}\n"
                    "  • C:\\Users\\31326\\bs_challenge_financial_14b_dataset\n\n"
                    "查看 agent.log 搜索 '数据目录未找到' 获取完整诊断信息。"
                ),
                "tool": "招股书问答"
            }

        # ================================================================
        # 阶段1: 公司名提取（多策略）
        # ================================================================
        q_compact = re.sub(r'\s+', '', query)  # 去除所有空格（PDF复制artifact）
        company_candidates = []

        # 策略A: 后缀模式匹配 "XX股份有限公司"、"XX有限公司"
        for suffix in ['股份有限公司', '有限公司', '有限责任公司', '科技集团', '控股集团']:
            idx = q_compact.find(suffix)
            if idx >= 0:
                start = max(0, idx - 14)  # 向前取最多14字
                name = q_compact[start:idx + len(suffix)]
                # 去掉前面可能的标点/虚词
                name = re.sub(
                    r'^[的了是在而如何什么哪该请帮查询计算报告期内分多少从及与于]+',
                    '', name
                )
                if len(name) >= 6:
                    company_candidates.append(name)

        # 策略B: 回退 — ≥6字的连续中文字符串
        if not company_candidates:
            long_words = re.findall(r'[一-龥]{6,}', q_compact)
            company_candidates = list(set(long_words))

        logger.info("公司名候选: %s", company_candidates[:3])

        # 从公司名生成多粒度搜索词
        company_search_terms = []
        for cand in company_candidates:
            company_search_terms.append(cand)  # 紧凑版
            # 每2字间插入空格版（PDF artifact）
            spaced = ' '.join(cand[i:i + 2] for i in range(0, len(cand), 2))
            company_search_terms.append(spaced)
            # ngram 片段 (3-6字)
            for n in [3, 4, 5, 6]:
                for i in range(len(cand) - n + 1):
                    company_search_terms.append(cand[i:i + n])

        # 从问题提取内容关键词（辅助打分）
        stop = r'[的了是而在如何什么哪该请帮查询计算报告期内分别多少负责具体以及来自\.\?\？\。\，\、\s：:]+'
        all_words = [
            kw.strip() for kw in re.split(stop, query) if len(kw.strip()) >= 2
        ]
        content_keywords = list(set(all_words))

        # ================================================================
        # 阶段2: 文件匹配（分层打分）
        # ================================================================
        txt_files = sorted([
            f for f in os.listdir(pdf_dir) if f.endswith('.txt')
        ])
        best_file, best_score, best_name = None, 0, ''

        # --- 第1轮: 内容匹配 ---
        for fname in txt_files:
            try:
                with open(os.path.join(pdf_dir, fname), 'r',
                          encoding='utf-8', errors='ignore') as f:
                    fc = f.read()
                fc_compact = re.sub(r'\s+', '', fc)  # 去空格版

                # 后缀匹配（权重 10000）
                suffix_hits = 0
                for cand in company_candidates:
                    short = cand[-8:] if len(cand) > 10 else cand
                    if short in fc_compact:
                        suffix_hits += 10000

                # ngram 匹配（权重 500）
                ngram_hits = sum(
                    1 for kw in set(company_search_terms) if kw in fc_compact
                )
                # 内容词匹配（权重 5）
                content_hits = sum(
                    1 for kw in content_keywords[:30]
                    if kw in fc or kw in fc_compact
                )
                score = suffix_hits + ngram_hits * 500 + content_hits * 5
                if score > best_score:
                    best_score, best_file, best_name = score, fc, fname
            except Exception:
                pass

        # --- 第2轮: 文件名+内容二次匹配（首轮得分低时触发）---
        if best_score < 1 and company_candidates:
            logger.info("内容匹配弱，尝试文件名+内容二次匹配...")
            for fname in txt_files:
                try:
                    with open(os.path.join(pdf_dir, fname), 'r',
                              encoding='utf-8', errors='ignore') as f:
                        fc = f.read()
                    fc_compact = re.sub(r'\s+', '', fc)
                    fname_compact = re.sub(r'\s+', '', fname)
                    score = 0
                    for cand in company_candidates:
                        short = cand[-8:] if len(cand) > 10 else cand
                        if short in fname_compact:
                            score += 20000
                        if cand in fname_compact:
                            score += 40000
                        if short in fc_compact:
                            score += 10000
                    ngram_hits = sum(
                        1 for kw in set(company_search_terms) if kw in fc_compact
                    )
                    content_hits = sum(
                        1 for kw in content_keywords[:30]
                        if kw in fc or kw in fc_compact
                    )
                    score += ngram_hits * 500 + content_hits * 5
                    if score > best_score:
                        best_score, best_file, best_name = score, fc, fname
                except Exception:
                    pass

        logger.info("招股书文件: %s (得分=%d)",
                     (best_name or '无')[:40], best_score)

        # --- 全量回退: 合并多个文件 ---
        if not best_file or best_score < 1:
            logger.warning("标准匹配失败，全量搜索...")
            all_content = []
            for fname in txt_files[:10]:
                try:
                    with open(os.path.join(pdf_dir, fname), 'r',
                              encoding='utf-8', errors='ignore') as f:
                        all_content.append(f.read()[:3000])
                except Exception:
                    pass
            if all_content:
                best_file = "\n---\n".join(all_content)
                best_name = "多文件合并"
            else:
                return {
                    "success": False,
                    "result": (
                        "未在80份招股书中找到相关信息，"
                        "请检查数据目录是否正确"
                    ),
                    "tool": "招股书问答"
                }

        # ================================================================
        # 阶段3-4: 委托 RAG 模块完成段落提取 + 问答
        # ================================================================
        answer = prospectus_rag_answer(
            best_file=best_file,
            best_name=best_name,
            query=query,
            company_candidates=company_candidates,
            all_words=all_words,
        )

        return {
            "success": True,
            "result": answer[:3000] if answer else "生成失败",
            "tool": "招股书问答"
        }

    except Exception as e:
        logger.error("招股书错误: %s", e)
        return {
            "success": False,
            "result": f"招股书查询失败: {str(e)[:200]}",
            "tool": "招股书问答"
        }

# -*- coding: utf-8 -*-
"""
main.py — 基金数据问答Web应用（前后端交互）
功能：Flask后端 + DeepSeek NL2SQL引擎，浏览器输入问题即时回答
启动后访问 http://127.0.0.1:5000 进入交互界面
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""
import json, sqlite3, time, os, sys, re, threading, argparse  # 标准库
from flask import Flask, request, jsonify, render_template  # Flask Web框架
import config  # 配置文件
from logger import setup_logging, get_logger
from db_explorer import explore_database, get_connection  # 数据库探索
from prompt_builder import build_system_prompt  # Prompt构建
from deepseek_client import call_deepseek_api, generate_sql, extract_sql_from_response  # API客户端
# 模板目录: 部署/templates/
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "部署", "templates")
if not os.path.isdir(_TEMPLATE_DIR):
    _TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "部署", "templates")
app = Flask(__name__, template_folder=_TEMPLATE_DIR)
logger = get_logger("fund_qa.main")
# 全局初始化（服务启动时执行一次）
print("=" * 55)  # 打印分隔线
print("  基金数据智能问答系统 — 启动中...")  # 启动提示
print("=" * 55)  # 打印分隔线

# 1. 加载数据库schema信息
print("[1/3] 加载数据库Schema...")  # 进度提示
DB_INFO = explore_database(config.DB_PATH)  # 探索10张表的结构
for t in DB_INFO['table_names']:  # 遍历表名
    info = DB_INFO['all_info'][t]  # 获取表信息
    print(f"  ✓ {t}: {info['row_count']:,} 行")  # 打印表名和行数

# 2. 构建NL2SQL系统提示词（整个服务共享一个Prompt）
print("[2/3] 构建NL2SQL Prompt...")  # 进度提示
SYSTEM_PROMPT = build_system_prompt(  # 构建系统提示词
    DB_INFO["schema_description"],  # 10张表schema描述
    DB_INFO["relationship_description"]  # 表关系描述
)
print(f"  ✓ Prompt 长度: {len(SYSTEM_PROMPT)} 字符")  # 打印长度

# 3. 建立数据库连接（线程本地存储，每个线程独立连接）
print("[3/3] 初始化数据库连接...")  # 进度提示
DB_CONN_LOCK = threading.Lock()  # 数据库连接锁，保证线程安全

print(f"\n  ✅ 服务就绪！请打开浏览器访问: http://127.0.0.1:5000\n")  # 就绪提示


def get_db_conn():
    """获取当前线程可用的数据库连接，并初始化临时视图（简化LLM的SQL生成）"""
    from flask import g  # Flask请求上下文
    if not hasattr(g, 'db_conn'):  # 当前请求还没有连接
        conn = get_connection(config.DB_PATH)  # 创建新连接
        _create_helper_views(conn)  # 创建辅助视图（预计算涨跌幅）
        g.db_conn = conn  # 缓存连接
    return g.db_conn  # 返回连接


def _create_helper_views(conn):
    """创建临时视图：预计算涨跌幅等指标，让LLM只需写简单SELECT，不用写LAG窗口函数"""
    cursor = conn.cursor()  # 创建游标
    # 创建3个辅助视图，预计算涨跌幅/涨停，避免LLM写LAG窗口函数
    cursor.execute("CREATE TEMP VIEW IF NOT EXISTS stock_daily_change AS SELECT \"股票代码\",\"交易日\",\"收盘价(元)\",\"昨收盘(元)\",CASE WHEN \"昨收盘(元)\" IS NOT NULL AND \"昨收盘(元)\"!=0 THEN (\"收盘价(元)\"-\"昨收盘(元)\")/\"昨收盘(元)\"*100 ELSE NULL END AS 涨跌幅 FROM \"A股票日行情表\"")  # A股涨跌幅
    cursor.execute("CREATE TEMP VIEW IF NOT EXISTS hk_stock_daily_change AS SELECT \"股票代码\",\"交易日\",\"收盘价(元)\",\"昨收盘(元)\",CASE WHEN \"昨收盘(元)\" IS NOT NULL AND \"昨收盘(元)\"!=0 THEN (\"收盘价(元)\"-\"昨收盘(元)\")/\"昨收盘(元)\"*100 ELSE NULL END AS 涨跌幅 FROM \"港股票日行情表\"")  # 港股涨跌幅
    cursor.execute("CREATE TEMP VIEW IF NOT EXISTS stock_limit_up AS SELECT \"股票代码\",\"交易日\",CASE WHEN \"昨收盘(元)\" IS NOT NULL AND \"昨收盘(元)\"!=0 AND (\"收盘价(元)\"/\"昨收盘(元)\"-1)*100>=9.8 THEN 1 ELSE 0 END AS 是否涨停 FROM \"A股票日行情表\"")  # 涨停标记
    conn.execute("PRAGMA query_only = ON")  # 创建完视图后开启只读保护


def execute_sql(sql, timeout=60):
    """在SQLite数据库中执行SQL查询，返回(结果列表, 列名列表)"""
    conn = get_db_conn()  # 获取数据库连接
    cursor = conn.cursor()  # 创建游标
    cursor.execute(f"PRAGMA busy_timeout = {timeout * 1000}")  # 设置忙碌超时
    cursor.execute(sql)  # 执行SQL语句
    columns = [desc[0] for desc in cursor.description] if cursor.description else []  # 提取列名
    rows = cursor.fetchall()  # 获取所有结果行
    result = []  # 存储字典格式的结果
    for row in rows:  # 遍历每一行
        row_dict = {}  # 单行字典
        for i, col in enumerate(columns):  # 遍历列
            row_dict[col] = row[i]  # 列名→值
        result.append(row_dict)  # 添加到结果
    return result, columns  # 返回结果和列名


def format_sql_result(result, columns):
    """将SQL查询结果格式化为人类可读的完整答案"""
    if not result:
        return "未查询到相关数据"

    # 构建列名映射（列名→值）的描述性输出
    def fmt_val(v):
        """格式化单个值"""
        if v is None:
            return "无"
        if isinstance(v, float):
            if v == int(v):
                return str(int(v))
            return str(round(v, 4))
        return str(v)

    # 单行单列
    if len(result) == 1 and len(columns) == 1:
        return fmt_val(result[0][columns[0]])

    # 单行多列 — 用列名+值的完整句式
    if len(result) == 1:
        parts = []
        for col in columns:
            parts.append(f"{col}：{fmt_val(result[0][col])}")
        return "，".join(parts)

    # 多行 — 每行完整描述
    lines = []
    for i, row in enumerate(result[:20], 1):
        parts = [f"{col}：{fmt_val(row[col])}" for col in columns]
        lines.append(f"{i}. {'，'.join(parts)}")
    if len(result) > 20:
        lines.append(f"...（共{len(result)}条，仅显示前20条）")
    return "\n".join(lines)


def search_pdf_texts(question, pdf_dir, max_files=5):
    """在PDF解析TXT文件中定位关键词出现位置，提取周围相关段落"""
    pdf_texts = []
    stop_chars = r'[的了是而在如何什么哪该请帮我查询计算一下\.\?\？\。\，\、\s]+'
    keywords = [kw.strip() for kw in re.split(stop_chars, question) if len(kw.strip()) >= 2]
    if len(keywords) <= 1:
        keywords = [kw for kw in re.findall(r'[一-龥a-zA-Z0-9]{2,}', question) if len(kw) >= 3]

    # 公司名识别：>=4字的词 + 提取包含"有限公司"/"股份"的连续片段
    company_names = [kw for kw in keywords if len(kw) >= 4]
    # 同时从问题中提取"XX有限公司"模式的公司名片段
    company_pattern = re.findall(r'[一-鿿]{2,}(?:有限公司|股份有限公司|有限责任公司)', question)
    company_names.extend(company_pattern)
    # 去重
    company_names = list(set(company_names))

    txt_files = [f for f in os.listdir(pdf_dir) if f.endswith('.txt')]
    if not txt_files:
        return []

    for txt_file in txt_files:
        try:
            filepath = os.path.join(pdf_dir, txt_file)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # 检查公司名匹配（支持部分匹配：如"华铭智能"命中"上海华铭智能终端设备股份有限公司"）
            company_hit = False
            for name in company_names:
                if name in content:
                    company_hit = True
                    break
                # 部分匹配：公司名中的短片段命中
                if len(name) >= 6:
                    short = name[2:-2]  # 去掉前2后2字
                    if len(short) >= 4 and short in content:
                        company_hit = True
                        break

            # 关键词命中计数
            kw_hits = sum(1 for kw in keywords if kw in content)

            # 放宽阈值：公司名部分匹配 或 1个关键词命中即可
            if not company_hit and kw_hits < 1:
                continue

            chunks = []
            # 优先用公司名核心词定位
            search_terms = company_names[:3] + keywords[:5]
            for kw in search_terms:
                pos = content.find(kw)
                if pos >= 0:
                    start, end = max(0, pos - 600), min(len(content), pos + 1500)
                    chunks.append(content[start:end])

            if chunks:
                snippet = "\n...\n".join(chunks[:3])
                score = kw_hits + (20 if company_hit else 0)
                pdf_texts.append({"file": txt_file, "score": score, "snippet": snippet[:4000]})
        except Exception:
            continue

    pdf_texts.sort(key=lambda x: x["score"], reverse=True)
    return pdf_texts[:max_files]


def answer_from_pdf(question, pdf_dir):
    """PDF文本检索 + LLM生成答案（关键词定位→上下文→阅读理解）"""
    relevant = search_pdf_texts(question, pdf_dir)  # 搜索相关文本块
    if not relevant:  # 未找到
        return "未在招股书PDF中找到与「" + question[:30] + "」相关的信息"  # 返回
    context = "\n\n---\n\n".join([t["snippet"] for t in relevant])  # 合并上下文
    rag_prompt = f"阅读以下招股书文本，回答用户问题。\n\n## 文本\n{context}\n\n## 问题\n{question}\n\n## 要求\n准确引用原文信息，简洁回答。文本不相关则说明未包含。"
    messages = [{"role": "user", "content": rag_prompt}]  # 构建消息
    answer = call_deepseek_api(  # 调用LLM
        messages, config.DEEPSEEK_API_KEY,  # 消息和密钥
        config.DEEPSEEK_BASE_URL, config.DEEPSEEK_MODEL, timeout=120  # 地址和模型
    )
    return answer[:2000] if answer else "PDF检索问答失败"  # 返回答案


def process_question(question):
    """核心NL2SQL流水线：自然语言 → SQL → 执行 → 答案（含3次自动修正）"""
    # 第一步：调用DeepSeek生成SQL
    sql, raw = generate_sql(  # 生成SQL
        question=question,  # 用户问题
        system_prompt=SYSTEM_PROMPT,  # 全局共享的系统提示词
        api_key=config.DEEPSEEK_API_KEY,  # API密钥
        base_url=config.DEEPSEEK_BASE_URL,  # API地址
        model=config.DEEPSEEK_MODEL  # 模型
    )
    # 处理特殊情况
    if sql is None:  # API调用失败
        return "抱歉，AI服务暂时不可用，请稍后重试"  # 友好提示
    if sql == "NEED_PDF" or (sql and sql.upper().startswith("NEED_PDF")):  # 需要PDF
        return answer_from_pdf(question, config.PDF_TXT_DIR)  # 走PDF检索

    # 第二步：执行SQL（最多重试2次，共3次尝试）
    for attempt in range(3):  # 最多3次尝试
        try:
            result, columns = execute_sql(sql, config.SQL_TIMEOUT)  # 执行SQL
            return format_sql_result(result, columns)  # 格式化返回
        except Exception as e:  # SQL错误
            error_msg = str(e)  # 错误信息
            if attempt < 2:  # 还有重试机会
                print(f"  SQL修正(第{attempt+1}次): {error_msg[:100]}")  # 打印日志
                # 构建修正提示：强调用辅助视图、正确表名列名
                fix_tip = f"SQL错误: {error_msg}。"  # 错误信息
                fix_tip += "涨跌幅/涨停类问题必须用stock_daily_change或stock_limit_up视图！"  # 强调视图
                fix_tip += "所有表名列名必须与Schema完全一致。请重写完整SQL。"  # 通用提示
                fix_prompt = f"SQL执行失败。\n{fix_tip}\n问题: {question}\n原SQL:\n{sql}\n\n直接输出修正后的完整SQL:"  # 修正请求
                messages = [  # 修正消息
                    {"role": "system", "content": "直接输出修正后的完整SQL。涨跌幅用stock_daily_change视图，涨停用stock_limit_up视图。表名列名与Schema一致。"},  # 系统提示
                    {"role": "user", "content": fix_prompt}  # 用户消息
                ]
                fixed = call_deepseek_api(  # 调用API修正
                    messages, config.DEEPSEEK_API_KEY,  # 消息和密钥
                    config.DEEPSEEK_BASE_URL, config.DEEPSEEK_MODEL  # 地址和模型
                )
                if fixed:  # 获取到修正SQL
                    sql = extract_sql_from_response(fixed)  # 提取SQL
                    if sql == "NEED_PDF":  # 修正后判断需PDF
                        return answer_from_pdf(question, config.PDF_TXT_DIR)
            else:  # 第3次也失败
                return f"查询出错（已重试2次）: {error_msg}"  # 返回最终错误
    return "处理失败，请换个问法试试"  # 兜底


def sanitize_question(question):
    """清洗用户输入：从JSON碎片中提取真实问题，去除无关前缀和残留"""
    # 1. 从JSON片段中提取question字段的值（处理截断的JSON，如缺少结尾"}）
    json_qs = re.findall(r'"question"\s*:\s*"([^"]*?)(?:"\s*[}\]]|\s*$)', question)  # 匹配完整或截断的JSON
    if not json_qs:  # 第一轮没匹配到
        json_qs = re.findall(r'"question"\s*:\s*"(.+)', question)  # 更宽松：从question开始取到行尾
    if json_qs:  # 找到了嵌入的问题
        question = ' '.join(q.strip() for q in json_qs)  # 用提取的问题替换原始输入
    # 2. 清除残留JSON符号和字段名
    question = re.sub(r'[{}"\\]', ' ', question)  # JSON特殊字符→空格
    question = re.sub(r'\b(id|question|answer)\s*:\s*', '', question)  # 去除JSON字段名
    question = re.sub(r'^[\d,，\s]+', '', question)  # 去除开头的数字和逗号残留
    question = re.sub(r'^.*?北京八维信息集团\s*', '', question)  # 无关前缀
    # 4. 如果包含多个段落，取最后一段包含数据关键词的有效问题
    parts = re.split(r'[。？\?]{2,}', question)  # 按连续句号/问号拆分
    if len(parts) > 1:  # 有多个段落
        # 优先选择包含数据查询关键词的段落
        data_kw = ['查询', '计算', '多少', '哪些', '哪个', '涨跌', '行业', '股票', '基金']  # 数据查询标志词
        for part in reversed(parts):  # 从后往前找（后面的通常是有效问题）
            if any(kw in part for kw in data_kw):  # 包含数据查询关键词
                question = part.strip()  # 用这段作为问题
                break  # 找到了
    # 5. 压缩空白
    question = re.sub(r'\s+', ' ', question).strip()  # 合并多余空白
    return question[:500] if len(question) > 500 else question  # 截断



@app.route('/')  # 首页路由
def index():
    """返回前端交互页面"""
    return render_template('index.html')  # 渲染HTML模板


@app.route('/api/chat', methods=['POST'])  # 问答API接口
def api_chat():
    """接收用户问题，返回AI答案"""
    data = request.get_json()  # 解析JSON请求体
    if not data:  # 请求体为空
        return jsonify({"error": "请求体不能为空"}), 400  # 返回400错误
    question = data.get('question', '').strip()  # 提取问题文本
    if not question:  # 问题为空
        return jsonify({"error": "问题不能为空"}), 400  # 返回400错误
    # 清洗输入：去除JSON混入、重复粘贴、无关字符
    question = sanitize_question(question)  # 清洗问题文本
    if not question:  # 清洗后为空
        return jsonify({"error": "无法识别有效问题，请重新输入"}), 400  # 返回错误
    # 记录请求日志
    print(f"  📩 收到问题: {question[:100]}...")  # 打印问题前100字
    t0 = time.time()  # 计时开始
    answer = process_question(question)  # 处理问题
    elapsed = time.time() - t0  # 计算耗时
    print(f"  ✅ 回答完成 ({elapsed:.1f}s): {answer[:100]}...")  # 打印答案
    return jsonify({  # 返回JSON响应
        "answer": answer,  # 答案文本
        "elapsed": round(elapsed, 2)  # 耗时（秒）
    })


@app.route('/api/health')  # 健康检查接口
def api_health():
    """服务健康检查"""
    return jsonify({"status": "ok", "tables": len(DB_INFO['table_names'])})


# 应用入口

def run_batch_mode(questions_path, output_dir, resume=True):
    """批量模式: 处理question.jsonl所有题目，输出answer_result.jsonl"""
    from batch_runner import load_questions, run_batch

    logger.info(f"批量模式启动: {questions_path}")

    questions = load_questions(questions_path)
    logger.info(f"加载 {len(questions)} 道题目")

    # 初始化全局组件
    global SYSTEM_PROMPT, DB_INFO
    logger.info("[1/3] 探索数据库...")
    DB_INFO = explore_database(config.DB_PATH)
    for t in DB_INFO['table_names']:
        info = DB_INFO['all_info'][t]
        logger.info(f"  {t}: {info['row_count']:,} 行")

    logger.info("[2/3] 构建NL2SQL提示词...")
    SYSTEM_PROMPT = build_system_prompt(
        DB_INFO["schema_description"],
        DB_INFO["relationship_description"]
    )
    logger.info(f"提示词长度: {len(SYSTEM_PROMPT)} 字符")

    logger.info("[3/3] 开始批量处理...")

    def process_fn(question):
        return process_question(question)

    result = run_batch(questions, process_fn, logger, output_dir=output_dir, resume=resume)

    logger.info(f"批量处理完成: 成功{result['completed']}/{result['total']}题, 耗时{result['elapsed']/60:.1f}分钟")
    logger.info(f"输出文件: {result['output']}")
    return result


def main():
    """启动Flask Web服务 或 批量处理模式"""
    parser = argparse.ArgumentParser(description="基金数据智能问答系统")
    parser.add_argument("--batch", action="store_true", help="批量处理模式(处理question.jsonl)")
    parser.add_argument("--questions", default=None, help="题目文件路径")
    parser.add_argument("--output-dir", default=None, help="输出目录")
    parser.add_argument("--no-resume", action="store_true", help="从头开始(不续传)")
    parser.add_argument("--port", type=int, default=5000, help="Web服务端口")
    args = parser.parse_args()

    # 批量处理模式
    if args.batch:
        questions_path = args.questions or config.QUESTION_PATH
        output_dir = args.output_dir or os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(questions_path):
            questions_path = os.path.join(config.DATASET_DIR, "question.json")
        if not os.path.exists(questions_path):
            print(f"[ERROR] 题目文件不存在: {questions_path}")
            sys.exit(1)
        # 设置日志
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        setup_logging(level="INFO", log_file=os.path.join(log_dir, "fund_qa.log"))
        batch_logger = get_logger("fund_qa.batch")
        batch_logger.info("批量模式启动")
        run_batch_mode(questions_path, output_dir, resume=not args.no_resume)
        return

    # Web服务模式
    print(f"\n  服务就绪！请打开浏览器访问: http://127.0.0.1:{args.port}\n")
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)

if __name__ == "__main__":  # 如果直接运行
    main()  # 启动服务

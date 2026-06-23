# -*- coding: utf-8 -*-
"""
main.py — 基金数据问答Web应用（前后端交互）
功能：Flask后端 + DeepSeek NL2SQL引擎，浏览器输入问题即时回答
启动后访问 http://127.0.0.1:5000 进入交互界面
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""
import json, sqlite3, time, os, sys, re, threading, uuid  # 标准库
from flask import Flask, request, jsonify, render_template, send_file, url_for  # Flask Web框架
import config  # 配置文件
from logger import logger  # 统一日志
from db_explorer import explore_database, get_connection  # 数据库探索
from prompt_builder import build_system_prompt  # Prompt构建
from deepseek_client import call_deepseek_api, generate_sql, extract_sql_from_response  # API客户端
# 初始化Flask，模板目录设在 部署/templates/
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "部署", "templates")
if not os.path.isdir(_TEMPLATE_DIR):
    _TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "部署", "templates")
app = Flask(__name__, template_folder=_TEMPLATE_DIR)

# ============================================================
# 数字人模块导入（延迟导入，避免启动时加载模型）
# ============================================================
_digital_human_available = True  # 标记数字人模块是否可用
try:
    from digital_human import (
        DigitalHumanPipeline, DigitalHumanManager,
        create_pipeline, broadcast_answer,
    )
    _DH_MANAGER = DigitalHumanManager()  # 数字人配置管理器
    _DH_PIPELINE = None  # 延迟初始化流水线
    logger.info("数字人模块已加载")
except Exception as _dh_err:
    _digital_human_available = False
    _DH_MANAGER = None
    logger.warning(f"数字人模块加载失败: {_dh_err}")
# 全局初始化（服务启动时执行一次）
logger.info("=" * 55)
logger.info("基金数据智能问答系统 — 启动中...")
logger.info("=" * 55)

# 1. 加载数据库schema信息
logger.info("[1/3] 加载数据库Schema...")
DB_INFO = explore_database(config.DB_PATH)  # 探索10张表的结构
for t in DB_INFO['table_names']:  # 遍历表名
    info = DB_INFO['all_info'][t]  # 获取表信息
    logger.info(f"  {t}: {info['row_count']:,} 行")  # 打印表名和行数

# 2. 构建NL2SQL系统提示词（整个服务共享一个Prompt）
logger.info("[2/3] 构建NL2SQL Prompt...")
SYSTEM_PROMPT = build_system_prompt(  # 构建系统提示词
    DB_INFO["schema_description"],  # 10张表schema描述
    DB_INFO["relationship_description"]  # 表关系描述
)
logger.info(f"Prompt 长度: {len(SYSTEM_PROMPT)} 字符")

# 3. 建立数据库连接（线程本地存储，每个线程独立连接）
logger.info("[3/3] 初始化数据库连接...")
DB_CONN_LOCK = threading.Lock()  # 数据库连接锁，保证线程安全

logger.info(f"服务就绪！请打开浏览器访问: http://127.0.0.1:5000")


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
    """将SQL查询结果格式化为人类可读的答案字符串"""
    if not result:  # 结果为空
        return "未查询到相关数据"  # 无数据
    # 单行单列：直接返回值（最常见情形）
    if len(result) == 1 and len(columns) == 1:  # 单值
        value = result[0][columns[0]]  # 取唯一值
        if value is None:  # NULL值
            return "无数据"  # 无数据
        if isinstance(value, float) and value == int(value):  # 整数浮点数
            return str(int(value))  # 转整数
        return str(value)  # 返回字符串
    # 单行多列：列值用顿号连接
    if len(result) == 1:  # 单行
        parts = []  # 存储各列值
        for col in columns:  # 遍历列
            val = result[0][col]  # 取列值
            if val is None:  # NULL
                parts.append("无")  # 显示无
            elif isinstance(val, float) and val == int(val):  # 整数浮点数
                parts.append(str(int(val)))  # 转整数
            elif isinstance(val, float):  # 浮点数
                parts.append(str(round(val, 4)))  # 保留4位小数
            else:
                parts.append(str(val))  # 其他类型
        return "、".join(parts)  # 顿号连接
    # 多行结果：每行一行，最多显示20行
    lines = []  # 存储每行
    for row in result[:20]:  # 最多20行
        row_parts = []  # 单行各部分
        for col in columns:  # 遍历列
            val = row[col]  # 取列值
            if val is None:  # NULL
                val = "无"  # 显示无
            elif isinstance(val, float) and val == int(val):  # 整数浮点数
                val = int(val)  # 转整数
            elif isinstance(val, float):  # 浮点数
                val = round(val, 4)  # 保留4位
            row_parts.append(str(val))  # 添加到行
        lines.append("、".join(row_parts))  # 顿号连接
    if len(result) > 20:  # 超过20行
        lines.append(f"...（共{len(result)}条，仅显示前20条）")  # 截断提示
    return "\n".join(lines)  # 换行连接


def search_pdf_texts(question, pdf_dir, max_files=3):
    """在PDF解析TXT文件中定位关键词出现位置，提取周围相关段落（而非死板的文件开头）"""
    pdf_texts = []  # 搜索结果
    stop_chars = r'[的了是而在如何什么哪该请帮我查询计算一下\.\?\？\。\，\、\s]+'  # 虚词标点
    keywords = [kw.strip() for kw in re.split(stop_chars, question) if len(kw.strip()) >= 2]  # 拆分后取>=2
    if len(keywords) <= 1:  # 拆分效果不好
        keywords = [kw for kw in re.findall(r'[一-龥a-zA-Z0-9]{2,}', question) if len(kw) >= 3]  # 降级方案
    company_names = [kw for kw in keywords if len(kw) >= 4]  # >=4字的词作为公司名
    txt_files = [f for f in os.listdir(pdf_dir) if f.endswith('.txt')]  # 所有TXT文件
    for txt_file in txt_files:  # 遍历每个文件
        try:
            filepath = os.path.join(pdf_dir, txt_file)  # 拼接路径
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:  # 打开文件
                content = f.read()  # 读取全部文本
            company_hit = any(name in content for name in company_names)  # 检查公司名命中
            kw_hits = sum(1 for kw in keywords if kw in content)  # 关键词命中计数
            if not company_hit and kw_hits < 2:  # 不相关文件
                continue  # 跳过
            chunks = []  # 存储文本块
            for kw in keywords[:5]:  # 用前5个关键词定位
                pos = content.find(kw)  # 找到关键词位置
                if pos >= 0:  # 命中
                    start, end = max(0, pos-400), min(len(content), pos+1200)  # 前后窗口
                    chunks.append(content[start:end])  # 截取上下文
            if chunks:  # 有找到的文本块
                snippet = "\n...\n".join(chunks[:3])  # 取前3块
                score = kw_hits + (10 if company_hit else 0)  # 计分
                pdf_texts.append({"file": txt_file, "score": score, "snippet": snippet[:3000]})  # 保存
        except Exception:  # 读取失败
            continue  # 跳过
    pdf_texts.sort(key=lambda x: x["score"], reverse=True)  # 按得分排序
    return pdf_texts[:max_files]  # 返回top N


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
                logger.warning(f"SQL修正(第{attempt+1}次): {error_msg[:100]}")
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
    logger.info(f"收到问题: {question[:100]}...")
    t0 = time.time()  # 计时开始
    answer = process_question(question)  # 处理问题
    elapsed = time.time() - t0  # 计算耗时
    logger.info(f"回答完成 ({elapsed:.1f}s): {answer[:100]}...")
    return jsonify({  # 返回JSON响应
        "answer": answer,  # 答案文本
        "elapsed": round(elapsed, 2)  # 耗时（秒）
    })


@app.route('/api/health')  # 健康检查接口
def api_health():
    """服务健康检查"""
    return jsonify({"status": "ok", "tables": len(DB_INFO['table_names'])})


# ============================================================
# 数字人 API 路由
# ============================================================

# 输出文件目录（存放生成的视频/音频）
_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(_OUTPUT_DIR, exist_ok=True)

# 上传头像目录
_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)


def _get_dh_pipeline():
    """获取或初始化数字人流水线（延迟加载）"""
    global _DH_PIPELINE
    if not _digital_human_available:
        return None
    if _DH_PIPELINE is None:
        _DH_PIPELINE = _DH_MANAGER.get_pipeline()
    return _DH_PIPELINE


@app.route('/api/digital-human/broadcast', methods=['POST'])
def api_digital_human_broadcast():
    """
    数字人播报接口
    接收答案文本，返回数字人说话视频

    请求: {"text": "播报文本", "avatar": "头像路径(可选)", "voice": "发音人(可选)"}
    响应: {"success": true, "video_url": "/output/xxx.mp4", "audio_url": "...", "elapsed": 2.5}
    """
    if not _digital_human_available:
        return jsonify({"success": False, "error": "数字人模块未加载，请检查依赖"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "播报文本不能为空"}), 400

    # 截断过长文本
    if len(text) > 800:
        text = text[:800] + "，以上为主要信息。"
    # 获取可选参数
    avatar = data.get("avatar") or _DH_MANAGER.get_avatar()
    voice = data.get("voice") or _DH_MANAGER.get_voice()

    # 如果头像路径相对，转绝对路径
    if avatar and not os.path.isabs(avatar):
        avatar = os.path.join(_UPLOAD_DIR, avatar)
    if not avatar or not os.path.exists(avatar):
        avatar = None  # 让 pipeline 使用 simple 模式

    logger.info(f"数字人播报: {text[:60]}...")

    # 创建临时流水线（支持覆盖语音）
    try:
        from digital_human import DigitalHumanPipeline
        pipeline = DigitalHumanPipeline(
            avatar_image=avatar,
            tts_voice=voice,
            talking_head_engine=_DH_MANAGER.config.get("engine", "sadtalker"),
            output_dir=_OUTPUT_DIR,
        )
    except Exception:
        pipeline = _get_dh_pipeline()

    if pipeline is None:
        return jsonify({"success": False, "error": "数字人流水线初始化失败"}), 500

    # 执行播报
    output_name = f"dh_{int(time.time()*1000)}"
    t0 = time.time()

    try:
        result = pipeline.broadcast(
            answer_text=text,
            output_name=output_name,
            return_video=True,
            return_audio=True,
        )

        elapsed = time.time() - t0

        # 构建响应
        response = {
            "success": result.get("success", False),
            "elapsed": round(elapsed, 2),
            "engine": result.get("engine", "unknown"),
        }

        if result.get("video_path"):
            video_name = os.path.basename(result["video_path"])
            response["video_url"] = f"/output/{video_name}"

        if result.get("audio_path"):
            audio_name = os.path.basename(result["audio_path"])
            response["audio_url"] = f"/output/{audio_name}"

        if result.get("error"):
            response["error"] = result["error"]

        return jsonify(response)

    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"数字人播报失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "elapsed": round(elapsed, 2),
        }), 500


@app.route('/api/digital-human/tts-only', methods=['POST'])
def api_tts_only():
    """
    仅 TTS 语音合成接口（不生成视频，快速返回音频）
    适用于只需要语音播报、不需要视频的场景

    请求: {"text": "要合成的文本", "voice": "发音人(可选)"}
    响应: {"success": true, "audio_url": "/output/xxx.mp3", "elapsed": 1.2}
    """
    if not _digital_human_available:
        return jsonify({"success": False, "error": "TTS 模块不可用"}), 503

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400

    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "文本不能为空"}), 400

    voice = data.get("voice") or _DH_MANAGER.get_voice()

    logger.info(f"TTS 合成: {text[:60]}...")
    t0 = time.time()

    try:
        from tts_engine import get_tts_engine
        tts = get_tts_engine("edge", voice=voice)

        output_name = f"tts_{int(time.time()*1000)}.mp3"
        output_path = os.path.join(_OUTPUT_DIR, output_name)
        tts.synthesize(text, output_path)

        elapsed = time.time() - t0

        return jsonify({
            "success": True,
            "audio_url": f"/output/{output_name}",
            "elapsed": round(elapsed, 2),
            "voice": voice,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"TTS 失败: {str(e)}",
            "elapsed": round(time.time() - t0, 2),
        }), 500


@app.route('/api/digital-human/config', methods=['GET', 'POST'])
def api_digital_human_config():
    """
    数字人配置管理

    GET:  获取当前配置
    POST: 更新配置 {"avatar": "...", "voice": "...", "engine": "..."}
    """
    if not _digital_human_available:
        return jsonify({"error": "数字人模块不可用"}), 503

    if request.method == 'GET':
        return jsonify({
            "avatar": _DH_MANAGER.get_avatar(),
            "voice": _DH_MANAGER.get_voice(),
            "engine": _DH_MANAGER.config.get("engine", "sadtalker"),
            "available": _digital_human_available,
            "voices": [
                {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓(女)", "style": "活泼自然"},
                {"id": "zh-CN-YunxiNeural", "name": "云希(男)", "style": "新闻播报"},
                {"id": "zh-CN-YunjianNeural", "name": "云健(男)", "style": "沉稳专业"},
                {"id": "zh-CN-XiaoyiNeural", "name": "晓伊(女)", "style": "温柔亲切"},
                {"id": "zh-CN-YunyangNeural", "name": "云扬(男)", "style": "新闻播音"},
                {"id": "zh-CN-XiaochenNeural", "name": "晓晨(女)", "style": "自然对话"},
            ],
        })

    # POST: 更新配置
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    if "voice" in data:
        _DH_MANAGER.set_voice(data["voice"])
    if "engine" in data:
        _DH_MANAGER.config["engine"] = data["engine"]
        _DH_MANAGER._save_config()
        global _DH_PIPELINE
        _DH_PIPELINE = None  # 重置 pipeline 以应用新引擎

    return jsonify({
        "success": True,
        "avatar": _DH_MANAGER.get_avatar(),
        "voice": _DH_MANAGER.get_voice(),
        "engine": _DH_MANAGER.config.get("engine", "sadtalker"),
    })


@app.route('/api/digital-human/upload-avatar', methods=['POST'])
def api_upload_avatar():
    """
    上传数字人头像

    请求: multipart/form-data, field: "avatar" (图片文件)
    响应: {"success": true, "avatar_url": "/uploads/xxx.jpg"}
    """
    if 'avatar' not in request.files:
        return jsonify({"success": False, "error": "未找到头像文件"}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"success": False, "error": "文件名为空"}), 400

    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"avatar_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(_UPLOAD_DIR, filename)
    file.save(filepath)

    # 设置为当前头像
    _DH_MANAGER.set_avatar(filepath)

    logger.info(f"头像已上传: {filename}")

    return jsonify({
        "success": True,
        "avatar_url": f"/uploads/{filename}",
        "filename": filename,
    })


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """提供上传文件的访问"""
    return send_file(os.path.join(_UPLOAD_DIR, filename))


@app.route('/output/<path:filename>')
def serve_output(filename):
    """提供生成的视频/音频文件访问"""
    filepath = os.path.join(_OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    return send_file(filepath)


# 应用入口

def main():
    """启动Flask Web服务"""
    logger.info("=" * 55)
    logger.info("基金数字人智能问答系统 — 就绪")
    logger.info("=" * 55)
    logger.info(f"前端页面:    http://127.0.0.1:5000")
    logger.info(f"NL2SQL问答:   http://127.0.0.1:5000/api/chat")
    logger.info(f"数字人播报:    http://127.0.0.1:5000/api/digital-human/broadcast")
    logger.info(f"TTS语音合成:  http://127.0.0.1:5000/api/digital-human/tts-only")
    logger.info(f"数字人配置:    http://127.0.0.1:5000/api/digital-human/config")
    logger.info("按 Ctrl+C 停止服务")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)  # 启动Flask

if __name__ == "__main__":  # 如果直接运行
    main()  # 启动服务

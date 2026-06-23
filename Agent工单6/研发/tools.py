# -*- coding: utf-8 -*-
"""
tools.py — Agent工具集（统一调用接口）
记账本→对话式NL2SQL(识别"我",自然语言回复) | 日程→NL2SQL
文生图→Qwen | 基金→DB直查 | 招股书→关键词RAG
工单编号：人工智能NLP-Agent数字人项目-智能体任务
"""

import json, time, sqlite3, os, sys, logging, requests, re  # 标准库
from datetime import datetime  # 日期
import config  # Agent配置

logger = logging.getLogger("agent.tools")  # 日志器


def _call_deepseek(messages, max_tokens=2048):
    """调用DeepSeek API（兼容推理模型：提取reasoning_content兜底）"""
    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": config.DEEPSEEK_MODEL, "messages": messages, "temperature": 0.0,
               "max_tokens": max_tokens, "stream": False}
    last_error = None
    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=config.API_TIMEOUT)
            if r.status_code == 200:
                body = r.json()
                msg = body["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                # 推理模型兜底：content为空时从reasoning_content提取
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        logger.warning("推理模型content为空，使用reasoning_content(%d字)", len(reasoning))
                        # 尝试从推理内容中提取最终答案（通常在最后一段）
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()
                if content:
                    return content
                # content和reasoning都为空，可能是max_tokens不够
                finish = body["choices"][0].get("finish_reason", "")
                logger.warning("DeepSeek返回空content (finish_reason=%s, max_tokens=%d)，重试中...",
                             finish, max_tokens)
                # 用更大max_tokens重试
                payload["max_tokens"] = max(max_tokens * 2, 4096)
            else:
                last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                logger.warning("DeepSeek API错误(尝试%d): %s", attempt + 1, last_error)
        except Exception as e:
            last_error = str(e)[:200]
            logger.warning("DeepSeek请求异常(尝试%d): %s", attempt + 1, last_error)
        time.sleep((attempt + 1) * 2)
    logger.error("DeepSeek最终失败: %s", last_error or "未知")
    return None


def _clean_sql(text):
    """清理SQL：去markdown标记、注释"""
    if not text: return ""  # 空
    text = text.strip()  # 去空白
    for m in ["```sql", "```SQL", "```"]:  # markdown
        if text.startswith(m): text = text[len(m):].strip()  # 开头
        if text.endswith("```"): text = text[:-3].strip()  # 结尾
    return "\n".join([l for l in text.split("\n") if not l.strip().startswith("--")]).strip()  # 去注释


def _resolve_data_path(relative_path, env_var=None):
    """跨平台解析数据路径

    依次尝试：环境变量 > WSL路径 > Windows路径 > 用户home目录
    relative_path: 相对于bs_challenge_financial_14b_dataset的相对路径
    env_var: 可选的环境变量名，用于手动指定数据根目录
    """
    from pathlib import Path
    # 0. 环境变量覆盖
    if env_var and os.environ.get(env_var):
        p = Path(os.environ[env_var]) / relative_path
        if p.exists(): return str(p)
    # 候选数据根目录
    candidates = [
        Path("/mnt/c/Users/31326/bs_challenge_financial_14b_dataset"),
        Path("C:/Users/31326/bs_challenge_financial_14b_dataset"),
        Path.home() / "bs_challenge_financial_14b_dataset",
    ]
    for base in candidates:
        p = base / relative_path
        if p.exists():
            return str(p)
    return None


# ============================================================
# 工具01: 记账本 — 对话式（理解"我",自然语言回复）
# ============================================================
def tool_ledger(query):
    """记账本：DeepSeek解析意图→执行SQL→自然语言回复"""
    logger.info("📒 记账: %s", query[:60])
    try:
        # 初始化DB（不存在则本地创建）
        local_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "money_notes.db")
        db_path = config.LEDGER_DB if os.path.exists(config.LEDGER_DB) else local_db
        conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; c = conn.cursor()
        # 确保表存在
        c.execute("""CREATE TABLE IF NOT EXISTS money_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT NOT NULL,
            member TEXT NOT NULL,
            action_type TEXT NOT NULL,
            category TEXT NOT NULL,
            item_name TEXT NOT NULL,
            amount REAL NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
        # 获取全部数据
        c.execute("SELECT * FROM money_notes WHERE enabled=1 ORDER BY record_date, id")
        rows = c.fetchall()
        cols = [d[0] for d in c.description] if c.description else []
        data_str = "\n".join([" | ".join(f"{c}={r[c]}" for c in cols) for r in rows])
        today = datetime.now().strftime("%Y-%m-%d")
        now_cn = datetime.now().strftime("%Y年%m月%d日")
        month_start = today[:7] + "-01"

        # 构建带SQL示例的清晰prompt（引导模型输出正确格式）
        prompt = f"""你是家庭记账助手。操作SQLite数据库 money_notes。

## 表结构（严格按此！）
CREATE TABLE money_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT NOT NULL,   -- 格式 YYYY-MM-DD
    member TEXT NOT NULL,        -- 爸爸/妈妈/女儿
    action_type TEXT NOT NULL,   -- 支出 或 收入
    category TEXT NOT NULL,      -- 买书/买菜/购物/餐饮/交通/报销/工资/娱乐/其他
    item_name TEXT NOT NULL,     -- 具体物品或事项名称
    amount REAL NOT NULL,        -- 金额，纯数字不含单位
    enabled INTEGER DEFAULT 1    -- 1=有效 0=已删除
);

## SQL 示例（照此格式写！）
-- 记账：今天买书花了50元（"我"=用户本人）→
INSERT INTO money_notes (record_date, member, action_type, category, item_name, amount, enabled) VALUES ('{today}', '我', '支出', '买书', '三体', 50, 1);
-- 记账：7月5日妈妈收到报销1000元 →
INSERT INTO money_notes (record_date, member, action_type, category, item_name, amount, enabled) VALUES ('{today[:5]}07-05', '妈妈', '收入', '报销', '报销款', 1000, 1);
-- 记账：今天女儿买了双登山鞋499元 →
INSERT INTO money_notes (record_date, member, action_type, category, item_name, amount, enabled) VALUES ('{today}', '女儿', '支出', '购物', '登山鞋', 499, 1);
-- 查某人总消费：女儿花了多少钱 →
SELECT COALESCE(SUM(amount), 0) AS total FROM money_notes WHERE enabled=1 AND member='女儿' AND action_type='支出';
-- 查本月某人：这个月女儿花了多少钱 →
SELECT COALESCE(SUM(amount), 0) AS total FROM money_notes WHERE enabled=1 AND member='女儿' AND action_type='支出' AND record_date>='{month_start}';
-- 查本月明细：这个月花钱明细 →
SELECT * FROM money_notes WHERE enabled=1 AND action_type='支出' AND record_date>='{month_start}' ORDER BY record_date;
-- 查某物购买日期：我哪天买的三体 →
SELECT * FROM money_notes WHERE enabled=1 AND item_name LIKE '%三体%' ORDER BY record_date;
-- 删账：删除第3条记录 →
UPDATE money_notes SET enabled=0 WHERE id=3;

## 当前数据库内容
{data_str[:3000] if data_str else '(空)'}

## 规则
- 今天是{now_cn}({today})，本月从{month_start}开始
- "我"就是 member='我'，不要替换成其他名字
- 记账用INSERT，查账用SELECT，删账用UPDATE SET enabled=0
- 回复要口语化友好，查账时总结数据给结论
- INSERT必须包含全部6个字段：record_date, member, action_type, category, item_name, amount, enabled

## 用户: {query}

输出一个JSON对象（以{{开头，}}结尾，不要markdown包裹，不要注释）:
{{"sql":"完整SQL语句","reply":"友好回复"}}
{{"""
        raw = _call_deepseek([{"role": "user", "content": prompt}], max_tokens=1024)
        if not raw:
            conn.close(); return {"success": False, "result": "AI服务暂不可用，请稍后重试", "tool": "记账本"}

        # 解析JSON — 更鲁棒的提取
        sql, reply = "", ""
        json_str = raw.strip()
        # 去掉markdown代码块包裹
        for tag in ["```json", "```sql", "```"]:
            if tag in json_str:
                parts = json_str.split(tag)
                if len(parts) >= 2:
                    json_str = parts[1].split("```")[0] if "```" in parts[1] else parts[1]
                    break
        # 定位JSON对象的花括号
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start >= 0 and end > start:
            json_str = json_str[start:end+1]
        try:
            parsed = json.loads(json_str)
            sql = (parsed.get("sql", "") or "").strip()
            reply = (parsed.get("reply", "") or "").strip()
            logger.info("记账JSON解析成功 | SQL=%s", sql[:80])
        except json.JSONDecodeError:
            logger.warning("JSON解析失败: %s", raw[:150])
            # 降级提取SQL — 找SQL关键字开始的完整语句
            for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
                idx = raw.upper().find(kw)
                if idx >= 0:
                    tail = raw[idx:]
                    # 取到分号、换行或下一个JSON键
                    for delim in [';', '\n', '",', '"}"']:
                        end_idx = tail.find(delim)
                        if end_idx > 0:
                            sql = tail[:end_idx].strip()
                            break
                    if not sql:
                        sql = tail.strip()
                    break
            # 尝试提取reply字段
            if not reply:
                m = re.search(r'"reply"\s*:\s*"([^"]*)"', raw)
                if m: reply = m.group(1)

        # SQL校验
        if sql:
            sql_upper = sql.upper().strip()
            # 检查是否引用了正确的表
            if "money_notes" not in sql.lower():
                logger.warning("SQL未引用money_notes表，丢弃: %s", sql[:100])
                sql = ""
            # INSERT必须有VALUES
            elif sql_upper.startswith("INSERT") and "VALUES" not in sql_upper:
                logger.warning("INSERT缺少VALUES，丢弃: %s", sql[:100])
                sql = ""

        if sql:
            try:
                c.execute(sql)
                if sql.upper().startswith("SELECT"):
                    rrows = c.fetchall()
                    if rrows:
                        if not reply:
                            d2 = "\n".join([" | ".join(str(r[c]) for c in cols) for r in rrows[:20]])
                            fp = f"根据查询结果用一句话友好回复:\n{d2}\n\n问题:{query}\n回复:"
                            reply = _call_deepseek([{"role": "user", "content": fp}], max_tokens=256) or str(rrows[:3])
                        result = reply
                    else:
                        result = "未查询到相关记录，可能还没有这笔账哦~"
                else:
                    conn.commit()
                    result = reply or "操作成功"
                logger.info("记账SQL执行成功: %s", sql[:100])
            except Exception as e:
                logger.warning("记账SQL执行失败(%s)，尝试修正...", str(e)[:60])
                # 带错误信息重试一次
                fp2 = f"SQL执行错误: {e}\n原SQL: {sql}\n表: money_notes(id,record_date,member,action_type,category,item_name,amount,enabled)\n今天:{today}\n修正后输出JSON: {{\"sql\":\"...\",\"reply\":\"...\"}}"
                r3 = _call_deepseek([{"role": "user", "content": fp2}], max_tokens=512)
                if r3:
                    try:
                        js = r3.strip()
                        for t in ["```json", "```"]:
                            if t in js: js = js.split(t)[1].split("```")[0]
                        s = js.find('{'); e = js.rfind('}')
                        if s >= 0 and e > s: js = js[s:e+1]
                        p2 = json.loads(js)
                        sql2 = (p2.get("sql", "") or "").strip()
                        if sql2 and "money_notes" in sql2.lower():
                            c.execute(sql2)
                            if not sql2.upper().startswith("SELECT"): conn.commit()
                            result = p2.get("reply", "操作成功")
                        else:
                            result = f"操作失败: {str(e)[:80]}"
                    except:
                        result = f"操作失败: {str(e)[:80]}"
                else:
                    result = f"操作失败: {str(e)[:80]}"
        else:
            # SQL无效时用AI兜底
            if not reply:
                fp_fallback = f"用户问: {query}\n数据:\n{data_str[:2000]}\n请直接自然语言回答(不要SQL):"
                reply = _call_deepseek([{"role": "user", "content": fp_fallback}], max_tokens=256)
            result = reply or "抱歉，没能理解您的需求，请换个说法试试～"

        conn.close()
        return {"success": True, "result": result, "tool": "记账本"}
    except Exception as e:
        logger.error("记账错误: %s", e)
        return {"success": False, "result": f"记账失败: {str(e)[:150]}", "tool": "记账本"}

def _init_schedule_db(db_path):
    """初始化日程数据库（不存在则创建）"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_date TEXT,
        schedule_time TEXT NOT NULL,
        content TEXT NOT NULL,
        repeat_rule TEXT DEFAULT 'none',
        repeat_detail TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        last_reminded TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    return conn


def _build_schedule_reply(rows, today_str):
    """构建日程回复——清单格式，按时间排列"""
    if not rows:
        return None
    lines = []
    for i, r in enumerate(rows, 1):
        t = r['schedule_time']
        c = r['content']
        try:
            rpt = r['repeat_rule'] if 'repeat_rule' in r.keys() else 'none'
        except Exception:
            rpt = 'none'
        tag = f" 🔁每日" if rpt == 'daily' else ""
        lines.append(f"{i}. {t} {c}{tag}")
    return f"📅 **{today_str}**\n\n您今天的日程安排如下：\n\n" + "\n".join(lines)


def tool_schedule(query):
    """日程提醒：智能解析自然语言→SQL查询→清单回复"""
    logger.info("📅 日程: %s", query[:60])
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        now_cn = datetime.now().strftime("%Y年%m月%d日")
        today_cn = datetime.now().strftime("%m月%d日")

        # 初始化DB（不存在则自动创建）
        local_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_notes.db")
        db_path = config.SCHEDULE_DB if os.path.exists(config.SCHEDULE_DB) else local_db
        conn = _init_schedule_db(db_path)
        c = conn.cursor()

        # 关键字判断意图：添加/查询/删除
        is_query = any(kw in query for kw in ['有哪些', '查看', '查询', '今天', '日程', '什么日程', '我的日程'])
        is_add = any(kw in query for kw in ['添加', '新增', '记录', '安排', '提醒我', '提醒', '新建'])
        is_delete = any(kw in query for kw in ['删除', '取消', '移除', '去掉'])

        if is_add:
            # === 添加日程：LLM提取时间+内容 ===
            prompt = f"""你是日程助手。从用户输入提取日程信息。今天是{now_cn}。
用户: {query}
输出JSON: {{"date":"YYYY-MM-DD或null","time":"HH:MM","content":"日程内容","repeat":"none/daily/weekly/monthly"}}
只输出JSON:"""
            raw = _call_deepseek([{"role": "user", "content": prompt}], max_tokens=300)
            dt, tm, content, rpt = today, "09:00", query, "none"
            if raw:
                try:
                    r2 = raw.strip()
                    if r2.startswith("```"): r2 = r2.split("```")[1].replace("json","",1)
                    p = json.loads(r2)
                    dt = p.get("date", today) or today
                    tm = p.get("time", "09:00")
                    content = p.get("content", query)
                    rpt = p.get("repeat", "none")
                except: pass
            c.execute("INSERT INTO schedules(schedule_date,schedule_time,content,repeat_rule) VALUES(?,?,?,?)",
                      (dt, tm, content, rpt))
            conn.commit()
            rid = c.lastrowid
            result = f"✅ **已添加日程**\n\n📌 {content}\n⏰ {dt} {tm}\n🔢 编号: {rid}"
            conn.close()
            return {"success": True, "result": result, "tool": "日程提醒"}

        if is_delete:
            # === 删除日程：提取编号 ===
            import re as _re
            ids = _re.findall(r'\d+', query)
            rid = int(ids[0]) if ids else None
            if rid:
                c.execute("SELECT * FROM schedules WHERE id=?", (rid,))
                target = c.fetchone()
                if target:
                    c.execute("UPDATE schedules SET enabled=0 WHERE id=?", (rid,))
                    conn.commit()
                    result = f"✅ **已删除日程**\n\n编号{rid}: {target['schedule_time']} {target['content']}"
                else:
                    result = f"未找到编号为{rid}的日程"
            else:
                result = "请提供要删除的日程编号（如：删除日程1）"
            conn.close()
            return {"success": True, "result": result, "tool": "日程提醒"}

        # === 查询日程 ===
        c.execute("SELECT * FROM schedules WHERE enabled=1 AND schedule_date=? ORDER BY schedule_time", (today,))
        today_rows = c.fetchall()

        if today_rows:
            reply = _build_schedule_reply(today_rows, today_cn)
        else:
            # 查所有未过期的
            c.execute("SELECT * FROM schedules WHERE enabled=1 AND schedule_date>=? ORDER BY schedule_date, schedule_time LIMIT 10", (today,))
            all_rows = c.fetchall()
            if all_rows:
                reply = f"📅 今天暂无日程。\n\n最近的日程安排：\n\n"
                for i, r in enumerate(all_rows, 1):
                    reply += f"{i}. {r['schedule_date']} {r['schedule_time']} {r['content']}\n"
            else:
                reply = f"📅 您目前没有任何日程安排。\n\n💡 试试说：\n• \"下午3点开会\"\n• \"每天早上8点提醒我运动\"\n• \"查看我的日程\""

        conn.close()
        return {"success": True, "result": reply, "tool": "日程提醒"}

    except Exception as e:
        logger.error("日程错误: %s", e)
        return {"success": False, "result": f"日程操作失败: {str(e)[:150]}", "tool": "日程提醒"}


def tool_text2image(query, image_base64=None):
    """文生图/人脸旋转：使用DashScope图像编辑API真正实现图片生成和人脸旋转"""
    logger.info("🎨 文生图: %s (图片=%s)", query[:60], "有" if image_base64 else "无")
    try:
        import dashscope
        from dashscope import MultiModalConversation

        if image_base64:
            # ===== 人脸旋转：使用 dashscope 图像编辑 API =====
            # 解析用户意图：左转/右转/其他
            intent_prompt = f"用户要求: {query}\n判断: 1=左转脸 2=右转脸 3=其他。只输出数字:"
            intent = _call_deepseek([{"role": "user", "content": intent_prompt}], max_tokens=10)
            intent_num = int(intent.strip()) if intent and intent.strip().isdigit() else 3

            if intent_num == 1:
                edit_prompt = "将这个人物的头部向左旋转约30度，保持面部特征和身份不变，保持背景和服装不变"
                direction = "左转30°"
            elif intent_num == 2:
                edit_prompt = "将这个人物的头部向右旋转约30度，保持面部特征和身份不变，保持背景和服装不变"
                direction = "右转30°"
            else:
                edit_prompt = query.strip()[:500]
                direction = "图像编辑"

            logger.info("🎯 人脸%s: prompt=%s", direction, edit_prompt[:60])

            # 调用 dashscope MultiModalConversation 进行真正的图像编辑
            image_url = f"data:image/png;base64,{image_base64}"
            messages = [{
                "role": "user",
                "content": [
                    {"image": image_url},
                    {"text": edit_prompt}
                ]
            }]

            response = MultiModalConversation.call(
                model="qwen-image-edit-max",
                messages=messages,
                api_key=config.QWEN_API_KEY,
                result_format="message",
            )

            if response.status_code == 200:
                output = response.output
                if output and hasattr(output, 'choices') and output.choices:
                    choice = output.choices[0]
                    msg = choice.message
                    result_images = []
                    # 提取返回的图片
                    if hasattr(msg, 'content') and msg.content:
                        for item in msg.content:
                            if isinstance(item, dict):
                                if 'image' in item:
                                    result_images.append(item['image'])
                                elif 'data' in item and 'image' in str(type(item)):
                                    result_images.append(item['data'])
                    if result_images:
                        result = f"✅ 人脸{direction}处理完成！"
                        return {"success": True, "result": result, "tool": "文生图",
                                "images": result_images}
                    elif hasattr(msg, 'content') and isinstance(msg.content, str) and msg.content.strip():
                        result = f"🔄 人脸{direction}处理结果:\n{msg.content[:500]}"
                        return {"success": True, "result": result, "tool": "文生图"}
                # 回退：尝试从response中直接提取图片URL
                output_dict = response.output if isinstance(response.output, dict) else {}
                if 'choices' in output_dict:
                    for c in output_dict.get('choices', []):
                        if 'message' in c and 'content' in c['message']:
                            for item in c['message']['content']:
                                if isinstance(item, dict) and 'image' in item:
                                    result = f"✅ 人脸{direction}处理完成！"
                                    return {"success": True, "result": result, "tool": "文生图",
                                            "images": [item['image']]}

            # API调用失败，给友好提示
            logger.warning("图像编辑API返回: %s", response.status_code if hasattr(response, 'status_code') else 'unknown')
            result = (
                f"⚠️ 人脸{direction}处理未能完成。\n\n"
                f"可能原因：\n"
                f"1. DashScope API密钥配置问题\n"
                f"2. 图像编辑模型(qwen-image-edit-max)不可用\n"
                f"3. 图片格式不支持\n\n"
                f"建议：检查config.py中的QWEN_API_KEY是否正确配置。"
            )
            return {"success": True, "result": result, "tool": "文生图"}

        # ===== 纯文本→文生图 =====
        # 提取图像prompt
        prompt = f"从以下中文描述提取精确的英文图像生成prompt（含风格、分辨率、构图细节）:\n{query}\n只输出英文prompt:"
        image_prompt = _call_deepseek([{"role": "user", "content": prompt}], max_tokens=200)
        if not image_prompt:
            return {"success": False, "result": "图像描述提取失败，请更具体地描述您想要的图片", "tool": "文生图"}

        logger.info("🖼️ 图像prompt: %s", image_prompt[:80])

        # 使用 dashscope 图像生成
        messages = [{
            "role": "user",
            "content": [{"text": image_prompt.strip()}]
        }]

        response = MultiModalConversation.call(
            model="qwen-image-edit-max",
            messages=messages,
            api_key=config.QWEN_API_KEY,
            result_format="message",
        )

        if response.status_code == 200:
            output = response.output
            result_images = []
            if output and hasattr(output, 'choices') and output.choices:
                msg = output.choices[0].message
                if hasattr(msg, 'content') and msg.content:
                    for item in msg.content:
                        if isinstance(item, dict) and 'image' in item:
                            result_images.append(item['image'])
            if result_images:
                return {"success": True, "result": f"✅ 已根据描述生成图片:\n{image_prompt[:100]}",
                        "tool": "文生图", "images": result_images}

        # 回退：用DeepSeek生成详细描述
        fallback = _call_deepseek([{"role": "user", "content": f"详细描述这张图片的内容(100-200字): {image_prompt}"}], max_tokens=300)
        result = f"🎨 图像prompt已生成:\n{image_prompt}\n\n📝 图片描述:\n{fallback or '生成中...'}\n\n💡 提示：实际图片生成需要DashScope图像API配额。"
        return {"success": True, "result": result, "tool": "文生图"}
    except Exception as e:
        logger.error("文生图错误: %s", e)
        return {"success": False, "result": f"文生图失败: {str(e)[:200]}", "tool": "文生图"}


def _format_fund_answer(query, rows, cols):
    """将SQL查询结果格式化为自然语言答案（带AI润色+兜底模板）"""
    if not rows:
        return "未查询到相关数据，请检查基金名称、日期或筛选条件是否正确。"
    data = "\n".join([" | ".join(str(r[c]) for c in cols) for r in rows])
    # 尝试AI润色
    fp = f"""根据以下查询结果，用自然流畅的中文回答用户问题。要求：
1. 完整复现所有查询结果，不要遗漏任何数据
2. 保持数据精度（小数位数）不变
3. 如果用户问的是"前N大"，请用编号逐条列出
4. 百分数保留两位小数，带%符号
5. 回答2-5句话，信息要完整

查询结果:
{data}

用户问题: {query}

请直接回答（不要markdown标记）:"""
    ai_answer = _call_deepseek([{"role": "user", "content": fp}], max_tokens=2048)
    if ai_answer and len(ai_answer.strip()) >= 10:
        return ai_answer.strip()
    # AI失败 → 模板兜底
    logger.warning("AI润色失败(len=%d)，使用模板兜底", len(ai_answer or ""))
    col_names = [str(c) for c in cols]
    lines = [f"根据查询结果，"]
    for i, row in enumerate(rows, 1):
        vals = []
        for c in cols:
            val = row[c]
            # 百分比类数值 → 格式化
            if isinstance(val, float):
                if '占比' in str(c) or '率' in str(c) or '比' in str(c):
                    vals.append(f"{val * 100:.2f}%")
                else:
                    vals.append(f"{val:.2f}" if val != int(val) else str(int(val)))
            else:
                vals.append(str(val))
        lines.append(f"第{i}项: {' | '.join(vals)}")
    if len(rows) > 1:
        lines.append(f"以上共{len(rows)}条记录。")
    return "\n".join(lines)


def tool_fund_qa(query):
    """基金问答：NL2SQL→查DB→自然语言回答（含完整兜底）"""
    logger.info("📊 基金: %s", query[:60])
    try:
        db_path = _resolve_data_path("dataset/博金杯比赛数据.db", env_var="FUND_DB_DIR")
        if not db_path:
            return {"success": False, "result": "基金数据库未找到(需下载bs_challenge_financial_14b_dataset或设置FUND_DB_DIR)", "tool": "基金问答"}
        conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; c = conn.cursor()
        # 获取表结构
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'idx_%'")
        tables = [r[0] for r in c.fetchall()]
        schema_str = ""
        for t in tables:
            c.execute(f"PRAGMA table_info('{t}')")
            cols = [f"{r['name']}({r['type']})" for r in c.fetchall()]
            c.execute(f"SELECT COUNT(*) FROM '{t}'"); cnt = c.fetchone()[0]
            schema_str += f"表:{t}({cnt}行) 列:{', '.join(cols)}\n"
        # 构建SQL生成prompt
        prompt = f"""你是基金数据库SQL专家。根据以下schema生成SQLite查询。

## 全部表结构（列名必须原样使用！带括号的列名必须保留）
{schema_str[:3500]}

## SQL示例（严格参照！）

### 1.基金债券/股票持仓查询
-- 某基金在某日季报的前N大持仓债券：
SELECT b."债券名称", ROUND(b."持债市值占基金资产净值比" * 100, 2) AS "持仓占比(%)"
FROM "基金债券持仓明细" b
JOIN "基金基本信息" f ON b."基金代码" = f."基金代码"
WHERE f."基金简称" LIKE '%景顺长城中短债债券C%'
  AND b."持仓日期" = '20210331'
  AND b."报告类型" LIKE '%季报%'
ORDER BY b."持债市值占基金资产净值比" DESC LIMIT 3;

-- 某基金股票持仓：
SELECT b."股票名称", ROUND(b."市值占基金资产净值比" * 100, 2) AS "持仓占比(%)"
FROM "基金股票持仓明细" b
JOIN "基金基本信息" f ON b."基金代码" = f."基金代码"
WHERE f."基金简称" LIKE '%基金名称%' AND b."持仓日期" = '日期'
ORDER BY b."市值占基金资产净值比" DESC LIMIT N;

### 2.股票涨跌幅查询（行业+日期）
SELECT a."股票代码", ROUND((a."收盘价(元)" - a."昨收盘(元)") / a."昨收盘(元)" * 100, 2) AS "涨跌幅(%)"
FROM "A股票日行情表" a
JOIN "A股公司行业划分表" i ON a."股票代码" = i."股票代码" AND a."交易日" = i."交易日期"
WHERE a."交易日" = '20210715' AND i."行业划分标准" = '中信行业分类'
  AND i."一级行业名称" = '消费者服务'
ORDER BY "涨跌幅(%)" DESC LIMIT 1;

### 3.基金净值查询
SELECT "单位净值", "累计单位净值" FROM "基金日行情表"
WHERE "基金代码" = (SELECT "基金代码" FROM "基金基本信息" WHERE "基金简称" LIKE '%基金名%')
  AND "交易日期" = '20210105';

## 关键规则
- 日期格式YYYYMMDD，无分隔符
- 带括号的列名必须完整保留，如 "收盘价(元)"
- 基金名用LIKE模糊匹配，基金代码用子查询
- 持仓查询需"报告类型"过滤（季报/年报/半年报）
- 排序取前N: ORDER BY 某列 DESC LIMIT N
- 别名用英文双引号包裹，如 AS "涨跌幅(%)"

## 查询
{query}

只输出一条完整SELECT语句（以SELECT开头，分号结尾）:"""
        sql = _clean_sql(_call_deepseek([{"role": "user", "content": prompt}], max_tokens=4096))
        logger.info("基金SQL: %s", str(sql)[:200])
        if sql and sql.upper().startswith("SELECT"):
            try:
                c.execute(sql); rows = c.fetchall()[:20]
                if rows:
                    cols2 = [d[0] for d in c.description]
                    result = _format_fund_answer(query, rows, cols2)
                else:
                    result = "未查询到相关数据，请检查基金名称、日期或筛选条件是否正确。"
            except Exception as e:
                logger.warning("首次SQL失败: %s", str(e)[:100])
                # 带错误信息重试
                fp2 = f"""SQL执行报错: {e}
原SQL: {sql}
表结构: {schema_str[:2500]}
查询需求: {query}
请修正SQL错误，只输出修正后的SELECT语句:"""
                sql2 = _clean_sql(_call_deepseek([{"role": "user", "content": fp2}], max_tokens=4096))
                if sql2 and sql2.upper().startswith("SELECT"):
                    try:
                        c.execute(sql2); rows = c.fetchall()[:20]
                        if rows:
                            cols2 = [d[0] for d in c.description]
                            result = _format_fund_answer(query, rows, cols2)
                        else:
                            result = "未查询到相关数据，请检查基金名称、日期或筛选条件是否正确。"
                    except Exception as e2:
                        result = f"查询失败(已重试): {str(e2)[:150]}"
                else:
                    result = f"SQL修正失败，原错误: {str(e)[:150]}"
        else:
            result = f"SQL生成失败，请尝试更明确地描述您的查询需求。"
        conn.close()
        return {"success": True, "result": result, "tool": "基金问答"}
    except Exception as e:
        logger.error("基金错误: %s", e)
        return {"success": False, "result": f"基金查询失败: {str(e)[:200]}", "tool": "基金问答"}


def tool_prospectus_qa(query):
    """招股书问答：公司名定位文件→智能内容搜索→RAG"""
    logger.info("📄 招股书: %s", query[:60])
    try:
        pdf_dir = _resolve_data_path("pdf_txt_file", env_var="PROSPECTUS_PDF_DIR")
        if not pdf_dir:
            return {"success": False, "result": "招股书PDF目录未找到(需下载bs_challenge_financial_14b_dataset)", "tool": "招股书问答"}

        # === 1. 公司名提取（多策略，优先精确后缀匹配） ===
        q_compact = re.sub(r'\s+', '', query)  # 去掉PDF复制空格
        company_candidates = []

        # 策略A: 后缀模式匹配 "XX股份有限公司"
        for suffix in ['股份有限公司', '有限公司', '有限责任公司', '科技集团', '控股集团']:
            idx = q_compact.find(suffix)
            if idx >= 0:
                start = max(0, idx - 14)
                name = q_compact[start:idx + len(suffix)]
                # 去掉前面的标点和虚词
                name = re.sub(r'^[的了是在而如何什么哪该请帮查询计算报告期内分多少从及与于]+', '', name)
                if len(name) >= 6:
                    company_candidates.append(name)

        # 策略B: >=6字的连续中文字符串
        if not company_candidates:
            long_words = re.findall(r'[一-龥]{6,}', q_compact)
            company_candidates = list(set(long_words))

        logger.info("公司名候选: %s", company_candidates[:3])

        # === 2. 文件匹配（分层：后缀匹配→ngram匹配→内容匹配） ===
        txt_files = sorted([f for f in os.listdir(pdf_dir) if f.endswith('.txt')])
        best_file, best_score, best_name = None, 0, ''

        # 从公司名生成搜索词(含去空格版)
        company_search_terms = []
        for cand in company_candidates:
            company_search_terms.append(cand)  # 紧凑版
            # 每2字间插入空格（PDF常见artifact）
            spaced = ' '.join(cand[i:i+2] for i in range(0, len(cand), 2))
            company_search_terms.append(spaced)
            # ngrams
            for n in [3, 4, 5, 6]:
                for i in range(len(cand) - n + 1):
                    company_search_terms.append(cand[i:i+n])

        # 内容关键词
        stop = r'[的了是而在如何什么哪该请帮查询计算报告期内分别多少负责具体以及来自\.\?\？\。\，\、\s：:]+'
        all_words = [kw.strip() for kw in re.split(stop, query) if len(kw.strip()) >= 2]
        content_keywords = list(set(all_words))

        for fname in txt_files:
            try:
                with open(os.path.join(pdf_dir, fname), 'r', encoding='utf-8', errors='ignore') as f:
                    fc = f.read()
                fc_compact = re.sub(r'\s+', '', fc)  # 去空格便于匹配

                # 公司名后缀匹配（最强信号）
                suffix_hits = 0
                for cand in company_candidates:
                    short_name = cand[-8:] if len(cand) > 10 else cand  # 取末尾8字匹配
                    if short_name in fc_compact:
                        suffix_hits += 10000

                # ngram匹配
                ngram_hits = sum(1 for kw in set(company_search_terms) if kw in fc_compact)

                # 内容词匹配（用紧凑版也试一遍）
                content_hits = sum(1 for kw in content_keywords[:30] if kw in fc or kw in fc_compact)

                score = suffix_hits + ngram_hits * 500 + content_hits * 5
                if score > best_score:
                    best_score = score
                    best_file = fc
                    best_name = fname
            except:
                pass

        # === 2b. 回退：文件名+内容二次匹配 ===
        if best_score < 1 and company_candidates:
            logger.info("内容匹配弱，尝试文件名+内容二次匹配...")
            for fname in txt_files:
                try:
                    with open(os.path.join(pdf_dir, fname), 'r', encoding='utf-8', errors='ignore') as f:
                        fc = f.read()
                    fc_compact = re.sub(r'\s+', '', fc)
                    fname_compact = re.sub(r'\s+', '', fname)
                    score = 0
                    for cand in company_candidates:
                        short = cand[-8:] if len(cand) > 10 else cand
                        # 文件名包含公司名（高权重，因为PDF常以公司名命名）
                        if short in fname_compact:
                            score += 20000
                        if cand in fname_compact:
                            score += 40000
                        # 文件内容包含公司名
                        if short in fc_compact:
                            score += 10000
                    # 叠加ngram和内容词
                    ngram_hits = sum(1 for kw in set(company_search_terms) if kw in fc_compact)
                    content_hits = sum(1 for kw in content_keywords[:30] if kw in fc or kw in fc_compact)
                    score += ngram_hits * 500 + content_hits * 5
                    if score > best_score:
                        best_score = score
                        best_file = fc
                        best_name = fname
                except:
                    pass

        logger.info("招股书文件: %s (得分=%d)", (best_name or '无')[:40], best_score)

        if not best_file or best_score < 1:
            # 放宽条件：直接搜所有文件
            logger.warning("标准匹配失败，全量搜索...")
            all_content = []
            for fname in txt_files[:10]:
                try:
                    with open(os.path.join(pdf_dir, fname), 'r', encoding='utf-8', errors='ignore') as f:
                        all_content.append(f.read()[:3000])
                except: pass
            if all_content:
                best_file = "\n---\n".join(all_content)
                best_name = "多文件合并"
            else:
                return {"success": False, "result": "未在80份招股书中找到相关信息，请检查数据目录是否正确", "tool": "招股书问答"}

        # === 3. 段落提取：直接搜索 + 关键词共现定位 ===
        # 从问题中提取核心关键词（用于共现评分）
        query_keywords = []
        for w in all_words:
            if len(w) >= 2:
                query_keywords.append(w)
        # 加入公司名片段
        for cand in company_candidates:
            for n in [2, 3, 4]:
                for i in range(len(cand) - n + 1):
                    piece = cand[i:i+n]
                    if piece not in query_keywords:
                        query_keywords.append(piece)

        # 方法A：用最精准的查询词直接定位（找所有包含答案的段落）
        # 优先使用低频高特异性词（如"军用领域"、"兴图新科"等）
        precise_terms = [kw for kw in query_keywords
                        if len(kw) >= 3 and best_file.count(kw) <= 50]
        if not precise_terms:
            precise_terms = [kw for kw in query_keywords
                           if len(kw) >= 2 and best_file.count(kw) <= 100]

        # 对每个精准词，提取其周围出现的段落
        raw_paragraphs = []
        for term in precise_terms[:10]:
            pos = 0
            count = 0
            while pos < len(best_file) and count < 15:
                pos = best_file.find(term, pos)
                if pos < 0:
                    break
                # 扩大上下文窗口：前1000字 + 后3000字
                start = max(0, pos - 1000)
                end = min(len(best_file), pos + 3000)
                para = best_file[start:end]
                if len(para) > 100:
                    raw_paragraphs.append(para)
                pos += len(term)
                count += 1

        # 方法B：如果精准词太少，用通用词补充
        if len(raw_paragraphs) < 5:
            generic_terms = ['收入', '合计', '分别为', '万元', '占比', '发行', '募集']
            for term in generic_terms:
                if term in best_file:
                    pos = best_file.find(term)  # 只取第一次出现
                    if pos >= 0:
                        start = max(0, pos - 500)
                        end = min(len(best_file), pos + 2500)
                        para = best_file[start:end]
                        if len(para) > 100:
                            raw_paragraphs.append(para)
                    if len(raw_paragraphs) >= 10:
                        break

        # === 加固1: 数据扫荡 —— 直接搜索答案模式（数字+单位序列） ===
        # 无论关键词匹配如何，这些段落最可能包含答案
        data_pattern = re.compile(
            r'(?:\d{1,3}(?:,\d{3})*\.?\d*\s*[万元亿%个百千万]+\s*[、，,和及与或\s]+){2,}'
            r'\d{1,3}(?:,\d{3})*\.?\d*\s*[万元亿%个百千万]+'
        )
        for m in data_pattern.finditer(best_file):
            pos = m.start()
            start = max(0, pos - 600)
            end = min(len(best_file), pos + 2000)
            dp = best_file[start:end]
            if len(dp) > 100:
                raw_paragraphs.append(dp)
            if len(raw_paragraphs) >= 30:
                break

        # === 加固2: 补齐被停用词拆散的关键词 ===
        extra_keywords = re.findall(r'[一-龥]{2,}', q_compact)
        for ek in extra_keywords:
            if ek not in query_keywords and len(ek) >= 2:
                query_keywords.append(ek)

        if not raw_paragraphs:
            raw_paragraphs = [best_file[:12000]]
            logger.warning("无段落命中，使用文件前12000字")

        # 去重
        seen = set()
        paragraphs = []
        for p in raw_paragraphs:
            key = p[200:500]
            if key not in seen:
                seen.add(key)
                paragraphs.append(p)

        # === 段落相关性评分 + 排序 ===
        query_kw_set = set(query_keywords)
        # 扩展关键词集
        for term in ['军用', '军方', '军品', '国防', '军队', '收入', '营收',
                      '营业收入', '主营业务收入', '分别为', '万元', '亿元',
                      '发行', '配售', '上市', '募集', '股东', '出资', '占比',
                      '报告期', '年度', '披露', '合计']:
            query_kw_set.add(term)

        def relevance_score(para):
            hits = sum(1 for kw in query_kw_set if kw in para)
            data_bonus = len(re.findall(r'\d+\.?\d*\s*[万元亿%]', para))
            return hits * 10 + data_bonus

        # 强制保留：包含原始查询关键词首次出现位置的段落
        # （这些段落最可能包含答案，防止被公司名ngram段落挤掉）
        guaranteed_paragraphs = []
        for term in all_words[:5]:  # 用户问题中的原始关键词（非ngram）
            if len(term) >= 2:
                pos = best_file.find(term)
                if pos >= 0:
                    start = max(0, pos - 1000)
                    end = min(len(best_file), pos + 3000)
                    gp = best_file[start:end]
                    if len(gp) > 100:
                        guaranteed_paragraphs.append(gp)

        # 去重保证段落
        seen_g = set()
        guaranteed_unique = []
        for p in guaranteed_paragraphs:
            key = p[200:500]
            if key not in seen_g:
                seen_g.add(key)
                guaranteed_unique.append(p)

        # 排序：保证段落优先，其余按相关性排列
        paragraphs.sort(key=relevance_score, reverse=True)
        # 移除与保证段落重复的
        guaranteed_keys = {p[200:500] for p in guaranteed_unique}
        other_paragraphs = [p for p in paragraphs if p[200:500] not in guaranteed_keys]

        final_paragraphs = guaranteed_unique + other_paragraphs
        context = "\n\n---\n\n".join(final_paragraphs[:8])
        logger.info("招股书段落: %d段 (保证%d段, top得分=%s)",
                   len(final_paragraphs[:8]), len(guaranteed_unique),
                   [relevance_score(p) for p in final_paragraphs[:3]])

        # === 4. RAG问答 ===
        sys_prompt = (
            "你是专业的招股说明书分析师。请严格基于提供的文本内容回答问题。\n"
            "规则:\n"
            "1. 只引用文本中有的数据，不要编造\n"
            "2. 保留原始数据的精度和单位\n"
            "3. 如果有多个数据点，请逐项列出\n"
            "4. 如果用户问的精确术语(如'战略配售结果')在文本中未出现，请搜索相关概念(如'发行'/'配售'/'网下配售'等)\n"
            "5. 尽量找到相关信息回答——即使不精确匹配，也要提供最接近的内容。比如问'配售结果'但文本只有'发行方案'，请把发行方案中相关的内容整理出来\n"
            "6. 确实完全无关时才说'未找到'，并说明搜索了哪些相关词，同时列出文本中可能与问题相关的内容\n"
            "7. 用简洁清晰的中文回复，信息要完整，至少2-3句话"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"## 招股书文本\n\n{context[:12000]}\n\n## 问题\n{query}\n\n请根据以上文本回答（如果精确术语未出现，请用相关概念搜索）："}
        ]
        answer = _call_deepseek(messages, max_tokens=3072)

        # === 加固3: 两轮RAG —— 如果第一轮没找到，用合并上下文重试 ===
        if answer and any(kw in answer for kw in ['未找到', '未在文本', '没有相关', '未披露', '未发现']):
            logger.warning("第一轮RAG未找到，启动合并数据扫荡重试...")
            # 合并第一轮段落 + 数据扫荡段落（取并集，不替换）
            data_paras = [p for p in raw_paragraphs
                         if re.findall(r'\d+\.?\d*\s*[万元亿%]', p)]
            data_paras.sort(key=lambda p: -len(re.findall(r'\d+\.?\d*\s*[万元亿%]', p)))
            # 合并：保证段落 + 数据段落 + 原始段落
            merged_paras = guaranteed_unique.copy()
            seen_m = {p[200:500] for p in merged_paras}
            for p in data_paras + final_paragraphs:
                key = p[200:500]
                if key not in seen_m:
                    seen_m.add(key)
                    merged_paras.append(p)
            retry_context = "\n\n---\n\n".join(merged_paras[:12])
            retry_prompt = (
                "你是专业的招股说明书分析师。以下是招股书的完整数据段落（含原文段落和数字密集段落）。\n"
                "请仔细阅读，找到与问题最相关的数据并完整回答。\n"
                "不要轻易说'未找到'——如果精确术语未出现，请用最接近的内容回答。\n"
                "规则: 1)只引用文本数据 2)保留精度和单位 3)逐项列出 4)信息完整"
            )
            retry_msg = [
                {"role": "system", "content": retry_prompt},
                {"role": "user", "content": f"## 招股书段落\n\n{retry_context[:12000]}\n\n## 问题\n{query}\n\n请根据以上文本回答："}
            ]
            retry_answer = _call_deepseek(retry_msg, max_tokens=3072)
            if retry_answer and len(retry_answer.strip()) >= 20:
                answer = retry_answer
                logger.info("第二轮RAG成功: %s", answer[:80])

        return {"success": True, "result": answer[:3000] if answer else "生成失败", "tool": "招股书问答"}
    except Exception as e:
        logger.error("招股书错误: %s", e)
        return {"success": False, "result": f"招股书查询失败: {str(e)[:200]}", "tool": "招股书问答"}

TOOL_REGISTRY = {
    "记账本": (tool_ledger, "记录收支、查询账目。适用：记账、花了多少钱、买书、收入支出等"),
    "日程提醒": (tool_schedule, "添加日程、查询日历、设置提醒。适用：提醒我、日程、日历等"),
    "文生图": (tool_text2image, "根据文本生成图片。适用：生成图片、画一张、文生图等"),
    "基金问答": (tool_fund_qa, "查询基金/股票/债券数据。适用：基金净值、股票涨跌、持仓等"),
    "招股书问答": (tool_prospectus_qa, "查询招股说明书。适用：招股书、IPO、发起人、公司背景等"),
}


def call_tool(tool_name, query):
    if tool_name not in TOOL_REGISTRY: return {"success": False, "result": f"未知工具: {tool_name}", "tool": tool_name}
    func, _ = TOOL_REGISTRY[tool_name]; return func(query)


def get_tool_descriptions():
    return "\n".join(f"- **{n}**: {d}" for n, (_, d) in TOOL_REGISTRY.items())

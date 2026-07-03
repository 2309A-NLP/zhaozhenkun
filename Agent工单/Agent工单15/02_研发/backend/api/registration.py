"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1
挂号管理 API —— 自然语言挂号/查号/取消/查医生（DeepSeek 意图解析 + SQLite）
================================================================================
"""
import re, json, logging  # 导入正则表达式模块（提取 JSON）、JSON 模块（解析意图）、日志模块（错误记录）
from datetime import datetime  # 导入 datetime，用于获取当前日期时间（挂号日期默认值）
from fastapi import APIRouter  # 导入 FastAPI 的路由器，用于定义 API 路由分组
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式的 HTTP 响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于请求数据模型定义和字段校验
from db.database import get_db  # 导入数据库连接管理器，返回 SQLite 连接上下文

_log = logging.getLogger("medical_agent.registration")  # 获取挂号管理模块的日志记录器实例
router = APIRouter(prefix="/api/registration", tags=["挂号管理"])  # 创建 API 路由器，前缀 /api/registration，Swagger 标签为"挂号管理"

class RegRequest(BaseModel):  # 定义挂号请求数据模型，继承 Pydantic BaseModel
    message: str = Field(..., min_length=1, max_length=2000)  # 必填：用户输入的自然语言挂号消息，长度 1-2000

from services.llm_client import get_deepseek_client  # 导入 DeepSeek 客户端工厂函数（延迟导入以避免循环依赖）

# DeepSeek 意图解析的提示词
INTENT_PROMPT = """你是挂号意图解析器，从用户消息提取 JSON。
意图: book(挂号), query(查号), cancel(取消), doctor_query(查医生)
参数: intent, child_name, department, doctor_title(专家/主任/普通),
      date(YYYY-MM-DD), time_slot(上午/下午), doctor_name, reason
当前: {now} | 用户: user_id=1, children: 大宝/二宝/小宝
    示例输出格式
只返回 JSON: {"intent":"book","child_name":"大宝","department":"儿科","doctor_title":"专家","date":"2026-06-29","time_slot":"下午"}"""

def _parse_intent(msg: str) -> dict:  # 定义意图解析函数：将自然语言消息转为结构化挂号参数字典
    """用 DeepSeek 将自然语言转为结构化挂号参数"""
    try:  # 使用 try 块捕获意图解析过程中的异常
        ds = get_deepseek_client()  # 获取 DeepSeek 客户端实例，用于意图解析
        now = datetime.now().strftime("%Y-%m-%d %A")  # 获取当前日期和星期，格式如 "2026-07-03 Thursday"
        r = ds.chat([{"role":"user","content":msg}],  # 调用 DeepSeek chat 接口，传入用户消息
                     system=INTENT_PROMPT.replace("{now}",now), max_tokens=300)  # 将系统提示词中的 {now} 替换为当前时间，限制回复长度
        m = re.search(r'\{[^{}]*\}', r.get("content",""))  # 从回复中提取 JSON：匹配第一个花括号包裹的 JSON 对象
        return json.loads(m.group()) if m else {"intent":"unknown"}  # 如果匹配到 JSON 则解析返回，否则返回意图 unknown
    except Exception as e:  # 捕获所有异常（JSON 解析、网络、API 错误等）
        _log.error("意图解析失败: %s", e)  # 记录错误日志：意图解析失败及具体原因
        return {"intent":"unknown"}  # 解析失败时返回意图 unknown

# 孩子名→ID 映射
CHILD_MAP = {"大宝":1,"二宝":2,"小宝":3}  # 将用户使用的孩子昵称映射为数据库中的 child_id

# 口语→数据库科室名映射（用户说的 vs 数据库存的）
DEPT_ALIAS = {  # 定义科室别名映射字典：将用户口语中的科室名映射为数据库中的正式名称
    "牙科":"口腔科","口腔":"口腔科","牙齿":"口腔科",  # 口腔相关：牙科、口腔、牙齿 → 口腔科
    "心脏科":"内科","心脏":"内科","心内科":"内科",  # 王强在"内科"——心脏科、心脏、心内科 → 内科
    "神经科":"神经内科","脑科":"神经内科",  # 神经相关：神经科、脑科 → 神经内科
    "肠胃科":"消化内科","肠胃":"消化内科","胃肠":"消化内科",  # 消化相关：肠胃科、肠胃、胃肠 → 消化内科
    "妇科":"妇产科","产科":"妇产科",  # 妇产相关：妇科、产科 → 妇产科
    "小儿科":"儿科","小儿":"儿科","儿童":"儿科",  # 儿科相关：小儿科、小儿、儿童 → 儿科
    "皮肤":"皮肤科","骨头":"骨科","眼睛":"眼科","耳鼻喉":"耳鼻喉科",  # 其他科室映射：皮肤、骨头、眼睛、耳鼻喉
    "呼吸科":"内科","内分泌":"内科","肾内科":"内科",  # 内科相关子科室统一映射为内科
}
def _norm_dept(d: str) -> str:  # 定义科室名规范化函数：将口语科室名转为数据库中的正式名
    """将口语科室名转为数据库中的正式名"""
    return DEPT_ALIAS.get(d, d)  # 在别名映射字典中查找，找到则返回正式名，找不到则返回原名

def _norm_slot(s: str) -> str:  # 定义时段规范化函数：将"下午2点"等自然语言转为"上午"或"下午"
    """下午2点→下午"""
    return "上午" if "上午" in s else ("下午" if "下午" in s else s)  # 如果包含"上午"则返回"上午"，包含"下午"则返回"下午"，否则原样返回

def _norm_title(t: str) -> str:  # 定义医生级别规范化函数：将口语中的级别映射为数据库中的标准级别  # noqa
    """专家→主任，普通→不限制"""
    return {"专家":"主任","主任":"主任","普通":"","主治":"主治","副主任":"副主任"}.get(t,t)  # 查字典：专家→主任，普通→空（不限制），找不到则保留原名

@router.post("/chat")  # 注册 POST 路由：/api/registration/chat，挂号对话入口
async def reg_chat(req: RegRequest):  # 定义异步挂号对话接口，接收 RegRequest 请求体
    """挂号对话入口：自动识别意图并执行"""
    try:  # 使用 try 块捕获挂号处理的整体异常
        p = _parse_intent(req.message)  # 调用意图解析函数，将用户消息转为结构化参数字典
        it = p.get("intent","unknown")  # 提取意图类型，默认为 unknown
        if it == "book": return _do_book(p)  # 意图为挂号(book) → 调用挂号执行函数
        if it == "query": return _do_query(p)  # 意图为查号(query) → 调用号源查询函数
        if it == "cancel": return _do_cancel(p)  # 意图为取消(cancel) → 调用取消挂号函数
        if it == "doctor_query": return _do_doctor(p)  # 意图为查医生(doctor_query) → 调用医生查询函数
        return _fallback(req.message)  # 无法识别时规则降级：使用关键词匹配兜底
    except Exception as e:  # 捕获所有异常
        _log.exception("挂号处理异常")  # 记录完整异常堆栈日志
        return JSONResponse({"success":False,"reply":f"系统错误: {e}"}, status_code=500)  # 返回 500 错误响应

def _fallback(msg: str) -> dict:  # 定义规则降级函数：不依赖 LLM 意图解析，纯关键词匹配兜底
    """简单规则降级：不依赖 LLM，纯关键词匹配"""
    dept = next((d for d in ["儿科","内科","外科","眼科","口腔科","皮肤科","消化内科"] if d in msg),"")  # 在消息中匹配已知科室关键词，取第一个匹配的
    title = "主任" if "专家" in msg or "主任" in msg else ("主治" if "普通" in msg else "")  # 根据关键词判断医生级别：专家/主任→主任，普通→主治
    child = next((c for c in ["大宝","二宝","小宝"] if c in msg),"")  # 在消息中匹配孩子昵称，取第一个匹配的
    return _do_book({"department":dept,"doctor_title":title,"child_name":child,"date":"","time_slot":"下午"})  # 用提取的参数调用挂号函数，默认下午

def _do_book(p: dict) -> dict:  # 定义挂号执行函数：查询可用号源→扣减库存→生成预约记录
    """执行挂号：查询可用号源→扣减库存→生成预约记录"""
    dept = _norm_dept(p.get("department",""))  # 口语→正式名：将用户说的科室转换为数据库中的正式科室名
    title, child = _norm_title(p.get("doctor_title","")), p.get("child_name","")  # 规范化医生级别、提取孩子姓名
    date, slot = p.get("date",""), _norm_slot(p.get("time_slot","下午"))  # 提取日期、规范化时段（默认下午）

    with get_db() as conn:  # 使用数据库上下文管理器获取 SQLite 连接
        # 查询可用号源（含医生姓名、科室、排班 ID）
        sql = """SELECT s.id as sid, s.date, s.time_slot, d.id as did, d.name as doctor,
                 dp.name as dept, d.title, s.current_patients, s.max_patients
                 FROM schedules s JOIN doctors d ON s.doctor_id=d.id
                 JOIN departments dp ON d.department_id=dp.id
                 WHERE s.current_patients < s.max_patients

                 AND s.date >= date('now')"""
        params = []  # 初始化 SQL 参数列表
        if dept: sql += " AND dp.name LIKE ?"; params.append(f"%{dept}%")    # 科室筛选：如果指定了科室，添加模糊匹配条件
        if title: sql += " AND d.title LIKE ?"; params.append(f"%{title}%")  # 级别筛选：如果指定了医生级别，添加模糊匹配条件
        if date: sql += " AND s.date = ?"; params.append(date)                # 日期筛选：如果指定了日期，添加精确匹配条件
        if slot: sql += " AND s.time_slot = ?"; params.append(slot)           # 时段筛选：如果指定了时段，添加精确匹配条件
        sql += " ORDER BY s.date, s.time_slot LIMIT 1"  # 按日期和时段排序，只取第一条最匹配的号源
        r = conn.execute(sql, params).fetchone()  # 执行 SQL 查询并获取第一条结果
        if not r:  # 如果没有找到精确匹配的号源
            # 无精确匹配 → 放宽条件推荐最近号源
            alt = conn.execute("""SELECT s.date,s.time_slot,d.name,d.title,dp.name as dept
                FROM schedules s JOIN doctors d ON s.doctor_id=d.id JOIN departments dp ON d.department_id=dp.id
                WHERE s.current_patients<s.max_patients AND dp.name LIKE ?
                AND s.date >= date('now')
                ORDER BY s.date LIMIT 3""", (f"%{dept}%",)).fetchall()
            if alt:  # 如果找到替代号源
                return {"success":True,"reply":"最近的可用号源：\n"+  # 返回推荐信息，列出最近的可用号源
                        "\n".join(f"  {a['date']} {a['time_slot']} {a['name']}({a['title']})" for a in alt)+"\n需要挂吗？"}  # 格式化显示号源并询问用户
            return {"success":True,"reply":f"{dept or '该科室'}暂无可用号源"}  # 无任何号源时返回提示

        # 执行挂号事务：更新号源计数 + 插入预约记录
        conn.execute("UPDATE schedules SET current_patients=current_patients+1 WHERE id=?",(r["sid"],))  # 号源计数+1：将该排班的已挂号人数加一
        conn.execute("INSERT INTO appointments(user_id,child_id,doctor_id,schedule_id) VALUES(1,?,?,?)",  # 插入预约记录：用户ID默认1
                     (CHILD_MAP.get(child), r["did"], r["sid"]))  # 参数：孩子ID（查映射表）、医生ID、排班ID
        # commit 由 get_db() context manager 自动执行
        return {"success":True,"reply":f"✅ 挂号成功！\n就诊人{'（'+child+'）' if child else ''}\n"  # 返回挂号成功信息，包含就诊人
                f"科室：{r['dept']}\n医生：{r['doctor']}({r['title']})\n时间：{r['date']} {r['time_slot']}"}  # 显示科室、医生（含级别）、预约时间

def _do_query(p: dict) -> dict:  # 定义号源查询函数：查询当前可用的挂号号源
    """查询可用号源"""
    dept = _norm_dept(p.get("department",""))  # 口语→正式名：规范化科室名称
    with get_db() as conn:  # 使用数据库上下文管理器获取连接
        rows = conn.execute("""SELECT s.date,s.time_slot,d.name,d.title,dp.name as dept,
            s.max_patients-s.current_patients as rem FROM schedules s
            JOIN doctors d ON s.doctor_id=d.id JOIN departments dp ON d.department_id=dp.id

            WHERE s.current_patients<s.max_patients AND s.date >= date('now')""" +
            (" AND dp.name LIKE ?" if dept else "") + " ORDER BY s.date LIMIT 8",  # 如果指定科室则添加筛选条件，按日期排序最多返回 8 条
            (f"%{dept}%",) if dept else ()).fetchall()  # 传入科室参数；无科室条件时参数为空元组
    return {"success":True,"reply": "\n".join(  # 返回号源查询结果
        f"📅 {r['date']} {r['time_slot']} | {r['dept']} | {r['name']}({r['title']}) | 余{r['rem']}号"  # 格式化每条号源信息
        for r in rows) if rows else f"{dept or '各科室'}暂无可用号源"}  # 有结果则格式化输出，无结果则提示暂无号源

def _do_cancel(p: dict) -> dict:  # 定义取消挂号函数：按科室+级别匹配，不匹配时取消最新的一条
    """取消挂号（按科室+级别匹配，不匹配时取消最新的一条）"""
    dept, title = p.get("department",""), _norm_title(p.get("doctor_title",""))  # 提取并规范化科室和医生级别
    with get_db() as conn:  # 使用数据库上下文管理器获取连接
        sql = """SELECT a.id,s.date,s.time_slot,d.name,d.title,dp.name as dept FROM appointments a
            JOIN schedules s ON a.schedule_id=s.id JOIN doctors d ON a.doctor_id=d.id
            JOIN departments dp ON d.department_id=dp.id WHERE a.user_id=1 AND a.status='confirmed'"""
        params = []  # 初始化 SQL 参数列表
        if dept: sql += " AND dp.name LIKE ?"; params.append(f"%{dept}%")  # 如果指定科室，添加模糊匹配条件
        if title: sql += " AND d.title LIKE ?"; params.append(f"%{title}%")  # 如果指定医生级别，添加模糊匹配条件
        r = conn.execute(sql+" ORDER BY a.created_at DESC LIMIT 1", params).fetchone()  # 按创建时间倒序取最新一条匹配的预约记录
        if r:  # 如果找到了可取消的预约记录
            conn.execute("UPDATE appointments SET status='cancelled' WHERE id=?",(r["id"],))  # 将预约状态更新为 cancelled（已取消）
            return {"success":True,"reply":f"✅ 已取消: {r['dept']} {r['name']}({r['title']}) {r['date']} {r['time_slot']}"}  # 返回取消成功信息
    return {"success":True,"reply":"没有找到可取消的挂号记录"}  # 没找到可取消的记录时返回提示

def _do_doctor(p: dict) -> dict:  # 定义医生查询函数：查询医生的坐诊时间和科室信息
    """查询医生坐诊时间"""
    name = p.get("doctor_name","")  # 提取要查询的医生姓名
    with get_db() as conn:  # 使用数据库上下文管理器获取连接
        rows = conn.execute("""SELECT d.name,d.title,dp.name as dept,s.date,s.time_slot FROM doctors d
            JOIN departments dp ON d.department_id=dp.id LEFT JOIN schedules s ON d.id=s.doctor_id
            AND s.date>=date('now') WHERE d.name LIKE ? ORDER BY s.date LIMIT 8""",
            (f"%{name}%",)).fetchall()  # 医生姓名模糊匹配查询
    if not rows: return {"success":True,"reply":f"未找到: {name}"}  # 未找到该医生时返回提示
    return {"success":True,"reply":"\n".join(  # 返回医生信息：先显示医生基本信息，再列出排班时间
        [f"👨‍⚕ {rows[0]['name']}({rows[0]['title']}) - {rows[0]['dept']}"]+  # 第一行：医生姓名、级别、所属科室
        [f"   📅 {r['date']} {r['time_slot']}" for r in rows if r['date']])}  # 后续行：列出具体的排班日期和时段（日期非空）

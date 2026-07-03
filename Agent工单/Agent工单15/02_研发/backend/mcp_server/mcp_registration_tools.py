"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1
MCP Server —— 挂号管理工具组 (Registration Tools)

工具列表:
  1. registration_chat   —— 自然语言挂号对话 (含意图解析 + 执行)
  2. registration_query  —— 按科室查询可用号源
  3. registration_book   —— 直接挂号下单
  4. registration_cancel —— 取消已预约挂号
  5. registration_doctor —— 查询医生坐诊时间

通过 @mcp.tool() 装饰器自动注册到 mcp_core.mcp 实例.
================================================================================
"""
import json

from mcp_server.mcp_core import mcp


# ================================================================
# registration_chat
# ================================================================

@mcp.tool(
    name="registration_chat",
    description="自然语言挂号对话 —— 支持挂号预约、号源查询、取消挂号、医生查询。示例：'帮大宝挂一个今天下午2点儿科专家的号'"
)
async def registration_chat(message: str) -> str:
    """
    挂号管理自然语言对话接口

    支持的操作类型:
      - 挂号: "帮大宝挂今天下午2点儿科专家的号"
      - 查号: "牙科最近的号是哪天的？"
      - 取消: "取消我上周三挂的消化内科普通号"
      - 查医生: "帮我查下张建国医生下周的坐诊时间"

    Args:
      message: 用户的自然语言挂号请求
    """
    from api.registration import _parse_intent, _do_book, _do_query, _do_cancel, _do_doctor

    try:
        p = _parse_intent(message)
        it = p.get("intent", "unknown")

        if it == "book":
            result = _do_book(p)
        elif it == "query":
            result = _do_query(p)
        elif it == "cancel":
            result = _do_cancel(p)
        elif it == "doctor_query":
            result = _do_doctor(p)
        else:
            # 规则降级
            result = _do_book({"department": "", "doctor_title": "",
                               "child_name": "", "date": "", "time_slot": "下午"})

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "reply": f"挂号处理失败: {e}"}, ensure_ascii=False)


# ================================================================
# registration_query
# ================================================================

@mcp.tool(
    name="registration_query",
    description="查询可用号源 —— 按科室筛选可用的挂号号源"
)
async def registration_query(department: str = "") -> str:
    """查询科室可用号源"""
    from api.registration import _do_query, _norm_dept
    result = _do_query({"department": _norm_dept(department)})
    return json.dumps(result, ensure_ascii=False)


# ================================================================
# registration_book
# ================================================================

@mcp.tool(
    name="registration_book",
    description="直接挂号 —— 指定科室、级别、时间、就诊人进行挂号"
)
async def registration_book(department: str, doctor_title: str = "",
                            child_name: str = "", date: str = "",
                            time_slot: str = "下午") -> str:
    """直接挂号"""
    from api.registration import _do_book, _norm_dept, _norm_title, _norm_slot
    result = _do_book({
        "department": _norm_dept(department),
        "doctor_title": _norm_title(doctor_title),
        "child_name": child_name,
        "date": date,
        "time_slot": _norm_slot(time_slot),
    })
    return json.dumps(result, ensure_ascii=False)


# ================================================================
# registration_cancel
# ================================================================

@mcp.tool(
    name="registration_cancel",
    description="取消挂号 —— 按科室和医生级别取消已预约的挂号"
)
async def registration_cancel(department: str, doctor_title: str = "") -> str:
    """取消挂号"""
    from api.registration import _do_cancel, _norm_title
    result = _do_cancel({"department": department, "doctor_title": _norm_title(doctor_title)})
    return json.dumps(result, ensure_ascii=False)


# ================================================================
# registration_doctor
# ================================================================

@mcp.tool(
    name="registration_doctor",
    description="查询医生坐诊时间"
)
async def registration_doctor(doctor_name: str) -> str:
    """查询医生坐诊时间"""
    from api.registration import _do_doctor
    result = _do_doctor({"doctor_name": doctor_name})
    return json.dumps(result, ensure_ascii=False)

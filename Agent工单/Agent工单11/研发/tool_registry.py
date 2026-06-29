# -*- coding: utf-8 -*-
"""
tool_registry.py — 挂号Agent工具注册表
--------------------------------------------------------------
功能: 维护所有可用工具的名称→函数映射, 提供统一调用接口。
  被 agent_core.py 导入, LLM 识别 intent 后通过此注册表路由到具体函数。

工具列表(6个):
  挂号 / 查询号源 / 取消挂号 / 查询排班 / 查询历史 / 科室列表

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import inspect                         # 函数签名检查（过滤无效参数）

# 导入写操作(挂号/取消/复约)
from tool_register import (
    make_registration,       # 创建挂号
    cancel_registration,     # 取消挂号
    rebook_from_history,     # 复约(历史→挂号)
)
# 导入读操作(查询)
from tool_query import (
    query_schedule,          # 号源查询
    query_registration_history,  # 历史记录
    query_doctor_schedule,   # 医生排班
    get_dept_list,           # 科室列表
)

# ============================================================
# 工具注册表: 工具名 → (函数, 描述)
# ============================================================
TOOL_REGISTRY = {
    "挂号": (make_registration, "创建挂号预约。适用: 挂号、预约、约号、挂一个号"),
    "查询号源": (query_schedule, "查询指定科室/医生的可用号源。适用: 还有号吗、号源、有没有号"),
    "取消挂号": (cancel_registration, "取消已有挂号。适用: 取消、退号、撤销挂号"),
    "查询排班": (query_doctor_schedule, "查询医生坐诊排班表。适用: 坐诊时间、排班、哪天有号"),
    "查询历史": (query_registration_history, "查询用户历史挂号记录。适用: 之前挂过、历史记录、挂过的号"),
    "科室列表": (get_dept_list, "获取所有科室列表。适用: 有哪些科室、科室列表"),
    "复约": (rebook_from_history, "根据历史记录重新预约同一个医生。适用: 再约、复约、再挂一次、之前看过XX再约"),
}


def _filter_kwargs(func, **kwargs):
    """只保留函数签名中实际接受的参数，过滤掉 LLM 多提取的无效参数。"""
    sig = inspect.signature(func)
    valid = set(sig.parameters.keys())
    return {k: v for k, v in kwargs.items() if k in valid}


def call_tool(tool_name: str, **kwargs) -> dict:
    """统一工具调用入口 — 根据工具名路由到对应函数并格式化输出。

    参数:
        tool_name: 工具名(必须是TOOL_REGISTRY中的key)
        **kwargs: 传给工具函数的参数(如user_id, dep_name, target_date等)
    返回:
        {"success": bool, "result": str(自然语言), "tool": str, "data": list|dict|None}

    工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
    """
    if tool_name not in TOOL_REGISTRY:       # 未知工具
        return {"success": False, "result": f"未知工具: {tool_name}", "tool": tool_name}
    func, _ = TOOL_REGISTRY[tool_name]       # 取函数(忽略描述)
    user_id = kwargs.pop("user_id", 1)       # 提取user_id(默认1), 防止传给不需要的函数

    # ---- 根据工具类型分别处理 ----
    if tool_name == "科室列表":
        data = func()                        # 无参数查询
        dept_names = [d["dep_Name"] for d in data]
        return {"success": True,
                "result": "可用科室: " + "、".join(dept_names),
                "tool": tool_name, "data": data}

    elif tool_name == "查询号源":
        r = func(**_filter_kwargs(func, **kwargs))  # 传参查询(过滤无效参数)
        if not r:                            # 无结果
            return {"success": True, "result": "当前暂无可挂号源。", "tool": tool_name}
        lines = ["查询结果:"]
        for s in r[:8]:                      # 最多显示8条
            lines.append(f"{s['sch_Date']} {s['sch_Period']} | {s['dep_Name']} | "
                        f"{s['d_Name']}({s['d_Profession']}) | 剩余{s['sch_Remain']}号 | "
                        f"{s['sch_Fee']}元")
        return {"success": True, "result": "\n".join(lines), "tool": tool_name, "data": r}

    elif tool_name == "查询历史":
        kwargs["user_id"] = user_id          # 查询历史需要user_id
        r = func(**_filter_kwargs(func, **kwargs))  # 传参查询(过滤无效参数)
        if not r:                            # 无记录
            return {"success": True, "result": "暂无挂号记录。", "tool": tool_name}
        lines = ["历史挂号记录:"]
        s_map = {0: "已预约", 1: "已取消", 2: "已完成"}  # 状态映射
        for h in r[:10]:                     # 最多10条
            lines.append(f"{h['reg_Time']} | {h['dep_Name']} | {h['d_Name']} | "
                        f"{s_map.get(h['reg_Status'], '?')}")
        return {"success": True, "result": "\n".join(lines), "tool": tool_name, "data": r}

    elif tool_name in ("挂号", "取消挂号", "复约"):
        kwargs["user_id"] = user_id          # 写操作需要user_id
        return func(**_filter_kwargs(func, **kwargs))  # 直接返回(过滤无效参数)
    elif tool_name == "查询排班":
        return func(**_filter_kwargs(func, **kwargs))  # 查询排班(过滤无效参数)

    return {"success": False, "result": "未知操作", "tool": tool_name}


def get_tool_descriptions() -> str:
    """生成工具描述文本 — 供 LLM 系统提示词使用。
    返回:
        str: 格式化为 "- **工具名**: 描述" 的多行文本
    """
    lines = []
    for name, (_, desc) in TOOL_REGISTRY.items():
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)

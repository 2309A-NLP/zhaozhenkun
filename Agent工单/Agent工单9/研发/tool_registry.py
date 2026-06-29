# -*- coding: utf-8 -*-
"""
tool_registry.py — 工具注册表（统一调度入口）
--------------------------------------------------------------
功能: 所有 Agent 工具的注册中心。
      提供工具名→函数映射、工具描述生成、统一调用接口。
      被 agent_core.py 导入使用。

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""

# 导入各工具模块的函数（每个文件一个独立工具）
from tool_ledger import tool_ledger              # 记账本 — 收支记录/查询
from tool_schedule import tool_schedule           # 日程提醒 — 日程管理
from tool_text2image import tool_text2image       # 文生图 — 图像生成/人脸旋转
from tool_fund import tool_fund_qa                # 基金问答 — NL2SQL 金融数据查询
from tool_prospectus import tool_prospectus_qa    # 招股书问答 — RAG 招股书检索


# ============================================================
# 工具注册表 — 工具名 → (函数, 描述)
# ============================================================
TOOL_REGISTRY = {
    "记账本": (tool_ledger, "记录收支、查询账目。适用：记账、花了多少钱、买书、收入支出等"),
    "日程提醒": (tool_schedule, "添加日程、查询日历、设置提醒。适用：提醒我、日程、日历等"),
    "文生图": (tool_text2image, "根据文本生成图片或人脸旋转。适用：生成图片、画一张、文生图、把人脸旋转等"),
    "基金问答": (tool_fund_qa, "查询基金/股票/债券行情数据。适用：基金净值、股票涨跌、持仓等"),
    "招股书问答": (tool_prospectus_qa, "查询招股说明书内容。适用：招股书、IPO、发起人、公司背景等"),
}


def call_tool(tool_name: str, query: str) -> dict:
    """统一工具调用入口

    功能: 根据工具名路由到对应的工具函数，传入用户查询并返回结果。

    参数:
        tool_name (str): 工具名（必须是 TOOL_REGISTRY 中的 key）
        query (str): 用户原始查询文本

    返回:
        dict: {"success": bool, "result": str, "tool": str}
    """
    # 检查工具名是否在注册表中
    if tool_name not in TOOL_REGISTRY:
        return {
            "success": False,
            "result": f"未知工具: {tool_name}",
            "tool": tool_name
        }
    # 从注册表取函数（元组第一个元素），忽略描述
    func, _ = TOOL_REGISTRY[tool_name]
    return func(query)


def get_tool_descriptions() -> str:
    """生成工具描述文本（供 LLM 系统提示词使用）

    功能: 遍历注册表，生成格式化的工具列表，帮助 LLM 理解可用工具。

    返回:
        str: 格式为 "- **工具名**: 描述" 的多行文本
    """
    lines = []
    for name, (_, desc) in TOOL_REGISTRY.items():
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    # 打印工具注册表信息
    print("可用工具注册表:")
    print(get_tool_descriptions())
    print(f"\n共 {len(TOOL_REGISTRY)} 个工具")

"""
================================================================================
文件名:   api/map_format.py
功能:     地图 API 结果格式化工具函数
          —— 将高德 API 返回的结构化 dict 精简为 LLM / 人类易读的文本格式
所属项目:  医疗智能体-影像分析系统
调用方:    api/map_chat.py（Step 3 整理回复时使用）
================================================================================
"""


def fmt_for_prompt(data: dict, depth: int = 0) -> str:
    """
    将高德 API 返回的结构化 dict 精简为 LLM 友好的文本格式

    为什么需要这个函数？
      - 高德 API 返回的原始 JSON 体积很大（含大量元数据）
      - LLM 的上下文窗口有限，需要精简
      - 格式化后的文本 LLM 理解更准确

    参数:
      data:  高德 API 返回的结果 dict
      depth: 递归深度（防止无限循环，最大 2 层）

    返回:
      纯文本摘要（不超过 500 字符）
    """
    # 防止递归过深
    if depth > 2:
        return ""
    lines = []  # 累积输出行

    # 处理医院 + 周边服务复合结果
    if depth == 0 and data.get("hospital"):
        h = data["hospital"]
        lines.append(f"🏥 医院: {h.get('name')} | {h.get('address')} | 坐标:{h.get('location')}")

    # 处理 POI 列表（搜索/周边结果）
    if data.get("pois"):
        lines.append(f"共找到 {data.get('total', len(data['pois']))} 个地点（展示前5个）:")
        for p in data["pois"][:5]:
            lines.append(f"  • {p.get('name')} | {p.get('address','')} | "
                        f"距离:{p.get('distance','?')}米 | 评分:{p.get('rating','?')} | "
                        f"电话:{p.get('tel','?')}")

    # 处理周边设施分类（医院周边一站式查询结果）
    if data.get("services"):
        for cat, pois in data["services"].items():        # 遍历每个分类
            if pois:
                lines.append(f"\n🍽️🍜🏨🚇 {cat}（{len(pois)}个）:")
                for p in pois[:3]:                        # 每类最多 3 个
                    lines.append(f"  • {p.get('name')} | {p.get('address','')} | "
                                f"距离:{p.get('distance','?')}米 | 评分:{p.get('rating','?')}")

    # 处理驾车/步行路线
    if data.get("paths"):
        for i, path in enumerate(data["paths"][:1]):      # 只取第一条路线
            dist = int(path.get("distance", 0))            # 总距离（米）
            dur = int(path.get("duration", 0))             # 总耗时（秒）
            lines.append(f"🚗 路线: 距离{fmt_dist(dist)}, 预计{fmt_time(dur)}")
            steps = path.get("steps", [])[:3]              # 最多 3 个导航步骤
            for s in steps:
                lines.append(f"  → {s.get('instruction','')[:80]}")  # 截断过长指令

    # 处理公交方案
    if data.get("transits"):
        for t in data["transits"][:1]:                    # 只取第一条方案
            cost = t.get("cost", "")                       # 总费用
            dur = int(t.get("duration", 0))                # 总耗时
            lines.append(f"🚌 公交: 费用{cost}元, 预计{fmt_time(dur)}")

    # 如果以上都没有匹配到，回退到原始字符串（截断到 500 字符）
    return "\n".join(lines) if lines else str(data)[:500]


def fmt_dist(meters: int) -> str:
    """
    距离格式化 —— 米 → 人类可读

    例: 3500 → "3.5公里"
         800 → "800米"
    """
    if meters >= 1000:
        return f"{meters/1000:.1f}公里"    # 超过 1km 用公里显示
    return f"{meters}米"                    # 不足 1km 用米显示


def fmt_time(seconds: int) -> str:
    """
    时间格式化 —— 秒 → 人类可读

    例: 4500 → "1小时15分钟"
         180 → "3分钟"
          45 → "45秒"
    """
    if seconds >= 3600:                              # 超过 1 小时
        h = seconds // 3600                          # 小时数
        m = (seconds % 3600) // 60                   # 余下的分钟数
        return f"{h}小时{m}分钟" if m else f"{h}小时"
    if seconds >= 60:                                # 分钟级别
        return f"{seconds // 60}分钟"
    return f"{seconds}秒"                            # 秒级别

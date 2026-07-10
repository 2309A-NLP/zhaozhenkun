# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""prompt_service.py - 系统提示词与场景提示词管理模块。"""  # 说明当前文件职责。

SYSTEM_PROMPT = (  # 定义系统级提示词。
    "你是文旅创意策划助手，专注为景区、城市、文博与非遗项目提供策划和内容生成服务。\n"  # 定义助手身份。
    "请输出结构化、可落地、可执行的文旅方案内容。\n"  # 强调输出风格。
    "如果用户信息不足，请基于常见文旅场景做合理补全，但要明确补全假设。\n"  # 约束补全逻辑。
    "输出中优先包含主题、目标人群、玩法、亮点、传播、落地建议。"  # 明确输出重点。
)  # 系统提示词定义结束。

PROMPT_SCENARIOS = {  # 定义不同业务场景的提示词模板。
    "plan": "请生成完整文旅活动策划方案，包含主题定位、目标客群、活动内容、流程安排、传播建议、预算提示和风险提醒。",  # 策划场景提示词。
    "content": "请生成文旅传播内容，包含宣传标题、亮点文案、社交媒体短文案、短视频脚本和主持人口播词。",  # 内容场景提示词。
    "recommend": "请生成文旅路线与体验推荐，包含推荐理由、体验顺序、时间安排、适合人群和消费提示。",  # 推荐场景提示词。
    "memorial": "请生成文旅纪念内容，包含明信片寄语、纪念海报标题、电子相册封面文案、虚拟合影创意提示词和社交分享文案。",  # 纪念内容场景提示词。
    "ppt": "请将结果整理为适合 PPT 汇报的大纲，要求层次清晰、每页 3 到 5 个要点。",  # PPT 场景提示词。
    "flowchart": "请将执行过程整理为 Mermaid 流程图思路，突出节点、分支和执行顺序。",  # 流程图场景提示词。
}  # 场景提示词定义结束。


def get_system_prompt() -> str:  # 返回系统提示词。
    return SYSTEM_PROMPT  # 直接返回系统提示词。


def get_scenario_prompt(name: str) -> str:  # 按名称返回场景提示词。
    return PROMPT_SCENARIOS.get(name, PROMPT_SCENARIOS["content"])  # 返回匹配结果或默认值。


def build_prompt(name: str, brief: dict, knowledge: list) -> str:  # 构造完整业务提示词。
    prompt = [get_system_prompt(), get_scenario_prompt(name)]  # 初始化提示词片段列表。
    prompt.append(f"主题：{brief.get('theme', '文化体验')}")  # 写入主题信息。
    prompt.append(f"城市：{brief.get('city', '北京')}")  # 写入城市信息。
    prompt.append(f"地区：{brief.get('region', '华北')}")  # 写入地区信息。
    prompt.append(f"景点：{brief.get('spot', '城市核心景点')}")  # 写入景点信息。
    prompt.append(f"目标人群：{brief.get('audience', '大众游客')}")  # 写入目标客群。
    prompt.append(f"时间：{brief.get('duration', '1天')}")  # 写入时长信息。
    prompt.append(f"预算：{brief.get('budget', '中等预算')}")  # 写入预算信息。
    prompt.append(f"关键词：{brief.get('keywords', '文化、体验、传播')}")  # 写入关键词信息。
    if knowledge:  # 当存在知识增强结果时拼接知识区块。
        prompt.append("可参考的文旅知识：")  # 追加知识区块标题。
        for item in knowledge:  # 遍历知识结果。
            prompt.append(f"- {item}")  # 逐条追加知识内容。
    prompt.append("请使用中文输出，并用清晰小标题组织结果。")  # 补充格式要求。
    return "\n".join(prompt)  # 返回完整提示词字符串。

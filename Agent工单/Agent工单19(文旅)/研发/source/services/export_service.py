# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""export_service.py - PPT 大纲、流程图与方案包导出模块。"""  # 说明当前文件职责。


def generate_ppt_outline(plan_result: dict, content_result: dict) -> dict:  # 生成 PPT 大纲结构。
    slides = [  # 初始化幻灯片列表。
        {"title": "项目概述", "bullets": [plan_result["positioning"], f"主题：{plan_result['brief']['theme']}", f"城市：{plan_result['brief']['city']}"]},  # 第一页。
        {"title": "核心亮点", "bullets": plan_result["highlights"]},  # 第二页。
        {"title": "活动流程", "bullets": [item["detail"] for item in plan_result["activities"]]},  # 第三页。
        {"title": "传播内容", "bullets": content_result["highlights"]},  # 第四页。
        {"title": "执行建议", "bullets": plan_result["risk_tips"]},  # 第五页。
    ]  # 幻灯片列表结束。
    return {"topic": content_result["title"], "slides": slides}  # 返回 PPT 大纲结果。


def generate_flowchart(plan_result: dict) -> dict:  # 生成 Mermaid 流程图文本。
    mermaid = [  # 初始化 Mermaid 行列表。
        "flowchart TD",  # 声明流程图方向。
        "A[需求输入] --> B[主题与客群分析]",  # 定义第一段流程。
        "B --> C[活动内容策划]",  # 定义第二段流程。
        "C --> D[传播内容生成]",  # 定义第三段流程。
        "D --> E[路线与体验推荐]",  # 定义第四段流程。
        "E --> F[纪念内容生成]",  # 定义第五段流程。
        "F --> G[导出汇报材料]",  # 定义第六段流程。
        "G --> H[测试验收与优化]",  # 定义第七段流程。
    ]  # Mermaid 行列表结束。
    return {"topic": plan_result["brief"]["theme"], "mermaid": "\n".join(mermaid)}  # 返回流程图结果。


def build_download_filename(brief: dict, suffix: str = "完整方案包") -> str:  # 构造导出文件名。
    theme = str(brief.get("theme", "文旅方案")).replace("/", "-").replace(" ", "")  # 清洗主题字段。
    city = str(brief.get("city", "城市")).replace("/", "-").replace(" ", "")  # 清洗城市字段。
    return f"{city}-{theme}-{suffix}.md"  # 返回 Markdown 文件名。


def build_markdown_pack(brief: dict, plan_result: dict, content_result: dict, recommend_result: dict, memorial_result: dict, flowchart_result: dict) -> str:  # 生成完整 Markdown 方案包。
    lines = [  # 初始化 Markdown 行列表。
        f"# {brief['city']}{brief['theme']}完整方案包",  # 写入文档主标题。
        "",  # 写入空行。
        "## 1. 基本信息",  # 写入基本信息标题。
        f"- 主题：{brief['theme']}",  # 写入主题。
        f"- 城市：{brief['city']}",  # 写入城市。
        f"- 地区：{brief.get('region', '')}",  # 写入地区。
        f"- 景点：{brief.get('spot', '')}",  # 写入景点。
        f"- 目标人群：{brief['audience']}",  # 写入目标人群。
        f"- 时长：{brief['duration']}",  # 写入时长。
        f"- 预算：{brief['budget']}",  # 写入预算。
        f"- 关键词：{brief['keywords']}",  # 写入关键词。
        "",  # 写入空行。
        "## 2. 策划定位",  # 写入策划定位标题。
        plan_result["positioning"],  # 写入策划定位正文。
        "",  # 写入空行。
        "## 3. 策划长文",  # 写入策划长文标题。
        plan_result.get("plan_text", ""),  # 写入策划长文正文。
        "",  # 写入空行。
        "## 4. 核心亮点",  # 写入核心亮点标题。
    ]  # 初始化内容结束。
    for item in plan_result.get("highlights", []):  # 遍历策划亮点列表。
        lines.append(f"- {item}")  # 逐条写入策划亮点。
    lines.extend(["", "## 5. 活动流程"])  # 追加活动流程标题。
    for item in plan_result.get("activities", []):  # 遍历活动流程列表。
        lines.append(f"- {item['name']}：{item['detail']}")  # 逐条写入活动流程。
    lines.extend(["", "## 6. 传播内容", content_result.get("content_text", "")])  # 追加传播内容长文。
    lines.extend(["", "## 7. 路线推荐", recommend_result.get("recommendation_text", "")])  # 追加路线推荐长文。
    lines.extend(["", "## 8. 纪念内容", memorial_result.get("memorial_text", "")])  # 追加纪念内容长文。
    lines.extend(["", "## 9. 纪念内容结构化结果"])  # 追加纪念结构化标题。
    lines.append(f"- 明信片寄语：{memorial_result.get('postcard_text', '')}")  # 写入明信片寄语。
    lines.append(f"- 纪念海报标题：{memorial_result.get('poster_title', '')}")  # 写入纪念海报标题。
    lines.append(f"- 电子相册封面：{memorial_result.get('album_cover', '')}")  # 写入电子相册封面。
    lines.append(f"- 虚拟合影提示词：{memorial_result.get('virtual_photo_prompt', '')}")  # 写入虚拟合影提示词。
    lines.append(f"- 社交分享文案：{memorial_result.get('share_copy', '')}")  # 写入社交分享文案。
    lines.extend(["", "## 10. Mermaid 流程图", "```mermaid", flowchart_result.get("mermaid", ""), "```", ""])  # 追加流程图代码块。
    return "\n".join(lines)  # 返回完整 Markdown 文本。

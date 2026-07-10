# -*- coding: utf-8 -*-
# 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
# 功能说明：本文件是文旅智能体项目入口，用于展示项目信息、检查交付物完整性、列出核心功能模块。
"""
文旅智能体（文旅创新智脑）- Agent工单16 项目入口

目录结构（五分类交付）：
  设计/  - 需求分析与架构设计文档、产品原型说明
  研发/  - Python入口、HTML原型、AI分析结果
  测试/  - 验收清单
  优化/  - 项目调整说明
  部署/  - Kimi配置文件、运行说明
"""

import os  # 用于文件路径操作和存在性检查

# 项目根目录 = 当前文件所在目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # 获取1.py的绝对路径所在目录
WORK_ORDER_ID = "CV-AIGC-16"  # 工单编号


def print_banner():
    """打印项目欢迎横幅，显示项目名称、工单编号和版本信息"""
    # 使用等号分隔线（等宽字符，中英文混排不会错位）
    print("=" * 56)
    print("  🧠 文旅创新智脑 - AI智能体平台")
    print("  Cultural Tourism Innovation Brain")
    print("  工单编号: %s" % WORK_ORDER_ID)
    print("  版本: V1.1 | 2026-03-06")
    print("=" * 56)
    print()


def list_deliverables():
    """列出项目所有交付物并检查文件完整性，输出文件路径和大小"""
    # 定义交付物清单：类别名 -> 文件相对路径
    deliverables = {
        "需求分析与架构设计": "../设计/文旅智能体需求分析与软件架构设计.md",
        "产品原型说明": "../设计/产品原型说明.md",
        "交互原型HTML": "prototype/index.html",
        "DeepSeek技术选型分析": "llm_analysis_deepseek_tech_selection.json",
        "千问场景需求分析": "llm_analysis_qwen_scenario_analysis.json",
        "验收清单": "../测试/验收清单.md",
        "项目调整说明": "../优化/项目调整说明.md",
        "Kimi配置": "../部署/config/kimi_config.json",
        "运行说明": "../部署/README-运行说明.md",
    }

    print("📋 项目交付物清单：")
    for item_name, rel_path in deliverables.items():  # 遍历每个交付物
        full_path = os.path.join(PROJECT_ROOT, rel_path)  # 拼接绝对路径
        full_path = os.path.normpath(full_path)  # 规范化路径（处理../等）
        if os.path.exists(full_path):  # 检查文件是否存在
            size_kb = os.path.getsize(full_path) / 1024  # 计算文件大小(KB)
            print("  ✅ %s: %s (%.1f KB)" % (item_name, rel_path, size_kb))
        else:
            print("  ❌ %s: %s [缺失!]" % (item_name, rel_path))
    print()


def list_core_features():
    """列出文旅智能体的六大核心功能模块及简要描述"""
    features = [
        {"icon": "🤖", "name": "数字人智能导览", "desc": "高仿真数字人，多模态交互，实时讲解，拍照识物"},
        {"icon": "🔍", "name": "多模态知识检索", "desc": "以图搜文/以文搜图，知识图谱，RAG生成，OCR识别"},
        {"icon": "📊", "name": "智能管理运营", "desc": "客流分析，IoT监控，应急调度，数字孪生推演"},
        {"icon": "🎨", "name": "创意内容生成", "desc": "AIGC纪念照，PPT生成，活动策划，风格迁移"},
        {"icon": "💡", "name": "数据洞察决策", "desc": "多维分析，NL2SQL问答，政策仿真，竞争力评估"},
        {"icon": "⚡", "name": "五大快捷指令", "desc": "资源挖掘/场景创意/文化创新/数字营销/效益提升"},
    ]

    print("🎯 核心功能模块：")
    for f in features:  # 遍历每个功能模块
        print("  %s %s: %s" % (f["icon"], f["name"], f["desc"]))
    print()


if __name__ == "__main__":  # 仅当直接运行1.py时执行以下代码
    print_banner()  # 步骤1：打印项目横幅
    list_deliverables()  # 步骤2：列出并检查交付物完整性
    list_core_features()  # 步骤3：列出核心功能模块
    # 步骤4：提示用户如何查看各交付物
    print("🚀 打开HTML原型: 浏览器打开 研发/prototype/index.html")
    print("📖 查看设计文档: 设计/文旅智能体需求分析与软件架构设计.md")
    print("⚙️  Kimi配置: 部署/config/kimi_config.json")

"""工单19：教育智能体个性化学习推荐项目的演示种子数据。"""

# 工单19：定义课程基础信息。
COURSE = {
    "name": "人工智能NLP实战课",
    "description": "面向教育场景的NLP、RAG与Agent进阶课程。",
}

# 工单19：定义知识点及其前置关系，模拟知识图谱。
KNOWLEDGE_POINTS = [
    {"id": 1, "name": "Python基础", "description": "掌握语法、函数与数据结构。", "difficulty": 1, "prerequisites": []},
    {"id": 2, "name": "线性代数基础", "description": "理解向量、矩阵与相似度。", "difficulty": 1, "prerequisites": []},
    {"id": 3, "name": "NLP基础", "description": "理解文本预处理、分词与向量化。", "difficulty": 2, "prerequisites": [1, 2]},
    {"id": 4, "name": "Embedding", "description": "掌握词向量与语义检索。", "difficulty": 2, "prerequisites": [2, 3]},
    {"id": 5, "name": "Transformer", "description": "理解注意力机制与编码结构。", "difficulty": 3, "prerequisites": [3, 4]},
    {"id": 6, "name": "Prompt工程", "description": "学会设计结构化提示词。", "difficulty": 2, "prerequisites": [3]},
    {"id": 7, "name": "RAG应用", "description": "构建知识检索增强生成流程。", "difficulty": 3, "prerequisites": [4, 5, 6]},
    {"id": 8, "name": "Agent设计", "description": "设计具备规划与工具调用能力的智能体。", "difficulty": 4, "prerequisites": [5, 6, 7]},
]

# 工单19：定义课程资源，用于个性化推荐。
RESOURCES = [
    {"id": 1, "knowledge_id": 3, "title": "NLP基础微课", "type": "微课", "minutes": 18, "description": "快速梳理文本清洗、分词与向量化。"},
    {"id": 2, "knowledge_id": 4, "title": "Embedding案例实验", "type": "实验", "minutes": 26, "description": "通过语义检索案例理解向量空间。"},
    {"id": 3, "knowledge_id": 5, "title": "Transformer动画讲解", "type": "动画课", "minutes": 22, "description": "从注意力计算切入理解模型结构。"},
    {"id": 4, "knowledge_id": 6, "title": "Prompt模板手册", "type": "资料", "minutes": 15, "description": "掌握角色、任务、约束的模板化组织。"},
    {"id": 5, "knowledge_id": 7, "title": "RAG搭建实训", "type": "项目", "minutes": 35, "description": "完成检索、重排、生成的闭环实践。"},
    {"id": 6, "knowledge_id": 8, "title": "Agent协作案例", "type": "案例", "minutes": 30, "description": "理解多代理协同与任务分解方式。"},
]

# 工单19：定义助教常见问题，用于推荐解释与内容联动。
ASSISTANT_FAQS = [
    {"id": 1, "knowledge_id": 4, "question": "Embedding和关键词检索有什么区别？", "answer": "Embedding更关注语义相似度，适合表达多样的问法。"},
    {"id": 2, "knowledge_id": 5, "question": "Transformer为什么适合文本理解？", "answer": "它能建模长距离依赖并并行处理序列信息。"},
    {"id": 3, "knowledge_id": 7, "question": "RAG为什么比纯大模型问答更稳？", "answer": "因为它先检索外部知识，再让模型基于证据生成回答。"},
    {"id": 4, "knowledge_id": 8, "question": "Agent与普通问答机器人差别是什么？", "answer": "Agent会规划步骤、调用工具并持续根据状态调整行动。"},
]

# 工单19：定义题库，用于诊断、练习与错题本生成。
QUESTIONS = [
    {
        "id": 101,
        "knowledge_id": 3,
        "question": "下列哪一项最适合作为文本向量化前的预处理步骤？",
        "options": ["图像增强", "去除停用词", "添加水印", "视频抽帧"],
        "answer": "去除停用词",
        "difficulty": 1,
        "common_error": "混淆多模态预处理与文本预处理",
    },
    {
        "id": 102,
        "knowledge_id": 4,
        "question": "Embedding 在教育问答场景中的主要作用是什么？",
        "options": ["压缩视频", "表达语义相似度", "生成数据库索引名", "替代前端样式"],
        "answer": "表达语义相似度",
        "difficulty": 2,
        "common_error": "只从字面关键词理解检索机制",
    },
    {
        "id": 103,
        "knowledge_id": 5,
        "question": "Transformer 的核心注意力机制主要用于解决什么问题？",
        "options": ["增加屏幕亮度", "捕获序列中的关联关系", "减少网络带宽", "管理用户权限"],
        "answer": "捕获序列中的关联关系",
        "difficulty": 3,
        "common_error": "不知道模型为何能处理长距离依赖",
    },
    {
        "id": 104,
        "knowledge_id": 6,
        "question": "一个高质量 Prompt 最需要明确的内容是什么？",
        "options": ["显示器品牌", "任务目标和输出约束", "操作系统壁纸", "键盘背光颜色"],
        "answer": "任务目标和输出约束",
        "difficulty": 2,
        "common_error": "忽略提示词中的结构化约束",
    },
    {
        "id": 105,
        "knowledge_id": 7,
        "question": "RAG 工作流中，生成回答前最关键的一步是什么？",
        "options": ["随机换色", "检索相关知识", "格式化硬盘", "关闭日志"],
        "answer": "检索相关知识",
        "difficulty": 3,
        "common_error": "把生成模型当作唯一信息来源",
    },
    {
        "id": 106,
        "knowledge_id": 8,
        "question": "Agent 系统相较单轮问答的核心能力提升是什么？",
        "options": ["更换字体", "多步规划与工具调用", "提高屏幕分辨率", "缩短文件名"],
        "answer": "多步规划与工具调用",
        "difficulty": 4,
        "common_error": "无法区分普通聊天与智能体流程",
    },
]

# 工单19：定义学生基础信息。
STUDENTS = [
    {"id": 1, "name": "林晓", "level": "基础进阶", "target_role": "教育AI应用工程师"},
    {"id": 2, "name": "周越", "level": "项目冲刺", "target_role": "智能体产品研发"},
]

# 工单19：定义学生初始化画像分数。
INITIAL_MASTERY = {
    1: {1: 0.86, 2: 0.72, 3: 0.66, 4: 0.52, 5: 0.44, 6: 0.58, 7: 0.31, 8: 0.24},
    2: {1: 0.78, 2: 0.75, 3: 0.71, 4: 0.64, 5: 0.55, 6: 0.68, 7: 0.48, 8: 0.39},
}

# 工单19：定义练习趋势数据，用于前端图表展示。
TREND_SAMPLES = {
    1: [62, 66, 70, 74, 72, 79, 83],
    2: [70, 73, 75, 77, 80, 82, 86],
}

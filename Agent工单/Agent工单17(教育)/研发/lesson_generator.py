# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：智能备课核心引擎 - 教案/课件/习题/案例/试卷自动生成
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import json  # JSON数据处理
import uuid  # 唯一ID生成
from typing import List, Optional, Dict  # 类型提示

try:
    from openai import OpenAI  # OpenAI兼容客户端
except ImportError:
    OpenAI = None
from config import get_settings  # 系统配置
from knowledge_base import knowledge_base_service  # 知识库服务


class LessonGenerator:
    """智能备课生成器 - 使用大模型+知识库自动生成各类教学内容"""

    def __init__(self):
        """初始化备课生成器 - 配置DeepSeek和Qwen双模型客户端"""
        self.settings = get_settings()  # 获取系统配置
        self.deepseek_client = None
        self.qwen_client = None
        if OpenAI and self.settings.DEEPSEEK_API_KEY:
            self.deepseek_client = OpenAI(
                api_key=self.settings.DEEPSEEK_API_KEY,  # DeepSeek API密钥
                base_url=self.settings.DEEPSEEK_BASE_URL,  # DeepSeek API地址
                timeout=60.0,  # 生成任务超时60秒
            )
        if OpenAI and self.settings.QWEN_API_KEY:
            self.qwen_client = OpenAI(
                api_key=self.settings.QWEN_API_KEY,  # Qwen API密钥
                base_url=self.settings.QWEN_BASE_URL,  # Qwen API地址
                timeout=60.0,  # 生成任务超时60秒
            )
        self.knowledge_base = knowledge_base_service  # 知识库服务引用

    def _build_system_prompt(self, content_type: str) -> str:
        """构建系统提示词 - 根据内容类型返回专业的教育提示词模板"""
        prompts = {  # 不同内容类型的系统提示词字典
            "lesson_plan": (  # 教案提示词
                "你是一位资深教育专家和课程设计师。请根据提供的课程信息，生成一份结构完整、"
                "符合教学规范的专业教案。教案应包含：教学目标、教学重难点、教学过程（导入、"
                "新授、巩固、小结、作业）、板书设计、教学反思等环节。使用Markdown格式输出。"
            ),
            "courseware": (  # 课件提示词
                "你是一位教学演示设计专家。请根据课程信息设计一份PPT课件大纲，包含每一页"
                "幻灯片的标题、核心内容要点、建议的配图/动画说明、互动环节设计。"
                "输出格式为Markdown，每页用'## 第N页：标题'分隔。"
            ),
            "exercise": (  # 习题提示词
                "你是一位教学评估专家。请根据课程知识点设计一套分层次的练习题，包含："
                "基础题（选择题、填空题）50%、提高题（简答题）30%、拓展题（综合应用题）20%。"
                "每道题需标注知识点归属和难度等级，并附上参考答案和解析。Markdown格式输出。"
            ),
            "case_study": (  # 案例提示词
                "你是一位行业实践专家。请结合课程内容设计3-5个真实或模拟的教学案例，"
                "每个案例包含：背景描述、问题呈现、分析过程、解决方案、反思讨论。"
                "案例应贴近实际应用场景，具有启发性和可讨论性。Markdown格式输出。"
            ),
            "exam_paper": (  # 试卷提示词
                "你是一位命题专家。请设计一份标准化的考试试卷，包含：试卷说明（考试时间、"
                "满分、题型分布）、试题（按题型分组）、答题卡模板、评分标准。"
                "难度比例：基础40%、中等40%、困难20%。Markdown格式输出。"
            ),
        }
        return prompts.get(content_type, prompts["lesson_plan"])  # 返回对应提示词，默认教案

    def _call_llm(self, system_prompt: str, user_prompt: str,
                  use_deepseek: bool = True) -> str:
        """调用大模型API - 统一的大模型调用接口，支持DeepSeek和Qwen双模型"""
        client = self.deepseek_client if use_deepseek else self.qwen_client  # 选择客户端
        model = self.settings.DEEPSEEK_MODEL if use_deepseek else self.settings.QWEN_TEXT_MODEL  # 选择模型
        if client is None:
            return self._generate_fallback_content(system_prompt)
        try:
            response = client.chat.completions.create(  # 调用大模型Chat API
                model=model,  # 模型名称
                messages=[  # 消息列表
                    {"role": "system", "content": system_prompt},  # 系统提示词
                    {"role": "user", "content": user_prompt},  # 用户提示词
                ],
                temperature=self.settings.DEEPSEEK_TEMPERATURE,  # 温度参数
                max_tokens=self.settings.DEEPSEEK_MAX_TOKENS,  # 最大Token数
                stream=False,  # 非流式输出（批量生成场景）
            )
            return response.choices[0].message.content  # 返回生成的文本内容
        except Exception as e:  # API调用异常
            print(f"大模型API调用失败：{e}")  # 错误日志
            return self._generate_fallback_content(system_prompt)  # 降级返回模板内容

    def _call_llm_stream(self, system_prompt: str, user_prompt: str,
                         use_deepseek: bool = True):
        """流式调用大模型API - 逐步返回生成内容，支持实时进度反馈"""
        client = self.deepseek_client if use_deepseek else self.qwen_client  # 选择客户端
        model = self.settings.DEEPSEEK_MODEL if use_deepseek else self.settings.QWEN_TEXT_MODEL  # 选择模型
        if client is None:
            fallback = self._generate_fallback_content(system_prompt)
            yield fallback
            return
        try:
            stream = client.chat.completions.create(  # 调用流式Chat API
                model=model,  # 模型名称
                messages=[  # 消息列表
                    {"role": "system", "content": system_prompt},  # 系统提示词
                    {"role": "user", "content": user_prompt},  # 用户提示词
                ],
                temperature=self.settings.DEEPSEEK_TEMPERATURE,  # 温度参数
                max_tokens=self.settings.DEEPSEEK_MAX_TOKENS,  # 最大Token数
                stream=True,  # 启用流式输出
            )
            for chunk in stream:  # 逐块迭代流式响应
                if chunk.choices[0].delta.content:  # 当前块有内容
                    yield chunk.choices[0].delta.content  # 产出文本片段
        except Exception as e:  # API调用异常
            print(f"流式API调用失败：{e}")  # 错误日志
            # 降级返回模板内容
            fallback = self._generate_fallback_content(system_prompt)  # 获取模板
            yield fallback  # 产出降级内容
            return  # 结束生成器

    def generate_content_stream(self, course_info: dict, content_type: str,
                                use_knowledge_base: bool = True):
        """流式内容生成 - 逐步返回生成内容，适合前端实时展示"""
        rag_context = ""  # 初始化RAG上下文为空
        if use_knowledge_base:  # 启用了知识库检索
            search_query = (  # 构建检索查询
                f"{course_info.get('course_name', '')} {course_info.get('chapter', '')} "
                f"{course_info.get('teaching_objectives', '')}")  # 拼接课程信息
            rag_context = self.knowledge_base.get_rag_context(search_query, top_k=3)  # 检索知识库
        system_prompt = self._build_system_prompt(content_type)  # 系统提示词
        user_prompt = self._build_user_prompt(course_info, content_type, rag_context)  # 用户提示词
        # 流式产出内容
        full_content = []  # 累积完整内容
        for token in self._call_llm_stream(system_prompt, user_prompt):  # 流式调用
            full_content.append(token)  # 累积token
            yield token  # 产出当前token片段
        # 生成完成后返回完整结果元数据
        content_id = str(uuid.uuid4())  # 生成内容ID
        yield {  # 最后一次yield返回结构化元数据
            "__meta__": True,  # 标记为元数据
            "content_id": content_id,  # 内容ID
            "content_type": content_type,  # 内容类型
            "title": f"{course_info.get('course_name', '课程')}-{self._get_content_type_name(content_type)}",  # 标题
            "model_used": self.settings.DEEPSEEK_MODEL,  # 使用的模型
            "full_length": len("".join(full_content)),  # 完整内容长度
        }

    def _generate_fallback_content(self, prompt_hint: str) -> str:
        """降级内容生成 - 当API不可用时返回结构化的模板内容"""

        if "教案" in prompt_hint:  # 教案模板
            return (
                "# 教学设计方案\n\n## 一、教学目标\n- 知识与技能：掌握核心概念和基本方法\n- 过程与方法：通过案例分析和实践操作\n- 情感态度价值观：培养科学思维和创新意识\n\n"
                "## 二、教学重难点\n- 教学重点：核心知识点和基本理论\n- 教学难点：复杂概念理解和应用迁移\n\n## 三、教学过程\n### 1. 导入环节（5分钟）\n情境导入，激发兴趣\n"
                "### 2. 新授环节（30分钟）\n逐步讲解核心知识点\n### 3. 巩固练习（10分钟）\n课堂练习与即时反馈\n### 4. 课堂小结（5分钟）\n知识框架梳理\n"
                "## 四、板书设计\n核心概念 → 关键原理 → 典型应用\n## 五、教学反思\n待课后补充\n"
            )
        elif "课件" in prompt_hint:  # 课件模板
            return (
                "# 课件大纲\n\n## 第1页：封面\n课程标题、教师信息、日期\n\n## 第2页：学习目标\n列出本节课的学习目标\n\n## 第3页：导入\n情境或问题引入\n\n"
                "## 第4-6页：核心知识点1\n概念讲解+示例\n\n## 第7-9页：核心知识点2\n原理分析+演示\n\n## 第10页：课堂练习\n互动题目\n\n"
                "## 第11页：小结\n知识回顾\n\n## 第12页：课后作业\n练习布置\n"
            )
        return f"# 生成内容\n\n## 概述\n本内容基于课程信息自动生成。\n\n## 详细内容\n{prompt_hint[:200]}...\n"  # 通用模板

    def _build_user_prompt(self, course_info: dict, content_type: str,
                           rag_context: str = "") -> str:
        """构建用户提示词 - 将课程信息和RAG上下文组装为LLM输入"""
        prompt_parts = [  # 用户提示词各部分
            f"## 课程基本信息",  # 标题
            f"- 课程名称：{course_info.get('course_name', '未指定')}",  # 课程名
            f"- 章节：{course_info.get('chapter', '未指定')}",  # 章节
            f"- 适用年级：{course_info.get('grade_level', '未指定')}",  # 年级
            f"- 学科：{course_info.get('subject', '未指定')}",  # 学科
            f"- 课时数：{course_info.get('class_hours', 1)}课时",  # 课时
            f"\n## 教学目标",  # 教学目标标题
            course_info.get('teaching_objectives', '未提供教学目标'),  # 教学目标内容
        ]
        if course_info.get('key_points'):  # 有教学重点
            prompt_parts.append(f"\n## 教学重点\n{course_info['key_points']}")  # 添加重点
        if course_info.get('difficult_points'):  # 有教学难点
            prompt_parts.append(f"\n## 教学难点\n{course_info['difficult_points']}")  # 添加难点
        if rag_context:  # 有RAG检索上下文
            prompt_parts.append(f"\n## 参考资料（来自知识库）\n{rag_context}")  # 添加知识库参考
        prompt_parts.append(  # 最终指令
            f"\n## 任务\n请根据以上信息，生成一份完整的**{self._get_content_type_name(content_type)}**。"
            f"请确保内容专业、结构清晰、可直接用于教学。工单编号：{self.settings.WORK_ORDER_ID[:30]}"
        )
        return "\n".join(prompt_parts)  # 拼接所有部分

    def _get_content_type_name(self, content_type: str) -> str:
        """获取内容类型中文名 - 将枚举值转为中文显示名称"""
        type_names = {  # 类型映射字典
            "lesson_plan": "教案", "courseware": "课件",
            "exercise": "习题", "case_study": "教学案例", "exam_paper": "试卷",
        }
        return type_names.get(content_type, "教学内容")  # 返回中文名，默认"教学内容"

    def generate_content(self, course_info: dict, content_types: List[str],
                         use_knowledge_base: bool = True,
                         additional_instructions: Optional[str] = None) -> List[Dict]:
        """核心生成方法 - 根据课程信息和内容类型生成多个教学内容"""
        generated_contents = []  # 生成内容结果列表
        for content_type in content_types:  # 遍历每种需要生成的内容类型
            print(f"正在生成：{self._get_content_type_name(content_type)}...")  # 进度日志
            # 获取RAG上下文
            rag_context = ""  # 初始化RAG上下文为空
            if use_knowledge_base:  # 启用了知识库检索
                search_query = (  # 构建检索查询
                    f"{course_info.get('course_name', '')} {course_info.get('chapter', '')} "
                    f"{course_info.get('teaching_objectives', '')}")  # 拼接课程信息作为检索词
                rag_context = self.knowledge_base.get_rag_context(search_query, top_k=3)  # 检索知识库
            # 构建提示词
            system_prompt = self._build_system_prompt(content_type)  # 系统提示词
            user_prompt = self._build_user_prompt(course_info, content_type, rag_context)  # 用户提示词
            if additional_instructions:  # 有额外指令
                user_prompt += f"\n\n## 额外要求\n{additional_instructions}"  # 追加到用户提示词
            # 调用大模型生成
            raw_content = self._call_llm(system_prompt, user_prompt)  # 调用LLM生成内容
            # 构建生成结果
            content_id = str(uuid.uuid4())  # 生成唯一内容ID
            generated_content = {  # 构建内容字典
                "content_id": content_id,  # 内容ID
                "content_type": content_type,  # 内容类型
                "title": f"{course_info.get('course_name', '课程')}-{self._get_content_type_name(content_type)}",  # 标题
                "raw_content": raw_content,  # Markdown原始内容
                "structured_content": None,  # 结构化内容（预留）
                "references": self._extract_references(raw_content),  # 提取引用
                "generated_at": None,  # 生成时间（由调用方设置）
                "model_used": self.settings.DEEPSEEK_MODEL,  # 使用的模型
                "rag_context_used": bool(rag_context),  # 是否使用了RAG
            }
            generated_contents.append(generated_content)  # 添加到结果列表
        return generated_contents  # 返回所有生成内容

    def _extract_references(self, content: str) -> List[Dict]:
        """提取引用信息 - 从生成内容中识别并提取参考资料引用"""
        references = []  # 引用列表
        lines = content.split("\n")  # 按行分割
        for line in lines:  # 遍历每一行
            if "参考资料" in line or "参考文献" in line or "来源" in line:  # 查找引用标记行
                ref = {"title": line.strip("# ").strip(), "citation_text": line.strip()}  # 构建引用对象
                references.append(ref)  # 添加到列表
        return references  # 返回引用列表

    def generate_with_multimodal(self, course_info: dict, image_description: str) -> str:
        """多模态内容生成 - 使用Qwen多模态能力，基于图片描述辅助生成教学内容"""
        system_prompt = (  # 多模态系统提示词
            "你是一位教育技术专家，擅长将视觉材料转化为教学内容。"
            "请根据提供的图片描述和课程信息，设计一个包含图文互动的教学片段。"
        )
        user_prompt = (  # 多模态用户提示词
            f"课程：{course_info.get('course_name', '未指定')}\n"
            f"图片内容描述：{image_description}\n"
            f"请设计3-5分钟的互动教学片段，结合图片内容讲解知识点。"
        )
        return self._call_llm(system_prompt, user_prompt, use_deepseek=False)  # 使用Qwen生成

    def batch_generate_all(self, course_info: dict) -> Dict[str, List[Dict]]:
        """批量生成所有类型 - 一次性生成教案、课件、习题、案例四类内容"""
        all_types = ["lesson_plan", "courseware", "exercise", "case_study"]  # 所有内容类型
        results = {}  # 结果字典
        for content_type in all_types:  # 遍历所有类型
            contents = self.generate_content(course_info, [content_type])  # 生成单个类型
            if contents:  # 生成成功
                results[content_type] = contents  # 存入结果字典
                print(f"{self._get_content_type_name(content_type)}生成完成 ✓")  # 成功日志
        return results  # 返回所有生成结果

    def improve_content(self, original_content: str, improvement_request: str) -> str:
        """内容优化 - 根据教师反馈改进已生成的教学内容"""
        system_prompt = (  # 优化系统提示词
            "你是一位教学文案编辑专家。请根据用户要求对以下教学内容进行优化和改进。"
            "保持内容专业性和结构完整性。"
        )
        user_prompt = (  # 优化用户提示词
            f"## 原始内容\n{original_content}\n\n## 改进要求\n{improvement_request}\n\n"
            f"请输出优化后的完整内容。"
        )
        return self._call_llm(system_prompt, user_prompt)  # 调用LLM优化内容


# 全局备课生成器单例
lesson_generator = LessonGenerator()  # 创建全局唯一的备课生成器实例

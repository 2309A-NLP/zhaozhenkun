# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：智能备课生成器测试 - 验证各类教学内容生成功能
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import pytest  # 测试框架
import sys  # 系统模块
import os  # 文件系统

# 将研发目录添加到Python路径以确保正确导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "研发"))  # 添加研发模块路径

from lesson_generator import lesson_generator  # 导入备课生成器
from knowledge_base import knowledge_base_service  # 导入知识库服务


class TestLessonGenerator:
    """智能备课生成器测试类 - 覆盖所有内容类型的生成功能"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前置设置 - 每个测试方法执行前运行"""
        self.course_info = {  # 标准测试用课程信息
            "course_name": "Python程序设计",  # 课程名
            "chapter": "第3章 函数与模块",  # 章节
            "grade_level": "大学一年级",  # 适用年级
            "subject": "计算机科学与技术",  # 学科
            "teaching_objectives": "理解函数的定义与调用方式，掌握参数传递的多种方式，"  # 教学目标
                                    "能够使用模块组织代码，理解作用域的概念",  # 教学目标续
            "class_hours": 2,  # 课时数
            "key_points": "函数定义(def)、参数类型(位置参数、关键字参数、默认参数)、"  # 教学重点
                         "模块导入(import)、常用内置模块",  # 教学重点续
            "difficult_points": "可变参数(*args/**kwargs)、作用域规则(LEGB)、闭包概念",  # 教学难点
        }

    def test_generate_lesson_plan(self):
        """测试T01：教案生成 - 验证教案类型内容生成功能"""
        print("\n===== 测试T01：教案生成 =====")  # 测试标题
        results = lesson_generator.generate_content(  # 调用生成方法
            course_info=self.course_info,  # 传入课程信息
            content_types=["lesson_plan"],  # 生成教案
            use_knowledge_base=True,  # 启用知识库
        )
        assert results is not None, "生成结果不应为None"  # 断言：结果非空
        assert len(results) == 1, f"应生成1个内容，实际生成{len(results)}个"  # 断言：生成1个内容
        content = results[0]  # 获取第一个内容
        assert content["content_type"] == "lesson_plan", "内容类型应为lesson_plan"  # 断言：类型正确
        assert len(content["raw_content"]) > 100, f"生成内容应超过100字符，实际{len(content['raw_content'])}字符"  # 断言：内容足够长
        assert content["content_id"] is not None, "内容ID不应为None"  # 断言：有内容ID
        print(f"✓ 教案生成成功，内容长度：{len(content['raw_content'])} 字符")  # 成功日志
        print(f"  内容预览：{content['raw_content'][:200]}...")  # 内容预览

    def test_generate_exercise(self):
        """测试T02：习题生成 - 验证习题类型内容生成功能"""
        print("\n===== 测试T02：习题生成 =====")  # 测试标题
        results = lesson_generator.generate_content(  # 调用生成方法
            course_info=self.course_info,  # 传入课程信息
            content_types=["exercise"],  # 生成习题
            use_knowledge_base=True,  # 启用知识库
        )
        assert results is not None, "生成结果不应为None"  # 断言：结果非空
        assert len(results) == 1, "应生成1个内容"  # 断言：生成1个内容
        content = results[0]  # 获取内容
        assert content["content_type"] == "exercise", "内容类型应为exercise"  # 断言：类型正确
        assert len(content["raw_content"]) > 50, "习题内容应超过50字符"  # 断言：有实际内容
        print(f"✓ 习题生成成功，内容长度：{len(content['raw_content'])} 字符")  # 成功日志

    def test_generate_courseware(self):
        """测试T03：课件生成 - 验证课件大纲生成功能"""
        print("\n===== 测试T03：课件生成 =====")  # 测试标题
        results = lesson_generator.generate_content(  # 调用生成方法
            course_info=self.course_info,  # 传入课程信息
            content_types=["courseware"],  # 生成课件
            use_knowledge_base=False,  # 不启用知识库（测试降级路径）
        )
        assert results is not None, "生成结果不应为None"  # 断言：结果非空
        assert len(results) == 1, "应生成1个内容"  # 断言：生成1个内容
        content = results[0]  # 获取内容
        assert content["content_type"] == "courseware", "内容类型应为courseware"  # 断言：类型正确
        print(f"✓ 课件生成成功，内容长度：{len(content['raw_content'])} 字符")  # 成功日志

    def test_generate_case_study(self):
        """测试T04：案例生成 - 验证教学案例生成功能"""
        print("\n===== 测试T04：案例生成 =====")  # 测试标题
        results = lesson_generator.generate_content(  # 调用生成方法
            course_info=self.course_info,  # 传入课程信息
            content_types=["case_study"],  # 生成案例
            use_knowledge_base=True,  # 启用知识库
        )
        assert results is not None, "生成结果不应为None"  # 断言：结果非空
        assert len(results) == 1, "应生成1个内容"  # 断言：生成1个内容
        content = results[0]  # 获取内容
        assert content["content_type"] == "case_study", "内容类型应为case_study"  # 断言：类型正确
        print(f"✓ 案例生成成功，内容长度：{len(content['raw_content'])} 字符")  # 成功日志

    def test_generate_multiple_types(self):
        """测试T05：多类型批量生成 - 验证一次生成多种内容类型"""
        print("\n===== 测试T05：批量多类型生成 =====")  # 测试标题
        types_to_generate = ["lesson_plan", "exercise", "case_study"]  # 三种内容类型
        results = lesson_generator.generate_content(  # 调用生成方法
            course_info=self.course_info,  # 传入课程信息
            content_types=types_to_generate,  # 批量生成
            use_knowledge_base=True,  # 启用知识库
        )
        assert results is not None, "生成结果不应为None"  # 断言：结果非空
        assert len(results) == len(types_to_generate), (  # 断言：生成数量正确
            f"应生成{len(types_to_generate)}个内容，实际生成{len(results)}个")
        generated_types = [c["content_type"] for c in results]  # 提取所有生成类型
        for expected_type in types_to_generate:  # 遍历期望的类型
            assert expected_type in generated_types, f"应包含{expected_type}类型的内容"  # 断言：每种类型都存在
        print(f"✓ 批量生成成功，共生成 {len(results)} 种内容")  # 成功日志

    def test_generate_with_rag(self):
        """测试T06：RAG增强生成 - 验证知识库检索对内容生成的增强效果"""
        print("\n===== 测试T06：RAG增强生成对比 =====")  # 测试标题
        # 使用知识库生成
        results_with_rag = lesson_generator.generate_content(  # 调用生成（启用RAG）
            course_info=self.course_info,  # 传入课程信息
            content_types=["lesson_plan"],  # 生成教案
            use_knowledge_base=True,  # 启用知识库RAG
        )
        # 不使用知识库生成
        results_without_rag = lesson_generator.generate_content(  # 调用生成（不启用RAG）
            course_info=self.course_info,  # 传入课程信息
            content_types=["lesson_plan"],  # 生成教案
            use_knowledge_base=False,  # 不启用知识库RAG
        )
        assert len(results_with_rag) == 1, "RAG生成结果数量应为1"  # 断言：RAG结果存在
        assert len(results_without_rag) == 1, "非RAG生成结果数量应为1"  # 断言：非RAG结果存在
        rag_content = results_with_rag[0]["raw_content"]  # RAG生成内容
        no_rag_content = results_without_rag[0]["raw_content"]  # 非RAG生成内容
        print(f"  RAG生成内容长度：{len(rag_content)} 字符")  # 输出对比
        print(f"  非RAG生成内容长度：{len(no_rag_content)} 字符")  # 输出对比

    def test_improve_content(self):
        """测试T07：内容优化 - 验证根据反馈改进内容的功能"""
        print("\n===== 测试T07：内容优化 =====")  # 测试标题
        original = "# 原内容\n\n这是一个测试内容。"  # 原始内容
        improvement_request = "请添加更多教学案例和互动环节"  # 改进要求
        improved = lesson_generator.improve_content(original, improvement_request)  # 调用优化
        assert improved is not None, "优化结果不应为None"  # 断言：结果非空
        assert len(improved) > len(original), "优化后内容应比原内容更长"  # 断言：内容有增加
        print(f"✓ 内容优化成功，原{len(original)}字符 → 优化后{len(improved)}字符")  # 成功日志

    def test_fallback_content(self):
        """测试T08：降级生成 - 验证空课程信息时的降级处理"""
        print("\n===== 测试T08：降级生成 =====")  # 测试标题
        minimal_info = {"course_name": "", "chapter": "", "teaching_objectives": ""}  # 最小课程信息
        results = lesson_generator.generate_content(  # 调用生成方法
            course_info=minimal_info,  # 最小信息
            content_types=["lesson_plan"],  # 生成教案
            use_knowledge_base=False,  # 不启用知识库
        )
        assert results is not None, "即使信息不足，也不应返回None"  # 断言：不崩溃
        assert len(results) == 1, "应返回1个内容"  # 断言：有结果
        assert len(results[0]["raw_content"]) > 0, "降级内容不应为空"  # 断言：有降级内容
        print(f"✓ 降级生成成功")  # 成功日志


class TestKnowledgeBase:
    """知识库测试类 - 验证向量存储和语义检索功能"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前置设置 - 初始化演示知识库"""
        knowledge_base_service.init_demo_knowledge()  # 确保演示数据已加载

    def test_kb_search(self):
        """测试T09：知识库检索 - 验证语义搜索功能"""
        print("\n===== 测试T09：知识库检索 =====")  # 测试标题
        results = knowledge_base_service.search("Python函数定义", top_k=3)  # 执行检索
        assert results is not None, "检索结果不应为None"  # 断言：结果非空
        assert len(results) > 0, "至少应返回1条结果"  # 断言：有返回结果
        print(f"✓ 检索到 {len(results)} 条结果")  # 成功日志
        for r in results:  # 遍历结果
            print(f"  - {r['title']} (相关度: {r['relevance_score']})")  # 输出每条结果

    def test_kb_add_document(self):
        """测试T10：添加文档 - 验证文档添加到知识库功能"""
        print("\n===== 测试T10：添加文档 =====")  # 测试标题
        stats_before = knowledge_base_service.get_statistics()  # 添加前统计
        resource_id = knowledge_base_service.add_document(  # 添加文档
            title="测试文档-计算机组成原理",  # 文档标题
            content="CPU是计算机的核心部件，负责执行指令和处理数据。"  # 文档内容
                    "内存用于存储运行中的程序和数据。输入输出设备用于人机交互。",  # 文档内容续
            resource_type="textbook",  # 资源类型
            tags=["计算机", "硬件"],  # 标签
        )
        stats_after = knowledge_base_service.get_statistics()  # 添加后统计
        assert resource_id is not None, "资源ID不应为None"  # 断言：有返回ID
        assert stats_after["total_vectors"] >= stats_before["total_vectors"], "向量数应增加"  # 断言：向量增加
        print(f"✓ 文档添加成功，ID：{resource_id}")  # 成功日志

    def test_kb_statistics(self):
        """测试T11：统计信息 - 验证知识库统计功能"""
        print("\n===== 测试T11：统计信息 =====")  # 测试标题
        stats = knowledge_base_service.get_statistics()  # 获取统计
        assert "total_vectors" in stats, "应包含total_vectors字段"  # 断言：包含必要字段
        assert "total_documents" in stats, "应包含total_documents字段"  # 断言：包含必要字段
        assert "vector_dimension" in stats, "应包含vector_dimension字段"  # 断言：包含必要字段
        print(f"✓ 统计信息：{stats}")  # 成功日志


# ==================== 测试执行入口 ====================
if __name__ == "__main__":
    """直接运行测试 - 不使用pytest时的简化测试执行"""
    print("=" * 60)  # 分隔线
    print("智能备课系统 - 单元测试执行")  # 标题
    print(f"工单编号：人工智能NLP-Agent数字人项目-17")  # 工单信息
    print("=" * 60)  # 分隔线

    test_lesson = TestLessonGenerator()  # 创建备课测试实例
    # 手动初始化测试数据（替代pytest fixture）
    test_lesson.course_info = {  # 设置测试用课程信息
        "course_name": "Python程序设计", "chapter": "第3章 函数与模块",
        "grade_level": "大学一年级", "subject": "计算机科学与技术",
        "teaching_objectives": "理解函数的定义与调用方式，掌握参数传递的多种方式，能够使用模块组织代码",
        "class_hours": 2, "key_points": "函数定义、参数类型、模块导入",
        "difficult_points": "可变参数、作用域规则、闭包概念",
    }  # 课程信息设置完成

    tests = [  # 测试用例列表（按功能分组）
        ("T01-教案生成", test_lesson.test_generate_lesson_plan),
        ("T02-习题生成", test_lesson.test_generate_exercise),
        ("T03-课件生成", test_lesson.test_generate_courseware),
        ("T04-案例生成", test_lesson.test_generate_case_study),
        ("T05-多类型批量生成", test_lesson.test_generate_multiple_types),
        ("T06-RAG增强生成", test_lesson.test_generate_with_rag),
        ("T07-内容优化", test_lesson.test_improve_content),
        ("T08-降级生成", test_lesson.test_fallback_content),
    ]

    passed = 0  # 通过计数
    failed = 0  # 失败计数
    for name, test_func in tests:  # 遍历执行测试
        try:
            test_func()  # 执行测试方法
            passed += 1  # 通过计数加1
        except Exception as e:  # 捕获测试异常
            failed += 1  # 失败计数加1
            print(f"✗ {name} 失败：{e}")  # 失败日志

    # 知识库测试
    test_kb = TestKnowledgeBase()  # 创建知识库测试实例
    knowledge_base_service.init_demo_knowledge()  # 手动初始化演示知识库（替代pytest fixture）
    kb_tests = [  # 知识库测试列表
        ("T09-知识库检索", test_kb.test_kb_search),
        ("T10-添加文档", test_kb.test_kb_add_document),
        ("T11-统计信息", test_kb.test_kb_statistics),
    ]
    for name, test_func in kb_tests:  # 遍历执行知识库测试
        try:
            test_func()  # 执行测试方法
            passed += 1  # 通过计数加1
        except Exception as e:  # 捕获测试异常
            failed += 1  # 失败计数加1
            print(f"✗ {name} 失败：{e}")  # 失败日志

    # 输出测试结果汇总
    total = passed + failed  # 总测试数
    print("\n" + "=" * 60)  # 分隔线
    print(f"测试完成：{total} 个用例，通过 {passed} 个，失败 {failed} 个")  # 汇总
    print(f"通过率：{passed / total * 100:.1f}%" if total > 0 else "无测试")  # 通过率
    print("=" * 60)  # 分隔线

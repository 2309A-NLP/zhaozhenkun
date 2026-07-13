# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：API接口测试 - 验证所有REST API端点的功能和正确性
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import pytest  # 测试框架
import sys  # 系统模块
import os  # 文件系统
from fastapi.testclient import TestClient  # FastAPI测试客户端
import json  # JSON处理

# 添加研发模块到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "研发"))  # 添加路径

from main import app  # 导入FastAPI应用
from auth import auth_service  # 导入认证服务

# 创建测试客户端
client = TestClient(app)  # FastAPI测试客户端实例


class TestAuthAPI:
    """认证API测试类 - 验证登录和用户认证接口"""

    def test_login_success(self):
        """测试API-01：成功登录 - 正确的用户名密码应返回Token"""
        print("\n===== 测试API-01：成功登录 =====")  # 测试标题
        response = client.post(  # 发送POST请求
            "/api/v1/auth/login",  # 登录接口
            json={"username": "teacher01", "password": "123456"},  # 正确的凭据
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}"  # 断言：200状态码
        data = response.json()  # 解析响应
        assert data["code"] == 200, "业务状态码应为200"  # 断言：业务成功
        assert "access_token" in data["data"], "响应应包含access_token"  # 断言：包含token
        assert data["data"]["token_type"] == "bearer", "令牌类型应为bearer"  # 断言：token类型
        print(f"✓ 登录成功，Token：{data['data']['access_token'][:50]}...")  # 成功日志

    def test_login_failure(self):
        """测试API-02：登录失败 - 错误密码应返回401"""
        print("\n===== 测试API-02：登录失败 =====")  # 测试标题
        response = client.post(  # 发送POST请求
            "/api/v1/auth/login",  # 登录接口
            json={"username": "teacher01", "password": "wrong_password"},  # 错误密码
        )
        assert response.status_code == 401, f"期望401，实际{response.status_code}"  # 断言：401状态码
        print(f"✓ 登录失败正确处理，返回401")  # 成功日志

    def test_get_current_user(self):
        """测试API-03：获取当前用户 - 有效Token应返回用户信息"""
        print("\n===== 测试API-03：获取当前用户 =====")  # 测试标题
        # 先登录获取token
        login_resp = client.post(  # 登录请求
            "/api/v1/auth/login",
            json={"username": "teacher01", "password": "123456"},  # 正确凭据
        )
        token = login_resp.json()["data"]["access_token"]  # 提取Token
        # 使用Token请求用户信息
        response = client.get(  # 发送GET请求
            "/api/v1/auth/me",  # 用户信息接口
            headers={"Authorization": f"Bearer {token}"},  # 携带Token
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["data"]["username"] == "teacher01", "用户名应为teacher01"  # 断言：用户名正确
        assert data["data"]["role"] == "teacher", "角色应为teacher"  # 断言：角色正确
        print(f"✓ 获取用户信息成功：{data['data']['display_name']}")  # 成功日志

    def test_unauthorized_access(self):
        """测试API-04：未授权访问 - 无Token应返回401"""
        print("\n===== 测试API-04：未授权访问 =====")  # 测试标题
        response = client.get("/api/v1/auth/me")  # 不带Token访问
        assert response.status_code == 401, f"期望401，实际{response.status_code}"  # 断言：401
        print(f"✓ 未授权访问正确拒绝")  # 成功日志


class TestLessonPrepAPI:
    """智能备课API测试类 - 验证内容生成和导出接口"""

    def _get_auth_header(self):
        """辅助方法：获取认证头 - 登录并返回Bearer Token Header"""
        login_resp = client.post(  # 登录请求
            "/api/v1/auth/login",
            json={"username": "teacher01", "password": "123456"},  # 测试账号
        )
        token = login_resp.json()["data"]["access_token"]  # 提取Token
        return {"Authorization": f"Bearer {token}"}  # 返回认证头字典

    def test_generate_lesson_content(self):
        """测试API-05：生成教学内容 - 完整的备课生成API流程"""
        print("\n===== 测试API-05：生成教学内容 =====")  # 测试标题
        headers = self._get_auth_header()  # 获取认证头
        response = client.post(  # 发送POST请求
            "/api/v1/lesson-prep/generate",  # 备课生成接口
            json={  # 课程参数（POST body）
                "course_name": "Python程序设计",  # 课程名
                "chapter": "第3章 函数与模块",  # 章节
                "grade_level": "大学一年级",  # 年级
                "subject": "计算机科学与技术",  # 学科
                "teaching_objectives": "理解函数定义与调用，掌握参数传递方式",  # 教学目标
                "class_hours": 2,  # 课时
                "content_types": "lesson_plan,exercise",  # 生成类型
                "use_kb": True,  # 启用知识库
                "key_points": "函数定义、参数类型、模块导入",  # 重点
                "difficult_points": "作用域、闭包",  # 难点
            },
            headers=headers,  # 认证头
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}: {response.text}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["code"] == 200, f"业务成功，实际{data.get('code')}"  # 断言：业务成功
        contents = data["data"]["contents"]  # 提取内容列表
        assert len(contents) == 2, f"应生成2个内容，实际{len(contents)}"  # 断言：生成2个
        for c in contents:  # 遍历内容
            assert c["content_id"], "每个内容应有content_id"  # 断言：有ID
            assert c["raw_content"], "每个内容应有raw_content"  # 断言：有内容
            print(f"  ✓ {c['content_type']}: {len(c['raw_content'])} 字符")  # 输出详情
        print(f"✓ API生成成功，共{len(contents)}个内容")  # 成功日志

    def test_improve_content(self):
        """测试API-06：优化内容 - 验证内容改进API"""
        print("\n===== 测试API-06：优化内容 =====")  # 测试标题
        headers = self._get_auth_header()  # 获取认证头
        response = client.post(  # 发送POST请求
            "/api/v1/lesson-prep/improve",  # 内容优化接口
            json={  # 优化参数（POST body）
                "content_text": "# 测试教案\n教学目标：掌握函数。",  # 原始内容
                "improvement_request": "添加更多案例和互动环节",  # 改进要求
            },
            headers=headers,  # 认证头
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["code"] == 200, "业务状态码应为200"  # 断言：业务成功
        improved = data["data"]["improved_content"]  # 获取优化后内容
        assert len(improved) > 0, "优化后内容不应为空"  # 断言：有内容
        print(f"✓ 内容优化成功，新内容{len(improved)}字符")  # 成功日志

    def test_search_knowledge(self):
        """测试API-07：检索知识库 - 验证知识库检索API"""
        print("\n===== 测试API-07：检索知识库 =====")  # 测试标题
        headers = self._get_auth_header()  # 获取认证头
        response = client.post(  # 发送POST请求
            "/api/v1/knowledge/search",  # 知识库检索接口
            json={"query": "Python函数", "max_results": 5},  # 检索参数（POST body）
            headers=headers,  # 认证头
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["code"] == 200, "业务状态码应为200"  # 断言：业务成功
        print(f"✓ 检索成功，找到 {data['data']['total_found']} 条结果")  # 成功日志

    def test_health_check(self):
        """测试API-08：健康检查 - 验证健康检查接口（无需认证）"""
        print("\n===== 测试API-08：健康检查 =====")  # 测试标题
        response = client.get("/health")  # 发送GET请求（无需认证）
        assert response.status_code == 200, f"期望200，实际{response.status_code}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["status"] == "healthy", "服务状态应为healthy"  # 断言：健康状态
        assert "knowledge_base" in data["components"], "应包含knowledge_base组件状态"  # 断言：包含组件
        print(f"✓ 健康检查通过：{json.dumps(data, ensure_ascii=False)}")  # 成功日志

    def test_export_content(self):
        """测试API-09：导出内容 - 验证内容导出API"""
        print("\n===== 测试API-09：导出内容 =====")  # 测试标题
        headers = self._get_auth_header()  # 获取认证头
        # 准备测试内容JSON
        test_content = json.dumps([{  # 构建测试内容
            "content_id": "test_001",  # 测试内容ID
            "content_type": "lesson_plan",  # 内容类型
            "title": "测试教案-导出验证",  # 标题
            "raw_content": "# 测试教案\n## 教学目标\n掌握测试方法\n## 教学过程\n1. 导入\n2. 新授",  # 测试内容
        }])
        response = client.post(  # 发送POST请求
            "/api/v1/export/convert",  # 导出接口
            json={  # 导出参数（POST body）
                "content_json": test_content,  # 内容JSON
                "title": "测试导出",  # 标题
                "export_format": "markdown",  # 导出格式
            },
            headers=headers,  # 认证头
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}: {response.text}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["code"] == 200, "业务状态码应为200"  # 断言：业务成功
        print(f"✓ 导出成功，文件信息：{data['data']['files']}")  # 成功日志

    def test_version_list(self):
        """测试API-10：版本列表 - 验证版本管理API"""
        print("\n===== 测试API-10：版本列表 =====")  # 测试标题
        headers = self._get_auth_header()  # 获取认证头
        # 先生成内容以创建版本
        gen_resp = client.post(  # 生成内容
            "/api/v1/lesson-prep/generate",
            json={  # 课程参数（POST body）
                "course_name": "版本测试课程", "chapter": "第1章",  # 基本信息
                "grade_level": "大一", "subject": "计算机",
                "teaching_objectives": "测试版本管理功能的课程目标",  # 教学目标
                "content_types": "lesson_plan", "use_kb": False,  # 生成教案，不使用KB
            },
            headers=headers,  # 认证头
        )
        content_id = gen_resp.json()["data"]["contents"][0]["content_id"]  # 提取内容ID
        # 查询版本列表
        response = client.get(  # 发送GET请求
            f"/api/v1/version/versions/{content_id}",  # 版本列表接口
            headers=headers,  # 认证头
        )
        assert response.status_code == 200, f"期望200，实际{response.status_code}"  # 断言：200
        data = response.json()  # 解析响应
        assert data["data"]["total"] >= 1, "至少应有1个版本（初始生成的版本）"  # 断言：有版本
        print(f"✓ 版本列表获取成功，共 {data['data']['total']} 个版本")  # 成功日志


# ==================== 测试执行入口 ====================
if __name__ == "__main__":
    """直接运行测试 - 不使用pytest时的简化执行"""
    print("=" * 60)  # 分隔线
    print("智能备课系统 - API接口测试")  # 标题
    print(f"工单编号：人工智能NLP-Agent数字人项目-17")  # 工单信息
    print("=" * 60)  # 分隔线

    test_auth = TestAuthAPI()  # 认证测试实例
    test_lesson = TestLessonPrepAPI()  # 备课API测试实例

    all_tests = [  # 所有测试用例
        ("API-01-成功登录", test_auth.test_login_success),
        ("API-02-登录失败", test_auth.test_login_failure),
        ("API-03-获取用户", test_auth.test_get_current_user),
        ("API-04-未授权访问", test_auth.test_unauthorized_access),
        ("API-05-生成教学内容", test_lesson.test_generate_lesson_content),
        ("API-06-优化内容", test_lesson.test_improve_content),
        ("API-07-检索知识库", test_lesson.test_search_knowledge),
        ("API-08-健康检查", test_lesson.test_health_check),
        ("API-09-导出内容", test_lesson.test_export_content),
        ("API-10-版本列表", test_lesson.test_version_list),
    ]

    passed = 0  # 通过计数
    failed = 0  # 失败计数
    for name, test_func in all_tests:  # 遍历执行
        try:
            test_func()  # 执行测试
            passed += 1  # 通过+1
        except Exception as e:  # 捕获异常
            failed += 1  # 失败+1
            print(f"✗ {name} 失败：{e}")  # 失败日志

    total = passed + failed  # 总数
    print("\n" + "=" * 60)  # 分隔线
    print(f"API测试完成：{total} 个用例，通过 {passed} 个，失败 {failed} 个")  # 汇总
    print(f"通过率：{passed / total * 100:.1f}%" if total > 0 else "无测试")  # 通过率
    print("=" * 60)  # 分隔线

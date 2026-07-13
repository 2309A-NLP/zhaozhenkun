"""该文件用于测试智能体服务在离线模式下的基本编排能力。"""

# 导入系统模块，用于调整测试期间的环境变量。
import os
# 导入单元测试框架，用于组织断言逻辑。
import unittest

# 导入待测试的智能体服务对象。
from development.services.agent_service import AgentService


# 定义智能体服务测试类，用于验证主流程输出结构。
class AgentServiceTestCase(unittest.TestCase):
    # 在每个测试开始前清理密钥环境变量，确保走离线模式。
    def setUp(self) -> None:
        # 清理 DeepSeek 密钥环境变量，避免真实外部调用。
        os.environ.pop("DEEPSEEK_API_KEY", None)
        # 清理千问密钥环境变量，避免真实外部调用。
        os.environ.pop("QWEN_API_KEY", None)

    # 测试教育问答是否能返回结构化响应结果。
    def test_handle_returns_structured_response(self) -> None:
        # 初始化默认的智能体服务对象。
        service = AgentService(provider_name="deepseek")
        # 执行一次离线问答流程。
        response = service.handle("请讲解牛顿第二定律", session_id="test-session")
        # 校验领域识别结果是否符合教育场景预期。
        self.assertEqual(response.domain, "education")
        # 校验技能列表中是否包含知识点讲解技能。
        self.assertIn("skill_knowledge_point_explain", response.skills_used)
        # 校验最终答案是否为字符串内容。
        self.assertIsInstance(response.answer, str)
        # 校验技能执行结果列表不应为空。
        self.assertGreater(len(response.skill_results), 0)


# 在脚本被直接执行时启动单元测试。
if __name__ == "__main__":
    # 运行当前文件内的所有测试用例。
    unittest.main()

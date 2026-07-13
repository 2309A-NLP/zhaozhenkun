"""该文件用于测试服务入口的普通接口与流式接口行为。"""

# 导入 JSON 模块，用于解析 SSE 事件负载。
import json
# 导入单元测试框架，用于组织接口测试。
import unittest
# 导入补丁工具，用于替换真实服务调用。
from unittest.mock import patch

# 导入 FastAPI 测试客户端，用于调用 HTTP 接口。
from fastapi.testclient import TestClient

# 导入待测试的 FastAPI 应用对象。
from development.server.app import app


# 定义服务接口测试类，用于验证普通响应与流式响应。
class AppTestCase(unittest.TestCase):
    # 在每个测试开始前初始化测试客户端。
    def setUp(self) -> None:
        # 创建 FastAPI 测试客户端对象。
        self.client = TestClient(app)

    # 测试普通聊天接口是否返回结构化响应。
    def test_chat_endpoint(self) -> None:
        # 发起普通聊天请求。
        response = self.client.post("/chat", json={"query": "请讲解牛顿第二定律", "session_id": "api-test"})
        # 校验 HTTP 状态码是否正确。
        self.assertEqual(response.status_code, 200)
        # 解析响应 JSON 数据。
        payload = response.json()
        # 校验响应中是否存在答案字段。
        self.assertIn("answer", payload)
        # 校验响应中是否存在技能列表字段。
        self.assertIn("skills_used", payload)

    # 测试流式聊天接口是否按顺序返回事件。
    def test_chat_stream_endpoint(self) -> None:
        # 构造模拟的流式事件序列。
        fake_events = [
            {"type": "meta", "domain": "education", "skills_used": ["skill_memory"], "skill_results": [], "session_id": "stream-test"},
            {"type": "chunk", "content": "你好"},
            {"type": "done", "response": {"answer": "你好"}},
        ]
        # 使用补丁替换真实的流式编排方法。
        with patch("development.server.app.service.stream_handle", return_value=iter(fake_events)):
            # 发起流式聊天请求。
            response = self.client.post("/chat/stream", json={"query": "测试流式接口", "session_id": "stream-test"})
        # 校验 HTTP 状态码是否正确。
        self.assertEqual(response.status_code, 200)
        # 将返回文本按 SSE 空行分块。
        blocks = [item for item in response.text.split("\n\n") if item.strip()]
        # 校验是否至少收到三条事件。
        self.assertGreaterEqual(len(blocks), 3)
        # 解析首条 SSE 事件负载。
        first_payload = json.loads(blocks[0].replace("data: ", ""))
        # 校验首条事件类型应为元数据。
        self.assertEqual(first_payload["type"], "meta")


# 在脚本被直接执行时启动单元测试。
if __name__ == "__main__":
    # 运行当前文件内的所有测试用例。
    unittest.main()

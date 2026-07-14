"""文件功能：通过脚本串联本地主要接口，执行一次端到端烟雾验证。"""

from __future__ import annotations  # 启用延后类型注解支持。

import json  # 输出结构化结果。
import sys  # 调整脚本运行时的模块搜索路径。
from pathlib import Path  # 计算项目根目录路径。

from fastapi.testclient import TestClient  # 导入 FastAPI 测试客户端。

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 计算项目根目录。
if str(PROJECT_ROOT) not in sys.path:  # 如果项目根目录还未加入模块搜索路径。
    sys.path.insert(0, str(PROJECT_ROOT))  # 把项目根目录加入模块搜索路径。

from 研发.app import create_app  # 导入应用构造函数。
from 研发.bootstrap import get_container  # 导入服务容器获取函数。


def main() -> None:  # 执行烟雾测试主流程。
    import os  # 在函数内导入环境变量模块。
    os.environ["USE_MOCK_RESPONSE"] = "true"  # 强制开启模拟响应模式。
    get_container.cache_clear()  # 清空容器缓存，确保载入新的环境变量。
    client = TestClient(create_app())  # 创建接口测试客户端。
    persona = client.post("/api/personas", json={"name": "烟雾测试数字人"}).json()  # 创建数字人。
    asset = client.post("/api/assets/text", json={"name": "项目简介", "content_text": "这是一个用于验证主流程的烟雾测试素材。", "tags": ["smoke"]}).json()  # 创建文本素材。
    train = client.post("/api/training-jobs", json={"persona_id": persona["persona_id"], "asset_ids": [asset["asset_id"]]}).json()  # 创建训练任务。
    chat = client.post("/api/chat", json={"persona_id": persona["persona_id"], "question": "请给出项目简介"}).json()  # 发起问答请求。
    avatar = client.post("/api/avatar-jobs", json={"persona_id": persona["persona_id"], "session_id": chat["session_id"], "answer_text": chat["answer_text"]}).json()  # 创建数字人任务。
    result = {"persona": persona, "asset": asset, "training": train, "chat": chat, "avatar": avatar}  # 汇总整个烟雾测试结果。
    print(json.dumps(result, ensure_ascii=False, indent=2))  # 打印最终结构化输出。


if __name__ == "__main__":  # 如果当前脚本作为主程序运行。
    main()  # 执行烟雾测试流程。

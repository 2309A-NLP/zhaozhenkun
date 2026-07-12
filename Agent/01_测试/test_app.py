# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""test_app.py - 教育 Agent 页面与健康接口测试模块。"""  # 说明当前文件职责。

import sys  # 导入解释器路径工具。
from pathlib import Path  # 导入路径处理工具。


ROOT = Path(__file__).resolve().parents[1] / "03_研发"  # 定位研发源码目录。
sys.path.insert(0, str(ROOT))  # 将研发目录加入模块搜索路径。

from app import create_app  # 导入应用工厂函数。


def test_home_page_loads():  # 验证首页可以正常加载。
    app = create_app()  # 创建应用实例。
    client = app.test_client()  # 创建测试客户端。
    response = client.get("/")  # 请求首页地址。
    assert response.status_code == 200  # 断言首页响应状态为成功。
    assert "EduAgent Studio" in response.get_data(as_text=True)  # 断言页面包含应用标题。


def test_health_api():  # 验证健康检查接口可以正常返回。
    app = create_app()  # 创建应用实例。
    client = app.test_client()  # 创建测试客户端。
    response = client.get("/api/health")  # 请求健康检查接口。
    assert response.status_code == 200  # 断言接口响应状态为成功。
    data = response.get_json()  # 解析接口响应 JSON 数据。
    assert data["success"] is True  # 断言接口成功标识为真。
    assert "deepseek_text" in data["data"]  # 断言返回结果中包含 DeepSeek 文本模型状态。
    assert "qwen_vision" in data["data"]  # 断言返回结果中包含千问多模态模型状态。

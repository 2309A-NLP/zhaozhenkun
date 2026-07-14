"""文件功能：通过 FastAPI TestClient 验证健康检查、预检、素材、问答和数字人任务主链路。"""
from __future__ import annotations  # 启用延后类型注解支持。

import io  # 构造内存上传文件。
from pathlib import Path  # 处理测试运行目录路径。

from fastapi.testclient import TestClient  # 导入 FastAPI 测试客户端。

from 研发.app import create_app  # 导入应用构造函数。
from 研发.bootstrap import get_container  # 导入服务容器获取函数。


def build_client(tmp_path: Path) -> TestClient:  # 使用临时运行目录构建测试客户端。
    get_container.cache_clear()  # 清空全局容器缓存，确保读取新的环境变量。
    import os  # 在函数内导入环境变量模块。
    os.environ["USE_MOCK_RESPONSE"] = "true"  # 强制开启模拟响应模式。
    os.environ["RUNTIME_DIR"] = str(tmp_path / "runtime")  # 把运行目录指向临时路径。
    return TestClient(create_app())  # 返回新的测试客户端实例。


def test_health_and_readiness(tmp_path: Path) -> None:  # 验证健康检查接口与预检信息。
    client = build_client(tmp_path)  # 构建测试客户端。
    health = client.get("/health")  # 发起健康检查请求。
    readiness = client.get("/api/readiness")  # 发起预检状态请求。
    assert health.status_code == 200  # 断言健康检查状态码正确。
    assert health.json()["status"] == "ok"  # 断言返回状态为正常。
    assert readiness.status_code == 200  # 断言预检状态码正确。
    assert readiness.json()["mock_mode"] is True  # 断言当前默认处于 mock 模式。
    assert "checks" in readiness.json()  # 断言返回了结构化检查项。


def test_upload_and_binding_and_full_flow(tmp_path: Path) -> None:  # 验证上传、绑定、训练、问答与数字人任务全流程。
    client = build_client(tmp_path)  # 构建测试客户端。
    persona = client.post("/api/personas", json={"name": "测试数字人", "description": "测试用数字人", "voice_style": "自然", "motion_style": "自然"}).json()  # 创建数字人。
    asset = client.post("/api/assets/text", json={"name": "个人介绍", "content_text": "我是一个专注人工智能项目交付的数字人。", "tags": ["介绍"]}).json()  # 创建文本素材。
    upload_response = client.post(  # 上传一个文本文件素材。
        "/api/assets/upload",
        data={"asset_type": "document", "tags": "上传,测试"},
        files={"file": ("knowledge.txt", io.BytesIO("这是上传的知识文件。".encode("utf-8")), "text/plain")},
    )
    assert upload_response.status_code == 200  # 断言上传接口成功。
    uploaded_asset = upload_response.json()  # 读取上传素材结果。
    updated_persona = client.put(  # 绑定知识素材与头像素材。
        f"/api/personas/{persona['persona_id']}",
        json={"knowledge_asset_ids": [asset["asset_id"], uploaded_asset["asset_id"]], "avatar_image_asset_id": uploaded_asset["asset_id"]},
    )
    assert updated_persona.status_code == 200  # 断言数字人更新成功。
    preflight = client.post("/api/training-jobs/preflight", json={"persona_id": persona["persona_id"], "asset_ids": [uploaded_asset["asset_id"]]})  # 执行训练预检。
    assert preflight.status_code == 200  # 断言训练预检成功。
    assert "ready_for_current_mode" in preflight.json()  # 断言返回了当前模式可执行性。
    job = client.post("/api/training-jobs", json={"persona_id": persona["persona_id"], "asset_ids": [uploaded_asset["asset_id"]]}).json()  # 创建训练任务。
    assert job["status"] == "prepared"  # 断言训练任务已准备完成。
    personas = client.get("/api/personas").json()  # 读取最新数字人列表。
    persona_after_training = next(item for item in personas if item["persona_id"] == persona["persona_id"])  # 定位训练后的数字人。
    assert persona_after_training["ultralight_dataset_dir"]  # 断言训练数据目录已回写。
    assert persona_after_training["ultralight_checkpoint_path"]  # 断言训练权重路径已回写。
    chat = client.post("/api/chat", json={"persona_id": persona["persona_id"], "question": "请介绍一下你自己", "session_id": ""}).json()  # 发起问答请求。
    assert "answer_text" in chat and chat["answer_text"]  # 断言返回了有效答案。
    assert "knowledge_assets" in chat  # 断言返回了命中的知识素材。
    avatar_preflight = client.post("/api/avatar-jobs/preflight", json={"persona_id": persona["persona_id"]})  # 执行数字人任务预检。
    assert avatar_preflight.status_code == 200  # 断言数字人任务预检成功。
    avatar = client.post("/api/avatar-jobs", json={"persona_id": persona["persona_id"], "session_id": chat["session_id"], "answer_text": chat["answer_text"]}).json()  # 创建数字人输出任务。
    assert avatar["status"] == "prepared"  # 断言数字人任务已准备完成。
    assert avatar["script_text"]  # 断言生成了口播脚本。
    assert avatar["output_path"]  # 断言返回了输出路径。

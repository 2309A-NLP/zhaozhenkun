# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""test_app.py - 工单18智能助教接口测试模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from pathlib import Path  # 工单18：导入路径处理类。
import io  # 工单18：导入内存流模块。
import sys  # 工单18：导入系统模块。
import zipfile  # 工单18：导入压缩文件模块。

from fastapi.testclient import TestClient  # 工单18：导入 FastAPI 测试客户端。

ROOT_DIR = Path(__file__).resolve().parents[1] / "研发"  # 工单18：定位研发目录。
sys.path.insert(0, str(ROOT_DIR))  # 工单18：将研发目录加入导入路径。

from main import app  # type: ignore  # 工单18：导入被测应用对象。

client = TestClient(app)  # 工单18：创建测试客户端实例。


def login_response(username: str = "student01", password: str = "123456") -> dict:  # 工单18：获取测试登录响应内容。
    response = client.post("/api/auth/login", json={"username": username, "password": password})  # 工单18：调用登录接口。
    assert response.status_code == 200  # 工单18：断言登录接口返回成功。
    return response.json()["data"]  # 工单18：返回登录数据对象。


def login_token(username: str = "student01", password: str = "123456") -> str:  # 工单18：获取测试登录令牌。
    return login_response(username, password)["access_token"]  # 工单18：返回访问令牌。


def build_docx_bytes(text: str) -> bytes:  # 工单18：构造最小可解析 DOCX 测试文件。
    document_xml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"""  # 工单18：构造最小 Word 文档 XML。
    content_types = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>"""  # 工单18：构造 DOCX 内容类型声明。
    rels = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>"""  # 工单18：构造根关系文件。
    buffer = io.BytesIO()  # 工单18：创建内存字节流。
    with zipfile.ZipFile(buffer, "w") as archive:  # 工单18：写入最小 DOCX 文件结构。
        archive.writestr("[Content_Types].xml", content_types)  # 工单18：写入内容类型文件。
        archive.writestr("_rels/.rels", rels)  # 工单18：写入根关系文件。
        archive.writestr("word/document.xml", document_xml)  # 工单18：写入主文档 XML。
    return buffer.getvalue()  # 工单18：返回 DOCX 字节内容。


def test_health() -> None:  # 工单18：测试健康检查接口。
    response = client.get("/health")  # 工单18：调用健康检查接口。
    assert response.status_code == 200  # 工单18：断言健康检查成功。
    assert response.json()["status"] == "ok"  # 工单18：断言返回状态为 ok。


def test_login_and_dashboard() -> None:  # 工单18：测试登录与工作台接口。
    token = login_token()  # 工单18：先获取测试令牌。
    response = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})  # 工单18：调用工作台接口。
    assert response.status_code == 200  # 工单18：断言工作台接口成功。
    assert response.json()["data"]["role"] == "student"  # 工单18：断言学生身份生效。


def test_login_response_does_not_leak_password() -> None:  # 工单18：测试登录响应不再回传密码字段。
    data = login_response()  # 工单18：获取登录返回数据。
    assert "password" not in data["user"]  # 工单18：断言返回用户对象中不包含密码。


def test_add_text_and_search() -> None:  # 工单18：测试文本知识录入与检索。
    token = login_token()  # 工单18：先获取测试令牌。
    create_response = client.post("/api/knowledge/text", headers={"Authorization": f"Bearer {token}"}, json={"title": "测试知识", "scope": "private", "resource_type": "text", "content_text": "梯度下降是通过负梯度方向不断更新参数的优化算法。", "source_url": "", "tags": "测试,机器学习"})  # 工单18：调用文本知识创建接口。
    assert create_response.status_code == 200  # 工单18：断言创建接口成功。
    search_response = client.post("/api/assistant/ask", headers={"Authorization": f"Bearer {token}"}, json={"question": "什么是梯度下降", "model_provider": "deepseek", "top_k": 5, "use_public": True, "use_private": True})  # 工单18：调用助教问答接口以验证检索链路。
    assert search_response.status_code == 200  # 工单18：断言问答接口成功。
    assert search_response.json()["data"]["references"]  # 工单18：断言返回了检索参考结果。
    assert isinstance(search_response.json()["data"]["citations"], list)  # 工单18：断言返回了结构化引用列表。


def test_docx_upload_generates_location_chunks() -> None:  # 工单18：测试 DOCX 上传后生成结构化定位片段。
    token = login_token("teacher01", "123456")  # 工单18：获取教师登录令牌。
    response = client.post("/api/knowledge/file?scope=private&model_provider=qwen", headers={"Authorization": f"Bearer {token}"}, files={"file": ("lesson.docx", build_docx_bytes("函数单调性讲义"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})  # 工单18：上传最小 DOCX 文件。
    assert response.status_code == 200  # 工单18：断言 DOCX 上传成功。
    data = response.json()["data"]  # 工单18：读取上传响应数据。
    assert data["chunks"]  # 工单18：断言生成了结构化片段。
    assert data["chunks"][0]["location"]  # 工单18：断言片段中存在定位信息。


def test_private_resource_isolation() -> None:  # 工单18：测试私有知识资源隔离。
    teacher_token = login_token("teacher01", "123456")  # 工单18：获取教师令牌。
    student_token = login_token("student01", "123456")  # 工单18：获取学生令牌。
    create_response = client.post("/api/knowledge/text", headers={"Authorization": f"Bearer {teacher_token}"}, json={"title": "教师私有资源", "scope": "private", "resource_type": "text", "content_text": "只有教师自己能看到的备课内容。", "source_url": "", "tags": "教师"})  # 工单18：创建教师私有资源。
    assert create_response.status_code == 200  # 工单18：断言私有资源创建成功。
    list_response = client.get("/api/knowledge/list?scope=private", headers={"Authorization": f"Bearer {student_token}"})  # 工单18：使用学生身份读取私有资源列表。
    titles = [item["title"] for item in list_response.json()["data"]["items"]]  # 工单18：收集学生可见私有资源标题。
    assert "教师私有资源" not in titles  # 工单18：断言学生看不到教师私有资源。


def test_legacy_office_upload_returns_clear_error() -> None:  # 工单18：测试旧版 Office 格式返回明确提示。
    token = login_token()  # 工单18：获取测试登录令牌。
    response = client.post("/api/knowledge/file?scope=private&model_provider=qwen", headers={"Authorization": f"Bearer {token}"}, files={"file": ("legacy.doc", b"binary", "application/msword")})  # 工单18：上传旧版 DOC 文件。
    assert response.status_code == 200  # 工单18：当前接口返回应用层成功响应。
    assert response.json()["success"] is False  # 工单18：断言接口用 success=false 表示能力边界。
    assert "转换为 docx" in response.json()["message"]  # 工单18：断言返回了明确转换提示。

"""工单19：个性化学习推荐项目的核心功能测试。"""

# 工单19：导入 JSON 处理工具，便于验证接口返回结构。
import json

# 工单19：导入临时目录工具，隔离测试数据库。
import tempfile

# 工单19：导入路径工具，生成测试数据库文件路径。
from pathlib import Path

# 工单19：导入环境变量工具，允许测试指定独立数据库。
import os

# 工单19：导入路径注册工具，确保测试脚本可直接找到项目包。
import sys


# 工单19：把项目根目录加入模块搜索路径。
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 工单19：导入项目应用工厂。
from development.app import create_app


# 工单19：创建隔离测试客户端，避免污染正式数据。
def build_client():
    temp_dir = tempfile.TemporaryDirectory()
    os.environ["APP_DATABASE_PATH"] = str(Path(temp_dir.name) / "test.db")
    app = create_app()
    app.config["TESTING"] = True
    return temp_dir, app.test_client()


# 工单19：验证首页页面可以正常渲染。
def test_dashboard_page_renders():
    temp_dir, client = build_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "个性化学习推荐" in response.get_data(as_text=True)
    temp_dir.cleanup()


# 工单19：验证仪表盘接口包含核心模块数据。
def test_dashboard_api_contains_sections():
    temp_dir, client = build_client()
    response = client.get("/api/dashboard?student_id=1")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["student"]["name"] == "林晓"
    assert len(payload["mastery_levels"]) > 0
    assert len(payload["learning_path"]) > 0
    assert len(payload["resources"]) > 0
    temp_dir.cleanup()


# 工单19：验证提交练习后会返回结果并生成错题记录。
def test_submit_practice_generates_wrong_book():
    temp_dir, client = build_client()
    questions_response = client.get("/api/questions?student_id=1")
    questions = questions_response.get_json()["items"]
    answers = []
    for question in questions:
        wrong_option = next(option for option in question["options"] if option != "表达语义相似度") if question["question_id"] == 102 else question["options"][0]
        answers.append({"question_id": question["question_id"], "chosen_answer": wrong_option})
    response = client.post("/api/practice/submit", json={"student_id": 1, "answers": answers})
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["total"] == len(answers)
    assert payload["wrong"] >= 1
    temp_dir.cleanup()


# 工单19：允许通过原生 Python 执行测试文件。
def main():
    test_dashboard_page_renders()
    test_dashboard_api_contains_sections()
    test_submit_practice_generates_wrong_book()
    print(json.dumps({"status": "ok", "tests": 3}, ensure_ascii=False))


# 工单19：允许直接运行本文件完成最小测试闭环。
if __name__ == "__main__":
    main()

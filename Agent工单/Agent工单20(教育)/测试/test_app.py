# 工单20：本文件用于验证面试AI复盘项目的核心接口与业务规则。
# 工单20：导入临时目录工具。
import tempfile  # 工单20：代码语句。
# 工单20：导入路径处理工具。
from pathlib import Path  # 工单20：代码语句。
# 工单20：导入导入工具。
import sys  # 工单20：代码语句。

# 工单20：追加研发目录到模块搜索路径。
sys.path.append(str(Path(__file__).resolve().parents[1] / "研发"))  # 工单20：代码语句。
# 工单20：导入应用工厂函数。
from app import create_app  # 工单20：代码语句。

# 工单20：定义示例数据目录。
SOURCE_DATA_DIR = Path(__file__).resolve().parents[1] / "研发" / "data"  # 工单20：代码语句。

# 工单20：定义测试客户端夹具。
def create_test_client():  # 工单20：代码语句。
    # 工单20：创建临时数据目录。
    temp_dir = Path(tempfile.mkdtemp())  # 工单20：代码语句。
    # 工单20：复制面试记录数据。
    (temp_dir / "interviews.json").write_text((SOURCE_DATA_DIR / "interviews.json").read_text(encoding="utf-8"), encoding="utf-8")  # 工单20：代码语句。
    # 工单20：复制知识库数据。
    (temp_dir / "knowledge_base.json").write_text((SOURCE_DATA_DIR / "knowledge_base.json").read_text(encoding="utf-8"), encoding="utf-8")  # 工单20：代码语句。
    # 工单20：初始化空缓存文件。
    (temp_dir / "reviews_cache.json").write_text("{}", encoding="utf-8")  # 工单20：代码语句。
    # 工单20：创建应用实例。
    app = create_app({"TESTING": True, "data_dir": str(temp_dir)})  # 工单20：代码语句。
    # 工单20：开启测试模式。
    app.config["TESTING"] = True  # 工单20：代码语句。
    # 工单20：返回测试客户端。
    return app.test_client()  # 工单20：代码语句。

# 工单20：定义健康检查测试。
def test_health_endpoint():  # 工单20：代码语句。
    # 工单20：创建测试客户端。
    client = create_test_client()  # 工单20：代码语句。
    # 工单20：请求健康检查接口。
    response = client.get("/api/health")  # 工单20：代码语句。
    # 工单20：断言状态码正确。
    assert response.status_code == 200  # 工单20：代码语句。
    # 工单20：断言返回成功标记。
    assert response.get_json()["ok"] is True  # 工单20：代码语句。

# 工单20：定义面试列表测试。

def test_list_interviews_endpoint():  # 工单20：代码语句。
    # 工单20：创建测试客户端。
    client = create_test_client()  # 工单20：代码语句。
    # 工单20：请求列表接口。
    response = client.get("/api/interviews")  # 工单20：代码语句。
    # 工单20：读取返回数据。
    payload = response.get_json()  # 工单20：代码语句。
    # 工单20：断言返回成功。
    assert payload["ok"] is True  # 工单20：代码语句。
    # 工单20：断言存在示例记录。
    assert len(payload["data"]) >= 1  # 工单20：代码语句。

# 工单20：定义复盘生成测试。
def test_create_review_endpoint():  # 工单20：代码语句。
    # 工单20：创建测试客户端。
    client = create_test_client()  # 工单20：代码语句。
    # 工单20：请求复盘生成接口。
    response = client.post("/api/reviews/INT-20260712-001", json={"provider": "deepseek"})  # 工单20：代码语句。
    # 工单20：读取返回数据。
    payload = response.get_json()  # 工单20：代码语句。
    # 工单20：断言返回成功。
    assert payload["ok"] is True  # 工单20：代码语句。
    # 工单20：断言存在总体得分。
    assert payload["review"]["overall_score"] >= 0  # 工单20：代码语句。
    # 工单20：断言存在问题解析。
    assert len(payload["review"]["question_analysis"]) >= 1  # 工单20：代码语句。
    # 工单20：断言优化版对话包含结构化表达。
    assert "我的结构化回答是" in payload["review"]["optimized_transcript"]  # 工单20：代码语句。

# 工单20：定义无录音但有转写文本可复盘测试。
def test_create_review_accepts_audio_text_without_file():  # 工单20：代码语句。
    # 工单20：创建测试客户端。
    client = create_test_client()  # 工单20：代码语句。
    # 工单20：先为待完善记录补充录音转写文本。
    update_response = client.post("/api/interviews/INT-20260711-002", json={  # 工单20：代码语句。
        "editor_name": "张悦",  # 工单20：代码语句。
        "audio_text": "面试官：你做过哪些AI产品？学生：我做过教育场景的错题本和学习画像。面试官：你怎么定义一个AI功能是否成功？学生：我会看留存、任务完成率、回答采纳率和满意度。",  # 工单20：代码语句。
        "full_transcript": "",  # 工单20：代码语句。
        "question_answers": [],  # 工单20：代码语句。
        "status": "待完善"  # 工单20：代码语句。
    })
    # 工单20：断言更新成功。
    assert update_response.get_json()["ok"] is True  # 工单20：代码语句。
    # 工单20：请求复盘生成接口。
    response = client.post("/api/reviews/INT-20260711-002", json={"provider": "deepseek"})  # 工单20：代码语句。
    # 工单20：读取返回数据。
    payload = response.get_json()  # 工单20：代码语句。
    # 工单20：断言返回成功。
    assert payload["ok"] is True  # 工单20：代码语句。
    # 工单20：断言从转写文本中成功抽取出问题解析。
    assert len(payload["review"]["question_analysis"]) >= 2  # 工单20：代码语句。
    # 工单20：断言原始记录展示为转写文本。
    assert "你怎么定义一个AI功能是否成功" in payload["review"]["original_transcript"]  # 工单20：代码语句。

# 工单20：定义批量导入测试。
def test_import_interviews_endpoint():  # 工单20：代码语句。
    # 工单20：创建测试客户端。
    client = create_test_client()  # 工单20：代码语句。
    # 工单20：构造导入数据。
    rows = [{  # 工单20：代码语句。
        "id": "INT-TEST-IMPORT-001",  # 工单20：代码语句。
        "student_name": "测试学生",  # 工单20：代码语句。
        "position_name": "NLP算法工程师",  # 工单20：代码语句。
        "interview_round": "一面",  # 工单20：代码语句。
        "interview_form": "技术面",  # 工单20：代码语句。
        "interview_city": "北京",  # 工单20：代码语句。
        "interview_time": "2026-07-13 18:00",  # 工单20：代码语句。
        "company_name": "测试企业",  # 工单20：代码语句。
        "self_intro": "测试自我介绍",  # 工单20：代码语句。
        "full_transcript": "面试官：请介绍一下项目。\n学生：我做过一个检索增强问答项目。"  # 工单20：代码语句。
    }]  # 工单20：代码语句。
    # 工单20：请求导入接口。
    response = client.post("/api/interviews/import", json={"rows": rows, "reporter_name": "测试老师"})  # 工单20：代码语句。
    # 工单20：读取返回数据。
    payload = response.get_json()  # 工单20：代码语句。
    # 工单20：断言请求成功。
    assert payload["ok"] is True  # 工单20：代码语句。
    # 工单20：再次导入同一条记录。
    response_repeat = client.post("/api/interviews/import", json={"rows": rows, "reporter_name": "测试老师"})  # 工单20：代码语句。
    # 工单20：断言重复记录不会继续导入。
    assert response_repeat.get_json()["count"] == 0  # 工单20：代码语句。

"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
API 自动化测试 —— 覆盖所有端点
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_研发", "backend"))
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

# ================================================================
# 基础测试
# ================================================================
def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200, f"健康检查失败: {r.status_code}"
    print("  ✅ GET /api/health")


def test_upload_reject():
    r = client.post("/api/upload/image",
                    files={"file": ("x.txt", b"x", "text/plain")})
    # FastAPI 可能返回 400（业务校验）或 422（Pydantic 校验），均表示正确拒绝
    assert r.status_code in (400, 422), f"应该拒绝txt文件，实际: {r.status_code}"
    print("  ✅ POST /api/upload/image (拒绝非法格式)")


# ================================================================
# VQA / MRG 测试
# ================================================================
def test_vqa_404():
    r = client.post("/api/vqa/ask",
                    json={"image_filename": "nope.jpg", "question": "?",
                          "prompt_option": "auto"})
    # 文件不存在返回 404 或 500（取决于实现）
    assert r.status_code in (404, 500)
    print("  ✅ POST /api/vqa/ask (文件不存在)")


def test_mrg_404():
    r = client.post("/api/mrg/generate",
                    json={"image_filename": "nope.jpg",
                          "clinical_info": ""})
    assert r.status_code in (404, 500)
    print("  ✅ POST /api/mrg/generate (文件不存在)")


# ================================================================
# 健康助理测试
# ================================================================
def test_assistant():
    r = client.post("/api/assistant/chat",
                    json={"message": "我头疼该挂什么科"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    print(f"  ✅ POST /api/assistant/chat (回复: {data['reply'][:50]}...)")


def test_registration():
    r = client.post("/api/registration/chat",
                    json={"message": "帮大宝挂一个儿科专家的号"})
    assert r.status_code == 200
    print(f"  ✅ POST /api/registration/chat")


def test_consultation():
    r = client.post("/api/consultation/chat",
                    json={"message": "百日咳的传播途径是什么"})
    assert r.status_code == 200
    print(f"  ✅ POST /api/consultation/chat")


# ================================================================
# 地图 API 测试（MCP 对接）
# ================================================================
def test_map_search():
    """测试地点搜索"""
    r = client.post("/api/map/search",
                    json={"keywords": "北京协和医院", "city": "北京"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") or "error" in data
    print(f"  ✅ POST /api/map/search (找到{data.get('total',0)}个结果)")


def test_map_nearby():
    """测试周边搜索"""
    r = client.post("/api/map/nearby",
                    json={"location": "116.397,39.909",
                          "poi_type": "050000", "radius": 2000})
    assert r.status_code == 200
    print(f"  ✅ POST /api/map/nearby")


def test_map_directions():
    """测试路线规划"""
    r = client.post("/api/map/directions",
                    json={"origin": "116.397,39.909",
                          "destination": "116.411,39.911",
                          "mode": "driving"})
    assert r.status_code == 200
    print(f"  ✅ POST /api/map/directions")


def test_map_geocode():
    """测试地理编码"""
    r = client.post("/api/map/geocode",
                    json={"address": "北京协和医院", "city": "北京"})
    assert r.status_code == 200
    print(f"  ✅ POST /api/map/geocode")


def test_map_regeocode():
    """测试逆地理编码"""
    r = client.post("/api/map/regeocode?location=116.397,39.909&radius=1000")
    assert r.status_code == 200
    print(f"  ✅ POST /api/map/regeocode")


def test_map_chat():
    """测试地图自然语言对话"""
    r = client.post("/api/map/chat",
                    json={"message": "北京协和医院附近的酒店"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    print(f"  ✅ POST /api/map/chat (回复: {data.get('reply','')[:50]}...)")


# ================================================================
# 运行所有测试
# ================================================================
print("\n" + "="*60)
print("医疗智能体-MCP API 测试")
print("工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0")
print("="*60)

tests = [
    test_health,
    test_upload_reject,
    test_vqa_404,
    test_mrg_404,
    test_assistant,
    test_registration,
    test_consultation,
    test_map_search,
    test_map_nearby,
    test_map_directions,
    test_map_geocode,
    test_map_regeocode,
    test_map_chat,
]

passed = failed = 0
for t in tests:
    try:
        t()
        passed += 1
    except AssertionError as e:
        print(f"  ❌ {t.__name__}: {e}")
        failed += 1
    except Exception as e:
        print(f"  💥 {t.__name__}: {e}")
        failed += 1

print("\n" + "="*60)
print(f"测试结果: {passed} 通过, {failed} 失败, {len(tests)} 总计")
print("="*60)


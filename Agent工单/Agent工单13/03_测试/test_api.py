"""API 测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_研发", "backend"))
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def test_health():
    assert client.get("/api/health").status_code == 200
def test_upload_reject():
    assert client.post("/api/upload/image", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 400
def test_vqa_404():
    assert client.post("/api/vqa/ask", json={"image_filename": "nope.jpg", "question": "?"}).status_code == 404
def test_mrg_404():
    assert client.post("/api/mrg/generate", json={"image_filename": "nope.jpg"}).status_code == 404

print("✅ 所有测试通过" if all([
    test_health(), test_upload_reject(), test_vqa_404(), test_mrg_404()
]) is None else "done")

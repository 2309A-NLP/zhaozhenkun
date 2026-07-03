"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
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
    assert r.status_code == 200
    print("  ✅ GET /api/health")

def test_upload_reject():
    r = client.post("/api/upload/image",
                    files={"file": ("x.txt", b"x", "text/plain")})
    assert r.status_code in (400, 422)
    print("  ✅ POST /api/upload/image (拒绝非法格式)")

# ================================================================
# VQA / MRG
# ================================================================
def test_vqa_404():
    r = client.post("/api/vqa/ask",
                    json={"image_filename": "nope.jpg", "question": "?"})
    assert r.status_code in (404, 500)
    print("  ✅ POST /api/vqa/ask")

def test_mrg_404():
    r = client.post("/api/mrg/generate",
                    json={"image_filename": "nope.jpg"})
    assert r.status_code in (404, 500)
    print("  ✅ POST /api/mrg/generate")

# ================================================================
# 健康助理
# ================================================================
def test_assistant():
    r = client.post("/api/assistant/chat",
                    json={"message": "头疼挂什么科"})
    assert r.status_code == 200
    print(f"  ✅ POST /api/assistant/chat")

def test_registration():
    r = client.post("/api/registration/chat",
                    json={"message": "帮大宝挂儿科专家"})
    assert r.status_code == 200
    print("  ✅ POST /api/registration/chat")

def test_consultation():
    r = client.post("/api/consultation/chat",
                    json={"message": "百日咳传播途径"})
    assert r.status_code == 200
    print("  ✅ POST /api/consultation/chat")

# ================================================================
# 🆕 实时语音识别
# ================================================================
def test_asr_process():
    """测试后处理转录文本"""
    r = client.post("/api/asr/process",
                    json={"transcript": "医生：你好，今天感觉怎么样？患者：头疼三天了。医生：先拍个CT。"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") or "raw" in data
    print(f"  ✅ POST /api/asr/process (DeepSeek后处理)")

def test_asr_translate():
    """测试翻译"""
    r = client.post("/api/asr/translate",
                    json={"text": "你好，我今天头疼", "target_lang": "英文"})
    assert r.status_code == 200
    print("  ✅ POST /api/asr/translate")

def test_asr_task_create():
    """测试创建后处理任务"""
    r = client.post("/api/asr/task/create",
                    json={"transcript": "测试转录文本"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("success")
    print(f"  ✅ POST /api/asr/task/create (task_id={data.get('task_id','?')})")

def test_asr_task_poll():
    """测试轮询任务"""
    # 先创建任务
    cr = client.post("/api/asr/task/create",
                     json={"transcript": "轮询测试"})
    task_id = cr.json().get("task_id", "unknown")

    # 轮询
    r = client.get(f"/api/asr/task/{task_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("processing", "done", "error")
    print(f"  ✅ GET /api/asr/task/{task_id} (status={data['status']})")

def test_asr_callback():
    """测试回调接收"""
    r = client.post("/api/asr/callback",
                    json={"task_id": "test123", "status": "completed",
                          "result": {"summary": "测试摘要"}})
    assert r.status_code == 200
    print("  ✅ POST /api/asr/callback (回调接收)")

def test_tingwu_create():
    """测试通义听悟 CreateTask（官方规范）"""
    r = client.post("/api/asr/tingwu/create?audio_url=https://example.com/audio.mp3")
    assert r.status_code == 200
    data = r.json()
    print(f"  ✅ POST /api/asr/tingwu/create (task_id={data.get('task_id','?')})")

def test_tingwu_get_task():
    """测试通义听悟 GetTaskInfo（官方规范）"""
    # 先创建
    cr = client.post("/api/asr/tingwu/create?audio_url=https://example.com/test.mp3")
    task_id = cr.json().get("task_id", "unknown")
    r = client.get(f"/api/asr/tingwu/{task_id}")
    assert r.status_code == 200
    print(f"  ✅ GET /api/asr/tingwu/{task_id}")

def test_voice_pipeline():
    """测试数字人语音管线"""
    r = client.post("/api/asr/voice",
                    json={"text": "我头疼三天了，该吃什么药",
                          "enable_tts": True, "voice": "xiaoxiao"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("success")
    has_audio = bool(data.get("audio_b64"))
    print(f"  ✅ POST /api/asr/voice (TTS={'✅' if has_audio else '⚠️ 静默'}, 回复={data.get('text','')[:30]}...)")

def test_avatar_list():
    """测试形象列表"""
    r = client.get("/api/avatar/list")
    assert r.status_code == 200
    print("  ✅ GET /api/avatar/list")

def test_avatar_speak():
    """测试数字人说话（无照片，应返回400）"""
    r = client.post("/api/avatar/speak",
                    json={"avatar_id": "nonexistent", "question": "测试"})
    assert r.status_code == 400  # 无此形象
    print("  ✅ POST /api/avatar/speak (无形象拒绝)")

def test_map_search():
    r = client.post("/api/map/search",
                    json={"keywords": "协和医院", "city": "北京"})
    assert r.status_code == 200
    print("  ✅ POST /api/map/search")

def test_map_nearby():
    r = client.post("/api/map/nearby",
                    json={"location": "116.397,39.909", "poi_type": "050000"})
    assert r.status_code == 200
    print("  ✅ POST /api/map/nearby")

def test_map_directions():
    r = client.post("/api/map/directions",
                    json={"origin": "116.397,39.909",
                          "destination": "116.415,39.912", "mode": "driving"})
    assert r.status_code == 200
    print("  ✅ POST /api/map/directions")

def test_map_chat():
    r = client.post("/api/map/chat",
                    json={"message": "北京协和医院附近的酒店"})
    assert r.status_code == 200
    print("  ✅ POST /api/map/chat")

# ================================================================
# 运行
# ================================================================
print("\n" + "="*60)
print("医疗智能体-实时语音识别 API 测试")
print("工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0")
print("="*60)

tests = [
    test_health, test_upload_reject,
    test_vqa_404, test_mrg_404,
    test_assistant, test_registration, test_consultation,
    test_asr_process, test_asr_translate,
    test_asr_task_create, test_asr_task_poll, test_asr_callback,
    test_tingwu_create, test_tingwu_get_task, test_voice_pipeline,
    test_avatar_list, test_avatar_speak,
    test_map_search, test_map_nearby, test_map_directions, test_map_chat,
]

passed = failed = 0
for t in tests:
    try:
        t()
        passed += 1
    except Exception as e:
        print(f"  ❌ {t.__name__}: {e}")
        failed += 1

print("\n" + "="*60)
print(f"测试结果: {passed} 通过, {failed} 失败, {len(tests)} 总计")
print("="*60)

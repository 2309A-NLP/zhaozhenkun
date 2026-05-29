# ADSD 多角色对话系统 — 测试文档

## 1. 测试方法论

本项目采用分层测试策略：单元测试 → 集成测试 → 系统测试 → 性能压测。

## 2. 单元测试

### 2.1 工具模块测试

```python
# test_utils.py
import pytest
from online.utils import normalize_username, tokenize_text, cosine_similarity_np

class TestNormalizeUsername:
    def test_basic(self):
        assert normalize_username("  TestUser  ") == "testuser"
        assert normalize_username("Admin@123") == "admin123"
        assert normalize_username("") == "guest"

class TestTokenizeText:
    def test_chinese(self):
        tokens = tokenize_text("今天天气真好")
        assert len(tokens) > 0
        assert isinstance(tokens, list)

class TestCosineSimilarity:
    def test_identical(self):
        assert cosine_similarity_np([1,0,0], [1,0,0]) == 1.0
    def test_orthogonal(self):
        assert cosine_similarity_np([1,0], [0,1]) == 0.0
```

### 2.2 短期记忆测试

```python
# test_short_term_memory.py
from online.short_term_memory import ShortTermMemory

def test_max_turns():
    mem = ShortTermMemory(max_turns=3)
    mem.add("user", "1")
    mem.add("assistant", "a")
    mem.add("user", "2")
    mem.add("assistant", "b")
    ctx = mem.get_context()
    # 应该只保留最后 3 轮
    assert "1" not in ctx
    assert "2" in ctx

def test_clear():
    mem = ShortTermMemory()
    mem.add("user", "hello")
    mem.clear()
    assert mem.get_context() == ""
```

### 2.3 输出优化器测试

```python
# test_output_optimizer.py
from online.output_optimizer import LLMOutputOptimizer

def test_remove_taohua():
    opt = LLMOutputOptimizer()
    result = opt.optimize(
        "总的来说，综上所述，我们需要注意以下几点。",
        "怎么办？",
        []
    )
    assert "总的来说" not in result
    assert "综上所述" not in result

def test_short_question_truncation():
    opt = LLMOutputOptimizer()
    long_answer = "A" * 500
    result = opt.optimize(long_answer, "你好", [])
    assert len(result) < len(long_answer)  # 简答应截断
```

### 2.4 会话管理器测试

```python
# test_session_manager.py
from online.session_manager import SessionManager

def test_build_and_get():
    session = SessionManager.build_session("testuser")
    assert session["username"] == "testuser"
    fetched = SessionManager.get_session(session["login_id"])
    assert fetched["username"] == "testuser"

def test_destroy():
    session = SessionManager.build_session("temp")
    login_id = session["login_id"]
    SessionManager.destroy_session(login_id)
    assert SessionManager.get_session(login_id) is None
```

### 2.5 限流器测试

```python
# test_rate_limiter.py
from online.rate_limiter import RateLimiter
import time

def test_not_exceed():
    limiter = RateLimiter(max_per_minute=60)
    for _ in range(5):
        limiter.wait_if_needed()   # 应该立即通过

def test_exceed():
    limiter = RateLimiter(max_per_minute=2)
    limiter.wait_if_needed()
    limiter.wait_if_needed()
    start = time.time()
    limiter.wait_if_needed()       # 应该等待
    assert time.time() - start > 0.5
```

## 3. 集成测试

### 3.1 对话 API 集成测试

```python
# test_api_chat.py (需要运行中的服务)
import requests
import json

BASE_URL = "http://localhost:5010"

class TestChatAPI:
    def setup_method(self):
        # 注册+登录
        self.session = requests.Session()
        self.session.post(f"{BASE_URL}/api/register",
            json={"username": "test", "password": "test123", "email": "test@test.com"})
        resp = self.session.post(f"{BASE_URL}/api/login",
            json={"username": "test", "password": "test123"})
        assert resp.json()["success"]

    def test_chat_normal(self):
        resp = self.session.post(f"{BASE_URL}/api/chat",
            json={"question": "你好", "avatar_id": "doctor"})
        data = resp.json()
        assert data["success"]
        assert len(data["answer"]) > 0
        assert "retrieval_modes" in data

    def test_empty_question(self):
        resp = self.session.post(f"{BASE_URL}/api/chat",
            json={"question": "", "avatar_id": "doctor"})
        assert resp.status_code == 400

    def test_switch_avatar(self):
        resp = self.session.post(f"{BASE_URL}/api/select_avatar",
            json={"avatar_id": "psychologist"})
        assert resp.json()["success"]
        assert resp.json()["avatar_id"] == "psychologist"
```

### 3.2 数据管道集成测试

```python
# test_pipeline.py
import json
from pathlib import Path

def test_processed_data_integrity():
    """验证处理后数据的完整性和格式"""
    data_path = Path("processed_data/chinese_teacher_vector_records.json")
    if data_path.exists():
        with open(data_path) as f:
            data = json.load(f)
        required_keys = {"id", "role", "question", "answer", "source"}
        for item in data:
            assert required_keys.issubset(item.keys()), f"缺失字段: {item.get('id')}"
```

## 4. 系统测试（端到端）

### 4.1 测试用例矩阵

| 测试场景 | 前置条件 | 操作 | 预期结果 |
|---------|---------|------|---------|
| 用户注册 | 无 | POST /api/register | 返回 success=True |
| 用户登录 | 已注册 | POST /api/login | 返回 session cookie |
| 聊天对话 | 已登录 | POST /api/chat | 返回非空 answer |
| 切换角色 | 已登录 | POST /api/select_avatar | 角色切换成功 |
| 获取历史 | 有对话记录 | GET /api/history | 返回消息列表 |
| 清除历史 | 有对话记录 | POST /api/clear_history | 历史清空 |
| 空问题 | 已登录 | POST 空 question | 400 错误 |
| 未登录访问 | 未登录 | GET /api/current_user | success=False |
| 健康检查 | 系统运行中 | GET /api/health | 返回 ready |
| 系统概览 | 初始化完成 | GET /api/system/overview | 返回系统信息 |

### 4.2 离线任务测试

```bash
# 检查所有依赖服务
python main.py offline check
# 预期输出：三个服务端口状态

# 数据预处理测试
python main.py offline processor
# 预期输出：处理统计信息

# 数据分析
python main.py offline analyze
# 预期输出：质量评分报告
```

## 5. 压力测试

项目已集成 JMeter 压测脚本：

```bash
# 位置
jmeter/hybrid_retrieval_test_plan.jmx
jmeter/hybrid_retrieval_queries.csv
jmeter/run_wsl.sh
```

### 5.1 测试场景

| 场景 | 并发数 | 持续时间 | 目标指标 |
|------|--------|---------|---------|
| 正常负载 | 10 并发 | 5 分钟 | QPS > 5, P95 < 3s |
| 中等负载 | 50 并发 | 5 分钟 | 无 5xx 错误 |
| 峰值负载 | 100 并发 | 2 分钟 | 系统不崩溃 |

### 5.2 关键性能指标

| 指标 | 目标值 |
|------|-------|
| QPS | ≥ 5 （含 LLM 调用） |
| P50 响应时间 | < 2s |
| P95 响应时间 | < 5s |
| 错误率 | < 1% |
| 内存使用 | < 8GB |
| GPU 显存 | < 6GB |

## 6. 测试报告模板

```json
{
  "测试时间": "2026-05-29",
  "测试环境": {
    "GPU": "RTX 5060 8GB",
    "内存": "32GB",
    "Python": "3.12"
  },
  "测试结果": [
    {
      "测试项": "对话API",
      "用例数": 10,
      "通过": 10,
      "失败": 0,
      "通过率": "100%"
    }
  ],
  "性能数据": {
    "平均QPS": 6.5,
    "P50响应": 1.2,
    "P95响应": 3.8,
    "最大内存": "4.2GB"
  },
  "结论": "全部通过"
}
```

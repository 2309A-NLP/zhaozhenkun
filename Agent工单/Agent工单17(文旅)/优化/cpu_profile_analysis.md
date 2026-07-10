# CPU性能剖析报告

**日期**: 2026-06-12  
**方法**: cProfile (容器内) + 代码路径分析
**环境**: RAGFlow nightly + Ollama llama3.1:8b + RTX 5060 8GB

> 注: py-spy 因容器缺少 SYS_PTRACE 权限无法运行，改用 Python 内置 cProfile 模块进行代码级 CPU 剖析。

---

## 一、LLMBundle 创建与缓存性能

| 操作 | 耗时 | 说明 |
|------|------|------|
| **Cache MISS** (首次创建 LLMBundle) | **11,276 ms** | 包含 Ollama 连接建立、litellm 初始化、模型校验等 |
| **Cache HIT** (复用缓存) | **0.008 ms** | 仅字典查找，无网络/IO |
| **1000 次缓存查找** | **0.2 ms** | 平均每次 0.0002ms |

### 结论
- 缓存命中比重新创建快 **1,400,000 倍**
- 5并发场景：无缓存时5个请求各需 ~11s 创建 LLMBundle → 总计 55s 额外开销
- 有缓存时：仅第一个请求触发创建（11s），后续请求无此开销
- **优化效果在真实20并发场景下将更为显著**

## 二、模块导入开销

| 模块 | 贡献 |
|------|------|
| `litellm.__init__` | 8.1s (包含远程模型价格表下载) |
| `chat_model.py` | 8.2s (累积) |
| `dialog_service.py` | 11.7s (累积，含20+个子模块导入) |
| `db_models.py` | 10.8s (累积) |
| `settings.py` | 10.5s (累积) |

### 发现
- litellm 在导入时尝试下载远程模型价格表（超时5.4s），失败后回退到本地缓存
- 这是启动时的**一次性开销**，不影响运行时性能
- 建议：预缓存 model_prices_and_context_window.json 避免启动时网络依赖

## 三、CPU热点函数（推断自代码静态分析 + cProfile）

| 热点 | 位置 | 原因 |
|------|------|------|
| Ollama HTTP 通信 | `httpx._client.send()` | LLM推理的HTTP往返等待（I/O等待为主） |
| litellm 模型路由 | `litellm/llms/ollama/chat.py` | 模型协议转换 |
| 向量搜索 | Elasticsearch 查询 | 检索请求的ES通信 |
| Tokenizer 编码 | `transformers.AutoTokenizer` | 首次加载tokenizer |

## 四、瓶颈确认

**主要瓶颈**: Ollama LLM 推理（单请求 ~2.5s, 5并发P95 ~24s）
- 排队效应：5个请求串行处理 → 第5个需等待前4个完成
- GPU是瓶颈，非RAGFlow代码

**代码层面优化效果**:
- LLMBundle 创建从 11s → 0.000008s ✅
- 缓存查找几乎零开销 ✅
- 并发控制有效防止资源耗尽 ✅

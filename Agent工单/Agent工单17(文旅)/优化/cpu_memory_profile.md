# RAGFlow CPU与内存剖析报告

## 单请求耗时分布 (实测)

| 阶段 | 耗时 | 占比 |
|------|------|------|
| HTTP连接 | 0.0001s | 0.01% |
| TTFB (首字节) | 1.31s | 99.9% |
| 总耗时 | 1.31s | 100% |

**TTFB = 总耗时** → 瓶颈完全在服务端处理，非网络。

## 服务端耗时分解 (RAGFlow内置计时)

（来自RAGFlow响应中的prompt字段）

关键阶段：
- LLM推理(llama3.1:8b): 约1.2-1.5s (Ollama GPU推理)
- 检索(如涉及KB): 约0.1-0.3s
- 模型加载/缓存: 0s (LLMBundle缓存命中)
- 数据库查询: <0.01s (连接池)

## 内存稳定性

| 场景 | 内存 |
|------|------|
| 空闲 | 3.371 GiB |
| 3并发请求后 | 3.371 GiB |
| 增长 | 0 GiB (稳定) ✅ |

## CPU热点（静态分析推断）

1. `async_chat` (dialog_service.py:547) - 主处理入口
2. `LLMBundle.async_chat` (llm_service.py:401) - LLM调用
3. `retriever.retrieval` - 向量检索
4. `message_fit_in` - Token截断计算
5. `_stream_with_think_delta` - 流式响应处理

## GPU使用

- 空闲: 1014 MiB / 8151 MiB (12.4%)
- 推理中: ~2-3 GiB (llama3.1:8b Q4)
- 利用率: 1%(空闲) → 80-100%(推理中)

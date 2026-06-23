# Redis 队列状态分析报告

**日期**: 2026-06-12  
**工具**: redis-cli (容器内)  
**数据库**: DB1 (rag_flow)

---

## 一、Redis 实例概览

| 指标 | 数值 |
|------|------|
| 内存使用 | 1.35 MiB / 128 MiB (max) |
| 内存碎片率 | 8.63 |
| 连接客户端 | 5 |
| 总命令处理 | 4,117 |
| 瞬时 ops/sec | 2 |
| 拒绝连接 | 0 |
| 淘汰键 | 0 |
| keyspace_hits | 4,362 |
| keyspace_misses | 261 |

## 二、任务队列结构

DB1 中的队列相关键:

| Key | 类型 | 大小 | 说明 |
|-----|------|------|------|
| `rag_flow_svr_queue` | stream | - | 任务队列 (Redis Stream) |
| `rag_flow_svr_queue_1` | stream | - | 第二个任务队列流 |
| `TASKEXE` | set | 1 | 当前活跃的 Task Executor 集合 (`task_executor_-i`) |
| `task_executor_-i` | zset | 26 | Task Executor 的调度信息 (有序集合) |
| `id_generator:memory` | - | - | ID生成器 |

## 三、关键发现

1. **任务队列使用 Redis Stream**: RAGFlow 使用 Redis Stream 而非传统 List 作为任务队列，支持消费者组和消息确认机制，架构合理。

2. **Task Executor 正常注册**: `TASKEXE` set 中包含 `task_executor_-i`，说明 task_executor 进程已正常注册并存活。

3. **队列无堆积**: 当前没有未消费的文档解析任务。Stream 中没有积压消息。

4. **文档解析任务已异步**: 通过 Redis Stream + TaskExecutor 架构，文档解析请求进入队列后由独立的 `task_executor.py` 进程消费，API Server 不阻塞。

5. **连接数正常**: 5个连接客户端（API Server + Task Executor + 其他），无异常连接。

6. **内存使用极低**: 1.35 MiB / 128 MiB，说明 Redis 自身不是瓶颈。

## 四、建议

1. 在生产环境中增加 `maxmemory` 限制（当前128MB对于高负载可能不足）
2. 监控 `rejected_connections` 指标（当前为0）
3. 关注 Redis Stream 的消费者组 lag 指标
4. 内存碎片率 8.63 偏高，考虑启用 `activedefrag`

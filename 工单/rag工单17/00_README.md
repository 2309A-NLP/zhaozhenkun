# RAG工单17 - 解决API服务并发瓶颈与资源泄漏

**工单编号**: 人工智能NLP-RAG-17
**创建日期**: 2026-06-12
**参数说明**: 已全部调小以适应本地开发环境

---

## 📁 文件清单

| 文件 | 说明 | 类型 |
|------|------|------|
| `README.md` | 本文件 | 索引 |
| `问题排查分析报告.md` | 静态代码分析、瓶颈定位、泄漏点分析 | 产出物1 |
| `jmeter_scenario_a_qa_5concurrent.jmx` | 场景A压测脚本 (5并发问答, 5分钟) | 产出物2 |
| `jmeter_scenario_b_mixed_3concurrent.jmx` | 场景B压测脚本 (3并发混合负载, 5分钟) | 产出物2 |
| `optimization.patch` | Git diff格式的代码补丁 | 产出物3 |
| `patches_common_resource_cache.py` | 新增资源缓存模块 | 产出物3 |
| `代码优化补丁说明.md` | 补丁详情、变更点、应用方法 | 产出物3 |
| `最终性能测试报告.md` | 性能测试报告模板（待填数据） | 产出物4 |
| `docker-compose-optimized.yml` | 优化后Docker部署配置 | 产出物5 |
| `部署与运维文档.md` | 部署步骤、运维命令、常见问题 | 产出物5 |

## 🚀 快速开始

### 1. 了解问题
阅读 `问题排查分析报告.md` — 了解发现了哪些瓶颈和泄漏点

### 2. 应用代码优化
```bash
cd /path/to/ragflow

# 复制新模块
cp rag工单17/patches_common_resource_cache.py common/resource_cache.py

# 应用diff补丁（或手动合并）
git apply rag工单17/optimization.patch
```

### 3. 运行压测
```bash
# 修改JMX文件中的变量 (API_KEY, CHAT_ID等)
# 然后运行:
jmeter -n -t jmeter_scenario_a_qa_5concurrent.jmx -l results_a.jtl -e -o report_a/
```

### 4. 填写报告
使用 `最终性能测试报告.md` 模板记录对比数据

## ⚙️ 参数调小说明

| 参数 | 原始 | 调小后 | 原因 |
|------|------|--------|------|
| 场景A并发 | 20 | 5 | 降低本地负载 |
| 场景B并发 | 10 | 3 | 降低本地负载 |
| 持续时间 | 10分钟 | 5分钟 | 快速验证 |
| 容器CPU | 无限制 | 4核 | 防止占满 |
| 容器内存 | 无限制 | 8GB | 防止OOM |
| 数据库连接池 | 无限制 | 20 | 防止耗尽 |

## 📋 验收标准

- ✅ 场景A: P95 ≤ 3s, 无失败, 内存增长 ≤ 10%
- ✅ 场景B: P95 ≤ 5s, 无崩溃
- ✅ 12小时稳定性: RSS增长 ≤ 20%

## 🔗 相关文件

- 需求: `人工智能NLP-RAG项目-17-解决API服务并发瓶颈与资源泄漏工单V1.1-20260123.pdf`
- 项目代码: `/home/zzy/ragflow/`

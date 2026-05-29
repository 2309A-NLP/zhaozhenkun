# JMeter 混合检索压测

这个项目原来的 `/api/stress/run` 是应用进程内线程压测，只适合快速自检，不适合代替 JMeter。

真正做外部 HTTP 压测时，应该压这个接口：

- `POST /api/retrieval/search`

请求体示例：

```json
{
  "query": "兰蔻小黑瓶具备哪些基础功能",
  "top_k": 5,
  "include_results": false
}
```

这个接口会返回适合压测统计的精简结果：

- `hit_count`
- `timings.total_ms`
- `timings.lexical_ms`
- `timings.vector_ms`
- `timings.fusion_ms`
- `timings.rerank_ms`
- `modes`

## 文件

- `jmeter/hybrid_retrieval_test_plan.jmx`
- `jmeter/hybrid_retrieval_queries.csv`
- `jmeter/run_wsl.sh`
- `jmeter/analyze_results.py`

## WSL 运行前

1. 启动项目服务

如果 Flask 服务跑在 Windows：

```powershell
python "24 main.py"
```

如果 Flask 服务也跑在 WSL：

```bash
python3 "24 main.py"
```

2. 在 WSL 里确认接口可访问

先试本机回环：

```bash
curl http://127.0.0.1:5010/api/health
```

如果不通，再试 Windows 宿主机：

```bash
curl http://host.docker.internal:5010/api/health
```

或者手动指定 Windows 主机 IP。

## WSL 命令行压测

最简单的跑法：

```bash
cd /mnt/c/Users/31326/Desktop/adsd
bash ./jmeter/run_wsl.sh
```

自定义参数：

```bash
cd /mnt/c/Users/31326/Desktop/adsd
HOST=127.0.0.1 \
PORT=5010 \
USERS=20 \
RAMP_UP=20 \
LOOPS=10 \
TOP_K=5 \
SLA_MS=3000 \
bash ./jmeter/run_wsl.sh
```

这个脚本默认会执行：

```bash
jmeter -n \
  -t ./jmeter/hybrid_retrieval_test_plan.jmx \
  -l ./jmeter/results/hybrid_retrieval.jtl \
  -e \
  -o ./jmeter/results/dashboard \
  -JHOST=127.0.0.1 \
  -JPORT=5010 \
  -JUSERS=20 \
  -JRAMP_UP=20 \
  -JLOOPS=10 \
  -JTOP_K=5 \
  -JSLA_MS=3000 \
  -JQUERY_FILE=./jmeter/hybrid_retrieval_queries.csv \
  -Jsample_variables=hit_count,total_ms,lexical_ms,vector_ms,fusion_ms,rerank_ms
```

## GUI 方式

如果你在 WSLg 或 Linux 桌面环境里跑 GUI：

1. 打开 JMeter
2. 导入 `jmeter/hybrid_retrieval_test_plan.jmx`
3. 修改这些变量：

- `HOST`
- `PORT`
- `USERS`
- `RAMP_UP`
- `LOOPS`
- `TOP_K`
- `SLA_MS`
- `QUERY_FILE`

`QUERY_FILE` 在 WSL 里建议填 Linux 路径，例如：

```text
/mnt/c/Users/31326/Desktop/adsd/jmeter/hybrid_retrieval_queries.csv
```

## 结果分析

压测完成后直接在 WSL 分析：

```bash
python3 ./jmeter/analyze_results.py ./jmeter/results/hybrid_retrieval.jtl
```

它会输出 JSON 汇总，包括：

- 总样本数
- 成功率
- 吞吐
- 平均耗时
- `P95`
- `P99`
- 平均 `hit_count`
- 平均 `total_ms / lexical_ms / vector_ms / fusion_ms / rerank_ms`

## 建议压测档位

基线：

- `USERS=5`
- `RAMP_UP=10`
- `LOOPS=10`

业务压测：

- `USERS=20`
- `RAMP_UP=20`
- `LOOPS=20`

极限压测：

- `USERS=50`
- `RAMP_UP=30`
- `LOOPS=20`

## 怎么判断“混合检索不太对”

- `hit_count` 经常是 `0`
- `vector_ms` 很高，但 `lexical_ms` 很低
- `rerank_ms` 明显高于其他阶段
- 并发升高后 `throughput` 不再上升，但 `P95/P99` 快速恶化
- `Error %` 上升，同时响应时间变长

如果 `TOP_K=10` 比 `TOP_K=5` 主要增加的是 `rerank_ms`，那问题大概率在重排序阶段，不在 BM25 或 Milvus 召回阶段。

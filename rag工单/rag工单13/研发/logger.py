"""
logger.py - RAG工单13 结构化日志模块
需求: 每个阶段进出的结构化日志+详细时间戳+请求ID追踪 — 工单"识别瓶颈的工具"第2类"日志记录"
功能: 1.RagLogger(请求ID追踪) 2.各阶段进出日志 3.记录检索文档数/上下文长度/token数 4.输出到文件
"""
import logging          # 需求：Python标准日志库
import uuid             # 需求：生成唯一请求ID
import time             # 需求：精确时间戳
import json             # 需求：结构化JSON日志
import os               # 需求：日志目录

import 研发.config as config          # 需求：输出路径


# 日志目录
LOG_DIR = os.path.join(config.OUTPUT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class RagLogger:
    """
    RAG结构化日志器——需求：工单"日志记录"要求的请求ID追踪+各阶段进出日志
    每个查询创建一个实例，携带唯一request_id
    """

    def __init__(self, request_id=None):
        self.request_id = request_id or str(uuid.uuid4())[:8]  # 需求：请求ID追踪
        self.start_time = time.time()
        self.stage_logs = []       # 各阶段日志列表
        self.metrics = {}          # 需求：记录检索文档数/上下文长度/token数

    def log_stage_start(self, stage_name, **kwargs):
        """记录阶段开始——需求：每个阶段进出的结构化日志+详细时间戳"""
        entry = {
            "request_id": self.request_id,
            "stage": stage_name,
            "event": "start",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": time.time(),
            **kwargs
        }
        self.stage_logs.append(entry)
        return time.time()      # 返回起始时间供stop使用

    def log_stage_end(self, stage_name, start_t, **kwargs):
        """记录阶段结束——需求：计算阶段耗时并记录"""
        elapsed = time.time() - start_t
        entry = {
            "request_id": self.request_id,
            "stage": stage_name,
            "event": "end",
            "elapsed_seconds": round(elapsed, 4),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **kwargs
        }
        self.stage_logs.append(entry)
        return elapsed

    def log_metric(self, key, value):
        """记录业务指标——需求：记录检索文档数量、上下文长度、生成token数"""
        self.metrics[key] = value

    def get_summary(self):
        """获取本次查询的完整摘要——需求：汇总各阶段耗时和指标"""
        total = time.time() - self.start_time
        return {
            "request_id": self.request_id,
            "total_seconds": round(total, 4),
            "stage_count": len([s for s in self.stage_logs if s["event"] == "end"]),
            "metrics": self.metrics,
            "stages": self.stage_logs
        }

    def print_summary(self):
        """打印本次查询的结构化日志摘要"""
        summary = self.get_summary()
        print(f"\n📋 请求 {self.request_id} 日志摘要:")
        print(f"  总耗时: {summary['total_seconds']:.3f}s")
        for log in self.stage_logs:
            if log["event"] == "end":
                print(f"  {log['stage']:<25} {log['elapsed_seconds']:.3f}s")
        if self.metrics:
            print(f"  指标: {json.dumps(self.metrics, ensure_ascii=False)}")


def save_logs(logs, filename=None):
    """将日志保存到文件——需求：产出物——过程跟踪步骤记录"""
    if filename is None:
        filename = f"rag_log_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(LOG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    print(f"💾 日志已保存: {path}")
    return path

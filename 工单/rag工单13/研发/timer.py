"""
timer.py - RAG工单13 计时工具模块
需求: 精确测量RAG各阶段耗时（工单"日志记录"——每个阶段带时间戳的结构化日志）
功能: 1.嵌套计时(start/stop) 2.with上下文支持 3.自动汇总统计 4.打印耗时表格
"""
import time                     # 需求：毫秒级时间测量（性能分析的基础工具）
from collections import defaultdict  # 需求：自动聚合相同阶段的多条耗时记录


class Timer:
    """计时器：记录RAG流水线各阶段的耗时，支持嵌套计时"""

    def __init__(self):
        """初始化计时器，重置所有统计数据"""
        self.reset()

    def reset(self):
        """重置所有计时数据——需求：支持多轮测试之间清零"""
        self._records = defaultdict(list)  # {阶段名: [耗时秒数, ...]}
        self._stack = []                    # 计时栈（支持嵌套）

    def start(self, name: str):
        """开始计时指定阶段——需求：进入每个处理阶段时打时间戳"""
        self._stack.append({
            "name": name,                  # 阶段名，如"embedding"
            "start_time": time.time()      # 开始时间戳
        })

    def stop(self, name: str = None) -> float:
        """结束计时并返回耗时秒数——需求：退出阶段时记录耗时"""
        if name is None and self._stack:
            frame = self._stack.pop()      # 无参则弹出栈顶
        else:
            frame = None
            for i in range(len(self._stack) - 1, -1, -1):
                if self._stack[i]["name"] == name:
                    frame = self._stack.pop(i)
                    break
            if frame is None:
                return 0.0
        elapsed = time.time() - frame["start_time"]
        self._records[frame["name"]].append(elapsed)
        return elapsed

    def get_summary(self) -> dict:
        """获取各阶段统计摘要（次数/总耗时/平均/最小/最大）"""
        summary = {}
        for name, times in self._records.items():
            if times:
                summary[name] = {
                    "count": len(times),                # 调用次数
                    "total": round(sum(times), 3),      # 总耗时（秒）
                    "avg": round(sum(times) / len(times), 3),  # 平均耗时
                    "min": round(min(times), 3),        # 最短耗时
                    "max": round(max(times), 3),        # 最长耗时
                }
        return summary

    def get_total_time(self) -> float:
        """获取所有阶段的总耗时——需求：用于瓶颈分析的占比计算"""
        return sum(sum(times) for times in self._records.values())

    def print_summary(self):
        """打印耗时统计表格——需求：可视化展示各阶段耗时占比"""
        summary = self.get_summary()
        if not summary:
            print("  (无计时数据)")
            return
        sorted_stages = sorted(summary.items(), key=lambda x: x[1]["total"], reverse=True)
        print(f"\n{'='*60}")
        print(f"📊 RAG 各阶段耗时统计")
        print(f"{'='*60}")
        print(f"{'阶段':<20} {'次数':>6} {'总耗时':>10} {'平均':>8} {'最慢':>8} {'占比':>8}")
        print(f"{'-'*20} {'-'*6} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
        total = self.get_total_time()
        for name, stats in sorted_stages:
            pct = (stats["total"] / total * 100) if total > 0 else 0
            print(f"{name:<20} {stats['count']:>6} {stats['total']:>8.2f}s {stats['avg']:>7.2f}s {stats['max']:>7.2f}s {pct:>6.1f}%")
        print(f"{'-'*60}")
        print(f"{'总计':<20} {'':>6} {total:>8.2f}s {'':>16}")
        print(f"{'='*60}")

    def get_stage_names(self) -> list:
        """获取所有阶段名称列表"""
        return list(self._records.keys())

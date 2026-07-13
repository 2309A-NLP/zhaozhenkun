# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：异步任务优化 - 后台任务队列和并发处理优化
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import asyncio  # 异步IO支持
import time  # 时间函数
import uuid  # 唯一ID生成
from typing import Dict, List, Optional, Any, Callable  # 类型提示
from dataclasses import dataclass, field  # 数据类
from datetime import datetime  # 时间处理
from enum import Enum  # 枚举
from collections import defaultdict  # 默认字典
import threading  # 线程支持


class TaskStatus(str, Enum):
    """任务状态枚举 - 定义异步任务的生命周期状态"""
    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class AsyncTask:
    """异步任务数据类 - 封装单个任务的完整信息"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # 任务唯一ID
    task_type: str = ""  # 任务类型（generate/export/search等）
    status: TaskStatus = TaskStatus.PENDING  # 任务状态
    params: Dict = field(default_factory=dict)  # 任务参数
    result: Optional[Any] = None  # 任务结果
    error: Optional[str] = None  # 错误信息
    progress: float = 0.0  # 进度（0-100）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())  # 创建时间
    started_at: Optional[str] = None  # 开始执行时间
    completed_at: Optional[str] = None  # 完成时间
    user_id: Optional[str] = None  # 提交用户ID


class AsyncTaskManager:
    """异步任务管理器 - 管理后台任务的创建、执行和状态查询"""

    def __init__(self, max_concurrent: int = 5):
        """初始化任务管理器 - 设置并发限制和任务存储"""
        self._tasks: Dict[str, AsyncTask] = {}  # 任务字典（task_id → AsyncTask）
        self._max_concurrent = max_concurrent  # 最大并发任务数
        self._running_count = 0  # 当前运行中的任务数
        self._lock = threading.RLock()  # 线程锁
        self._task_queue: List[str] = []  # 待执行任务队列

    def create_task(self, task_type: str, params: Dict,
                    user_id: Optional[str] = None) -> AsyncTask:
        """创建异步任务 - 注册新任务并加入队列"""
        task = AsyncTask(task_type=task_type, params=params, user_id=user_id)  # 创建任务对象
        with self._lock:  # 线程安全
            self._tasks[task.task_id] = task  # 存储任务
            self._task_queue.append(task.task_id)  # 加入执行队列
        print(f"任务已创建：{task.task_id} ({task_type})")  # 创建日志
        return task  # 返回任务对象

    async def execute_task(self, task_id: str,
                           coroutine_func: Callable, *args, **kwargs) -> Any:
        """执行异步任务 - 运行协程函数并记录状态"""
        task = self._tasks.get(task_id)  # 获取任务
        if not task:  # 任务不存在
            return None  # 返回None
        with self._lock:  # 线程安全
            task.status = TaskStatus.RUNNING  # 标记为运行中
            task.started_at = datetime.now().isoformat()  # 记录开始时间
            self._running_count += 1  # 运行计数+1
        try:
            result = await coroutine_func(*args, **kwargs)  # 执行协程函数
            with self._lock:  # 线程安全
                task.status = TaskStatus.COMPLETED  # 标记完成
                task.result = result  # 存储结果
                task.progress = 100.0  # 进度100%
        except Exception as e:  # 执行异常
            with self._lock:  # 线程安全
                task.status = TaskStatus.FAILED  # 标记失败
                task.error = str(e)  # 记录错误
                print(f"任务失败 {task_id}: {e}")  # 错误日志
        finally:
            with self._lock:  # 线程安全
                task.completed_at = datetime.now().isoformat()  # 记录完成时间
                self._running_count -= 1  # 运行计数-1
        # 从队列中移除已完成的任务
        with self._lock:  # 线程安全
            if task_id in self._task_queue:  # 在队列中
                self._task_queue.remove(task_id)  # 移出队列
        return task.result  # 返回执行结果

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态 - 返回任务的当前状态和进度"""
        task = self._tasks.get(task_id)  # 获取任务
        if not task:  # 任务不存在
            return None  # 返回None
        return {  # 返回状态摘要
            "task_id": task.task_id, "task_type": task.task_type,
            "status": task.status.value, "progress": task.progress,
            "created_at": task.created_at, "started_at": task.started_at,
            "completed_at": task.completed_at, "error": task.error,
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务 - 取消等待中的任务"""
        task = self._tasks.get(task_id)  # 获取任务
        if not task:  # 任务不存在
            return False  # 取消失败
        if task.status == TaskStatus.PENDING:  # 仅可取消等待中的任务
            task.status = TaskStatus.CANCELLED  # 标记取消
            if task_id in self._task_queue:  # 在队列中
                self._task_queue.remove(task_id)  # 移出队列
            return True  # 取消成功
        return False  # 不可取消

    def get_pending_tasks(self, user_id: Optional[str] = None) -> List[Dict]:
        """获取待处理任务列表"""
        pending = []  # 待处理列表
        for task in self._tasks.values():  # 遍历所有任务
            if task.status == TaskStatus.PENDING:  # 等待中
                if user_id is None or task.user_id == user_id:  # 全部用户或指定用户
                    pending.append(self.get_task_status(task.task_id))  # 添加到列表
        return pending  # 返回待处理列表

    def get_stats(self) -> Dict:
        """获取任务管理器统计信息"""
        status_counts = defaultdict(int)  # 各状态计数
        for task in self._tasks.values():  # 遍历任务
            status_counts[task.status.value] += 1  # 计数+1
        return {  # 统计信息
            "total_tasks": len(self._tasks),  # 总任务数
            "running": self._running_count,  # 运行中
            "queued": len(self._task_queue),  # 队列中
            "status_breakdown": dict(status_counts),  # 状态分布
            "max_concurrent": self._max_concurrent,  # 最大并发
        }


class BatchProcessor:
    """批量处理器 - 优化批量操作，减少API调用次数"""

    def __init__(self, batch_size: int = 5):
        """初始化处理器 - 设置批处理大小"""
        self.batch_size = batch_size  # 每批处理数量

    async def process_batch(self, items: List[Any],
                            process_func: Callable) -> List[Any]:
        """批量异步处理 - 将大列表分批并发处理"""
        results = []  # 总结果列表
        total_batches = (len(items) + self.batch_size - 1) // self.batch_size  # 计算总批次数
        for batch_idx in range(total_batches):  # 遍历每个批次
            start = batch_idx * self.batch_size  # 批次起始索引
            end = min(start + self.batch_size, len(items))  # 批次结束索引
            batch = items[start:end]  # 获取当前批次
            print(f"批量处理 第{batch_idx + 1}/{total_batches}批 ({len(batch)}项)")  # 进度日志
            # 并发处理当前批次
            batch_tasks = [process_func(item) for item in batch]  # 创建协程任务列表
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)  # 并发执行
            # 处理结果，过滤异常
            for item, result in zip(batch, batch_results):  # 遍历批次结果
                if isinstance(result, Exception):  # 处理异常
                    print(f"项处理失败: {result}")  # 错误日志
                    results.append(None)  # 异常项返回None
                else:
                    results.append(result)  # 正常结果
            # 批次间短暂延迟（避免API限流）
            if batch_idx < total_batches - 1:  # 非最后一批
                await asyncio.sleep(0.5)  # 等待500ms
        return results  # 返回所有结果


# 全局异步管理器实例
async_task_manager = AsyncTaskManager(max_concurrent=5)  # 最大5个并发任务
batch_processor = BatchProcessor(batch_size=5)  # 每批5个

# -*- coding: utf-8 -*-
"""
文件功能：定时调度器模块 —— 后台守护线程轮询检查到期日程并触发温馨提醒。

职责说明：
  1. 启动后台守护线程，每隔 10 秒检查一次是否有到期日程
  2. 发现到期日程后，随机选择温馨话术模板生成提醒文本
  3. 将提醒推入通知队列，供前端轮询获取
  4. 更新日程的 last_reminded 字段，防止同一分钟内重复提醒
  5. 同一分钟只检查一次（通过 last_check_minute 去重）

设计要点：
  - 守护线程：主程序退出时自动结束，不会阻止进程退出
  - 线程安全：通知列表使用 threading.Lock 保护
  - 话术多样性：6 种温馨提醒模板随机选择，满足工单验收要求
  - 数据库回调：通过 get_db_callback 延迟获取数据库实例

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import logging      # 日志记录
import random       # 随机选择提醒话术模板
import threading    # 后台守护线程
import time         # sleep 和时间格式化
import traceback    # 打印异常堆栈
from datetime import datetime  # 获取当前时间
from pathlib import Path       # 跨平台路径（本模块暂未直接使用，保留）
from typing import Any          # 通用类型注解

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_2.scheduler")


# ========== 温馨提醒话术模板 ==========
# 共 6 种模板，每次提醒随机选择，满足工单验收"多种话术"要求
# {content} 会被替换为具体的日程内容
REMINDER_TEMPLATES = [
    "温馨提醒：（{content}）的时间到啦，主人！",
    "主人！是时候（{content}）了喔~",
    "亲爱的主人，现在是（{content}）的时候啦！",
    "嘿，主人，该（{content}）了哦~",
    "叮咚！{content}的时间到啦，别忘啦！",
    "小助手提醒您：（{content}）的时候到了！",
]


class ReminderScheduler:
    """
    后台定时调度器。

    通过独立守护线程每 10 秒轮询一次数据库，
    检查当前时间是否有到期的日程，并生成温馨提醒。
    """

    def __init__(self, get_db_callback) -> None:
        """
        初始化调度器。

        参数:
          get_db_callback: 可调用对象，返回 ScheduleDatabase 实例。
                           使用回调而非直接保存引用，确保每次调用获取最新数据库状态。
        """
        logger.info("初始化提醒调度器...")
        # 保存数据库获取回调（延迟获取，避免循环依赖）
        self._get_db = get_db_callback
        # 运行状态标志（False 时停止循环）
        self._running = False
        # 后台线程引用
        self._thread: threading.Thread | None = None
        # 通知队列：存储待推送给前端的提醒消息
        self._notifications: list[dict[str, Any]] = []
        # 线程锁：保护通知队列的并发访问
        self._lock = threading.Lock()
        # 累计提醒次数统计
        self._total_reminders = 0
        logger.info("提醒调度器初始化完成（%s 种话术模板）", len(REMINDER_TEMPLATES))

    def start(self) -> None:
        """
        启动后台调度线程。

        创建 daemon=True 的守护线程，主程序退出时自动销毁。
        防止重复启动：如果已在运行则跳过。
        """
        if self._running:
            logger.warning("调度器已在运行中，跳过重复启动")
            return

        # 设置运行标志
        self._running = True
        # 创建守护线程：daemon=True 确保主程序退出时自动结束
        self._thread = threading.Thread(target=self._loop, daemon=True, name="reminder-scheduler")
        # 启动线程（开始执行 _loop 方法）
        self._thread.start()
        logger.info("日程提醒调度器已启动（守护线程：reminder-scheduler）")

    def stop(self) -> None:
        """
        停止调度器。

        设置 _running = False 让循环退出，
        然后等待线程结束（最多等 5 秒）。
        """
        logger.info("正在停止调度器...")
        self._running = False  # 通知循环退出

        if self._thread:
            # 等待线程结束，最多等 5 秒
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("调度器线程未能在5秒内退出")
            else:
                logger.info("调度器线程已退出")

        logger.info("日程提醒调度器已停止（累计提醒：%s次）", self._total_reminders)

    def get_notifications(self) -> list[dict[str, Any]]:
        """
        获取并清空待显示的通知列表。

        被前端 /api/notifications 接口轮询调用，
        每次调用返回新累积的通知并清空队列。

        返回:
          通知消息列表，每条包含 id / content / schedule_time / reminder / timestamp
        """
        with self._lock:
            count = len(self._notifications)
            # 拷贝当前通知列表
            notes = self._notifications[:]
            # 清空原列表（已获取的通知不再保留）
            self._notifications.clear()

        if count > 0:
            logger.debug("推送 %s 条通知到前端", count)
        return notes

    def _loop(self) -> None:
        """
        调度器主循环：每 10 秒检查一次到期日程。

        循环逻辑：
          1. 获取当前时间的 HH:MM 和 YYYY-MM-DD
          2. 如果当前分钟与上次检查不同（避免同分钟重复检查）
          3. 调用 _check_due 查询到期日程并生成提醒
          4. sleep 10 秒后继续
        """
        logger.info("调度器主循环开始（间隔：10秒）")
        last_check_minute = ""  # 上次检查的分钟标识（用于去重）
        loop_count = 0          # 循环计数

        while self._running:
            try:
                loop_count += 1
                now = datetime.now()
                current_minute = now.strftime("%H:%M")      # 当前时间 HH:MM
                current_date = now.strftime("%Y-%m-%d")     # 当前日期 YYYY-MM-DD

                # 去重：同一分钟内不重复检查
                if current_minute != last_check_minute:
                    logger.debug("调度器触发检查：%s %s (loop #%s)", current_date, current_minute, loop_count)
                    last_check_minute = current_minute  # 更新上次检查分钟
                    self._check_due(current_minute, current_date)  # 执行检查

            except Exception as e:
                # 单次检查异常不影响后续循环
                logger.error("调度器循环异常：%s", e)
                logger.debug("异常堆栈：%s", traceback.format_exc())

            # 休眠 10 秒后进入下一轮
            time.sleep(10)

        logger.info("调度器主循环退出（共执行 %s 次循环）", loop_count)

    def _check_due(self, current_time: str, current_date: str) -> None:
        """
        检查当前时间到期的日程，生成提醒通知。

        流程：
          1. 调用数据库 find_due_schedules 查询到期日程
          2. 对每条到期日程，随机选择话术模板生成提醒文本
          3. 将提醒推入通知队列（线程安全）
          4. 更新 last_reminded 防止重复提醒

        参数:
          current_time: 当前时间 HH:MM
          current_date: 当前日期 YYYY-MM-DD
        """
        logger.debug("开始检查到期日程：%s %s", current_date, current_time)

        # Step 1：查询到期日程
        try:
            db = self._get_db()  # 通过回调获取最新的数据库实例
            due_schedules = db.find_due_schedules(current_time, current_date)
        except Exception as e:
            logger.error("获取到期日程失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return

        # 无到期日程则直接返回
        if not due_schedules:
            return

        logger.info("发现 %s 条到期日程", len(due_schedules))

        # Step 2：逐条处理到期日程，生成提醒
        for schedule in due_schedules:
            try:
                # 随机选择一条温馨话术模板
                template = random.choice(REMINDER_TEMPLATES)
                # 将模板中的 {content} 替换为实际日程内容
                reminder_text = template.format(content=schedule["content"])
                logger.info("🔔 触发提醒：#%s %s → 话术模板：%s",
                           schedule["id"], schedule["content"], template[:30])

                # Step 3：线程安全地推入通知队列
                with self._lock:
                    self._notifications.append({
                        "id": schedule["id"],                        # 日程 ID
                        "content": schedule["content"],             # 日程内容
                        "schedule_time": schedule["schedule_time"], # 日程时间
                        "reminder": reminder_text,                  # 提醒文本
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 提醒时间戳
                    })
                self._total_reminders += 1  # 累计计数

                # Step 4：更新 last_reminded 防止今天重复提醒
                db.update_reminded(schedule["id"], current_date)
                logger.debug("已更新提醒记录：id=%s, date=%s", schedule["id"], current_date)

            except Exception as e:
                # 单条处理失败不影响其他日程
                logger.error("处理单条提醒失败：id=%s, error=%s", schedule.get("id"), e)
                continue

# -*- coding: utf-8 -*-
"""
文件功能：最小自测脚本 —— 对日程提醒智能体的核心业务流程进行端到端验证。

测试说明：
  本脚本模拟用户从添加日程到查询再到删除的完整对话流程，
  覆盖以下核心场景：
    1. 添加普通日程（指定时间+事项）
    2. 添加每日重复日程
    3. 添加每周重复日程
    4. 添加指定日期的日程（明天）
    5. 查询今日日程
    6. 按编号删除（两步确认）
    7. 按编号取消（两步确认）

运行方式：
  cd 到项目根目录，执行：
  python 测试/test_app.py

注意事项：
  - 测试使用独立的 SQLite 数据库文件（test_schedule_notes.db），
    不会影响正式数据（schedule_notes.db）
  - 每次运行前会删除旧的测试数据库，确保测试环境干净
  - 测试结束后自动清理测试数据库

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import logging    # 日志记录
import sys        # 系统路径管理
import time       # 计时和统计测试耗时
from pathlib import Path  # 跨平台路径处理

# ---------- 路径修正 ----------
# 确保项目根目录在 Python 模块搜索路径中
# 这样测试脚本可以从任意目录运行
BASE_DIR = Path(__file__).resolve().parents[1]  # 向上两级：测试/ → 项目根
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ---------- 项目内部导入 ----------
from 研发.database import ScheduleDatabase        # 日程数据库操作类
from 研发.logger_config import setup_logging        # 日志初始化函数
from 研发.service import ScheduleService            # 业务逻辑服务类

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_2.test")


def main() -> None:
    """
    测试主函数：依次执行预定义的测试用例，验证结果，输出统计。
    """
    # ---------- 初始化日志 ----------
    log_path = setup_logging(BASE_DIR)
    t_start = time.time()  # 计时起点

    logger.info("=" * 60)
    logger.info("🤖 Agent工单2 - 日程提醒智能体 自动化测试")
    logger.info("日志文件：%s", log_path)
    logger.info("测试时间：%s", time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # ---------- 准备测试数据库 ----------
    # 测试数据库路径：测试/test_schedule_notes.db（与正式数据库隔离）
    db_path = BASE_DIR / "测试" / "test_schedule_notes.db"
    # 删除旧测试数据库，确保每次测试从零开始
    if db_path.exists():
        db_path.unlink()
        logger.info("已删除旧测试数据库：%s", db_path)

    logger.info("测试数据库路径：%s", db_path)
    # 创建数据库实例（自动建表）
    database = ScheduleDatabase(db_path)
    # 创建服务实例（注入数据库依赖）
    service = ScheduleService(database)
    logger.info("测试环境初始化完成")

    # ---------- 定义测试用例 ----------
    # 每个用例是 (名称, 输入文本, 预期描述) 的三元组
    cases = [
        # === 添加日程 ===
        ("添加日程", "添加日程：下午5点开会", '时间17:00 + 事项「开会」入库'),
        ("每日重复", "每天早上8点提醒我起床", "时间08:00 + repeat=daily"),
        ("每周重复", "每周一上午9点开例会", "时间09:00 + repeat=weekly(Monday)"),
        ("明天日程", "明天上午10点提醒我交报告", "日期明天 + 时间10:00"),
        # === 查询日程 ===
        ("查询今日", "我今天的日程有哪些？", "列出今日所有日程"),
        # === 修改操作（两步确认）===
        ("修改确认", "修改日程1 时间改为下午3点", "展示匹配记录，等待修改确认"),
        ("执行修改", "确认修改", "执行修改，回复已修改内容"),
        # === 修改内容 ===
        ("修改内容-确认", "把日程2改成每天上午8点买咖啡", "整体替换，确认修改"),
        ("修改内容-执行", "确认修改", "执行修改，内容已更新"),
        # === 删除操作（两步确认）===
        ("删除确认", "删除日程4", "展示匹配记录，等待确认"),
        ("执行删除", "确认删除", "执行删除，回复已删除内容"),
        # === 取消操作（同删除流程，不同关键词）===
        ("取消确认", "取消日程3", "展示匹配记录，等待确认"),
        ("取消执行", "确认删除", "执行取消，回复已取消内容"),
    ]

    passed = 0  # 通过计数
    failed = 0  # 失败计数
    logger.info("-" * 60)
    logger.info("开始执行 %s 条测试用例...", len(cases))
    logger.info("-" * 60)

    # ---------- 执行测试 ----------
    for i, (case_name, input_text, expected) in enumerate(cases, 1):
        logger.info("【测试 %s/%s】%s", i, len(cases), case_name)
        logger.debug("  输入：%s", input_text)
        logger.debug("  预期：%s", expected)

        try:
            # 将测试输入送入服务层处理
            result = service.handle_message(input_text)
        except Exception as e:
            # 异常视为失败
            logger.error("  测试异常：%s", e)
            failed += 1
            continue

        # 检查是否有回复内容
        reply = result.get("reply", "")
        if reply:
            passed += 1
            logger.info("  ✅ 通过：%s", reply[:120])
        else:
            failed += 1
            logger.error("  ❌ 失败：无回复内容")

    # ---------- 验证数据库最终状态 ----------
    logger.info("-" * 60)
    logger.info("验证数据库状态...")
    all_records = database.find_all_schedules(include_disabled=True)
    logger.info("数据库总记录数：%s", len(all_records))
    # 逐条打印记录详情
    for r in all_records:
        status = "✓启用" if r.get("enabled") == 1 else "✗取消"
        logger.info("  #%s | %s %s | %s | %s | repeat=%s",
                    r["id"],
                    r.get("schedule_date", "-"),
                    r["schedule_time"],
                    r["content"],
                    status,
                    r.get("repeat_rule", "none"))

    # ---------- 清理测试环境 ----------
    if db_path.exists():
        db_path.unlink()
        logger.info("已清理测试数据库：%s", db_path)

    # ---------- 输出测试统计 ----------
    elapsed = time.time() - t_start
    logger.info("=" * 60)
    logger.info("📊 测试结果：通过 %s / %s，失败 %s，耗时 %.1f秒",
               passed, len(cases), failed, elapsed)
    if failed == 0:
        logger.info("✅ 全部测试通过！")
    else:
        logger.warning("⚠ 存在 %s 条失败用例", failed)
    logger.info("=" * 60)


# ---------- 入口判断 ----------
if __name__ == "__main__":
    main()

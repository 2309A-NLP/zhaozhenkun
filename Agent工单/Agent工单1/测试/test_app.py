# -*- coding: utf-8 -*-
"""
文件功能：端到端测试脚本 —— 对家庭记账本的核心业务流程进行全面验证。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

测试覆盖：
  1. 基本记账（支出/收入）
  2. 口语化表达测试（LLM 智能理解）
  3. 智能分类测试（语义推断类别）
  4. 查询购买日期
  5. 查询明细
  6. 按月汇总（按成员、按类型）
  7. 删除 + 确认删除
  8. 不完整输入引导

运行方式：
  cd 到项目根目录，执行：
  python 测试/test_app.py
"""

# ---------- 标准库导入 ----------
import json
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（解决从 测试/ 子目录运行时找不到 研发/ 模块的问题）
_base_dir = Path(__file__).resolve().parents[1]
if str(_base_dir) not in sys.path:
    sys.path.insert(0, str(_base_dir))

# ---------- 项目内部导入 ----------
from 研发.database import LedgerDatabase
from 研发.llm_client import LLMClient
from 研发.logger_config import setup_logging
from 研发.service import LedgerService

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_1.test")


def main() -> None:
    """测试主函数。"""
    base_dir = Path(__file__).resolve().parents[1]
    log_path = setup_logging(base_dir)
    logger.info("开始执行自测，日志文件：%s", log_path)

    # ---------- 准备测试数据库 ----------
    db_path = base_dir / "测试" / "test_money_notes.db"
    if db_path.exists():
        db_path.unlink()
        logger.info("已删除旧测试数据库：%s", db_path)

    database = LedgerDatabase(db_path)

    # ---------- 初始化 LLM 客户端 ----------
    config_path = base_dir / "部署" / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}

    llm_client = None
    if config.get("llm_api_key"):
        llm_client = LLMClient(config)
        logger.info("LLM 模式已启用")
    else:
        logger.info("正则模式（未配置 LLM API Key）")

    service = LedgerService(database, llm_client)

    # ========== 测试用例 ==========

    # ---- 记账测试 ----
    cases = [
        # 基本记账
        "今天我买了三体50元",
        "今天女儿买了双登山鞋499元",
        "7月5日妈妈收到报销1000元",

        # 口语化表达（LLM 智能理解测试）
        "昨天花了200块请朋友吃饭",
        "上星期闺女买了个新书包花了180",
        "老爸发工资8000",

        # 查询测试
        "我哪天买的三体",
        "看下这个月家里花钱明细",
        "这个月女儿花了多少钱",

        # 删除测试
        "删除女儿登山鞋的费用",
        "确认删除",

        # 不完整输入引导测试
        "花了500元",           # 缺少成员
        "买了一本书",           # 缺少金额和成员
    ]

    for text in cases:
        result = service.handle_message(text)
        logger.info("[输入] %s", text)
        logger.info("[输出] %s", result["reply"])
        if "data" in result:
            logger.info("[数据] %s", result["data"])
        logger.info("%s", "-" * 50)


if __name__ == "__main__":
    main()

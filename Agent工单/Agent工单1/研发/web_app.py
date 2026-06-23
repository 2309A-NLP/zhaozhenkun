# -*- coding: utf-8 -*-
"""
文件功能：Web 模块 —— 创建 Flask Web 应用，提供页面渲染和 API 接口。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 创建 Flask 应用实例，配置模板目录和静态文件目录
  2. 初始化数据库、LLM 客户端和服务层（依赖注入）
  3. 注册路由：
     - GET  /           → 渲染首页（index.html）
     - POST /api/chat   → 对话接口
     - GET  /api/records → 数据接口（返回全部已存账目）
"""

# ---------- 标准库导入 ----------
import logging
from pathlib import Path

# ---------- 第三方库导入 ----------
from flask import Flask, jsonify, render_template, request

# ---------- 项目内部导入 ----------
from 研发.database import LedgerDatabase
from 研发.llm_client import LLMClient
from 研发.service import LedgerService

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_1.web")


def create_app(base_dir: Path, config: dict) -> Flask:
    """
    工厂函数：创建并配置 Flask 应用实例。

    参数:
      base_dir: 项目根目录
      config: 配置字典

    返回:
      已配置好路由的 Flask 应用实例
    """
    # ---------- 路径配置 ----------
    template_dir = base_dir / "部署" / "templates"
    static_dir = base_dir / "部署" / "static"

    # ---------- 创建 Flask 应用 ----------
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    # 让 jsonify 直接输出中文，而不是 \uXXXX 编码
    app.json.ensure_ascii = False

    # ---------- 数据库初始化 ----------
    db_path = base_dir / config.get("db_name", "money_notes.db")
    database = LedgerDatabase(db_path)

    # ---------- LLM 客户端初始化 ----------
    llm_client = None
    if config.get("llm_api_key"):
        llm_client = LLMClient(config)
        logger.info("LLM 客户端已启用：model=%s", config.get("llm_model", "deepseek-chat"))
    else:
        logger.warning("未配置 llm_api_key，LLM 功能禁用，将使用正则解析模式")

    # ---------- 服务层初始化（依赖注入） ----------
    service = LedgerService(database, llm_client)

    logger.info("Flask 应用创建完成：template=%s, static=%s", template_dir, static_dir)

    # ========== 路由注册 ==========

    @app.route("/")
    def index():
        """首页路由。"""
        logger.info("访问首页")
        return render_template("index.html")

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """
        对话接口。

        POST /api/chat
        请求体 JSON: { "message": "今天女儿买了登山鞋499元" }
        响应 JSON:    { "reply": "已记录：...", "data": {...} }
        """
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()

        logger.info("收到聊天请求：%s", message)

        result = service.handle_message(message)

        logger.info("聊天响应完成")
        return jsonify(result)

    @app.route("/api/welcome", methods=["GET"])
    def welcome():
        """欢迎语接口：返回工单要求的开场白。"""
        from datetime import datetime
        now = datetime.now()
        welcome_msg = (
            f"您好，欢迎使用咱们小家专属记账本！\n"
            f"今天是 {now.strftime('%Y年%m月%d日')} {now.strftime('%A')}。\n"
            '请按照"x年x月x日，谁做什么事收入/支出多少钱"的格式来输入。\n'
            '请告诉我你的账目需求吧~'
        )
        return jsonify({"reply": welcome_msg})

    @app.route("/api/records", methods=["GET"])
    def records():
        """
        数据接口：返回全部已存账目。

        GET /api/records
        响应 JSON: { "records": [...] }
        """
        data = database.find_all_records(include_disabled=False)
        logger.info("返回全部账目：count=%s", len(data))
        return jsonify({"records": data})

    return app

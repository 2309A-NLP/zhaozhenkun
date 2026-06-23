# -*- coding: utf-8 -*-
"""
文件功能：Web 模块 —— 创建 Flask Web 应用，提供页面渲染和 API 接口。

职责说明：
  1. 创建 Flask 应用实例，配置模板目录和静态文件目录
  2. 初始化数据库和服务层（依赖注入）
  3. 注入后台调度器，实现提醒通知的推送
  4. 注册路由：
     - GET  /                 → 渲染首页（index.html）
     - POST /api/chat         → 对话接口（接收自然语言消息，返回处理结果）
     - GET  /api/welcome      → 欢迎语接口（返回个性化欢迎信息）
     - GET  /api/records      → 数据接口（返回全部已存日程）
     - GET  /api/notifications → 提醒通知接口（前端轮询获取到期提醒）

路由设计说明：
  - /api/chat:       核心对话接口，前端将用户输入 POST 到此，返回解析+处理结果
  - /api/welcome:    页面加载时调用，获取个性化问候语
  - /api/records:    查看所有日程（含已取消），用于调试和数据展示
  - /api/notifications: 前端定时轮询（如每5秒），获取调度器产生的新提醒

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import logging      # 日志记录
import time         # 计算接口响应耗时
import traceback    # 打印异常堆栈
from pathlib import Path  # 跨平台路径处理

# ---------- 第三方库导入 ----------
from flask import Flask, jsonify, render_template, request
# Flask:           Web 应用框架
# jsonify:         将 Python 对象转为 JSON 响应
# render_template: 渲染 Jinja2 模板（HTML）
# request:         访问请求数据（路径、参数、body 等）

# ---------- 项目内部导入 ----------
from 研发.database import ScheduleDatabase  # 日程数据库操作类
from 研发.llm_client import LLMClient       # LLM 客户端（DeepSeek）
from 研发.service import ScheduleService    # 日程业务逻辑服务类

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_2.web")


def create_app(base_dir: Path, config: dict, scheduler=None) -> Flask:
    """
    工厂函数：创建并配置 Flask 应用实例。

    采用工厂模式（延迟创建），不依赖全局变量，便于测试和多环境部署。

    参数:
      base_dir: 项目根目录（Path 对象），用于定位模板、静态文件、数据库文件
      config: 配置字典，包含 db_name / host / port 等配置项
      scheduler: 后台提醒调度器实例（可选），用于 /api/notifications 接口

    返回:
      已配置好路由和依赖的 Flask 应用实例
    """
    logger.info("开始创建 Flask 应用...")

    # ---------- 路径配置 ----------
    # 模板目录：部署/templates/
    template_dir = base_dir / "部署" / "templates"
    # 静态文件目录：部署/static/（CSS、JS、图片等）
    static_dir = base_dir / "部署" / "static"
    logger.debug("模板目录：%s", template_dir)
    logger.debug("静态资源目录：%s", static_dir)

    # ---------- 创建 Flask 应用 ----------
    # 指定模板和静态文件的实际存储路径
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    # 让 jsonify 直接输出中文，而不是 \uXXXX 编码
    app.json.ensure_ascii = False

    # ---------- 数据库路径 ----------
    db_path = base_dir / config.get("db_name", "schedule_notes.db")
    logger.info("数据库路径：%s", db_path)

    # ---------- 初始化依赖（依赖注入） ----------
    # 创建数据库实例（自动建表）
    database = ScheduleDatabase(db_path)

    # 初始化 LLM 客户端（如果配置了 API Key）
    llm_client = None
    if config.get("llm_api_key"):
        llm_client = LLMClient(config)
        logger.info("LLM 客户端已启用：model=%s", config.get("llm_model", "deepseek-chat"))
    else:
        logger.warning("未配置 llm_api_key，LLM 功能禁用，将使用正则解析模式")

    # 创建服务实例（注入数据库和 LLM 依赖）
    service = ScheduleService(database, llm_client)
    logger.info("Flask 应用创建完成")

    # ========== 路由注册 ==========

    @app.route("/")
    def index():
        """
        首页路由：返回渲染后的 HTML 页面。

        GET / → 返回 部署/templates/index.html
        """
        logger.info("【Web请求】GET / → 首页")
        # render_template 在 template_dir 下查找模板文件
        return render_template("index.html")

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """
        对话接口：接收用户自然语言消息，返回日程处理结果。

        POST /api/chat
        请求体 JSON: { "message": "下午5点开会" }
        响应 JSON:    { "reply": "已添加日程 #1：...", "data": {...} }

        性能：记录接口耗时（毫秒级），方便监控
        """
        t_start = time.time()  # 计时起点

        # 解析 JSON 请求体，silent=True 让解析失败时返回空字典
        payload = request.get_json(silent=True) or {}
        # 提取 message 字段
        message = str(payload.get("message", "")).strip()
        logger.info("【Web请求】POST /api/chat → message=%s", message[:100])

        try:
            # 调用服务层处理消息
            result = service.handle_message(message)
            # 计算耗时（毫秒）
            elapsed = int((time.time() - t_start) * 1000)
            logger.info("【Web响应】/api/chat → %sms, reply=%s",
                       elapsed, result.get("reply", "")[:80])
            # jsonify 序列化为 JSON 响应
            return jsonify(result)
        except Exception as e:
            logger.error("【Web异常】/api/chat 处理失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            # 500 状态码 + 错误提示
            return jsonify({"reply": "服务器出错了，请稍后重试。"}), 500

    @app.route("/api/welcome", methods=["GET"])
    def welcome():
        """
        欢迎语接口：返回个性化问候和使用说明。

        GET /api/welcome
        响应 JSON: { "reply": "早上好！我是你的日程提醒小助手～..." }
        """
        logger.info("【Web请求】GET /api/welcome")
        # 调用服务层生成欢迎语（根据当前时段）
        welcome_msg = service.get_welcome()
        logger.debug("欢迎语：%s", welcome_msg[:60])
        return jsonify({"reply": welcome_msg})

    @app.route("/api/records", methods=["GET"])
    def records():
        """
        数据接口：返回数据库中全部日程记录（含已取消的）。

        GET /api/records
        响应 JSON: { "records": [...] }
        """
        logger.info("【Web请求】GET /api/records")
        try:
            # include_disabled=True 包含已取消的日程
            data = database.find_all_schedules(include_disabled=True)
            # 统计启用和取消的数量
            enabled = sum(1 for r in data if r.get("enabled") == 1)
            disabled = len(data) - enabled
            logger.info("【Web响应】/api/records → 总计%s条（启用%s，取消%s）",
                       len(data), enabled, disabled)
            return jsonify({"records": data})
        except Exception as e:
            logger.error("【Web异常】/api/records 查询失败：%s", e)
            return jsonify({"records": [], "error": str(e)}), 500

    @app.route("/api/notifications", methods=["GET"])
    def notifications():
        """
        提醒通知接口：获取调度器产生的新提醒通知。

        前端定时轮询此接口（如每 5 秒一次），
        每次调用返回新累积的通知并清空调度器队列。

        GET /api/notifications
        响应 JSON: { "notifications": [...] }
        """
        if scheduler:
            # 从调度器获取并清空通知队列
            notes = scheduler.get_notifications()
            if notes:
                logger.info("【Web请求】GET /api/notifications → 推送%s条提醒", len(notes))
            return jsonify({"notifications": notes})

        # 无调度器时返回空列表
        logger.debug("【Web请求】GET /api/notifications → 无调度器")
        return jsonify({"notifications": []})

    # 返回配置好的 Flask 应用实例
    return app

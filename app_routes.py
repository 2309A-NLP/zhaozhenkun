# -*- coding: utf-8 -*-
import time
from datetime import datetime

from flask import jsonify, redirect, render_template, request, session

from app_text import DEFAULT_QUERY, SANITIZED_AVATARS, repair_text
import app_services
from session_manager import SessionManager
from utils import normalize_username


def register_routes(app, qps_monitor):
    """
    注册所有路由函数到Flask应用

    参数:
        app: Flask应用实例
        qps_monitor: QPS监控器实例
    """

    # ==================== 请求拦截器（中间件） ====================

    @app.before_request
    def before_request_timer():
        """在每个请求处理前执行，记录请求开始时间"""
        request._start_time = time.time()  # 将当前时间戳存储到request对象中

    @app.after_request
    def after_request_qps(response):
        """在每个请求处理后执行，记录请求耗时到QPS监控器"""
        start_time = getattr(request, "_start_time", None)  # 获取之前记录的请求开始时间
        if start_time is not None:  # 如果有开始时间记录
            duration_ms = (time.time() - start_time) * 1000  # 计算请求耗时（转换为毫秒）
            # 记录请求到监控器：当前时间戳、耗时、是否成功（状态码<400表示成功）
            qps_monitor.record(time.time(), duration_ms, response.status_code < 400)
        return response  # 返回原始响应对象

    # ==================== 会话管理辅助函数 ====================

    def get_current_session():
        """获取当前登录用户的会话信息"""
        login_id = session.get("login_id")  # 从Flask session中获取登录ID
        if login_id:
            return SessionManager.get_session(login_id)  # 通过SessionManager获取完整会话信息
        return None  # 未登录返回None

    def destroy_current_session():
        """销毁当前用户的会话"""
        login_id = session.get("login_id")  # 获取登录ID
        if login_id:
            SessionManager.destroy_session(login_id)  # 销毁会话
            session.pop("login_id", None)  # 从Flask session中移除登录ID

    def ensure_system_ready():
        """确保RAG系统已就绪，未就绪则返回503错误响应"""
        state = app_services.get_system_state()  # 获取系统状态
        # 如果系统未就绪或RAG系统为None，返回错误信息
        if not state["system_ready"] or state["rag_system"] is None:
            return jsonify({
                "success": False,
                "error": repair_text(state["system_error"]) or "系统尚未完成初始化"
            }), 503  # HTTP 503 Service Unavailable
        return None  # 系统就绪，返回None表示无错误

    # ==================== 页面路由（返回HTML模板） ====================

    @app.route("/")
    def index():
        """首页路由：已登录跳转到聊天页，否则返回登录页"""
        if get_current_session():  # 检查是否已登录
            return redirect("/chat")  # 已登录，跳转到聊天页面
        return render_template("login.html")  # 未登录，返回登录页

    @app.route("/chat")
    def chat_page():
        """聊天页面：未登录则跳转回首页"""
        if get_current_session() is None:  # 检查是否已登录
            return redirect("/")  # 未登录，跳转到登录页
        return render_template("chat.html")  # 已登录，返回聊天页面

    @app.route("/qps")
    def qps_page():
        """QPS监控仪表盘页面"""
        return render_template("qps_dashboard.html")

    @app.route("/performance")
    def performance_page():
        """性能测试仪表盘页面"""
        return render_template("performance_dashboard.html")

    @app.route("/stress")
    def stress_page():
        """压力测试仪表盘页面"""
        return render_template("stress_dashboard.html")

    @app.route("/retrieval")
    def retrieval_page():
        """检索调试仪表盘页面"""
        return render_template("retrieval_dashboard.html")

    @app.route("/load-balancer")
    def load_balancer_page():
        """负载均衡状态仪表盘页面"""
        return render_template("load_balancer_dashboard.html")

    # ==================== API路由（返回JSON数据） ====================

    @app.route("/api/health", methods=["GET"])
    def api_health():
        """健康检查API：返回系统状态"""
        state = app_services.get_system_state()  # 获取系统状态
        return jsonify({
            "status": "ready" if state["system_ready"] else "initializing",  # 系统状态
            "system_ready": state["system_ready"],  # 系统是否就绪
            "error": repair_text(state["system_error"]),  # 错误信息（如果有）
        })

    @app.route("/api/system/overview", methods=["GET"])
    def api_system_overview():
        """系统概览API：返回RAG系统的总体信息"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready  # 系统未就绪，返回503错误
        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        return jsonify({"success": True, "overview": rag_system.get_system_overview()})

    @app.route("/api/current_user", methods=["GET"])
    def api_current_user():
        """获取当前登录用户信息API"""
        current = get_current_session()  # 获取当前会话
        if current:
            return jsonify({"success": True, "username": current.get("username")})
        return jsonify({"success": False, "username": "guest"})  # 未登录返回guest

    @app.route("/api/login", methods=["POST"])
    def api_login():
        """用户登录API"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready

        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据，失败则返回空字典
        username = normalize_username(data.get("username", ""))  # 规范化用户名
        password = data.get("password", "")  # 获取密码
        result = rag_system.login_user(username, password)  # 调用RAG系统登录方法
        if not result.get("success"):
            return jsonify(result)  # 登录失败，返回错误信息

        destroy_current_session()  # 销毁已有的会话（如果有）
        current = SessionManager.build_session(result["username"])  # 创建新会话
        session["login_id"] = current["login_id"]  # 存储登录ID到Flask session
        session.permanent = True  # 设置会话为永久（有超时时间）
        current["current_avatar"] = result.get("avatar_id", "doctor")  # 设置当前角色
        return jsonify({
            "success": True,
            "username": result["username"],
            "avatar_id": current["current_avatar"]
        })

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        """用户登出API"""
        current = get_current_session()  # 获取当前会话
        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        if current and rag_system is not None:
            rag_system.clear_short_memory(current.get("session_id", ""))  # 清除短期记忆
        destroy_current_session()  # 销毁会话
        return jsonify({"success": True})

    @app.route("/api/register", methods=["POST"])
    def api_register():
        """用户注册API"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready

        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据
        username = normalize_username(data.get("username", ""))  # 规范化用户名
        email = data.get("email", "")  # 获取邮箱
        password = data.get("password", "")  # 获取密码
        return jsonify(rag_system.register_user(username, email, password))  # 调用注册方法

    @app.route("/api/avatars", methods=["GET"])
    def api_avatars():
        """获取所有可用角色列表API"""
        avatars = []  # 存储角色列表
        # 遍历所有预定义的角色
        for avatar_id, avatar in SANITIZED_AVATARS.items():
            avatars.append({
                "id": avatar_id,  # 角色ID
                "name": avatar.get("name", avatar_id),  # 角色显示名称
                "icon": avatar.get("icon", "AI"),  # 角色图标
                "color": avatar.get("color", "#14b8a6"),  # 主题颜色
                "desc": avatar.get("desc", ""),  # 角色描述
                "welcome": avatar.get("welcome", ""),  # 欢迎语
                "suggestions": avatar.get("suggestions", []),  # 示例问题列表
            })
        return jsonify({"success": True, "avatars": avatars})

    @app.route("/api/current_avatar", methods=["GET"])
    def api_current_avatar():
        """获取当前用户选择的角色及聊天记录API"""
        current = get_current_session()  # 获取当前会话
        if not current:
            return jsonify({"success": False, "error": "未登录"}), 401  # 未登录返回401

        avatar_id = current.get("current_avatar", "doctor")  # 获取当前角色ID
        avatar = SANITIZED_AVATARS.get(avatar_id, SANITIZED_AVATARS["doctor"])  # 获取角色配置
        messages = current.get("histories", {}).get(avatar_id, [])  # 获取该角色的聊天记录
        return jsonify({
            "success": True,
            "id": avatar_id,
            "avatar_id": avatar_id,
            "name": avatar.get("name", avatar_id),
            "icon": avatar.get("icon", "AI"),
            "color": avatar.get("color", "#14b8a6"),
            "messages": messages,  # 聊天记录
        })

    @app.route("/api/select_avatar", methods=["POST"])
    def api_select_avatar():
        """切换角色API"""
        current = get_current_session()  # 获取当前会话
        if not current:
            return jsonify({"success": False, "error": "未登录"}), 401  # 未登录返回401

        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据
        avatar_id = data.get("avatar_id", "doctor")  # 获取要切换的角色ID
        if avatar_id not in SANITIZED_AVATARS:  # 验证角色ID是否有效
            return jsonify({"success": False, "error": "无效角色"}), 400

        current["current_avatar"] = avatar_id  # 更新当前角色
        if rag_system is not None:
            rag_system.set_user_avatar(current["username"], avatar_id)  # 同步到RAG系统

        avatar = SANITIZED_AVATARS[avatar_id]  # 获取角色配置
        messages = current.get("histories", {}).get(avatar_id, [])  # 获取该角色的聊天记录
        return jsonify({
            "success": True,
            "id": avatar_id,
            "avatar_id": avatar_id,
            "name": avatar.get("name", avatar_id),
            "icon": avatar.get("icon", "AI"),
            "color": avatar.get("color", "#14b8a6"),
            "messages": messages,
        })

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        """聊天对话API：发送问题并获取回答"""
        current = get_current_session()  # 获取当前会话
        if not current:
            return jsonify({"success": False, "error": "请先登录"}), 401  # 未登录返回401

        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready

        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据
        avatar_id = data.get("avatar_id") or current.get("current_avatar", "doctor")  # 获取角色ID
        question = repair_text((data.get("question") or "").strip())  # 清理并获取用户问题
        if not question:  # 验证问题是否为空
            return jsonify({"success": False, "error": "问题不能为空"}), 400

        histories = current.setdefault("histories", {})  # 获取或创建历史记录字典
        history = histories.get(avatar_id, [])  # 获取该角色的历史记录
        # 调用RAG系统的聊天方法
        result = rag_system.chat(
            session_id=current["session_id"],
            username=current["username"],
            avatar_id=avatar_id,
            question=question,
            history_messages=history,
        )

        if result.get("success"):  # 如果回答成功
            # 将用户问题和助手回答添加到历史记录中
            histories[avatar_id] = history + [
                {"role": "user", "content": question, "timestamp": datetime.now().isoformat()},
                {"role": "assistant", "content": result["answer"], "timestamp": datetime.now().isoformat()},
            ]
            # 更新会话中的历史记录
            SessionManager.update_session_history(current["login_id"], avatar_id, histories[avatar_id])
            result["messages"] = histories[avatar_id]  # 将完整历史记录添加到返回结果中
        return jsonify(result)

    @app.route("/api/history", methods=["GET"])
    def api_history():
        """获取聊天历史记录API"""
        current = get_current_session()  # 获取当前会话
        if not current:
            return jsonify({"success": False, "messages": []})  # 未登录返回空列表
        avatar_id = request.args.get("avatar_id", current.get("current_avatar", "doctor"))  # 获取角色ID
        messages = current.get("histories", {}).get(avatar_id, [])  # 获取历史记录
        return jsonify({"success": True, "messages": messages})

    @app.route("/api/clear_history", methods=["POST"])
    def api_clear_history():
        """清除聊天历史记录API"""
        current = get_current_session()  # 获取当前会话
        if not current:
            return jsonify({"success": False, "error": "未登录"}), 401  # 未登录返回401

        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据
        avatar_id = data.get("avatar_id", current.get("current_avatar", "doctor"))  # 获取角色ID
        current.setdefault("histories", {})[avatar_id] = []  # 清空该角色的历史记录
        SessionManager.update_session_history(current["login_id"], avatar_id, [])  # 更新会话存储
        if rag_system is not None:
            rag_system.clear_short_memory(current["session_id"])  # 清除短期记忆
        return jsonify({"success": True})

    @app.route("/api/qps/stats", methods=["GET"])
    def api_qps_stats():
        """获取QPS统计数据API"""
        state = app_services.get_system_state()  # 获取系统状态
        return jsonify({
            "success": True,
            "qps": qps_monitor.snapshot(),  # 获取QPS监控快照数据
            "system_ready": state["system_ready"],
            "system_error": repair_text(state["system_error"]),
        })

    @app.route("/api/load_balancer/stats", methods=["GET"])
    def api_load_balancer_stats():
        """获取负载均衡器统计数据API"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready
        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        return jsonify({"success": True, "stats": rag_system.get_load_balancer_stats()})

    @app.route("/api/retrieval/debug", methods=["GET"])
    def api_retrieval_debug():
        """检索调试API：返回知识库检索的详细信息"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready
        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        query = repair_text((request.args.get("query") or DEFAULT_QUERY).strip())  # 获取查询问题
        top_k = int(request.args.get("top_k", "5"))  # 获取返回结果数量
        return jsonify({"success": True, "debug": rag_system.search_knowledge_debug(query, top_k=top_k)})

    @app.route("/api/performance/run", methods=["POST"])
    def api_performance_run():
        """性能测试API：运行性能测试并返回结果"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready
        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据
        query = repair_text((data.get("query") or DEFAULT_QUERY).strip())  # 获取测试查询
        rounds = int(data.get("rounds", 12))  # 获取测试轮数
        top_k = int(data.get("top_k", 5))  # 获取返回结果数量
        return jsonify({"success": True, "result": rag_system.run_performance_test(query, rounds=rounds, top_k=top_k)})

    @app.route("/api/stress/run", methods=["POST"])
    def api_stress_run():
        """压力测试API：运行压力测试并返回结果"""
        not_ready = ensure_system_ready()  # 检查系统是否就绪
        if not_ready:
            return not_ready
        rag_system = app_services.get_system_state()["rag_system"]  # 获取RAG系统实例
        data = request.get_json(silent=True) or {}  # 获取JSON请求数据
        query = repair_text((data.get("query") or DEFAULT_QUERY).strip())  # 获取测试查询
        concurrency = int(data.get("concurrency", 8))  # 获取并发数
        request_count = int(data.get("request_count", 40))  # 获取总请求数
        top_k = int(data.get("top_k", 5))  # 获取返回结果数量
        return jsonify({
            "success": True,
            "result": rag_system.run_stress_test(
                query,
                concurrency=concurrency,
                request_count=request_count,
                top_k=top_k
            ),
        })

    @app.route("/api/ping", methods=["GET"])
    def api_ping():
        """心跳检测API：简单的健康检查"""
        return jsonify({"success": True, "message": "pong"})
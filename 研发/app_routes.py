"""
app_routes — ADSD 项目在线模块路由配置。

功能说明：
- 定义所有 Flask 路由（页面路由 + API 路由）
- 包括 before_request / after_request 中间件（请求计时与QPS记录）
- 提供登录、注册、聊天、角色切换、历史记录等业务API
- 提供 QPS监控、性能测试、压力测试、检索调试、负载均衡、综合测试等调试API
- 包含会话管理辅助函数（获取/销毁会话、检查系统就绪状态）
"""
# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

import time
# 导入时间模块，用于记录请求开始时间和计算耗时
from datetime import datetime
# 从datetime导入datetime类，用于生成时间戳
from flask import jsonify, redirect, render_template, request, session
# 从flask导入常用工具：jsonify(返回JSON)、redirect(重定向)、render_template(渲染模板)、request(请求对象)、session(会话对象)
from 设计.app_text import DEFAULT_QUERY, SANITIZED_AVATARS, repair_text
# 从文本处理模块导入默认查询文本、清理后的角色配置、文本乱码修复函数
import 研发.app_services as app_services
# 导入应用服务模块（使用别名），用于获取系统状态和RAG系统实例
from 研发.session_manager import SessionManager
# 从会话管理模块导入会话管理器
from 研发.utils import normalize_username
# 从工具模块导入用户名规范化函数


def register_routes(app, qps_monitor):
    # 定义函数：将所有路由注册到Flask应用实例

    """
    注册所有路由函数到Flask应用

    参数:
        app: Flask应用实例
        qps_monitor: QPS监控器实例
    """

    # ==================== 请求拦截器（中间件） ====================

    @app.before_request
    def before_request_timer():
        # 使用装饰器注册：在每个请求处理前执行的中间件
        """在每个请求处理前执行，记录请求开始时间"""
        request._start_time = time.time()
        # 将当前时间戳（秒）存储到request对象的_start_time属性中，供后续中间件使用

    @app.after_request
    def after_request_qps(response):
        # 使用装饰器注册：在每个请求处理后执行的中间件
        """在每个请求处理后执行，记录请求耗时到QPS监控器"""
        start_time = getattr(request, "_start_time", None)
        # 获取之前通过before_request记录的请求开始时间（如果没有则返回None）
        if start_time is not None:
            # 如果有开始时间记录
            duration_ms = (time.time() - start_time) * 1000
            # 计算请求耗时（当前时间减去开始时间，转换为毫秒）
            qps_monitor.record(time.time(), duration_ms, response.status_code < 400)
            # 记录请求到监控器：三个参数分别为时间戳、耗时（毫秒）、是否成功（状态码<400表示成功）
        return response
        # 返回原始响应对象（不修改响应内容）

    # ==================== 会话管理辅助函数 ====================

    def get_current_session():
        # 定义内部函数：获取当前登录用户的会话信息
        """获取当前登录用户的会话信息"""
        login_id = session.get("login_id")
        # 从Flask的session对象中获取存储的登录ID
        if login_id:
            # 如果存在登录ID
            return SessionManager.get_session(login_id)
            # 通过SessionManager的get_session方法获取完整的会话信息
        return None
        # 未登录则返回None

    def destroy_current_session():
        # 定义内部函数：销毁当前用户的会话
        """销毁当前用户的会话"""
        login_id = session.get("login_id")
        # 从Flask session中获取登录ID
        if login_id:
            # 如果有登录ID
            SessionManager.destroy_session(login_id)
            # 调用SessionManager销毁该会话
            session.pop("login_id", None)
            # 从Flask session中移除login_id键

    def ensure_system_ready():
        # 定义内部函数：检查RAG系统是否已初始化完成
        """确保RAG系统已就绪，未就绪则返回503错误响应"""
        state = app_services.get_system_state()
        # 获取当前系统状态（包括system_ready、rag_system、system_error）
        if not state["system_ready"] or state["rag_system"] is None:
            # 如果系统未就绪，或者RAG系统实例为None
            return jsonify({
                "success": False,
                "error": repair_text(state["system_error"]) or "系统尚未完成初始化"
            }), 503
            # 返回JSON错误响应，HTTP状态码503（Service Unavailable）
            # 系统错误信息经过repair_text修复乱码；如果没有错误信息则使用默认提示
        return None
        # 系统就绪，返回None表示无错误（调用方据此判断）

    # ==================== 页面路由（返回HTML模板） ====================

    @app.route("/")
    def index():
        # 定义根路径"/"的路由处理函数
        """首页路由：已登录跳转到聊天页，否则返回登录页"""
        if get_current_session():
            # 检查当前是否已登录（会话是否存在）
            return redirect("/chat")
            # 已登录，重定向到聊天页面
        return render_template("login.html")
        # 未登录，渲染并返回登录页面模板

    @app.route("/chat")
    def chat_page():
        # 定义"/chat"路由处理函数
        """聊天页面：未登录则跳转回首页"""
        if get_current_session() is None:
            # 检查是否未登录
            return redirect("/")
            # 未登录则重定向到首页登录页
        return render_template("chat.html")
        # 已登录，渲染并返回聊天页面模板

    @app.route("/qps")
    def qps_page():
        # 定义"/qps"路由处理函数
        """QPS监控仪表盘页面"""
        return render_template("qps_dashboard.html")
        # 渲染QPS监控仪表盘页面

    @app.route("/performance")
    def performance_page():
        # 定义"/performance"路由处理函数
        """性能测试仪表盘页面"""
        return render_template("performance_dashboard.html")
        # 渲染性能测试仪表盘页面

    @app.route("/stress")
    def stress_page():
        # 定义"/stress"路由处理函数
        """压力测试仪表盘页面"""
        return render_template("stress_dashboard.html")
        # 渲染压力测试仪表盘页面

    @app.route("/retrieval")
    def retrieval_page():
        # 定义"/retrieval"路由处理函数
        """检索调试仪表盘页面"""
        return render_template("retrieval_dashboard.html")
        # 渲染检索调试仪表盘页面

    @app.route("/load-balancer")
    def load_balancer_page():
        # 定义"/load-balancer"路由处理函数
        """负载均衡状态仪表盘页面"""
        return render_template("load_balancer_dashboard.html")
        # 渲染负载均衡状态仪表盘页面

    @app.route("/combined-test")
    def combined_test_page():
        # 定义"/combined-test"路由处理函数
        """综合测试仪表盘页面"""
        return render_template("combined_test_dashboard.html")
        # 渲染综合测试仪表盘页面

    # ==================== API路由（返回JSON数据） ====================

    @app.route("/api/health", methods=["GET"])
    def api_health():
        # 定义健康检查API
        """健康检查API：返回系统状态"""
        state = app_services.get_system_state()
        # 获取系统状态
        return jsonify({
            "status": "ready" if state["system_ready"] else "initializing",
            # 系统状态：就绪返回"ready"，否则返回"initializing"
            "system_ready": state["system_ready"],
            # 系统是否就绪的布尔值
            "error": repair_text(state["system_error"]),
            # 系统错误信息（如果有），经过乱码修复
        })

    @app.route("/api/system/overview", methods=["GET"])
    def api_system_overview():
        # 定义系统概览API
        """系统概览API：返回RAG系统的总体信息"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        return jsonify({"success": True, "overview": rag_system.get_system_overview()})
        # 返回系统概览信息

    @app.route("/api/current_user", methods=["GET"])
    def api_current_user():
        # 定义获取当前用户API
        """获取当前登录用户信息API"""
        current = get_current_session()
        # 获取当前会话
        if current:
            # 如果已登录
            return jsonify({"success": True, "username": current.get("username")})
            # 返回用户名
        return jsonify({"success": False, "username": "guest"})
        # 未登录则返回"guest"

    @app.route("/api/login", methods=["POST"])
    def api_login():
        # 定义用户登录API（POST请求）
        """用户登录API"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应

        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据，silent=True表示解析失败时不抛异常，返回None后再转为空字典
        username = normalize_username(data.get("username", ""))
        # 从请求数据中获取用户名并进行规范化处理
        password = data.get("password", "")
        # 从请求数据中获取密码
        result = rag_system.login_user(username, password)
        # 调用RAG系统的login_user方法验证用户名和密码
        if not result.get("success"):
            # 如果登录失败
            return jsonify(result)
            # 直接返回包含错误信息的结果

        destroy_current_session()
        # 销毁当前已有的会话（如果有的话，确保不重复登录）
        current = SessionManager.build_session(result["username"])
        # 为用户创建新的会话，返回会话信息（包含login_id、session_id等）
        session["login_id"] = current["login_id"]
        # 将登录ID存储到Flask session中（后续请求可通过session.get("login_id")获取）
        session.permanent = True
        # 设置Flask会话为永久（带超时时间的持久化会话）
        current["current_avatar"] = result.get("avatar_id", "doctor")
        # 获取用户上次使用的角色ID，如果没有则为默认的"doctor"
        return jsonify({
            "success": True,
            "username": result["username"],
            "avatar_id": current["current_avatar"]
        })
        # 返回登录成功响应，包含用户名和当前角色ID

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        # 定义用户登出API
        """用户登出API"""
        current = get_current_session()
        # 获取当前会话
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        if current and rag_system is not None:
            # 如果用户已登录且RAG系统可用
            rag_system.clear_short_memory(current.get("session_id", ""))
            # 清除该会话的短期记忆
        destroy_current_session()
        # 销毁会话
        return jsonify({"success": True})
        # 返回登出成功

    @app.route("/api/register", methods=["POST"])
    def api_register():
        # 定义用户注册API
        """用户注册API"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应

        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        username = normalize_username(data.get("username", ""))
        # 规范化用户名
        email = data.get("email", "")
        # 获取邮箱
        password = data.get("password", "")
        # 获取密码
        return jsonify(rag_system.register_user(username, email, password))
        # 调用RAG系统的register_user方法并返回注册结果

    @app.route("/api/avatars", methods=["GET"])
    def api_avatars():
        # 定义获取角色列表API
        """获取所有可用角色列表API"""
        avatars = []
        # 初始化空列表，用于存储角色信息
        for avatar_id, avatar in SANITIZED_AVATARS.items():
            # 遍历所有已清理的角色配置
            avatars.append({
                "id": avatar_id,
                # 角色ID
                "name": avatar.get("name", avatar_id),
                # 角色显示名称，缺省时使用avatar_id
                "icon": avatar.get("icon", "AI"),
                # 角色图标，缺省时使用"AI"
                "color": avatar.get("color", "#14b8a6"),
                # 主题颜色，缺省时使用默认青绿色
                "desc": avatar.get("desc", ""),
                # 角色描述
                "welcome": avatar.get("welcome", ""),
                # 欢迎语
                "suggestions": avatar.get("suggestions", []),
                # 示例问题列表
            })
        return jsonify({"success": True, "avatars": avatars})
        # 返回角色列表

    @app.route("/api/current_avatar", methods=["GET"])
    def api_current_avatar():
        # 定义获取当前角色和聊天记录API
        """获取当前用户选择的角色及聊天记录API"""
        current = get_current_session()
        # 获取当前会话
        if not current:
            # 如果未登录
            return jsonify({"success": False, "error": "未登录"}), 401
            # 返回401未授权错误

        avatar_id = current.get("current_avatar", "doctor")
        # 获取当前角色ID，缺省为"doctor"
        avatar = SANITIZED_AVATARS.get(avatar_id, SANITIZED_AVATARS["doctor"])
        # 获取该角色的配置信息，如果角色不存在则使用doctor
        messages = current.get("histories", {}).get(avatar_id, [])
        # 从会话历史记录中获取该角色的聊天记录
        return jsonify({
            "success": True,
            "id": avatar_id,
            "avatar_id": avatar_id,
            "name": avatar.get("name", avatar_id),
            "icon": avatar.get("icon", "AI"),
            "color": avatar.get("color", "#14b8a6"),
            "messages": messages,
            # 返回当前角色信息和聊天记录
        })

    @app.route("/api/select_avatar", methods=["POST"])
    def api_select_avatar():
        # 定义切换角色API
        """切换角色API"""
        current = get_current_session()
        # 获取当前会话
        if not current:
            # 如果未登录
            return jsonify({"success": False, "error": "未登录"}), 401
            # 返回401未授权错误

        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        avatar_id = data.get("avatar_id", "doctor")
        # 获取要切换到的角色ID
        if avatar_id not in SANITIZED_AVATARS:
            # 验证角色ID是否在有效的角色列表中
            return jsonify({"success": False, "error": "无效角色"}), 400
            # 如果角色ID无效，返回400错误

        current["current_avatar"] = avatar_id
        # 更新当前会话的角色选择
        if rag_system is not None:
            # 如果RAG系统可用
            rag_system.set_user_avatar(current["username"], avatar_id)
            # 同步更新用户在RAG系统中的默认角色设置

        avatar = SANITIZED_AVATARS[avatar_id]
        # 获取新角色的配置信息
        messages = current.get("histories", {}).get(avatar_id, [])
        # 获取该角色的聊天历史记录
        return jsonify({
            "success": True,
            "id": avatar_id,
            "avatar_id": avatar_id,
            "name": avatar.get("name", avatar_id),
            "icon": avatar.get("icon", "AI"),
            "color": avatar.get("color", "#14b8a6"),
            "messages": messages,
            # 返回切换后的角色信息和聊天记录
        })

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        # 定义聊天对话API
        """聊天对话API：发送问题并获取回答"""
        current = get_current_session()
        # 获取当前会话
        if not current:
            # 如果未登录
            return jsonify({"success": False, "error": "请先登录"}), 401
            # 返回401未授权错误

        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应

        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        avatar_id = data.get("avatar_id") or current.get("current_avatar", "doctor")
        # 获取角色ID：优先使用请求中指定的，否则使用当前会话的角色
        question = repair_text((data.get("question") or "").strip())
        # 获取用户问题，去除首尾空白，并进行乱码修复
        if not question:
            # 如果问题为空
            return jsonify({"success": False, "error": "问题不能为空"}), 400
            # 返回400错误

        histories = current.setdefault("histories", {})
        # 在会话中获取或创建histories字典（存储各角色的聊天历史）
        history = histories.get(avatar_id, [])
        # 获取该角色的历史消息列表
        result = rag_system.chat(
            # 调用RAG系统的chat方法处理用户问题
            session_id=current["session_id"],
            # 传入会话ID
            username=current["username"],
            # 传入用户名
            avatar_id=avatar_id,
            # 传入角色ID
            question=question,
            # 传入用户问题
            history_messages=history,
            # 传入历史消息
        )

        if result.get("success"):
            # 如果RAG系统返回成功
            histories[avatar_id] = history + [
                # 将新对话追加到历史记录中
                {"role": "user", "content": question, "timestamp": datetime.now().isoformat()},
                # 用户的问题消息，包含角色和ISO格式时间戳
                {"role": "assistant", "content": result["answer"], "timestamp": datetime.now().isoformat()},
                # 助手的回答消息，包含角色和时间戳
            ]
            SessionManager.update_session_history(current["login_id"], avatar_id, histories[avatar_id])
            # 将会话历史记录更新到SessionManager中（持久化）
            result["messages"] = histories[avatar_id]
            # 将完整的历史记录添加到返回结果中
        return jsonify(result)
        # 返回聊天结果JSON

    @app.route("/api/history", methods=["GET"])
    def api_history():
        # 定义获取聊天历史API
        """获取聊天历史记录API"""
        current = get_current_session()
        # 获取当前会话
        if not current:
            # 如果未登录
            return jsonify({"success": False, "messages": []})
            # 返回空消息列表
        avatar_id = request.args.get("avatar_id", current.get("current_avatar", "doctor"))
        # 从查询参数获取角色ID，缺省使用当前会话的角色
        messages = current.get("histories", {}).get(avatar_id, [])
        # 从会话历史中获取该角色的消息列表
        return jsonify({"success": True, "messages": messages})
        # 返回历史消息

    @app.route("/api/clear_history", methods=["POST"])
    def api_clear_history():
        # 定义清除聊天历史API
        """清除聊天历史记录API"""
        current = get_current_session()
        # 获取当前会话
        if not current:
            # 如果未登录
            return jsonify({"success": False, "error": "未登录"}), 401
            # 返回401未授权错误

        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        avatar_id = data.get("avatar_id", current.get("current_avatar", "doctor"))
        # 获取要清除历史的角色ID
        current.setdefault("histories", {})[avatar_id] = []
        # 清空该角色的历史记录（设为空列表）
        SessionManager.update_session_history(current["login_id"], avatar_id, [])
        # 同步更新SessionManager中的记录（持久化为空）
        if rag_system is not None:
            # 如果RAG系统可用
            rag_system.clear_short_memory(current["session_id"])
            # 清除该会话的短期记忆
        return jsonify({"success": True})
        # 返回清除成功

    @app.route("/api/qps/stats", methods=["GET"])
    def api_qps_stats():
        # 定义QPS统计API
        """获取QPS统计数据API"""
        state = app_services.get_system_state()
        # 获取系统状态
        return jsonify({
            "success": True,
            "qps": qps_monitor.snapshot(),
            # 获取QPS监控器的快照数据（包含当前QPS、历史QPS、成功率等）
            "system_ready": state["system_ready"],
            # 系统就绪状态
            "system_error": repair_text(state["system_error"]),
            # 系统错误信息（经过乱码修复）
        })

    @app.route("/api/load_balancer/stats", methods=["GET"])
    def api_load_balancer_stats():
        # 定义负载均衡统计API
        """获取负载均衡器统计数据API"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        return jsonify({"success": True, "stats": rag_system.get_load_balancer_stats()})
        # 返回负载均衡器统计信息

    @app.route("/api/retrieval/debug", methods=["GET"])
    def api_retrieval_debug():
        # 定义检索调试API
        """检索调试API：返回知识库检索的详细信息"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        query = repair_text((request.args.get("query") or DEFAULT_QUERY).strip())
        # 从查询参数获取检索问题，如果为空则使用默认查询，并进行乱码修复
        top_k = int(request.args.get("top_k", "5"))
        # 获取返回结果数量参数，默认5
        avatar_id = (request.args.get("avatar_id") or "").strip() or None
        # 获取角色ID参数，如果为空则设为None
        return jsonify({"success": True, "debug": rag_system.search_knowledge_debug(query, top_k=top_k, avatar_id=avatar_id)})
        # 执行检索调试并返回详细结果

    @app.route("/api/retrieval/search", methods=["POST"])
    def api_retrieval_search():
        # 定义检索API（用于压测）
        """检索接口：返回适合 JMeter 压测的精简结果"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        query = repair_text((data.get("query") or DEFAULT_QUERY).strip())
        # 获取检索问题
        top_k = int(data.get("top_k", 5))
        # 获取返回结果数量
        include_results = bool(data.get("include_results", False))
        # 获取是否返回命中详情
        avatar_id = (data.get("avatar_id") or "").strip() or None
        # 获取角色ID
        return jsonify({
            "success": True,
            "result": rag_system.run_retrieval_probe(
                query,
                top_k=top_k,
                include_results=include_results,
                avatar_id=avatar_id,
            ),
            # 执行检索探针并返回精简结果
        })

    @app.route("/api/performance/run", methods=["POST"])
    def api_performance_run():
        # 定义性能测试API
        """性能测试API：运行性能测试并返回结果"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        query = repair_text((data.get("query") or DEFAULT_QUERY).strip())
        # 获取测试查询文本
        rounds = int(data.get("rounds", 12))
        # 获取测试轮数，默认12轮
        top_k = int(data.get("top_k", 5))
        # 获取返回结果数量
        return jsonify({"success": True, "result": rag_system.run_performance_test(query, rounds=rounds, top_k=top_k)})
        # 执行性能测试并返回结果

    @app.route("/api/stress/run", methods=["POST"])
    def api_stress_run():
        # 定义压力测试API
        """压力测试API：运行压力测试并返回结果"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        query = repair_text((data.get("query") or DEFAULT_QUERY).strip())
        # 获取测试查询文本
        concurrency = int(data.get("concurrency", 8))
        # 获取并发数，默认8
        request_count = int(data.get("request_count", 40))
        # 获取总请求数，默认40
        top_k = int(data.get("top_k", 5))
        # 获取返回结果数量
        return jsonify({
            "success": True,
            "result": rag_system.run_stress_test(
                query,
                concurrency=concurrency,
                request_count=request_count,
                top_k=top_k
            ),
            # 执行压力测试并返回结果
        })

    @app.route("/api/combined-test/run", methods=["POST"])
    def api_combined_test_run():
        # 定义综合测试API
        """综合测试API：一次返回混合检索、负载均衡和压力测试结果"""
        not_ready = ensure_system_ready()
        # 检查系统是否就绪
        if not_ready:
            # 如果系统未就绪
            return not_ready
            # 返回503错误响应
        rag_system = app_services.get_system_state()["rag_system"]
        # 获取RAG系统实例
        data = request.get_json(silent=True) or {}
        # 获取请求中的JSON数据
        query = repair_text((data.get("query") or DEFAULT_QUERY).strip())
        # 获取测试查询文本
        concurrency = int(data.get("concurrency", 8))
        # 获取并发数
        request_count = int(data.get("request_count", 40))
        # 获取总请求数
        top_k = int(data.get("top_k", 5))
        # 获取返回结果数量
        return jsonify({
            "success": True,
            "result": rag_system.run_combined_test(
                query,
                concurrency=concurrency,
                request_count=request_count,
                top_k=top_k,
            ),
            # 执行综合测试并返回结果
        })

    @app.route("/api/ping", methods=["GET"])
    def api_ping():
        # 定义心跳检测API
        """心跳检测API：简单的健康检查"""
        return jsonify({"success": True, "message": "pong"})
        # 返回pong表示服务正常运行

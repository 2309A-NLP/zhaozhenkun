"""
app.py - RAG工单7 Flask Web展示模块
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 提供Web界面展示10个测试问题、RAG检索结果、
      评估指标和问题分析报告
"""

import logging, json, sys

# 导入配置
from config import LOG_FMT, LOG_DATEFMT, WO_ID, OUTPUT_DIR

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("app")

# 延迟创建Flask应用
app = None


def create_app():
    """
    创建Flask应用（延迟初始化）
    返回:
        Flask应用实例
    """
    from flask import Flask, render_template, jsonify

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["WO_ID"] = WO_ID

    @app.route("/")
    def index():
        """首页展示评估报告"""
        return render_template("index.html", wo_id=WO_ID)

    @app.route("/api/results")
    def api_results():
        """返回评估结果JSON"""
        json_path = OUTPUT_DIR / "evaluation_results.json"
        if not json_path.exists():
            return jsonify({"error": "评估结果未生成，请先运行 run.py"})
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)

    @app.route("/api/summary")
    def api_summary():
        """返回评估摘要"""
        json_path = OUTPUT_DIR / "evaluation_results.json"
        if not json_path.exists():
            return jsonify({"error": "无评估数据"})
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data.get("summary", {}))

    return app


def get_app():
    """获取Flask应用实例（延迟初始化）"""
    global app
    if app is None:
        app = create_app()
    return app


if __name__ == "__main__":
    """启动Web服务"""
    flapp = get_app()
    logger.info(f"启动Web服务: http://127.0.0.1:5007")
    # 避免端口冲突，使用5007
    flapp.run(host="127.0.0.1", port=5007, debug=False)

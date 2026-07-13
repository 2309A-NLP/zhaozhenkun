"""工单19：教育智能体个性化学习推荐项目的主启动入口。"""

# 工单19：导入路径注册工具，确保直接运行 main.py 时可解析项目模块。
import sys

# 工单19：导入路径工具，便于定位项目根目录。
from pathlib import Path


# 工单19：定位项目根目录并加入模块搜索路径。
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 工单19：导入应用工厂函数。
from development.app import create_app


# 工单19：创建 Flask 应用实例。
app = create_app()


# 工单19：在本地开发环境下直接启动服务。
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

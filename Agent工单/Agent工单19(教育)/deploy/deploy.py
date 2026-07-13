"""工单19：项目启动前检查与一键部署脚本。"""

# 工单19：导入路径工具，便于定位项目根目录。
from pathlib import Path

# 工单19：导入路径注册工具，确保可直接运行部署脚本。
import sys


# 工单19：定位当前文件所在目录。
BASE_DIR = Path(__file__).resolve().parents[1]

# 工单19：把项目根目录加入模块搜索路径，保证部署脚本可独立启动。
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 工单19：导入项目数据库初始化逻辑，便于部署前预热数据。
from development.database import initialize_database


# 工单19：检查关键目录是否已经创建完成。
def verify_directories():
    required = [
        BASE_DIR / "development",
        BASE_DIR / "development" / "templates",
        BASE_DIR / "development" / "static",
        BASE_DIR / "tests",
        BASE_DIR / "design",
    ]
    return all(path.exists() for path in required)


# 工单19：执行数据库初始化，确保首次启动即可访问。
def bootstrap_data():
    initialize_database()


# 工单19：输出项目启动建议，辅助本地部署。
def main():
    print("目录检查:", "通过" if verify_directories() else "缺失")
    bootstrap_data()
    print("数据库初始化: 完成")
    print("启动命令: py main.py")
    print("环境变量: DEEPSEEK_API_KEY / QWEN_API_KEY 按需配置")


# 工单19：允许直接执行该脚本查看部署提示。
if __name__ == "__main__":
    main()

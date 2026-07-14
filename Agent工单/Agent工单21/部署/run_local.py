"""文件功能：提供本地启动入口，统一加载 FastAPI 应用并启动 Uvicorn 服务。"""

from __future__ import annotations  # 启用延后类型注解支持。

import sys  # 调整脚本运行时的模块搜索路径。
from pathlib import Path  # 计算项目根目录路径。

import uvicorn  # 导入 Uvicorn 服务启动器。

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 计算项目根目录。
if str(PROJECT_ROOT) not in sys.path:  # 如果项目根目录还未加入模块搜索路径。
    sys.path.insert(0, str(PROJECT_ROOT))  # 把项目根目录加入模块搜索路径。

from 研发.bootstrap import get_container  # 导入全局服务容器获取函数。


def main() -> None:  # 定义本地启动主函数。
    container = get_container()  # 获取全局服务容器。
    uvicorn.run("研发.app:app", host=container.settings.host, port=container.settings.port, reload=False)  # 启动 Web 服务。


if __name__ == "__main__":  # 如果当前文件作为脚本运行。
    main()  # 执行本地启动逻辑。

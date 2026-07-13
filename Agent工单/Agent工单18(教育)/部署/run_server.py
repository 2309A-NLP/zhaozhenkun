# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""run_server.py - 工单18智能助教项目的一键启动脚本。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import os  # 工单18：导入环境变量模块。
import subprocess  # 工单18：导入子进程模块。
from pathlib import Path  # 工单18：导入路径处理类。

BASE_DIR = Path(__file__).resolve().parents[1]  # 工单18：定位项目根目录。
APP_DIR = BASE_DIR / "研发"  # 工单18：定位研发目录。


def main() -> None:  # 工单18：启动 FastAPI 服务。
    port = os.getenv("EDU_AGENT_PORT", "8018")  # 工单18：读取外部传入端口或使用默认端口。
    command = ["py", "-3", "main.py"]  # 工单18：构造启动命令。
    env = os.environ.copy()  # 工单18：复制当前进程环境变量。
    env["EDU_AGENT_PORT"] = port  # 工单18：将目标端口写回子进程环境。
    subprocess.run(command, cwd=APP_DIR, check=True, env=env)  # 工单18：在研发目录下执行启动命令。


if __name__ == "__main__":  # 工单18：判断是否直接执行脚本。
    main()  # 工单18：执行启动逻辑。

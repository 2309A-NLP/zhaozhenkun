# -*- coding: utf-8 -*-
"""
run.py — Agent工单11 项目启动入口
================================================================
功能: 医疗挂号Agent系统启动脚本。
  将研发/目录加入Python搜索路径, 调用 main.py 的 main() 启动 Flask Web 服务。

启动方式:
      cd Agent工单11
      python run.py
      浏览器打开 http://127.0.0.1:5003

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
所属目录: 根目录(入口脚本)
"""
import os
import sys

# 将 研发/ 目录加入搜索路径, 确保后续 import 能找到所有模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "研发"))

from main import main  # Flask 应用主入口

# 启动服务
main()

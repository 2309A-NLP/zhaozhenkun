# -*- coding: utf-8 -*-
"""
run.py — Agent工单9 项目启动入口
================================================================
功能: 数字人与智能体集成系统的统一启动脚本。
      将研发目录加入 Python 搜索路径后，调用 main.py 的 main() 启动 Flask Web 服务。

启动方式:
      cd Agent工单9
      python run.py
      浏览器打开 http://127.0.0.1:5002

服务端口: 5002
核心能力:
      - 文本对话 (POST /api/chat) — 意图识别 → 工具路由 → 回复
      - 语音对话 (POST /api/voice/chat) — 🎤→ASR→Agent→TTS→数字人视频
      - TTS合成 (POST /api/t

      ts) — 文本转语音+声音克隆
      - 数字人视频流 (GET /api/video/stream) — MJPEG 实时流
      - 健康检查 (GET /api/health) — ASR/TTS/DH 状态

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 根目录（入口脚本）
"""
import os
import sys

# 将 研发/ 目录加入搜索路径，确保后续 import 能找到所有模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "研发"))

from main import main  # Flask 应用主入口

# 启动服务
main()

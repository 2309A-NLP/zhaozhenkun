#!/bin/bash
# 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
# 文旅创新智脑 - AI智能体一键启动脚本

echo "============================================================"
echo "  🧠 文旅创新智脑 - AI智能体服务"
echo "  工单编号: CV-AIGC-16"
echo "============================================================"
echo ""

cd "$(dirname "$0")"

echo "[1/2] 检查Python环境..."
python3 --version || python --version

echo ""
echo "[2/2] 安装依赖 & 启动服务..."
pip install -r requirements.txt -q

echo ""
echo "🚀 启动AI智能体服务..."
echo ""
echo "============================================================"
echo "  🌐 前端页面: http://localhost:8765"
echo "  📡 API文档:  http://localhost:8765/docs"
echo "  🤖 对话模型: Kimi / DeepSeek / 千问"
echo "============================================================"
echo ""

python3 server.py || python server.py

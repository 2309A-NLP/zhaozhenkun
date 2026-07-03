#!/bin/bash
# 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
cd "$(dirname "$0")/02_研发/backend"
pip install -r requirements.txt -q 2>/dev/null
python main.py

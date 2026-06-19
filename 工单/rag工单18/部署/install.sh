#!/bin/bash
# 文档质量评估系统安装脚本
# Document Quality Assessment System Installation Script

echo "=========================================="
echo "文档质量评估系统安装脚本"
echo "=========================================="

# 检查Python版本
echo "检查Python版本..."
python_version=$(python3 --version 2>&1)
if [[ $? -ne 0 ]]; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi
echo "Python版本: $python_version"

# 创建虚拟环境（可选）
read -p "是否创建虚拟环境? (y/n): " create_venv
if [[ $create_venv == "y" || $create_venv == "Y" ]]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "虚拟环境已激活"
fi

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

if [[ $? -ne 0 ]]; then
    echo "警告: 部分依赖安装失败，可能影响某些功能"
else
    echo "依赖安装完成"
fi

# 运行测试
read -p "是否运行测试? (y/n): " run_test
if [[ $run_test == "y" || $run_test == "Y" ]]; then
    echo "运行测试..."
    python tests/test_assessment.py
fi

echo "=========================================="
echo "安装完成!"
echo ""
echo "使用方法:"
echo "  1. 评估文档: python main.py assess /path/to/documents -o ./reports"
echo "  2. 启动API: python main.py api --host 0.0.0.0 --port 5000"
echo "  3. 运行演示: python demo.py"
echo "=========================================="
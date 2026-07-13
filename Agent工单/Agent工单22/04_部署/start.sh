#!/bin/bash
# ============================================================
# 多领域智能体长期记忆系统 — 一键启动脚本
# ============================================================
# 用法:
#   chmod +x start.sh
#   ./start.sh              # 启动所有服务
#   ./start.sh --test       # 启动后运行测试
#   ./start.sh --stop       # 停止所有服务
# ============================================================

set -e  # 遇到错误立即退出

# --- 颜色定义，让输出更好看 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # 恢复默认颜色

# 打印带颜色的消息
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- 项目路径 ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"  # 脚本所在目录
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"  # 项目根目录
MEM0_DEPLOY_DIR="$HOME/mem0-deploy"  # mem0 基础服务目录

# --- 检查依赖 ---
check_prerequisites() {
    info "检查依赖..."

    # 检查 Docker
    if ! command -v docker &>/dev/null; then
        error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    success "Docker 已安装"

    # 检查 Python
    if ! command -v python3 &>/dev/null; then
        error "Python3 未安装"
        exit 1
    fi
    success "Python3 已安装"
}

# --- 启动 mem0 基础服务 ---
start_mem0() {
    info "启动 mem0 基础服务 (PostgreSQL + Neo4j + mem0 API)..."
    if [ -d "$MEM0_DEPLOY_DIR" ]; then
        cd "$MEM0_DEPLOY_DIR"
        docker compose up -d 2>&1 | while read line; do
            echo "  $line"
        done
        success "mem0 基础服务已启动"
    else
        warn "mem0-deploy 目录不存在，请先部署 mem0 基础服务"
        warn "参考: ~/mem0-deploy/"
    fi
    cd "$PROJECT_DIR"
}

# --- 安装 Python 依赖 ---
install_deps() {
    info "安装 Python 依赖..."
    cd "$PROJECT_DIR"
    pip install -r 04_部署/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q 2>&1
    success "依赖安装完成"
}

# --- 启动桥接服务 ---
start_bridge() {
    info "启动记忆桥接 API 服务 (端口 8008)..."
    cd "$PROJECT_DIR/02_研发"
    # 后台启动 uvicorn
    nohup python3 agent_bridge.py > /tmp/agent_bridge.log 2>&1 &
    BRIDGE_PID=$!
    echo $BRIDGE_PID > /tmp/agent_bridge.pid
    sleep 2  # 等待服务启动

    # 检查是否启动成功
    if kill -0 $BRIDGE_PID 2>/dev/null; then
        success "桥接服务已启动 (PID: $BRIDGE_PID)"
        success "API 文档: http://localhost:8008/docs"
    else
        error "桥接服务启动失败，查看日志: cat /tmp/agent_bridge.log"
        exit 1
    fi
}

# --- 运行测试 ---
run_tests() {
    info "运行集成测试..."
    cd "$PROJECT_DIR/03_测试"

    # 测试医疗场景
    info "1/3 医疗复诊模拟测试..."
    python3 test_medical.py && success "医疗测试通过" || error "医疗测试未通过"

    # 测试文旅场景
    info "2/3 文旅规划模拟测试..."
    python3 test_tourism.py && success "文旅测试通过" || error "文旅测试未通过"

    # 测试教育场景
    info "3/3 教育辅导模拟测试..."
    python3 test_education.py && success "教育测试通过" || error "教育测试未通过"

    success "全部测试完成"
}

# --- 停止所有服务 ---
stop_all() {
    info "停止记忆桥接服务..."
    if [ -f /tmp/agent_bridge.pid ]; then
        kill "$(cat /tmp/agent_bridge.pid)" 2>/dev/null || true
        rm -f /tmp/agent_bridge.pid
        success "桥接服务已停止"
    fi

    info "停止 mem0 基础服务..."
    if [ -d "$MEM0_DEPLOY_DIR" ]; then
        cd "$MEM0_DEPLOY_DIR"
        docker compose down 2>&1
        success "mem0 基础服务已停止"
    fi
}

# --- 显示状态 ---
show_status() {
    echo ""
    echo "=========================================="
    echo "  服务状态"
    echo "=========================================="
    # mem0 状态
    if curl -s http://localhost:8888/health > /dev/null 2>&1; then
        success "mem0 API      : http://localhost:8888"
    else
        warn "mem0 API      : 未运行"
    fi
    # 桥接 API 状态
    if curl -s http://localhost:8008/api/health > /dev/null 2>&1; then
        success "桥接 API      : http://localhost:8008"
    else
        warn "桥接 API      : 未运行"
    fi
    # PostgreSQL 状态
    if docker ps --format '{{.Names}}' | grep -q mem0-postgres; then
        success "PostgreSQL    : 运行中"
    else
        warn "PostgreSQL    : 未运行"
    fi
    # Neo4j 状态
    if docker ps --format '{{.Names}}' | grep -q mem0-neo4j; then
        success "Neo4j         : 运行中"
    else
        warn "Neo4j         : 未运行"
    fi
    echo "=========================================="
}

# ============================================================
# 主入口
# ============================================================

case "${1:-start}" in
    start)
        # 默认：启动全部服务
        check_prerequisites
        start_mem0
        install_deps
        start_bridge
        show_status
        ;;
    --test)
        # 启动 + 测试
        check_prerequisites
        start_mem0
        install_deps
        start_bridge
        run_tests
        show_status
        ;;
    --stop)
        # 停止服务
        stop_all
        ;;
    --status)
        # 查看状态
        show_status
        ;;
    *)
        echo "用法: $0 [start|--test|--stop|--status]"
        echo "  start     - 启动所有服务（默认）"
        echo "  --test    - 启动后运行集成测试"
        echo "  --stop    - 停止所有服务"
        echo "  --status  - 查看服务状态"
        exit 1
        ;;
esac

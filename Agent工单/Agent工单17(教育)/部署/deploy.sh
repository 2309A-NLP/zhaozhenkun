#!/bin/bash
# ============================================================
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 文件：部署脚本 - 智能备课系统一键部署
# 创建时间：2025年6月
# 使用方式：bash deploy.sh [start|stop|restart|status|test]
# ============================================================

set -e  # 遇到错误立即退出

# 颜色定义 - 终端输出美化
RED='\033[0;31m'    # 红色 - 错误信息
GREEN='\033[0;32m'  # 绿色 - 成功信息
YELLOW='\033[1;33m' # 黄色 - 警告信息
BLUE='\033[0;34m'   # 蓝色 - 步骤信息
NC='\033[0m'        # 无色 - 重置颜色

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"  # 获取项目根目录绝对路径
echo -e "${BLUE}============================================${NC}"  # 打印分隔线
echo -e "${BLUE}  教育Agent智能备课系统 - 部署脚本${NC}"  # 打印标题
echo -e "${BLUE}  工单编号：人工智能NLP-Agent数字人项目-17${NC}"  # 打印工单编号
echo -e "${BLUE}============================================${NC}"  # 打印分隔线

# 创建必要的目录结构
init_dirs() {
    echo -e "${YELLOW}[1/4] 初始化数据目录...${NC}"  # 步骤提示
    mkdir -p "$PROJECT_DIR/data/faiss_index"  # 创建FAISS索引目录
    mkdir -p "$PROJECT_DIR/data/knowledge_base"  # 创建知识库目录
    mkdir -p "$PROJECT_DIR/data/uploads"  # 创建上传目录
    mkdir -p "$PROJECT_DIR/data/exports"  # 创建导出目录
    mkdir -p "$PROJECT_DIR/logs"  # 创建日志目录
    echo -e "${GREEN}  ✓ 目录初始化完成${NC}"  # 成功提示
}

# 检查Python环境
check_python() {
    echo -e "${YELLOW}[2/4] 检查Python环境...${NC}"  # 步骤提示
    if command -v python3 &> /dev/null; then  # Python3已安装
        PYTHON_VERSION=$(python3 --version 2>&1)  # 获取Python版本
        echo -e "${GREEN}  ✓ $PYTHON_VERSION${NC}"  # 打印版本
    else  # Python3未安装
        echo -e "${RED}  ✗ Python3未安装，请先安装Python 3.9+${NC}"  # 错误提示
        exit 1  # 退出脚本
    fi
}

# 安装Python依赖
install_deps() {
    echo -e "${YELLOW}[3/4] 安装Python依赖...${NC}"  # 步骤提示
    cd "$PROJECT_DIR"  # 进入项目目录
    if [ -f "部署/requirements.txt" ]; then  # 依赖文件存在
        pip install -r 部署/requirements.txt \
            -i https://pypi.tuna.tsinghua.edu.cn/simple \
            --quiet  # 静默模式
        echo -e "${GREEN}  ✓ 依赖安装完成${NC}"  # 成功提示
    else  # 依赖文件不存在
        echo -e "${RED}  ✗ requirements.txt 不存在${NC}"  # 错误提示
        exit 1  # 退出脚本
    fi
}

# 启动服务
start_service() {
    echo -e "${YELLOW}[4/4] 启动服务...${NC}"  # 步骤提示
    cd "$PROJECT_DIR/研发"  # 进入研发目录
    # 检查端口是否被占用
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then  # 端口8000已被占用
        echo -e "${RED}  ✗ 端口8000已被占用，请先停止已有服务${NC}"  # 错误提示
        exit 1  # 退出脚本
    fi
    # 后台启动Uvicorn服务
    nohup python3 main.py > ../logs/service.log 2>&1 &  # 后台启动并重定向日志
    SERVICE_PID=$!  # 获取进程ID
    echo $SERVICE_PID > "$PROJECT_DIR/service.pid"  # 保存PID到文件
    sleep 3  # 等待3秒确保服务启动
    # 验证服务是否启动成功
    if kill -0 $SERVICE_PID 2>/dev/null; then  # 进程存在
        echo -e "${GREEN}  ✓ 服务启动成功 (PID: $SERVICE_PID)${NC}"  # 成功提示
        echo -e "${GREEN}  ✓ API地址: http://localhost:8000${NC}"  # API地址
        echo -e "${GREEN}  ✓ API文档: http://localhost:8000/docs${NC}"  # 文档地址
        echo -e "${GREEN}  ✓ 健康检查: http://localhost:8000/health${NC}"  # 健康检查地址
    else  # 进程不存在
        echo -e "${RED}  ✗ 服务启动失败，请检查日志: logs/service.log${NC}"  # 错误提示
        exit 1  # 退出脚本
    fi
}

# 停止服务
stop_service() {
    echo -e "${YELLOW}正在停止服务...${NC}"  # 步骤提示
    if [ -f "$PROJECT_DIR/service.pid" ]; then  # PID文件存在
        PID=$(cat "$PROJECT_DIR/service.pid")  # 读取PID
        if kill -0 $PID 2>/dev/null; then  # 进程存在
            kill $PID  # 终止进程
            echo -e "${GREEN}  ✓ 服务已停止 (PID: $PID)${NC}"  # 成功提示
        fi
        rm -f "$PROJECT_DIR/service.pid"  # 删除PID文件
    else  # PID文件不存在
        echo -e "${YELLOW}  服务未运行${NC}"  # 未运行提示
    fi
}

# 服务状态检查
check_status() {
    if [ -f "$PROJECT_DIR/service.pid" ]; then  # PID文件存在
        PID=$(cat "$PROJECT_DIR/service.pid")  # 读取PID
        if kill -0 $PID 2>/dev/null; then  # 进程存在
            echo -e "${GREEN}服务运行中 (PID: $PID)${NC}"  # 运行中
            # 尝试调用健康检查接口
            if command -v curl &> /dev/null; then  # curl可用
                HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{"error":"无法连接"}')  # 健康检查
                echo -e "健康状态: $HEALTH"  # 打印健康信息
            fi
        else  # 进程不存在
            echo -e "${RED}服务已停止（PID文件过期）${NC}"  # 已停止
        fi
    else  # PID文件不存在
        echo -e "${YELLOW}服务未运行${NC}"  # 未运行
    fi
}

# 运行测试
run_tests() {
    echo -e "${YELLOW}运行测试用例...${NC}"  # 步骤提示
    cd "$PROJECT_DIR/测试"  # 进入测试目录
    python3 test_lesson_generator.py  # 运行备课生成器测试
    python3 test_api.py  # 运行API测试
    echo -e "${GREEN}  ✓ 测试完成${NC}"  # 成功提示
}

# 主流程 - 根据参数执行不同操作
case "${1:-start}" in  # 默认操作为start
    start)  # 启动服务
        init_dirs  # 初始化目录
        check_python  # 检查Python
        install_deps  # 安装依赖
        start_service  # 启动服务
        ;;
    stop)  # 停止服务
        stop_service  # 停止服务
        ;;
    restart)  # 重启服务
        stop_service  # 停止服务
        sleep 2  # 等待2秒
        init_dirs  # 初始化目录
        start_service  # 启动服务
        ;;
    status)  # 查看状态
        check_status  # 检查状态
        ;;
    test)  # 运行测试
        check_python  # 检查Python
        install_deps  # 安装依赖
        run_tests  # 运行测试
        ;;
    *)  # 其他参数
        echo "用法: $0 {start|stop|restart|status|test}"  # 使用说明
        echo "  start   - 初始化并启动服务 (默认)"  # 启动说明
        echo "  stop    - 停止服务"  # 停止说明
        echo "  restart - 重启服务"  # 重启说明
        echo "  status  - 查看服务状态"  # 状态说明
        echo "  test    - 运行测试用例"  # 测试说明
        exit 1  # 退出
        ;;
esac

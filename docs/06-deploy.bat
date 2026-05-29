@echo off
chcp 65001 >nul
title ADSD 多角色对话系统 - 启动器
echo ============================================
echo   ADSD 多角色对话系统 - 部署启动脚本
echo ============================================
echo.
echo 请选择操作：
echo  1. 启动全部服务 (Milvus + Redis + MySQL + Web)
echo  2. 启动 Web 服务（需先启动数据库）
echo  3. 离线数据预处理
echo  4. 检查依赖服务
echo  5. 构建向量索引
echo  6. 查看说明
echo  0. 退出
echo.

set /p choice="请输入编号 (0-6): "

if "%choice%"=="1" goto start_all
if "%choice%"=="2" goto start_web
if "%choice%"=="3" goto offline_processor
if "%choice%"=="4" goto check_services
if "%choice%"=="5" goto build_index
if "%choice%"=="6" goto show_help
if "%choice%"=="0" goto end
echo 无效输入
goto end

:start_all
echo.
echo [1/4] 检查 Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未运行，请先启动 Docker Desktop
    pause
    goto end
)
echo ✅ Docker 运行中

echo [2/4] 启动 Milvus + Redis + MySQL...
docker compose -f docker-compose.yml up -d milvus redis mysql 2>nul
if exist docker-compose.yml (
    echo ✅ 服务已启动
) else (
    echo ⚠️ 未找到 docker-compose.yml，跳过
)

echo [3/4] 检查服务端口...
python main.py offline check

echo [4/4] 启动 Web 服务...
python main.py online
goto end

:start_web
echo.
echo 启动 Web 服务...
echo 确保 Milvus、Redis、MySQL 已运行
python main.py online
goto end

:offline_processor
echo.
echo 运行离线数据预处理...
python main.py offline processor
echo.
echo 数据预处理完成！
pause
goto end

:check_services
echo.
echo 检查依赖服务...
python main.py offline check
pause
goto end

:build_index
echo.
echo 构建向量索引...
echo 确保 BGE-M3 模型已下载到 models/bge-m3/
echo 确保 Milvus 已运行
echo.
python main.py offline index
echo.
echo 向量索引构建完成！
pause
goto end

:show_help
echo.
echo ============================================
echo   ADSD 多角色对话系统
echo   AI-Driven Student Development
echo ============================================
echo.
echo 访问地址:
echo   聊天页面:   http://localhost:5010/chat
echo   QPS监控:    http://localhost:5010/qps
echo   性能测试:    http://localhost:5010/performance
echo   负载均衡:   http://localhost:5010/load-balancer
echo.
echo 角色列表:
echo   医生         - 健康建议、症状分析
echo   心理医生     - 情绪疏导、压力陪伴
echo   营销专家     - 品牌增长、内容策划
echo   语文老师     - 课文讲解、文言文分析
echo.
echo 离线命令:
echo   python main.py offline processor  - 数据预处理
echo   python main.py offline index      - 向量索引构建
echo   python main.py offline check      - 端口检查
echo   python main.py offline analyze    - 数据分析
echo   python main.py offline pdf        - PDF导入Milvus
echo.
pause
goto end

:end
echo.
echo 按任意键退出...
pause >nul

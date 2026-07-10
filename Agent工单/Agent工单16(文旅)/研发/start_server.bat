@echo off
chcp 65001 >nul
:: 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
:: 文旅创新智脑 - AI智能体一键启动 (Windows)

echo ============================================================
echo   文旅创新智脑 - AI智能体服务 v2.0
echo   工单: CV-AIGC-16
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 检查Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Python，请先安装Python 3.9+
    pause
    exit /b 1
)
python --version

echo.
echo [2/3] 安装依赖...
pip install fastapi uvicorn httpx python-pptx pydantic -q
if errorlevel 1 (
    echo [WARN] 部分依赖安装失败，尝试继续...
)

echo.
echo [3/3] 启动服务...
echo.
echo   http://localhost:8765     前端页面
echo   http://localhost:8765/docs  API文档
echo.
echo   按 Ctrl+C 停止
echo ============================================================

python server.py
pause

@echo off
REM 文档质量评估系统启动脚本

set ROOT_DIR=%~dp0..
cd /d "%ROOT_DIR%"

echo ==========================================
echo 文档质量评估系统启动脚本
echo ==========================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

if exist "venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
)

:menu
echo.
echo 请选择操作:
echo 1. 评估文档
echo 2. 启动API服务
echo 3. 运行演示
echo 4. 运行测试
echo 5. 退出
echo.

set /p choice="请输入选择 (1-5): "

if "%choice%"=="1" goto assess
if "%choice%"=="2" goto api
if "%choice%"=="3" goto demo
if "%choice%"=="4" goto test
if "%choice%"=="5" goto exit
echo 无效选择，请重新输入
goto menu

:assess
echo.
set /p input_path="请输入文档路径: "
set /p output_dir="请输入报告输出目录 (默认: 测试\reports): "
if "%output_dir%"=="" set output_dir=测试\reports

echo 开始评估文档...
python run.py --assess "%input_path%" --output "%output_dir%" --summary
pause
goto menu

:api
echo.
set /p port="请输入API端口 (默认: 5000): "
if "%port%"=="" set port=5000

echo 启动API服务...
echo 访问地址: http://localhost:%port%
python run.py --api --host 0.0.0.0 --port %port% --debug
pause
goto menu

:demo
echo.
echo 运行演示...
python 测试\demo.py
pause
goto menu

:test
echo.
echo 运行测试...
python 测试\test_assessment.py
pause
goto menu

:exit
echo 感谢使用文档质量评估系统!
pause
exit /b 0

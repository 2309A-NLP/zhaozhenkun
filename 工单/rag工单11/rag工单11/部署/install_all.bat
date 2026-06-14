@echo off
chcp 65001 >nul
title Embedding微调-环境安装

echo ========================================
echo  Embedding模型微调 - 环境一键安装
echo ========================================
echo.

:: ====== 1. 先装CPU版PyTorch（从阿里云，快）======
echo [1/5] 安装 PyTorch (CPU版 — 数据准备和评估可用)...
d:\conda\python.exe -m pip install torch torchvision torchaudio -i https://mirrors.aliyun.com/pypi/simple/
if %ERRORLEVEL% NEQ 0 (
    echo [失败] PyTorch 安装失败，请检查网络
    pause
    exit /b 1
)
echo [完成] PyTorch 安装成功！
echo.

:: ====== 2. 安装其他依赖 ======
echo [2/5] 安装 transformers...
d:\conda\python.exe -m pip install transformers -i https://mirrors.aliyun.com/pypi/simple/

echo [3/5] 安装 sentence-transformers + peft...
d:\conda\python.exe -m pip install sentence-transformers peft -i https://mirrors.aliyun.com/pypi/simple/

echo [4/5] 安装 pymupdf + accelerate + datasets...
d:\conda\python.exe -m pip install pymupdf accelerate datasets -i https://mirrors.aliyun.com/pypi/simple/

echo [完成] 所有基础依赖安装完成！
echo.

:: ====== 3. 尝试安装CUDA版PyTorch ======
echo [5/5] 尝试安装 PyTorch CUDA 版（2.5GB，网络慢可能超时）...
echo   如果失败，可稍后手动重试以下命令：
echo   d:\conda\python.exe -m pip install torch==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124
echo.
:: 尝试下载，给30分钟超时
d:\conda\python.exe -m pip install torch==2.5.1+cu124 torchvision==0.20.1+cu124 torchaudio==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124 --default-timeout=1800
if %ERRORLEVEL% EQU 0 (
    echo [完成] CUDA版 PyTorch 安装成功！
) else (
    echo [注意] CUDA版 PyTorch 未安装成功，CPU版可用。
    echo   你可以稍后在Windows PowerShell里手动下载：
    echo   Start-BitsTransfer -Source 'https://download.pytorch.org/whl/cu124/torch-2.5.1%%2Bcu124-cp312-cp312-win_amd64.whl' -Destination 'C:\Users\31326\Desktop\rag工单11\torch_cuda.whl'
    echo   然后运行：d:\conda\python.exe -m pip install C:\Users\31326\Desktop\rag工单11\torch_cuda.whl
)

echo.
echo ========================================
echo 安装完成！
echo.
echo 运行方式：
echo   python main.py          -- 一键全流程
echo   python main.py --step 1 -- 仅数据准备
echo   python main.py --step 2 -- 仅基线评估
echo   python main.py --step 3 -- 仅微调训练
echo ========================================
pause

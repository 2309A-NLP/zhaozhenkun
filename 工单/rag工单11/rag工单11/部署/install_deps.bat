@echo off
echo 正在安装 Embedding 微调所需依赖...
echo.

echo [1/6] 安装 PyTorch+CUDA...
d:\conda\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo [2/6] 安装 transformers...
d:\conda\python.exe -m pip install transformers -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo [3/6] 安装 sentence-transformers...
d:\conda\python.exe -m pip install sentence-transformers -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo [4/6] 安装 peft (LoRA)...
d:\conda\python.exe -m pip install peft -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo [5/6] 安装 pymupdf (PDF解析)...
d:\conda\python.exe -m pip install pymupdf -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo [6/6] 安装 accelerate + datasets...
d:\conda\python.exe -m pip install accelerate datasets -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo 全部安装完成！
pause

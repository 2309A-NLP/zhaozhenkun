@echo off
echo 配置 conda 国内镜像...
d:\conda\condabin\conda.bat config --remove-key channels 2>nul
d:\conda\condabin\conda.bat config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
d:\conda\condabin\conda.bat config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
d:\conda\condabin\conda.bat config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r/
d:\conda\condabin\conda.bat config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/msys2/
d:\conda\condabin\conda.bat config --set show_channel_urls yes
echo.
echo 安装 PyTorch CUDA 版...
echo 注意: 如果 conda 版本太新，pytorch 包名可能是 pytorch 或 pytorch-cuda
d:\conda\condabin\conda.bat install -y -c conda-forge pytorch torchvision torchaudio cudatoolkit=12.1 --repodata-fn repodata.json
echo.
echo 安装完成，验证...
d:\conda\python.exe -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"
pause

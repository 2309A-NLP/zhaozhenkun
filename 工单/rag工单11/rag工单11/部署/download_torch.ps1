#requires -Version 5.0
$url = "https://download.pytorch.org/whl/cu124/torch-2.5.1%2Bcu124-cp312-cp312-win_amd64.whl"
$dest = "C:\Users\31326\Desktop\rag工单11\torch-2.5.1+cu124-cp312-cp312-win_amd64.whl"

Write-Host "正在下载 PyTorch CUDA wheel (2.5GB)..."
Write-Host "URL: $url"
Write-Host "保存到: $dest"
Write-Host ""

try {
    # 用 BITS 下载，支持断点续传
    Start-BitsTransfer -Source $url -Destination $dest -Asynchronous -Priority High
    $job = Get-BitsTransfer | Where-Object {$_.JobState -ne "Transferred"}
    
    while ($job) {
        $pct = [math]::Round($job.BytesTransferred / $job.BytesTotal * 100, 1)
        $transferred = [math]::Round($job.BytesTransferred / 1MB, 0)
        $total = [math]::Round($job.BytesTotal / 1MB, 0)
        Write-Progress -Activity "下载 PyTorch CUDA" -PercentComplete $pct -Status "$pct% ($transferred MB / $total MB)"
        Start-Sleep -Seconds 5
        $job = Get-BitsTransfer | Where-Object {$_.JobState -ne "Transferred"}
    }
    
    # 完成传输
    Get-BitsTransfer | Complete-BitsTransfer
    Write-Host "下载完成！" -ForegroundColor Green
    
    # 验证文件
    $file = Get-Item $dest
    Write-Host "文件大小: $([math]::Round($file.Length / 1MB, 0)) MB"
    
    # 安装
    Write-Host ""
    Write-Host "正在安装 PyTorch..."
    & "D:\conda\python.exe" -m pip install $dest
    Write-Host "安装完成！" -ForegroundColor Green
    
} catch {
    Write-Host "下载失败: $_" -ForegroundColor Red
    # 尝试普通下载
    Write-Host "尝试使用 WebClient 下载..."
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($url, $dest)
    Write-Host "下载完成！"
}

# 验证
& "D:\conda\python.exe" -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"
Read-Host "按回车退出"

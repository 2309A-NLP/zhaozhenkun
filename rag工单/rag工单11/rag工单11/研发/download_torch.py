import logging
logger = logging.getLogger(__name__)
"""多线程下载 PyTorch CUDA wheel"""
import urllib.request
import sys
import os

url = "https://download.pytorch.org/whl/cu124/torch-2.5.1%2Bcu124-cp312-cp312-win_amd64.whl"
dest = "/mnt/c/Users/31326/Desktop/rag工单11/torch-2.5.1+cu124-cp312-cp312-win_amd64.whl"

# 先检查是否已有部分下载
if os.path.exists(dest):
    existing = os.path.getsize(dest)
    if existing > 2_500_000_000:
        print(f"文件已完整下载: {existing} bytes")
        sys.exit(0)
    print(f"已有部分下载: {existing/1e6:.0f} MB，继续...")
else:
    existing = 0

# 获取文件大小
req = urllib.request.Request(url, method='HEAD')
with urllib.request.urlopen(req, timeout=30) as resp:
    total = int(resp.headers['Content-Length'])
print(f"总大小: {total/1e6:.0f} MB")

# 断点续传下载
headers = {'User-Agent': 'Mozilla/5.0'}
if existing > 0:
    headers['Range'] = f'bytes={existing}-'

req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=600) as resp:
    mode = 'ab' if existing > 0 else 'wb'
    with open(dest, mode) as f:
        downloaded = existing
        while True:
            chunk = resp.read(8*1024*1024)  # 8MB chunks
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            pct = downloaded * 100 / total
            print(f"\r  进度: {downloaded/1e6:.0f}/{total/1e6:.0f} MB ({pct:.1f}%)", end='', flush=True)

print(f"\n下载完成！文件: {dest}")

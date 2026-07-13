# 该文件用于定义本地与容器部署时的启动命令。
python -m pip install -r deploy/requirements.txt
set -a && source deploy/.env.example && set +a
uvicorn development.server.app:app --host 127.0.0.1 --port 8000 --reload

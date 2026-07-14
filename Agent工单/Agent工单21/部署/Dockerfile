FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r 部署/requirements.txt
CMD ["python", "部署/run_local.py"]

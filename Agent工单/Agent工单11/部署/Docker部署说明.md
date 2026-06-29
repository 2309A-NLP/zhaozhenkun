# Docker 部署说明 — 医疗挂号Agent系统

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务

## 一、快速启动

```bash
cd Agent工单11/部署
docker compose up -d
# 浏览器打开 http://localhost:5003
```

## 二、本地开发启动

```bash
cd Agent工单11
python run.py
# 浏览器打开 http://127.0.0.1:5003
```

## 三、API端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 聊天UI界面 |
| `/api/chat` | POST | 文本对话(主接口) |
| `/api/health` | GET | 健康检查 |

## 四、测试

```bash
# 先启动服务
python run.py &
# 运行测试
python 测试/test_6_cases.py
```

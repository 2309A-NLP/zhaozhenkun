---
name: verify
description: 启动 Flask 仪表盘并用 HTTP/浏览器方式验证个性化学习推荐流程。
---

# 项目验证方法

1. 启动应用：`py main.py`
2. 打开首页：`http://127.0.0.1:5000/`
3. 验证首页是否展示学习画像、学习路径、今日任务、错题本、资源推荐。
4. 调用 `GET /api/questions?student_id=1` 获取推荐练习题。
5. 调用 `POST /api/practice/submit` 提交答案，确认会更新画像并生成错题本。
6. 调用 `GET /api/dashboard?student_id=1` 检查 `wrong_book`、`trend_points`、`summary` 是否变化。
7. 边界检查：空 `answers` 应返回 `400`。

注意：如果未配置 `DEEPSEEK_API_KEY` 或 `QWEN_API_KEY`，系统会使用本地兜底错题解析。
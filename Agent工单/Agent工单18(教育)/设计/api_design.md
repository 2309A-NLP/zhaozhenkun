# api_design.md

- `POST /api/auth/login`：用户名密码登录，返回 `access_token` 与脱敏 `user`
- `GET /api/me`：返回当前登录用户公开信息
- `GET /api/dashboard`：返回工作台统计
- `POST /api/knowledge/text`：新增文本知识资源
- `POST /api/knowledge/file`：上传文件或图片知识资源
- `GET /api/knowledge/list`：按范围与类型列出可访问资源
- `GET /api/knowledge/{resource_id}`：查看资源详情与结构化片段
- `DELETE /api/knowledge/{resource_id}`：删除当前用户自己上传的资源
- `POST /api/knowledge/search`：仅执行检索并返回结构化引用
- `POST /api/assistant/ask`：执行检索增强问答并返回答案与引用

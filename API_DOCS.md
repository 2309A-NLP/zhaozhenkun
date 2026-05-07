# API 接口文档

## 页面路由

- `GET /`
  - 登录页。
- `GET /chat`
  - 聊天页。未登录时重定向到 `/`。

## 系统接口

- `GET /api/status`
  - 返回系统状态、模型加载情况、检索能力状态。
- `GET /api/evaluate`
  - 返回检索评估报告。
- `GET /api/docs`
  - 返回结构化接口文档。
- `GET /api/docs/markdown`
  - 返回 Markdown 文档。

## 用户接口

- `POST /api/login`
  - 请求：`{"username": "任意字符串", "password": "任意字符串"}`
  - 说明：当前版本允许任意输入登录；为空时自动生成访客名。
- `POST /api/logout`
  - 退出当前会话，并清空本次登录下的所有角色对话。
- `POST /api/register`
  - 兼容接口。当前版本会直接创建或更新用户，不要求严格校验。
- `GET /api/current_user`
  - 返回当前登录用户名。

## 角色接口

- `GET /api/avatars`
  - 返回三位角色的基础信息和建议问题。
- `GET /api/current_avatar`
  - 返回当前选中的角色。
- `POST /api/select_avatar`
  - 请求：`{"avatar_id": "doctor|psychologist|marketer"}`
  - 返回：角色信息和该角色当前会话消息。

## 对话接口

- `POST /api/chat`
  - 请求：`{"avatar_id": "doctor", "question": "..." }`
  - 返回：
    - `answer`
    - `messages`
    - `retrieved_count`
    - `retrieval_method`
    - `load_balancer_endpoint`
- `GET /api/history?avatar_id=doctor`
  - 返回当前登录会话中该角色的消息列表。
- `POST /api/clear_history`
  - 请求：`{"avatar_id": "doctor"}`
  - 清空当前登录会话中该角色的消息列表。

## 检索增强能力

- BGE-M3 向量化模型：`C:\Users\31326\Desktop\bge-m3`
- BGE-Reranker 重排序模型：`C:\Users\31326\Desktop\bge-reranker-base`
- 多路召回：向量检索 + BM25 + TF-IDF
- 融合排序：RRF + Reranker
- 余弦相似度过滤：融合结果二次过滤
- 知识库数据增强：同义词扩展用于词法召回索引
- 短期记忆增强：角色级会话记忆窗口
- 大模型输出优化：去冗余、压缩、引用提示
- 负载均衡：OpenAI 兼容端点轮询调度

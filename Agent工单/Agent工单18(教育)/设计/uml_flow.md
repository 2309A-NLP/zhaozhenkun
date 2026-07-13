# uml_flow.md

1. 用户登录 -> 获取脱敏用户信息与 Bearer Token
2. 文本/文件/图片上传 -> 解析器统一输出 content_text + chunks + location
3. 资源写入状态文件 -> 公共库或私有库隔离存储
4. 用户提问 -> 公私资源过滤 -> 关键词召回 + 语义召回 -> 融合排序
5. 助教回答 -> 返回答案、references、citations
6. 前端展示 -> 问答区、引用区、资源详情区同步更新

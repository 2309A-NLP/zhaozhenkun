# 该文件用于沉淀技能化架构设计说明。

## 设计目标
- 将单一 Agent 重构为可编排的 `SKILLS` 架构。
- 覆盖文旅、教育、医疗三类领域场景。
- 保持目录按 `设计 / 研发 / 测试 / 部署 / 优化` 分层。
- 保证单个 Python 文件不超过 300 行。

## 核心设计
- `development/core` 负责配置、模型、路由、记忆等基础能力。
- `development/skills` 负责技能实现，按通用 / 文旅 / 教育 / 医疗拆分。
- `development/services` 负责技能注册与智能体编排。
- `development/server` 提供 FastAPI 接口。
- `design/skills/*/skill.md` 负责沉淀每个领域 Skill 的标准元数据、输入输出示例与依赖关系。
- `optimization` 保留性能与扩展建议。

## 默认模型接入
- 默认提供方为 `deepseek`。
- 兼容切换到 `qwen` 兼容接口。
- 通过环境变量注入 `base_url`、`model` 与 `api_key`。

## 联网技能接入
- `skill_web_search` 已接入公开搜索能力，优先调用 DuckDuckGo，并在无结果时回退到中文维基检索。
- `skill_weather_check` 已接入 Open-Meteo 地理编码与天气预报接口，可返回未来 3 天天气摘要。
- `skill_drug_info_query` 已接入 openFDA 药品标签接口，并对常见中文药名做英文通用名归一化。
- 联网接口失败时保留明确降级提示，不会让主流程直接崩溃。

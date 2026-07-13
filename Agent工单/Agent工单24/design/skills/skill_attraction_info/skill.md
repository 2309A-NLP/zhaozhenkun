# skill_attraction_info

## 功能描述
- 提供文旅场景下的景点基础信息检索能力。
- 面向景点简介、门票、开放时间、交通方式等问题输出公开信息摘要。
- 当前通过公开搜索服务聚合结果，并返回适合大模型二次整合的文本。

## 调用方式
- 技能名：`skill_attraction_info`
- 适用领域：`tourism`
- Python 实现位置：`development/skills/tourism_skills.py`
- 依赖服务：`development/services/search_service.py`

## 输入示例
```json
{
  "query": "帮我介绍一下北京故宫的门票和开放时间",
  "domain": "tourism",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_attraction_info",
  "domain": "tourism",
  "content": "1. 故宫：... 来源：https://...\n2. 故宫博物院：... 来源：https://..."
}
```

## 依赖关系
- 依赖 `SearchService.search()` 获取公开搜索结果。
- 由 `SkillRegistry` 注册并注入到 `AttractionInfoSkill`。
- 输出结果会被 `AgentService` 汇总进最终提示词。

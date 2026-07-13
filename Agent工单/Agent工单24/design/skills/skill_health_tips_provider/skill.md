# skill_health_tips_provider

## 功能描述
- 提供医疗场景下的通用健康提示能力。
- 输出生活方式、休息、补水、观察风险信号等保守建议。
- 不进行确诊，不替代线下医疗服务。

## 调用方式
- 技能名：`skill_health_tips_provider`
- 适用领域：`medical`
- Python 实现位置：`development/skills/medical_skills.py`
- 依赖服务：无外部服务依赖

## 输入示例
```json
{
  "query": "最近喉咙痛该注意什么",
  "domain": "medical",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_health_tips_provider",
  "domain": "medical",
  "content": "建议保持补水、规律作息、清淡饮食，并持续观察是否出现高热、呼吸困难等预警信号。"
}
```

## 依赖关系
- 由 `SkillRegistry` 注册到医疗技能集合。
- 输出结果会被 `AgentService` 汇总进最终提示词。
- 需要与最终系统提示中的医疗安全边界配合使用。

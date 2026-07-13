# skill_symptom_analyzer

## 功能描述
- 提供医疗场景下的症状分析与分诊建议。
- 只输出保守型健康建议，不替代医生诊断。
- 强调症状记录、风险观察与线下就医边界。

## 调用方式
- 技能名：`skill_symptom_analyzer`
- 适用领域：`medical`
- Python 实现位置：`development/skills/medical_skills.py`
- 依赖服务：无外部服务依赖

## 输入示例
```json
{
  "query": "我发烧咳嗽应该怎么办",
  "domain": "medical",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_symptom_analyzer",
  "domain": "medical",
  "content": "建议先记录症状持续时间、伴随表现与体温变化；若症状加重或持续不缓解，应尽快线下就医。"
}
```

## 依赖关系
- 由 `SkillRegistry` 注册到医疗技能集合。
- 输出结果会被 `AgentService` 汇总进最终提示词。
- 需要与最终系统提示中的医疗安全边界配合使用。

# skill_knowledge_point_explain

## 功能描述
- 提供教育场景下的知识点讲解能力。
- 适合概念解释、公式原理、例题带学与误区说明。
- 当前输出知识讲解框架，供大模型展开教学式回答。

## 调用方式
- 技能名：`skill_knowledge_point_explain`
- 适用领域：`education`
- Python 实现位置：`development/skills/education_skills.py`
- 依赖服务：无外部服务依赖

## 输入示例
```json
{
  "query": "请讲解牛顿第二定律",
  "domain": "education",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_knowledge_point_explain",
  "domain": "education",
  "content": "建议从定义、原理、例题与常见误区四个层次讲解。"
}
```

## 依赖关系
- 由 `SkillRegistry` 注册到教育技能集合。
- 输出结果会被 `AgentService` 汇总进最终提示词。

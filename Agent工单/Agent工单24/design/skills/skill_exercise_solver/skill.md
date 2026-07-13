# skill_exercise_solver

## 功能描述
- 提供教育场景下的题目求解框架能力。
- 适合数学、物理等具有明确解题路径的问题。
- 当前输出结构化解题建议，供大模型组织完整答案。

## 调用方式
- 技能名：`skill_exercise_solver`
- 适用领域：`education`
- Python 实现位置：`development/skills/education_skills.py`
- 依赖服务：无外部服务依赖

## 输入示例
```json
{
  "query": "请解这道二次函数题",
  "domain": "education",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_exercise_solver",
  "domain": "education",
  "content": "建议按‘已知条件-目标结论-解题步骤-结果校验’四段式组织答案。"
}
```

## 依赖关系
- 由 `SkillRegistry` 注册到教育技能集合。
- 输出结果会被 `AgentService` 汇总进最终提示词。

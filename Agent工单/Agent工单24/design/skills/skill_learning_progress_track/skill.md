# skill_learning_progress_track

## 功能描述
- 提供教育场景下的学习进度规划与跟踪建议。
- 适合复习计划、阶段安排、错题回顾与学习节奏控制。
- 当前输出学习计划框架，供大模型生成个性化学习建议。

## 调用方式
- 技能名：`skill_learning_progress_track`
- 适用领域：`education`
- Python 实现位置：`development/skills/education_skills.py`
- 依赖服务：无外部服务依赖

## 输入示例
```json
{
  "query": "帮我做一个下周的复习计划",
  "domain": "education",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_learning_progress_track",
  "domain": "education",
  "content": "建议拆分为每日目标、每周回顾、错题整理与阶段测评四部分。"
}
```

## 依赖关系
- 由 `SkillRegistry` 注册到教育技能集合。
- 输出结果会被 `AgentService` 汇总进最终提示词。

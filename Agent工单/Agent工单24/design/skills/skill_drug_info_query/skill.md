# skill_drug_info_query

## 功能描述
- 提供医疗场景下的药品公开标签查询能力。
- 支持常见中文药名归一化到英文通用名，再调用 openFDA 查询。
- 输出适应症、用法用量、警示与不良反应摘要。

## 调用方式
- 技能名：`skill_drug_info_query`
- 适用领域：`medical`
- Python 实现位置：`development/skills/medical_skills.py`
- 依赖服务：`development/services/drug_service.py`

## 输入示例
```json
{
  "query": "布洛芬有哪些副作用",
  "domain": "medical",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_drug_info_query",
  "domain": "medical",
  "content": "药品查询：布洛芬\n品牌名：Ibuprofen Dye Free\n通用名：IBUPROFEN"
}
```

## 依赖关系
- 依赖 `DrugService.extract_drug_name()` 抽取药名。
- 依赖 `DrugService.lookup()` 获取 openFDA 公开药品标签结果。
- 输出结果会被 `AgentService` 汇总进最终提示词。

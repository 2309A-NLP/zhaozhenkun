# skill_route_planning

## 功能描述
- 提供文旅场景下的真实地图路线规划能力。
- 支持从自然语言中抽取起点、终点和出行方式。
- 当前接入 Nominatim 地理编码与 OSRM 公网路线规划接口。

## 调用方式
- 技能名：`skill_route_planning`
- 适用领域：`tourism`
- Python 实现位置：`development/skills/tourism_skills.py`
- 依赖服务：`development/services/route_service.py`

## 输入示例
```json
{
  "query": "请帮我从北京站到故宫怎么走",
  "domain": "tourism",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_route_planning",
  "domain": "tourism",
  "content": "路线规划：北京站 → 故宫\n出行方式：驾车，全程约 4.0 公里，预计 6 分钟。"
}
```

## 依赖关系
- 依赖 `RouteService.extract_route_points()` 抽取起终点。
- 依赖 `RouteService.plan_route()` 获取真实导航摘要。
- 输出结果会被 `AgentService` 汇总进最终提示词。

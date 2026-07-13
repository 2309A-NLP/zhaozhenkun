# skill_weather_check

## 功能描述
- 提供文旅场景下的实时天气查询能力。
- 自动从用户问题中抽取地点，并返回未来 3 天天气摘要。
- 当前接入 Open-Meteo 地理编码与天气预报公开接口。

## 调用方式
- 技能名：`skill_weather_check`
- 适用领域：`tourism`
- Python 实现位置：`development/skills/tourism_skills.py`
- 依赖服务：`development/services/weather_service.py`

## 输入示例
```json
{
  "query": "帮我查一下北京天气",
  "domain": "tourism",
  "history": []
}
```

## 输出示例
```json
{
  "name": "skill_weather_check",
  "domain": "tourism",
  "content": "地点：北京，中国\n2026-07-13：小毛毛雨，25.3°C~32.9°C，降水概率 16%"
}
```

## 依赖关系
- 依赖 `WeatherService.extract_location()` 抽取地点。
- 依赖 `WeatherService.get_forecast()` 获取真实天气结果。
- 输出结果会被 `AgentService` 汇总进最终提示词。

# 文旅智能体（文旅创新智脑）- Agent工单16

> 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
> 
> 当前状态：已整理为干净的五分类交付结构

一、根目录结构

```text
Agent工单16/
├─ 设计/
├─ 研发/
├─ 测试/
├─ 优化/
├─ 部署/
└─ README.md
```

二、目录说明

1. 设计
   - 文旅智能体需求分析与软件架构设计.md
   - 产品原型说明.md

2. 研发
   - 1.py
   - prototype/index.html
   - llm_analysis_deepseek_tech_selection.json
   - llm_analysis_qwen_scenario_analysis.json

3. 测试
   - 验收清单.md

4. 优化
   - 项目调整说明.md

5. 部署
   - config/kimi_config.json
   - README-运行说明.md

三、Kimi配置

- base_url: https://api.moonshot.cn/v1
- 配置文件：部署/config/kimi_config.json

四、查看顺序

1. 设计/文旅智能体需求分析与软件架构设计.md
2. 设计/产品原型说明.md
3. 研发/prototype/index.html
4. 测试/验收清单.md
5. 优化/项目调整说明.md
6. 部署/README-运行说明.md

五、运行入口

```bash
python 研发/1.py
```

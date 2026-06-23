# 文档质量评估系统

## 项目简介

文档质量评估系统是一个基于Python的智能文档质量评估工具，用于对知识库文档进行全面的质量检测和分析。该系统实现了文档格式分布统计、PDF页面类型识别、文档长度分布分析、重复文件检测、敏感信息检测等功能，并提供了RESTful API接口，可集成到RAGFlow等智能体工作流中。

## 功能特性

### 1. 格式分布统计
- 遍历指定目录，统计各类文档格式（.pdf, .docx, .md, .txt等）的数量和占比
- 支持自定义支持的文件格式列表
- 输出格式分布统计报告

### 2. PDF页面类型识别
- 判断PDF文件是文字型、扫描型还是混合型
- 基于页面字符数阈值进行智能分类
- 所有阈值可配置，输出待确认列表

### 3. 文档长度分布统计
- 统计所有文档的字符数
- 计算分位数（P25/P50/P75/P90/P99）
- 输出长度区间分布

### 4. 重复文件检测
- **MD5精确检测**：识别完全相同的文件
- **SimHash相似度检测**：识别高相似度的文档（进阶功能）
- 输出待确认的版本冲突列表

### 5. 敏感信息检测
- 支持手机号、邮箱、身份证、银行卡等敏感信息检测
- 使用正则表达式进行模式匹配
- 输出待审核列表，包含上下文信息

### 6. 文档分类标签
- 基于内容分析自动分配文档类型标签
- 支持多种内容类型：技术文档、用户手册、API文档等
- 质量等级评估：高质量、中等质量、低质量

## 系统架构

```
document_quality_assessment/
├── core/                    # 核心功能模块
│   ├── base.py             # 基础类和工具
│   ├── format_distribution.py  # 格式分布统计
│   ├── pdf_classifier.py   # PDF分类器
│   ├── length_distribution.py  # 长度分布分析
│   ├── duplicate_detection.py  # 重复检测
│   ├── sensitive_detection.py  # 敏感信息检测
│   ├── document_classifier.py  # 文档分类器
│   └── assessor.py         # 主评估器
├── api/                    # API接口模块
│   └── api.py             # Flask API实现
├── config/                 # 配置文件
│   └── assessment_config.yaml  # 评估配置
├── tests/                  # 测试脚本
│   └── test_assessment.py # 功能测试
├── main.py                # 主程序入口
├── requirements.txt       # 依赖列表
└── README.md             # 项目说明
```

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- PyYAML: 配置文件处理
- numpy: 数值计算
- flask: Web API框架
- pdfplumber: PDF处理
- python-docx: Word文档处理
- simhash: 相似度检测
- tqdm: 进度条显示

## 使用方法

### 1. 命令行使用

#### 评估文件夹
```bash
python main.py assess /path/to/documents -o ./reports -s
```

#### 评估单个文件
```bash
python main.py assess /path/to/document.pdf -o ./reports
```

#### 启动API服务
```bash
python main.py api --host 0.0.0.0 --port 5000 --debug
```

### 2. Python API使用

```python
from document_quality_assessment import DocumentQualityAssessor

# 创建评估器
assessor = DocumentQualityAssessor('config/assessment_config.yaml')

# 评估目录
result = assessor.assess_directory('/path/to/documents')

# 生成报告
report_files = assessor.generate_report(result, './reports')

# 打印摘要
for section, content in result['summary'].items():
    print(f"{section}:")
    print(content)
```

### 3. RESTful API使用

#### 健康检查
```bash
curl http://localhost:5000/v1/document/quality-inspection/health
```

#### 评估文件夹
```bash
curl -X POST http://localhost:5000/v1/document/quality-inspection \
  -H "Content-Type: application/json" \
  -d '{
    "folder_path": "/path/to/documents",
    "output_formats": ["json", "html"]
  }'
```

#### 上传文件评估
```bash
curl -X POST http://localhost:5000/v1/document/quality-inspection/upload \
  -F "files=@document1.pdf" \
  -F "files=@document2.docx" \
  -F 'config={"output_formats": ["json"]}'
```

#### 下载报告
```bash
curl -O http://localhost:5000/v1/document/quality-inspection/report/assessment_report_20240101_120000.json
```

## 配置说明

配置文件位于 `config/assessment_config.yaml`，包含以下主要配置：

### 基本配置
- `supported_formats`: 支持的文件格式列表
- `max_file_size_mb`: 最大文件大小限制
- `max_workers`: 并发处理数

### PDF分类配置
- `scan_page_char_threshold`: 扫描页字符数阈值
- `scan_pdf_ratio_threshold`: 扫描型PDF比例阈值
- `mixed_pdf_ratio_min/max`: 混合型PDF比例区间

### 重复检测配置
- `enable_md5`: 启用MD5检测
- `enable_simhash`: 启用SimHash检测
- `simhash_similarity_threshold`: SimHash相似度阈值

### 敏感信息检测配置
- `enable_detection`: 启用敏感信息检测
- `detection_types`: 各类型检测配置
- `context_chars`: 上下文字符数

## 输出报告

系统支持生成两种格式的报告：

### JSON报告
- 完整的评估结果数据
- 包含所有统计信息和详细数据
- 便于程序处理和数据分析

### HTML报告
- 可视化的评估报告
- 包含图表和摘要信息
- 便于人工查看和分享

## 测试

运行测试脚本：
```bash
cd document_quality_assessment
python tests/test_assessment.py
```

## 集成到RAGFlow

### 1. 注册Skill
将文档质量评估Skill注册到RAGFlow的技能库中。

### 2. 创建工作流
创建 `document_ingestion_workflow` 工作流，包含以下节点：
- 触发质检节点
- 调用DocumentQualityAssessmentSkill节点
- 根据分类标签路由到不同解析器

### 3. 暴露API端点
在RAGFlow的API服务中新增端点：
```
POST /v1/document/quality-inspection
```

## 验收标准

### 功能验收
- ✅ 五大功能全覆盖：格式统计、PDF分类、长度分析、重复检测、敏感信息检测
- ✅ 分类准确性：自动分配的文档分类标签准确率≥85%
- ✅ 列表可操作性：待确认和待审核列表包含足够判断信息

### 集成验收
- ✅ Skill能通过API端点被成功调用
- ✅ 返回结构化的JSON报告
- ✅ Skill可被智能体工作流中的决策节点调用

### 代码质量验收
- ✅ 代码结构清晰，符合项目规范
- ✅ 所有核心判断逻辑的阈值配置化
- ✅ 良好的错误处理机制

## 注意事项

1. **SimHash检测**：此为进阶功能，可能误报率较高，默认关闭
2. **性能考虑**：处理大量文档时可能耗时较长，建议启用进度反馈
3. **内存使用**：处理大文件时注意内存使用，可配置文件大小限制
4. **编码问题**：处理中文文档时注意编码设置

## 许可证

本项目由八维文化与产业研究院开发，用于RAG项目文档质量评估。

## 联系方式

如有问题或建议，请联系项目维护人员。
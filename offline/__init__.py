"""
离线处理模块包。

该包包含ADSD项目离线数据处理相关的所有模块，主要包括：
- runner: 离线任务统一入口，调度各子模块运行
- pdf_to_milvus: PDF清洗、表格提取、知识JSON生成及Milvus向量入库
- specialized_data_processor: 多种特殊格式数据（eval.jsonl、r1、SoulChat）的统一处理器
- vector_index_creator: 向量索引创建器，使用BGE-M3模型将数据向量化并存储到Milvus和Redis
- check_port: 检查RAG系统所需的基础服务（Milvus、Redis、MySQL）是否正常运行
- analyze_processed_data: 分析处理后的数据质量，生成质量报告
"""

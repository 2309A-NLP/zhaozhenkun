"""
研发模块（development package）

本模块是多用户聊天AI系统的核心研发实现包，包含以下核心组件：
- runner: 离线任务统一调度入口，通过runpy动态运行各子模块脚本
- short_term_memory: 短期记忆管理器，维护对话的上下文记忆
- milvus_manager: Milvus向量数据库管理器，负责向量检索和集合管理
- online_main: 在线服务主入口，提供Flask API接口

包含系统的核心业务逻辑，涵盖在线推理和离线处理两大功能域。
"""
# development package — 核心研发实现  # 模块标识注释，说明这是一个核心研发实现的包

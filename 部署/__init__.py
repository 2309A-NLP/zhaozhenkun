"""
部署模块（deployment package）

本模块是多用户聊天AI系统的部署脚本包，负责：
- Docker容器编排和部署配置
- docker-compose服务编排文件管理
- 服务启动、停止和健康检查脚本
- 环境变量和依赖配置管理

用于将系统各组件（Milvus、Redis、MySQL、Flask应用等）部署到生产环境。
"""
# deployment package — 部署脚本  # 模块标识注释，说明这是一个部署脚本相关的包

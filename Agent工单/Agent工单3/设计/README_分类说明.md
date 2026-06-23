# Agent工单3 - 文生图智能体项目

## 项目概述

基于 Stable Diffusion + ControlNet 实现的人脸文生图智能体，支持面部旋转生成和图像扩图功能。

## 项目结构

```
Agent工单3/
├── 部署/                    # 部署相关配置文件
│   └── config.py           # 项目配置模块
├── 测试/                    # 测试文件（待补充）
├── 设计/                    # 设计文档（待补充）
├── 研发/                    # 核心研发代码
│   ├── app.py              # Gradio Web界面主入口
│   ├── embedding_service.py # BGE-M3文本向量化服务
│   ├── face_processor.py   # 人脸检测与处理模块
│   ├── image_generator.py  # SD+ControlNet图像生成模块
│   ├── main.py             # 命令行主入口
│   ├── outpainter.py       # 图像扩图模块
│   └── utils.py            # 通用工具函数模块
├── 优化/                    # 性能优化模块
│   ├── cache_manager.py    # Redis缓存管理模块
│   └── vector_store.py     # Milvus向量存储与检索模块
├── input/                   # 输入文件目录
├── output/                  # 输出文件目录
├── models/                  # 模型文件目录
└── README.md               # 项目说明文档
```

## 文件分类说明

### 部署 (1个文件)
- **config.py**: 项目配置模块，定义所有模型路径、数据库连接、生成参数等配置

### 测试 (待补充)
- 未来可添加单元测试、集成测试等文件

### 设计 (待补充)
- 未来可添加架构设计文档、API设计文档等

### 研发 (7个文件)
- **app.py**: Gradio Web界面主入口，提供面部旋转和扩图的可视化操作界面
- **embedding_service.py**: BGE-M3文本向量化服务，将提示词编码为1024维向量用于语义检索
- **face_processor.py**: 人脸检测与处理模块，实现人脸检测、关键点提取、姿态估计、深度图生成
- **image_generator.py**: SD+ControlNet面部旋转图像生成模块，集成Redis缓存和Milvus语义检索
- **main.py**: 命令行主入口，执行完整处理流程
- **outpainter.py**: 图像扩图模块，支持创建扩图画布/遮罩并执行扩图推理
- **utils.py**: 通用工具函数模块，提供图像加载/保存/缩放、对比网格拼接等功能

### 优化 (2个文件)
- **cache_manager.py**: Redis缓存管理模块，支持精确查询和统计
- **vector_store.py**: Milvus向量数据库操作模块，管理提示词向量的集合创建、插入和语义检索

## 代码注释说明

所有Python文件已添加：
1. **文件头功能说明注释块**: 包含文件名、功能描述、分类、主要类和函数清单
2. **逐行中文注释**: 每一行代码都有简洁明了的中文注释，解释代码作用

## 快速开始

### 1. 环境准备
```bash
pip install -r requirements.txt
```

### 2. 命令行运行
```bash
python 研发/main.py --input input/your_face.jpg
```

### 3. Web界面运行
```bash
python 研发/app.py
```

## 依赖服务

- **Milvus**: 向量数据库，端口19530
- **Redis**: 缓存数据库，端口6379
- **BGE-M3**: 文本向量化模型

## 注意事项

1. 首次运行需要下载AI模型，请确保网络连接正常
2. 国内用户建议使用本地模型路径，避免从HuggingFace在线下载
3. 所有配置项在 `部署/config.py` 中定义，可根据环境修改

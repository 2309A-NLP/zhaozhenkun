# 文生图智能体

## 项目概述

基于 Stable Diffusion + ControlNet 实现的人脸文生图智能体，支持：

- 输入 1 张人脸图，生成 `左转(-30°)`、`右转(+30°)`、`端正(0°)` 3 张结果图
- 对生成结果继续执行扩图（outpainting）
- 保留 `BGE-M3 + Milvus + Redis` 作为语义检索与缓存增强能力
- 提供命令行入口和 Gradio Web 演示入口

本项目对应工单：`人工智能NLP-Agent数字人项目-文生图智能体任务`

## 当前已定位的问题

### 1. 人脸检测和模型生成已拆开

现在点击 `检测人脸` 时：
- 只加载 `MediaPipe`
- 不再提前加载 `Stable Diffusion / ControlNet / Inpainting`
- 不会因为外网拉模型超时，导致“检测人脸”也跟着失败

### 2. 你现在的新报错根因

你当前生成时报错：
- `lllyasviel/control_v11f1p_sd15_depth does not appear to have a file named config.json`

这不是真缺 `config.json`，本质是：
- 代码正尝试从 `huggingface.co` 在线下载 `ControlNet` 模型
- 你的网络连不上或超时
- 本地缓存里也没有这个模型
- 所以最终报成 `config.json` 找不到

## 现在怎么处理

### 方案一：先验证检测链路

重新运行后，先只点：
- `检测人脸`

如果这一步能成功，说明：
- `MediaPipe` 已正常
- 前端流程已拆开
- 现在剩下的就是扩散模型没准备好

### 方案二：准备本地 SD / ControlNet 模型

你这个环境在国内，别走 HuggingFace 在线拉取。
最好改成“模型全部本地路径”。

当前代码默认会联网拉：
- `stabilityai/stable-diffusion-2-1`
- `lllyasviel/control_v11f1p_sd15_depth`
- `stabilityai/stable-diffusion-2-inpainting`

如果你本地还没这几个模型，点击生成/扩图就一定继续报错。

## 已知依赖修复命令

### mediapipe
```bash
C:\Users\31326\anaconda3\envs\llamafactory\python.exe -m pip install mediapipe==0.10.14
```

### diffusers / peft
```bash
C:\Users\31326\anaconda3\envs\llamafactory\python.exe -m pip install peft==0.17.0
```

如果还不行：
```bash
C:\Users\31326\anaconda3\envs\llamafactory\python.exe -m pip install diffusers==0.35.1 peft==0.17.0 transformers==4.51.3 accelerate==1.8.1
```

## 功能说明

### 1. 核心功能
- 面部旋转生成：输入原图后生成左转、右转、端正三张结果图
- 图像扩图：对图像四周自然补全，输出更大尺寸图像

### 2. 增强能力
- Redis：缓存相同输入图像 + 相同参数下的生成结果，减少重复推理
- BGE-M3：对提示词进行向量化编码
- Milvus：保存提示词向量，支持相似提示语义检索与状态展示

注意：
- `BGE-M3 / Milvus / Redis` 是增强组件，不会替代核心文生图流程
- 缓存已改为“提示词 + 输入图像哈希 + 参数”联合键，避免不同人脸误命中
- 项目现在已经增加依赖检查，缺包或版本冲突时会给明确提示，不会再一层层炸

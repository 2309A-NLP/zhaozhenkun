# -*- coding: utf-8 -*-
"""
配置文件 — 集中管理微调数据路径、模型参数、LoRA配置和评估参数。

功能说明：
- BGE-M3嵌入模型路径和MiMo API密钥（用于评估和基线与微调模型对比）
- IMDR数据文件路径和输出目录
- Ollama Qwen2.5-VL:3b配置（用于VLM图片识别评估）
- 原始PDF文档目录（用于提取专利图纸图片）
- LoRA微调核心参数（秩、缩放因子、目标模块、学习率等）
- 专业评估指标参数（术语词典、评估集切分）
"""
import logging  # 导入logging模块

logger = logging.getLogger(__name__)  # 获取当前模块的logger

import os  # 导入os模块，用于环境变量和路径操作
from pathlib import Path  # 导入Path类，用于跨平台路径操作

# ==================== 项目路径 ====================
# 项目根目录（config.py 在 设计/ 下，向上1级为项目根）
BASE_DIR = Path(__file__).resolve().parent.parent  # rag工单16/

# ==================== Ollama VLM（Qwen2.5-VL:3b）= ====================
# 用户指定的图片识别模型（Ollama部署）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_VLM_MODEL = os.getenv("OLLAMA_VLM_MODEL", "qwen2.5vl:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))  # 图片推理需5分钟+

# ==================== 原始PDF文档目录 ====================
# IMDR专利PDF存放位置（1700份工业专利）
# 从工单14-17附件中复制出来
PDF_DIR = os.getenv("PDF_DIR", str(BASE_DIR / "部署" / "patents"))
# 图片提取缓存目录（PDF页面转图片后存放）
IMAGES_DIR = str(BASE_DIR / "优化" / "images")

# ==================== BGE-M3 嵌入模型 ====================
# BGE-M3模型路径（WSL下自动转换路径）
BGE_M3_PATH = os.getenv("BGE_M3_PATH", r"C:\Users\31326\Desktop\bge-m3")
if os.name == "posix" and BGE_M3_PATH.startswith("C:"):
    BGE_M3_PATH = BGE_M3_PATH.replace("C:", "/mnt/c").replace("\\", "/")

# ==================== MiMo API（用于评估） ====================
# 使用MiMo API作为基线VLM进行对比评估
# API Key 通过环境变量配置: export MIMO_API_KEY="your-key"
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_MODEL = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")
MIMO_EVAL_MODEL = os.getenv("MIMO_EVAL_MODEL", "mimo-v2-omni")
MIMO_TIMEOUT = int(os.getenv("MIMO_TIMEOUT", "45"))

# ==================== 数据路径 ====================
# IMDR原始问答数据（10096条工业专利QA）
QUESTIONS_FILE = str(BASE_DIR / "测试" / "questions.jsonl")
# 输出目录（存放转换后的微调数据和评估报告）
OUTPUT_DIR = str(BASE_DIR / "优化" / "output")
# 微调JSONL输出路径
FINETUNE_DATA = str(Path(OUTPUT_DIR) / "vlm_finetune_data.jsonl")
# 评估集输出路径
EVAL_DATA = str(Path(OUTPUT_DIR) / "eval_set.json")

# ==================== LoRA微调参数 ====================
# 基础模型名称（使用Qwen2.5-VL-3B或类似VLM）
# 可从 ModelScope 下载: https://modelscope.cn/models/Qwen/Qwen2.5-VL-3B-Instruct
BASE_MODEL = os.getenv("BASE_MODEL", "/home/zzy/LLaMA-Factory/models/Qwen2.5-VL-3B-Instruct")
# 如果下载到本地，改为本地路径，如：
# BASE_MODEL = r"D:\\models\\Qwen2.5-VL-3B-Instruct"
# LoRA秩（低秩矩阵的维度，越大表示可学习参数越多）
LORA_RANK = 4
# LoRA缩放因子（alpha / rank 的比值控制更新幅度）
LORA_ALPHA = 8
# LoRA Dropout（防止过拟合）
LORA_DROPOUT = 0.1
# 目标模块列表（Transformer中应用LoRA的线性层）
TARGET_MODULES = ["q_proj", "v_proj"]  # 减少目标模块，降低显存

# ==================== 训练参数 ====================
# 训练轮数
NUM_EPOCHS = 1
# 批次大小（每GPU，RTX 5060 8GB 显存建议 =1）
BATCH_SIZE = 1
# 梯度累积步数（扩大有效批次大小，有效batch= BATCH_SIZE × GRADIENT_ACCUMULATION）
GRADIENT_ACCUMULATION = 4
# 学习率
LEARNING_RATE = 2e-4
# 学习率调度器
LR_SCHEDULER = "cosine"
# 预热步数
WARMUP_RATIO = 0.03
# 最大序列长度（文本分词后）
MAX_SEQ_LEN = 1024
# 日志和保存步数
LOGGING_STEPS = 10
SAVE_STEPS = 100
EVAL_STEPS = 100

# ==================== 评估指标 ====================
# BLEU / ROUGE 权重
BLEU_WEIGHT = 0.3
ROUGE_WEIGHT = 0.3
TERM_ACC_WEIGHT = 0.2  # 术语准确率权重
DRAWING_ACC_WEIGHT = 0.2  # 图纸推理准确率权重

# ==================== 工业专业术语词典 ====================
# 用于评估模型对工业术语的理解能力
INDUSTRY_TERMS = [
    "淬火", "回火", "正火", "退火", "渗碳", "调质",  # 热处理
    "公差配合", "间隙配合", "过盈配合", "过渡配合",  # 机械配合
    "同轴度", "平行度", "垂直度", "圆跳动", "全跳动",  # 形位公差
    "疲劳强度", "屈服强度", "抗拉强度", "硬度",  # 材料性能
    "轴承", "齿轮", "链轮", "链条", "螺杆", "弹簧",  # 机械零件
    "液压缸", "活塞", "密封圈", "阀门", "法兰",  # 液压气动
    "熔渣", "淬冷", "矿渣", "炉渣", "钢渣",  # 冶金
    "静电除尘", "布袋除尘", "旋风分离", "沉降",  # 环保
    "散料", "块状散料", "粉料", "粒料", "物料分配",  # 物料处理
    "管线", "管道", "反应器", "釜式", "塔器",  # 化工容器
]

# ==================== 专业术语评估集 ====================
# 从数据集中筛选出的专业术语相关问题索引
TERM_EVAL_INDICES = list(range(0, min(50, 10096)))  # 默认使用前50条

# ==================== 图纸推理评估集 ====================
# 从数据集中筛选出的图纸推理问题索引（Group 2和Group 3）
DRAWING_EVAL_INDICES = list(range(50, min(150, 10096)))  # 默认使用50-149条

"""
config.py - RAG工单8 GraphRAG配置模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 管理CCF年报路径、DeepSeek API、BGE-M3模型、
      Milvus向量库参数、分块检索参数、评估参数等
说明: 所有路径自动适配Windows/WSL双平台，
      config.py是全局配置中心，所有模块从这里读取参数
"""

import os, sys
from pathlib import Path

# ===== 项目根目录（自动适配Windows/WSL双平台） =====
# Windows上用USERPROFILE环境变量定位桌面
# WSL上直接使用/mnt/c/映射路径
PROJECT_DIR = Path(__file__).parent.resolve()
if sys.platform == "win32":
    DESKTOP_DIR = Path(os.environ["USERPROFILE"]) / "Desktop"
else:
    DESKTOP_DIR = Path("/mnt/c/Users/31326/Desktop")

# ===== CCF竞赛PDF路径（金融研报数据源） =====
# 数据来源：CCF竞赛金融年报数据集
# 包含平安银行、招商银行、中国人寿等多份年报
# 主路径：工单/RAG工单/附件/ccf_competition/pdf/
# 备用路径：桌面/ccf_competition/pdf/
CCF_PDF_DIR = DESKTOP_DIR / "工单" / "RAG 工单" / "附件" / "ccf_competition" / "pdf"
CCF_PDF_DIR_SIMPLE = DESKTOP_DIR / "ccf_competition" / "pdf"

# ===== 测试问题PDF路径 =====
# 包含5个金融问答测试用例及其参考答案
SAMPLE_QUESTIONS_PDF = DESKTOP_DIR / "工单" / "RAG 工单" / "附件" / "sample_questions.pdf"
SAMPLE_QUESTIONS_FALLBACK = PROJECT_DIR / "sample_questions.pdf"

# ===== 输出目录（存放所有中间结果和报告） =====
# 包括：chunks.json, knowledge_graph.json, qa_results.json,
#       evaluation_summary.json, evaluation_report.html等
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 小米MiMo API (默认) =====
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-czex5np7bgf6duyuyvqntmw44xcunseatmblffiw9lk9w0jy")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5-pro"     # 推理模型，用于问答生成
MIMO_ENTITY_MODEL = "mimo-v2-omni"  # 实体提取用（非推理模型，结构化输出更稳定）
EVAL_MODEL = "mimo-v2-omni"      # 评估用（非推理，有content输出）

# ===== DeepSeek API (备选) =====
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ===== 默认LLM提供商 =====
LLM_PROVIDER = "mimo"

# ===== BGE-M3向量模型配置（本地路径） =====
# 模型路径：桌面/bge-m3/目录
# 使用FP16半精度推理适配RTX5060 8GB显存
# batch_size=2避免OOM，max_length=1024控制显存占用
BGE_M3_PATH = str(DESKTOP_DIR / "bge-m3")
BGE_M3_BATCH = 2          # RTX5060 8GB显存安全配置
BGE_M3_MAX_LEN = 1024     # 最大序列长度（避免显存溢出）
BGE_M3_DEVICE = "cuda"    # GPU加速推理
BGE_M3_FP16 = True        # 半精度模式（model.half()）

# ===== Milvus向量库参数 =====
# 本地Milvus服务，默认端口19530
# 集合名rag_work_order_8独立于其他工单
# 向量维度1024对应BGE-M3密集向量输出
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
MILVUS_COLL = "rag_work_order_8"   # 集合名称
MILVUS_DIM = 1024                   # 向量维度

# ===== 文本分块参数 =====
# CHUNK_SIZE: 每块的字符数上限
# CHUNK_OVERLAP: 相邻块的重叠字符数（保持上下文连续性）
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50

# ===== 检索参数 =====
TOP_K = 10                # 向量检索返回Top-K结果
GRAPH_EXPAND_K = 5        # 图谱扩展的最大关联节点数
FINAL_TOP_K = 8           # 最终融合排序后保留的chunk数

# ===== 实体类型定义（GraphRAG用） =====
ENTITY_TYPES = ["公司", "人物", "产品", "指标"]

# ===== 评估参数 =====
EVAL_LLM_MODEL = "mimo-v2-omni"   # 评估用模型
EVAL_TIMEOUT = 30                  # LLM评估超时(秒)，MiMo API响应较慢

# ===== 日志配置 =====
LOG_FMT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
WO_ID = "人工智能NLP-RAG-基于Graph RAG 实现金融问答"

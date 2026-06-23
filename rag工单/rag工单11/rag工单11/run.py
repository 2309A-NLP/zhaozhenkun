"""
run.py — Embedding模型微调 项目入口（放在rag工单11根目录，PyCharm直接运行本文件即可）
功能：自动加载所有子目录，调用部署/run_all.py 的完整流水线
用法：python run.py                 → 完整流水线
      python run.py --step 1        → 仅数据准备
      python run.py --step 2        → 仅基线评估
      python run.py --step 3        → 仅LoRA微调
      python run.py --step 4        → 仅微调后评估
      python run.py --step 5        → 仅对比报告
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""
import sys
import logging
from pathlib import Path

# 先加路径，再导入config
ROOT = Path(__file__).parent.resolve()
for sub in ["设计", "研发", "测试", "优化", "部署"]:
    p = ROOT / sub
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)
# 路径已在文件头部完成桥接

# 导入并执行总入口模块
if __name__ == "__main__":
    from run_all import run_all                 # 部署/run_all.py 的主函数
    run_all()                                   # 执行完整流水线

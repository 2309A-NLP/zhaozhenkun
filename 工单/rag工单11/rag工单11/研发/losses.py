"""
损失函数模块 - Embedding模型微调的所有损失函数
包含 Triplet Loss / Contrastive Loss / CosineSimilarity Loss 三种，
通过 get_loss_function() 根据配置自动选择。
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""

import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
from config import TRAIN_CONFIG

logger = logging.getLogger(__name__)


def mean_pooling(token_embeddings: torch.Tensor,
                 attention_mask: torch.Tensor) -> torch.Tensor:
    """
    均值池化：对token级别的hidden states按attention mask做加权平均。
    BGE-M3使用均值池化聚合所有token的表示。
    """
    mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    sum_emb = torch.sum(token_embeddings * mask, dim=1)
    sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
    return sum_emb / sum_mask


def compute_embeddings(model: nn.Module,
                       input_ids: torch.Tensor,
                       attention_mask: torch.Tensor) -> torch.Tensor:
    """
    用模型计算文本嵌入向量，返回L2归一化后的嵌入。
    """
    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    embeddings = mean_pooling(outputs.last_hidden_state, attention_mask)
    return F.normalize(embeddings, p=2, dim=1)


def triplet_loss(anchor: torch.Tensor, positive: torch.Tensor,
                 negative: torch.Tensor, margin: float = 0.3) -> torch.Tensor:
    """
    三元组损失 Triplet Loss.
    Loss = max(0, d(a,p) - d(a,n) + margin)
    拉近 anchor-positive 距离，推远 anchor-negative 距离。
    """
    pos_dist = 1 - (anchor * positive).sum(dim=1)
    neg_dist = 1 - (anchor * negative).sum(dim=1)
    return F.relu(pos_dist - neg_dist + margin).mean()


def contrastive_loss(anchor: torch.Tensor, positive: torch.Tensor,
                     negative: torch.Tensor, margin: float = 0.5) -> torch.Tensor:
    """
    对比损失 Contrastive Loss.
    正例对距离<margin，负例对距离>margin。
    """
    pos_dist = 1 - (anchor * positive).sum(dim=1)
    neg_dist = 1 - (anchor * negative).sum(dim=1)
    pos_loss = pos_dist ** 2
    neg_loss = torch.clamp(margin - neg_dist, min=0) ** 2
    return (pos_loss + neg_loss).mean()


def cosine_similarity_loss(anchor: torch.Tensor, positive: torch.Tensor,
                           negative: torch.Tensor,
                           target_sim: float = 0.8) -> torch.Tensor:
    """
    余弦相似度损失 Cosine Similarity Loss.
    引导正例对相似度逼近 target_sim，负例对逼近 -target_sim。
    (此函数在旧版trainer.py中被引用但从未定义，现已修复)
    """
    pos_sim = (anchor * positive).sum(dim=1)
    neg_sim = (anchor * negative).sum(dim=1)
    pos_loss = F.mse_loss(pos_sim, torch.full_like(pos_sim, target_sim))
    neg_loss = F.mse_loss(neg_sim, torch.full_like(neg_sim, -target_sim))
    return (pos_loss + neg_loss) / 2


def matryoshka_loss(anchor: torch.Tensor, positive: torch.Tensor,
                    negative: torch.Tensor,
                    dimensions: list = None,
                    margin: float = 0.3) -> torch.Tensor:
    """
    套娃损失 Matryoshka Loss.
    在多个维度子集上分别计算Triplet Loss再求和，
    确保嵌入向量具备分层可截断特性（前N维也能用）。
    """
    if dimensions is None:
        dimensions = [128, 256, 512, anchor.size(1)]
    total = torch.tensor(0.0, device=anchor.device)
    for dim in dimensions:
        if dim > anchor.size(1):
            continue
        a, p, n = anchor[:, :dim], positive[:, :dim], negative[:, :dim]
        # 对子向量重新归一化
        a = F.normalize(a, p=2, dim=1)
        p = F.normalize(p, p=2, dim=1)
        n = F.normalize(n, p=2, dim=1)
        total = total + triplet_loss(a, p, n, margin=margin)
    return total / len(dimensions)


# 缓存避免重复解析配置
_loss_fn_cache = {}


def get_loss_function():
    """
    根据 TRAIN_CONFIG 配置返回对应的损失函数。
    支持: triplet (默认), contrastive, cosine_sim
    Returns:
        损失函数，签名: f(anchor, positive, negative) -> loss
    """
    loss_type = TRAIN_CONFIG.get("loss_type", "triplet")
    if loss_type in _loss_fn_cache:
        return _loss_fn_cache[loss_type]

    if loss_type == "contrastive":
        margin = TRAIN_CONFIG.get("contrastive_margin", 0.5)
        fn = lambda a, p, n: contrastive_loss(a, p, n, margin=margin)
    elif loss_type == "cosine_sim":
        target = TRAIN_CONFIG.get("cosine_target", 0.8)
        fn = lambda a, p, n: cosine_similarity_loss(a, p, n, target_sim=target)
    elif loss_type == "matryoshka":
        margin = TRAIN_CONFIG.get("triplet_margin", 0.3)
        fn = lambda a, p, n: matryoshka_loss(a, p, n, margin=margin)
    else:
        margin = TRAIN_CONFIG.get("triplet_margin", 0.3)
        fn = lambda a, p, n: triplet_loss(a, p, n, margin=margin)

    _loss_fn_cache[loss_type] = fn
    return fn

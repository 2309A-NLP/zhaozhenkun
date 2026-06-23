"""
模型微调模块 - LoRA 训练 BGE-M3 嵌入模型
PEFT/LoRA在领域数据上微调，8GB显存下batch=2+梯度累积+FP16。
损失函数从 losses.py 导入(triplet/contrastive/cosine_sim)。
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""

import logging
import json, time
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoModel, AutoTokenizer
from peft import LoraConfig, get_peft_model
from config import get_model_path, LORA_CONFIG, TRAIN_CONFIG, MODEL_DIR, ensure_dirs
from losses import compute_embeddings, get_loss_function

logger = logging.getLogger(__name__)
logger.info("EmbeddingFineTuner 初始化")


class TripletDataset(Dataset):
    """三元组数据集: (anchor, positive, negative)编码为token IDs"""
    def __init__(self, triplets, tokenizer, max_len):
        self.triplets, self.tokenizer, self.max_len = triplets, tokenizer, max_len
    def __len__(self):
        return len(self.triplets)
    def __getitem__(self, idx):
        t = self.triplets[idx]
        return (self._enc(t["anchor"]), self._enc(t["positive"]), self._enc(t["negative"]))
    def _enc(self, text):
        e = self.tokenizer(text, max_length=self.max_len, padding="max_length",
                           truncation=True, return_tensors="pt")
        return {k: v.squeeze(0) for k, v in e.items()}


def collate_triplets(batch):
    """将三元组列表整理为模型输入格式"""
    r = {}
    for i, k in enumerate(["anchor", "positive", "negative"]):
        r[k] = {"input_ids": torch.stack([b[i]["input_ids"] for b in batch]),
                "attention_mask": torch.stack([b[i]["attention_mask"] for b in batch])}
    return r


def get_device():
    """检测可用设备"""
    if torch.cuda.is_available():
        d = torch.device("cuda")
        print(f"  [设备] CUDA: {torch.cuda.get_device_name(0)} "
              f"({torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB)")
        return d
    return torch.device("cpu")


class EmbeddingFineTuner:
    """Embedding模型微调器：加载→LoRA→训练→保存"""

    def __init__(self):
        self.device = get_device()
        self.model = self.tokenizer = self.optimizer = None

    def load_model(self):
        """加载BGE-M3 + LoRA"""
        path = get_model_path()
        print(f"\n[加载模型] {path}")
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        base = AutoModel.from_pretrained(path,
            torch_dtype=torch.float16 if TRAIN_CONFIG["fp16"] else torch.float32,
            trust_remote_code=True)
        peft = LoraConfig(r=LORA_CONFIG["r"], lora_alpha=LORA_CONFIG["lora_alpha"],
            lora_dropout=LORA_CONFIG["lora_dropout"],
            target_modules=LORA_CONFIG["target_modules"],
            bias=LORA_CONFIG["bias"], task_type="FEATURE_EXTRACTION")
        self.model = get_peft_model(base, peft).to(self.device)
        self.model.train()
        tp = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        tt = sum(p.numel() for p in self.model.parameters())
        print(f"  [LoRA] 可训练: {tp:,}/{tt:,} = {tp/tt*100:.2f}%")

    def encode(self, texts, bs=8):
        """批量编码文本，返回归一化嵌入"""
        self.model.eval()
        embs = []
        for i in range(0, len(texts), bs):
            e = self.tokenizer(texts[i:i+bs], padding=True, truncation=True,
                max_length=TRAIN_CONFIG["max_seq_length"], return_tensors="pt").to(self.device)
            with torch.no_grad():
                embs.append(compute_embeddings(self.model, e["input_ids"], e["attention_mask"]).cpu())
        return torch.cat(embs)

    def _forward(self, batch):
        """将batch移到设备并前向计算损失"""
        a = compute_embeddings(self.model,
            batch["anchor"]["input_ids"].to(self.device),
            batch["anchor"]["attention_mask"].to(self.device))
        p = compute_embeddings(self.model,
            batch["positive"]["input_ids"].to(self.device),
            batch["positive"]["attention_mask"].to(self.device))
        n = compute_embeddings(self.model,
            batch["negative"]["input_ids"].to(self.device),
            batch["negative"]["attention_mask"].to(self.device))
        return get_loss_function()(a, p, n)

    def train(self, train_data, eval_data):
        """执行LoRA微调"""
        print(f"\n{'='*40}\n开始微调\n{'='*40}")
        print(f"  样本: 训练{len(train_data)} 评估{len(eval_data)}")
        train_loader = DataLoader(TripletDataset(train_data, self.tokenizer,
            TRAIN_CONFIG["max_seq_length"]), batch_size=TRAIN_CONFIG["batch_size"],
            shuffle=True, collate_fn=collate_triplets)
        eval_loader = DataLoader(TripletDataset(eval_data, self.tokenizer,
            TRAIN_CONFIG["max_seq_length"]), batch_size=TRAIN_CONFIG["batch_size"],
            collate_fn=collate_triplets)
        self.optimizer = torch.optim.AdamW(self.model.parameters(),
            lr=TRAIN_CONFIG["learning_rate"], weight_decay=TRAIN_CONFIG["weight_decay"])
        total_steps = len(train_loader) * TRAIN_CONFIG["epochs"]
        scaler = torch.cuda.amp.GradScaler() if (TRAIN_CONFIG["fp16"]
            and self.device.type == "cuda") else None
        best_loss = float("inf")
        gs, t0 = 0, time.time()

        for epoch in range(TRAIN_CONFIG["epochs"]):
            print(f"\n--- Epoch {epoch+1}/{TRAIN_CONFIG['epochs']} ---")
            self.model.train()
            el, steps = 0, 0
            for step, batch in enumerate(train_loader):
                if scaler:
                    with torch.cuda.amp.autocast():
                        loss = self._forward(batch)
                    scaler.scale(loss).backward()
                else:
                    loss = self._forward(batch)
                    loss.backward()
                el += loss.item(); steps += 1

                if (step + 1) % TRAIN_CONFIG["gradient_accumulation"] == 0:
                    if scaler:
                        scaler.unscale_(self.optimizer)
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), TRAIN_CONFIG["max_grad_norm"])
                        scaler.step(self.optimizer); scaler.update()
                    else:
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), TRAIN_CONFIG["max_grad_norm"])
                        self.optimizer.step()
                    self.optimizer.zero_grad(); gs += 1
                    if gs % TRAIN_CONFIG["logging_steps"] == 0:
                        print(f"  Step {gs}/{total_steps} | Loss: {loss.item():.4f} | LR: {self.optimizer.param_groups[0]['lr']:.2e}")
                    if gs % TRAIN_CONFIG["eval_steps"] == 0:
                        ev = self._evaluate(eval_loader)
                        if ev < best_loss: best_loss = ev; self._save_ckpt(gs)
            print(f"  Epoch {epoch+1} 完成 | 平均Loss: {el/max(steps,1):.4f}")
        print(f"\n[完成] 耗时: {time.time()-t0:.0f}秒 步数: {gs}")

    def _evaluate(self, loader):
        """评估集平均损失"""
        self.model.eval()
        total = cnt = 0
        with torch.no_grad():
            for batch in loader:
                total += self._forward(batch).item(); cnt += 1
        avg = total / max(cnt, 1)
        print(f"  [评估] 平均Loss: {avg:.4f}")
        self.model.train()
        return avg

    def _save_ckpt(self, step):
        """保存中间检查点"""
        p = MODEL_DIR / f"checkpoint-{step}"
        self.model.save_pretrained(p); self.tokenizer.save_pretrained(p)
        print(f"  [保存] 检查点 → {p}")

    def save_final_model(self):
        """保存最终模型"""
        ensure_dirs()
        f = MODEL_DIR / "final"
        self.model.save_pretrained(f); self.tokenizer.save_pretrained(f)
        with open(f / "train_config.json", "w") as j:
            json.dump({"base_model": str(get_model_path()), "lora_config": LORA_CONFIG,
                       "train_config": dict(TRAIN_CONFIG)}, j, ensure_ascii=False, indent=2)
        print(f"\n[保存] 最终模型 → {f}")
        return f


if __name__ == "__main__":
    tuner = EmbeddingFineTuner()
    tuner.load_model()
    e = tuner.encode(["测试文本", "嵌入模型微调"])
    print(f"嵌入向量形状: {e.shape}")

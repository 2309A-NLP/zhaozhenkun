"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
LLM 客户端 —— 千问多模态 + DeepSeek 文本推理
================================================================================
"""
import base64, time, httpx
from typing import Optional, List, Dict, Any
from pathlib import Path
from openai import OpenAI  # v1.x SDK，兼容千问和 DeepSeek 的 OpenAI 接口

from config import (
    QWEN_API_KEY, QWEN_BASE_URL, QWEN_VISION_MODEL, QWEN_TEXT_MODEL, QWEN_API_TIMEOUT,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_API_TIMEOUT,
)

# ============================================================
# 工具函数
# ============================================================
def _safe_usage(usage) -> dict:
    """安全提取 token 统计（字段名因 API 版本而异）"""
    if usage is None: return {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}
    return {
        "prompt_tokens": getattr(usage,"prompt_tokens",0) or 0,
        "completion_tokens": getattr(usage,"completion_tokens",0) or 0,
        "total_tokens": getattr(usage,"total_tokens",0) or 0,
    }

# ============================================================
# QwenClient: 千问多模态（看图+文本）→ VQA + MRG
# ============================================================
class QwenClient:
    def __init__(self):
        self.client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL,
            timeout=httpx.Timeout(QWEN_API_TIMEOUT,connect=10.0), max_retries=2)

    @staticmethod
    def _encode_image(path: str, max_mb=20) -> str:
        """本地图片 → base64 data: URL（超 20MB 拒绝防止上下文溢出）"""
        sz = Path(path).stat().st_size
        if sz > max_mb*1024*1024: raise ValueError(f"图片过大({sz/1024/1024:.1f}MB)")
        with open(path,"rb") as f: data = base64.b64encode(f.read()).decode()
        ext = Path(path).suffix.lower().replace(".","")
        mime = {"jpg":"jpeg","jpeg":"jpeg","png":"png","gif":"gif","webp":"webp",
                "tiff":"tiff","tif":"tiff","dcm":"dicom"}.get(ext,"jpeg")
        return f"data:image/{mime};base64,{data}"

    @staticmethod
    def _safe_content(r) -> str:
        try: c = r.choices[0].message.content; return c or "（空响应）"
        except: return "（解析失败）"

    def vqa(self, image_path: str, question: str, sp: str = None) -> dict:
        """VQA 视觉问答：图片 + 问题 → AI 诊断回答"""
        if not sp: sp = "你是资深医学影像专家，用专业中文回答。结构：1.所见 2.诊断 3.鉴别 4.建议"
        img = self._encode_image(image_path)
        msgs = [{"role":"system","content":sp},
                {"role":"user","content":[{"type":"image_url","image_url":{"url":img}},
                                           {"type":"text","text":question}]}]
        t0 = time.time()
        try:
            r = self.client.chat.completions.create(model=QWEN_VISION_MODEL, messages=msgs,
                                                     max_tokens=2048, temperature=0.2)
            return {"content":self._safe_content(r), "model":r.model,
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}
        except Exception as e:
            return {"content":f"Qwen VQA 失败: {e}", "model":QWEN_VISION_MODEL,
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}

    def generate_report(self, image_path: str, clinical_info="") -> dict:
        """MRG 报告生成：影像 + 临床信息 → 结构化诊断报告"""
        sp = ("你是资深放射科专家，生成规范中文报告。格式：【检查项目】【检查技术】"
              "【影像所见】【诊断印象】【建议】")
        img = self._encode_image(image_path)
        prompt = "请生成完整影像诊断报告。" if not clinical_info else f"临床信息：{clinical_info}\n\n请生成完整影像诊断报告。"
        msgs = [{"role":"system","content":sp},
                {"role":"user","content":[{"type":"image_url","image_url":{"url":img}},
                                           {"type":"text","text":prompt}]}]
        t0 = time.time()
        try:
            r = self.client.chat.completions.create(model=QWEN_VISION_MODEL, messages=msgs,
                                                     max_tokens=4096, temperature=0.2)
            return {"content":self._safe_content(r), "model":r.model,
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}
        except Exception as e:
            return {"content":f"Qwen MRG 失败: {e}", "model":QWEN_VISION_MODEL,
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}

    def text_chat(self, msgs: List[Dict], system=None, max_tokens=2048) -> dict:
        """纯文本对话（备用）"""
        full = [{"role":"system","content":system}] if system else []
        full.extend(msgs)
        t0 = time.time()
        try:
            r = self.client.chat.completions.create(model=QWEN_TEXT_MODEL, messages=full,
                                                     max_tokens=max_tokens, temperature=0.2)
            return {"content":self._safe_content(r), "model":r.model,
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}
        except Exception as e:
            return {"content":f"Qwen 文本失败: {e}", "model":QWEN_TEXT_MODEL,
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}

# ============================================================
# DeepSeekClient: 文本推理 → RAG + 挂号意图
# ============================================================
class DeepSeekClient:
    def __init__(self):
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL,
            timeout=httpx.Timeout(DEEPSEEK_API_TIMEOUT,connect=10.0), max_retries=2)

    @staticmethod
    def _safe_content(r) -> str:
        try: c = r.choices[0].message.content; return c or "（空响应）"
        except: return "（解析失败）"

    @staticmethod
    def _classify(err: str) -> str:
        """原始错误 → 用户友好中文提示"""
        e = err.lower()
        if "401" in err or "unauthorized" in e: return "API Key 无效，请检查 DEEPSEEK_API_KEY"
        if "402" in err or "insufficient" in e: return "API 余额不足"
        if "429" in err or "rate" in e: return "请求太频繁，请稍后"
        if "timeout" in e: return "API 超时，请检查网络"
        if "connection" in e: return "无法连接 DeepSeek"
        return f"DeepSeek API 错误: {err}"

    def rag_query(self, question: str, docs: List[str], sp: str = None) -> dict:
        """RAG 检索增强：知识库文档 + 问题 → 有据可依的回答"""
        if not sp: sp = ("你是医学AI助手。严格基于参考资料回答，不足请说明。"
                         "引用参考编号。结构：回答→依据→补充")
        ctx = "\n\n".join(f"【参考 {i+1}】\n{d}" for i,d in enumerate(docs))
        msg = f"{ctx}\n\n【问题】\n{question}"
        # 粗估 token 防超长（DeepSeek ~64K 上下文）
        if len(msg)//2 + len(sp)//2 > 60000:
            ml = max(0,(60000-len(question)-len(sp))//max(len(docs),1))
            docs = [d[:ml]+"..." for d in docs]
            ctx = "\n\n".join(f"【参考 {i+1}】\n{d}" for i,d in enumerate(docs))
            msg = f"{ctx}\n\n【问题】\n{question}"
        t0 = time.time()
        try:
            r = self.client.chat.completions.create(model=DEEPSEEK_MODEL,
                messages=[{"role":"system","content":sp},{"role":"user","content":msg}],
                max_tokens=2048, temperature=0.1)
            return {"content":self._safe_content(r), "model":r.model,
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}
        except Exception as e:
            return {"content":self._classify(str(e)), "model":DEEPSEEK_MODEL,
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}

    def chat(self, msgs: List[Dict], system=None, max_tokens=2048) -> dict:
        """通用文本对话：挂号意图 / 健康咨询"""
        full = [{"role":"system","content":system}] if system else []
        full.extend(msgs)
        t0 = time.time()
        try:
            r = self.client.chat.completions.create(model=DEEPSEEK_MODEL, messages=full,
                                                     max_tokens=max_tokens, temperature=0.2)
            return {"content":self._safe_content(r), "model":r.model,
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}
        except Exception as e:
            return {"content":self._classify(str(e)), "model":DEEPSEEK_MODEL,
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}

# ============================================================
# 全局单例
# ============================================================
_qwen = None; _ds = None

def get_qwen_client():
    global _qwen
    if not _qwen: _qwen = QwenClient()
    return _qwen

def get_deepseek_client():
    global _ds
    if not _ds: _ds = DeepSeekClient()
    return _ds

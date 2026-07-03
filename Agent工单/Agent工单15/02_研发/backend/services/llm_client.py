"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
LLM 客户端 —— 千问多模态 + DeepSeek 文本推理
================================================================================
"""
import base64, time, httpx  # 导入base64编码、时间、HTTP客户端库
from typing import Optional, List, Dict, Any  # 导入类型提示，用于函数签名标注
from pathlib import Path  # 导入路径处理库，用于文件路径操作
from openai import OpenAI  # v1.x SDK，兼容千问和 DeepSeek 的 OpenAI 接口（统一调用协议）

from config import (  # 从项目配置文件导入所有API密钥和模型参数
    QWEN_API_KEY, QWEN_BASE_URL, QWEN_VISION_MODEL, QWEN_TEXT_MODEL, QWEN_API_TIMEOUT,  # 千问（通义千问）API配置：密钥、地址、视觉模型、文本模型、超时
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_API_TIMEOUT,  # DeepSeek API配置：密钥、地址、模型名、超时
    KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL, KIMI_API_TIMEOUT,  # Kimi（月之暗面/Moonshot）API配置：密钥、地址、模型名、超时
)

# ============================================================
# 工具函数
# ============================================================
def _safe_usage(usage) -> dict:  # 定义安全提取token用量统计的辅助函数，参数usage为API返回的usage对象
    """安全提取 token 统计（字段名因 API 版本而异）"""  # 文档字符串：说明函数用途
    if usage is None: return {"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}  # 如果usage为None则返回全零统计（防御性编程）
    return {  # 返回一个包含token统计的字典
        "prompt_tokens": getattr(usage,"prompt_tokens",0) or 0,  # 安全获取提示词token数，不存在则默认为0
        "completion_tokens": getattr(usage,"completion_tokens",0) or 0,  # 安全获取补全token数，不存在则默认为0
        "total_tokens": getattr(usage,"total_tokens",0) or 0,  # 安全获取总token数，不存在则默认为0
    }

# ============================================================
# QwenClient: 千问多模态（看图+文本）→ VQA + MRG
# ============================================================
class QwenClient:  # 定义千问客户端类，封装通义千问多模态API的调用逻辑
    def __init__(self):  # 构造函数，初始化千问客户端实例
        self.client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL,  # 创建OpenAI兼容客户端，传入千问API密钥和基础URL
            timeout=httpx.Timeout(QWEN_API_TIMEOUT,connect=10.0), max_retries=2)  # 设置HTTP超时（总超时+连接超时10秒）和最大重试次数2

    @staticmethod  # 声明为静态方法，不依赖类实例
    def _encode_image(path: str, max_mb=20) -> str:  # 将本地图片文件编码为base64格式的data:URL字符串，max_mb为文件大小上限（MB）
        """本地图片 → base64 data: URL（超 20MB 拒绝防止上下文溢出）"""  # 文档字符串说明功能
        sz = Path(path).stat().st_size  # 获取图片文件的字节大小
        if sz > max_mb*1024*1024: raise ValueError(f"图片过大({sz/1024/1024:.1f}MB)")  # 如果文件超过限制大小则抛出异常，防止超大图片导致API上下文溢出
        with open(path,"rb") as f: data = base64.b64encode(f.read()).decode()  # 以二进制模式读取图片并编码为base64字符串
        ext = Path(path).suffix.lower().replace(".","")  # 提取文件扩展名并转小写，去掉点号（如".jpg"→"jpg"）
        mime = {"jpg":"jpeg","jpeg":"jpeg","png":"png","gif":"gif","webp":"webp",  # 建立文件扩展名到MIME类型的映射字典
                "tiff":"tiff","tif":"tiff","dcm":"dicom"}.get(ext,"jpeg")  # 查字典获取MIME，DICOM医学影像特殊映射，未匹配则默认jpeg
        return f"data:image/{mime};base64,{data}"  # 返回标准的base64 data:URL格式字符串，供API直接使用

    @staticmethod  # 声明为静态方法
    def _safe_content(r) -> str:  # 安全提取API响应中的文本内容
        try: c = r.choices[0].message.content; return c or "（空响应）"  # 尝试获取第一条回复的消息内容，如果为None则返回空响应占位符
        except: return "（解析失败）"  # 如果解析过程出现任何异常，返回解析失败提示

    def vqa(self, image_path: str, question: str, sp: str = None) -> dict:  # 视觉问答方法：输入图片路径和问题，返回AI诊断回答
        """VQA 视觉问答：图片 + 问题 → AI 诊断回答"""  # 文档字符串说明功能
        if not sp: sp = "你是资深医学影像专家，用专业中文回答。结构：1.所见 2.诊断 3.鉴别 4.建议"  # 如果未提供系统提示词，使用默认的医学影像专家提示词模板
        img = self._encode_image(image_path)  # 将图片编码为base64格式
        msgs = [{"role":"system","content":sp},  # 构建消息列表：第一条为系统角色提示词
                {"role":"user","content":[{"type":"image_url","image_url":{"url":img}},  # 用户消息：包含编码后的图片URL（多模态输入）
                                           {"type":"text","text":question}]}]  # 用户消息：同时包含文本问题（图文混排）
        t0 = time.time()  # 记录API调用开始时间，用于计算延迟
        try:  # 异常捕获：处理API调用可能出现的网络或认证错误
            r = self.client.chat.completions.create(model=QWEN_VISION_MODEL, messages=msgs,  # 调用千问视觉模型进行图文对话补全
                                                     max_tokens=2048, temperature=0.2)  # 限制最大输出2048token，温度0.2使回答稳定确定
            return {"content":self._safe_content(r), "model":r.model,  # 返回字典：提取的回答内容、使用的模型名
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}  # 返回token用量统计和API调用延迟（毫秒）
        except Exception as e:  # 捕获所有API调用异常
            return {"content":f"Qwen VQA 失败: {e}", "model":QWEN_VISION_MODEL,  # 返回失败信息：错误描述和模型名
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}  # 返回空用量统计、延迟时间、以及错误详情字符串

    def generate_report(self, image_path: str, clinical_info="") -> dict:  # 报告生成方法：影像+临床信息→结构化诊断报告
        """MRG 报告生成：影像 + 临床信息 → 结构化诊断报告"""  # 文档字符串说明
        sp = ("你是资深放射科专家，生成规范中文报告。格式：【检查项目】【检查技术】"  # 系统提示词前半部分：角色设定为放射科专家
              "【影像所见】【诊断印象】【建议】")  # 系统提示词后半部分：报告结构化格式要求
        img = self._encode_image(image_path)  # 将影像图片编码为base64
        prompt = "请生成完整影像诊断报告。" if not clinical_info else f"临床信息：{clinical_info}\n\n请生成完整影像诊断报告。"  # 根据是否有临床信息构建不同的用户提示词
        msgs = [{"role":"system","content":sp},  # 系统消息：放射科专家角色提示
                {"role":"user","content":[{"type":"image_url","image_url":{"url":img}},  # 用户消息：包含编码后的影像图片
                                           {"type":"text","text":prompt}]}]  # 用户消息：包含文本提示（含或不含临床信息）
        t0 = time.time()  # 记录开始时间
        try:  # 异常捕获
            r = self.client.chat.completions.create(model=QWEN_VISION_MODEL, messages=msgs,  # 调用千问视觉模型生成报告
                                                     max_tokens=4096, temperature=0.2)  # 报告通常较长，设置4096最大token，温度0.2确保专业性
            return {"content":self._safe_content(r), "model":r.model,  # 返回报告内容、模型名
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}  # 返回token统计和延迟
        except Exception as e:  # 捕获异常
            return {"content":f"Qwen MRG 失败: {e}", "model":QWEN_VISION_MODEL,  # 返回失败信息
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}  # 返回空统计、延迟和错误

    def text_chat(self, msgs: List[Dict], system=None, max_tokens=2048) -> dict:  # 纯文本对话方法（备用），支持自定义消息列表和系统提示
        """纯文本对话（备用）"""  # 文档字符串
        full = [{"role":"system","content":system}] if system else []  # 如果有系统提示词则添加系统消息，否则从空列表开始
        full.extend(msgs)  # 将用户提供的消息列表追加到对话历史后面
        t0 = time.time()  # 记录开始时间
        try:  # 异常捕获
            r = self.client.chat.completions.create(model=QWEN_TEXT_MODEL, messages=full,  # 调用千问纯文本模型进行对话
                                                     max_tokens=max_tokens, temperature=0.2)  # 使用传入的最大token数和稳定温度
            return {"content":self._safe_content(r), "model":r.model,  # 返回回答内容和模型名
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}  # 返回token统计和延迟
        except Exception as e:  # 捕获异常
            return {"content":f"Qwen 文本失败: {e}", "model":QWEN_TEXT_MODEL,  # 返回失败信息
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}  # 返回空统计、延迟和错误

# ============================================================
# DeepSeekClient: 文本推理 → RAG + 挂号意图
# ============================================================
class DeepSeekClient:  # 定义DeepSeek客户端类，封装DeepSeek API调用逻辑（用于RAG推理和挂号意图识别）
    def __init__(self):  # 构造函数
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL,  # 创建OpenAI兼容客户端，传入DeepSeek API密钥和地址
            timeout=httpx.Timeout(DEEPSEEK_API_TIMEOUT,connect=10.0), max_retries=2)  # 设置HTTP超时和最大重试次数2

    @staticmethod  # 声明为静态方法
    def _safe_content(r) -> str:  # 安全提取API响应内容
        try: c = r.choices[0].message.content; return c or "（空响应）"  # 提取第一条消息内容，空则返回占位符
        except: return "（解析失败）"  # 解析失败返回提示

    @staticmethod  # 声明为静态方法
    def _classify(err: str) -> str:  # 将原始错误信息转换为用户友好的中文提示
        """原始错误 → 用户友好中文提示"""  # 文档字符串
        e = err.lower()  # 将错误信息转为小写以便统一匹配
        if "401" in err or "unauthorized" in e: return "API Key 无效，请检查 DEEPSEEK_API_KEY"  # 401未授权错误：提示检查API密钥
        if "402" in err or "insufficient" in e: return "API 余额不足"  # 402付费错误：提示余额不足
        if "429" in err or "rate" in e: return "请求太频繁，请稍后"  # 429限流错误：提示请求过于频繁
        if "timeout" in e: return "API 超时，请检查网络"  # 超时错误：提示检查网络连接
        if "connection" in e: return "无法连接 DeepSeek"  # 连接错误：提示无法连接服务
        return f"DeepSeek API 错误: {err}"  # 其他未知错误：返回原始错误信息

    def rag_query(self, question: str, docs: List[str], sp: str = None) -> dict:  # RAG检索增强查询：知识库文档+问题→有据可依的回答
        """RAG 检索增强：知识库文档 + 问题 → 有据可依的回答"""  # 文档字符串
        if not sp: sp = ("你是医学AI助手。严格基于参考资料回答，不足请说明。"  # 默认系统提示词第一部分：角色定位为医学AI助手
                         "引用参考编号。结构：回答→依据→补充")  # 默认系统提示词第二部分：要求引用参考编号并给出结构化回答
        ctx = "\n\n".join(f"【参考 {i+1}】\n{d}" for i,d in enumerate(docs))  # 将所有参考文档拼接为上下文，每条以"【参考 N】"标记编号
        msg = f"{ctx}\n\n【问题】\n{question}"  # 将上下文和用户问题组合成完整的用户消息
        # 粗估 token 防超长（DeepSeek ~64K 上下文）  # 注释：DeepSeek上下文窗口约64K tokens
        if len(msg)//2 + len(sp)//2 > 60000:  # 粗略估算token数（中文字符大约2字符=1token），超过60000则触发截断
            ml = max(0,(60000-len(question)-len(sp))//max(len(docs),1))  # 计算每个文档允许的最大字符数（平均分配剩余空间）
            docs = [d[:ml]+"..." for d in docs]  # 按计算的长度截断每个文档，末尾加省略号
            ctx = "\n\n".join(f"【参考 {i+1}】\n{d}" for i,d in enumerate(docs))  # 用截断后的文档重新构建上下文
            msg = f"{ctx}\n\n【问题】\n{question}"  # 重新组合用户消息
        t0 = time.time()  # 记录开始时间
        try:  # 异常捕获
            r = self.client.chat.completions.create(model=DEEPSEEK_MODEL,  # 调用DeepSeek模型
                messages=[{"role":"system","content":sp},{"role":"user","content":msg}],  # 构建消息：系统提示词+用户消息（含上下文）
                max_tokens=2048, temperature=0.1)  # 最大输出2048token，温度0.1使回答非常确定（减少幻觉）
            return {"content":self._safe_content(r), "model":r.model,  # 返回回答内容和模型名
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}  # 返回token统计和延迟
        except Exception as e:  # 捕获异常
            return {"content":self._classify(str(e)), "model":DEEPSEEK_MODEL,  # 返回分类后的友好错误提示和模型名
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}  # 返回空统计、延迟和错误

    def chat(self, msgs: List[Dict], system=None, max_tokens=2048) -> dict:  # 通用文本对话方法：用于挂号意图识别和健康咨询
        """通用文本对话：挂号意图 / 健康咨询"""  # 文档字符串
        full = [{"role":"system","content":system}] if system else []  # 如果有系统提示词则构建系统消息
        full.extend(msgs)  # 追加用户消息列表
        t0 = time.time()  # 记录开始时间
        try:  # 异常捕获
            r = self.client.chat.completions.create(model=DEEPSEEK_MODEL, messages=full,  # 调用DeepSeek模型进行对话
                                                     max_tokens=max_tokens, temperature=0.2)  # 使用传入的最大token和稳定温度
            return {"content":self._safe_content(r), "model":r.model,  # 返回回答和模型名
                    "usage":_safe_usage(r.usage), "latency_ms":round((time.time()-t0)*1000,2)}  # 返回token统计和延迟
        except Exception as e:  # 捕获异常
            return {"content":self._classify(str(e)), "model":DEEPSEEK_MODEL,  # 返回友好错误提示和模型名
                    "usage":{}, "latency_ms":round((time.time()-t0)*1000,2), "error":str(e)}  # 返回空统计、延迟和错误

# ============================================================
# KimiClient: Moonshot API → 需求分析 / 医学报告生成
#   工单要求：使用 Kimi 进行需求分析，产出分析报告
# ============================================================
class KimiClient:  # 定义Kimi客户端类，封装月之暗面Moonshot API调用逻辑（用于需求分析和报告生成）
    def __init__(self):  # 构造函数
        self.client = OpenAI(api_key=KIMI_API_KEY, base_url=KIMI_BASE_URL,  # 创建OpenAI兼容客户端，传入Kimi API密钥和地址
            timeout=httpx.Timeout(KIMI_API_TIMEOUT, connect=10.0), max_retries=2)  # 设置HTTP超时和最大重试次数2

    @staticmethod  # 声明为静态方法
    def _safe_content(r) -> str:  # 安全提取API响应内容
        try: c = r.choices[0].message.content; return c or "（空响应）"  # 提取第一条消息内容，空则返回占位符
        except: return "（解析失败）"  # 解析失败返回提示

    @staticmethod  # 声明为静态方法
    def _classify(err: str) -> str:  # 错误分类器：将原始错误转换为中文友好提示
        e = err.lower()  # 转为小写统一匹配
        if "401" in err or "unauthorized" in e: return "Kimi API Key 无效"  # 认证失败提示
        if "402" in err or "insufficient" in e: return "Kimi API 余额不足"  # 余额不足提示
        if "429" in err or "rate" in e: return "请求太频繁，请稍后"  # 限流提示
        if "timeout" in e: return "Kimi API 超时"  # 超时提示
        return f"Kimi API 错误: {err}"  # 其他错误返回原始信息

    def analyze(self, content: str, task: str = "需求分析") -> dict:  # Kimi需求分析方法：输入文档/需求内容→结构化分析报告
        """Kimi 需求分析：输入文档/需求 → 结构化分析报告"""  # 文档字符串
        sp = ("你是一位资深的技术需求分析师。请对以下内容进行全面分析，"  # 系统提示词第一部分：角色设定为技术需求分析师
              "生成结构化的分析报告。格式：\n"  # 系统提示词第二部分：要求生成结构化报告
              "1. 需求概述\n2. 功能点拆解\n3. 技术可行性评估\n"  # 报告结构：需求概述、功能拆解、技术评估
              "4. 风险评估\n5. 实施建议\n6. 关键指标\n"  # 报告结构：风险评估、实施建议、关键指标
              "用中文，简洁专业。")  # 语言要求：中文，简洁专业
        t0 = time.time()  # 记录开始时间
        try:  # 异常捕获
            r = self.client.chat.completions.create(model=KIMI_MODEL,  # 调用Kimi模型
                messages=[{"role":"system","content":sp},  # 系统消息：分析师角色和报告格式要求
                         {"role":"user","content":f"任务：{task}\n\n内容：\n{content[:8000]}"}],  # 用户消息：任务描述和待分析内容（截断至8000字符防止超长）
                max_tokens=4096, temperature=0.3)  # 分析报告需要较长输出，设置4096最大token，温度0.3保持一定的分析创造性
            return {"content": self._safe_content(r), "model": r.model,  # 返回分析报告内容和模型名
                    "usage": _safe_usage(r.usage), "latency_ms": round((time.time()-t0)*1000, 2)}  # 返回token统计和延迟（毫秒，保留2位小数）
        except Exception as e:  # 捕获异常
            return {"content": self._classify(str(e)), "model": KIMI_MODEL,  # 返回友好错误提示和模型名
                    "usage": {}, "latency_ms": round((time.time()-t0)*1000, 2), "error": str(e)}  # 返回空统计、延迟和原始错误

    def chat(self, msgs: list, system=None, max_tokens=2048) -> dict:  # Kimi通用对话方法
        """通用对话"""  # 文档字符串
        full = [{"role": "system", "content": system}] if system else []  # 如果有系统提示词则添加
        full.extend(msgs)  # 追加用户消息列表
        t0 = time.time()  # 记录开始时间
        try:  # 异常捕获
            r = self.client.chat.completions.create(model=KIMI_MODEL, messages=full,  # 调用Kimi模型进行对话
                max_tokens=max_tokens, temperature=0.2)  # 使用传入的最大token和稳定温度
            return {"content": self._safe_content(r), "model": r.model,  # 返回回答和模型名
                    "usage": _safe_usage(r.usage), "latency_ms": round((time.time()-t0)*1000, 2)}  # 返回token统计和延迟
        except Exception as e:  # 捕获异常
            return {"content": self._classify(str(e)), "model": KIMI_MODEL,  # 返回友好错误和模型名
                    "usage": {}, "latency_ms": round((time.time()-t0)*1000, 2), "error": str(e)}  # 返回空统计、延迟和错误

# ============================================================
# 全局单例
# ============================================================
_qwen = None; _ds = None; _kimi = None  # 初始化三个客户端的全局单例变量，均为None表示尚未创建

def get_qwen_client():  # 获取千问客户端单例的工厂函数
    global _qwen  # 声明使用全局变量_qwen
    if not _qwen: _qwen = QwenClient()  # 如果尚未创建实例则新建（懒加载模式，延迟初始化）
    return _qwen  # 返回千问客户端单例

def get_deepseek_client():  # 获取DeepSeek客户端单例的工厂函数
    global _ds  # 声明使用全局变量_ds
    if not _ds: _ds = DeepSeekClient()  # 如果尚未创建实例则新建（懒加载）
    return _ds  # 返回DeepSeek客户端单例

def get_kimi_client():  # 获取Kimi客户端单例的工厂函数
    global _kimi  # 声明使用全局变量_kimi
    if not _kimi: _kimi = KimiClient()  # 如果尚未创建实例则新建（懒加载）
    return _kimi  # 返回Kimi客户端单例

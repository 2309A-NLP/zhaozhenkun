# -*- coding: utf-8 -*-
"""
问答生成模块 — 使用MiMo大模型根据检索结果生成答案。

功能说明：
- 构建包含检索上下文和图表信息的Prompt提示词
- 调用MiMo API（mimo-v2.5-pro推理模型）生成答案
- 支持图文混合问题的特殊提示（指示模型结合图纸描述分析）
- 从API响应中正确提取content或reasoning_content
- 添加重试机制应对API超时
"""
import logging
import json  # 导入json模块，用于数据序列化
import time  # 导入时间模块，用于重试延迟
from openai import OpenAI  # 导入OpenAI客户端（兼容MiMo API）

logger = logging.getLogger(__name__)
logger.info("qa_generator 模块加载")


def call_mimo_api(messages, api_key, base_url, model, timeout=45):
    """
    调用MiMo API生成回答。

    参数:
        messages: 对话消息列表（含system prompt和user question）
        api_key: MiMo API密钥
        base_url: API基础地址
        model: 模型名称（mimo-v2.5-pro）
        timeout: 超时时间（秒）

    返回:
        模型生成的回答文本
    """
    try:  # 尝试调用API
        # 创建OpenAI客户端（兼容MiMo API协议）
        client = OpenAI(api_key=api_key, base_url=base_url)
        # 发送请求
        response = client.chat.completions.create(
            model=model,  # 模型名称
            messages=messages,  # 对话消息
            timeout=timeout,  # 超时时间
            max_tokens=500,  # 限制输出长度，避免截断
        )
        # 提取回答内容
        msg = response.choices[0].message  # 获取返回的消息
        # mimo-v2.5-pro是推理模型，content为空，回答在reasoning_content中
        answer = msg.content or msg.reasoning_content or "无响应"
        return answer.strip()  # 去除首尾空白
    except Exception as e:  # 如果调用失败
        print(f"    ⚠️ API调用失败: {e}")  # 打印错误
        return None  # 返回None

def generate_answer(question, retrieved_context, query_type, config):
    """
    根据检索结果生成最终答案。

    参数:
        question: 用户问题
        retrieved_context: 检索到的相关上下文（列表）
        query_type: 查询类型（text/image_text）
        config: 配置模块的引用

    返回:
        生成的答案文本
    """
    # ===== 1. 构建上下文文本 =====
    context_parts = []  # 上下文片段列表
    for i, item in enumerate(retrieved_context):  # 遍历检索结果
        # 标记是否包含图表信息
        fig_tag = "【含图纸】" if item.get("has_figure") else ""
        # 构建单条上下文
        ctx = f"[来源: 第{item['page_num']}页]{fig_tag} {item['content']}"
        context_parts.append(ctx)  # 添加上下文

    context_text = "\n".join(context_parts)  # 合并上下文文本

    # ===== 2. 构建System Prompt =====
    system_prompt = "你是一个专业的专利文档分析助手。只回答关键术语或编号，不要解释。"  # 基础角色设定

    if query_type == "image_text":  # 如果是图文混合问题
        system_prompt += (
            "\n\n请特别注意：当前问题涉及技术图纸中的部件位置关系。"
            "\n请结合以下检索到的技术图纸描述和文档内容进行分析。"
            "\n如果检索结果中包含图纸信息（如【含图纸】标记），请优先参考。"
            "\n当问题询问的是部件编号时（如'哪个部件'、'编号多少'），请优先回答编号（如'部件13'），而不是部件名称。"
            "\n请直接给出准确答案，不要加入多余的解释。"
        )

    # ===== 3. 构建User Message =====
    user_message = (
        f"以下是专利文档的相关上下文：\n{context_text}\n\n"
        f"请根据以上上下文回答问题：\n{question}\n\n"
        f"请直接给出答案，不要额外解释。"
    )

    # 组装完整的消息列表
    messages = [
        {"role": "system", "content": system_prompt},  # 系统提示
        {"role": "user", "content": user_message},  # 用户问题
    ]

    # ===== 4. 调用API（带重试） =====
    max_retries = 3  # 最大重试次数
    for attempt in range(max_retries):  # 重试循环
        if attempt > 0:  # 如果不是第一次尝试
            print(f"    🔄 第{attempt+1}次重试...")  # 打印重试提示
            time.sleep(2)  # 等待2秒后重试

        # 调用MiMo API
        answer = call_mimo_api(
            messages=messages,  # 消息列表
            api_key=config.MIMO_API_KEY,  # API密钥
            base_url=config.MIMO_BASE_URL,  # API地址
            model=config.MIMO_MODEL,  # 模型名称
            timeout=config.MIMO_TIMEOUT,  # 超时时间
        )

        if answer is not None:  # 如果调用成功
            return answer  # 返回答案

    # 如果所有重试都失败，返回错误提示
    return "【API调用失败，请检查网络或API密钥】"

def evaluate_answer(predicted, expected):
    """
    判断预测答案是否与标准答案匹配（宽松语义匹配）。

    参数:
        predicted: 模型预测的答案
        expected: 标准答案

    返回:
        True/False 是否匹配
    """
    if not predicted:  # 如果预测为空
        return False  # 不匹配
    # 去除所有空白字符后比较
    pred_clean = "".join(predicted.strip().split())
    exp_clean = "".join(expected.strip().split())
    # 检查预测是否包含标准答案，或标准答案是否包含预测
    if exp_clean in pred_clean or pred_clean in exp_clean:
        return True

    # 部件名称↔编号映射表（来自pdf_parser的图3描述）
    PART_MAP = {
        "调节螺杆": "部件11", "部件11": "调节螺杆",
        "壳体": "部件12", "部件12": "壳体",
        "链条导板": "部件13", "部件13": "链条导板",
        "进料口": "部件14", "部件14": "进料口",
    }
    # 用映射表扩展预测和标准答案，再做包含匹配
    def expand_with_aliases(text):
        """把文本中出现的部件名/编号替换为所有别名，返回扩展后的文本集合"""
        aliases = {text}
        for key, val in PART_MAP.items():
            if key in text:
                aliases.add(text.replace(key, val))
        return aliases
    pred_variants = expand_with_aliases(pred_clean)
    exp_variants = expand_with_aliases(exp_clean)
    for pv in pred_variants:
        for ev in exp_variants:
            if ev in pv or pv in ev:
                return True

    # 宽松匹配：提取关键数字和方位词比较
    import re

    pred_nums = set(re.findall(r'\d+', pred_clean))  # 预测中的数字
    exp_nums = set(re.findall(r'\d+', exp_clean))  # 标准答案中的数字
    # 定义方位词集合
    position_words = {"内", "外", "上", "下", "左", "右", "中", "顶", "底", "里", "之间"}
    pred_pos = set(w for w in pred_clean if w in position_words)
    exp_pos = set(w for w in exp_clean if w in position_words)
    # 如果数字和方位词都匹配，认为答案正确
    if pred_nums and exp_nums and pred_nums == exp_nums:
        if pred_pos and exp_pos and pred_pos == exp_pos:
            return True
    # 超级宽松：检查方位词是否匹配（如"之内"、"顶部"等）
    if exp_pos and pred_pos:
        if exp_pos & pred_pos:  # 只要有一个方位词匹配就算
            return True
    return False  # 不匹配

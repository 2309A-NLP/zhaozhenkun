import logging
logger = logging.getLogger(__name__)
"""
MiMo 对话助手模块（研发层）
功能：调用小米 MiMo API 实现交互式对话，支持多轮上下文
完成：直接运行即可开始聊天，输入 exit 退出 / clear 清空历史
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""
import json                                              # JSON序列化
from urllib import request as ureq, error as uerr         # HTTP请求
from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL  # 小米API配置


def ask_mimo(messages, temperature=0.7, max_tokens=2048):
    """
    向 MiMo API 发送消息并获取回复
    参数：messages - 对话历史列表, temperature - 温度, max_tokens - 最大生成长度
    返回：AI回复文本
    """
    url = f"{MIMO_BASE_URL}/chat/completions"                   # API端点
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}",        # 认证头
               "Content-Type": "application/json"}               # JSON格式
    payload = json.dumps({"model": MIMO_MODEL,                   # 模型名
                          "messages": messages,                  # 对话历史
                          "temperature": temperature,            # 温度
                          "max_tokens": max_tokens}).encode()    # 编码为字节
    try:
        req = ureq.Request(url, data=payload, headers=headers, method="POST")
        with ureq.urlopen(req, timeout=60) as resp:             # 60秒超时
            result = json.loads(resp.read().decode("utf-8"))    # 解析响应
        msg = result["choices"][0]["message"]                    # 提取消息
        return msg.get("content") or msg.get("reasoning_content") or "无响应"
    except Exception as e:
        return f"[错误] {e}"


def chat():
    """交互式对话主循环"""
    print("\n" + "=" * 50)
    print("🤖 MiMo 对话助手 (v2.5-pro)")
    print("输入 exit 退出 | 输入 clear 清空历史")
    print("=" * 50)

    history = [{"role": "system", "content": "你是一个有帮助的AI助手。"}]

    while True:
        user_input = input("\n👤 你: ").strip()                 # 读取用户输入
        if not user_input:
            continue                                              # 跳过空输入
        if user_input.lower() in ("exit", "quit", "退出"):
            print("👋 拜拜~")
            break                                                 # 退出
        if user_input.lower() == "clear":
            history = [history[0]]                                # 保留系统提示
            print("🗑️ 历史已清空")
            continue

        history.append({"role": "user", "content": user_input})   # 添加用户消息
        print("\n🤖 MiMo: ", end="", flush=True)
        reply = ask_mimo(history)                                 # 调用API
        print(reply[:500])                                        # 显示前500字
        if len(reply) > 500:
            print(f"...(共{len(reply)}字，已截断)")
        history.append({"role": "assistant", "content": reply})   # 添加助手回复
        if len(history) > 20:                                     # 限制历史长度
            history = [history[0]] + history[-18:]


if __name__ == "__main__":
    chat()  # 直接运行启动对话

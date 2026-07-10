"""工单18：大模型讲解服务，负责调用DeepSeek生成导览、问答与互动文案。"""
# 工单18：导入requests库，用于访问DeepSeek聊天接口。
import requests

# 工单18：把会话历史整理成适合模型阅读的纯文本上下文。
def build_history_text(messages: list) -> str:
    # 工单18：按角色拼接最近对话，帮助模型保留上下文。
    return "\n".join(f"{item['role']}: {item['content']}" for item in messages)

# 工单18：调用DeepSeek生成最终讲解结果。
def generate_answer(settings: dict, system_prompt: str, user_prompt: str) -> str:
    # 工单18：如果没配DeepSeek密钥，就返回可用的本地占位讲解文本。
    if not settings.get("DEEPSEEK_API_KEY"):
        return "当前未配置DeepSeek密钥，所以这里返回本地演示讲解结果。你可以在部署目录配置密钥后切换为真实大模型回答。"
    # 工单18：拼接DeepSeek聊天接口地址。
    url = settings["DEEPSEEK_BASE_URL"].rstrip("/") + "/chat/completions"
    # 工单18：准备请求头，带上认证信息与JSON格式声明。
    headers = {"Authorization": f"Bearer {settings['DEEPSEEK_API_KEY']}", "Content-Type": "application/json"}
    # 工单18：构造标准聊天消息体，区分系统提示与用户问题。
    payload = {
        "model": settings["DEEPSEEK_MODEL"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
    # 工单18：发起网络请求，让模型生成讲解文本。
    response = requests.post(url, headers=headers, json=payload, timeout=45)
    # 工单18：若请求失败则抛错，由上层接口返回统一错误提示。
    response.raise_for_status()
    # 工单18：解析JSON响应。
    data = response.json()
    # 工单18：优先取content字段，兼容部分返回结构。
    message = data["choices"][0]["message"]
    # 工单18：返回主内容，若为空则退回reasoning_content兼容字段。
    return message.get("content") or message.get("reasoning_content") or ""

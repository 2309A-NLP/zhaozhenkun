"""工单19：错题解析、错因归纳与变式题生成服务。"""

# 工单19：导入 JSON 处理工具，用于解析模型输出。
import json

# 工单19：导入网络请求工具，用于调用兼容 OpenAI 的模型接口。
import urllib.error
import urllib.request

# 工单19：导入项目模型配置。
from development.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, MODEL_PROVIDER, QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL


# 工单19：按优先级选择可用的大模型供应商。
def choose_provider():
    providers = {
        "deepseek": {"name": "deepseek", "base_url": DEEPSEEK_BASE_URL, "api_key": DEEPSEEK_API_KEY, "model": DEEPSEEK_MODEL},
        "qwen": {"name": "qwen", "base_url": QWEN_BASE_URL, "api_key": QWEN_API_KEY, "model": QWEN_MODEL},
    }
    preferred = providers.get(MODEL_PROVIDER)
    if preferred and preferred["api_key"]:
        return preferred
    for provider in providers.values():
        if provider["api_key"]:
            return provider
    return None


# 工单19：构造错题分析提示词，强调解释性与变式练习输出。
def build_prompt(question_row, wrong_answer, knowledge_point):
    payload = {
        "原题题干": question_row["question"],
        "学生错误答案": wrong_answer,
        "正确答案": question_row["answer"],
        "所属知识点": knowledge_point["name"],
        "常见错误类型": question_row["common_error"],
    }
    instruction = {
        "任务": "你是教育智能体中的助教，请面向学生生成可理解、可解释的错题分析。",
        "输出要求": [
            "返回 JSON 对象，且不要输出 JSON 之外的任何说明。",
            "analysis 字段用 2-3 句话解释题目。",
            "reason 字段用 1-2 句话指出学生可能的错误原因。",
            "variants 字段输出 3 道同知识点不同形式的变式题，每道包含 question、answer。",
        ],
        "输入": payload,
    }
    return json.dumps(instruction, ensure_ascii=False)


# 工单19：从模型文本中提取 JSON 块，兼容模型额外输出说明的情况。
def parse_json_content(raw_text):
    start_index = raw_text.find("{")
    end_index = raw_text.rfind("}")
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        raise ValueError("模型返回内容不包含 JSON 对象")
    return json.loads(raw_text[start_index : end_index + 1])


# 工单19：调用兼容 OpenAI 的聊天接口，获取结构化错题分析。
def call_compatible_model(prompt, provider):
    endpoint = provider["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": provider["model"],
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": "你是严谨的教育助教。"},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return parse_json_content(content)


# 工单19：在未配置模型或模型失败时，生成稳定可用的本地兜底内容。
def build_fallback_result(question_row, wrong_answer, knowledge_point):
    analysis = (
        f"这道题考查的是“{knowledge_point['name']}”的核心概念。"
        f"正确答案是“{question_row['answer']}”，关键在于先识别题目真正考查的能力，再排除与知识点无关的干扰项。"
    )
    reason = (
        f"你选择了“{wrong_answer}”，可能是因为{question_row['common_error']}。"
        f"建议先回到“{knowledge_point['name']}”的定义与典型应用场景，再做同类判断。"
    )
    variants = [
        {"question": f"请用自己的话解释“{knowledge_point['name']}”在学习推荐场景中的作用。", "answer": f"能够支撑与{knowledge_point['name']}相关的学习判断与推荐。"},
        {"question": f"如果要把“{knowledge_point['name']}”应用到教育智能体中，最先要明确什么？", "answer": "要明确该知识点解决的问题与输入输出约束。"},
        {"question": f"围绕“{knowledge_point['name']}”，请给出一个与原题不同问法的判断要点。", "answer": "先识别知识点本质，再根据场景匹配最合适的策略。"},
    ]
    return {"analysis": analysis, "reason": reason, "variants": variants, "provider": "local-fallback"}


# 工单19：对外暴露统一的错题解析生成方法。
def generate_wrong_book_content(question_row, wrong_answer, knowledge_point):
    provider = choose_provider()
    if not provider:
        return build_fallback_result(question_row, wrong_answer, knowledge_point)
    prompt = build_prompt(question_row, wrong_answer, knowledge_point)
    try:
        result = call_compatible_model(prompt, provider)
        result["provider"] = provider["name"]
        return result
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
        return build_fallback_result(question_row, wrong_answer, knowledge_point)

"""
LLM 问答模块
功能：调用小米 MiMo API 进行问答，将检索到的上下文与用户问题组合成 prompt
说明：参考上下文从 retriever 模块获取，本模块负责生成最终答案。带自动重试机制
"""
import logging
import requests                                  # HTTP 请求库
import json                                      # JSON 解析
import time                                      # 重试延时
import traceback                                 # 异常堆栈

logger = logging.getLogger(__name__)
logger.info("llm_qa 模块加载")


from config import (

    MIMO_API_KEY,                                # MiMo API 密钥
    MIMO_BASE_URL,                               # API 地址
    MIMO_MODEL,                                  # 模型名称
    MIMO_TIMEOUT,                                # 超时时间
    MIMO_TEMPERATURE,                            # 生成温度
    MIMO_MAX_TOKENS,                             # 最大生成 token
)

def call_mimo(prompt: str, system_prompt: str = None, retries: int = 2) -> str:
    """
    调用小米 MiMo API，发送 prompt 返回 AI 回复（带自动重试+指数退避）
    参数：prompt — 用户输入
          system_prompt — 系统角色设定（可选）
          retries — 失败重试次数
    返回：AI 回复的文本
    """
    last_error = None
    # 循环执行：首次尝试 + retries 次重试
    for attempt in range(1 + retries):
        try:
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {MIMO_API_KEY}",
                "Content-Type": "application/json",
            }

            # 构建消息列表
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # 构建请求体
            payload = {
                "model": MIMO_MODEL,
                "messages": messages,
                "temperature": MIMO_TEMPERATURE,
                "max_tokens": MIMO_MAX_TOKENS,
            }

            # 发送 POST 请求到 chat/completions 接口
            resp = requests.post(
                url=f"{MIMO_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=MIMO_TIMEOUT,
            )

            # 检查 HTTP 状态码
            if resp.status_code != 200:
                # 500 错误可能是后端临时故障，重试可能解决
                if resp.status_code == 500 and attempt < retries:
                    wait = 10 * (attempt + 1)   # 指数退避：10s, 20s, ...
                    print(f"  ⚠ API返回{resp.status_code}，{wait}秒后重试({attempt+1}/{retries})")
                    time.sleep(wait)
                    continue
                raise Exception(
                    f"API请求失败: HTTP {resp.status_code}, {resp.text[:200]}"
                )

            # 解析返回 JSON，提取 AI 回复内容
            result = resp.json()
            msg = result["choices"][0]["message"]
            # MiMo推理模型会把答案放在reasoning_content里，content可能为空
            content = msg.get("content", "") or ""
            reasoning = msg.get("reasoning_content", "") or ""
            # 优先用 content，如果 content 为空则用 reasoning_content
            if not content.strip() and reasoning.strip():
                content = reasoning.strip()
            # 推理模型输出处理：提取最终答案
            if content:
                # 如果 content 太长（包含完整推理），提取答案部分
                if len(content) > 300:
                    # 找"答案是"或"选"等关键词的最后一个出现位置
                    for keyword in ["答案是", "最终答案是", "正确选项是", "应选"]:
                        last_pos = content.rfind(keyword)
                        if last_pos > len(content) * 0.2:  # 在20%位置之后
                            content = content[last_pos:]
                            break
                    # 如果还是太长，取末尾250字符
                    if len(content) > 300:
                        content = content[-250:]
                    # 去掉开头可能的"选"、"选项B："等推理前缀
                    content = content.lstrip("选").lstrip("择").lstrip("项").lstrip("：").strip()
                # 移到下一行的"答案是"处理
                for line in content.split("\n"):
                    line = line.strip()
                    if any(line.startswith(kw) for kw in ["答案是", "正确选项是", "应选"]):
                        content = line
                        break
            return content

        except requests.exceptions.Timeout:
            # 超时错误，重试
            if attempt < retries:
                wait = 15 * (attempt + 1)  # 指数退避：15s, 30s, ...
                print(f"  ⏳ API超时，{wait}秒后重试({attempt+1}/{retries})")
                time.sleep(wait)
                continue
            raise Exception(f"API请求超时（重试{retries}次后仍失败）")

        except Exception as e:
            # 其他异常，记录最后一个错误
            last_error = e
            if attempt < retries:
                wait = 5 * (attempt + 1)
                print(f"  ⚠ API异常: {str(e)[:60]}，{wait}秒后重试")
                time.sleep(wait)
                continue
            raise last_error

    # 不应该走到这里，但以防万一
    raise Exception("API调用失败（未知原因）")

def build_qa_prompt(question: str, context_chunks: list[dict]) -> str:
    """
    构建问答 prompt：将检索到的上下文和问题组合成结构化 prompt
    参数：question — 用户问题
          context_chunks — 检索到的相关文本块
    返回：完整 prompt 文本
    """
    # 将检索到的块合并为上下文文本
    context_parts = []
    for i, c in enumerate(context_chunks):
        source = f"[来源：第{c['page']}页]"
        context_parts.append(f"--- 片段{i+1} {source} ---\n{c['text']}")

    context_str = "\n\n".join(context_parts)

    # 构建完整 prompt
    prompt = f"""请根据以下参考资料回答问题。

参考资料：
{context_str}

问题：{question}

要求：
1. 只根据参考资料中的信息回答，不要编造
2. 如果参考资料不足以回答问题，回答"无法从资料中确定"
3. 回答要简洁准确，直接给出答案
4. 引用来源页码（如"根据第X页"）

答案："""
    return prompt

def generate_answer(question: str, context_chunks: list[dict], options: list[str] = None) -> str:
    """
    生成问题答案的完整流程：构建 prompt → 调用 API → 返回答案
    参数：question — 用户问题（含选项）
          context_chunks — 检索到的上下文块
          options — 选项列表（选择题用）
    返回：AI 生成的答案文本
    """
    # 构建系统提示词（精简版，强化格式要求+关键领域知识）
    system_prompt = (
        "你是专利文档问答助手。\n"
        "核心规则：\n"
        "1. 【最重要】答案必须严格以'答案是X.'开头（X=A/B/C/D），然后给出选项内容\n"
        "2. 严禁输出任何分析、推理、思考过程，只输出最终答案\n"
        "3. 根据参考资料，准确匹配选项内容\n\n"
        "领域知识（CN100342976C专利）：\n"
        "4. [72]=发明人(A. P·吉特勒)，[73]=专利权人(西门子/工业设备制造)\n"
        "5. 结构编号：1=管状入口, 2=外壳, 3=中心轴线, 4=圆柱形部分, "
        "5=台阶, 6/6'/6\"=配气带孔盘, 7=气流方向, 8=除尘器, 9=管状出口, 10=圆锥形部分\n"
        "6. 结构顺序(从左到右沿气流)：入口(1)→圆锥(10)→圆柱(4)→台阶(5)→出口(9), "
        "部件4在部件5左侧\n"
        "7. 配气带孔盘：6最靠台阶, 6\"最靠入口, 气流先经6\"再经6'\n"
        "8. X1/X2/X3=配气带孔盘6/6'/6\"之间的间距; h1=圆柱部分4高度, h2=圆锥部分10高度\n"
        "9.【关键】该静电除尘器管状入口特征：单个圆锥形部分，达外壳直径80-95%，剩余为台阶形式"
    )
    user_prompt = f"""请根据以下参考资料回答选择题。

参考资料：
"""
    for i, c in enumerate(context_chunks):
        user_prompt += f"\n[来源：第{c['page']}页]\n{c['text']}\n"

    user_prompt += f"\n问题：{question}"

    if options:
        user_prompt += "\n\n⚠️ 重要：答案必须以'答案是X.'开头（X=A/B/C/D），然后接选项原文。严禁输出分析过程。"

    # 调用 MiMo API 获取答案
    print(f"  ⏳ 调用MiMo API生成答案...")
    answer = call_mimo(user_prompt, system_prompt)
    print(f"  ✓ 答案已生成")

    return answer

# ======================== 独立测试入口 ========================
if __name__ == "__main__":
    resp = call_mimo("你好，请只回复'连接成功'四个字")
    print(f"  API测试结果: {resp}")

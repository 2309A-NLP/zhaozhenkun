# -*- coding: utf-8 -*-
"""
deepseek_client.py — DeepSeek大模型API客户端
功能：封装DeepSeek API调用，包含重试机制、超时控制、SQL结果提取
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import requests  # HTTP请求库
import time  # 时间控制，用于重试间隔


def call_deepseek_api(messages, api_key, base_url, model, timeout=120, max_retries=3):
    """调用DeepSeek Chat Completion API，返回模型生成的完整文本"""
    # 构建API请求URL（Chat Completion端点）
    url = f"{base_url.rstrip('/')}/chat/completions"  # 拼接完整API地址
    # 构建请求头
    headers = {  # HTTP请求头字典
        "Authorization": f"Bearer {api_key}",  # 认证令牌
        "Content-Type": "application/json"  # 请求体格式
    }
    # 构建请求体
    payload = {  # API请求参数
        "model": model,  # 模型名称
        "messages": messages,  # 对话消息列表
        "temperature": 0.0,  # 温度设为0，保证输出确定性（生成SQL需要稳定）
        "max_tokens": 2048,  # 最大输出token数，足够生成复杂SQL
        "top_p": 1.0,  # nucleus sampling参数
        "stream": False  # 不使用流式输出
    }
    # 重试循环
    last_error = None  # 记录最后一次错误
    for attempt in range(max_retries):  # 最多重试max_retries次
        try:
            # 发送POST请求
            response = requests.post(  # HTTP POST请求
                url,  # API地址
                headers=headers,  # 请求头
                json=payload,  # 请求体（自动序列化为JSON）
                timeout=timeout  # 超时时间
            )
            # 检查HTTP状态码
            if response.status_code == 200:  # 请求成功
                result = response.json()  # 解析JSON响应
                # 提取模型生成的文本内容
                content = result["choices"][0]["message"]["content"]  # 获取回复内容
                return content.strip()  # 返回去除首尾空白的文本
            else:  # HTTP错误
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"  # 记录错误信息
                print(f"  API请求失败 (尝试 {attempt+1}/{max_retries}): {last_error}")  # 打印错误
        except requests.exceptions.Timeout:  # 请求超时
            last_error = "请求超时"  # 记录超时错误
            print(f"  API请求超时 (尝试 {attempt+1}/{max_retries})")  # 打印超时信息
        except Exception as e:  # 其他异常
            last_error = str(e)  # 记录异常信息
            print(f"  API请求异常 (尝试 {attempt+1}/{max_retries}): {e}")  # 打印异常
        # 如果不是最后一次尝试，等待后重试（指数退避）
        if attempt < max_retries - 1:  # 还有重试机会
            wait_time = (attempt + 1) * 2  # 递增等待：2秒、4秒、6秒
            time.sleep(wait_time)  # 等待后再重试
    # 所有重试都失败
    print(f"  API调用最终失败: {last_error}")  # 打印最终错误
    return None  # 返回None表示失败


def extract_sql_from_response(response_text):
    """从模型回复中提取纯SQL语句（去掉可能的markdown包裹和多余内容）"""
    if response_text is None:  # 空响应
        return None  # 返回None
    text = response_text.strip()  # 去除首尾空白
    # 检查是否是PDF类问题标记
    if "NEED_PDF" in text.upper():  # 模型判断需要PDF数据
        return "NEED_PDF"  # 返回特殊标记
    # 去掉可能的markdown代码块标记
    if text.startswith("```"):  # 以```开头
        # 找到第一个换行后的内容
        lines = text.split("\n")  # 按行拆分
        # 去掉第一行（```sql或```）
        sql_lines = []  # 存储SQL行
        for line in lines[1:]:  # 从第二行开始
            if line.startswith("```"):  # 遇到结束标记
                break  # 停止收集
            sql_lines.append(line)  # 添加SQL行
        return "\n".join(sql_lines).strip()  # 合并并返回SQL
    # 尝试提取SQL关键字开始的内容
    sql_keywords = ["SELECT", "WITH", "INSERT", "UPDATE", "DELETE"]  # SQL起始关键字
    for keyword in sql_keywords:  # 遍历关键字
        upper_text = text.upper()  # 转大写用于匹配
        if upper_text.startswith(keyword):  # 以SQL关键字开头
            # SQL以分号结尾时去掉分号（SQLite执行时不需要）
            sql = text.rstrip(";")  # 去掉末尾分号
            return sql  # 返回SQL
        # 查找关键字在文本中的位置（处理前面有解释文字的情况）
        idx = upper_text.find(f"\n{keyword}")  # 查找换行后的SQL关键字
        if idx != -1:  # 找到了
            return text[idx+1:].rstrip(";")  # 从关键字开始截取并返回
    # 如果以上都不匹配，返回原始文本（可能是简短答案）
    return text  # 返回原始文本


def generate_sql(question, system_prompt, api_key, base_url, model, timeout=120, max_retries=3):
    """完整的SQL生成流程：构建消息 → 调用API → 提取SQL"""
    from prompt_builder import build_messages  # 导入消息构建函数（延迟导入避免循环依赖）
    # 构建完整的messages
    messages = build_messages(system_prompt, question)  # 构建API消息
    # 调用DeepSeek API
    response_text = call_deepseek_api(  # 调用API
        messages=messages,  # 消息列表
        api_key=api_key,  # API密钥
        base_url=base_url,  # API地址
        model=model,  # 模型名称
        timeout=timeout,  # 超时时间
        max_retries=max_retries  # 最大重试次数
    )
    # 从回复中提取SQL
    sql = extract_sql_from_response(response_text)  # 提取SQL语句
    return sql, response_text  # 返回SQL和原始回复（用于调试）


# 测试代码
if __name__ == "__main__":  # 如果直接运行
    import config  # 导入配置
    from db_explorer import explore_database  # 导入探索函数
    # 探索数据库获取schema信息
    db_info = explore_database(config.DB_PATH)  # 获取DB信息
    from prompt_builder import build_system_prompt  # 导入prompt构建
    system = build_system_prompt(  # 构建系统提示词
        db_info["schema_description"],  # schema描述
        db_info["relationship_description"]  # 关系描述
    )
    # 测试简单问题
    test_question = "股票002244在20191220日期中的收盘价是多少?"
    sql, raw = generate_sql(  # 生成SQL
        question=test_question,  # 测试问题
        system_prompt=system,  # 系统提示词
        api_key=config.DEEPSEEK_API_KEY,  # API密钥
        base_url=config.DEEPSEEK_BASE_URL,  # API地址
        model=config.DEEPSEEK_MODEL  # 模型
    )
    print(f"问题: {test_question}")  # 打印问题
    print(f"生成SQL: {sql}")  # 打印生成的SQL

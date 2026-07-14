#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
研发 — 搜索工具模块
==============================================================================
功能: 提供 Research Agent 所需的所有外部工具，包括:
      1. Web Search — 通过 SerpAPI 联网搜索
      2. Web Fetch — 获取指定网页文本内容
      3. 备用搜索 — 当 SerpAPI 不可用时的 DuckDuckGo 备用方案
说明: 每个工具返回标准化的结果字典，供 Agent 统一处理。
==============================================================================
"""
import json  # JSON 序列化
import re  # 正则表达式，用于清洗 HTML
import time  # 时间相关
from typing import Dict, List, Optional  # 类型注解
from urllib.parse import quote  # URL 编码

import requests  # HTTP 请求库

from .config import (  # 导入配置
    SERPAPI_API_KEY,  # SerpAPI 密钥
    SERPAPI_BASE_URL,  # SerpAPI 端点
    SEARCH_NUM_RESULTS,  # 搜索结果数量
    REQUEST_TIMEOUT,  # 请求超时
    FETCH_MAX_CHARS,  # 网页获取最大字符数
)


# ============================================================
# 一、Web Search 工具 (SerpAPI)
# ============================================================

def search_serpapi(query: str, num: int = None) -> Dict:  # 通过 SerpAPI 搜索
    """使用 SerpAPI 执行 Google 搜索，返回结构化结果。"""
    if num is None:  # 未指定结果数量
        num = SEARCH_NUM_RESULTS  # 使用默认数量

    if not SERPAPI_API_KEY:  # 未配置 SerpAPI Key
        return {  # 返回错误提示
            "success": False,  # 搜索失败
            "error": "SERPAPI_API_KEY 未配置，请设置环境变量后重试",  # 错误信息
            "results": [],  # 空结果
        }

    params = {  # 构建请求参数
        "api_key": SERPAPI_API_KEY,  # API 密钥
        "q": query,  # 搜索关键词
        "num": num,  # 结果数量
        "engine": "google",  # 搜索引擎
        "hl": "zh-CN",  # 界面语言
        "gl": "cn",  # 地理定位
    }

    try:  # 尝试发送请求
        response = requests.get(  # GET 请求
            SERPAPI_BASE_URL,  # SerpAPI 端点
            params=params,  # 查询参数
            timeout=REQUEST_TIMEOUT,  # 超时设置
        )
        response.raise_for_status()  # 检查 HTTP 错误
        data = response.json()  # 解析 JSON 响应

        # 提取有机搜索结果
        organic_results = data.get("organic_results", [])  # 获取自然搜索结果
        results = []  # 格式化结果列表

        for r in organic_results[:num]:  # 遍历每个结果
            results.append({  # 构建结构化结果
                "title": r.get("title", ""),  # 网页标题
                "url": r.get("link", ""),  # 网页 URL
                "snippet": r.get("snippet", ""),  # 网页摘要
            })

        return {  # 返回搜索结果
            "success": True,  # 搜索成功
            "query": query,  # 搜索关键词
            "results": results,  # 结果列表
            "total_found": len(results),  # 找到的结果数
        }

    except requests.exceptions.Timeout:  # 超时异常
        return {"success": False, "error": f"搜索超时: {query}", "results": []}  # 超时错误
    except Exception as e:  # 其他异常
        return {"success": False, "error": f"搜索失败: {str(e)}", "results": []}  # 返回错误


# ============================================================
# 二、Web Search 备用方案 (DuckDuckGo HTML)
# ============================================================

def search_duckduckgo(query: str, num: int = None) -> Dict:  # DuckDuckGo 备用搜索
    """使用 DuckDuckGo HTML 版搜索（无需 API Key 的备用方案）。"""
    if num is None:  # 未指定结果数量
        num = SEARCH_NUM_RESULTS  # 使用默认数量

    url = "https://html.duckduckgo.com/html/"  # DuckDuckGo HTML 端点
    headers = {  # 请求头（模拟浏览器）
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # User-Agent
    }

    try:  # 尝试发送请求
        response = requests.post(  # POST 请求
            url,  # 搜索端点
            data={"q": query},  # 搜索关键词
            headers=headers,  # 浏览器头
            timeout=REQUEST_TIMEOUT,  # 超时设置
        )
        response.raise_for_status()  # 检查 HTTP 错误
        html = response.text  # 获取 HTML 文本

        # 使用简单正则解析搜索结果
        results = []  # 结果列表
        # 匹配结果链接和摘要
        pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>.*?<a[^>]*class="result__snippet"[^>]*>([^<]*)</a>'  # noqa: E501
        matches = re.findall(pattern, html, re.DOTALL)  # 查找所有匹配

        for match in matches[:num]:  # 遍历匹配结果
            url_str = match[0].strip()  # URL
            title_str = re.sub(r'<[^>]+>', '', match[1]).strip()  # 去除 HTML 标签
            snippet_str = re.sub(r'<[^>]+>', '', match[2]).strip()  # 去除 HTML 标签

            if title_str and url_str:  # 有效结果
                results.append({  # 添加到结果列表
                    "title": title_str,  # 标题
                    "url": url_str,  # URL
                    "snippet": snippet_str,  # 摘要
                })

        return {  # 返回搜索结果
            "success": True,  # 搜索成功
            "query": query,  # 搜索关键词
            "results": results[:num],  # 限制结果数
            "total_found": len(results),  # 找到数
        }

    except Exception as e:  # 异常处理
        return {"success": False, "error": f"DuckDuckGo 搜索失败: {str(e)}", "results": []}  # 返回错误


# ============================================================
# 三、统一搜索接口
# ============================================================

def web_search(query: str, num: int = None) -> Dict:  # 统一搜索接口
    """执行联网搜索，优先使用 SerpAPI，失败时回退到 DuckDuckGo。"""
    # 先尝试 SerpAPI
    if SERPAPI_API_KEY:  # 如果配置了 SerpAPI
        result = search_serpapi(query, num)  # 使用 SerpAPI 搜索
        if result["success"] and result["results"]:  # 搜索成功且有结果
            return result  # 返回结果

    # 回退到 DuckDuckGo
    return search_duckduckgo(query, num)  # 使用备用搜索


# ============================================================
# 四、Web Fetch 工具
# ============================================================

def web_fetch(url: str) -> Dict:  # 获取网页内容
    """获取指定 URL 的网页文本内容，自动清洗 HTML。"""
    headers = {  # 请求头
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # 模拟 Chrome
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",  # 接受的内容类型
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",  # 语言偏好
    }

    try:  # 尝试获取网页
        response = requests.get(  # GET 请求
            url,  # 目标 URL
            headers=headers,  # 浏览器头
            timeout=REQUEST_TIMEOUT,  # 超时设置
            allow_redirects=True,  # 允许重定向
        )
        response.raise_for_status()  # 检查 HTTP 错误

        html = response.text  # 获取 HTML 内容

        # 清洗 HTML，提取纯文本
        text = _clean_html(html)  # 调用 HTML 清洗函数

        # 截断过长内容
        if len(text) > FETCH_MAX_CHARS:  # 内容超过限制
            text = text[:FETCH_MAX_CHARS] + "...(内容已截断)"  # 截断并加提示

        return {  # 返回结果
            "success": True,  # 获取成功
            "url": url,  # 原始 URL
            "content": text,  # 清洗后的文本
            "length": len(text),  # 文本长度
        }

    except requests.exceptions.Timeout:  # 超时
        return {"success": False, "url": url, "error": "网页请求超时", "content": ""}  # 超时错误
    except requests.exceptions.HTTPError as e:  # HTTP 错误
        return {"success": False, "url": url, "error": f"HTTP {e.response.status_code}", "content": ""}  # HTTP 错误
    except Exception as e:  # 其他异常
        return {"success": False, "url": url, "error": str(e), "content": ""}  # 返回错误


def _clean_html(html: str) -> str:  # HTML 文本清洗
    """清洗 HTML 标签，提取纯文本内容。"""
    # 移除 script 和 style 标签及其内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)  # 移除 script
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)  # 移除 style

    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', html)  # 标签替换为空格

    # 解码 HTML 实体
    text = text.replace('&nbsp;', ' ')  # 空格实体
    text = text.replace('&amp;', '&')  # & 符号
    text = text.replace('&lt;', '<')  # < 符号
    text = text.replace('&gt;', '>')  # > 符号
    text = text.replace('&quot;', '"')  # 引号实体
    text = text.replace('&#39;', "'")  # 单引号实体

    # 压缩多余空白
    text = re.sub(r'\s+', ' ', text)  # 多个空白合并为一个空格
    text = re.sub(r'\n\s*\n', '\n', text)  # 多个换行合并

    return text.strip()  # 去除首尾空白


# ============================================================
# 五、搜索结果格式化
# ============================================================

def format_search_results(search_result: Dict) -> str:  # 格式化搜索结果
    """将搜索结果 dict 格式化为 LLM 可读的文本。"""
    if not search_result.get("success"):  # 搜索失败
        return f"搜索失败: {search_result.get('error', '未知错误')}"  # 返回错误信息

    results = search_result.get("results", [])  # 获取结果列表
    if not results:  # 无结果
        return "未找到相关搜索结果。"  # 返回无结果提示

    lines = [f"搜索查询: {search_result.get('query', '')}"]  # 标题行
    lines.append(f"找到 {len(results)} 条结果:\n")  # 结果计数

    for i, r in enumerate(results, 1):  # 遍历结果
        lines.append(f"[{i}] {r.get('title', '')}")  # 标题
        lines.append(f"    URL: {r.get('url', '')}")  # URL
        lines.append(f"    摘要: {r.get('snippet', '')}")  # 摘要
        lines.append("")  # 空行分隔

    return "\n".join(lines)  # 返回格式化文本


# ============================================================
# 六、模块自检
# ============================================================
if __name__ == "__main__":  # 模块自检入口
    print("=" * 50)  # 分隔线
    print("  搜索工具模块 — 自检")  # 标题
    print("=" * 50)  # 分隔线

    # 测试搜索功能
    test_query = "Python programming"  # 测试搜索词
    print(f"  测试搜索: '{test_query}'")  # 打印测试关键词
    result = web_search(test_query, num=3)  # 执行搜索
    print(f"  搜索成功: {result['success']}")  # 打印是否成功
    print(f"  结果数量: {len(result.get('results', []))}")  # 打印结果数
    if result["results"]:  # 有结果
        print(f"  第一条: {result['results'][0]['title']}")  # 打印第一条标题

    # 测试格式化
    formatted = format_search_results(result)  # 格式化结果
    print(f"  格式化文本长度: {len(formatted)} 字符")  # 打印文本长度
    print("  自检完成: OK")  # 自检通过

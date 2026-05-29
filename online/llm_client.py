# -*- coding: utf-8 -*-
"""
ADSD 在线服务 - 大模型客户端模块
负责管理与大语言模型（LLM）API的连接和调用
主要功能：
1. 多端点连接管理：支持多个API密钥和URL的配置
2. 负载均衡：通过加权轮询算法分发请求到多个端点
3. 故障转移：自动跳过不可用的端点，确保服务可用
4. 速率限制：控制API调用频率，避免超限
5. 模拟模式：当所有API连接失败时提供模拟响应
"""
import time  # 导入时间模块，用于计算响应时间和延迟
from openai import OpenAI  # 导入OpenAI客户端库，用于调用大模型API
from typing import Optional, List, Dict  # 导入类型提示，用于函数参数和返回值的类型注解
from online.load_balancer import EndpointConfig, WeightedRoundRobinBalancer  # 从负载均衡模块导入端点配置和加权轮询均衡器
from online.rate_limiter import RateLimiter  # 从限流模块导入限流器


class LLMClient:
    """LLM客户端管理器"""  # 类的文档字符串，说明这个类用于管理大模型客户端

    def __init__(self, api_key: Optional[str] = None):
        """初始化LLM客户端管理器"""  # 构造函数文档
        self.client_pool = {}  # 客户端池，字典结构，存储端点名称到OpenAI客户端的映射
        self.load_balancer = None  # 负载均衡器实例，初始为None
        self.use_mock = True  # 是否使用模拟模式（当API连接失败时自动启用）
        self.api_connected = False  # API是否成功连接的标志
        self.api_error_msg = ""  # API连接失败时的错误信息
        self.last_balancer_endpoint = "mock"  # 最后一次使用的端点名称（默认mock模式）
        self.rate_limiter = RateLimiter()  # 限流器实例，用于控制请求频率

    def init_llm(self, api_key: str, base_url: str, model: str,
                 api_keys: List[str] = None, base_urls: List[str] = None,
                 models: List[str] = None):
        """初始化LLM连接和多端点负载均衡"""  # 初始化方法文档
        print("\n" + "=" * 50)  # 打印分隔线，便于查看输出
        print("初始化 LLM API 连接")  # 打印初始化提示
        print("=" * 50)  # 打印分隔线

        keys = api_keys or [api_key]  # 如果提供了多个API密钥则使用，否则使用单个密钥组成列表
        urls = base_urls or [base_url]  # 如果提供了多个URL则使用，否则使用单个URL组成列表
        models_list = models or [model]  # 如果提供了多个模型则使用，否则使用单个模型组成列表

        endpoints = []  # 创建空列表，用于存储所有端点配置
        for i in range(max(len(keys), len(urls), len(models_list), 1)):  # 遍历最大长度，确保不遗漏任何配置
            key = keys[i] if i < len(keys) and keys else ""  # 获取第i个API密钥，如果不存在则为空字符串
            url = urls[i] if i < len(urls) and urls else base_url  # 获取第i个URL，如果不存在则使用默认值
            m = models_list[i] if i < len(models_list) and models_list else model  # 获取第i个模型名，如果不存在则使用默认值
            if key:  # 只有当API密钥存在时才添加端点
                endpoints.append(EndpointConfig(name=f"llm-{i + 1}", api_key=key, base_url=url, model=m))

        if not endpoints:  # 如果没有配置任何端点
            print("[WARN] 未配置 API Key")  # 打印错误提示
            self.use_mock = True  # 启用模拟模式
            self.api_connected = False  # 标记API未连接
            self.api_error_msg = "未配置 API Key"  # 记录错误信息
            return  # 提前返回

        success_count = 0  # 记录成功连接的端点数量
        for ep in endpoints:  # 遍历所有端点配置
            print(f"\n[INFO] 测试连接 {ep.name}: {ep.base_url}")  # 打印正在测试的端点信息
            print(f"   模型: {ep.model}")  # 打印模型名称
            if self._test_connection(ep.api_key, ep.base_url, ep.model):  # 测试连接是否可用
                try:  # 尝试创建OpenAI客户端
                    self.client_pool[ep.name] = OpenAI(api_key=ep.api_key, base_url=ep.base_url)  # 创建OpenAI客户端并存入池中
                    success_count += 1  # 成功计数加1
                    print(f"   [OK] {ep.name} 连接成功")  # 打印成功信息
                except Exception as e:  # 捕获客户端创建异常
                    print(f"   [WARN] {ep.name} 客户端创建失败: {e}")  # 打印失败信息
            else:  # 连接测试失败
                print(f"   [WARN] {ep.name} 连接失败")  # 打印失败信息

        valid_endpoints = [ep for ep in endpoints if ep.name in self.client_pool]  # 过滤出成功连接的端点
        self.load_balancer = WeightedRoundRobinBalancer(valid_endpoints)  # 创建加权轮询负载均衡器
        self.use_mock = len(self.client_pool) == 0  # 如果客户端池为空则启用模拟模式
        self.api_connected = not self.use_mock  # API连接状态与模拟模式相反

        if self.use_mock:  # 如果是模拟模式
            self.api_error_msg = f"所有API连接失败 (尝试了 {len(endpoints)} 个端点)"  # 记录错误信息
            print("\n[WARN] 所有 API 连接失败，将使用模拟模式")  # 打印警告信息
        else:  # 至少有一个端点连接成功
            print(f"\n[OK] API 连接成功 | 成功连接 {success_count}/{len(endpoints)} 个端点")  # 打印成功统计

        print(f"[OK] LLM 初始化完成 | 模型数: {len(self.client_pool)} | 模拟模式: {self.use_mock}")  # 打印初始化完成信息
        print("=" * 50 + "\n")  # 打印结束分隔线

    def _test_connection(self, api_key: str, base_url: str, model: str) -> bool:
        """测试单个端点的API连接是否可用"""  # 私有方法文档
        try:  # 尝试测试API连接
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=10)  # 创建临时OpenAI客户端（10秒超时）
            response = client.chat.completions.create(  # 发送测试请求
                model=model,  # 指定模型
                messages=[{"role": "user", "content": "测试连接，请回复'ok'"}],  # 测试消息
                max_tokens=5,  # 限制输出长度仅为5个token
                temperature=0  # 温度设为0，使输出确定性最强
            )
            return True  # 未抛出异常则返回True表示连接成功
        except Exception as e:  # 捕获任何异常
            print(f"   API测试失败: {e}")  # 打印失败信息
            return False  # 返回False表示连接失败

    def call_llm(self, prompt: str) -> str:
        """调用大模型API获取响应，支持负载均衡和故障转移"""  # 调用方法文档
        if self.use_mock:  # 如果处于模拟模式
            return "当前处于演示模式。系统已经完成检索，可接入真实大模型获得正式回答。"  # 返回模拟响应

        self.rate_limiter.wait_if_needed()  # 检查限流器，如果需要则等待

        for _ in range(len(self.client_pool)):  # 最多尝试所有端点一次（故障转移循环）
            ep = self.load_balancer.next()  # 从负载均衡器获取下一个端点
            if not ep or ep.name not in self.client_pool:  # 如果端点为None或不在客户端池中
                continue  # 跳过本次循环，尝试下一个端点
            try:  # 尝试调用API
                start_time = time.time()  # 记录请求开始时间
                self.last_balancer_endpoint = ep.name  # 记录本次使用的端点名称
                resp = self.client_pool[ep.name].chat.completions.create(  # 调用大模型API
                    model=ep.model,  # 使用端点的模型
                    messages=[  # 构建消息列表
                        {"role": "system", "content": "你是专业AI助手，根据知识库回答问题。"},  # 系统提示词
                        {"role": "user", "content": prompt}  # 用户问题
                    ],
                    temperature=0.6,  # 温度设为0.6，平衡创造性和确定性
                    max_tokens=900  # 限制最大输出900个token
                )
                response_time = (time.time() - start_time) * 1000  # 计算响应时间（毫秒）
                self.load_balancer.record_result(ep.name, True, response_time)  # 记录成功结果到负载均衡器
                self.load_balancer.release(ep.name)  # 释放端点（通知负载均衡器请求完成）
                return resp.choices[0].message.content or ""  # 返回响应内容，如果为空则返回空字符串
            except Exception as e:  # 捕获API调用异常
                response_time = (time.time() - start_time) * 1000  # 计算响应时间（毫秒）
                self.load_balancer.record_result(ep.name, False, response_time)  # 记录失败结果到负载均衡器
                self.load_balancer.release(ep.name)  # 释放端点
                continue  # 继续尝试下一个端点

        return "模型接口暂时不可用。"  # 所有端点都失败后返回错误提示

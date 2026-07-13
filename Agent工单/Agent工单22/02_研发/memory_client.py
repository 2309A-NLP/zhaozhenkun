#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — mem0 记忆系统客户端
==============================================================================
封装对 mem0 REST API 的 HTTP 调用，提供记忆的增删改查接口。
mem0 API 地址: http://localhost:8888
==============================================================================
"""

import json  # JSON 序列化/反序列化
import os  # 环境变量读取
from typing import Optional, Dict, Any, List  # 类型注解
import requests  # HTTP 请求库

from runtime_env import load_local_env  # 加载项目本地运行配置

load_local_env()


# ============================================================
# 配置常量
# ============================================================
# mem0 REST API 默认地址
MEM0_BASE_URL = os.getenv("MEM0_BASE_URL", "http://localhost:8888")


class MemoryClient:
    """mem0 记忆系统 HTTP 客户端。

    封装 POST/GET/PUT/DELETE /memories 全套 API。
    使用: client = MemoryClient(); client.create("文本", user_id="u1")
    """

    def __init__(self, base_url: str = None):
        """初始化 mem0 客户端。base_url 默认 http://localhost:8888"""
        # 保存并规范化 URL（去掉末尾斜杠）
        self.base_url = (base_url or MEM0_BASE_URL).rstrip("/")
        # 请求超时时间，单位秒
        self.timeout = 30

    def _post(self, path: str, data: Dict) -> Dict[str, Any]:
        """POST 请求封装。"""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=data, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接 mem0 服务: {self.base_url}，请确认服务已启动")

    def _get(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """GET 请求封装。"""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, params=params or {}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接 mem0 服务: {self.base_url}，请确认服务已启动")

    def _put(self, path: str, data: Dict) -> Dict[str, Any]:
        """PUT 请求封装。"""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.put(url, headers={"Content-Type": "application/json"}, json=data, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接 mem0 服务: {self.base_url}，请确认服务已启动")

    def _delete(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """DELETE 请求封装。"""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.delete(url, params=params or {}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接 mem0 服务: {self.base_url}，请确认服务已启动")

    # ----------------------------------------------------------
    # 核心记忆操作
    # ----------------------------------------------------------

    def create(self, text: str = None, messages: List[Dict] = None,
               user_id: str = "default", agent_id: str = None,
               run_id: str = None, metadata: Dict = None) -> Dict[str, Any]:
        """创建一条新记忆，调用 POST /memories。"""
        # 构建请求体
        payload = {
            "user_id": user_id,  # 用户标识
        }
        # 可选字段：只在提供了的时候才加入
        if text:
            payload["text"] = text  # 文本形式的记忆
        if messages:
            payload["messages"] = messages  # 消息列表形式的记忆
        if agent_id:
            payload["agent_id"] = agent_id  # 智能体标识
        if run_id:
            payload["run_id"] = run_id  # 会话标识
        if metadata:
            payload["metadata"] = metadata  # 附加元数据
        # 调用 POST /memories
        return self._post("/memories", payload)

    def list(self, user_id: str = "default", agent_id: str = None,
             run_id: str = None) -> Dict[str, Any]:
        """列出指定用户/智能体的所有记忆，调用 GET /memories。"""
        # 构建查询参数
        params = {"user_id": user_id}
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        # 调用 GET /memories
        return self._get("/memories", params)

    def search(self, query: str, user_id: str = "default",
               agent_id: str = None, run_id: str = None) -> Dict[str, Any]:
        """语义搜索记忆，调用 GET /memories/search。"""
        # 构建查询参数
        params = {"query": query, "user_id": user_id}
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        # 调用 GET /memories/search
        return self._get("/memories/search", params)

    def update(self, memory_id: str, text: str = None,
               metadata: Dict = None) -> Dict[str, Any]:
        """更新一条记忆，调用 PUT /memories/{memory_id}。"""
        # 构建请求体
        payload = {}
        if text:
            payload["text"] = text
        if metadata:
            payload["metadata"] = metadata
        # 调用 PUT /memories/{memory_id}
        return self._put(f"/memories/{memory_id}", payload)

    def delete(self, memory_id: str) -> Dict[str, Any]:
        """删除一条记忆，调用 DELETE /memories/{memory_id}。"""
        # 调用 DELETE /memories/{memory_id}
        return self._delete(f"/memories/{memory_id}")

    def reset(self, user_id: str = "default", agent_id: str = None,
              run_id: str = None) -> Dict[str, Any]:
        """清空指定用户所有记忆（不可逆），调用 DELETE /memories。"""
        # 构建查询参数
        params = {"user_id": user_id}
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        # 调用 DELETE /memories
        return self._delete("/memories", params)

    def health(self) -> bool:
        """检查 mem0 服务是否正常运行，返回 True/False。"""
        try:
            # 调用 health endpoint
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            resp.raise_for_status()
            # 检查返回的 JSON 中 status 是否为 ok
            data = resp.json()
            return data.get("status") == "ok"
        except Exception:
            # 任何异常都返回 False
            return False


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":
    # 创建客户端并测试连接
    client = MemoryClient()
    print(f"mem0 客户端已初始化: {client.base_url}")

    # 测试健康检查
    ok = client.health()
    print(f"  服务状态: {'正常' if ok else '异常 - 请先启动 mem0 服务'}")

    if ok:
        # 测试创建记忆
        test_user = "test_user_001"
        print(f"\n  测试创建记忆 (user_id={test_user})...")
        try:
            result = client.create(
                text="用户叫李四，喜欢爬山和摄影",
                user_id=test_user,
                agent_id="test_agent",
            )
            print(f"  创建成功: {json.dumps(result, ensure_ascii=False, indent=2)[:200]}")
        except Exception as e:
            print(f"  创建失败: {e}")

        # 测试列出记忆
        print(f"\n  测试列出记忆...")
        try:
            result = client.list(user_id=test_user)
            count = len(result.get("results", []))
            print(f"  找到 {count} 条记忆")
        except Exception as e:
            print(f"  列表失败: {e}")

        # 清理测试数据
        print(f"\n  清理测试数据...")
        try:
            client.reset(user_id=test_user)
            print("  清理完成")
        except Exception as e:
            print(f"  清理失败: {e}")

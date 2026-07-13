"""该文件用于封装外部 HTTP JSON 接口访问能力。"""

# 导入系统环境变量模块，用于读取超时配置。
import os
# 导入网络请求库，用于访问外部公开 API。
import requests


# 定义轻量 JSON 客户端，用于统一处理 GET 请求与超时设置。
class HttpJsonClient:
    # 初始化客户端，并创建可复用的会话对象。
    def __init__(self, timeout: int | None = None) -> None:
        # 读取外部传入超时值或环境变量默认值。
        self.timeout = timeout or int(os.getenv("HTTP_TIMEOUT", "20"))
        # 创建请求会话，减少重复建连开销。
        self.session = requests.Session()
        # 设置基础请求头，降低被公共接口拒绝的概率。
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "skills-agent24/1.0",
            }
        )

    # 发送 GET 请求并返回 JSON 数据。
    def get_json(self, url: str, params: dict[str, object]) -> dict[str, object]:
        # 发起带超时的 GET 请求。
        response = self.session.get(url, params=params, timeout=self.timeout)
        # 若响应状态异常，则抛出错误交给上层处理。
        response.raise_for_status()
        # 将响应体解析成 JSON 字典并返回。
        return response.json()

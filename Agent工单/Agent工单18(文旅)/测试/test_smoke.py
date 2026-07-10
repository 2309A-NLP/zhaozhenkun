"""工单18：接口冒烟测试脚本，负责验证健康检查、会话、文本与行为接口。"""
# 工单18：导入标准JSON模块，便于格式化输出测试结果。
import json
# 工单18：导入urllib模块，避免额外依赖也能发HTTP请求。
from urllib import request

# 工单18：定义基础服务地址，默认指向本地5050端口。
BASE_URL = "http://127.0.0.1:5050"

# 工单18：封装GET请求，简化测试脚本重复代码。
def get_json(url: str) -> dict:
    # 工单18：发起GET请求并解析JSON响应。
    with request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))

# 工单18：封装POST JSON请求，便于调用后端接口。
def post_json(url: str, payload: dict) -> dict:
    # 工单18：把请求体转成UTF-8字节串。
    data = json.dumps(payload).encode("utf-8")
    # 工单18：构造带JSON头的请求对象。
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    # 工单18：发起POST请求并解析结果。
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

# 工单18：按顺序执行核心接口测试。
def main() -> None:
    # 工单18：先检查服务是否存活。
    ping = get_json(f"{BASE_URL}/ping")
    # 工单18：创建测试会话。
    session = post_json(f"{BASE_URL}/api/session/create", {})
    # 工单18：调用文本问答接口。
    text_result = post_json(
        f"{BASE_URL}/api/chat/text",
        {"session_id": session["session_id"], "question": "请介绍主教学楼", "language": "zh"},
    )
    # 工单18：调用行为互动接口。
    behavior_result = post_json(
        f"{BASE_URL}/api/chat/behavior",
        {"session_id": session["session_id"], "behavior": "wave", "language": "zh"},
    )
    # 工单18：统一打印结果，便于用户查看。
    print(json.dumps({"ping": ping, "session": session, "text": text_result, "behavior": behavior_result}, ensure_ascii=False, indent=2))

# 工单18：当脚本被直接执行时，运行主测试流程。
if __name__ == "__main__":
    main()

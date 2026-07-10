"""工单18：实时识别接口测试脚本，负责验证后端对关键点JSON的行为识别结果。"""
# 工单18：导入JSON模块，便于组装和解析HTTP请求体。
import json
# 工单18：导入urllib请求工具，避免额外第三方依赖。
from urllib import request

# 工单18：定义本地服务地址，默认走5050端口。
BASE_URL = "http://127.0.0.1:5050"

# 工单18：封装POST JSON请求函数。
def post_json(url: str, payload: dict) -> dict:
    # 工单18：把请求体转成JSON字节串。
    data = json.dumps(payload).encode("utf-8")
    # 工单18：构造标准JSON请求对象。
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    # 工单18：发起请求并解析返回结果。
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

# 工单18：执行实时行为识别测试。
def main() -> None:
    # 工单18：先创建会话，保证实时互动结果能进入上下文。
    session = post_json(f"{BASE_URL}/api/session/create", {})
    # 工单18：构造一个明显的挥手关键点样本。
    payload = {
        "session_id": session["session_id"],
        "language": "zh",
        "pose": {
            "left_shoulder": {"x": 0.40, "y": 0.55, "visibility": 0.99},
            "right_shoulder": {"x": 0.60, "y": 0.55, "visibility": 0.99},
            "left_wrist": {"x": 0.15, "y": 0.22, "visibility": 0.99},
            "right_wrist": {"x": 0.78, "y": 0.70, "visibility": 0.99},
        },
        "hands": [],
        "face": {},
    }
    # 工单18：请求实时行为识别接口。
    result = post_json(f"{BASE_URL}/api/realtime/behavior", payload)
    # 工单18：打印结果，便于用户检查识别是否成功。
    print(json.dumps(result, ensure_ascii=False, indent=2))

# 工单18：当脚本直接运行时，执行主测试逻辑。
if __name__ == "__main__":
    main()

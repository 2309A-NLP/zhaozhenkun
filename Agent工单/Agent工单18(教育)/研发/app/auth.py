# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""auth.py - 工单18智能助教的本地鉴权与用户脱敏模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import base64  # 工单18：导入 Base64 编解码模块。
import hashlib  # 工单18：导入哈希模块。
import hmac  # 工单18：导入 HMAC 签名模块。
import json  # 工单18：导入 JSON 处理模块。

from fastapi import Header  # 工单18：导入请求头依赖工具。
from fastapi import HTTPException  # 工单18：导入异常类。
from fastapi import status  # 工单18：导入状态码枚举。

from app.config import APP_SECRET  # 工单18：导入应用签名密钥。
from app.state import load_state  # 工单18：导入状态读取函数。


def public_user(user: dict) -> dict:  # 工单18：返回不含密码的用户公开信息。
    return {"user_id": user["user_id"], "username": user["username"], "role": user["role"], "display_name": user["display_name"]}  # 工单18：输出前端真正需要的用户字段。


def find_user(username: str, password: str) -> dict | None:  # 工单18：按用户名和密码查找用户。
    for user in load_state()["users"]:  # 工单18：遍历全部内置用户。
        if user["username"] == username and user["password"] == password:  # 工单18：匹配用户名密码组合。
            return user  # 工单18：返回命中的完整用户对象。
    return None  # 工单18：未命中时返回空值。


def _sign(payload_text: str) -> str:  # 工单18：对载荷文本生成签名。
    digest = hmac.new(APP_SECRET.encode("utf-8"), payload_text.encode("utf-8"), hashlib.sha256).hexdigest()  # 工单18：计算 HMAC-SHA256 签名。
    return digest  # 工单18：返回十六进制签名字符串。


def issue_token(user: dict) -> str:  # 工单18：为登录用户签发访问令牌。
    payload = {"user_id": user["user_id"], "username": user["username"], "role": user["role"]}  # 工单18：构造需要编码的用户载荷。
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))  # 工单18：序列化令牌载荷。
    signature = _sign(payload_text)  # 工单18：计算当前载荷签名。
    token_text = json.dumps({"payload": payload, "signature": signature}, ensure_ascii=False, separators=(",", ":"))  # 工单18：构造完整令牌内容。
    return base64.urlsafe_b64encode(token_text.encode("utf-8")).decode("utf-8")  # 工单18：返回 URL 安全的令牌字符串。


def parse_token(token: str) -> dict:  # 工单18：解析并校验访问令牌。
    try:  # 工单18：开始执行令牌解析流程。
        raw_text = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")  # 工单18：执行 Base64 解码。
        token_data = json.loads(raw_text)  # 工单18：解析解码后的 JSON 内容。
        payload = token_data["payload"]  # 工单18：读取令牌载荷内容。
        payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))  # 工单18：重新序列化载荷以便验签。
        if not hmac.compare_digest(token_data["signature"], _sign(payload_text)):  # 工单18：安全比较令牌签名与实时计算值。
            raise ValueError("invalid signature")  # 工单18：签名不匹配时抛出异常。
        return payload  # 工单18：校验通过后返回用户载荷。
    except Exception as exc:  # 工单18：捕获全部解析异常。
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效登录状态") from exc  # 工单18：统一抛出未授权异常。


def get_user_by_id(user_id: str) -> dict | None:  # 工单18：按用户编号查找用户信息。
    for user in load_state()["users"]:  # 工单18：遍历全部用户数据。
        if user["user_id"] == user_id:  # 工单18：匹配用户编号。
            return user  # 工单18：返回命中的用户对象。
    return None  # 工单18：未命中时返回空值。


def get_current_user(authorization: str = Header(default="")) -> dict:  # 工单18：从请求头解析当前登录用户。
    if not authorization.startswith("Bearer "):  # 工单18：校验 Bearer 令牌前缀。
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")  # 工单18：缺失登录态时抛出异常。
    payload = parse_token(authorization.split(" ", 1)[1])  # 工单18：解析请求头中的令牌主体。
    user = get_user_by_id(payload["user_id"])  # 工单18：根据令牌用户编号查询完整用户。
    if not user:  # 工单18：校验令牌用户是否仍然存在。
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")  # 工单18：不存在时抛出异常。
    return user  # 工单18：返回完整用户对象供服务层使用。

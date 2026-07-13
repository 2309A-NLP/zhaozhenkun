# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""write_secrets.py - 工单18双模型密钥本地落盘脚本。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import json  # 工单18：导入 JSON 模块。
from pathlib import Path  # 工单18：导入路径处理类。

BASE_DIR = Path(__file__).resolve().parents[1]  # 工单18：定位项目根目录。
SECRET_FILE = BASE_DIR / "部署" / "model_secrets.local.json"  # 工单18：定义本地密钥文件路径。


def main() -> None:  # 工单18：写入用户提供的双模型配置。
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)  # 工单18：确保部署目录存在。
    payload = {  # 工单18：构造双模型配置内容。
        "deepseek": {"base_url": "https://api.deepseek.com", "api_key": "sk-70c456e35e914eb88fa233a04856bcf4", "model": "deepseek-chat"},  # 工单18：写入 DeepSeek 配置。
        "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "sk-cb2873cdfdb543d1a8a05f3ffda4620c", "model": "qwen-plus"},  # 工单18：写入千问配置。
    }  # 工单18：结束模型配置构造。
    SECRET_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")  # 工单18：持久化配置文件。
    print(f"已写入：{SECRET_FILE}")  # 工单18：输出写入结果。


if __name__ == "__main__":  # 工单18：判断是否直接执行脚本。
    main()  # 工单18：执行密钥文件写入逻辑。

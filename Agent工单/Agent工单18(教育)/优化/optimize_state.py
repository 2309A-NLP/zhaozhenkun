# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""optimize_state.py - 工单18状态数据优化与清洗脚本。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import json  # 工单18：导入 JSON 模块。
from pathlib import Path  # 工单18：导入路径处理类。

STATE_FILE = Path(__file__).resolve().parents[1] / "研发" / "data" / "state.json"  # 工单18：定义状态文件路径。


def main() -> None:  # 工单18：对状态文件执行轻量优化。
    if not STATE_FILE.exists():  # 工单18：在状态文件缺失时直接结束。
        print("state.json 不存在，无需优化")  # 工单18：输出提示信息。
        return  # 工单18：提前结束脚本。
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))  # 工单18：读取状态文件内容。
    for resource in state.get("resources", []):  # 工单18：遍历全部资源对象。
        resource["content_text"] = resource.get("content_text", "").strip()  # 工单18：清除正文首尾空白。
        resource["tags"] = list(dict.fromkeys(resource.get("tags", [])))  # 工单18：对标签执行去重。
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")  # 工单18：回写优化后的状态文件。
    print("状态文件优化完成")  # 工单18：输出优化完成提示。


if __name__ == "__main__":  # 工单18：判断是否直接执行脚本。
    main()  # 工单18：执行状态优化逻辑。

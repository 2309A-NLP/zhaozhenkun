# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""requirements_export.py - 工单18设计说明输出脚本。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from pathlib import Path  # 工单18：导入路径处理类。

BASE_DIR = Path(__file__).resolve().parents[1]  # 工单18：定位项目根目录。
OUTPUT_FILE = BASE_DIR / "设计" / "system_design.txt"  # 工单18：定义设计说明输出路径。


def main() -> None:  # 工单18：生成技术设计说明文本。
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)  # 工单18：确保设计目录存在。
    lines = [  # 工单18：构造设计说明文本。
        "工单18 智能助教系统设计",  # 工单18：写入设计标题。
        "1. 用户角色：教师、学生。",  # 工单18：写入角色定义。
        "2. 知识库：公共知识库 + 用户私有知识库。",  # 工单18：写入知识库设计。
        "3. 检索链路：文件解析 -> 切块 -> 公私库混合检索 -> 简单重排。",  # 工单18：写入检索设计。
        "4. 模型接入：DeepSeek / 千问，前端按钮切换。",  # 工单18：写入模型设计。
        "5. 输出：答案 + 引用 + 多模态标签。",  # 工单18：写入输出设计。
    ]  # 工单18：结束设计说明构造。
    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")  # 工单18：写入设计说明文件。
    print(f"已输出：{OUTPUT_FILE}")  # 工单18：输出完成提示。


if __name__ == "__main__":  # 工单18：判断是否直接执行脚本。
    main()  # 工单18：执行设计说明生成逻辑。

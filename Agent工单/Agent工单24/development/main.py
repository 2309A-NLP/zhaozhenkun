"""该文件用于提供命令行入口，便于本地快速体验智能体问答。"""

# 导入参数解析模块，用于处理命令行输入。
import argparse
# 导入 JSON 模块，用于美化打印响应结果。
import json

# 导入智能体服务，用于执行问答流程。
from development.services.agent_service import AgentService


# 定义命令行主函数，用于启动一次问答流程。
def main() -> None:
    # 初始化命令行参数解析器。
    parser = argparse.ArgumentParser(description="运行 SKILLS 化智能体示例。")
    # 注册用户问题参数。
    parser.add_argument("query", help="用户输入的问题内容")
    # 注册会话编号参数。
    parser.add_argument("--session-id", default="default", help="会话编号")
    # 注册模型提供方参数，支持 deepseek 或 qwen。
    parser.add_argument("--provider", default="deepseek", help="模型提供方名称")
    # 解析命令行参数。
    args = parser.parse_args()
    # 初始化智能体服务对象。
    service = AgentService(provider_name=args.provider)
    # 执行单轮问答。
    response = service.handle(query=args.query, session_id=args.session_id)
    # 以格式化 JSON 输出结果。
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


# 在脚本直接运行时启动主函数。
if __name__ == "__main__":
    # 调用命令行主入口。
    main()

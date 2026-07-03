"""
================================================================================
文件名:   tingwu_client.py
功能:     通义听悟客户端兼容性重导出模块
          —— 汇总 tingwu_core / tingwu_ws / tingwu_postprocess 三个子模块
             对外暴露统一的 TingwuClient 类和 get_tingwu_client() 工厂函数
所属项目: 医疗智能体-Agent 数字人项目

内部结构（重构后，2024-07-03）:
  tingwu_core.py         —— TingwuClient 核心（鉴权、实时 ASR 入口、单例）
  tingwu_ws.py           —— DashScope WebSocket 实时 ASR 协议处理
  tingwu_postprocess.py  —— 离线转写、转录分析、翻译、摘要解析

本模块用途:
  保持向后兼容 —— 旧代码中的
    from services.tingwu_client import TingwuClient, get_tingwu_client
  继续有效，无需修改任何调用方代码。

导出:
  TingwuClient        —— 通义听悟客户端（完整功能）
  get_tingwu_client() —— 全局单例工厂
  SUMMARY_PROMPT      —— 会议纪要 System Prompt（按需使用）
  _parse_summary_result() —— DeepSeek 输出解析器（按需使用）
================================================================================
"""
# 从核心模块导入
from services.tingwu_core import (
    TingwuClient,                                                   # 完整客户端类
    get_tingwu_client,                                              # 单例工厂函数
)

# 从后处理模块导入工具函数和常量（可选导出，供外部直接使用）
from services.tingwu_postprocess import (
    SUMMARY_PROMPT,                                                 # DeepSeek 会议纪要 Prompt
    _parse_summary_result,                                          # 结构化输出解析器
    process_transcript,                                             # DeepSeek 转录分析
    translate_text,                                                 # DeepSeek 翻译
    create_task,                                                    # 离线转写任务创建
    get_task_info,                                                  # 离线转写任务查询
)

# 从 WebSocket 模块导入协议实现（内部使用，不推荐外部直接调用）
from services.tingwu_ws import (
    _dashscope_ws_asr,                                              # WebSocket 实时 ASR 协议
)

# ================================================================
# 所有对外接口一览:
#   TingwuClient          —— 通义听悟客户端类（推荐使用 get_tingwu_client() 获取单例）
#   get_tingwu_client()   —— 单例工厂函数
#   SUMMARY_PROMPT        —— 会议纪要分析 System Prompt 模板
#   _parse_summary_result —— 解析 DeepSeek 输出为结构化数据
#   process_transcript    —— 独立函数: DeepSeek 转录分析
#   translate_text        —— 独立函数: DeepSeek 翻译
#   create_task           —— 独立函数: 创建离线转写任务
#   get_task_info         —— 独立函数: 查询离线转写任务状态
#   _dashscope_ws_asr     —— 内部函数: WebSocket 实时 ASR 协议处理
# ================================================================

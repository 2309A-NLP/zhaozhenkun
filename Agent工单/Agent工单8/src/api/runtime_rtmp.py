"""
src/api/runtime_rtmp.py - RTMP 运行时控制辅助
功能: 封装 RTMP 启停与状态判断，避免路由文件承载过多业务细节。
说明: 当前仍使用全局 pipeline 输出对象，不扩展为多会话多实例管理。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""


def start_pipeline_rtmp(pipeline, rtmp_url: str) -> tuple[str, str]:
    """启动全局 RTMP 推流并返回状态与最终 URL。"""
    rtmp = getattr(pipeline, "rtmp", None)
    if rtmp is None:
        raise RuntimeError("RTMP 输出对象未初始化")

    if rtmp.is_active:
        rtmp.stop()

    rtmp.rtmp_url = rtmp_url
    rtmp.start()
    status = "pushing" if rtmp.is_active else "error"
    return status, rtmp.rtmp_url


def stop_pipeline_rtmp(pipeline) -> str:
    """停止全局 RTMP 推流并返回当前状态。"""
    rtmp = getattr(pipeline, "rtmp", None)
    if rtmp is None:
        raise RuntimeError("RTMP 输出对象未初始化")

    if rtmp.is_active:
        rtmp.stop()
    return "stopped"

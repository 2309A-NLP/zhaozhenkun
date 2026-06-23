# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：Gradio Web 界面入口模块 — 文生图智能体
==============================================================================
本文件定义 Gradio Web UI 并启动服务，包含 5 个功能 Tab：
  1. 🔄 面部旋转 + 扩图（千问 Qwen-Image-Edit-Max）
  2. 🖼️ 单独扩图
  3. 🤖 千问AI编辑（自由编辑）
  4. 🖥️ 系统状态
  5. 📖 使用说明

所有回调函数在 callbacks.py 中实现，所有输出统一保存到 output/face_rotation/

使用方法: python app.py [--port PORT]
浏览器打开 http://127.0.0.1:PORT 即可使用。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os  # 路径处理
import sys  # 系统退出
import argparse  # 命令行参数
import logging  # 日志

# 添加项目根目录到 path，确保导入正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import setup_logging  # 日志初始化

# 回调函数导入
from callbacks import detect_face, generate_rotation  # 面部旋转 Tab
from callbacks_qwen import outpaint_single, qwen_edit_images, get_status  # 千问编辑/扩图/状态

logger = logging.getLogger(__name__)  # 模块日志器


def _find_free_port(start_port: int = 7890, max_attempts: int = 10) -> int:
    """从 start_port 开始查找第一个可用 TCP 端口"""
    import socket
    for offset in range(max_attempts):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))  # 尝试绑定
                return port
            except OSError:
                continue  # 端口被占用，尝试下一个
    raise OSError(f"No free port in range {start_port}-{start_port + max_attempts - 1}")


def create_ui():
    """构建 Gradio Web UI（5个Tab）"""
    with gr.Blocks(title="文生图智能体 - 面部旋转 + 扩图") as demo:

        # 页面标题
        gr.Markdown("""
        # 🎨 文生图智能体
        **工单：NLP-Agent 数字人项目 — 文生图智能体任务**
        """)

        with gr.Tabs():
            # ================================================================
            # Tab 1: 面部旋转 + 扩图（简化版，千问模型）
            # ================================================================
            with gr.Tab("🔄 面部旋转 + 扩图"):
                with gr.Row():
                    # 左侧：输入区
                    with gr.Column(scale=1):
                        inp = gr.Image(label="📤 上传面部照片", type="numpy", height=280)
                        det_btn = gr.Button("🔍 1. 检测人脸", variant="secondary")
                        info = gr.Textbox(label="检测结果", lines=6, interactive=False)
                        gen_btn = gr.Button("🎨 2. 生成旋转 + 扩图", variant="primary", size="lg")

                    # 右侧：输出区
                    with gr.Column(scale=2):
                        gr.Markdown("### 🔄 旋转结果（千问 AI）")
                        with gr.Row():
                            o1 = gr.Image(label="⬅️ 左转", height=240)
                            o2 = gr.Image(label="➡️ 右转", height=240)
                        o3 = gr.Image(label="😊 端正", height=240)

                        gr.Markdown("### 🖼️ 扩图结果")
                        with gr.Row():
                            op1 = gr.Image(label="扩图-左转", height=240)
                            op2 = gr.Image(label="扩图-右转", height=240)
                        op3 = gr.Image(label="扩图-端正", height=240)

                        st = gr.Textbox(label="📋 状态", lines=4, interactive=False)

                # 绑定事件
                det_btn.click(detect_face, [inp], [info])
                gen_btn.click(generate_rotation, [inp],
                              [o1, o2, o3, op1, op2, op3, st])

            # ================================================================
            # Tab 2: 单独扩图
            # ================================================================
            with gr.Tab("🖼️ 单独扩图"):
                with gr.Row():
                    with gr.Column(scale=1):
                        inp2 = gr.Image(label="上传图像", type="numpy", height=280)
                        sl = gr.Slider(1.1, 2.0, 1.5, 0.1, label="扩展比例")
                        ob = gr.Button("🖼️ 执行扩图", variant="primary")
                    with gr.Column(scale=2):
                        oo = gr.Image(label="扩图结果", height=400)
                        os2 = gr.Textbox(label="状态", lines=4, interactive=False)
                ob.click(outpaint_single, [inp2, sl], [oo, os2])

            # ================================================================
            # Tab 3: 千问AI编辑
            # ================================================================
            with gr.Tab("🤖 千问AI编辑"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📤 输入图像 (1-3张)")
                        qw_img1 = gr.Image(label="图1 (主图)", type="numpy", height=180)
                        qw_img2 = gr.Image(label="图2 (可选参考图)", type="numpy", height=180)
                        qw_img3 = gr.Image(label="图3 (可选参考图)", type="numpy", height=180)

                        gr.Markdown("### ✏️ 编辑指令")
                        qw_prompt = gr.Textbox(
                            label="编辑指令",
                            placeholder="例如：将背景替换为海滩日落、转换为油画风格、将图1衣服换成图2的...",
                            lines=4,
                        )

                        gr.Markdown("### ⚙️ 生成参数")
                        with gr.Row():
                            qw_n = gr.Slider(1, 6, 1, 1, label="输出数量")
                            qw_extend = gr.Checkbox(label="智能扩展提示词", value=True)
                        qw_size = gr.Dropdown(
                            choices=["1024*1024", "1280*720", "720*1280", "2048*2048"],
                            value="1024*1024", label="输出分辨率",
                        )
                        qw_negative = gr.Textbox(
                            label="反向提示词 (不想出现的内容)",
                            placeholder="例如：模糊、低质量、变形...", lines=2,
                        )
                        qw_btn = gr.Button("🎨 AI 编辑", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        gr.Markdown("### 🖼️ 生成结果")
                        with gr.Row():
                            qw_out1 = gr.Image(label="结果 1", height=240)
                            qw_out2 = gr.Image(label="结果 2", height=240)
                        with gr.Row():
                            qw_out3 = gr.Image(label="结果 3", height=240)
                            qw_out4 = gr.Image(label="结果 4", height=240)
                        with gr.Row():
                            qw_out5 = gr.Image(label="结果 5", height=240)
                            qw_out6 = gr.Image(label="结果 6", height=240)
                        qw_status = gr.Textbox(label="📋 状态", lines=4, interactive=False)

                qw_btn.click(
                    qwen_edit_images,
                    [qw_img1, qw_img2, qw_img3, qw_prompt, qw_n, qw_size, qw_negative, qw_extend],
                    [qw_out1, qw_out2, qw_out3, qw_out4, qw_out5, qw_out6, qw_status],
                )

            # ================================================================
            # Tab 4: 系统状态
            # ================================================================
            with gr.Tab("🖥️ 系统状态"):
                st_btn = gr.Button("🔄 检查状态")
                st_text = gr.Markdown("点击按钮查看各模块运行状态")
                st_btn.click(get_status, [], [st_text])

            # ================================================================
            # Tab 5: 使用说明
            # ================================================================
            with gr.Tab("📖 使用说明"):
                gr.Markdown("""
                ## 🚀 快速开始

                1. **上传照片** → **检测人脸** → **生成旋转+扩图**
                2. 所有结果保存在 `output/face_rotation/` 目录
                3. 千问AI编辑 Tab 支持自由编辑（换背景、换风格、多图融合等）

                ## 🤖 模型说明
                - **面部旋转**: 千问 Qwen-Image-Edit-Max
                - **扩图**: 千问 Qwen-Image-Edit-Max
                - **人脸检测**: MediaPipe
                - **AI 自由编辑**: 千问 Qwen-Image-Edit-Max

                ## ⚙️ 启动选项
                ```bash
                python app.py              # 默认端口 7890
                python app.py --port 8888  # 指定端口
                ```
                """)

    return demo


def main():
    """主入口：解析参数、启动 Gradio Web 服务"""
    parser = argparse.ArgumentParser(description="文生图智能体 Web 界面")
    parser.add_argument("--port", type=int, default=None,
                        help="Web 服务端口（默认自动查找，从 7890 开始）")
    parser.add_argument("--share", action="store_true", help="创建公网分享链接")
    args = parser.parse_args()

    setup_logging()  # 初始化日志

    # 清理 Windows 代理环境变量（避免 Gradio 6.0 502 问题）
    for key in list(os.environ.keys()):
        if key.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                           "http_proxy", "https_proxy", "all_proxy"):
            logger.info(f"移除代理环境变量: {key}={os.environ.pop(key)}")
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,.local")

    # 自动查找空闲端口
    start_port = args.port or 7890
    port = _find_free_port(start_port)

    logger.info("=== 文生图智能体 Web 界面启动 ===")
    logger.info(f"本界面地址: http://127.0.0.1:{port}")
    if port != start_port:
        logger.warning(f"端口 {start_port} 已被占用，自动使用端口 {port}")

    demo = create_ui()  # 构建 UI

    # 启动 Gradio（兼容 6.0 Windows localhost 502 问题）
    try:
        demo.launch(
            server_name="127.0.0.1",
            server_port=port,
            share=args.share,
            theme=gr.themes.Soft(),
        )
    except Exception as e:
        error_msg = str(e)
        if "startup-events" in error_msg and "502" in error_msg:
            logger.warning("Gradio 6.0 启动自检失败，切换到 FastAPI 直连模式...")
            _launch_with_uvicorn(demo, port, args.share)  # 回退方案
        else:
            raise


def _launch_with_uvicorn(demo, port: int, share: bool):
    """Gradio 启动失败时的回退方案：用 uvicorn 直接启动底层 FastAPI"""
    import uvicorn  # ASGI 服务器

    # 确保 Gradio app 已构建
    if not hasattr(demo, "app"):
        demo.launch(server_name="127.0.0.1", server_port=port,
                    prevent_thread_lock=True, show_error=False)
        import time
        time.sleep(1)

    logger.info(f"✅ 服务启动在: http://127.0.0.1:{port}")
    uvicorn.run(demo.app, host="127.0.0.1", port=port, log_level="warning")


# 兼容 gradio 旧版本：延迟导入在文件末尾
try:
    import gradio as gr
except ImportError:
    print("请先安装 gradio: pip install gradio")
    sys.exit(1)

if __name__ == "__main__":
    main()

"""
src/utils/ffmpeg_utils.py - FFmpeg 辅助工具
功能: 封装 FFmpeg 子进程调用，用于 RTMP 推流和视频编码。
      对应工单需求: "支持 RTMP 和 WebRTC 协议，确保低延迟通信"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import subprocess
import logging

logger = logging.getLogger(__name__)


def build_rtmp_command(
    rtmp_url: str,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    bitrate: str = "4000k",
    encoder: str = "libx264",
    preset: str = "ultrafast",
    sample_rate: int = 16000,
) -> list:
    """构建FFmpeg RTMP推流命令，视频从stdin读取BGR原始帧。"""
    cmd = [
        "ffmpeg", "-loglevel", "error",
        # 视频输入: stdin管道, BGR rawvideo格式
        "-f", "rawvideo", "-pixel_format", "bgr24",
        "-video_size", f"{width}x{height}",
        "-framerate", str(fps), "-i", "pipe:0",
        # 视频编码: 低延迟zerolatency调优
        "-c:v", encoder, "-preset", preset,
        "-tune", "zerolatency", "-b:v", bitrate,
        "-pix_fmt", "yuv420p",
        # 音频编码: AAC
        "-c:a", "aac", "-b:a", "128k",
        "-ar", str(sample_rate), "-ac", "1",
        # 输出: FLV封装RTMP推流
        "-f", "flv", rtmp_url,
    ]
    return cmd


class RTMPStreamer:
    """RTMP推流器，封装FFmpeg子进程，对应工单流媒体输出需求。"""

    def __init__(self, rtmp_url: str, width: int = 1280, height: int = 720,
                 fps: int = 25, bitrate: str = "4000k"):
        self.rtmp_url = rtmp_url
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.process = None

    def start(self) -> None:
        """启动FFmpeg子进程开始推流。"""
        cmd = build_rtmp_command(
            self.rtmp_url, self.width, self.height,
            self.fps, self.bitrate
        )
        logger.info(f"启动RTMP推流: {self.rtmp_url}")
        self.process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    def send_frame(self, frame_bytes: bytes) -> None:
        """发送一帧BGR视频数据到FFmpeg stdin。"""
        if self.process is None or self.process.stdin is None:
            return
        try:
            self.process.stdin.write(frame_bytes)
            self.process.stdin.flush()
        except BrokenPipeError:
            logger.error("FFmpeg管道断开")
            self.stop()

    def stop(self) -> None:
        """安全停止推流。"""
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

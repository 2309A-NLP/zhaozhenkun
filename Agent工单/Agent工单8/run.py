#!/usr/bin/env python3
"""
run.py - 实时数字人交互系统 主入口(音视频同步版本)
功能: 加载配置→初始化模块→启动Web服务。音视频同步: 同一段TTS音频驱动口型+输出声音。
用法:
  python run.py                    # 启动Web服务
  python run.py --offline --input in.wav --output out.mp4  # 离线处理
  python run.py --check            # 环境检查
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import sys, os, argparse, logging, numpy as np, asyncio

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(PROJECT_ROOT, "config.yaml")
sys.path.insert(0, PROJECT_ROOT)

# 加载 .env 文件 (如果存在)
try:
    from dotenv import load_dotenv
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logging.getLogger(__name__).info(f"已加载 .env: {env_path}")
    else:
        load_dotenv()  # 尝试默认位置
except ImportError:
    pass  # python-dotenv 可选依赖

from src.utils.logger import setup_logging, get_logger
from src.core.config import load_config, AppConfig
from src.core.session import SessionManager
from src.asr.whisper_asr import WhisperASR
from src.llm.dialogue import create_llm_client
from src.tts.tts_engine import create_tts_engine
from src.audio.feature_extractor import MelFeatureExtractor
from src.lipsync.lipsync_factory import create_lipsync_engine
from src.video.compositor import FrameCompositor
from src.video.face_detector import FaceDetector
from src.video.idle_video import IdleVideoPlayer
from src.core.barge_in import BargeInDetector, InterruptHandler
from src.core.pipeline import PipelineOrchestrator
from src.output.webrtc_output import WebRTCOutput
from src.output.rtmp_output import RTMPOutput
from src.core.config_validator import validate_config

logger = get_logger(__name__)


def check_environment(config: AppConfig) -> bool:
    """检查环境: GPU、API Key、FFmpeg、Wav2Lip权重。使用ConfigValidator。"""
    logger.info("=" * 50)
    logger.info("  环境检查")
    logger.info("=" * 50)

    all_ok = validate_config(config)

    # 额外打印快速摘要
    import torch
    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        logger.info(f"  GPU: {gpu} ({vram:.1f} GB)")
    else:
        logger.warning("  GPU: 不可用")
    import shutil
    logger.info(f"  FFmpeg: {'OK' if shutil.which('ffmpeg') else '未找到'}")
    logger.info(f"  LLM后端={config.llm.provider}, model={config.llm.model}")
    logger.info(f"  ASR={config.asr.model}, TTS={config.tts.default_backend}")
    logger.info(f"  LipSync模型={config.lipsync.model}")
    logger.info("=" * 50)
    return all_ok


def init_modules(config: AppConfig):
    """
    初始化所有模块: ASR→LLM→TTS→LipSync→Video→Output→Pipeline。
    使用工厂函数创建LLM/TTS/LipSync实例，支持多后端切换。
    """
    logger.info("初始化模块...")

    session_mgr = SessionManager(
        max_concurrent=config.sessions.max_concurrent,
        timeout_s=config.sessions.timeout_s)
    asr_engine = WhisperASR(model_name=config.asr.model,
                            language=config.asr.language,
                            device=config.asr.device)

    # LLM客户端 (工厂函数 — 支持 deepseek/ollama/vllm/openai)
    llm_client = create_llm_client(config)

    tts_engine = create_tts_engine(config)

    # LipSync引擎 (工厂函数 — 支持 wav2lip/musetalk/ernerf)
    lipsync_engine = create_lipsync_engine(config)

    compositor = FrameCompositor(output_width=config.pipeline.video_width,
                                 output_height=config.pipeline.video_height,
                                 background_path=config.video.background)
    bargein_detector = BargeInDetector(
        energy_threshold=config.barge_in.energy_threshold,
        trigger_duration_ms=config.barge_in.trigger_duration_ms)
    interrupt_handler = InterruptHandler(
        fade_out_ms=config.barge_in.fade_out_ms)

    # 空闲视频播放器优先复用现有背景素材路径，保证空闲时有基础画面回退。
    idle_player = IdleVideoPlayer(
        video_path=config.video.background or None,
        width=config.pipeline.video_width,
        height=config.pipeline.video_height)
    idle_player.load()

    # 输出通道 — 音视频同步输出
    webrtc_out = WebRTCOutput()
    webrtc_out.create_tracks(width=config.pipeline.video_width,
                             height=config.pipeline.video_height,
                             fps=config.pipeline.video_fps)
    rtmp_out = RTMPOutput(
        width=config.pipeline.video_width,
        height=config.pipeline.video_height,
        fps=config.pipeline.video_fps,
        bitrate=config.rtmp.bitrate,
        encoder=config.rtmp.encoder,
        preset=config.rtmp.preset)

    pipeline = PipelineOrchestrator(
        config=config, session_manager=session_mgr,
        asr_engine=asr_engine, llm_client=llm_client, tts_engine=tts_engine,
        lipsync_engine=lipsync_engine, compositor=compositor,
        bargein_detector=bargein_detector, interrupt_handler=interrupt_handler,
        webrtc_output=webrtc_out, rtmp_output=rtmp_out,
        idle_player=idle_player)

    logger.info("所有模块初始化完成")
    logger.info(f"  LLM后端: {config.llm.provider}")
    logger.info(f"  TTS引擎: {config.tts.default_backend}")
    logger.info(f"  LipSync模型: {config.lipsync.model}")
    return pipeline, session_mgr


def run_offline(config: AppConfig, input_path: str, output_path: str):
    """离线模式: 音频文件→LLM对话→TTS→唇形同步→音视频MP4。"""
    import soundfile as sf, cv2, subprocess

    logger.info(f"离线模式: {input_path} -> {output_path}")
    pipeline, session_mgr = init_modules(config)
    session = session_mgr.create_session()

    # 读取输入音频
    audio, sr = sf.read(input_path)
    if sr != 16000:
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)

    # 处理一轮对话
    result = asyncio.run(
        pipeline.process_turn(session, audio.astype(np.float32)))

    if not result or "video" not in result:
        logger.error("未生成音视频内容")
        return

    video_frames = result["video"]
    tts_audio = result["audio"]
    logger.info(f"生成: {len(video_frames)}帧 + {len(tts_audio)}采样点")

    # FFmpeg合成音视频
    vtmp = output_path + ".yuv"
    atmp = output_path + ".pcm"
    try:
        with open(vtmp, "wb") as f:
            for frame in video_frames:
                f.write(frame.tobytes())
        audio_s16 = (tts_audio * 32767).clip(-32768, 32767).astype(np.int16)
        with open(atmp, "wb") as f:
            f.write(audio_s16.tobytes())
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "bgr24",
            "-video_size", f"{config.pipeline.video_width}x{config.pipeline.video_height}",
            "-framerate", str(config.pipeline.video_fps), "-i", vtmp,
            "-f", "s16le", "-ar", "16000", "-ac", "1", "-i", atmp,
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-b:a", "128k",
            "-shortest", output_path,
        ], check=True)
        logger.info(f"音视频已保存: {output_path}")
    except Exception as e:
        logger.error(f"FFmpeg失败: {e}")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        w = cv2.VideoWriter(output_path, fourcc, config.pipeline.video_fps,
                            (config.pipeline.video_width, config.pipeline.video_height))
        for f in video_frames:
            w.write(f)
        w.release()
    finally:
        for tmp in [vtmp, atmp]:
            if os.path.exists(tmp):
                os.remove(tmp)


def main():
    parser = argparse.ArgumentParser(description="实时数字人交互系统")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--input", help="输入音频文件")
    parser.add_argument("--output", default="output.mp4")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--rtmp", help="RTMP推流地址")
    parser.add_argument("--api-key", help="LLM API Key (DeepSeek/OpenAI)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.port:
        config.server.port = args.port
    setup_logging(level=config.logging.level, fmt=config.logging.format)

    # === API Key 处理 ===
    # --api-key 命令行参数优先
    if args.api_key:
        config.llm.api_key = args.api_key
    # 如果环境变量和配置文件都没有API Key，在终端提示用户输入（仅一次）
    if not config.llm.api_key:
        print()
        print("=" * 55)
        print("  未检测到 LLM API Key!")
        print("  方式1: 创建 api_key.txt 文件，写入Key，下次自动读取")
        print("  方式2: 设置环境变量 DEEPSEEK_API_KEY")
        print("  方式3: 在下方直接输入Key（仅本次会话有效）")
        print("=" * 55)
        try:
            user_key = input("  请输入 DeepSeek API Key (直接回车跳过): ").strip()
            if user_key:
                config.llm.api_key = user_key
                # 同时更新 DeepSeekClient 中的 key
                print(f"  OK! Key已加载 ({user_key[:10]}...) 仅本次会话有效\n")
            else:
                print("  未输入Key，对话功能将不可用。\n")
        except (EOFError, KeyboardInterrupt):
            print()

    env_ok = check_environment(config)

    if args.check:
        if not env_ok:
            logger.warning("环境检查发现问题，请修复后重新运行")
            sys.exit(1)
        logger.info("环境检查全部通过")
        return

    if not env_ok:
        logger.warning("环境检查不通过，系统可能无法正常工作")
        logger.warning("继续启动...(使用 --check 仅检查环境)")

    if args.offline:
        if not args.input:
            logger.error("--offline 需要 --input 参数")
            return
        run_offline(config, args.input, args.output)
    else:
        pipeline, session_mgr = init_modules(config)
        if args.rtmp:
            pipeline.rtmp.rtmp_url = args.rtmp
            pipeline.rtmp.start()
            logger.info(f"RTMP推流已启动: {args.rtmp}")
        from src.api.server import start_server
        start_server(config, session_mgr, pipeline)


if __name__ == "__main__":
    main()

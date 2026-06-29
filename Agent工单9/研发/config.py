# -*- coding: utf-8 -*-
"""
config.py — Agent 智能体全局配置文件
--------------------------------------------------------------
功能: 管理所有模型 API 密钥/URL、工具路径、数据库路径、
      ASR/TTS/数字人引擎参数。
      DeepSeek (文本问答/意图识别) + Qwen (文生图) 双模型。

敏感密钥优先从环境变量读取，回退到默认值。

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import os  # 文件系统路径处理 + 环境变量读取

# ============================================================
# 项目根目录 — 容器化支持
# ============================================================
# APP_HOME 环境变量: Docker 容器内为 /app，本地开发自动回退
APP_HOME = os.environ.get("APP_HOME", os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.join(APP_HOME, "研发") if os.path.basename(APP_HOME) != "研发" else APP_HOME
if not os.path.isdir(BASE_DIR):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 回退: 当前文件所在目录

# ============================================================
# DeepSeek — 文本问答 / 意图识别 / NL2SQL / RAG
# 优先从环境变量读取密钥，回退到默认值（向后兼容）
# ============================================================
DEEPSEEK_BASE_URL = "https://api.deepseek.com"                    # API 端点地址
DEEPSEEK_API_KEY = os.environ.get(                                # API 密钥
    "DEEPSEEK_API_KEY",
    "sk-70c456e35e914eb88fa233a04856bcf4"                         # 默认值（开发环境）
)
DEEPSEEK_MODEL = "deepseek-v4-pro"                                 # 模型名称（推理模型）

# ============================================================
# Qwen (通义千问) — 文生图 / 图像编辑
# 使用 DashScope 兼容接口
# ============================================================
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # DashScope API 端点
QWEN_API_KEY = os.environ.get(                                        # API 密钥
    "QWEN_API_KEY",
    "sk-cb2873cdfdb543d1a08a05f3ffda4620c"                           # 默认值
)
QWEN_MODEL = "qwen-vl-plus"             # 多模态模型（图像理解，备用）
QWEN_IMAGE_MODEL = "qwen-vl-plus"       # 文生图模型（程序中使用 qwen-image-edit-max）

# ============================================================
# 工具路径 — 容器化: 优先环境变量, 回退到本地路径
# ============================================================
# Docker 中通过 TOOLS_ROOT=/app/tools 统一指定兄弟项目根目录
_TOOLS_ROOT = os.environ.get("TOOLS_ROOT", os.path.dirname(os.path.dirname(BASE_DIR)))
TOOL_PATHS = {
    "01_记账本": os.environ.get("TOOL_01_PATH", os.path.join(_TOOLS_ROOT, "Agent工单1")),
    "02_日程提醒": os.environ.get("TOOL_02_PATH", os.path.join(_TOOLS_ROOT, "Agent工单2")),
    "03_文生图": os.environ.get("TOOL_03_PATH", os.path.join(_TOOLS_ROOT, "Agent工单3")),
    "04_基金问答": os.environ.get("TOOL_04_PATH", os.path.join(_TOOLS_ROOT, "Agent工单4")),
    "05_招股书问答": os.environ.get("TOOL_05_PATH", os.path.join(_TOOLS_ROOT, "Agent工单5")),
}

# ============================================================
# Agent 通用参数
# ============================================================
API_TIMEOUT = 120     # API 调用超时时间（秒）
MAX_RETRIES = 2       # API 最大重试次数
MAX_HISTORY = 10      # 多轮对话保留最近 N 条消息（N×2条 user+assistant）

# ============================================================
# 数据库路径 — 容器化: 优先环境变量，回退到工具路径
# ============================================================
LEDGER_DB = os.environ.get(
    "LEDGER_DB_PATH",
    os.path.join(TOOL_PATHS["01_记账本"], "money_notes.db")
)
SCHEDULE_DB = os.environ.get(
    "SCHEDULE_DB_PATH",
    os.path.join(TOOL_PATHS["02_日程提醒"], "schedule_notes.db")
)
SCHEDULE_LOCAL_DB = os.environ.get(
    "SCHEDULE_LOCAL_DB_PATH",
    os.path.join(BASE_DIR, "schedule_notes.db")
)

# ============================================================
# 语音识别 (ASR) — FunASR SenseVoiceSmall
# 对应工单需求: "语音识别：funASR"
# ============================================================
ASR_MODEL = "iic/SenseVoiceSmall"    # FunASR 模型名 (SenseVoiceSmall 多语言高精度)
ASR_LANGUAGE = "zh"                  # 识别语言 (zh=中文 / en=英文 / auto=自动)
ASR_DEVICE = "cpu"                   # 推理设备 (cpu / cuda:0)

# ============================================================
# 语音合成 (TTS) — GPT-SoVITS + EdgeTTS 回退
# 对应工单需求: "语音合成：gptSovits"、"自定义语音合成"
# ============================================================
GPTSOVITS_URL = "http://localhost:9880"          # GPT-SoVITS 独立服务 API 地址
GPTSOVITS_REF_AUDIO = None                       # 声音克隆参考音频路径（None=未设置）
GPTSOVITS_REF_TEXT = ""                          # 参考音频对应文本
TTS_FALLBACK_VOICE = "zh-CN-XiaoxiaoNeural"      # EdgeTTS 回退语音（晓晓-中文女声）

# ============================================================
# 数字人 — SadTalker (语音驱动唇形同步)
# 支持 safetensor 和 pth 两种权重格式
# 容器化: SADTALKER_ROOT 环境变量指定模型根目录
# ============================================================
def _find_sadtalker():
    """查找 SadTalker 模型路径。按优先级: 环境变量 → WSL → Windows → 通用。"""
    # 容器化: 环境变量显式指定
    env_root = os.environ.get("SADTALKER_ROOT")
    if env_root:
        ckpt = os.path.join(env_root, "checkpoints")
        src = os.path.join(env_root, "src")
        cfg = os.path.join(src, "config")
        if os.path.isdir(ckpt):
            return ckpt, cfg, src

    # 本地开发: 自动发现 SadTalker 安装路径
    # 按优先级搜索: SADTALKER_ROOT环境变量 → ~/SadTalker* → 项目同级 → USERPROFILE
    candidates = []
    # 候选1: 用户主目录下的 SadTalker 安装
    home = os.path.expanduser("~")
    for pattern in [
        os.path.join(home, "SadTalker_modelscope", "*", "sadtalker"),
        os.path.join(home, "SadTalker_modelscope", "sadtalker"),
        os.path.join(home, "SadTalker", "checkpoints"),
    ]:
        if "*" in pattern:
            import glob as _glob
            for p in sorted(_glob.glob(pattern)):
                candidates.append(p)
        else:
            candidates.append(pattern)

    # 候选2: Windows 用户目录下的 SadTalker 安装
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        candidates.append(os.path.join(userprofile, "SadTalker_modelscope", "wwd123", "sadtalker"))
        candidates.append(os.path.join(userprofile, "SadTalker_modelscope", "sadtalker"))

    # 候选3: 项目同级目录
    project_parent = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(project_parent, "SadTalker_modelscope"))

    for ms in candidates:
        if not os.path.isdir(ms):
            continue
        ckpt = os.path.join(ms, "checkpoints")
        src = os.path.join(ms, "src")
        cfg = os.path.join(ms, "src", "config")
        if os.path.isdir(ckpt) and os.path.isfile(os.path.join(src, "gradio_demo.py")):
            return ckpt, cfg, src
    # 回退: 返回 ~/SadTalker_modelscope 下的默认路径（帮助定位报错）
    ms = os.path.join(home, "SadTalker_modelscope")
    return (
        os.path.join(ms, "checkpoints"),
        os.path.join(ms, "src", "config"),
        os.path.join(ms, "src")
    )

# SadTalker 路径（延迟计算，模块加载时执行）
SADTALKER_CHECKPOINT, SADTALKER_CONFIG, SADTALKER_SRC = _find_sadtalker()
AVATAR_PATH = os.path.join(                                        # 默认数字人形象
    os.path.dirname(SADTALKER_SRC), "..", "examples", "source_image", "man.png"
)
BG_VIDEO_PATH = None                  # 背景视频路径（None=不使用）
DIGITAL_HUMAN_WIDTH = 512             # 输出视频宽度
DIGITAL_HUMAN_HEIGHT = 512            # 输出视频高度
DIGITAL_HUMAN_FPS = 25                # 输出视频帧率
DH_DEVICE = "cuda:0"                  # 推理设备（cuda:0 / cpu）

# ============================================================
# 语音克隆样本存储目录
# ============================================================
VOICE_SAMPLES_DIR = os.path.join(BASE_DIR, "..", "voice_samples")  # 克隆音频保存位置

# ============================================================
# 自测（直接运行此文件）
# ============================================================
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger(__name__)
    log.info("DeepSeek: %s / %s", DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    log.info("Qwen: %s / %s", QWEN_BASE_URL, QWEN_IMAGE_MODEL)
    for k, v in TOOL_PATHS.items():
        log.info("%s: %s (存在=%s)", k, v, os.path.exists(v))
    log.info("SadTalker CKPT: %s", SADTALKER_CHECKPOINT)

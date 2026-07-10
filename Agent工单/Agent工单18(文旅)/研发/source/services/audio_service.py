"""工单18：语音与音频服务 — 百度TTS(国内可用) + edge-tts降级 + 唇形同步 + ASR(Whisper)"""
import base64
import asyncio
import json
import struct
import wave
import io
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

# 工单18：尝试懒加载SpeechRecognition，缺依赖时允许降级运行。
def _load_sr():
    try:
        import speech_recognition as sr
        return sr
    except Exception:
        return None

# 工单18：尝试懒加载Whisper，若环境依赖冲突则自动降级。
def _load_whisper():
    try:
        import whisper
        return whisper
    except Exception:
        return None

# 工单18：缓存懒加载模块与模型实例，避免重复加载。
_SR = None
_WHISPER_MODULE = None
_WHISPER_MODEL = None

def _get_whisper_model():
    global _WHISPER_MODULE, _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    if _WHISPER_MODULE is None:
        _WHISPER_MODULE = _load_whisper()
    if _WHISPER_MODULE is None:
        return None
    try:
        _WHISPER_MODEL = _WHISPER_MODULE.load_model("base")
        return _WHISPER_MODEL
    except Exception:
        return None

def _get_sr():
    global _SR
    if _SR is None:
        _SR = _load_sr()
    return _SR

# 工单18：将文本转为语音 — 国内优先百度TTS → edge-tts → 静音降级
def synthesize_speech(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> dict:
    if not text or not text.strip():
        return _silent_audio_fallback()
    # 工单18：优先使用百度TTS（国内可用，免API Key）
    result = _baidu_tts_synthesize(text)
    if result:
        return result
    # 工单18：降级尝试 edge-tts（海外/代理可用）
    try:
        return asyncio.run(_edge_tts_synthesize(text, voice))
    except Exception:
        pass
    # 工单18：最终降级 — 静音占位，前端显示字幕
    return _silent_audio_fallback()

# 工单18：百度翻译TTS — 国内直连，免费，返回MP3
def _baidu_tts_synthesize(text: str) -> dict | None:
    try:
        import requests
        # 百度TTS对长文本分段，每段最多200字
        text = text.strip()
        if len(text) > 200:
            text = text[:200]  # 截断，保证核心内容可播放

        url = "https://fanyi.baidu.com/gettts"
        resp = requests.get(url, params={
            "text": text,
            "lan": "zh",
            "spd": 3,       # 语速 1-9
            "source": "web"
        }, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=10)

        if resp.status_code == 200 and len(resp.content) > 200:
            audio_b64 = base64.b64encode(resp.content).decode("utf-8")
            # 工单18：百度TTS无法提供字级时间戳，返回空唇形帧让前端用振幅驱动(更准确)
            return {
                "audio_base64": audio_b64,
                "audio_mime": "audio/mp3",
                "tts_text": text,
                "lip_sync": [],  # 空 → 前端自动切换到振幅驱动唇形同步
                "duration": round(len(text) * 0.28, 2),
            }
    except Exception:
        pass
    return None

# 工单18：从文本估算唇形关键帧 — 按字符节奏生成口型序列
def _build_lip_sync_from_text(text: str, total_duration: float) -> list:
    chars = list(text.strip())
    if not chars:
        return [{"t": 0, "v": 0}, {"t": total_duration, "v": 0}]
    char_dur = total_duration / len(chars)
    frames = [{"t": 0, "v": 0}]
    for i, ch in enumerate(chars):
        t_start = round(i * char_dur, 3)
        t_peak = round(t_start + char_dur * 0.5, 3)
        t_end = round(t_start + char_dur, 3)
        v = _estimate_viseme(ch)
        # 每个字产生两个关键帧：开口峰值 + 闭合
        if v > 0.15:
            frames.append({"t": t_start, "v": round(v * 0.7, 2)})
            frames.append({"t": t_peak, "v": round(v, 2)})
        frames.append({"t": t_end, "v": 0})
    frames.append({"t": round(total_duration, 3), "v": 0})
    return _smooth_lip_sync(frames)

# 工单18：edge-tts 异步合成（海外/代理可用时）
async def _edge_tts_synthesize(text: str, voice: str) -> dict:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    audio_chunks = []
    word_timeline = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            offset = float(chunk.get("offset", 0)) / 1e7
            duration = float(chunk.get("duration", 0)) / 1e7
            word_timeline.append({
                "text": chunk.get("text", ""),
                "offset": round(offset, 3),
                "duration": round(duration, 3),
            })
    audio_bytes = b"".join(audio_chunks)
    if not audio_bytes:
        return _silent_audio_fallback()
    lip_sync = _build_lip_sync_from_timeline(word_timeline)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return {
        "audio_base64": audio_b64,
        "audio_mime": "audio/mp3",
        "tts_text": text,
        "lip_sync": lip_sync,
        "duration": round(sum(w["duration"] for w in word_timeline) + word_timeline[-1]["offset"] if word_timeline else 2.0, 2),
    }

# 工单18：基于 WordBoundary 生成唇形同步关键帧序列。
def _build_lip_sync_from_timeline(word_timeline: list) -> list:
    if not word_timeline:
        return [{"t": 0, "v": 0}, {"t": 2.0, "v": 0}]
    frames = []
    for w in word_timeline:
        t = w["offset"]
        dur = w["duration"]
        openness = _estimate_viseme(w["text"])
        frames.append({"t": round(t, 3), "v": round(openness, 2)})
        frames.append({"t": round(t + dur * 0.6, 3), "v": round(openness * 1.2, 2)})
        frames.append({"t": round(t + dur, 3), "v": 0.0})
    return _smooth_lip_sync(frames)

# 工单18：根据中文文字估算口型大小。
def _estimate_viseme(text: str) -> float:
    wide_open = set("啊阿呀哈爸妈大他拿拉嘎卡扎擦撒发哇压挂跨话化花画华涯崖")
    medium_open = set("哦喔我多脱诺罗锅扩昨错所说若活或火伙过国涡")
    small_open = set("额俄鹅恶遏扼鄂萼")
    text = text.strip()
    score = 0.0
    for ch in text:
        if ch in wide_open:
            score = max(score, 0.85)
        elif ch in medium_open:
            score = max(score, 0.55)
        elif ch in small_open:
            score = max(score, 0.30)
        else:
            score = max(score, 0.10)
    return score if score > 0 else 0.15

# 工单18：平滑唇形同步帧，去除抖动并补间。
def _smooth_lip_sync(frames: list) -> list:
    if len(frames) <= 2:
        return frames
    merged = [frames[0]]
    for f in frames[1:]:
        last = merged[-1]
        if abs(f["t"] - last["t"]) < 0.03:
            merged[-1] = {"t": f["t"], "v": max(last["v"], f["v"])}
        else:
            merged.append(f)
    if merged[0]["t"] > 0:
        merged.insert(0, {"t": 0, "v": 0})
    return merged

# 工单18：无声占位音频 — 当所有TTS不可用时的降级方案。
def _silent_audio_fallback() -> dict:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    audio_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return {
        "audio_base64": audio_b64,
        "audio_mime": "audio/wav",
        "tts_text": "",
        "lip_sync": [{"t": 0, "v": 0}, {"t": 2.0, "v": 0}],
        "duration": 2.0,
    }

# 工单18：语音转文字 — 优先 Whisper 本地离线识别，失败后回退 SpeechRecognition。
def transcribe_audio(audio_bytes: bytes, suffix: str = ".wav") -> str:
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_bytes(audio_bytes)
    try:
        model = _get_whisper_model()
        if model is not None:
            try:
                result = model.transcribe(str(tmp_path), language="zh")
                text = result.get("text", "") if isinstance(result, dict) else ""
                text = text.strip() if isinstance(text, str) else ""
                if text:
                    return text
            except Exception:
                pass
        sr_mod = _get_sr()
        if sr_mod is not None:
            recognizer = sr_mod.Recognizer()
            try:
                with sr_mod.AudioFile(str(tmp_path)) as source:
                    audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language="zh-CN")
                return text.strip() or "语音已接收，但未识别出有效文本。"
            except Exception:
                pass
        return "语音已接收，当前环境缺少可用语音识别依赖。项目已降级保持可启动。"
    finally:
        tmp_path.unlink(missing_ok=True)

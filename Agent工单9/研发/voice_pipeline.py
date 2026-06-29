# -*- coding: utf-8 -*-
"""
voice_pipeline.py — 语音对话管线路由
--------------------------------------------------------------
功能: 注册语音相关的 Flask 路由端点。
      语音→FunASR→Agent→GPT-SoVITS→数字人视频

端点:
  POST /api/voice/chat   — 语音对话核心管线
  POST /api/tts           — 文本转语音
  POST /api/voice/clone   — 声音克隆注册

被 main.py 的 main() 调用 register_voice_routes() 注册路由。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, time, uuid, logging, base64, re  # 标准库
import numpy as np                          # 音频数组处理
from flask import request, jsonify          # Flask 请求/响应
from collections import deque               # 视频帧缓冲

import config  # 全局配置
logger = logging.getLogger("agent")


def _parse_audio_input():
    """解析请求中的音频数据。

    支持三种格式: WAV(RIFF头) / PCM int16 / PCM float32。
    返回: (audio_arr: np.ndarray | None, sid: str, error_msg: str | None)
    当 error_msg 非空时，audio_arr 为 None 表示应返回错误响应。
    """
    audio_data = None; sid = "default"
    if 'audio' in request.files:                         # multipart 文件
        audio_data = request.files['audio'].read()
        sid = request.form.get('session', 'default')
    elif request.is_json:                                 # JSON + base64
        data = request.get_json() or {}
        b64 = data.get('audio', '')
        if b64: audio_data = base64.b64decode(b64)
        sid = data.get('session', 'default')
    else:                                                  # 原始二进制
        audio_data = request.get_data()
        sid = request.args.get('session', 'default')

    if not audio_data or len(audio_data) < 160:           # <10ms
        return None, sid, "音频数据为空或太短"

    # 解码音频: WAV头 → PCM int16 → float32
    import io, wave
    try:
        with wave.open(io.BytesIO(audio_data), 'rb') as wf:
            sr = wf.getframerate(); n = wf.getnframes()
            pcm = wf.readframes(n)
            arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            if sr != 16000:
                try:
                    import librosa
                    arr = librosa.resample(arr, orig_sr=sr, target_sr=16000)
                except ImportError:
                    logger.warning("librosa未安装，跳过重采样(sr=%d)", sr)
    except (wave.Error, EOFError):
        try:
            arr = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            arr = np.frombuffer(audio_data, dtype=np.float32)
    return arr, sid, None


def register_voice_routes(app, sessions, video_frame_buffer, output_dir, base_dir):
    """注册语音管线 Flask 路由。

    参数:
        app: Flask 应用实例
        sessions: 多轮对话 session 字典
        video_frame_buffer: 数字人视频帧缓冲 (sid → deque)
        output_dir: 视频输出目录路径
        base_dir: 研发目录路径
    """

    # ================================================================
    # POST /api/voice/chat — 语音对话核心管线
    # ================================================================
    @app.route('/api/voice/chat', methods=['POST'])
    def api_voice_chat():
        """语音对话: 音频→ASR→Agent→TTS→数字人视频。"""
        t0 = time.time()

        # --- 解析音频 ---
        audio_arr, sid, err = _parse_audio_input()
        if err: return jsonify({"error": err}), 400

        logger.info("🎤 语音输入: session=%s", sid[:8])

        # === 步骤1: ASR (FunASR SenseVoiceSmall) ===
        t1 = time.time()
        try:
            from asr_engine import get_asr_engine
            asr = get_asr_engine(); query = asr.transcribe_sync(audio_arr)
            asr_elapsed = time.time() - t1
            logger.info("🎯 ASR(%.1fms): %s", asr_elapsed * 1000, query[:80])
        except ImportError as e:
            return jsonify({"error": f"ASR引擎不可用: {e}"}), 503
        except Exception as e:
            return jsonify({"error": f"语音识别失败: {str(e)[:100]}"}), 500

        if not query or not query.strip():
            return jsonify({"error": "未检测到语音内容", "query": ""}), 400

        from main import _clean_query
        query = _clean_query(query)  # 清洗文本

        # === 步骤2: Agent处理 ===
        if sid not in sessions: sessions[sid] = []
        history = sessions[sid]
        from agent_core import recognize_intent, process_query
        intent_tool, _, _ = recognize_intent(query, history)
        logger.info("🎯 意图预判: %s", intent_tool)
        # ★ 只有当意图明确匹配工具时才传递 pre_recognized_tool，避免 unknown 时重复调用 API
        from tool_registry import TOOL_REGISTRY
        ptool = intent_tool if (intent_tool and intent_tool in TOOL_REGISTRY) else None
        result = process_query(query, history, pre_recognized_tool=ptool)
        agent_elapsed = result.get('elapsed', 0); answer = result['answer']

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer[:500]})
        if len(history) > config.MAX_HISTORY * 2:
            history = history[-config.MAX_HISTORY * 2:]
        sessions[sid] = history

        # === 步骤3: TTS (GPT-SoVITS / EdgeTTS回退) ===
        t2 = time.time(); audio_b64 = None
        tts_audio = np.array([], dtype=np.float32); tts_elapsed = 0
        try:
            from tts_engine import get_tts_engine
            tts = get_tts_engine()
            # ★ 性能优化: TTS 文本上限 200 字（约 30-40 秒音频，避免 3 分钟+ 的视频渲染）
            tts_text = answer[:200]
            if len(answer) > 200:
                tts_text = tts_text.rsplit('。', 1)[0] + '。'
            tts_audio = tts.synthesize_sync(tts_text)
            if len(tts_audio) > 0:
                audio_b64 = tts.audio_to_base64_wav(tts_audio)
            tts_elapsed = time.time() - t2
            logger.info("🔊 TTS(%.1fms, %.1fs): %s...",
                         tts_elapsed * 1000, len(tts_audio) / 16000, answer[:40])
            try:
                from metrics import get_metrics
                get_metrics().record_stage("tts", tts_elapsed)
            except Exception: pass
        except ImportError:
            logger.warning("TTS不可用，仅返回文本")
        except Exception as e:
            logger.error("TTS失败: %s", e)

        # === 步骤4: 数字人视频 ===
        t3 = time.time(); video_frame_count = 0; video_url = None
        try:
            from digital_human import get_digital_human
            dh = get_digital_human()
            if len(tts_audio) > 0:
                vf = dh.generate_video(tts_audio, answer[:200])
                video_frame_count = len(vf)
                if sid not in video_frame_buffer:
                    video_frame_buffer[sid] = deque(maxlen=60)
                for f in vf[-30:]: video_frame_buffer[sid].append(f)
                if vf:
                    vname = f"reply_{uuid.uuid4().hex[:8]}.mp4"
                    vpath = os.path.join(output_dir, vname)
                    dh.composite_audio_video(vf, tts_audio, vpath)
                    # 确保文件完全写入磁盘
                    import time as _t; _t.sleep(0.05)
                    video_url = f"/static/output/{vname}"
                    # 唇形同步诊断
                    aud_dur = len(tts_audio) / 16000.0
                    exp_fr = int(aud_dur * 25)
                    if abs(video_frame_count - exp_fr) > 1:
                        logger.warning("唇形同步: 语音%d帧 vs 音频%.2fs(期望%d帧) 偏差%+d",
                                     video_frame_count, aud_dur, exp_fr, video_frame_count - exp_fr)
                dh_elapsed = time.time() - t3
                logger.info("🎬 DH: %d帧 (%.1fms)", video_frame_count, dh_elapsed * 1000)
                try:
                    from metrics import get_metrics
                    get_metrics().record_stage("dh_video", dh_elapsed)
                except Exception: pass
        except ImportError: pass
        except Exception as e:
            logger.error("DH失败: %s", e)

        total_elapsed = time.time() - t0
        # SLA记录
        try:
            from metrics import get_metrics
            m = get_metrics(); m.record_stage("asr", asr_elapsed)
            m.record_stage("agent_intent", asr_elapsed * 0.15)
            m.record_stage("agent_tool", agent_elapsed * 0.85)
            m.record_stage("total", total_elapsed)
        except Exception: pass

        resp = {"query": query, "answer": answer[:500], "tool": result['tool'],
                "elapsed": round(total_elapsed, 2), "asr_elapsed": round(asr_elapsed, 2),
                "tts_elapsed": round(tts_elapsed, 2), "video_frames": video_frame_count,
                "sla_ok": total_elapsed <= 3.0, "_v": 5}
        if audio_b64:
            resp["audio"] = audio_b64; resp["audio_format"] = "wav"
            resp["audio_sample_rate"] = 16000
        if video_url: resp["video_url"] = video_url

        logger.info("✅ 语音管线: total=%.1fs %s", total_elapsed,
                     "SLA✓" if total_elapsed <= 3.0 else "SLA✗")
        return jsonify(resp)


    # ================================================================
    # POST /api/tts — 独立文本转语音
    # ================================================================
    @app.route('/api/tts', methods=['POST'])
    def api_tts():
        """文本转语音，支持voice参数进行声音克隆。"""
        text = ""; voice = None
        if request.is_json:
            data = request.get_json() or {}
            text = data.get('text', '').strip(); voice = data.get('voice')
        else:
            text = request.form.get('text', '').strip()
            voice = request.form.get('voice')
        if not text: return jsonify({"error": "文本为空"}), 400
        try:
            from tts_engine import get_tts_engine
            tts = get_tts_engine()
            tts_text = text[:200]  # 性能优化：限制TTS长度
            if len(text) > 200:
                tts_text = tts_text.rsplit('。', 1)[0] + '。'
            audio = tts.synthesize_sync(tts_text, voice=voice)
            if len(audio) == 0: return jsonify({"error": "TTS合成失败"}), 500
            return jsonify({"audio": tts.audio_to_base64_wav(audio), "format": "wav",
                            "sample_rate": 16000, "duration_s": round(len(audio) / 16000, 2),
                            "engine": "gptsovits" if tts.check_available() else "edgetts"})
        except ImportError:
            return jsonify({"error": "TTS引擎不可用"}), 503
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 500


    # ================================================================
    # POST /api/voice/clone — 声音克隆注册
    # ================================================================
    @app.route('/api/voice/clone', methods=['POST'])
    def api_voice_clone():
        """上传参考音频→注册到GPT-SoVITS→返回voice_id。"""
        voice_name = "custom_voice"; ref_text = ""; audio_data = None
        if 'audio' in request.files:
            audio_data = request.files['audio'].read()
            voice_name = request.form.get('name', 'custom_voice')
            ref_text = request.form.get('ref_text', '')
        elif request.is_json:
            data = request.get_json() or {}
            b64 = data.get('audio', '')
            if b64: audio_data = base64.b64decode(b64)
            else: return jsonify({"error": "缺少音频数据"}), 400
            voice_name = data.get('name', 'custom_voice')
            ref_text = data.get('ref_text', '')
        else:
            return jsonify({"error": "请上传音频文件"}), 400

        # 保存参考音频
        clone_dir = os.path.join(base_dir, "..", "voice_samples")
        os.makedirs(clone_dir, exist_ok=True)
        audio_path = os.path.join(clone_dir, f"{voice_name}.wav")
        with open(audio_path, "wb") as f: f.write(audio_data)
        if ref_text:
            with open(os.path.join(clone_dir, f"{voice_name}.txt"), "w", encoding="utf-8") as f:
                f.write(ref_text)

        # 尝试GPT-SoVITS注册
        gptsovits_ok = False
        try:
            from tts_engine import get_tts_engine
            tts = get_tts_engine()
            if tts.check_available():
                import asyncio
                gptsovits_ok = asyncio.run(tts.clone_voice(voice_name, audio_path, ref_text))
        except Exception as e:
            logger.warning("GPT-SoVITS注册失败: %s", e)

        logger.info("声音克隆: %s (%dKB)", voice_name, len(audio_data) / 1024)
        return jsonify({"status": "registered" if gptsovits_ok else "saved",
                        "voice_id": voice_name, "audio_path": audio_path,
                        "size_kb": round(len(audio_data) / 1024, 1),
                        "message": ("已注册到GPT-SoVITS" if gptsovits_ok
                                    else "已保存。启动GPT-SoVITS后可进行克隆推理。"),
                        "usage": {"tts_endpoint": "/api/tts",
                                  "how_to_use": f'POST /api/tts {{"text":"你好","voice":"{voice_name}"}}'}})

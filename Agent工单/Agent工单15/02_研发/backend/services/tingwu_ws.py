"""
================================================================================
文件名:   tingwu_ws.py
功能:     通义听悟 DashScope WebSocket 实时语音识别协议处理
          —— 全双工流式音频识别核心，严格遵循 DashScope WebSocket 协议
参考:     https://help.aliyun.com/zh/model-studio/real-time-speech-recognition
          https://help.aliyun.com/zh/model-studio/websocket-for-paraformer
所属项目: 医疗智能体-Agent 数字人项目
工单编号: 人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0

DashScope WebSocket 实时 ASR 协议规范:
  端点: wss://{host}/api-ws/v1/inference
  鉴权: Authorization: Bearer {api_key}
  传输: 全双工 WebSocket（二进制音频帧上行 / JSON 识别结果下行）

  消息流程（客户端 → 服务端）:
    Client → Server:  {"header":{"action":"run-task","task_id":"xxx"},
                       "payload":{"model":"paraformer-realtime-v2",
                       "parameters":{"format":"pcm","sample_rate":16000},
                       "input":{"language_hints":["zh"]}}}
    Client → Server:  <binary PCM audio frames>
    Client → Server:  {"header":{"action":"finish-task","task_id":"xxx"}}

  事件流程（服务端 → 客户端）:
    Server → Client:  {"header":{"event":"task-started",...}}      任务已启动
    Server → Client:  {"header":{"event":"result-generated",...},  识别结果
                       "payload":{"output":{"sentence":{"text":"...",...}}}}
    Server → Client:  {"header":{"event":"task-finished",...}}     任务完成
    Server → Client:  {"header":{"event":"task-failed",...}}       任务失败

本模块导出:
  _dashscope_ws_asr(api_key, task_id, audio_chunks, sample_rate, language)
    → 异步生成器，yield 识别结果字典
================================================================================
"""
import json
import logging
import asyncio
import aiohttp
from config import DASHSCOPE_WS_URL                                 # 从环境变量读取 WebSocket 地址

_log = logging.getLogger("medical_agent.tingwu.ws")                 # 子 logger 便于按模块过滤日志


async def _dashscope_ws_asr(
        api_key: str,                                               # DashScope API Key（sk-xxx）
        task_id: str,                                               # 唯一任务 ID（UUID 前 16 位）
        audio_chunks,                                               # AsyncGenerator[bytes, None] 音频帧流
        sample_rate: int = 16000,                                   # 音频采样率（Hz）
        language: str = "zh",                                       # 识别语言代码
):
    """
    DashScope WebSocket 实时语音识别 —— 全双工流式核心

    连接 DashScope 全双工 WebSocket，建立双向通信通道：
      上行: 逐帧发送 PCM 原始音频数据（二进制）
      下行: 实时接收 JSON 格式的识别结果

    参数:
      api_key:       DashScope API Key，格式为 sk-xxx
      task_id:       任务唯一标识，用于跟踪整个识别会话
      audio_chunks:  异步生成器，每次 yield 一个 bytes 类型的音频帧
      sample_rate:   PCM 音频采样率，默认 16000 Hz
      language:      识别语言提示，如 "zh"（中文）、"en"（英文）

    Yields (异步生成器，每次 yield 一个 dict):
      {"type":"partial","text":"中间识别结果"}                      临时/不完整的结果
      {"type":"final","text":"完整句子","begin_time":0,"end_time":2500,
       "sentence_id":1}                                             已确认的最终句子
      {"type":"done","task_id":"xxx","sentence_count":N}           识别成功完成
      {"type":"error","message":"错误描述"}                         连接或识别错误
    """
    ws_url = DASHSCOPE_WS_URL                                       # DashScope WebSocket 端点
    headers = {"Authorization": f"Bearer {api_key}"}                # Bearer Token 鉴权头

    try:
        # ================================================================
        # 建立 WebSocket 连接
        # ================================================================
        async with aiohttp.ClientSession() as session:              # 创建 HTTP 会话
            async with session.ws_connect(
                ws_url,                                             # 目标地址
                headers=headers,                                    # Authorization 头
                timeout=aiohttp.ClientWSTimeout(ws_close=10.0),     # 关闭超时 10s
                heartbeat=20.0,                                     # 心跳间隔 20s
            ) as ws:

                # ================================================================
                # Step 1: 发送 run-task 启动识别任务
                # ================================================================
                start_msg = {
                    "header": {
                        "action": "run-task",                      # 启动任务指令
                        "task_id": task_id,                        # 任务唯一 ID
                        "streaming": "duplex",                     # 全双工流模式
                    },
                    "payload": {
                        "task_group": "audio",                     # 音频类任务
                        "task": "asr",                             # 语音识别
                        "function": "recognition",                 # 识别功能
                        "model": "paraformer-realtime-v2",         # Paraformer 实时模型 v2
                        "parameters": {
                            "format": "pcm",                       # 原始 PCM 格式
                            "sample_rate": sample_rate,            # 采样率
                            "language_hints": [language],          # 语言提示列表
                        },
                        "input": {},                               # 空输入占位
                    },
                }
                await ws.send_str(json.dumps(start_msg, ensure_ascii=False))
                _log.info("DashScope WS run-task 已发送: task_id=%s", task_id)

                # ================================================================
                # Step 2: 创建后台协程 —— 等待 task-started → 发送音频 → finish-task
                #   关键约束: ★ 必须先收到 task-started 事件才能发送音频
                #              ★ 音频发送完毕后立即发送 finish-task 结束识别
                # ================================================================
                task_started_event = asyncio.Event()               # 任务启动信号
                send_done = asyncio.Event()                         # 音频和 finish-task 发送完成
                send_error = []                                     # 发送错误收集

                async def send_audio():
                    """后台协程: 等 server 就绪 → 逐帧发送音频 → 发送 finish-task"""
                    try:
                        # ★ 阻塞等待服务器确认任务启动（超时 10 秒）
                        await asyncio.wait_for(task_started_event.wait(), timeout=10.0)
                        chunk_count = 0
                        async for chunk in audio_chunks:
                            if chunk:
                                try:
                                    await ws.send_bytes(bytes(chunk))   # 发送二进制 PCM 帧
                                    chunk_count += 1
                                    await asyncio.sleep(0)              # 让出 CPU 给事件循环
                                except (ConnectionError, RuntimeError) as ce:
                                    _log.warning("音频发送中断（连接关闭）: %s", ce)
                                    break
                        _log.info("音频发送完成: %d 个chunk", chunk_count)

                        # ★ 音频流发送完毕后，发送 finish-task 通知服务端结束
                        if chunk_count > 0:
                            try:
                                finish_msg = {
                                    "header": {"action": "finish-task", "task_id": task_id},
                                    "payload": {"input": {}},
                                }
                                await ws.send_str(json.dumps(finish_msg))
                                _log.info("finish-task 已发送: task_id=%s", task_id)
                            except Exception:
                                _log.warning("finish-task 发送失败（连接已关闭）")
                    except asyncio.TimeoutError:
                        _log.error("等待 task-started 超时，音频未发送")
                        send_error.append("task-started timeout")
                    except GeneratorExit:
                        pass                                            # 生成器被提前关闭（正常流程）
                    except Exception as e:
                        send_error.append(str(e))
                        _log.error("音频发送异常: %s", e)
                    finally:
                        send_done.set()                                 # 无论如何标记发送结束

                send_task = asyncio.create_task(send_audio())           # 启动后台发送协程

                # ================================================================
                # Step 3: 主循环 —— 接收服务端事件并实时 yield 识别结果
                #   与 send_audio 并发运行: send_audio 发上行数据，这里收下行结果
                # ================================================================
                sentence_count = 0                                      # 已确认的最终句子计数
                task_started = False                                    # 任务是否已启动
                last_partial = ""                                       # 上次中间结果（用于去重）

                async for msg in ws:                                    # 遍历 WebSocket 消息流
                    if msg.type == aiohttp.WSMsgType.TEXT:              # JSON 文本消息
                        data = json.loads(msg.data)                     # 解析 JSON
                        event = data.get("header", {}).get("event", "") # 提取事件类型

                        # ----- 事件: task-started（任务已启动，可以发送音频了）-----
                        if event == "task-started":
                            task_started = True
                            task_started_event.set()                    # ★ 唤醒 send_audio 协程
                            _log.info("DashScope WS 任务已启动: task_id=%s", task_id)

                        # ----- 事件: result-generated（收到识别结果）-----
                        elif event == "result-generated":
                            output = data.get("payload", {}).get("output", {})
                            sentence = output.get("sentence", {})
                            text = sentence.get("text", "")

                            if not text:
                                continue                                # 跳过空结果

                            bt = sentence.get("begin_time") or 0        # 句子开始时间 ms
                            et = sentence.get("end_time") or 0          # 句子结束时间 ms

                            # 判断是否最终句子: 有 sentence_end 标记 或 有有效时间戳
                            is_final = (
                                sentence.get("sentence_end", False) or  # 服务端标记句子结束
                                (bt > 0 and et > bt)                    # 有有效起止时间
                            )

                            if is_final:
                                sentence_count += 1
                                yield {
                                    "type": "final",
                                    "text": text,
                                    "begin_time": bt,
                                    "end_time": et,
                                    "sentence_id": sentence_count,
                                }
                                last_partial = ""                       # 重置中间结果
                            else:
                                # 中间结果去重: 内容不变时不重复输出
                                if text != last_partial:
                                    yield {"type": "partial", "text": text}
                                    last_partial = text

                        # ----- 事件: task-finished（任务成功完成）-----
                        elif event == "task-finished":
                            _log.info("DashScope WS 任务完成: sentences=%d", sentence_count)
                            if not send_done.is_set():
                                send_done.set()                         # 确保发送事件被标记
                            break

                        # ----- 事件: task-failed（任务失败）-----
                        elif event == "task-failed":
                            _log.error("DashScope WS 任务失败, 完整响应: %s",
                                       json.dumps(data, ensure_ascii=False)[:500])
                            err_code = data.get("header", {}).get("error_code", "")
                            err_msg = data.get("header", {}).get("error_message", "")
                            if not err_msg:
                                # 尝试从 payload 提取详细错误
                                err_payload = data.get("payload", {})
                                err_msg = str(err_payload.get("error", err_payload))[:200]
                            yield {"type": "error",
                                   "message": f"{err_code}: {err_msg}" if err_code else err_msg}
                            break

                    elif msg.type == aiohttp.WSMsgType.ERROR:           # WebSocket 协议级错误
                        _log.error("WebSocket 错误: %s", ws.exception())
                        yield {"type": "error",
                               "message": f"WebSocket 错误: {ws.exception()}"}
                        break

                    elif msg.type == aiohttp.WSMsgType.CLOSED:          # 连接正常关闭
                        _log.info("WebSocket 连接已关闭")
                        break

                # ================================================================
                # 清理: 确保发送协程结束，然后 yield 最终 done 事件
                # ================================================================
                if not send_done.is_set():
                    send_done.set()
                await send_task                                         # 等待后台发送协程退出

                yield {"type": "done", "task_id": task_id,
                       "sentence_count": sentence_count}                # 识别完成

    except aiohttp.ClientError as e:
        _log.error("DashScope WS 连接失败: %s", e)
        yield {"type": "error", "message": f"语音服务连接失败: {e}"}
    except Exception as e:
        _log.error("DashScope WS 异常: %s", e)
        yield {"type": "error", "message": f"语音识别异常: {e}"}

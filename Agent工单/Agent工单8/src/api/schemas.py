"""
src/api/schemas.py - Pydantic 数据模型
功能: 定义REST API的请求和响应数据结构。
      对应工单需求: Web API接口规范
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
from pydantic import BaseModel, Field
from typing import Optional


class SessionCreateRequest(BaseModel):
    """创建会话的请求体。"""
    avatar_id: str = Field(default="default", description="数字人形象ID")
    language: str = Field(default="zh-CN", description="对话语言代码")
    voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="TTS语音角色")


class SessionCreateResponse(BaseModel):
    """创建会话的响应体。"""
    session_id: str = Field(..., description="会话唯一标识(UUID)")
    ws_url: str = Field(..., description="WebSocket信令地址")
    status: str = Field(default="created")


class SessionStatusResponse(BaseModel):
    """会话状态查询的响应体。"""
    session_id: str
    state: str = Field(..., description="会话状态: idle/listening/thinking/speaking")
    total_turns: int = Field(default=0, description="总对话轮次")
    latency_ms: float = Field(default=0.0, description="最近一次端到端延迟(ms)")
    fps: float = Field(default=0.0, description="当前帧率")


class TextInputRequest(BaseModel):
    """文本输入(替代语音)的请求体。"""
    text: str = Field(..., min_length=1, max_length=2000, description="用户输入文本")


class TextInputResponse(BaseModel):
    """文本输入的响应体。"""
    status: str = Field(default="queued", description="处理状态")
    response_text: Optional[str] = Field(default=None, description="数字人回复文本")
    audio_url: Optional[str] = Field(default=None, description="生成的音频URL")


class InterruptResponse(BaseModel):
    """打断操作的响应体。"""
    status: str = Field(default="interrupted", description="打断是否成功")


class HealthResponse(BaseModel):
    """健康检查的响应体。"""
    status: str = Field(default="ok")
    gpu: str = Field(default="unknown")
    vram_free_mb: float = Field(default=0.0, description="剩余显存(MB)")
    active_sessions: int = Field(default=0, description="活跃会话数")
    fps: float = Field(default=0.0)


class RTMPStartRequest(BaseModel):
    """启动RTMP推流的请求体。"""
    rtmp_url: str = Field(..., description="RTMP推流目标地址")
    bitrate: str = Field(default="4000k", description="视频码率")


class RTMPStatusResponse(BaseModel):
    """RTMP推流状态的响应体。"""
    status: str = Field(..., description="pushing/stopped/error")
    rtmp_url: str = Field(default="")


class VoiceCloneRequest(BaseModel):
    """声音克隆的请求体。"""
    voice_name: str = Field(..., description="克隆声音的名称")
    text_sample: Optional[str] = Field(default=None, description="声音样本对应的文本")


class VoiceCloneResponse(BaseModel):
    """声音克隆的响应体。"""
    voice_id: str = Field(..., description="克隆声音的唯一ID")
    status: str = Field(default="processing", description="处理状态")
    preview_url: Optional[str] = Field(default=None)


class ErrorResponse(BaseModel):
    """通用错误响应体。"""
    error: str = Field(..., description="错误描述")
    detail: Optional[str] = Field(default=None, description="错误详情")
    code: int = Field(default=500, description="HTTP状态码")


class SessionSettingsRequest(BaseModel):
    """更新会话设置的请求体。"""
    language: Optional[str] = Field(default=None, description="对话语言: zh-CN/en-US/ja-JP")
    scenario: Optional[str] = Field(default=None, description="对话场景: default/customer_service/teacher/english")
    voice: Optional[str] = Field(default=None, description="TTS语音角色名称")
    system_prompt: Optional[str] = Field(default=None, description="自定义系统提示词")


class SessionSettingsResponse(BaseModel):
    """会话设置响应体。"""
    session_id: str
    language: str
    scenario: str
    voice: str
    updated: bool = True


class PerformanceMetricsResponse(BaseModel):
    """管线性能指标响应体。"""
    session_id: str
    # 延迟指标(ms)
    total_latency_ms: float = Field(default=0.0, description="端到端总延迟")
    asr_latency_ms: float = Field(default=0.0, description="ASR语音识别延迟")
    llm_first_token_ms: float = Field(default=0.0, description="LLM首Token延迟")
    tts_first_audio_ms: float = Field(default=0.0, description="TTS首音频延迟")
    audio_feat_ms: float = Field(default=0.0, description="Mel特征提取延迟")
    lipsync_infer_ms: float = Field(default=0.0, description="唇形推理延迟")
    frame_comp_ms: float = Field(default=0.0, description="帧合成延迟")
    # 帧率
    current_fps: float = Field(default=0.0, description="当前实时帧率")
    # SLA检查
    sla_total_ok: bool = Field(default=True, description="总延迟≤3s")
    sla_tts_ok: bool = Field(default=True, description="TTS延迟≤1.7s")
    sla_audio_ok: bool = Field(default=True, description="音频处理延迟≤0.4s")
    sla_fps_ok: bool = Field(default=True, description="帧率≥20fps")
    # 计数
    total_turns: int = Field(default=0)
    interrupt_count: int = Field(default=0)

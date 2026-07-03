"""
================================================================================
文件名:   api/avatar.py
功能:     数字人形象 API 路由 —— 照片上传 / 形象管理 / 语音对话视频生成
================================================================================
"""
import os, json, time, logging, asyncio, uuid  # 导入所需标准库：os 文件操作、json 序列化、time 时间、logging 日志、asyncio 异步、uuid 唯一标识
from pathlib import Path  # 导入 Path 类，用于安全的文件路径操作
from fastapi import APIRouter, UploadFile, File, Form  # 导入 FastAPI 组件：路由器、上传文件、文件参数、表单参数
from fastapi.responses import JSONResponse, FileResponse  # 导入响应类：JSON 响应和文件下载响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于数据模型定义和字段校验
from services.avatar_client import get_avatar_client, AVATAR_DIR  # 导入数字人客户端工厂函数和形象文件存储目录路径

_log = logging.getLogger("medical_agent.avatar")  # 获取数字人形象模块的日志记录器实例
router = APIRouter(prefix="/api/avatar", tags=["数字人形象（SadTalker面部动画）"])  # 创建 API 路由器，前缀 /api/avatar，Swagger 标签描述 SadTalker 功能

_avatars: dict = {}  # 模块级内存字典：存储已上传的形象信息，key 为 avatar_id，value 为 {"path":路径, "name":名称}
_video_tasks: dict = {}  # 模块级内存字典：存储异步视频生成任务状态，key 为 task_id，value 为状态信息字典


class SpeakRequest(BaseModel):  # 定义语音对话请求数据模型
    avatar_id: str = Field(default="", description="形象ID")  # 可选字段：数字人形象 ID，默认为空字符串
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")  # 必填字段：用户提问内容，长度 1-2000 字符
    async_mode: bool = Field(default=True, description="是否异步模式")  # 是否使用异步模式生成视频，默认为 True


@router.post("/upload")  # 注册 POST 路由：/api/avatar/upload，上传数字人形象照片
async def upload_avatar(file: UploadFile = File(...), name: str = Form(default="")):  # 定义异步上传形象接口：file 为必填上传文件，name 为可选表单字段
    ext = Path(file.filename).suffix.lower()  # 提取文件扩展名并转为小写，用于格式校验
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):  # 检查扩展名是否为支持的图片格式
        return JSONResponse({"success": False, "error": "仅支持 JPG/PNG/WEBP"}, status_code=400)  # 不支持的格式返回 400 错误
    avatar_id = uuid.uuid4().hex[:8]  # 生成 8 位十六进制随机字符串作为唯一形象 ID
    save_path = AVATAR_DIR / f"{avatar_id}{ext}"  # 拼接保存路径：形象目录 + 形象ID + 原始扩展名
    content = await file.read()  # 异步读取上传文件的全部字节内容
    save_path.write_bytes(content)  # 将字节内容写入磁盘保存路径
    avatar_name = name or file.filename or f"形象_{avatar_id}"  # 形象名称优先级：用户指定 > 原始文件名 > 默认命名"形象_xxx"
    _avatars[avatar_id] = {"path": str(save_path), "name": avatar_name}  # 将形象信息存入内存字典：路径和名称
    _log.info("形象已上传: id=%s name=%s size=%d", avatar_id, avatar_name, len(content))  # 记录日志：形象ID、名称、文件大小
    return JSONResponse({"success": True, "avatar_id": avatar_id, "name": avatar_name,  # 返回上传成功响应：形象ID、名称
                         "url": f"/api/avatar/image/{avatar_id}", "size_bytes": len(content)})  # 返回访问 URL 和文件字节大小


@router.get("/image/{avatar_id}")  # 注册 GET 路由：/api/avatar/image/{avatar_id}，获取形象原图
async def get_avatar_image(avatar_id: str):  # 定义异步获取形象图片接口，路径参数 avatar_id 为形象 ID
    avatar = _avatars.get(avatar_id)  # 从内存字典中根据 ID 查找形象信息
    if not avatar or not os.path.exists(avatar["path"]):  # 如果形象不存在于内存或文件已从磁盘删除
        return JSONResponse({"error": "形象不存在"}, status_code=404)  # 返回 404 错误
    return FileResponse(avatar["path"])  # 返回文件响应，直接输出图片文件内容


@router.get("/list")  # 注册 GET 路由：/api/avatar/list，列出所有已上传的形象
async def list_avatars():  # 定义异步形象列表接口
    return JSONResponse({"avatars": [{"avatar_id": k, "name": v["name"]} for k, v in _avatars.items()]})  # 遍历内存字典，返回形象 ID 和名称列表


@router.post("/speak")  # 注册 POST 路由：/api/avatar/speak，数字人语音对话视频生成入口
async def avatar_speak(req: SpeakRequest):  # 定义异步语音对话接口，接收 SpeakRequest 请求体
    avatar = _avatars.get(req.avatar_id)  # 根据请求中的 avatar_id 查找形象信息
    if not avatar:  # 如果形象不存在（未上传或 ID 无效）
        return JSONResponse({"success": False, "error": "请先上传照片"}, status_code=400)  # 返回 400 错误，提示先上传照片

    source_image = avatar["path"]  # 获取形象照片的文件路径，作为 SadTalker 的输入源图片

    if req.async_mode:  # 异步模式：立即返回任务 ID，后台生成视频
        task_id = uuid.uuid4().hex[:8]  # 生成 8 位十六进制随机字符串作为唯一任务 ID
        _video_tasks[task_id] = {"status": "processing", "text": "", "video_path": ""}  # 初始化任务状态：处理中、空回复文本、空视频路径

        from services.tts_client import get_tts_client  # 延迟导入 TTS 客户端工厂函数（避免循环依赖）
        from services.llm_client import get_deepseek_client  # 延迟导入 DeepSeek 客户端工厂函数（避免循环依赖）
        ds = get_deepseek_client()  # 获取 DeepSeek 实例，用于生成 AI 回复文本
        agent_result = ds.chat([{"role": "user", "content": req.question}],  # 调用 DeepSeek chat：传入用户问题
                               system="你是智能健康助理'小医'。用中文回复，一句话，20字以内。",  # 系统提示词：角色设定为一句话短回复的健康助理
                               max_tokens=60)  # 限制最大生成 token 数为 60，确保回复简短
        reply_text = agent_result.get("content", "抱歉，暂无法回答。")  # 获取 AI 回复文本，失败时使用默认回复
        _video_tasks[task_id]["text"] = reply_text  # 将回复文本存入任务状态字典

        asyncio.create_task(_generate_video_async(task_id, source_image, req.question, reply_text))  # 创建异步后台任务：开始生成 SadTalker 视频

        return JSONResponse({"success": True, "task_id": task_id, "text": reply_text,  # 立即返回响应：任务 ID、回复文本
                             "video_ready": False, "message": "视频生成中..."})  # 视频就绪状态为 False，提示正在生成
    else:  # 同步模式：阻塞等待视频生成完成后返回结果
        client = get_avatar_client()  # 获取数字人客户端实例
        result = client.speak_pipeline(source_image, req.question, req.avatar_id)  # 调用同步语音管线：传入图片、问题、形象 ID
        return JSONResponse({"success": True, **result})  # 返回包含管线结果的 JSON 响应


@router.get("/video/{task_id}")  # 注册 GET 路由：/api/avatar/video/{task_id}，查询视频生成任务状态
async def get_video(task_id: str):  # 定义异步视频状态查询接口，路径参数 task_id 为任务 ID
    task = _video_tasks.get(task_id)  # 从内存任务字典中查找任务信息
    if not task:  # 如果任务不存在
        return JSONResponse({"error": "任务不存在"}, status_code=404)  # 返回 404 错误
    if task["status"] == "done":  # 如果视频已生成完成
        return JSONResponse({"status": "done", "text": task["text"],  # 返回完成状态、回复文本
                             "video_url": f"/api/avatar/play/{task_id}"})  # 返回视频播放 URL
    if task["status"] == "error":  # 如果视频生成过程中出错
        return JSONResponse({"status": "error", "text": task.get("text", ""),  # 返回错误状态、回复文本
                             "error": task.get("error", "")})  # 返回具体错误信息
    return JSONResponse({"status": task["status"], "text": task.get("text", "")})  # 处理中状态：返回当前状态和已有回复文本


@router.get("/play/{task_id}")  # 注册 GET 路由：/api/avatar/play/{task_id}，播放已生成的视频文件
async def play_video(task_id: str):  # 定义异步视频播放接口，路径参数 task_id 为任务 ID
    task = _video_tasks.get(task_id)  # 从内存任务字典中查找任务信息
    if not task or not task.get("video_path"):  # 如果任务不存在或视频尚未生成
        return JSONResponse({"error": "视频不存在或尚未生成"}, status_code=404)  # 返回 404 错误
    path = task["video_path"]  # 获取视频文件的磁盘路径
    if not os.path.exists(path):  # 检查视频文件是否真实存在于磁盘
        return JSONResponse({"error": "视频文件丢失"}, status_code=404)  # 文件丢失则返回 404 错误
    return FileResponse(path, media_type="video/mp4")  # 返回视频文件响应，指定 MIME 类型为 video/mp4


async def _generate_video_async(task_id: str, source_image: str,  # 定义异步视频生成函数：参数包括任务ID、源图片路径
                                question: str, reply_text: str):  # 用户问题、AI回复文本
    """后台异步生成 SadTalker 唇形视频"""  # 函数文档字符串
    try:  # 使用 try 块捕获视频生成全过程异常
        from services.tts_client import get_tts_client  # 延迟导入 TTS 客户端（函数内导入避免循环依赖）
        tts = get_tts_client()  # 获取 TTS（文本转语音）客户端实例
        audio_bytes = await tts.synthesize(reply_text)  # 异步调用 TTS：将回复文本合成语音，返回音频字节流
        if not audio_bytes:  # 如果 TTS 合成失败，返回空音频
            _video_tasks[task_id]["status"] = "error"  # 更新任务状态为 error
            _video_tasks[task_id]["error"] = "TTS 失败"  # 记录错误信息
            return  # 提前返回，终止视频生成流程

        mp3_path = str(AVATAR_DIR / f"speech_{task_id}.mp3")  # 拼接音频文件保存路径：形象目录 + speech_任务ID.mp3
        with open(mp3_path, "wb") as f:  # 以二进制写入模式打开音频文件
            f.write(audio_bytes)  # 将 TTS 生成的音频字节写入磁盘文件

        loop = asyncio.get_event_loop()  # 获取当前运行的事件循环
        client = get_avatar_client()  # 获取数字人客户端实例

        def _run():  # 定义同步运行函数：在独立线程中执行 CPU 密集型的 SadTalker 视频生成
            wav = client._convert_to_wav(mp3_path)  # 将 MP3 音频转换为 WAV 格式（SadTalker 需要 WAV 输入）
            if not wav: return ""  # 如果音频转换失败，返回空字符串
            return client.generate_sadtalker_video(source_image, wav, task_id) or ""  # 调用 SadTalker 生成唇形同步视频，失败返回空字符串

        video_path = await loop.run_in_executor(None, _run)  # 在默认线程池中执行同步的视频生成函数，避免阻塞事件循环
        if video_path:  # 如果视频生成成功，返回了视频文件路径
            _video_tasks[task_id]["status"] = "done"  # 更新任务状态为 done（完成）
            _video_tasks[task_id]["video_path"] = video_path  # 保存视频文件路径到任务字典
            _log.info("SadTalker 完成: %s", video_path)  # 记录日志：视频生成完成及路径
        else:  # 如果视频生成失败
            _video_tasks[task_id]["status"] = "error"  # 更新任务状态为 error
            _video_tasks[task_id]["error"] = "SadTalker 生成失败"  # 记录错误原因
    except Exception as e:  # 捕获视频生成过程中的任何异常
        _log.error("视频生成异常: %s", e)  # 记录错误日志：异常详情
        _video_tasks[task_id]["status"] = "error"  # 更新任务状态为 error
        _video_tasks[task_id]["error"] = str(e)  # 将异常信息转为字符串存入错误信息字段

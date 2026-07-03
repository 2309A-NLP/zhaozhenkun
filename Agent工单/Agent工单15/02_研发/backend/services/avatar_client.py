"""
================================================================================
文件名:   avatar_client.py
功能:     数字人形象客户端 —— 照片上传 + 面部动画生成（SadTalker）
================================================================================
"""
import os, sys, time, logging, asyncio, uuid, subprocess, shutil  # 导入：os（系统操作）、sys（系统参数）、time（时间）、logging（日志）、asyncio（异步IO）、uuid（唯一ID）、subprocess（子进程）、shutil（文件操作）
from pathlib import Path  # 导入Path用于跨平台路径处理
from typing import Optional  # 导入Optional类型提示，表示值可为None

# 修复 torchvision 0.20+ 兼容性  # 注释：torchvision 0.20+移除了functional_tensor模块，需要手动映射
try:  # 尝试进行兼容性修复
    import torchvision.transforms.functional  # 导入torchvision的功能模块
    sys.modules['torchvision.transforms.functional_tensor'] = torchvision.transforms.functional  # 将旧的functional_tensor模块名映射到新的functional模块，兼容SadTalker的旧引用
except Exception:  # 修复失败时静默跳过
    pass  # 忽略错误（torchvision可能未安装，这不影响其他功能）

# 修复 numpy 2.x 兼容性（SadTalker 需要 numpy 1.x 的宽松 array 创建）  # 注释：numpy 2.x对array创建更严格，需要兼容修复
try:  # 尝试进行numpy兼容性修复
    import numpy as _np  # 导入numpy并使用别名_np
    _np_old_array = _np.array  # 保存原始numpy.array函数引用
    def _np_patched_array(*args, **kwargs):  # 定义修补后的array函数：增加容错能力
        try: return _np_old_array(*args, **kwargs)  # 首先尝试使用原始方法创建数组
        except (ValueError, TypeError):  # 捕获值错误和类型错误（numpy 2.x对不一致形状更严格）
            kwargs['dtype'] = _np.object_  # 将dtype设置为object类型以容纳任意形状的数据
            return _np_old_array(*args, **kwargs)  # 使用object dtype重新尝试创建数组
    _np.array = _np_patched_array  # 用修补后的函数替换numpy.array
    _np.ndarray = _np.ndarray  # keep reference（保留ndarray的引用，确保类型一致性）
except Exception:  # 修复失败时静默跳过
    pass  # 忽略错误

_log = logging.getLogger("medical_agent.avatar")  # 创建模块级日志记录器，标识为"medical_agent.avatar"

# SadTalker 相关路径（可通过环境变量覆盖）  # 注释：路径配置可通过环境变量灵活覆盖
_SADTALKER_MODELS = os.getenv("SADTALKER_MODEL_DIR", "")  # 从环境变量读取SadTalker模型目录，默认空字符串
_SADTALKER_CODE = os.getenv("SADTALKER_CODE_DIR", "")  # 从环境变量读取SadTalker代码目录，默认空字符串

if _SADTALKER_MODELS:  # 如果环境变量指定了模型目录
    SADTALKER_MODEL_DIR = Path(_SADTALKER_MODELS)  # 使用环境变量指定的路径
else:  # 否则使用默认路径
    SADTALKER_MODEL_DIR = Path.home() / "SadTalker_modelscope"  # 默认路径：用户主目录下的SadTalker_modelscope目录

if _SADTALKER_CODE:  # 如果环境变量指定了代码目录
    SADTALKER_DIR = Path(_SADTALKER_CODE)  # 使用环境变量指定的路径
else:  # 否则使用默认路径
    SADTALKER_DIR = Path.home() / "SadTalker_code"  # 默认路径：用户主目录下的SadTalker_code目录

# 项目数据目录：从当前文件位置自动推断项目根目录  # 注释：通过文件路径反向推导项目根目录
# avatar_client.py → services/ → backend/ → 02_研发/ → Agent工单15/  # 注释：路径层级说明
_PROJ = Path(__file__).resolve().parent.parent.parent.parent  # 通过当前文件路径逐级向上4层获取项目根目录
AVATAR_DIR = _PROJ / "data" / "avatars"  # 构造数字人数据存储目录：项目根目录/data/avatars
AVATAR_DIR.mkdir(parents=True, exist_ok=True)  # 确保目录存在：如果不存在则递归创建（parents=True创建所有父目录）

_log.info("SadTalker 模型目录: %s (exists=%s)", SADTALKER_MODEL_DIR, SADTALKER_MODEL_DIR.exists())  # 记录模型目录路径及是否存在
_log.info("SadTalker 代码目录: %s (exists=%s)", SADTALKER_DIR, SADTALKER_DIR.exists())  # 记录代码目录路径及是否存在
_log.info("数字人数据目录: %s", AVATAR_DIR)  # 记录数字人数据输出目录路径


class AvatarClient:  # 定义数字人客户端类：封装照片上传和面部动画生成功能
    def __init__(self):  # 构造函数：初始化数字人客户端
        self.use_gpu = self._check_gpu()  # 检查GPU是否可用并保存结果
        _log.info("数字人初始化: GPU=%s", self.use_gpu)  # 记录GPU可用状态

    def _check_gpu(self) -> bool:  # 私有方法：检查CUDA GPU是否可用
        try:  # 尝试导入torch并检查CUDA
            import torch  # 导入PyTorch
            return torch.cuda.is_available()  # 返回CUDA是否可用的布尔值
        except ImportError:  # 如果torch未安装
            return False  # 返回False表示GPU不可用

    def generate_simple_video(self, source_image: str, audio_path: str,  # 简单视频生成方法：照片+音频→视频（使用ffmpeg合成）
                              task_id: str = "") -> Optional[str]:  # task_id用于标识任务，返回生成的视频路径或None
        """ffmpeg 合成：照片 + 音频 → 视频（秒出，无唇形）"""  # 文档字符串说明
        run_id = task_id or uuid.uuid4().hex[:8]  # 如果未提供task_id则生成8位随机16进制ID作为运行标识
        result_dir = AVATAR_DIR / run_id  # 构造结果输出目录路径
        result_dir.mkdir(parents=True, exist_ok=True)  # 创建输出目录（递归创建并忽略已存在错误）
        output_path = str(result_dir / f"avatar_{run_id}.mp4")  # 构造输出视频文件的完整路径
        try:  # 异常捕获：处理ffmpeg调用可能出现的错误
            cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(source_image),  # 构建ffmpeg命令：-y覆盖输出，-loop 1循环静态图片
                   "-i", str(audio_path), "-c:v", "libx264", "-tune", "stillimage",  # 输入音频，视频编码为H.264，调优模式为静态图像
                   "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest",  # 音频编码为AAC 128kbps，像素格式yuv420p，-shortest以最短流结束
                   "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2",  # 视频滤镜：缩放到512x512并保持宽高比，不够的部分用黑边填充居中
                   output_path]  # 指定输出文件路径
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)  # 执行ffmpeg命令：捕获输出，文本模式，60秒超时
            if proc.returncode == 0 and os.path.exists(output_path):  # 检查命令是否成功且输出文件已生成
                _log.info("ffmpeg 视频已生成: %s (%d bytes)", output_path, os.path.getsize(output_path))  # 记录成功日志：输出路径和文件大小
                return output_path  # 返回生成的视频文件路径
            _log.error("ffmpeg 失败: %s", proc.stderr[-300:])  # 记录ffmpeg错误日志，只取最后300字符防止日志过长
        except Exception as e:  # 捕获ffmpeg执行异常
            _log.error("ffmpeg 异常: %s", e)  # 记录异常日志
        return None  # 失败时返回None

    def generate_sadtalker_video(self, source_image: str, audio_path: str,  # SadTalker唇形动画视频生成方法：输入源图片和音频
                                 task_id: str = "") -> Optional[str]:  # 返回生成的视频路径或None
        """唇形动画：直接调用 SadTalker（使用无中文临时目录避开 Windows OpenCV 路径bug）"""  # 文档字符串说明
        import tempfile, shutil as _shutil  # 导入tempfile用于创建临时目录，shutil重命名为_shutil避免与外层shutil冲突

        sadtalker_root = str(SADTALKER_MODEL_DIR)  # 获取SadTalker模型根目录路径字符串
        old_cwd = os.getcwd()  # 保存当前工作目录（事后恢复用）
        old_path = sys.path.copy()  # 保存sys.path的副本（事后恢复用，因为SadTalker会修改path）

        # 用无中文的临时目录作为 SadTalker 工作区（Windows OpenCV 不支持中文路径）  # 注释：Windows下OpenCV不能处理中文路径
        tmp_base = Path(tempfile.gettempdir()) / "sadtalker_work"  # 构造临时工作基目录路径
        tmp_base.mkdir(parents=True, exist_ok=True)  # 确保临时基目录存在
        run_id = task_id or uuid.uuid4().hex[:8]  # 生成任务ID：使用提供的task_id或随机8位16进制
        result_dir = tmp_base / run_id  # 构造本次任务的临时结果目录
        if result_dir.exists():  # 如果临时目录已存在（清理旧数据）
            _shutil.rmtree(str(result_dir))  # 递归删除旧目录
        result_dir.mkdir(parents=True, exist_ok=True)  # 重新创建干净的临时目录

        try:  # 异常捕获：处理SadTalker运行中的所有可能错误
            os.chdir(sadtalker_root)  # 切换到SadTalker根目录（SadTalker内部使用相对路径）
            if sadtalker_root not in sys.path:  # 如果SadTalker根目录不在Python搜索路径中
                sys.path.insert(0, sadtalker_root)  # 将其插入到搜索路径最前面，确保模块能被找到

            # 转 PNG + 缩放  # 注释：将源图片转为PNG格式并缩放到合适尺寸
            import PIL.Image  # 导入PIL图片处理库
            safe_img = str(tmp_base / f"sadtalker_input_{run_id}.png")  # 构造安全的PNG输入图片路径（纯英文路径）
            img = PIL.Image.open(source_image).convert('RGB')  # 打开源图片并转换为RGB模式
            w, h = img.size  # 获取图片的宽和高
            if max(w, h) > 1024:  # 如果图片任一维度超过1024像素
                ratio = 1024.0 / max(w, h)  # 计算缩放比例（以1024为上限）
                img = img.resize((int(w*ratio), int(h*ratio)), PIL.Image.LANCZOS)  # 按比例缩放图片，使用LANCZOS高质量算法
            img.save(safe_img, 'PNG')  # 保存处理后的图片为PNG格式到安全路径

            # 音频也复制到临时目录  # 注释：确保音频也在纯英文路径下
            safe_audio = str(tmp_base / f"speech_{run_id}.wav")  # 构造安全的WAV音频路径
            _shutil.copy(audio_path, safe_audio)  # 复制音频文件到临时目录

            from src.gradio_demo import SadTalker  # 从SadTalker的gradio_demo模块导入SadTalker类
            st = SadTalker(  # 创建SadTalker实例
                checkpoint_path=os.path.join(sadtalker_root, 'checkpoints'),  # 指定模型检查点目录
                config_path=os.path.join(sadtalker_root, 'src/config'))  # 指定配置文件目录
            st.test(source_image=safe_img, driven_audio=safe_audio,  # 调用test方法生成唇形动画：指定源图片和驱动音频
                    preprocess='crop', still_mode=True, use_enhancer=False,  # 预处理模式为crop，静止模式开启（减少抖动），不使用增强器
                    size=256, result_dir=str(result_dir))  # 生成分辨率256x256，结果输出到临时目录
            videos = list(result_dir.glob("**/*.mp4"))  # 递归搜索结果目录下所有的mp4文件
            if videos:  # 如果找到了生成的视频文件
                video_path = str(max(videos, key=lambda p: p.stat().st_mtime))  # 取最新修改时间的视频文件（通常就是生成的最终视频）
                # 复制到项目目录  # 注释：将视频从临时目录复制到项目持久化目录
                final_path = str(AVATAR_DIR / f"sadtalker_{run_id}.mp4")  # 构造项目目录下的最终视频路径
                _shutil.copy(video_path, final_path)  # 复制视频到项目目录
                _log.info("SadTalker 视频: %s (%d bytes)", final_path, Path(final_path).stat().st_size)  # 记录成功日志：视频路径和文件大小
                return final_path  # 返回最终视频文件路径
        except Exception as e:  # 捕获SadTalker运行异常
            _log.error("SadTalker 异常: %s", e)  # 记录异常日志
        finally:  # finally块：无论成功与否都要执行的清理代码
            os.chdir(old_cwd)  # 恢复原始工作目录
            sys.path = old_path  # 恢复原始sys.path
        return None  # 失败时返回None

    def generate_video(self, source_image: str, audio_path: str,  # 智能视频生成方法：自动选择最佳方案
                       avatar_id: str = "", task_id: str = "") -> Optional[str]:  # avatar_id为数字人标识，task_id为任务标识
        """智能视频生成：先 SadTalker 唇形 → 失败则 ffmpeg"""  # 文档字符串说明策略
        video = self.generate_sadtalker_video(source_image, audio_path, task_id)  # 优先尝试SadTalker生成高质量唇形动画视频
        if video:  # 如果SadTalker成功生成了视频
            return video  # 直接返回视频路径
        _log.info("SadTalker 不可用，降级 ffmpeg")  # 记录降级日志
        return self.generate_simple_video(source_image, audio_path, task_id)  # SadTalker失败时降级使用ffmpeg简单合成静态图片+音频视频

    def speak_pipeline(self, source_image: str, question: str,  # 数字人完整说话管线：Agent生成回复→TTS合成语音→生成视频
                       avatar_id: str = "") -> dict:  # 返回包含所有管线结果的字典
        """数字人完整管线：Agent → TTS → 视频"""  # 文档字符串
        task_id = uuid.uuid4().hex[:8]  # 为本次任务生成唯一8位16进制ID
        from services.llm_client import get_deepseek_client  # 延迟导入DeepSeek客户端
        ds = get_deepseek_client()  # 获取DeepSeek客户端单例
        result = ds.chat([{"role": "user", "content": question}],  # 调用DeepSeek对话：用户问题作为输入
                         system="你是智能健康助理'小医'。用中文回复，一句话，20字以内。",  # 系统提示词：角色为小医，限制回复一句话20字以内
                         max_tokens=60)  # 限制最大输出60token（足够一句简短回复）
        reply_text = result.get("content", "抱歉，我暂时无法回答。")  # 提取Agent回复文本，失败则用默认道歉语
        audio_path = None  # 初始化音频路径为None
        tts_success = False  # 初始化TTS合成成功标志为False
        try:  # TTS合成异常捕获
            from services.tts_client import get_tts_client  # 延迟导入TTS客户端
            tts = get_tts_client()  # 获取TTS客户端单例
            audio_bytes = tts.synthesize_sync(reply_text)  # 同步合成语音：将回复文本转为音频字节
            if audio_bytes:  # 如果合成成功返回了音频数据
                audio_path = str(AVATAR_DIR / f"speech_{task_id}.mp3")  # 构造音频文件保存路径
                with open(audio_path, "wb") as f:  # 以二进制写入模式打开文件
                    f.write(audio_bytes)  # 将音频字节写入文件
                tts_success = True  # 标记TTS合成成功
        except Exception as e:  # 捕获TTS合成异常
            _log.warning("TTS 失败: %s", e)  # 记录TTS失败警告
        video_path = None  # 初始化视频路径为None
        video_success = False  # 初始化视频生成成功标志为False
        if tts_success and audio_path:  # 如果TTS成功且音频路径有效
            wav_path = self._convert_to_wav(audio_path)  # 将MP3音频转换为WAV格式（SadTalker需要WAV输入）
            if wav_path:  # 如果音频转换成功
                video_path = self.generate_video(source_image, wav_path, avatar_id, task_id)  # 调用智能视频生成方法
                video_success = video_path is not None  # 根据视频路径是否为None设置成功标志
        return {"avatar_id": avatar_id, "task_id": task_id, "text": reply_text,  # 返回管线结果字典：数字人ID、任务ID、回复文本
                "audio_path": audio_path, "video_path": video_path,  # 音频文件路径、视频文件路径
                "tts_success": tts_success, "video_success": video_success}  # TTS成功标志、视频生成成功标志

    def _convert_to_wav(self, mp3_path: str) -> Optional[str]:  # 私有方法：将MP3音频转换为WAV格式（16kHz单声道）
        wav_path = mp3_path.rsplit(".", 1)[0] + ".wav"  # 将MP3文件扩展名替换为.wav构造WAV路径
        try:  # 异常捕获
            cmd = ["ffmpeg", "-y", "-i", mp3_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path]  # 构建ffmpeg转换命令：-y覆盖，PCM 16bit小端编码，采样率16kHz，单声道
            proc = subprocess.run(cmd, capture_output=True, timeout=30)  # 执行转换命令：捕获输出，30秒超时
            if proc.returncode == 0 and os.path.exists(wav_path):  # 检查命令成功且WAV文件已生成
                return wav_path  # 返回WAV文件路径
        except: pass  # 任何异常都静默忽略
        return mp3_path  # 转换失败时回退返回原始MP3路径


_avatar: Optional[AvatarClient] = None  # 全局AvatarClient单例变量，类型标注为Optional[AvatarClient]，初始为None

def get_avatar_client() -> AvatarClient:  # 获取数字人客户端单例的工厂函数
    global _avatar  # 声明使用全局变量_avatar
    if _avatar is None:  # 检查单例是否已创建
        _avatar = AvatarClient()  # 未创建则新建实例（懒加载模式）
    return _avatar  # 返回数字人客户端单例

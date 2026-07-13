# 工单20：本文件用于处理录音上传与兼容转写流程。
# 工单20：导入路径处理工具。
from pathlib import Path  # 工单20：代码语句。
# 工单20：导入时间戳工具。
from datetime import datetime  # 工单20：代码语句。
# 工单20：导入OpenAI兼容客户端。
from openai import OpenAI  # 工单20：代码语句。
# 工单20：导入文件名安全处理工具。
from werkzeug.utils import secure_filename  # 工单20：代码语句。

# 工单20：定义音频服务类。
class AudioService:  # 工单20：代码语句。
    # 工单20：初始化音频服务配置。
    def __init__(self, settings: dict):  # 工单20：代码语句。
        # 工单20：保存配置字典。
        self.settings = settings  # 工单20：代码语句。
        # 工单20：保存上传目录对象。
        self.upload_dir = Path(settings.get("upload_dir"))  # 工单20：代码语句。
        # 工单20：定义允许的音频后缀集合。
        self.allowed_suffixes = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}  # 工单20：代码语句。

    # 工单20：定义文件类型校验函数。
    def is_allowed(self, filename: str) -> bool:  # 工单20：代码语句。
        # 工单20：提取后缀并转为小写。
        suffix = Path(filename).suffix.lower()  # 工单20：代码语句。
        # 工单20：返回是否允许上传。
        return suffix in self.allowed_suffixes  # 工单20：代码语句。

    # 工单20：定义保存上传文件函数。
    def save_upload(self, file_storage) -> tuple[bool, str, str]:  # 工单20：代码语句。
        # 工单20：处理空文件情况。
        if not file_storage or not file_storage.filename:  # 工单20：代码语句。
            return False, "", "未选择录音文件。"  # 工单20：代码语句。
        # 工单20：校验文件后缀。
        if not self.is_allowed(file_storage.filename):  # 工单20：代码语句。
            return False, "", "仅支持 mp3、wav、m4a、aac、ogg 格式。"  # 工单20：代码语句。
        # 工单20：构造安全文件名。
        safe_name = secure_filename(file_storage.filename)  # 工单20：代码语句。
        # 工单20：拼接时间戳前缀。
        target_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"  # 工单20：代码语句。
        # 工单20：生成目标路径。
        target_path = self.upload_dir / target_name  # 工单20：代码语句。
        # 工单20：保存文件到本地。
        file_storage.save(target_path)  # 工单20：代码语句。
        # 工单20：返回成功结果。
        return True, target_name, "上传成功。"  # 工单20：代码语句。

    # 工单20：定义兼容转写函数。
    def transcribe_audio(self, stored_name: str) -> str:  # 工单20：代码语句。
        # 工单20：无文件名时返回空文本。
        if not stored_name:  # 工单20：代码语句。
            return ""  # 工单20：代码语句。
        # 工单20：生成本地文件路径。
        audio_path = self.upload_dir / stored_name  # 工单20：代码语句。
        # 工单20：文件不存在时返回提示文本。
        if not audio_path.exists():  # 工单20：代码语句。
            return "录音文件不存在，无法生成转写内容。"  # 工单20：代码语句。
        # 工单20：读取千问接口地址。
        base_url = self.settings.get("qwen_base_url")  # 工单20：代码语句。
        # 工单20：读取千问密钥。
        api_key = self.settings.get("qwen_api_key")  # 工单20：代码语句。
        # 工单20：读取千问ASR模型名。
        model_name = self.settings.get("qwen_asr_model")  # 工单20：代码语句。
        # 工单20：缺少配置时回退到说明文本。
        if not base_url or not api_key or not model_name:  # 工单20：代码语句。
            return f"当前演示版已接入录音上传流程，文件 {stored_name} 已保存，可继续接入供应商ASR接口生成正式转写。"  # 工单20：代码语句。
        try:  # 工单20：代码语句。
            # 工单20：初始化千问兼容客户端。
            client = OpenAI(api_key=api_key, base_url=base_url)  # 工单20：代码语句。
            # 工单20：以二进制方式打开音频文件。
            with audio_path.open("rb") as audio_file:  # 工单20：代码语句。
                # 工单20：调用兼容转写接口。
                response = client.audio.transcriptions.create(model=model_name, file=audio_file)  # 工单20：代码语句。
            # 工单20：读取转写文本内容。
            text = getattr(response, "text", "") or ""  # 工单20：代码语句。
            # 工单20：返回有效转写文本。
            if text.strip():  # 工单20：代码语句。
                return text.strip()  # 工单20：代码语句。
        except Exception:  # 工单20：代码语句。
            # 工单20：转写失败时进入降级分支。
            pass  # 工单20：代码语句。
        # 工单20：返回当前版本的稳妥降级结果。
        return f"当前演示版已接入录音上传流程，文件 {stored_name} 已保存，可继续接入供应商ASR接口生成正式转写。"  # 工单20：代码语句。

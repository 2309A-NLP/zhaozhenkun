# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""multimodal_service.py - 教育场景中的图片校验与多模态解析模块。"""  # 说明当前文件职责。

from pathlib import Path  # 导入路径处理工具。
from uuid import uuid4  # 导入唯一标识生成工具。


class MultimodalService:  # 定义多模态辅助服务类。
    ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}  # 定义允许上传的图片后缀集合。

    def __init__(self, upload_dir: str, max_upload_mb: int, llm_client):  # 初始化多模态辅助服务。
        self.upload_dir = Path(upload_dir)  # 保存上传目录路径对象。
        self.max_upload_mb = max_upload_mb  # 保存上传大小限制值。
        self.llm_client = llm_client  # 保存统一模型客户端实例。
        self.upload_dir.mkdir(parents=True, exist_ok=True)  # 确保上传目录存在。

    def save_upload(self, file_storage):  # 保存上传文件并返回本地路径。
        if not file_storage or not file_storage.filename:  # 当上传对象为空时抛出异常。
            raise ValueError("请先上传图片文件")  # 提示用户上传有效文件。
        suffix = Path(file_storage.filename).suffix.lower()  # 读取上传文件后缀。
        if suffix not in self.ALLOWED_SUFFIXES:  # 当文件后缀不在允许范围内时拒绝保存。
            raise ValueError("仅支持 PNG、JPG、JPEG、WEBP 图片")  # 抛出文件类型异常。
        target = self.upload_dir / f"{uuid4().hex}{suffix}"  # 生成唯一文件名以避免覆盖。
        file_storage.save(target)  # 将上传内容保存到目标路径。
        size_in_mb = target.stat().st_size / 1024 / 1024  # 计算已保存文件大小。
        if size_in_mb > self.max_upload_mb:  # 当文件超出限制时删除并抛出异常。
            target.unlink(missing_ok=True)  # 删除超限文件。
            raise ValueError(f"图片大小不能超过 {self.max_upload_mb}MB")  # 抛出大小限制异常。
        return str(target)  # 返回保存后的本地文件路径。

    def analyze_homework_image(self, prompt: str, image_path: str, provider: str = "qwen") -> str:  # 调用指定多模态模型分析作业图片。
        system_prompt = "你是教育场景中的作业讲评助手，请识别图片中的题目与答案，并给出教学化反馈。"  # 定义多模态系统提示词。
        return self.llm_client.chat_vision(system_prompt, prompt, image_path, provider=provider)  # 返回多模态分析结果。

"""文件功能：处理文本素材创建、文件上传保存、摘要生成和素材查询。"""

from __future__ import annotations  # 启用延后类型注解支持。

from pathlib import Path  # 处理本地文件路径。

from fastapi import UploadFile  # 导入上传文件类型。

from 设计.architecture import AppSettings  # 导入应用配置类型。
from 设计.schemas import AssetRecord  # 导入素材记录结构。
from 研发.repositories_local import ProjectRepository  # 导入项目仓储。


class AssetService:  # 定义素材服务。
    def __init__(self, settings: AppSettings, repository: ProjectRepository) -> None:  # 初始化素材服务。
        self.settings = settings  # 保存全局配置。
        self.repository = repository  # 保存仓储对象。

    def _build_summary(self, text: str) -> str:  # 生成素材摘要。
        normalized = " ".join(text.strip().split())  # 把文本压缩为单行格式。
        return normalized[:180] + ("..." if len(normalized) > 180 else "")  # 返回截断后的摘要文本。

    def create_text_asset(self, name: str, content_text: str, tags: list[str]) -> dict[str, str]:  # 创建文本素材。
        asset = AssetRecord(  # 构造素材对象。
            name=name,  # 保存素材名称。
            asset_type="text",  # 标记素材类型为文本。
            file_name="inline_text.txt",  # 标记为内联文本素材。
            file_path="",  # 文本素材无需本地文件路径。
            content_text=content_text.strip(),  # 保存清理后的文本内容。
            tags=tags,  # 保存标签列表。
            summary=self._build_summary(content_text),  # 生成并保存摘要。
        )  # 完成素材对象构建。
        return self.repository.save_asset(asset)  # 保存并返回素材结果。

    async def save_upload(self, upload_file: UploadFile, asset_type: str, tags: list[str]) -> dict[str, str]:  # 保存上传文件为素材。
        raw_bytes = await upload_file.read()  # 读取上传文件字节内容。
        if len(raw_bytes) > self.settings.max_upload_bytes:  # 如果文件超出限制大小。
            raise ValueError("上传文件超过大小限制。")  # 抛出用户可感知的异常。
        asset = AssetRecord(  # 预先创建素材对象。
            name=Path(upload_file.filename or "未命名文件").stem,  # 使用文件名主体作为素材名称。
            asset_type=asset_type,  # 保存素材类型。
            file_name=upload_file.filename or "upload.bin",  # 保存原始文件名。
            tags=tags,  # 保存标签列表。
        )  # 完成素材对象构建。
        suffix = Path(asset.file_name).suffix or ".bin"  # 提取原始文件扩展名。
        target_path = self.settings.uploads_dir / f"{asset.asset_id}{suffix}"  # 计算保存路径。
        target_path.write_bytes(raw_bytes)  # 把上传内容写入本地文件。
        text_content = raw_bytes.decode("utf-8", errors="ignore") if asset_type in {"text", "document"} else ""  # 尝试解析文本类内容。
        asset.file_path = str(target_path)  # 保存本地文件路径。
        asset.content_text = text_content.strip()  # 保存提取出的文本内容。
        asset.summary = self._build_summary(text_content or asset.file_name)  # 生成素材摘要。
        return self.repository.save_asset(asset)  # 保存并返回素材结果。

    def list_assets(self) -> list[dict[str, str]]:  # 列出全部素材。
        return self.repository.assets.list_items()  # 返回仓储中的素材列表。

    def get_asset(self, asset_id: str) -> dict[str, str] | None:  # 获取单个素材。
        return self.repository.assets.get_item("asset_id", asset_id)  # 返回目标素材记录。

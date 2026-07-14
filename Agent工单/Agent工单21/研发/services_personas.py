"""文件功能：处理数字人画像创建、更新和查询。"""
from __future__ import annotations  # 启用延后类型注解支持。
from 设计.schemas import PersonaRecord  # 导入数字人记录结构。
from 研发.repositories_local import ProjectRepository  # 导入项目仓储。


class PersonaService:  # 定义数字人画像服务。
    def __init__(self, repository: ProjectRepository) -> None:  # 初始化数字人服务。
        self.repository = repository  # 保存仓储对象。

    def create_persona(self, payload: dict[str, object]) -> dict[str, object]:  # 创建数字人画像。
        persona = PersonaRecord(**payload)  # 使用请求内容构造画像对象。
        return self.repository.save_persona(persona)  # 保存并返回数字人结果。

    def update_persona(self, persona_id: str, payload: dict[str, object]) -> dict[str, object]:  # 更新数字人画像。
        stored = self.repository.personas.get_item("persona_id", persona_id)  # 读取已有数字人记录。
        if stored is None:  # 如果数字人不存在。
            raise ValueError("数字人不存在，无法更新。")  # 抛出业务异常。
        merged = {**stored, **payload, "persona_id": persona_id}  # 合并现有内容与更新字段。
        persona = PersonaRecord(**merged)  # 使用合并后的内容重建画像对象。
        return self.repository.save_persona(persona)  # 保存并返回更新结果。

    def list_personas(self) -> list[dict[str, object]]:  # 列出全部数字人画像。
        return self.repository.personas.list_items()  # 返回全部数字人记录。

    def get_persona(self, persona_id: str) -> dict[str, object] | None:  # 获取单个数字人画像。
        return self.repository.personas.get_item("persona_id", persona_id)  # 返回目标数字人记录。

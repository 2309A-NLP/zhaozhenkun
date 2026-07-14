"""文件功能：处理数字人训练任务创建、真实 Ultralight 训练调用和任务状态查询。"""
from __future__ import annotations  # 启用延后类型注解支持。
import json  # 读取训练结果清单。
from pathlib import Path  # 处理训练清单路径。
from 设计.schemas import TrainingJobRecord  # 导入训练任务结构。
from 研发.clients_ultralight import UltralightAdapter  # 导入 Ultralight 适配器。
from 研发.repositories_local import ProjectRepository  # 导入项目仓储。


class TrainingService:  # 定义训练编排服务。
    def __init__(self, repository: ProjectRepository, ultralight_adapter: UltralightAdapter) -> None:  # 初始化训练服务。
        self.repository = repository  # 保存仓储对象。
        self.ultralight_adapter = ultralight_adapter  # 保存数字人适配器。

    def preflight_job(self, persona_id: str, asset_ids: list[str]) -> dict[str, object]:  # 检查训练任务是否满足执行条件。
        persona = self.repository.personas.get_item("persona_id", persona_id)  # 读取目标数字人画像。
        if persona is None:  # 如果数字人不存在。
            raise ValueError("数字人不存在，无法执行训练预检。")  # 抛出业务异常。
        assets = [item for item in self.repository.assets.list_items() if item.get("asset_id") in asset_ids]  # 读取任务所需素材。
        return self.ultralight_adapter.preflight_training(persona, assets)  # 返回训练预检结果。

    def create_job(self, persona_id: str, asset_ids: list[str]) -> dict[str, object]:  # 创建训练任务并执行真实训练。
        persona = self.repository.personas.get_item("persona_id", persona_id)  # 读取目标数字人画像。
        if persona is None:  # 如果数字人不存在。
            raise ValueError("数字人不存在，无法创建训练任务。")  # 抛出业务异常。
        assets = [item for item in self.repository.assets.list_items() if item.get("asset_id") in asset_ids]  # 读取任务所需素材。
        job = TrainingJobRecord(persona_id=persona_id, asset_ids=asset_ids, status="running", stage="preparing")  # 构造训练任务对象。
        job.result_path = self.ultralight_adapter.prepare_training_artifacts(persona, assets, job.job_id)  # 执行真实预处理和训练并记录清单路径。
        manifest = json.loads(Path(job.result_path).read_text(encoding="utf-8"))  # 读取训练结果清单。
        persona["ultralight_dataset_dir"] = manifest.get("dataset_dir", "")  # 回写数字人画像中的数据目录路径。
        persona["ultralight_checkpoint_path"] = manifest.get("checkpoint", "")  # 回写数字人画像中的权重路径。
        self.repository.personas.upsert_item("persona_id", persona)  # 保存更新后的数字人画像。
        job.status = "prepared"  # 更新任务状态为已准备。
        job.stage = "artifacts_ready"  # 更新任务阶段。
        job.message = "真实 Ultralight 训练已执行，训练产物路径已写回数字人画像。"  # 更新任务说明。
        return self.repository.save_training_job(job)  # 保存并返回训练任务。

    def list_jobs(self) -> list[dict[str, object]]:  # 列出全部训练任务。
        return self.repository.training_jobs.list_items()  # 返回全部训练任务记录。

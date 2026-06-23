"""智能体工作流骨架。"""

from typing import Any, Dict, Optional

from workflow.skill_adapter import DocumentQualityAssessmentSkill


class DocumentIngestionWorkflow:
    """文档入库前质量检查工作流骨架。"""

    def __init__(self, config_path: Optional[str] = None):
        self.quality_skill = DocumentQualityAssessmentSkill(config_path)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        quality_result = self.quality_skill.run(payload)
        route = self._decide_route(quality_result)
        return {
            "workflow_name": "document_ingestion_workflow",
            "quality_gate": quality_result,
            "route": route,
        }

    def _decide_route(self, quality_result: Dict[str, Any]) -> str:
        hint = quality_result.get("next_action_hint", {})
        if hint.get("pending_review_count", 0) > 0:
            return "manual_sensitive_review"
        if hint.get("pending_confirmation_count", 0) > 0:
            return "manual_quality_confirmation"
        return "parser_and_chunking"

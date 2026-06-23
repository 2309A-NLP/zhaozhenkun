"""文档质量评估 Skill 适配层。"""

from typing import Any, Dict, List, Optional

from core.assessor import DocumentQualityAssessor


class DocumentQualityAssessmentSkill:
    """将质量评估器包装为可供工作流调用的 Skill。"""

    def __init__(self, config_path: Optional[str] = None):
        assessor_config = config_path if config_path else None
        self.assessor = DocumentQualityAssessor(assessor_config)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        folder_path = payload.get("folder_path")
        file_list = payload.get("file_list") or []
        output_dir = payload.get("output_dir")
        formats = payload.get("output_formats", ["json", "html"])

        if folder_path:
            result = self.assessor.assess_directory(folder_path)
        elif file_list:
            result = self.assessor.assess_files(file_list)
        else:
            raise ValueError("folder_path 或 file_list 至少提供一个")

        reports = {}
        if output_dir:
            reports = self.assessor.generate_report(result, output_dir=output_dir, formats=formats)

        return {
            "skill_name": "document_quality_assessment",
            "success": True,
            "assessment_result": result,
            "report_files": reports,
            "next_action_hint": self._build_next_action_hint(result),
        }

    def _build_next_action_hint(self, result: Dict[str, Any]) -> Dict[str, Any]:
        pending_confirmation = result.get("pending_confirmation_count", 0)
        pending_review = result.get("pending_review_count", 0)
        summary = result.get("summary", {})
        recommendation: List[str] = []

        if pending_review > 0:
            recommendation.append("存在敏感信息，优先进入人工审核节点")
        if pending_confirmation > 0:
            recommendation.append("存在待确认项目，建议进入人工确认或规则复核节点")
        if not recommendation:
            recommendation.append("可进入后续解析、切分、向量化流程")

        return {
            "pending_confirmation_count": pending_confirmation,
            "pending_review_count": pending_review,
            "recommended_routes": recommendation,
            "summary_keys": list(summary.keys()),
        }

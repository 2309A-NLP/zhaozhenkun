# 工单20：本文件用于编排面试AI复盘生成流程。
# 工单20：导入仓储服务。
from services.repository import InterviewRepository  # 工单20：代码语句。
# 工单20：导入评分服务。
from services.scoring_service import build_review  # 工单20：代码语句。
# 工单20：导入模型增强服务。
from services.llm_service import LLMService  # 工单20：代码语句。

# 工单20：定义复盘编排服务类。
class ReviewService:  # 工单20：代码语句。
    # 工单20：初始化复盘服务依赖。
    def __init__(self, repository: InterviewRepository, llm_service: LLMService):  # 工单20：代码语句。
        # 工单20：保存仓储实例。
        self.repository = repository  # 工单20：代码语句。
        # 工单20：保存模型服务实例。
        self.llm_service = llm_service  # 工单20：代码语句。

    # 工单20：定义复盘生成函数。
    def generate_review(self, interview_id: str, provider: str) -> dict:  # 工单20：代码语句。
        # 工单20：读取目标面试记录。
        interview = self.repository.get_interview(interview_id)  # 工单20：代码语句。
        # 工单20：未命中记录时返回错误结构。
        if not interview:  # 工单20：代码语句。
            return {"ok": False, "message": "未找到面试记录。"}  # 工单20：代码语句。
        # 工单20：存在录音文件或录音转写文本时允许生成AI复盘。
        if not (interview.get("audio_file_name") or interview.get("audio_text", "").strip()):  # 工单20：代码语句。
            return {"ok": False, "message": "当前记录缺少录音文件或录音转写文本，暂不支持生成AI复盘。"}  # 工单20：代码语句。
        # 工单20：读取岗位知识点列表。
        knowledge_points = self.repository.get_knowledge_points(interview.get("position_name", ""))  # 工单20：代码语句。
        # 工单20：生成本地规则复盘结果。
        review = build_review(interview, knowledge_points)  # 工单20：代码语句。
        # 工单20：追加模型增强结果。
        review = self.llm_service.enhance_review(review, interview, provider)  # 工单20：代码语句。
        # 工单20：写入缓存便于详情页直接读取。
        self.repository.save_review_cache(interview_id, provider, review)  # 工单20：代码语句。
        # 工单20：返回成功结构。
        return {"ok": True, "interview": interview, "review": review}  # 工单20：代码语句。

    # 工单20：定义读取缓存或重新生成函数。
    def get_or_create_review(self, interview_id: str, provider: str) -> dict:  # 工单20：代码语句。
        # 工单20：读取缓存结果。
        cache = self.repository.get_review_cache(interview_id, provider)  # 工单20：代码语句。
        # 工单20：缓存存在时直接返回。
        if cache:  # 工单20：代码语句。
            interview = self.repository.get_interview(interview_id)  # 工单20：代码语句。
            return {"ok": True, "interview": interview, "review": cache}  # 工单20：代码语句。
        # 工单20：缓存不存在时重新生成。
        return self.generate_review(interview_id, provider)  # 工单20：代码语句。

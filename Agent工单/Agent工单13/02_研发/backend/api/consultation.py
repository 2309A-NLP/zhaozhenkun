"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.0
健康咨询 API —— 知识图谱检索 + LLM 精确回答
================================================================================
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from kg.knowledge import answer_question
from services.llm_client import get_deepseek_client

router = APIRouter(prefix="/api/consultation", tags=["健康咨询"])
_last_disease = {"name": ""}

class ConsultRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)

SYSTEM = (
    "你是临床医学考试辅导专家。回答要求：\n"
    "1. 给出标准医学教科书级别的精确答案，包含具体数值\n"
    "2. 药物必须给出名称和剂量（如红霉素30-50mg/kg/d）\n"
    "3. 时间必须精确（如隔离至病后40天或痉咳后30天）\n"
    "4. 实验室数据给出参考值范围（如白细胞20-50×10⁹/L）\n"
    "5. 优先用中文医学术语，简洁直接\n"
    "6. 结尾加：⚠ 仅供参考，请及时就医\n"
    "7. 不要解释你如何得出答案，直接给出答案"
)

@router.post("/chat")
async def consult(req: ConsultRequest):
    kg = answer_question(req.message, _last_disease["name"])
    ds = get_deepseek_client()

    if kg.get("found"):
        _last_disease["name"] = kg["disease"]

        # 根据问题类型选择不同的回答策略
        q = req.message.lower()
        if any(w in q for w in ["隔离","预防"]):
            hint = "请给出标准隔离期时长，精确到天数。"
        elif any(w in q for w in ["抗生素","药物","治疗","吃什么药"]):
            hint = "请给出首选药物名称和标准剂量（如红霉素30-50mg/kg/d）。"
        elif any(w in q for w in ["血常规","实验室","检查"]):
            hint = "请给出白细胞计数和淋巴细胞比例的具体参考范围。"
        elif any(w in q for w in ["中医","辨证"]):
            hint = "请给出标准方剂名称（如桑白皮汤）。"
        elif any(w in q for w in ["护理"]):
            hint = "请重点说明夜间突发窒息的防范措施。"
        elif any(w in q for w in ["食物","饮食","吃"]):
            hint = "请列出具体的禁忌食物类别（如海鲜类：螃蟹、海虾、海螺等）。"
        else:
            hint = "请给出标准医学教科书级别的精确答案。"

        ctx = f"知识库: {kg['disease']} - {kg['reply'][:300]}\n{hint}"
        prompt = f"{ctx}\n\n用户问题: {req.message}"
    else:
        prompt = f"用户问题: {req.message}\n请给出标准医学答案。"

    r = ds.chat([{"role":"user","content":prompt}], system=SYSTEM, max_tokens=600)
    return JSONResponse({
        "success": "error" not in r, "reply": r["content"],
        "knowledge_graph": {"found": kg.get("found",False),
                            "disease": kg.get("disease",""),
                            "raw": kg.get("reply","")[:200]},
        "model": r["model"], "latency_ms": r.get("latency_ms",0),
    })

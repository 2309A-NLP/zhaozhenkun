"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
健康咨询 API —— Neo4j 知识图谱检索 + LLM 精确回答
================================================================================
Agent 分析思路（示例）：
  1. 分析用户 query 中实体、关系（基于 medical.json 搭建的实体、关系数据结构）
  2. 生成知识图谱查询语句 Cypher
  3. 链接 Neo4j 医疗知识图谱，执行查询语句，获取结果
  4. 根据用户 query、返回的图谱数据，通过大模型实现 answer 生成
================================================================================
"""
from fastapi import APIRouter  # 导入 FastAPI 的路由器，用于定义 API 路由分组
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式的 HTTP 响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于请求数据模型定义和字段校验
from kg.knowledge import answer_question  # 导入知识图谱问答函数：基于 Neo4j/内存知识图谱检索疾病信息
from services.llm_client import get_deepseek_client  # 导入 DeepSeek 客户端工厂函数，用于生成最终回答

router = APIRouter(prefix="/api/consultation", tags=["健康咨询"])  # 创建 API 路由器，前缀 /api/consultation，Swagger 标签为"健康咨询"
_last_disease = {"name": ""}  # 模块级变量：记录上一次查询的疾病名称，用于上下文关联（相同疾病可复用图谱结果）

class ConsultRequest(BaseModel):  # 定义健康咨询请求数据模型，继承 Pydantic BaseModel
    message: str = Field(..., min_length=1, max_length=2000)  # 必填：用户输入的健康咨询问题，长度 1-2000 字符

SYSTEM = (  # 定义系统提示词：设定 AI 为临床医学考试辅导专家
    "你是临床医学考试辅导专家。回答要求：\n"  # 角色设定：临床医学考试辅导专家
    "1. 给出标准医学教科书级别的精确答案，包含具体数值\n"  # 要求1：答案需达到教科书级别的精确度
    "2. 药物必须给出名称和剂量（如红霉素30-50mg/kg/d）\n"  # 要求2：药物信息必须包含标准名称和剂量
    "3. 时间必须精确（如隔离至病后40天或痉咳后30天）\n"  # 要求3：时间相关答案必须精确到天数
    "4. 实验室数据给出参考值范围（如白细胞20-50×10⁹/L）\n"  # 要求4：实验室检查数据需包含参考值范围
    "5. 优先用中文医学术语，简洁直接\n"  # 要求5：使用中文医学术语，回答简洁直接
    "6. 结尾加：⚠ 仅供参考，请及时就医\n"  # 要求6：每条回答末尾添加免责声明
    "7. 不要解释你如何得出答案，直接给出答案"  # 要求7：直接给答案，不解释推理过程
)

@router.post("/chat")  # 注册 POST 路由：/api/consultation/chat，健康咨询对话入口
async def consult(req: ConsultRequest):  # 定义异步健康咨询接口，接收 ConsultRequest 请求体
    kg = answer_question(req.message, _last_disease["name"])  # 调用知识图谱问答：传入用户问题和上一次的疾病名称（用于上下文关联）
    ds = get_deepseek_client()  # 获取 DeepSeek 客户端实例，用于基于图谱数据生成最终回答

    if kg.get("found"):  # 如果知识图谱找到了匹配的疾病信息
        _last_disease["name"] = kg["disease"]  # 更新上一次记录的疾病名称，用于下次查询的上下文关联

        # 检测 KB 数据是否不足（kg/reply 以 ⚠ 开头）
        kb_weak = kg.get("reply","").startswith("⚠")  # 判断图谱回复是否以 ⚠ 开头（表示数据不完整）

        # 根据问题类型选择不同的回答策略
        q = req.message.lower()  # 将用户问题转为小写，用于关键词匹配
        if any(w in q for w in ["隔离","预防"]):  # 检测问题是否涉及隔离或预防
            hint = "请给出标准隔离期时长，精确到天数。"  # 隔离/预防类问题的提示：强调精确天数
        elif any(w in q for w in ["抗生素","药物","治疗","吃什么药","首选"]):  # 检测问题是否涉及药物或治疗
            hint = "请给出首选药物名称和标准剂量（如红霉素30-50mg/kg/d）。"  # 药物类问题的提示：要求给出名称和剂量
        elif any(w in q for w in ["血常规","实验室","检查","检验"]):  # 检测问题是否涉及实验室检查
            hint = "请给出白细胞计数和淋巴细胞比例的具体参考范围。"  # 检查类问题的提示：要求具体参考值范围
        elif any(w in q for w in ["中医","辨证","方剂","方药"]):  # 检测问题是否涉及中医
            hint = "请基于《中医儿科学》教材给出标准方剂名称（百日咳痉咳期主方为桑白皮汤或清金化痰汤加减）。如不确定请明确说明。"  # 中医类问题的提示：要求标准方剂名
        elif any(w in q for w in ["护理"]):  # 检测问题是否涉及护理
            hint = "请重点说明夜间突发窒息的防范措施。"  # 护理类问题的提示：关注夜间紧急情况
        elif any(w in q for w in ["食物","饮食","吃","忌口"]):  # 检测问题是否涉及饮食
            hint = "请列出具体的禁忌食物类别（如海鲜类：螃蟹、海虾、海螺等）。"  # 饮食类问题的提示：要求具体食物类别
        else:  # 其他类型的问题
            hint = "请给出标准医学教科书级别的精确答案。"  # 通用提示：要求教科书级别的标准答案

        # KB 数据不足时加警告标记，让 LLM 更谨慎
        weak_warn = "\n⚠ 知识库数据不足，请严格基于标准医学教科书回答，不确定的地方请明确标注。" if kb_weak else ""  # KB 不足时的额外警告标记
        ctx = f"知识库: {kg['disease']} - {kg['reply'][:500]}\n{hint}{weak_warn}"  # 构建上下文：疾病名 + 图谱回复（截取500字符）+ 提示 + 警告
        prompt = f"{ctx}\n\n用户问题: {req.message}"  # 构建最终提示词：上下文 + 用户问题
    else:  # 如果知识图谱未找到匹配信息
        prompt = f"用户问题: {req.message}\n请给出标准医学答案。"  # 直接使用用户问题构建提示词，要求标准答案

    r = ds.chat([{"role":"user","content":prompt}], system=SYSTEM, max_tokens=600)  # 调用 DeepSeek chat 接口：传入提示词和系统设定，限制 max_tokens 为 600
    return JSONResponse({  # 返回 JSON 格式的健康咨询响应
        "success": "error" not in r, "reply": r["content"],  # 成功标志（无 error 即为成功）、AI 回答内容
        "knowledge_graph": {"found": kg.get("found",False),  # 知识图谱查询结果：是否找到匹配疾病
                            "disease": kg.get("disease",""),  # 匹配到的疾病名称
                            "raw": kg.get("reply","")[:200],  # 图谱原始回复（截取前200字符）
                            "backend": kg.get("backend", "memory"),  # 图谱后端类型（Neo4j 或内存）
                            "cypher": kg.get("cypher"),       # 🆕 生成的 Cypher 查询语句（Neo4j 后端时返回）
                            "neo4j_result": kg.get("neo4j_result"),  # 🆕 Neo4j 查询原始结果
                            "intent": kg.get("intent", ""),   # 🆕 识别的意图类型
                            },
        "model": r["model"], "latency_ms": r.get("latency_ms",0),  # 返回使用的模型名、请求延迟（毫秒）
    })

"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
MCP Server —— 健康咨询 / 地图服务 / 影像分析工具组

工具列表:
  健康咨询 (Consultation):
    consultation_chat   —— Neo4j 知识图谱 + LLM 精准医学问答
    consultation_search —— 根据症状/关键词搜索疾病

  地图服务 (Map):
    map_search_hospital —— 高德 POI 搜索医院
    map_search_nearby   —— 医院周边设施搜索
    map_directions      —— 驾车/步行/公交路线规划
    map_chat            —— LLM 意图解析 + 高德 API + LLM 回复整理

  影像分析 (Image Analysis):
    image_rag_query  —— RAG 检索增强生成
    image_rag_stats  —— 知识库统计信息

通过 @mcp.tool() 装饰器自动注册到 mcp_core.mcp 实例.
================================================================================
"""
import json

from mcp_server.mcp_core import mcp


# ================================================================
# 健康咨询工具组 (Consultation Tools)
#    工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
# ================================================================

@mcp.tool(
    name="consultation_chat",
    description="医疗健康咨询 —— 基于 Neo4j 知识图谱 + LLM 的精准医学问答。覆盖6143种疾病的病原体/症状/诊断/治疗/预防/护理/饮食。"
)
async def consultation_chat(question: str, context_disease: str = "") -> str:
    """
    医疗健康知识问答

    支持的问答类型:
      - 病原体: "百日咳的致病病原体是什么？"
      - 传播途径: "百日咳主要通过什么途径传播？"
      - 典型症状: "百日咳最具特征性的临床表现是什么？"
      - 实验室诊断: "百日咳患者的血常规检查会呈现什么特征？"
      - 治疗药物: "百日咳西医治疗首选的抗生素是什么？"
      - 并发症: "百日咳最常见的严重并发症是什么？"
      - 中医治疗: "中医治疗痉咳期百日咳的主方是什么？"
      - 预防隔离: "百日咳患者的隔离期应持续多久？"
      - 护理要点: "护理百日咳患儿时需特别注意防范什么？"
      - 饮食指导: "百日咳患者应避免食用哪类食物？"

    Args:
      question: 医学问题
      context_disease: 上文讨论的疾病名（用于追问场景）
    """
    from kg.knowledge import answer_question
    from services.llm_client import get_deepseek_client

    kg = answer_question(question, context_disease)
    ds = get_deepseek_client()

    if kg.get("found"):
        system = ("你是临床医学考试辅导专家。给出标准医学教科书级别的精确答案。"
                  "药物给出剂量，时间精确到天，实验室数据给参考范围。"
                  "结尾: ⚠ 仅供参考，请及时就医")
        prompt = f"知识库: {kg['disease']} - {kg['reply'][:500]}\n\n用户问题: {question}"
        r = ds.chat([{"role": "user", "content": prompt}], system=system, max_tokens=600)
        return json.dumps({
            "success": True,
            "answer": r["content"],
            "disease": kg["disease"],
            "knowledge_graph": {
                "backend": kg.get("backend", "memory"),
                "cypher": kg.get("cypher"),
                "intent": kg.get("intent", ""),
            },
            "model": r["model"],
        }, ensure_ascii=False)
    else:
        return json.dumps({"success": False, "answer": kg.get("reply", "未找到相关信息")},
                         ensure_ascii=False)


@mcp.tool(
    name="consultation_search",
    description="搜索疾病信息 —— 根据症状或关键词搜索可能的疾病"
)
async def consultation_search(query: str, top_k: int = 3) -> str:
    """搜索疾病"""
    from kg.knowledge import search_disease
    results = search_disease(query, top_k=top_k)
    diseases = [{"name": r["disease"]["name"],
                 "intro": str(r["disease"].get("intro", ""))[:200],
                 "score": r["score"]} for r in results]
    return json.dumps({"success": True, "diseases": diseases, "count": len(diseases)},
                     ensure_ascii=False)


# ================================================================
# 地图服务工具组 (Map Tools)
#    工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
# ================================================================

@mcp.tool(
    name="map_search_hospital",
    description="搜索医院 —— 根据关键词和城市搜索医院信息"
)
async def map_search_hospital(keywords: str, city: str = "") -> str:
    """搜索医院"""
    from services.amap_client import get_amap_client
    amap = get_amap_client()
    result = amap.search_poi(keywords, city=city, poi_type="090000")
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    name="map_search_nearby",
    description="搜索医院周边设施 —— 住宿、餐饮、公交、地铁"
)
async def map_search_nearby(location: str, poi_type: str = "",
                            keywords: str = "", radius: int = 3000) -> str:
    """
    周边搜索

    Args:
      location: 中心坐标 "lng,lat" 如 "116.397,39.909"
      poi_type: POI类型 100000=住宿 050000=餐饮 150300=公交站 150500=地铁站
      keywords: 关键词
      radius: 搜索半径(米)
    """
    from services.amap_client import get_amap_client
    amap = get_amap_client()
    result = amap.search_around(location, keywords=keywords,
                                poi_type=poi_type, radius=radius)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    name="map_directions",
    description="路线规划 —— 驾车/步行/公交路线规划"
)
async def map_directions(origin: str, destination: str, mode: str = "driving") -> str:
    """
    路线规划

    Args:
      origin: 起点坐标 "lng,lat"
      destination: 终点坐标 "lng,lat"
      mode: 出行方式 driving/walking/transit
    """
    from services.amap_client import get_amap_client
    amap = get_amap_client()
    if mode == "walking":
        result = amap.direction_walking(origin, destination)
    elif mode == "transit":
        result = amap.direction_transit(origin, destination)
    else:
        result = amap.direction_driving(origin, destination)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    name="map_chat",
    description="地图自然语言查询 —— 集成高德地图的智能出行助手。示例：'北京协和医院附近的酒店有哪些？'"
)
async def map_chat(message: str) -> str:
    """地图自然语言查询（LLM意图解析 + 高德API + LLM回复整理）"""
    import re as _re
    from services.amap_client import get_amap_client
    from services.llm_client import get_deepseek_client

    ds = get_deepseek_client()
    amap = get_amap_client()

    MAP_SYSTEM = """你是地图服务意图解析器。从用户消息提取JSON:
可用功能:
1. search: {"action":"search","keywords":"三甲医院","city":"北京"}
2. nearby: {"action":"nearby","location":"116.397,39.909","keywords":"酒店","poi_type":"100000","radius":3000}
3. directions: {"action":"directions","origin_name":"天安门","dest_name":"协和医院","mode":"driving"}
4. hospital_services: {"action":"hospital_services","hospital_name":"协和医院","city":"北京"}
只返回JSON。"""

    # Step 1: 意图解析
    parse_r = ds.chat([{"role": "user", "content": message}],
                     system=MAP_SYSTEM, max_tokens=300)
    m = _re.search(r'\{[^{}]*\}', parse_r.get("content", "{}"))
    intent = json.loads(m.group()) if m else {"action": "search"}

    # Step 2: 调用高德API
    action = intent.get("action", "search")
    if action == "search":
        api_result = amap.search_poi(intent.get("keywords", message),
                                     city=intent.get("city", ""))
    elif action == "nearby":
        api_result = amap.search_around(intent.get("location", ""),
                                        keywords=intent.get("keywords", ""),
                                        poi_type=intent.get("poi_type", ""))
    elif action == "hospital_services":
        api_result = amap.search_hospital_with_services(
            intent.get("hospital_name", message), city=intent.get("city", ""))
    else:
        api_result = {"success": False, "error": "不支持的 action"}

    # Step 3: 整理回复
    if api_result.get("success"):
        summary_prompt = f"用户: {message}\n高德API返回:\n{json.dumps(api_result, ensure_ascii=False)[:1000]}\n请用中文整理回复。"
        summary_r = ds.chat([{"role": "user", "content": summary_prompt}],
                          system="你是智能出行助手，专业简洁友好。", max_tokens=600)
        reply = summary_r.get("content", "")
    else:
        reply = f"查询失败: {api_result.get('error', '未知错误')}"

    return json.dumps({"success": api_result.get("success", False),
                      "reply": reply, "intent": intent}, ensure_ascii=False)


# ================================================================
# 影像分析工具组 (Image Analysis Tools)
#    工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.1
# ================================================================

@mcp.tool(
    name="image_rag_query",
    description="医学知识库检索问答(RAG) —— 基于医疗知识库 + DeepSeek 推理回答医学问题"
)
async def image_rag_query(question: str, top_k: int = 5) -> str:
    """
    医学RAG检索增强生成

    Args:
      question: 医学问题
      top_k: 检索文档数量
    """
    from services.llm_client import get_deepseek_client
    from rag.vector_store import get_vector_store

    vs = get_vector_store()
    deepseek = get_deepseek_client()

    retrieved = vs.search(question, top_k=top_k)
    context_docs = [doc["content"] for doc in retrieved]

    result = deepseek.rag_query(question, context_docs)
    return json.dumps({
        "success": "error" not in result,
        "answer": result["content"],
        "retrieved_count": len(retrieved),
        "model": result["model"],
        "references": [{"content": d["content"][:200], "score": d["score"]}
                       for d in retrieved[:3]],
    }, ensure_ascii=False)


@mcp.tool(
    name="image_rag_stats",
    description="获取知识库统计信息"
)
async def image_rag_stats() -> str:
    """获取知识库统计"""
    from rag.vector_store import get_vector_store
    stats = get_vector_store().get_stats()
    return json.dumps(stats, ensure_ascii=False)

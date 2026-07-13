# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""retrieval.py - 工单18智能助教的公共+私有知识混合检索模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from app.document_parser import chunk_text  # 工单18：导入文本切块函数。
from app.document_parser import detect_media_kinds  # 工单18：导入多模态类型检测函数。
from app.indexing.fusion import fuse_ranked_items  # 工单18：导入双路召回融合函数。
from app.indexing.lexical_index import lexical_score  # 工单18：导入关键词召回评分函数。
from app.indexing.semantic_index import cosine_similarity  # 工单18：导入轻量语义召回评分函数。
from app.state import load_state  # 工单18：导入状态加载函数。
from app.state import new_id  # 工单18：导入唯一标识函数。
from app.state import update_state  # 工单18：导入原子状态更新函数。


def location_text(location: dict) -> str:  # 工单18：将结构化定位信息格式化为可读文本。
    if location.get("page"):  # 工单18：优先处理 PDF 页码定位。
        return f"第{location['page']}页"  # 工单18：返回页码文本。
    if location.get("slide"):  # 工单18：处理课件幻灯片定位。
        return f"第{location['slide']}页幻灯片"  # 工单18：返回幻灯片文本。
    if location.get("sheet"):  # 工单18：处理 Excel 工作表定位。
        return f"工作表 {location['sheet']} 第{location.get('row', 0)}行"  # 工单18：返回工作表定位文本。
    if location.get("row"):  # 工单18：处理 CSV 行号定位。
        return f"第{location['row']}行"  # 工单18：返回表格行号文本。
    if location.get("chunk"):  # 工单18：处理基础文本切块定位。
        return f"片段{location['chunk']}"  # 工单18：返回片段编号文本。
    if location.get("kind"):  # 工单18：处理非标准定位场景。
        return str(location["kind"])  # 工单18：返回定位类型文本。
    return "全文"  # 工单18：回退到全文定位说明。


def _enrich_chunk(resource: dict, chunk: dict, index: int) -> dict:  # 工单18：为资源片段补齐统一字段。
    content = chunk.get("content", "").strip()  # 工单18：读取片段正文并清洗空白。
    location = dict(chunk.get("location", {}))  # 工单18：复制当前片段定位信息。
    location.setdefault("chunk", index)  # 工单18：为缺失定位的片段补充编号。
    return {  # 工单18：返回标准化后的片段结构。
        "chunk_id": chunk.get("chunk_id", f"{resource['resource_id']}-chunk-{index}"),  # 工单18：写入片段唯一标识。
        "resource_id": resource["resource_id"],  # 工单18：写入所属资源编号。
        "content": content,  # 工单18：写入片段正文内容。
        "summary": chunk.get("summary", content[:60]),  # 工单18：写入片段摘要文本。
        "location": location,  # 工单18：写入结构化定位信息。
        "location_text": location_text(location),  # 工单18：写入定位展示文本。
        "modality": chunk.get("modality", "text"),  # 工单18：写入片段模态类型。
        "preview": chunk.get("preview", content[:120]),  # 工单18：写入前端预览文本。
        "source_name": resource.get("file_name", resource.get("title", "")),  # 工单18：写入源文件名称。
    }  # 工单18：结束标准化片段结构。


def normalize_resource(resource: dict) -> dict:  # 工单18：补齐资源对象的切块与多模态信息。
    resource.setdefault("chunks", [])  # 工单18：确保资源存在切块字段。
    resource.setdefault("content_text", "")  # 工单18：确保资源存在正文文本字段。
    if not resource.get("chunks"):  # 工单18：若资源尚未切块则执行基础切块。
        resource["chunks"] = chunk_text(resource.get("content_text", ""))  # 工单18：为资源正文生成检索片段。
    resource["chunks"] = [_enrich_chunk(resource, chunk, index) for index, chunk in enumerate(resource.get("chunks", []), start=1)]  # 工单18：统一标准化全部片段。
    if not resource.get("media_kinds"):  # 工单18：若尚未生成多模态标签则补齐。
        resource["media_kinds"] = detect_media_kinds(resource.get("file_name", resource.get("title", "text.txt")), resource.get("content_text", ""))  # 工单18：根据文件名与文本推断标签。
    return resource  # 工单18：返回标准化后的资源对象。


def _resource_allowed(owner: dict, resource: dict) -> bool:  # 工单18：判断当前用户是否可访问指定资源。
    if resource["scope"] == "public":  # 工单18：公共资源允许所有登录用户访问。
        return True  # 工单18：返回可访问。
    return resource["owner_id"] == owner["user_id"]  # 工单18：仅允许用户访问自己的私有资源。


def add_text_resource(owner: dict, payload: dict) -> dict:  # 工单18：新增文本知识资源。
    resource = normalize_resource({  # 工单18：构造并标准化待写入的新资源对象。
        "resource_id": new_id("res"),  # 工单18：生成资源编号。
        "owner_id": owner["user_id"],  # 工单18：写入资源所属用户编号。
        "owner_role": owner["role"],  # 工单18：写入资源所属角色。
        "scope": payload["scope"],  # 工单18：写入公共或私有范围。
        "title": payload["title"],  # 工单18：写入资源标题。
        "resource_type": payload["resource_type"],  # 工单18：写入资源类型。
        "file_name": payload["title"] + ".txt",  # 工单18：构造展示用文件名。
        "source_url": payload.get("source_url", ""),  # 工单18：写入来源链接。
        "tags": payload.get("tags", []),  # 工单18：写入资源标签列表。
        "content_text": payload["content_text"],  # 工单18：写入资源正文。
        "media_kinds": [],  # 工单18：初始化多模态标签列表。
        "chunks": [],  # 工单18：初始化检索切块列表。
        "created_at": payload["created_at"],  # 工单18：写入创建时间。
    })  # 工单18：结束资源对象构造。
    update_state(lambda state: state["resources"].append(resource))  # 工单18：在单次锁保护下将资源写入状态。
    return resource  # 工单18：返回新增资源对象。


def add_file_resource(owner: dict, resource: dict) -> dict:  # 工单18：新增文件型知识资源。
    normalized = normalize_resource(resource)  # 工单18：先对文件资源执行标准化处理。
    update_state(lambda state: state["resources"].append(normalized))  # 工单18：将标准化文件资源写入状态。
    return normalized  # 工单18：返回新增文件资源对象。


def accessible_resources(owner: dict) -> list[dict]:  # 工单18：获取当前用户可访问资源列表。
    items = []  # 工单18：初始化可访问资源列表。
    for resource in load_state()["resources"]:  # 工单18：遍历全部资源。
        normalized = normalize_resource(resource)  # 工单18：先标准化当前资源。
        if _resource_allowed(owner, normalized):  # 工单18：仅保留当前用户可访问的资源。
            items.append(normalized)  # 工单18：追加可访问资源。
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)  # 工单18：按创建时间倒序排列资源。
    return items  # 工单18：返回当前用户可访问资源。


def list_resources(owner: dict, scope: str = "all", resource_type: str = "all") -> list[dict]:  # 工单18：按筛选条件返回知识资源列表。
    items = accessible_resources(owner)  # 工单18：先获取全部可访问资源。
    if scope != "all":  # 工单18：按公共或私有范围执行过滤。
        items = [item for item in items if item["scope"] == scope]  # 工单18：保留指定范围资源。
    if resource_type != "all":  # 工单18：按资源类型执行过滤。
        items = [item for item in items if item["resource_type"] == resource_type]  # 工单18：保留指定类型资源。
    return items  # 工单18：返回筛选后的资源列表。


def get_resource(owner: dict, resource_id: str) -> dict | None:  # 工单18：按编号读取当前用户可访问的单个资源。
    for item in accessible_resources(owner):  # 工单18：遍历当前用户全部可访问资源。
        if item["resource_id"] == resource_id:  # 工单18：匹配目标资源编号。
            return item  # 工单18：返回命中的资源对象。
    return None  # 工单18：未命中时返回空值。


def delete_resource(owner: dict, resource_id: str) -> dict:  # 工单18：删除当前用户有权管理的资源。
    holder = {}  # 工单18：初始化删除结果持有字典。

    def mutator(state: dict) -> None:  # 工单18：定义在锁内执行的删除逻辑。
        for index, resource in enumerate(state["resources"]):  # 工单18：遍历当前全部资源。
            if resource["resource_id"] != resource_id:  # 工单18：跳过非目标资源。
                continue  # 工单18：继续处理下一个资源。
            if resource["owner_id"] != owner["user_id"]:  # 工单18：仅允许资源所有者删除自己的资源。
                raise PermissionError("仅允许删除自己上传的资源")  # 工单18：拒绝越权删除。
            holder["resource"] = state["resources"].pop(index)  # 工单18：删除目标资源并暂存返回值。
            return  # 工单18：结束删除逻辑。
        raise LookupError("资源不存在")  # 工单18：目标资源不存在时抛出查找异常。

    update_state(mutator)  # 工单18：在单次锁保护下执行资源删除。
    return normalize_resource(holder["resource"])  # 工单18：返回被删除的标准化资源对象。


def _browse_resources(resources: list[dict], top_k: int) -> list[dict]:  # 工单18：为空查询生成资源浏览结果。
    results = []  # 工单18：初始化浏览结果列表。
    for resource in resources[:top_k]:  # 工单18：遍历限定数量的资源。
        first_chunk = resource.get("chunks", [{}])[0] if resource.get("chunks") else {}  # 工单18：读取资源首个片段。
        results.append({  # 工单18：构造浏览结果项。
            "candidate_id": first_chunk.get("chunk_id", resource["resource_id"]),  # 工单18：写入候选标识。
            "resource_id": resource["resource_id"],  # 工单18：写入资源编号。
            "title": resource["title"],  # 工单18：写入资源标题。
            "scope": resource["scope"],  # 工单18：写入资源范围。
            "resource_type": resource["resource_type"],  # 工单18：写入资源类型。
            "media_kinds": resource["media_kinds"],  # 工单18：写入多模态类型。
            "tags": resource["tags"],  # 工单18：写入标签列表。
            "snippet": first_chunk.get("content", resource.get("content_text", ""))[:240],  # 工单18：写入资源摘要片段。
            "location": first_chunk.get("location", {"chunk": 1}),  # 工单18：写入定位信息。
            "location_text": first_chunk.get("location_text", "片段1"),  # 工单18：写入定位展示文本。
            "score": 1.0,  # 工单18：为浏览结果写入固定分数。
        })  # 工单18：结束浏览结果项构造。
    return results  # 工单18：返回资源浏览结果。


def search_resources(owner: dict, query: str, top_k: int, use_public: bool, use_private: bool) -> list[dict]:  # 工单18：执行公共+私有知识混合检索与融合重排。
    resources = [item for item in accessible_resources(owner) if (item["scope"] != "public" or use_public) and (item["scope"] != "private" or use_private)]  # 工单18：按开关过滤可访问资源。
    if not query.strip():  # 工单18：为空查询提供默认资源浏览结果。
        return _browse_resources(resources, top_k)  # 工单18：返回浏览模式结果。
    lexical_items = []  # 工单18：初始化关键词召回候选列表。
    semantic_items = []  # 工单18：初始化语义召回候选列表。
    for resource in resources:  # 工单18：遍历全部候选资源。
        title_text = resource.get("title", "") + "\n" + resource.get("content_text", "")  # 工单18：拼接资源标题与全文文本。
        for chunk in resource.get("chunks", []):  # 工单18：遍历资源全部结构化片段。
            lexical = lexical_score(query, title_text + "\n" + chunk.get("content", ""))  # 工单18：计算关键词召回得分。
            semantic = cosine_similarity(query, chunk.get("content", ""))  # 工单18：计算语义召回得分。
            if lexical <= 0 and semantic <= 0:  # 工单18：过滤双路都不相关的片段。
                continue  # 工单18：继续处理下一个片段。
            item = {  # 工单18：构造统一候选结构。
                "candidate_id": chunk["chunk_id"],  # 工单18：写入片段候选编号。
                "resource_id": resource["resource_id"],  # 工单18：写入所属资源编号。
                "title": resource["title"],  # 工单18：写入资源标题。
                "scope": resource["scope"],  # 工单18：写入资源范围。
                "resource_type": resource["resource_type"],  # 工单18：写入资源类型。
                "media_kinds": resource["media_kinds"],  # 工单18：写入多模态类型。
                "tags": resource["tags"],  # 工单18：写入资源标签。
                "snippet": chunk.get("content", "")[:240],  # 工单18：写入展示摘要内容。
                "location": chunk.get("location", {}),  # 工单18：写入结构化定位信息。
                "location_text": chunk.get("location_text", "全文"),  # 工单18：写入定位展示文本。
                "lexical_score": lexical,  # 工单18：写入关键词得分。
                "semantic_score": semantic,  # 工单18：写入语义得分。
                "modality": chunk.get("modality", "text"),  # 工单18：写入片段模态类型。
            }  # 工单18：结束候选结构构造。
            if lexical > 0:  # 工单18：将关键词命中片段加入稀疏召回结果。
                lexical_items.append(item)  # 工单18：追加关键词候选。
            if semantic > 0:  # 工单18：将语义命中片段加入语义召回结果。
                semantic_items.append(item)  # 工单18：追加语义候选。
    lexical_items.sort(key=lambda item: item["lexical_score"], reverse=True)  # 工单18：按关键词得分降序排序。
    semantic_items.sort(key=lambda item: item["semantic_score"], reverse=True)  # 工单18：按语义得分降序排序。
    fused = fuse_ranked_items(lexical_items[:50], semantic_items[:50])  # 工单18：执行双路召回融合。
    for item in fused:  # 工单18：遍历融合后的结果列表。
        item["score"] = round(item["fusion_score"] + (0.15 if item["scope"] == "private" else 0.05), 4)  # 工单18：在融合分上叠加轻微公私库偏置。
    fused.sort(key=lambda item: item["score"], reverse=True)  # 工单18：按最终分数再次降序排序。
    return fused[:top_k]  # 工单18：返回指定数量的最佳结果。


def build_citations(results: list[dict]) -> list[dict]:  # 工单18：构造结构化引用列表。
    return [  # 工单18：返回每条命中结果的结构化引用。
        {"resource_id": item["resource_id"], "title": item["title"], "scope": item["scope"], "media_kinds": item["media_kinds"], "location": item["location"], "location_text": item["location_text"], "snippet": item["snippet"]}  # 工单18：写入统一引用字段。
        for item in results  # 工单18：遍历全部检索结果。
    ]  # 工单18：结束结构化引用列表构造。

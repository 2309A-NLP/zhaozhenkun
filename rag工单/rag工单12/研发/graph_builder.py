"""
知识图谱构建模块（LightRAG 核心 — 含增量更新）
功能：使用 NetworkX 构建实体关系有向图，支持增量更新/合并、BFS 扩展、可视化
完成：实体去重建图、邻居 BFS 扩展、D3.js 可视化、增量图谱合并、JSON 序列化
"""
import logging
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json                        # JSON 序列化/反序列化
import hashlib                     # MD5 哈希生成唯一节点 ID
import networkx as nx              # NetworkX 图数据库引擎
from typing import Optional        # 类型注解

import config                      # 图谱配置（扩展跳数、缓存路径等）

logger = logging.getLogger(__name__)
logger.info("知识图谱构建模块加载")

logger = logging.getLogger(__name__)


def md5_id(text: str) -> str:
    """
    用 MD5 哈希前 12 位生成实体的唯一稳定 ID
    相同名称的实体始终得到相同 ID，支持增量合并
    """
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


# ======================== 图谱构建 ========================

def build_graph(entities: list[dict], relations: list[dict]) -> nx.DiGraph:
    """
    从实体和关系列表构建有向知识图谱
    参数：
        entities:  [{"name", "type", "description"}, ...] 实体列表
        relations: [{"source", "target", "type", "description"}, ...] 关系列表
    返回：
        NetworkX 有向图（节点存 name/type/description，边存 type/description）
    """
    graph = nx.DiGraph()  # 有向图实例
    # 添加所有实体节点（以 MD5 哈希为节点 ID）
    for ent in entities:
        graph.add_node(
            md5_id(ent["name"]),                      # 节点 ID（MD5 哈希）
            name=ent["name"],                         # 实体名称
            type=ent.get("type", "未知"),              # 实体类型
            description=ent.get("description", "")     # 实体描述
        )
    # 添加所有关系边
    for rel in relations:
        # 兼容 source 和 source_name 两种字段名
        src = rel.get("source", rel.get("source_name", ""))
        tgt = rel.get("target", rel.get("target_name", ""))
        if not src or not tgt:
            continue  # 跳过源或目标为空的无效关系
        sid = md5_id(src)  # 源实体节点 ID
        tid = md5_id(tgt)  # 目标实体节点 ID
        # 确保节点存在（关系引用的实体可能不在实体列表中）
        if not graph.has_node(sid):
            graph.add_node(sid, name=src, type="未知", description="")
        if not graph.has_node(tid):
            graph.add_node(tid, name=tgt, type="未知", description="")
        # 添加有向边
        graph.add_edge(
            sid, tid,
            type=rel.get("type", "相关"),               # 关系类型
            description=rel.get("description", "")       # 关系描述
        )
    print(f"📊 图谱: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
    return graph


# ======================== 增量更新（LightRAG 核心特性） ========================

def incremental_update(
    graph: nx.DiGraph,
    new_entities: list[dict],
    new_relations: list[dict]
) -> dict:
    """
    LightRAG 增量更新：将新提取的实体/关系合并到现有图谱
    只更新变化的部分，无需重建整个图谱（LightRAG 核心优势）
    参数：
        graph:         现有 NetworkX 有向图
        new_entities:  新提取的实体列表
        new_relations: 新提取的关系列表
    返回：
        {"added_nodes": int, "added_edges": int, "merged_nodes": int,
         "total_nodes": int, "total_edges": int}
    """
    old_nodes = graph.number_of_nodes()   # 更新前节点数
    old_edges = graph.number_of_edges()   # 更新前边数

    # 增量合并实体：新实体不存在则添加，存在则合并描述
    for ent in new_entities:
        nid = md5_id(ent["name"])  # 实体唯一 ID
        if not graph.has_node(nid):
            # 新实体：直接添加节点
            graph.add_node(
                nid,
                name=ent["name"],
                type=ent.get("type", "未知"),
                description=ent.get("description", "")
            )
        else:
            # 已有实体：合并描述信息（补充而非覆盖）
            existing_desc = graph.nodes[nid].get("description", "")
            new_desc = ent.get("description", "")
            if new_desc and new_desc not in existing_desc:
                graph.nodes[nid]["description"] = existing_desc + "；" + new_desc

    # 增量合并关系：以 (source_id, target_id, type) 为 key 去重
    for rel in new_relations:
        src = rel.get("source", rel.get("source_name", ""))
        tgt = rel.get("target", rel.get("target_name", ""))
        if not src or not tgt:
            continue  # 跳过无效关系
        sid = md5_id(src)  # 源实体 ID
        tid = md5_id(tgt)  # 目标实体 ID
        # 确保两端节点存在
        if not graph.has_node(sid):
            graph.add_node(sid, name=src, type="未知", description="")
        if not graph.has_node(tid):
            graph.add_node(tid, name=tgt, type="未知", description="")
        # 检查边是否已存在（相同 source+target+type 视为重复）
        edge_exists = False
        if graph.has_edge(sid, tid):
            existing_type = graph.edges[sid, tid].get("type", "")
            if existing_type == rel.get("type", ""):
                edge_exists = True  # 完全重复的边，跳过
        if not edge_exists:
            graph.add_edge(
                sid, tid,
                type=rel.get("type", "相关"),
                description=rel.get("description", "")
            )

    # 计算增量统计
    added_nodes = graph.number_of_nodes() - old_nodes
    added_edges = graph.number_of_edges() - old_edges
    print(f"📊 增量更新: +{added_nodes} 节点, +{added_edges} 边, "
          f"总计 {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
    return {
        "added_nodes": added_nodes, "added_edges": added_edges,
        "merged_nodes": len(new_entities) - added_nodes,
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges()
    }


def diff_graphs(old_graph: nx.DiGraph, new_graph: nx.DiGraph) -> dict:
    """
    计算两个图谱之间的差异（用于增量更新前的变化分析）
    参数：
        old_graph: 旧版本图谱
        new_graph: 新版本图谱
    返回：
        {"new_nodes": list, "removed_nodes": list, "new_edges": list, "removed_edges": list}
    """
    old_nset = set(old_graph.nodes())
    new_nset = set(new_graph.nodes())
    old_eset = set(old_graph.edges())
    new_eset = set(new_graph.edges())
    return {
        "new_nodes": list(new_nset - old_nset),           # 新增节点
        "removed_nodes": list(old_nset - new_nset),       # 移除节点
        "new_edges": list(new_eset - old_eset),           # 新增边
        "removed_edges": list(old_eset - new_eset)        # 移除边
    }


# ======================== 图谱序列化 ========================

def save_graph(graph: nx.DiGraph, path: str) -> None:
    """
    以 node-link JSON 格式保存图谱到文件
    参数：graph - NetworkX 有向图, path - 输出路径
    """
    with open(path, "w", encoding="utf-8") as f:
        # edges="links" 兼容旧版 NetworkX 的命名习惯
        json.dump(nx.node_link_data(graph, edges="links"), f,
                  ensure_ascii=False, indent=2)


def load_graph(path: str) -> Optional[nx.DiGraph]:
    """
    从 node-link JSON 文件加载图谱
    参数：path - JSON 缓存文件路径
    返回：NetworkX 有向图，文件不存在或格式错误则返回 None
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)  # 加载 JSON 数据
        # 自动检测 edges key：新版 NetworkX 用 "edges"，旧版用 "links"
        edges_key = "edges" if "edges" in data else "links"
        g = nx.node_link_graph(data, edges=edges_key)
        print(f"📂 加载图谱: {g.number_of_nodes()} 节点, {g.number_of_edges()} 边")
        return g
    except (FileNotFoundError, json.JSONDecodeError):
        return None  # 文件不存在或格式错误


# ======================== 图谱查询 ========================

def find_entity(graph: nx.DiGraph, name: str) -> Optional[str]:
    """
    按名称在图谱中查找实体节点 ID（前缀匹配）
    参数：graph - 图谱, name - 实体名称（支持部分匹配）
    返回：节点 ID 字符串，未找到返回 None
    """
    for nid, data in graph.nodes(data=True):
        if name in data.get("name", ""):
            return nid  # 返回第一个匹配的节点 ID
    return None


def expand_neighbors(graph: nx.DiGraph, node_ids: list[str],
                     hops: int = 2) -> set[str]:
    """
    BFS 扩展邻居：从给定节点出发，沿关系边向外扩展指定跳数
    参数：
        graph:    NetworkX 有向图
        node_ids: 起始节点 ID 列表
        hops:     扩展跳数（默认值从 config 读取）
    返回：
        所有可达节点 ID 的集合（含起始节点）
    """
    reached = set(node_ids)   # 已访问节点集合
    frontier = set(node_ids)  # 当前层节点（BFS 前沿）
    for _ in range(hops):
        nxt = set()  # 下一层节点
        for nid in frontier:
            # 同时沿出边（successors）和入边（predecessors）扩展
            nxt |= (set(graph.successors(nid)) | set(graph.predecessors(nid))) - reached
        reached |= nxt   # 合并到已访问集合
        frontier = nxt   # 更新前沿为下一层
        if not frontier:
            break         # 没有新节点可扩展，提前终止
    return reached


# ======================== 图谱可视化 ========================

def graph_to_html(graph: nx.DiGraph, output_path: str) -> None:
    """
    使用 D3.js 力导向图生成交互式知识图谱可视化 HTML
    参数：graph - NetworkX 有向图, output_path - 输出 HTML 路径
    """
    # 将 NetworkX 图转为 node-link JSON 格式
    data = nx.node_link_data(graph, edges="links")
    # 实体类型 → 颜色映射（IPO 招股书专用配色）
    type_colors = {
        "发行人": "#6C5CE7", "控股股东/实际控制人": "#FD79A8",
        "关联方/子公司/参股公司": "#00CEC9", "中介机构": "#E17055",
        "高管/核心人员": "#0984E3", "主营业务/产品": "#FDCB6E",
        "核心技术/专利": "#00B894", "募投项目": "#E17055",
        "财务指标": "#D63031", "行业/市场": "#00B894",
        "标准/资质": "#FDCB6E", "地点/区域": "#636E72",
        "获奖/荣誉": "#FFD700",
        # 兜底：通用类型
        "公司": "#6C5CE7", "人物": "#FD79A8", "产品": "#00CEC9",
        "项目": "#E17055", "技术": "#0984E3", "标准": "#FDCB6E",
        "行业": "#00B894", "地点": "#E17055"
    }
    # 读取可视化模板 HTML
    tmpl = os.path.join(os.path.dirname(__file__), "templates", "graph_viz_template.html")
    with open(tmpl, "r", encoding="utf-8") as f:
        html = f.read()  # 模板内容
    # 替换模板占位符为实际数据
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    html = html.replace("__COLORS__", json.dumps(type_colors, ensure_ascii=False))
    # 写入输出文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📊 可视化已保存: {output_path}")


# ======================== 命令行测试入口 ========================

if __name__ == "__main__":
    """命令行测试：加载实体提取缓存 → 构建图谱 → 保存并可视化"""
    cf = os.path.join(config.CACHE_DIR, "entity_extractions.json")
    if not os.path.exists(cf):
        print("❌ 请先运行 entity_extractor.py")
        exit(1)
    with open(cf, "r", encoding="utf-8") as f:
        merged = json.load(f).get("merged", {})  # 加载合并后的实体/关系
    # 构建图谱
    g = build_graph(merged.get("entities", []), merged.get("relations", []))
    # 保存并可视化
    save_graph(g, config.GRAPH_CACHE)
    graph_to_html(g, config.GRAPH_VIZ_PATH)

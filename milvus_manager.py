# -*- coding: utf-8 -*-
from typing import List, Dict  # 导入类型提示，用于函数参数和返回值的类型注解

try:
    from pymilvus import Collection, connections  # 尝试从pymilvus导入集合和连接模块
except Exception:  # 捕获导入失败异常（通常是因为pymilvus未安装）
    Collection = None  # 如果导入失败，将Collection设为None
    connections = None  # 如果导入失败，将connections设为None


class MilvusManager:
    """Milvus向量数据库管理器"""  # 类的文档字符串，说明该类用于管理Milvus向量数据库

    def __init__(self, hosts: List[str], port: str):
        """初始化Milvus管理器，设置主机列表和端口"""  # 构造函数文档
        self.hosts = hosts  # Milvus服务器主机地址列表（支持多个主机实现高可用）
        self.port = port  # Milvus服务端口（通常是19530）
        self.collection = None  # Milvus集合实例，初始为None，连接成功后会赋值

    def connect(self) -> bool:
        """连接到Milvus数据库并加载集合，返回是否连接成功"""  # 连接方法文档
        if connections is None or Collection is None:  # 检查pymilvus是否可用
            print("[WARN] pymilvus 不可用")  # 打印警告信息
            return False  # 返回False表示连接失败

        for host in self.hosts:  # 遍历所有主机地址（支持故障转移）
            try:
                print(f"[INFO] 连接 Milvus: {host}:{self.port} ...")  # 打印正在连接的主机信息
                connections.connect(alias="default", host=host, port=self.port, timeout=5)  # 连接到Milvus，超时5秒
                self.collection = Collection("qa_embeddings")  # 获取名为"qa_embeddings"的集合
                self.collection.load()  # 将集合加载到内存中，提高查询性能
                print(f"[OK] Milvus 连接成功 | 数据量: {self.collection.num_entities} 条")  # 打印成功信息和数据条数
                return True  # 返回True表示连接成功
            except Exception as e:  # 捕获连接或加载过程中的异常
                print(f"   连接失败: {e}")  # 打印具体的失败原因

        self.collection = None  # 所有主机都连接失败，将集合设为None
        print("[WARN] Milvus 连接失败")  # 打印最终失败警告
        return False  # 返回False表示连接失败

    def vector_search(self, query_vector: List[float], limit: int) -> List[Dict]:
        """执行向量相似度搜索，返回匹配的结果列表"""  # 向量搜索方法文档
        if self.collection is None:  # 检查集合是否已加载
            return []  # 如果未加载，返回空列表

        try:
            results = self.collection.search(  # 执行Milvus向量搜索
                data=[query_vector],  # 查询向量列表，支持批量查询，这里只有一个
                anns_field="embedding",  # 指定存储向量的字段名
                param={"metric_type": "IP", "params": {"nprobe": 10}},  # 搜索参数：IP为内积相似度，nprobe为搜索聚类数
                limit=limit,  # 返回的最大结果数量
                output_fields=["question", "answer", "source"]  # 指定需要返回的标量字段
            )

            docs = []  # 创建空列表，用于存储搜索结果
            for hits in results:  # 遍历每个查询的结果（这里只有一个查询）
                for hit in hits:  # 遍历每个查询的命中结果
                    if hit.score > 0:  # 只保留相似度分数大于0的结果
                        docs.append({  # 将结果添加为字典格式
                            "question": hit.entity.get("question", ""),  # 获取问题文本，不存在则为空字符串
                            "answer": hit.entity.get("answer", ""),  # 获取答案文本，不存在则为空字符串
                            "source": hit.entity.get("source", ""),  # 获取来源，不存在则为空字符串
                            "vector_score": hit.score,  # 保留原始向量分数（重命名为vector_score）
                            "score": hit.score,  # 保留分数副本（便于统一排序）
                            "retrieval_method": "vector"  # 标识该结果来自向量检索
                        })
            return docs  # 返回结果列表
        except Exception as e:  # 捕获搜索过程中的异常
            print(f"向量搜索失败: {e}")  # 打印错误信息
            return []  # 返回空列表

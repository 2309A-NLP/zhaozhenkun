# -*- coding: utf-8 -*-
# 数据源(3个文件) -> 数据预处理 -> 向量化(BGE-M3) -> milvus存储(1024维) -> redis缓存 -> 本地备份
import json
# 导入json模块 用于处理json形式的数据文件
import hashlib
# 导入哈希库 用于生成数据的唯一ID(MD5加密)
from pathlib import Path
# 导入path类 用于面向对象的文件路径操作
from typing import List, Dict
# 导入类型提示 声明函数参数和返回值的类型
from datetime import datetime
# 导入时间模块 用于记录数据创建时间
import numpy as np
# 导入Numpy科学计算库
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
# 从milvus向量数据库导入所需组件
# connections:管理数据库链接
# collection:操作数据集合
# FieldSchema:定义字段结构
# CollectionSchema:定义集合结构
# DataType:字段数据类型
# utility:工具函数(如检查集合是否存在)
import redis
# 导入redis数据库 用于缓存
from sentence_transformers import SentenceTransformer


# 导入SentenceTransformer库 用于加载BGE-M3模型生成真实语义向量


class VectorIndexCreator:
    """向量索引创建器 - 使用BGE-M3模型和Milvus和Redis"""

    def __init__(self, data_dir: str):
        # 构建函数 接收数据目录路径参数
        self.data_dir = Path(data_dir)
        # 将字符串路径转换为Path对象 便于路径操作
        self.output_dir = self.data_dir / "vector_index"
        # 设置输出目录为数据目录下的vector_index文件夹
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # 创建输出目录 parents=True创建父目录 exist_ok=True存在时不报错

        # 加载BGE-M3模型（真实语义向量）
        self.load_bge_model()

        # 初始化Milvus
        self.init_milvus()

        # 初始化Redis
        self.init_redis()

        # 存储所有处理的数据
        self.all_data = []

    def load_bge_model(self):
        """加载BGE-M3模型生成真实语义向量"""
        print("🔄 正在加载 BGE-M3 模型...")
        try:
            # 加载BGE-M3模型 使用GPU加速(cuda)
            self.bge_model = SentenceTransformer(
                r"C:\Users\31326\Desktop\bge-m3",
                device="cuda"
            )
            self.vector_dim = 1024  # BGE-M3模型输出维度是1024
            print(f"✅ BGE-M3 加载成功 | 向量维度: {self.vector_dim} | 设备: cuda")
        except Exception as e:
            print(f"⚠️ BGE-M3 加载失败: {e}，将使用简单向量（不推荐）")
            self.bge_model = None
            self.vector_dim = 128  # 降级方案使用128维简单向量

    def init_milvus(self):
        """初始化Milvus连接"""
        try:
            connections.connect(
                alias="default",
                host='localhost',
                port='19530'
            )
            # alias:连接别名(用于多连接管理)
            # host:服务器地址
            # port:默认端口19530
            print("✅ Milvus 连接成功")
        except Exception as e:
            print(f"❌ Milvus 连接失败: {e}")
            raise

    def init_redis(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True,
                db=0
            )
            # port:redis默认端口6379
            # decode_responses:自动解码响应为字符串
            # db:选择数据库编号为0
            self.redis_client.ping()
            # 测试redis连接 如果连接失败会抛出异常
            print("✅ Redis 连接成功")
        except Exception as e:
            print(f"⚠️ Redis 连接失败: {e}")
            self.redis_client = None
            # 连接失败时设为None后续操作会跳过redis功能

    def create_real_embedding(self, text: str) -> List[float]:
        """
        使用BGE-M3模型生成真实的语义向量

        参数:
            text: 输入文本字符串

        返回:
            1024维的浮点数向量列表
        """
        if self.bge_model:
            # 使用BGE模型编码 normalize_embeddings=True使向量归一化（长度为1）
            vector = self.bge_model.encode(text, normalize_embeddings=True).tolist()
            return vector
        else:
            # 降级方案：使用简单哈希向量
            return self.create_simple_embedding(text, self.vector_dim)

    def create_simple_embedding(self, text: str, dimension: int = 128) -> List[float]:
        """
        创建简单的文本向量（降级方案，仅在BGE模型不可用时使用）

        参数:
            text: 要向量化的文本
            dimension: 向量维度 默认128

        返回:
            浮点数列表
        """
        # 使用文本的哈希值和长度创建简单向量
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        # 计算文本的MD5哈希 encode()将字符串转为字节 digest()返回16字节的哈希值

        # 生成dimension维度的向量
        vector = []
        for i in range(dimension):
            # 循环生成指定维度的向量

            # 使用哈希值和位置生成向量值
            val = (hash_bytes[i % 16] * (i + 1)) % 256 / 255.0
            # i % 16:循环使用16字节的哈希值
            # * (i + 1):乘上位置因子增加多样性
            # % 256:确保值在0-255范围
            # / 255.0:归一化到0-1范围
            vector.append(val)

        return vector

    def load_and_process_data(self):
        """加载并处理所有数据文件"""
        print("\n" + "=" * 50)
        print("开始加载数据")
        print("=" * 50)

        # 处理 eval.jsonl
        eval_file = self.data_dir / "eval.jsonl"
        if eval_file.exists():
            print("\n📄 处理 eval.jsonl...")
            data = self.process_jsonl_file(eval_file, "eval")
            self.all_data.extend(data)
            print(f"  ✓ 处理 {len(data)} 条数据")

        # 处理 r1_data_example.jsonl
        r1_file = self.data_dir / "r1_data_example.jsonl"
        if r1_file.exists():
            print("\n📄 处理 r1_data_example.jsonl...")
            data = self.process_jsonl_file(r1_file, "r1")
            self.all_data.extend(data)
            print(f"  ✓ 处理 {len(data)} 条数据")

        # 处理 SoulChatCorpus-sft-multi-Turn.json
        soulchat_file = self.data_dir / "SoulChatCorpus-sft-multi-Turn.json"
        if soulchat_file.exists():
            print("\n📄 处理 SoulChatCorpus-sft-multi-Turn.json...")
            data = self.process_soulchat_file(soulchat_file)
            self.all_data.extend(data)
            print(f"  ✓ 处理 {len(data)} 条数据")

        print(f"\n✅ 总共加载 {len(self.all_data)} 条数据")
        return self.all_data

    def process_jsonl_file(self, file_path: Path, source: str) -> List[Dict]:
        """处理JSONL文件"""
        processed_data = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    item = json.loads(line)

                    # 智能提取字段
                    question = (
                            item.get('question') or
                            item.get('instruction') or
                            item.get('prompt') or
                            item.get('query') or
                            item.get('input') or
                            ''
                    )

                    answer = (
                            item.get('answer') or
                            item.get('output') or
                            item.get('response') or
                            item.get('completion') or
                            ''
                    )

                    if question and answer:
                        record = {
                            'id': hashlib.md5(f"{source}_{line_num}_{question[:50]}".encode()).hexdigest(),
                            'source': source,
                            'question': question,
                            'answer': answer,
                            'context': item.get('context', item.get('history', '')),
                            'text_length': len(question) + len(answer),
                            'created_at': datetime.now().isoformat()
                        }
                        processed_data.append(record)

                except json.JSONDecodeError:
                    continue

        return processed_data

    def process_soulchat_file(self, file_path: Path) -> List[Dict]:
        """处理SoulChat文件"""
        processed_data = []

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)

                # 处理不同的数据结构
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict) and 'data' in data:
                    items = data['data']
                else:
                    items = [data] if isinstance(data, dict) else []

                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue

                    # 提取问答对
                    if 'instruction' in item and 'output' in item:
                        record = {
                            'id': hashlib.md5(f"soulchat_{idx}_{item['instruction'][:50]}".encode()).hexdigest(),
                            'source': 'SoulChatCorpus',
                            'question': item['instruction'],
                            'answer': item['output'],
                            'context': item.get('input', ''),
                            'text_length': len(item['instruction']) + len(item['output']),
                            'created_at': datetime.now().isoformat()
                        }
                        processed_data.append(record)

                    elif 'conversations' in item:
                        for conv in item['conversations']:
                            if isinstance(conv, dict):
                                question = conv.get('question', conv.get('user', ''))
                                answer = conv.get('answer', conv.get('assistant', ''))
                                if question and answer:
                                    record = {
                                        'id': hashlib.md5(f"soulchat_{idx}_{question[:50]}".encode()).hexdigest(),
                                        'source': 'SoulChatCorpus',
                                        'question': question,
                                        'answer': answer,
                                        'context': conv.get('context', ''),
                                        'text_length': len(question) + len(answer),
                                        'created_at': datetime.now().isoformat()
                                    }
                                    processed_data.append(record)

            except Exception as e:
                print(f"  处理错误: {e}")

        return processed_data

    def create_milvus_collection(self, collection_name: str = "qa_embeddings"):
        """创建Milvus集合 - 使用1024维向量（匹配BGE-M3）"""

        # 如果集合已存在，删除它（避免冲突）
        if utility.has_collection(collection_name):
            print(f"  删除已存在的集合: {collection_name}")
            utility.drop_collection(collection_name)

        # 定义集合结构
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            # 定义ID字段:字符串类型 最大长度64 设为主键
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50),
            # 定义来源字段:字符串类型 最大长度50
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2000),
            # 问题字段:字符串类型 最大长度2000
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=2000),
            # 答案字段:字符串类型 最大长度2000
            FieldSchema(name="context", dtype=DataType.VARCHAR, max_length=2000),
            # 上下文字段:字符串类型 最大长度2000
            FieldSchema(name="text_length", dtype=DataType.INT64),
            # 文本长度字段:64位整数类型
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim)
            # 向量字段:浮点数向量类型 维度为1024（BGE-M3）
        ]

        schema = CollectionSchema(fields, description="QA问答向量集合(BGE-M3 1024维)")
        collection = Collection(collection_name, schema)

        # 创建索引
        index_params = {
            "metric_type": "IP",  # 内积相似度（因为向量已归一化，IP等价于余弦相似度）
            "index_type": "IVF_FLAT",  # IVF_FLAT索引类型
            "params": {"nlist": 128}  # 聚类中心数量
        }
        collection.create_index("embedding", index_params)

        print(f"  ✅ 创建Milvus集合: {collection_name} | 向量维度: {self.vector_dim}")
        return collection

    def build_vector_index(self):
        """构建向量索引 - 使用BGE-M3生成真实语义向量"""
        if not self.all_data:
            print("❌ 没有数据可处理")
            return None

        print("\n" + "=" * 50)
        print(f"构建向量索引（使用BGE-M3 {self.vector_dim}维真实语义向量）")
        print("=" * 50)

        # 创建Milvus集合
        collection = self.create_milvus_collection()

        # 准备批量插入的数据
        batch_size = 100
        total_inserted = 0

        print(f"\n开始插入 {len(self.all_data)} 条数据到Milvus...")

        for i in range(0, len(self.all_data), batch_size):
            batch = self.all_data[i:i + batch_size]

            # 准备数据列表
            ids = []
            sources = []
            questions = []
            answers = []
            contexts = []
            text_lengths = []
            embeddings = []

            for item in batch:
                # 拼接问题和答案作为向量化的文本
                text_for_embedding = item['question'] + " " + item['answer']
                # 使用BGE-M3生成真实语义向量
                embedding = self.create_real_embedding(text_for_embedding)

                ids.append(item['id'])
                sources.append(item['source'])
                questions.append(item['question'][:2000])
                answers.append(item['answer'][:2000])
                contexts.append(item.get('context', '')[:2000])
                text_lengths.append(item['text_length'])
                embeddings.append(embedding)

            # 批量插入数据
            collection.insert([
                ids, sources, questions, answers, contexts, text_lengths, embeddings
            ])

            total_inserted += len(batch)
            print(f"  进度: {total_inserted}/{len(self.all_data)} ({total_inserted / len(self.all_data) * 100:.1f}%)")

        # 刷新数据，确保持久化到磁盘
        collection.flush()

        print(f"\n✅ 成功插入 {total_inserted} 条向量到Milvus")
        print(f"  集合名称: {collection.name}")
        print(f"  向量维度: {self.vector_dim} (BGE-M3 真实语义向量)")
        return collection

    def cache_to_redis(self):
        """缓存热门数据到Redis"""
        if not self.redis_client:
            print("⚠️ Redis未连接，跳过缓存")
            return

        print("\n" + "=" * 50)
        print("缓存数据到Redis")
        print("=" * 50)

        # 缓存前500条数据作为热门数据
        cache_count = min(500, len(self.all_data))

        for i, item in enumerate(self.all_data[:cache_count]):
            key = f"qa:{item['id']}"
            value = json.dumps({
                'question': item['question'],
                'answer': item['answer'],
                'source': item['source'],
                'cached_at': datetime.now().isoformat()
            }, ensure_ascii=False)

            # 设置24小时过期（86400秒）
            self.redis_client.setex(key, 86400, value)

            if (i + 1) % 100 == 0:
                print(f"  缓存进度: {i + 1}/{cache_count}")

        print(f"✅ 缓存 {cache_count} 条数据到Redis")

        # 缓存统计信息
        stats = {
            'total_records': len(self.all_data),
            'vector_dimension': self.vector_dim,
            'sources': {}
        }

        for item in self.all_data:
            source = item['source']
            stats['sources'][source] = stats['sources'].get(source, 0) + 1

        # 统计信息缓存1小时（3600秒）
        self.redis_client.setex("qa:stats", 3600, json.dumps(stats, ensure_ascii=False))
        print(f"✅ 缓存统计信息到Redis")

    def save_local_backup(self):
        """保存本地备份"""
        print("\n" + "=" * 50)
        print("保存本地备份")
        print("=" * 50)

        # 保存为JSON格式（美化格式）
        json_file = self.output_dir / "all_data.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 保存JSON: {json_file}")

        # 保存为JSONL格式（每行一个JSON对象，便于流式处理）
        jsonl_file = self.output_dir / "all_data.jsonl"
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            for item in self.all_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(f"✅ 保存JSONL: {jsonl_file}")

        # 保存统计报告
        report = {
            'created_at': datetime.now().isoformat(),
            'total_records': len(self.all_data),
            'vector_dimension': self.vector_dim,
            'sources': {}
        }

        for item in self.all_data:
            source = item['source']
            report['sources'][source] = report['sources'].get(source, 0) + 1

        report_file = self.output_dir / "index_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ 保存报告: {report_file}")

    def search_similar(self, query: str, top_k: int = 5):
        """搜索相似问题（使用BGE-M3真实语义向量）"""
        print("\n" + "=" * 50)
        print("搜索相似问题")
        print("=" * 50)
        print(f"查询: {query}")

        # 使用BGE-M3创建查询向量
        query_vector = self.create_real_embedding(query)

        collection_name = "qa_embeddings"
        if utility.has_collection(collection_name):
            collection = Collection(collection_name)
            collection.load()  # 加载到内存

            # 搜索参数
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}

            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["question", "answer", "source"]
            )

            print(f"\n找到 {len(results[0])} 个相关结果（基于BGE-M3语义向量）:")
            for i, hit in enumerate(results[0]):
                print(f"\n{i + 1}. 相似度: {hit.score:.4f}")
                print(f"   问题: {hit.entity.get('question')[:100]}...")
                print(f"   来源: {hit.entity.get('source')}")
        else:
            print("集合不存在，请先构建索引")


# 主程序
if __name__ == "__main__":
    # 设置数据目录
    DATA_DIR = r"C:\Users\31326\Desktop\adsd"

    # 创建向量索引构建器
    builder = VectorIndexCreator(DATA_DIR)

    # 1. 加载和处理数据
    data = builder.load_and_process_data()

    if data:
        # 2. 构建向量索引（Milvus）- 使用BGE-M3 1024维真实语义向量
        collection = builder.build_vector_index()

        # 3. 缓存到Redis
        builder.cache_to_redis()

        # 4. 保存本地备份
        builder.save_local_backup()

        # 5. 测试搜索（可选）
        print("\n" + "=" * 50)
        print("测试搜索功能（BGE-M3语义搜索）")
        print("=" * 50)
        test_query = "如何提高工作效率？"
        builder.search_similar(test_query, top_k=3)

        print("\n" + "=" * 50)
        print("✅ 所有任务完成！")
        print("=" * 50)
        print(f"\n📊 统计信息:")
        print(f"  总数据量: {len(data)}")
        print(f"  向量维度: {builder.vector_dim} (BGE-M3)")
        print(f"  Milvus向量: {collection.num_entities if collection else 0}")
        print(f"  Redis缓存: 已设置")
        print(f"  本地备份: {builder.output_dir}")
    else:
        print("❌ 没有数据可处理")
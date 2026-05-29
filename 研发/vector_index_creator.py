# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
# 数据源(3个文件) -> 数据预处理 -> 向量化(BGE-M3) -> milvus存储(1024维) -> redis缓存 -> 本地备份   # 整体处理流程概述
"""
向量索引创建器模块。

本模块实现完整的向量索引构建流程：
1. 加载数据：处理eval.jsonl、r1_data_example.jsonl、SoulChatCorpus三种格式的数据
2. 向量化：使用BGE-M3模型（1024维）生成真实语义向量（降级方案使用哈希向量）
3. Milvus存储：创建QA问答向量集合，批量插入向量数据
4. Redis缓存：将热门数据（前500条）缓存到Redis，设置24小时过期
5. 本地备份：保存JSON/JSONL格式备份及统计报告

包含VectorIndexCreator主类，整合BGE-M3 + Milvus + Redis三种组件。
"""
import json   # 导入json模块，用于处理JSON格式的数据文件
import hashlib   # 导入hashlib库，用于生成数据的唯一ID（MD5加密）
import os   # 导入os模块，用于读取环境变量
from pathlib import Path   # 从pathlib导入Path类，用于面向对象的文件路径操作
from typing import List, Dict   # 导入类型提示，声明函数参数和返回值的类型
from datetime import datetime   # 从datetime导入datetime类，用于记录数据创建时间
import numpy as np   # 导入NumPy科学计算库，用于数值计算
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
# 从pymilvus向量数据库导入所需组件：
# connections: 管理数据库连接
# Collection: 操作数据集合
# FieldSchema: 定义字段结构
# CollectionSchema: 定义集合结构
# DataType: 字段数据类型
# utility: 工具函数（如检查集合是否存在）
import redis   # 导入Redis数据库客户端，用于缓存热门数据
from sentence_transformers import SentenceTransformer   # 导入SentenceTransformer库，用于加载BGE-M3模型生成语义向量


class VectorIndexCreator:   # 定义VectorIndexCreator类
    """向量索引创建器 - 使用BGE-M3模型和Milvus和Redis"""   # 类的文档字符串

    def __init__(self, data_dir: str):   # 构造函数，接收数据目录路径参数
        self.data_dir = Path(data_dir)   # 将字符串路径转换为Path对象，便于路径操作
        self.output_dir = self.data_dir / "vector_index"   # 设置输出目录为数据目录下的vector_index文件夹
        self.output_dir.mkdir(parents=True, exist_ok=True)   # 创建输出目录（递归创建父目录，存在时不报错）

        # 加载BGE-M3模型（真实语义向量）   # 注释：初始化阶段加载嵌入模型
        self.load_bge_model()   # 调用加载BGE-M3模型的方法

        # 初始化Milvus   # 注释：初始化阶段连接Milvus数据库
        self.init_milvus()   # 调用初始化Milvus连接的方法

        # 初始化Redis   # 注释：初始化阶段连接Redis缓存
        self.init_redis()   # 调用初始化Redis连接的方法

        # 存储所有处理的数据   # 注释：初始化数据存储列表
        self.all_data = []   # 初始化空列表，用于存储所有处理后的数据

    def load_bge_model(self):   # 定义方法：加载BGE-M3模型
        """加载BGE-M3模型生成真实语义向量"""   # 方法文档字符串
        print("🔄 正在加载 BGE-M3 模型...")   # 打印加载中的提示
        try:   # 开始异常捕获
            # 加载BGE-M3模型 使用GPU加速(cuda)   # 注释：从相对路径加载模型，指定CUDA设备
            bge_path = os.getenv("BGE_M3_PATH", str(Path(__file__).resolve().parent.parent / "models" / "bge-m3"))
            self.bge_model = SentenceTransformer(   # 创建SentenceTransformer模型实例
                bge_path,   # BGE-M3模型路径（优先使用环境变量）
                device="cuda"   # 指定使用CUDA（GPU）加速推理
            )
            self.vector_dim = 1024   # BGE-M3模型输出维度固定为1024
            print(f"✅ BGE-M3 加载成功 | 向量维度: {self.vector_dim} | 设备: cuda")   # 打印成功信息
        except Exception as e:   # 如果加载失败
            print(f"⚠️ BGE-M3 加载失败: {e}，将使用简单向量（不推荐）")   # 打印警告信息
            self.bge_model = None   # 将模型设为None，后续使用降级方案
            self.vector_dim = 128   # 降级方案使用128维简单向量

    def init_milvus(self):   # 定义方法：初始化Milvus连接
        """初始化Milvus连接"""   # 方法文档字符串
        try:   # 开始异常捕获
            connections.connect(   # 建立与Milvus服务器的连接
                alias="default",   # 连接别名（用于多连接管理）
                host='localhost',   # 服务器地址为本地
                port='19530'   # Milvus默认端口19530
            )
            print("✅ Milvus 连接成功")   # 打印成功信息
        except Exception as e:   # 如果连接失败
            print(f"❌ Milvus 连接失败: {e}")   # 打印失败信息
            raise   # 抛出异常，阻止后续操作

    def init_redis(self):   # 定义方法：初始化Redis连接
        """初始化Redis连接"""   # 方法文档字符串
        try:   # 开始异常捕获
            self.redis_client = redis.Redis(   # 创建Redis客户端实例
                host='localhost',   # Redis服务器地址
                port=6379,   # Redis默认端口6379
                decode_responses=True,   # 自动解码响应为字符串（而非字节）
                db=0   # 选择数据库编号为0
            )
            self.redis_client.ping()   # 发送PING命令测试连接是否正常
            print("✅ Redis 连接成功")   # 打印成功信息
        except Exception as e:   # 如果连接失败
            print(f"⚠️ Redis 连接失败: {e}")   # 打印警告信息
            self.redis_client = None   # 连接失败时设为None，后续操作跳过Redis功能

    def create_real_embedding(self, text: str) -> List[float]:   # 定义方法：使用BGE-M3生成真实语义向量
        """
        使用BGE-M3模型生成真实的语义向量

        参数:
            text: 输入文本字符串

        返回:
            1024维的浮点数向量列表
        """   # 方法文档字符串
        if self.bge_model:   # 如果BGE模型已成功加载
            # 使用BGE模型编码 normalize_embeddings=True使向量归一化（长度为1）   # 注释：编码并归一化
            vector = self.bge_model.encode(text, normalize_embeddings=True).tolist()   # 编码文本并转为Python列表
            return vector   # 返回生成的向量
        else:   # 如果BGE模型不可用
            # 降级方案：使用简单哈希向量   # 注释：模型不可用时使用降级方案
            return self.create_simple_embedding(text, self.vector_dim)   # 调用简单向量生成方法

    def create_simple_embedding(self, text: str, dimension: int = 128) -> List[float]:   # 定义方法：创建简单哈希向量（降级方案）
        """
        创建简单的文本向量（降级方案，仅在BGE模型不可用时使用）

        参数:
            text: 要向量化的文本
            dimension: 向量维度 默认128

        返回:
            浮点数列表
        """   # 方法文档字符串
        # 使用文本的哈希值和长度创建简单向量   # 注释：基于MD5哈希生成确定性向量
        hash_obj = hashlib.md5(text.encode())   # 计算文本的MD5哈希对象
        hash_bytes = hash_obj.digest()   # 获取16字节的哈希值（二进制）

        # 生成dimension维度的向量   # 注释：循环生成指定维度的向量
        vector = []   # 初始化空向量列表
        for i in range(dimension):   # 循环dimension次，生成每个维度的值
            # 使用哈希值和位置生成向量值   # 注释：保证相同文本生成相同向量
            val = (hash_bytes[i % 16] * (i + 1)) % 256 / 255.0
            # i % 16: 循环使用16字节的哈希值
            # * (i + 1): 乘上位置因子增加多样性
            # % 256: 确保值在0-255范围
            # / 255.0: 归一化到0-1范围
            vector.append(val)   # 将计算值添加到向量列表

        return vector   # 返回生成的向量

    def load_and_process_data(self):   # 定义方法：加载并处理所有数据文件
        """加载并处理所有数据文件"""   # 方法文档字符串
        print("\n" + "=" * 50)   # 打印分隔线
        print("开始加载数据")   # 打印标题
        print("=" * 50)   # 打印分隔线

        # 处理 eval.jsonl   # 注释：处理评估数据集
        eval_file = self.data_dir / "eval.jsonl"   # 构建eval.jsonl文件路径
        if eval_file.exists():   # 如果文件存在
            print("\n📄 处理 eval.jsonl...")   # 打印处理提示
            data = self.process_jsonl_file(eval_file, "eval")   # 调用JSONL处理方法
            self.all_data.extend(data)   # 将处理结果添加到总数据列表
            print(f"  ✓ 处理 {len(data)} 条数据")   # 打印处理条数

        # 处理 r1_data_example.jsonl   # 注释：处理R1推理数据
        r1_file = self.data_dir / "r1_data_example.jsonl"   # 构建r1文件路径
        if r1_file.exists():   # 如果文件存在
            print("\n📄 处理 r1_data_example.jsonl...")   # 打印处理提示
            data = self.process_jsonl_file(r1_file, "r1")   # 调用JSONL处理方法
            self.all_data.extend(data)   # 将处理结果添加到总数据列表
            print(f"  ✓ 处理 {len(data)} 条数据")   # 打印处理条数

        # 处理 SoulChatCorpus-sft-multi-Turn.json   # 注释：处理SoulChat多轮对话数据
        soulchat_file = self.data_dir / "SoulChatCorpus-sft-multi-Turn.json"   # 构建SoulChat文件路径
        if soulchat_file.exists():   # 如果文件存在
            print("\n📄 处理 SoulChatCorpus-sft-multi-Turn.json...")   # 打印处理提示
            data = self.process_soulchat_file(soulchat_file)   # 调用SoulChat处理方法
            self.all_data.extend(data)   # 将处理结果添加到总数据列表
            print(f"  ✓ 处理 {len(data)} 条数据")   # 打印处理条数

        print(f"\n✅ 总共加载 {len(self.all_data)} 条数据")   # 打印总加载数据条数
        return self.all_data   # 返回所有加载的数据

    def process_jsonl_file(self, file_path: Path, source: str) -> List[Dict]:   # 定义方法：处理JSONL文件
        """处理JSONL文件"""   # 方法文档字符串
        processed_data = []   # 初始化处理后的数据列表

        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开文件
            for line_num, line in enumerate(f, 1):   # 逐行遍历并计数（从1开始）
                if not line.strip():   # 如果去除首尾空白后为空行
                    continue   # 跳过空行

                try:   # 开始异常捕获
                    item = json.loads(line)   # 解析当前行为JSON对象

                    # 智能提取字段   # 注释：从多种可能的字段名中智能提取问题和回答
                    question = (   # 提取问题字段，按优先级依次尝试
                            item.get('question') or   # 优先使用question字段
                            item.get('instruction') or   # 其次使用instruction字段
                            item.get('prompt') or   # 再次使用prompt字段
                            item.get('query') or   # 再次使用query字段
                            item.get('input') or   # 再次使用input字段
                            ''   # 所有字段都不存在则返回空字符串
                    )

                    answer = (   # 提取回答字段，按优先级依次尝试
                            item.get('answer') or   # 优先使用answer字段
                            item.get('output') or   # 其次使用output字段
                            item.get('response') or   # 再次使用response字段
                            item.get('completion') or   # 再次使用completion字段
                            ''   # 所有字段都不存在则返回空字符串
                    )

                    if question and answer:   # 如果问题且回答都不为空
                        record = {   # 构建统一格式的记录
                            'id': hashlib.md5(f"{source}_{line_num}_{question[:50]}".encode()).hexdigest(),
                            # 生成唯一ID：使用来源_行号_问题前50字符的MD5哈希
                            'source': source,   # 标记数据来源
                            'question': question,   # 保存问题文本
                            'answer': answer,   # 保存回答文本
                            'context': item.get('context', item.get('history', '')),   # 提取上下文或历史记录
                            'text_length': len(question) + len(answer),   # 计算问题+回答的总文本长度
                            'created_at': datetime.now().isoformat()   # 记录创建时间戳
                        }
                        processed_data.append(record)   # 将记录添加到结果列表

                except json.JSONDecodeError:   # 捕获JSON解析错误
                    continue   # 跳过无法解析的行

        return processed_data   # 返回处理后的数据列表

    def process_soulchat_file(self, file_path: Path) -> List[Dict]:   # 定义方法：处理SoulChat文件
        """处理SoulChat文件"""   # 方法文档字符串
        processed_data = []   # 初始化处理后的数据列表

        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开文件
            try:   # 开始异常捕获
                data = json.load(f)   # 加载整个JSON文件

                # 处理不同的数据结构   # 注释：SoulChat数据可能为列表或字典格式
                if isinstance(data, list):   # 如果根节点是列表
                    items = data   # 直接使用列表作为数据项
                elif isinstance(data, dict) and 'data' in data:   # 如果根节点是字典且有data字段
                    items = data['data']   # 从data字段获取数据列表
                else:   # 其他情况
                    items = [data] if isinstance(data, dict) else []   # 如果是单个字典则包装为列表，否则空列表

                for idx, item in enumerate(items):   # 遍历每条数据项
                    if not isinstance(item, dict):   # 如果数据项不是字典类型
                        continue   # 跳过

                    # 提取问答对   # 注释：从不同数据格式中提取问答对
                    if 'instruction' in item and 'output' in item:   # 如果是单轮instruction-output格式
                        record = {   # 构建统一格式记录
                            'id': hashlib.md5(f"soulchat_{idx}_{item['instruction'][:50]}".encode()).hexdigest(),
                            # 生成唯一ID：使用soulchat_索引_指令前50字符的MD5哈希
                            'source': 'SoulChatCorpus',   # 标记数据来源
                            'question': item['instruction'],   # 将instruction作为问题
                            'answer': item['output'],   # 将output作为回答
                            'context': item.get('input', ''),   # 提取输入作为上下文
                            'text_length': len(item['instruction']) + len(item['output']),   # 计算文本总长度
                            'created_at': datetime.now().isoformat()   # 记录创建时间戳
                        }
                        processed_data.append(record)   # 将记录添加到结果列表

                    elif 'conversations' in item:   # 如果是多轮conversations格式
                        for conv in item['conversations']:   # 遍历每一轮对话
                            if isinstance(conv, dict):   # 如果该轮对话是字典类型
                                question = conv.get('question', conv.get('user', ''))   # 提取用户问题
                                answer = conv.get('answer', conv.get('assistant', ''))   # 提取助手回答
                                if question and answer:   # 如果问题且回答都不为空
                                    record = {   # 构建统一格式记录
                                        'id': hashlib.md5(f"soulchat_{idx}_{question[:50]}".encode()).hexdigest(),
                                        # 生成唯一ID：使用soulchat_索引_问题前50字符的MD5哈希
                                        'source': 'SoulChatCorpus',   # 标记数据来源
                                        'question': question,   # 保存问题文本
                                        'answer': answer,   # 保存回答文本
                                        'context': conv.get('context', ''),   # 提取上下文
                                        'text_length': len(question) + len(answer),   # 计算文本总长度
                                        'created_at': datetime.now().isoformat()   # 记录创建时间戳
                                    }
                                    processed_data.append(record)   # 将记录添加到结果列表

            except Exception as e:   # 捕获处理过程中的任何异常
                print(f"  处理错误: {e}")   # 打印错误信息

        return processed_data   # 返回处理后的数据列表

    def create_milvus_collection(self, collection_name: str = "qa_embeddings"):   # 定义方法：创建Milvus集合
        """创建Milvus集合 - 使用1024维向量（匹配BGE-M3）"""   # 方法文档字符串

        # 如果集合已存在，删除它（避免冲突）   # 注释：先删除旧集合再新建，保证schema一致
        if utility.has_collection(collection_name):   # 检查集合是否已存在
            print(f"  删除已存在的集合: {collection_name}")   # 打印提示信息
            utility.drop_collection(collection_name)   # 删除已存在的集合

        # 定义集合结构   # 注释：定义集合的字段Schema
        fields = [   # 定义字段列表
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            # ID字段：字符串类型，最大长度64，设为主键
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50),
            # 来源字段：字符串类型，最大长度50
            FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2000),
            # 问题字段：字符串类型，最大长度2000
            FieldSchema(name="answer", dtype=DataType.VARCHAR, max_length=2000),
            # 答案字段：字符串类型，最大长度2000
            FieldSchema(name="context", dtype=DataType.VARCHAR, max_length=2000),
            # 上下文字段：字符串类型，最大长度2000
            FieldSchema(name="text_length", dtype=DataType.INT64),
            # 文本长度字段：64位整数类型
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.vector_dim)
            # 向量字段：浮点数向量类型，维度为self.vector_dim（BGE-M3为1024）
        ]

        schema = CollectionSchema(fields, description="QA问答向量集合(BGE-M3 1024维)")   # 创建集合Schema
        collection = Collection(collection_name, schema)   # 使用名称和Schema创建集合

        # 创建索引   # 注释：为向量字段创建索引以加速检索
        index_params = {   # 定义索引参数
            "metric_type": "IP",   # 内积相似度（因为向量已归一化，IP等价于余弦相似度）
            "index_type": "IVF_FLAT",   # IVF_FLAT索引类型（倒排文件索引）
            "params": {"nlist": 128}   # 聚类中心数量为128
        }
        collection.create_index("embedding", index_params)   # 在embedding字段上创建索引

        print(f"  ✅ 创建Milvus集合: {collection_name} | 向量维度: {self.vector_dim}")   # 打印成功信息
        return collection   # 返回创建的集合

    def build_vector_index(self):   # 定义方法：构建向量索引
        """构建向量索引 - 使用BGE-M3生成真实语义向量"""   # 方法文档字符串
        if not self.all_data:   # 如果没有数据
            print("❌ 没有数据可处理")   # 打印错误信息
            return None   # 返回None

        print("\n" + "=" * 50)   # 打印分隔线
        print(f"构建向量索引（使用BGE-M3 {self.vector_dim}维真实语义向量）")   # 打印标题
        print("=" * 50)   # 打印分隔线

        # 创建Milvus集合   # 注释：先创建或重建Milvus集合
        collection = self.create_milvus_collection()   # 调用创建集合方法

        # 准备批量插入的数据   # 注释：设置批量大小和计数器
        batch_size = 100   # 每批次插入100条数据
        total_inserted = 0   # 初始化已插入计数器

        print(f"\n开始插入 {len(self.all_data)} 条数据到Milvus...")   # 打印开始插入提示

        for i in range(0, len(self.all_data), batch_size):   # 按批次遍历所有数据
            batch = self.all_data[i:i + batch_size]   # 获取当前批次的数据切片

            # 准备数据列表   # 注释：初始化各字段的批量数据列表
            ids = []   # ID列表
            sources = []   # 来源列表
            questions = []   # 问题列表
            answers = []   # 回答列表
            contexts = []   # 上下文列表
            text_lengths = []   # 文本长度列表
            embeddings = []   # 向量列表

            for item in batch:   # 遍历批次中的每条记录
                # 拼接问题和答案作为向量化的文本   # 注释：问+答作为编码文本
                text_for_embedding = item['question'] + " " + item['answer']   # 拼接问题和回答
                # 使用BGE-M3生成真实语义向量   # 注释：调用向量生成方法
                embedding = self.create_real_embedding(text_for_embedding)   # 生成文本向量

                ids.append(item['id'])   # 添加ID
                sources.append(item['source'])   # 添加来源
                questions.append(item['question'][:2000])   # 添加问题（截取前2000字符）
                answers.append(item['answer'][:2000])   # 添加回答（截取前2000字符）
                contexts.append(item.get('context', '')[:2000])   # 添加上下文（截取前2000字符）
                text_lengths.append(item['text_length'])   # 添加文本长度
                embeddings.append(embedding)   # 添加向量

            # 批量插入数据   # 注释：将准备好的列表数据批量插入Milvus
            collection.insert([   # 调用insert方法批量插入
                ids, sources, questions, answers, contexts, text_lengths, embeddings   # 所有字段的列表
            ])

            total_inserted += len(batch)   # 累加已插入数量
            print(f"  进度: {total_inserted}/{len(self.all_data)} ({total_inserted / len(self.all_data) * 100:.1f}%)")
            # 打印插入进度百分比

        # 刷新数据，确保持久化到磁盘   # 注释：调用flush确保数据写入磁盘
        collection.flush()   # 刷新集合缓存

        print(f"\n✅ 成功插入 {total_inserted} 条向量到Milvus")   # 打印成功信息
        print(f"  集合名称: {collection.name}")   # 打印集合名称
        print(f"  向量维度: {self.vector_dim} (BGE-M3 真实语义向量)")   # 打印向量维度信息
        return collection   # 返回集合对象

    def cache_to_redis(self):   # 定义方法：缓存热门数据到Redis
        """缓存热门数据到Redis"""   # 方法文档字符串
        if not self.redis_client:   # 如果Redis未连接
            print("⚠️ Redis未连接，跳过缓存")   # 打印警告信息
            return   # 直接返回

        print("\n" + "=" * 50)   # 打印分隔线
        print("缓存数据到Redis")   # 打印标题
        print("=" * 50)   # 打印分隔线

        # 缓存前500条数据作为热门数据   # 注释：只缓存前500条，控制内存占用
        cache_count = min(500, len(self.all_data))   # 最多缓存500条

        for i, item in enumerate(self.all_data[:cache_count]):   # 遍历前cache_count条数据
            key = f"qa:{item['id']}"   # 构建Redis键名：qa:记录ID
            value = json.dumps({   # 构建要缓存的值（JSON格式）
                'question': item['question'],   # 问题文本
                'answer': item['answer'],   # 回答文本
                'source': item['source'],   # 数据来源
                'cached_at': datetime.now().isoformat()   # 缓存时间戳
            }, ensure_ascii=False)   # 保留中文

            # 设置24小时过期（86400秒）   # 注释：设置键的过期时间
            self.redis_client.setex(key, 86400, value)   # 写入Redis并设置过期时间

            if (i + 1) % 100 == 0:   # 每缓存100条打印一次进度
                print(f"  缓存进度: {i + 1}/{cache_count}")   # 打印缓存进度

        print(f"✅ 缓存 {cache_count} 条数据到Redis")   # 打印完成信息

        # 缓存统计信息   # 注释：构建并缓存数据统计信息
        stats = {   # 统计信息字典
            'total_records': len(self.all_data),   # 总记录数
            'vector_dimension': self.vector_dim,   # 向量维度
            'sources': {}   # 来源分布（空字典，下面填充）
        }

        for item in self.all_data:   # 遍历所有数据，统计来源分布
            source = item['source']   # 获取数据来源
            stats['sources'][source] = stats['sources'].get(source, 0) + 1   # 累加各来源的计数

        # 统计信息缓存1小时（3600秒）   # 注释：统计信息设置较短过期时间
        self.redis_client.setex("qa:stats", 3600, json.dumps(stats, ensure_ascii=False))   # 缓存统计信息
        print(f"✅ 缓存统计信息到Redis")   # 打印成功信息

    def save_local_backup(self):   # 定义方法：保存本地备份
        """保存本地备份"""   # 方法文档字符串
        print("\n" + "=" * 50)   # 打印分隔线
        print("保存本地备份")   # 打印标题
        print("=" * 50)   # 打印分隔线

        # 保存为JSON格式（美化格式）   # 注释：保存为格式化的JSON文件
        json_file = self.output_dir / "all_data.json"   # 构建JSON文件路径
        with open(json_file, 'w', encoding='utf-8') as f:   # 以写入模式、UTF-8编码打开
            json.dump(self.all_data, f, ensure_ascii=False, indent=2)   # 写入JSON（保留中文，缩进2空格）
        print(f"✅ 保存JSON: {json_file}")   # 打印成功信息

        # 保存为JSONL格式（每行一个JSON对象，便于流式处理）   # 注释：保存为逐行JSON格式
        jsonl_file = self.output_dir / "all_data.jsonl"   # 构建JSONL文件路径
        with open(jsonl_file, 'w', encoding='utf-8') as f:   # 以写入模式、UTF-8编码打开
            for item in self.all_data:   # 遍历每条数据
                f.write(json.dumps(item, ensure_ascii=False) + '\n')   # 每行写入一个JSON对象
        print(f"✅ 保存JSONL: {jsonl_file}")   # 打印成功信息

        # 保存统计报告   # 注释：生成并保存统计报告
        report = {   # 报告字典
            'created_at': datetime.now().isoformat(),   # 报告生成时间
            'total_records': len(self.all_data),   # 总记录数
            'vector_dimension': self.vector_dim,   # 向量维度
            'sources': {}   # 来源分布（空字典，下面填充）
        }

        for item in self.all_data:   # 遍历所有数据，统计来源分布
            source = item['source']   # 获取数据来源
            report['sources'][source] = report['sources'].get(source, 0) + 1   # 累加各来源的计数

        report_file = self.output_dir / "index_report.json"   # 构建报告文件路径
        with open(report_file, 'w', encoding='utf-8') as f:   # 以写入模式、UTF-8编码打开
            json.dump(report, f, ensure_ascii=False, indent=2)   # 写入报告JSON
        print(f"✅ 保存报告: {report_file}")   # 打印成功信息

    def search_similar(self, query: str, top_k: int = 5):   # 定义方法：搜索相似问题
        """搜索相似问题（使用BGE-M3真实语义向量）"""   # 方法文档字符串
        print("\n" + "=" * 50)   # 打印分隔线
        print("搜索相似问题")   # 打印标题
        print("=" * 50)   # 打印分隔线
        print(f"查询: {query}")   # 打印查询文本

        # 使用BGE-M3创建查询向量   # 注释：将查询文本转换为向量
        query_vector = self.create_real_embedding(query)   # 生成查询向量

        collection_name = "qa_embeddings"   # 集合名称
        if utility.has_collection(collection_name):   # 如果集合存在
            collection = Collection(collection_name)   # 获取集合对象
            collection.load()   # 加载集合到内存

            # 搜索参数   # 注释：设置向量检索参数
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}   # 内积度量 + 聚类搜索数量

            results = collection.search(   # 执行向量相似度搜索
                data=[query_vector],   # 查询向量列表
                anns_field="embedding",   # 指定搜索的向量字段
                param=search_params,   # 搜索参数
                limit=top_k,   # 返回前k个最相似结果
                output_fields=["question", "answer", "source"]   # 需要返回的字段
            )

            print(f"\n找到 {len(results[0])} 个相关结果（基于BGE-M3语义向量）:")   # 打印结果数量
            for i, hit in enumerate(results[0]):   # 遍历搜索结果
                print(f"\n{i + 1}. 相似度: {hit.score:.4f}")   # 打印相似度分数
                print(f"   问题: {hit.entity.get('question')[:100]}...")   # 打印问题前100字符
                print(f"   来源: {hit.entity.get('source')}")   # 打印来源
        else:   # 如果集合不存在
            print("集合不存在，请先构建索引")   # 提示先构建索引


# 主程序   # 注释：以下为脚本直接运行时的入口
if __name__ == "__main__":   # 判断是否直接运行此脚本（而非被导入）
    # 设置数据目录   # 注释：自动获取项目根目录
    DATA_DIR = str(Path(__file__).resolve().parent.parent)   # 数据目录路径（自动适配本地和远程环境）

    # 创建向量索引构建器   # 注释：实例化VectorIndexCreator
    builder = VectorIndexCreator(DATA_DIR)   # 创建向量索引构建器实例

    # 1. 加载和处理数据   # 注释：第一步：加载并处理所有数据文件
    data = builder.load_and_process_data()   # 调用数据加载方法

    if data:   # 如果成功加载到数据
        # 2. 构建向量索引（Milvus）- 使用BGE-M3 1024维真实语义向量   # 注释：第二步：向量化并存入Milvus
        collection = builder.build_vector_index()   # 调用构建向量索引方法

        # 3. 缓存到Redis   # 注释：第三步：热门数据缓存到Redis
        builder.cache_to_redis()   # 调用Redis缓存方法

        # 4. 保存本地备份   # 注释：第四步：保存JSON/JSONL本地备份
        builder.save_local_backup()   # 调用本地备份方法

        # 5. 测试搜索（可选）   # 注释：第五步：测试向量相似度搜索功能
        print("\n" + "=" * 50)   # 打印分隔线
        print("测试搜索功能（BGE-M3语义搜索）")   # 打印标题
        print("=" * 50)   # 打印分隔线
        test_query = "如何提高工作效率？"   # 测试查询文本
        builder.search_similar(test_query, top_k=3)   # 执行搜索测试

        print("\n" + "=" * 50)   # 打印分隔线
        print("✅ 所有任务完成！")   # 打印完成信息
        print("=" * 50)   # 打印分隔线
        print(f"\n📊 统计信息:")   # 打印统计标题
        print(f"  总数据量: {len(data)}")   # 打印总数据量
        print(f"  向量维度: {builder.vector_dim} (BGE-M3)")   # 打印向量维度
        print(f"  Milvus向量: {collection.num_entities if collection else 0}")   # 打印Milvus中的实体数
        print(f"  Redis缓存: 已设置")   # 打印Redis缓存状态
        print(f"  本地备份: {builder.output_dir}")   # 打印备份目录
    else:   # 如果没有数据
        print("❌ 没有数据可处理")   # 打印错误信息

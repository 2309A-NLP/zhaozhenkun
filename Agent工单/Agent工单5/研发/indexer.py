# -*- coding: utf-8 -*-
"""
indexer.py — 招股书文档索引器
功能：加载80个TXT文件 → 文本分块 → 构建TF-IDF索引 → 缓存到磁盘
      首次运行建立索引，后续运行直接加载缓存（<1秒）
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
"""

import os  # 文件系统操作
import re  # 正则表达式
import json  # JSON序列化
import pickle  # Python对象序列化
import time  # 计时
import logging  # 日志
import warnings  # 警告控制
import config  # 配置文件

logger = logging.getLogger(__name__)  # 模块日志器
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")  # 抑制sklearn版本警告


def load_documents(pdf_txt_dir):
    """加载目录下所有TXT文件，返回文件名→文本内容的字典"""
    documents = {}  # 文件名 -> 文本内容
    txt_files = sorted([f for f in os.listdir(pdf_txt_dir) if f.endswith('.txt')])  # 获取所有TXT并排序
    logger.info("发现 %d 个TXT文件", len(txt_files))  # 日志
    for fname in txt_files:  # 遍历每个文件
        filepath = os.path.join(pdf_txt_dir, fname)  # 拼接完整路径
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:  # 打开文件
                text = f.read()  # 读取全部文本
            if len(text) > 100:  # 只保留有实质内容的文件（>100字符）
                documents[fname] = text  # 存入字典
        except Exception as e:  # 读取失败
            logger.warning("无法读取 %s: %s", fname, e)  # 警告日志
    logger.info("成功加载 %d 个有效文档", len(documents))  # 日志
    return documents  # 返回文档字典


def clean_text(text):
    """清洗文本：去除多余空白、页码、特殊字符"""
    text = re.sub(r'\s+', ' ', text)  # 合并所有空白为单个空格
    text = re.sub(r'[‐-]+', '', text)  # 去除连字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)  # 去除控制字符
    return text.strip()  # 去除首尾空白


def chunk_text(text, chunk_size=1200, overlap=200):
    """将长文本按自然段落边界分割为重叠的块"""
    paragraphs = re.split(r'\n\s*\n|(?<=[。！？])\s*(?=[一-鿿一二三四五六七八九十])', text)  # 按段落/句号分割
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 20]  # 过滤短段落
    chunks = []  # 存储文本块
    current_chunk = ""  # 当前正在构建的块
    current_len = 0  # 当前块长度
    for para in paragraphs:  # 遍历段落
        para_len = len(para)  # 段落长度
        if current_len + para_len > chunk_size and current_len > 0:  # 超限
            chunks.append(current_chunk.strip())  # 保存当前块
            if len(current_chunk) > overlap:  # 保留重叠
                overlap_start = len(current_chunk) - overlap  # overlap起始位置
                for sep in ['。', '！', '？', '；', '\n']:  # 句子分隔符
                    idx = current_chunk.rfind(sep, overlap_start - 100, overlap_start + 100)  # 找分隔符
                    if idx > 0:  # 找到了
                        overlap_start = idx + 1  # 从分隔符后开始
                        break  # 用第一个找到的分隔符
                current_chunk = current_chunk[overlap_start:]  # 保留末尾作为重叠
                current_len = len(current_chunk)  # 更新长度
            else:
                current_chunk = ""  # 块太短，不留重叠
                current_len = 0  # 重置
        current_chunk += para  # 添加段落
        current_len += para_len  # 更新长度
    if current_chunk.strip():  # 最后一块不为空
        chunks.append(current_chunk.strip())  # 保存最后一块
    return chunks  # 返回文本块列表


def build_index(documents, chunk_size=1200, overlap=200):
    """对文档集合进行分块和TF-IDF索引构建"""
    from sklearn.feature_extraction.text import TfidfVectorizer  # TF-IDF向量化器
    logger.info("正在分块...")  # 日志
    all_chunks = []  # 存储所有文本块
    chunk_metadata = []  # 存储每块的元数据
    for doc_name, text in documents.items():  # 遍历每个文档
        cleaned = clean_text(text)  # 清洗文本
        chunks = chunk_text(cleaned, chunk_size, overlap)  # 分块
        for i, chunk in enumerate(chunks):  # 遍历每个块
            all_chunks.append(chunk)  # 添加到块列表
            chunk_metadata.append({"source": doc_name, "chunk_id": i})  # 记录元数据
    logger.info("共生成 %d 个文本块", len(all_chunks))  # 日志
    logger.info("正在构建TF-IDF索引...")  # 日志
    vectorizer = TfidfVectorizer(  # 创建TF-IDF向量化器
        analyzer='char_wb',  # 字符级n-gram（适合中文）
        ngram_range=config.NGRAM_RANGE,  # n-gram范围
        max_features=config.MAX_FEATURES,  # 最大特征数
        sublinear_tf=True,  # 1+log(tf)平滑
        max_df=0.8,  # 忽略高频词
        min_df=2  # 忽略仅1文档的词
    )
    chunk_vectors = vectorizer.fit_transform(all_chunks)  # 计算TF-IDF矩阵
    logger.info("词汇表: %d, 矩阵: %s", len(vectorizer.vocabulary_), chunk_vectors.shape)  # 日志
    return vectorizer, chunk_vectors, all_chunks, chunk_metadata  # 返回索引组件


def build_company_index(all_chunks, chunk_metadata):
    """从每份招股书提取公司全名，构建 公司全名→文件名 映射"""
    company_map = {}  # 公司全名 → 文件名
    seen_files = set()  # 已处理文件
    for i, meta in enumerate(chunk_metadata):  # 遍历元数据
        fname = meta["source"]  # 文件名
        if fname in seen_files:  # 已处理
            continue  # 跳过
        seen_files.add(fname)  # 标记
        full_name = None  # 公司全名
        for j in range(min(50, len(all_chunks) - i)):  # 检查前50块
            chunk_text = all_chunks[i + j]  # 当前块
            m = re.search(r'公司名称[：:]\s*([一-龥]{6,}(?:股份|有限|集团)\S{0,6})', chunk_text)  # 公司名称：全名
            if m:  # 找到
                full_name = m.group(1).strip()  # 取全名
                break  # 停止
            m = re.search(r'([一-龥]{6,}(?:股份有限公司|有限责任公司|有限公司))', chunk_text)  # 公司全名模式
            if m and '本公司' not in m.group(1):  # 排除"本公司"
                full_name = m.group(1).strip()  # 取全名
                break  # 停止
        if full_name:  # 找到公司名
            company_map[full_name] = fname  # 全名→文件（主key）
            if len(full_name) >= 10:  # 全名够长
                short = full_name[-10:]  # 后10字
                if short not in company_map:  # 不冲突
                    company_map[short] = fname  # 辅助key
    logger.info("公司名映射: %d 条", len(company_map))  # 日志
    return company_map  # 返回映射


def save_index(vectorizer, chunk_vectors, all_chunks, chunk_metadata, cache_dir):
    """将索引保存到磁盘（加速后续启动）"""
    logger.info("正在缓存索引...")  # 日志
    import sklearn  # sklearn版本
    with open(os.path.join(cache_dir, "sklearn_version.txt"), "w") as f:  # 版本文件
        f.write(sklearn.__version__)  # 写版本
    cfg_fp = f"{config.CHUNK_SIZE}_{config.CHUNK_OVERLAP}_{config.MAX_FEATURES}_{config.NGRAM_RANGE}"  # 指纹
    with open(os.path.join(cache_dir, "config_fingerprint.txt"), "w") as f:  # 指纹文件
        f.write(cfg_fp)  # 写指纹
    company_map = build_company_index(all_chunks, chunk_metadata)  # 构建映射
    with open(os.path.join(cache_dir, "company_map.json"), "w", encoding="utf-8") as f:  # 映射文件
        json.dump(company_map, f, ensure_ascii=False)  # JSON
    from scipy import sparse  # 稀疏矩阵
    sparse.save_npz(os.path.join(cache_dir, "chunk_vectors.npz"), chunk_vectors)  # TF-IDF矩阵
    with open(os.path.join(cache_dir, "vectorizer.pkl"), "wb") as f:  # 向量化器
        pickle.dump(vectorizer, f)  # 序列化
    with open(os.path.join(cache_dir, "chunks.json"), "w", encoding="utf-8") as f:  # 文本块
        json.dump(all_chunks, f, ensure_ascii=False)  # JSON
    with open(os.path.join(cache_dir, "metadata.json"), "w", encoding="utf-8") as f:  # 元数据
        json.dump(chunk_metadata, f, ensure_ascii=False)  # JSON
    logger.info("索引已缓存到: %s", cache_dir)  # 日志


def load_index(cache_dir):
    """从磁盘加载已缓存的索引（检测sklearn版本，不兼容则返回None）"""
    import sklearn  # sklearn版本检测
    ver_file = os.path.join(cache_dir, "sklearn_version.txt")  # 版本文件
    if os.path.exists(ver_file):  # 有记录
        with open(ver_file, "r") as f:  # 读取
            cached_ver = f.read().strip()  # 缓存版本
        if cached_ver != sklearn.__version__:  # 版本变更
            logger.info("sklearn版本变更(%s→%s)，自动重建索引", cached_ver, sklearn.__version__)  # 日志
            return None  # 触发重建
    from scipy import sparse  # 稀疏矩阵
    logger.info("正在加载缓存索引...")  # 日志
    chunk_vectors = sparse.load_npz(os.path.join(cache_dir, "chunk_vectors.npz"))  # TF-IDF矩阵
    with open(os.path.join(cache_dir, "vectorizer.pkl"), "rb") as f:  # 向量化器
        vectorizer = pickle.load(f)  # 反序列化
    with open(os.path.join(cache_dir, "chunks.json"), "r", encoding="utf-8") as f:  # 文本块
        all_chunks = json.load(f)  # JSON
    with open(os.path.join(cache_dir, "metadata.json"), "r", encoding="utf-8") as f:  # 元数据
        chunk_metadata = json.load(f)  # JSON
    company_map = {}  # 默认空
    cmap_path = os.path.join(cache_dir, "company_map.json")  # 映射路径
    if os.path.exists(cmap_path):  # 存在
        with open(cmap_path, "r", encoding="utf-8") as f:  # 加载
            company_map = json.load(f)  # JSON
    logger.info("加载完成: %d块, %d词汇, %d家公司", len(all_chunks), len(vectorizer.vocabulary_), len(company_map))  # 日志
    return vectorizer, chunk_vectors, all_chunks, chunk_metadata, company_map  # 返回


def index_exists(cache_dir):
    """检查索引缓存是否已存在"""
    required = ["chunk_vectors.npz", "vectorizer.pkl", "chunks.json", "metadata.json",
                "sklearn_version.txt", "company_map.json"]  # 必需文件
    return all(os.path.exists(os.path.join(cache_dir, f)) for f in required)  # 全部存在


def get_or_build_index(pdf_txt_dir, cache_dir, chunk_size=1200, overlap=200):
    """获取索引：有缓存就加载，没缓存或不兼容就构建"""
    if index_exists(cache_dir):  # 缓存存在
        result = load_index(cache_dir)  # 尝试加载
        if result is not None:  # 加载成功
            return result  # 返回
        import shutil  # 文件操作
        shutil.rmtree(cache_dir, ignore_errors=True)  # 删旧缓存
        os.makedirs(cache_dir, exist_ok=True)  # 重建目录
    logger.info("首次运行，正在构建招股书索引...")  # 日志
    t0 = time.time()  # 计时
    documents = load_documents(pdf_txt_dir)  # 加载80个TXT
    vectorizer, chunk_vectors, all_chunks, chunk_metadata = build_index(documents, chunk_size, overlap)  # 构建索引
    company_map = build_company_index(all_chunks, chunk_metadata)  # 公司名映射
    save_index(vectorizer, chunk_vectors, all_chunks, chunk_metadata, cache_dir)  # 保存
    logger.info("索引构建完成，耗时 %.1f 秒", time.time() - t0)  # 日志
    return vectorizer, chunk_vectors, all_chunks, chunk_metadata, company_map  # 返回


if __name__ == "__main__":  # 测试
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # 简易日志配置
    result = get_or_build_index(config.PDF_TXT_DIR, config.INDEX_CACHE_DIR, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    logger.info("块数: %d, 词表: %d", len(result[2]), len(result[0].vocabulary_))  # 打印

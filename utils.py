# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

import hashlib
# 导入hashlib模块，用于生成哈希值（如SHA1、MD5等加密哈希函数）

import re
# 导入re模块，提供正则表达式支持，用于文本模式匹配和字符串处理

import socket
# 导入socket模块，用于网络通信，这里主要用来获取本机IP地址

from datetime import datetime
# 从datetime模块导入datetime类，用于处理日期和时间

from typing import List
# 从typing模块导入List类型，用于类型注解，表示列表类型

import numpy as np

# 导入numpy库并重命名为np，用于数值计算、数组操作和数学运算

try:
    import jieba
except Exception:
    jieba = None


# 尝试导入jieba中文分词库，如果失败（未安装），则将jieba设为None，避免程序崩溃


def normalize_username(username: str) -> str:
    # 定义用户名规范化函数，接收用户名字符串，返回规范化后的字符串

    cleaned = (username or "").strip()
    # 如果username为None或空，则用空字符串替代，然后去除首尾空白字符

    return cleaned[:32] if cleaned else f"guest-{datetime.now().strftime('%H%M%S')}"
    # 如果cleaned不为空，返回前32个字符（限制用户名最大长度）
    # 如果cleaned为空，生成guest-加上当前时间（时:分:秒）的默认用户名


def tokenize_text(text: str) -> List[str]:
    # 定义文本分词函数，接收文本字符串，返回分词后的字符串列表

    if not text:
        # 如果文本为空或None

        return []
        # 返回空列表

    if jieba is None:
        # 如果jieba分词库未安装

        return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)
        # 使用正则表达式分词：
        # [A-Za-z0-9_]+ 匹配英文单词、数字、下划线（连续的字母数字下划线）
        # | 或
        # [\u4e00-\u9fff] 匹配中文字符（Unicode范围：基本汉字到扩展A区）
        # findall返回所有匹配的字符串列表

    return [token.strip() for token in jieba.cut(text) if token.strip()]
    # 使用jieba进行中文分词
    # jieba.cut(text) 返回生成器，产生分词结果
    # token.strip() 去除每个词首尾空白
    # if token.strip() 过滤空字符串
    # 返回处理后的分词列表


def cosine_similarity_np(vec_a: List[float], vec_b: List[float]) -> float:
    # 计算两个向量的余弦相似度，接收两个浮点数列表，返回相似度值（-1到1之间的浮点数）

    array_a = np.array(vec_a, dtype=float)
    # 将第一个向量转换为numpy数组，指定数据类型为浮点数

    array_b = np.array(vec_b, dtype=float)
    # 将第二个向量转换为numpy数组，指定数据类型为浮点数

    norm_a = np.linalg.norm(array_a)
    # 计算第一个向量的L2范数（欧几里得范数），即向量各元素平方和的平方根

    norm_b = np.linalg.norm(array_b)
    # 计算第二个向量的L2范数

    if norm_a == 0 or norm_b == 0:
        # 如果任一向量为零向量（范数为0）

        return 0.0
        # 返回0.0，表示没有相似度（余弦相似度公式中分母不能为0）

    return float(np.dot(array_a, array_b) / (norm_a * norm_b))
    # 计算余弦相似度 = (A·B) / (|A| * |B|)
    # np.dot()计算两个向量的点积
    # 除以范数的乘积得到余弦值
    # 将结果转为Python float类型返回


def reduce_dimension(embedding: List[float], target_dim: int) -> List[float]:
    # 定义降维函数，将向量降维或升维到目标维度
    # embedding: 原始向量（浮点数列表）
    # target_dim: 目标维度

    if len(embedding) == target_dim:
        # 如果原始维度已经等于目标维度

        return embedding
        # 直接返回原向量，无需处理

    array = np.array(embedding, dtype=float)
    # 将向量转换为numpy数组，指定浮点数类型

    if len(array) < target_dim:
        # 如果原始维度小于目标维度（需要升维）

        reduced = np.interp(
            # 使用线性插值方法增加维度
            np.linspace(0, 1, target_dim),
            # x坐标：目标维度的等间距点（0到1之间target_dim个点）
            np.linspace(0, 1, len(array)),
            # x坐标：原始维度的等间距点（0到1之间原始维度个点）
            array,
            # y坐标：原始向量的值
        )
        # np.interp()根据原始数据点进行线性插值，生成目标维度的新向量

    else:
        # 如果原始维度大于目标维度（需要降维）

        group_size = max(1, len(array) // target_dim)
        # 计算每组大小：原始维度除以目标维度，至少为1
        # 例如：原始1024维，目标256维，则每4个元素平均成1个

        reduced = array[: target_dim * group_size].reshape(target_dim, group_size).mean(axis=1)
        # array[: target_dim * group_size] 截取能完整分组的元素
        # reshape(target_dim, group_size) 重塑为target_dim行，group_size列的二维数组
        # mean(axis=1) 按行计算平均值，每行group_size个元素求平均，得到target_dim个值

    norm = np.linalg.norm(reduced)
    # 计算降维/升维后向量的L2范数

    return (reduced / norm).tolist() if norm > 0 else reduced.tolist()
    # 如果范数大于0，进行归一化处理（除以范数），然后转为Python列表返回
    # 如果范数为0（零向量），直接转为列表返回


def generate_doc_id(question: str, answer: str, source: str = "") -> str:
    # 生成文档唯一ID，用于标识问答对
    # question: 用户问题
    # answer: 系统回答
    # source: 来源，默认为空字符串

    return hashlib.sha1(f"{question}|{answer}|{source}".encode("utf-8")).hexdigest()
    # 使用SHA1哈希算法生成文档ID
    # f"{question}|{answer}|{source}" 将三个字符串用竖线分隔拼接
    # .encode("utf-8") 将字符串编码为UTF-8字节序列
    # hashlib.sha1() 创建SHA1哈希对象
    # .hexdigest() 返回16进制表示的哈希字符串（40个字符）


def get_local_ip() -> str:
    # 获取本机局域网IP地址函数

    try:
        # 尝试获取IP地址

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 创建UDP套接字
        # AF_INET: IPv4地址族
        # SOCK_DGRAM: UDP协议（数据报套接字）

        sock.connect(("8.8.8.8", 80))
        # 连接到Google的公共DNS服务器（不发送数据，只是建立虚拟连接）
        # 这样系统会选择一个本地IP地址作为出口IP

        ip = sock.getsockname()[0]
        # getsockname()返回套接字绑定的地址，格式为(ip, port)
        # [0]取出IP地址字符串

        sock.close()
        # 关闭套接字，释放资源

        return ip
        # 返回获取到的IP地址

    except Exception:
        # 如果任何步骤出错（如无网络连接）

        return "127.0.0.1"
        # 返回本地回环地址作为默认值
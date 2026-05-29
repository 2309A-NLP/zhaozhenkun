# -*- coding: utf-8 -*-
"""
ADSD 在线服务 - 大模型输出优化器模块
负责优化大语言模型生成的回答内容
主要功能：
1. 去除冗余文本：移除"总的来说"、"综上所述"等套话
2. 格式美化：合并多余换行和空格
3. 添加参考来源：根据检索结果的相关性分数，在回答末尾添加知识来源标注
4. 过长回答截断：对简短问题对应的过长回答进行截断
"""
import re  # 导入正则表达式模块，用于字符串模式匹配和替换
from typing import List, Dict  # 导入类型提示，用于函数参数和返回值的类型注解


class LLMOutputOptimizer:
    """大模型输出优化器"""  # 类的文档字符串，说明该类用于优化大模型的输出内容

    def __init__(self):
        """初始化优化器，定义需要移除的冗余文本模式"""  # 构造函数文档
        self.redundant_patterns = [  # 冗余文本模式列表，存储需要移除的常见套话和结尾句
            r"总的来说[：:，, ]*",  # 匹配"总的来说"及其后的冒号、逗号等标点（中英文）
            r"综上所述[：:，, ]*",  # 匹配"综上所述"及其后的标点符号
            r"如果你还有其他问题.*$",  # 匹配"如果你还有其他问题"及其后的所有内容直到行尾
            r"欢迎继续提问.*$"  # 匹配"欢迎继续提问"及其后的所有内容直到行尾
        ]

    def optimize(self, answer: str, question: str, context: List[Dict]) -> str:
        """优化大模型输出，去除冗余、格式化文本并添加参考来源"""
        optimized = answer or ""  # 如果answer为空则用空字符串代替，作为优化的起始文本
        for pattern in self.redundant_patterns:  # 遍历所有冗余模式
            optimized = re.sub(pattern, "", optimized, flags=re.IGNORECASE | re.MULTILINE)  # 使用正则替换移除匹配的冗余文本（忽略大小写、多行匹配）
        optimized = re.sub(r"\n{3,}", "\n\n", optimized).strip()  # 将连续3个以上的换行符替换为2个换行符，并去除首尾空白
        optimized = re.sub(r"[ \t]{2,}", " ", optimized)  # 将连续2个以上的空格或制表符替换为单个空格

        if context and "[参考]" not in optimized:  # 如果有检索上下文且优化后的文本中还没有参考标记
            best = context[0]  # 获取最相关（分数最高）的检索结果
            # 检查向量分数是否大于0.55 或 融合分数是否大于0.02（阈值用于判断知识是否足够相关）
            if best.get("score", 0) > 0.55 or best.get("fusion_score", 0) > 0.02:
                # 在回答末尾添加参考来源，格式为"[参考] 来源名称"
                optimized = f"{optimized}\n\n[参考] {best.get('source', '知识库')}"

        # 如果问题长度小于18个字符（简短短问）且优化后的回答长度超过600字
        if len(question) < 18 and len(optimized) > 600:
            optimized = optimized[:600].rstrip() + "..."  # 截取前600个字符，去除尾部空白，然后添加省略号

        return optimized or "暂时没有生成有效回答。"  # 如果优化后为空则返回默认提示，否则返回优化结果

# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
"""专门处理三种特殊格式数据的处理器——多源数据格式统一处理器。"""   # 模块文档字符串：说明本模块的功能定位
import json   # 导入json模块，用于读写JSON格式数据
import hashlib   # 导入hashlib库，用于生成唯一的数据ID
from pathlib import Path   # 从pathlib导入Path类，用于跨平台路径处理
from typing import List, Dict, Any   # 导入类型提示，增强代码可读性
from datetime import datetime   # 从datetime导入datetime类，用于时间戳记录
import pandas as pd   # 导入pandas数据分析库，用于导出CSV文件
import re   # 导入正则表达式模块

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # 获取项目根目录：当前文件所在目录的父目录



class SpecializedDataProcessor:   # 定义SpecializedDataProcessor类，用于处理特定格式的数据
    """专门处理三种特殊格式数据的处理器  多源数据格式统一处理器"""   # 类的文档字符串

    def __init__(self, data_dir: str, output_dir: str):   # 构造函数，当创建实例时自动调用
        self.data_dir = Path(data_dir)   # 将输入目录字符串转换为Path对象并保存
        self.output_dir = Path(output_dir)   # 将输出目录字符串转换为Path对象并保存
        self.output_dir.mkdir(parents=True, exist_ok=True)   # 创建输出目录（递归创建父目录，存在时不报错）

    def process_all_files(self):   # 定义方法：处理所有数据文件
        """处理所有文件"""   # 方法文档字符串
        all_processed_data = []   # 初始化列表，用于存储所有处理后的数据

        # 处理 eval.jsonl   # 注释：处理评估数据集文件
        eval_file = self.data_dir / "eval.jsonl"   # 构建eval.jsonl文件路径
        if eval_file.exists():   # 如果该文件存在
            print("处理 eval.jsonl...")   # 打印提示信息
            eval_data = self.process_eval_jsonl(eval_file)   # 调用专门的处理函数处理eval数据
            all_processed_data.extend(eval_data)   # 将处理结果合并到总列表中
            self.save_data(eval_data, "eval_processed")   # 单独保存eval处理结果
        else:   # 如果文件不存在
            print(f"未找到: {eval_file}")   # 打印警告信息

        # 处理 r1_data_example.jsonl   # 注释：处理R1推理数据文件
        r1_file = self.data_dir / "r1_data_example.jsonl"   # 构建r1文件路径
        if r1_file.exists():   # 如果该文件存在
            print("处理 r1_data_example.jsonl...")   # 打印提示信息
            r1_data = self.process_r1_jsonl(r1_file)   # 调用专门的处理函数处理R1数据
            all_processed_data.extend(r1_data)   # 将处理结果合并到总列表中
            self.save_data(r1_data, "r1_processed")   # 单独保存R1处理结果
        else:   # 如果文件不存在
            print(f"未找到: {r1_file}")   # 打印警告信息

        # 处理 SoulChatCorpus-sft-multi-Turn.json   # 注释：处理SoulChat多轮对话数据文件
        soulchat_file = self.data_dir / "SoulChatCorpus-sft-multi-Turn.json"   # 构建SoulChat文件路径
        if soulchat_file.exists():   # 如果该文件存在
            print("处理 SoulChatCorpus-sft-multi-Turn.json...")   # 打印提示信息
            soulchat_data = self.process_soulchat_json(soulchat_file)   # 调用专门的处理函数处理SoulChat数据
            all_processed_data.extend(soulchat_data)   # 将处理结果合并到总列表中
            self.save_data(soulchat_data, "soulchat_processed")   # 单独保存SoulChat处理结果
        else:   # 如果文件不存在
            print(f"未找到: {soulchat_file}")   # 打印警告信息

        # 保存所有合并数据   # 注释：将三个来源的数据合并后统一保存
        if all_processed_data:   # 如果有处理后的数据
            self.save_data(all_processed_data, "all_data_merged")   # 保存合并后的全部数据
            print(f"\n✅ 处理完成！共处理 {len(all_processed_data)} 条数据")   # 打印完成统计信息
        else:   # 如果没有处理到任何数据
            print("\n❌ 未找到任何数据文件！")   # 打印未找到文件的提示

        return all_processed_data   # 返回所有处理后的数据列表

    def process_eval_jsonl(self, file_path: Path) -> List[Dict]:   # 定义方法：处理eval.jsonl格式数据
        """处理 eval.jsonl 格式"""   # 方法文档字符串
        processed_data = []   # 初始化处理后的数据列表

        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开文件
            for line_num, line in enumerate(f, 1):   # 逐行遍历并计数（从1开始）
                if line.strip():   # 如果去除首尾空白后不为空行
                    try:   # 开始异常捕获
                        item = json.loads(line)   # 解析当前行为JSON对象

                        # 根据实际格式提取数据   # 注释：从不同可能的字段名中提取信息
                        # 假设 eval.jsonl 可能包含的字段   # 注释：说明兼容多种字段命名
                        processed_item = {   # 构建统一格式的处理后数据字典
                            'id': hashlib.md5(f"eval_{line_num}_{str(item)}".encode()).hexdigest(),
                            # 生成唯一ID：使用eval_行号_原始内容的MD5哈希
                            'role': '评估数据',   # 角色字段设为"评估数据"
                            'question': item.get('question', item.get('input', item.get('prompt', ''))),
                            # 提取问题字段，兼容question/input/prompt三种命名
                            'answer': item.get('answer', item.get('output', item.get('response', ''))),
                            # 提取回答字段，兼容answer/output/response三种命名
                            'context': item.get('context', item.get('history', '')),   # 提取上下文或历史记录
                            'intent': item.get('intent', 'evaluation'),   # 提取意图字段，默认为evaluation
                            'difficulty': item.get('difficulty', 'medium'),   # 提取难度字段，默认为medium
                            'source': 'eval.jsonl',   # 标记数据来源
                            'timestamp': datetime.now().isoformat(),   # 记录当前时间戳
                            'original_data': json.dumps(item, ensure_ascii=False)[:200]   # 保留原始数据前200字符作为片段
                        }

                        # 只添加有效数据   # 注释：确保问题和回答字段都不为空
                        if processed_item['question'] and processed_item['answer']:   # 如果问题且回答都不为空
                            processed_data.append(processed_item)   # 将处理后的条目添加到列表
                        else:   # 如果缺少必要字段
                            print(f"  警告: 第{line_num}行缺少必要字段")   # 打印警告信息

                    except json.JSONDecodeError as e:   # 捕获JSON解析错误
                        print(f"  错误: 第{line_num}行JSON解析失败: {e}")   # 打印解析失败信息

        print(f"  ✓ 成功处理 {len(processed_data)} 条数据")   # 打印成功处理的数据条数
        return processed_data   # 返回处理后的数据列表

    def process_r1_jsonl(self, file_path: Path) -> List[Dict]:   # 定义方法：处理r1_data_example.jsonl格式数据
        """处理 r1_data_example.jsonl 格式"""   # 方法文档字符串
        processed_data = []   # 初始化处理后的数据列表

        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开文件
            for line_num, line in enumerate(f, 1):   # 逐行遍历并计数（从1开始）
                if line.strip():   # 如果去除首尾空白后不为空行
                    try:   # 开始异常捕获
                        item = json.loads(line)   # 解析当前行为JSON对象

                        # R1格式可能包含的特殊字段   # 注释：针对R1推理数据的特殊字段处理
                        processed_item = {   # 构建统一格式的处理后数据字典
                            'id': hashlib.md5(f"r1_{line_num}_{str(item)}".encode()).hexdigest(),
                            # 生成唯一ID：使用r1_行号_原始内容的MD5哈希
                            'role': '推理数据',   # 角色字段设为"推理数据"
                            'question': item.get('question', item.get('instruction', item.get('query', ''))),
                            # 提取问题字段，兼容question/instruction/query三种命名
                            'answer': item.get('answer', item.get('response', item.get('output', ''))),
                            # 提取回答字段，兼容answer/response/output三种命名
                            'context': item.get('context', item.get('reasoning', '')),   # 提取上下文或推理过程
                            'intent': item.get('intent', 'reasoning'),   # 提取意图字段，默认为reasoning
                            'difficulty': item.get('difficulty', 'medium'),   # 提取难度字段，默认为medium
                            'source': 'r1_data_example.jsonl',   # 标记数据来源
                            'timestamp': datetime.now().isoformat(),   # 记录当前时间戳
                            'original_data': json.dumps(item, ensure_ascii=False)[:200]   # 保留原始数据片段
                        }

                        if processed_item['question'] and processed_item['answer']:   # 如果问题且回答都不为空
                            processed_data.append(processed_item)   # 将处理后的条目添加到列表
                        else:   # 如果缺少必要字段
                            print(f"  警告: 第{line_num}行缺少必要字段")   # 打印警告信息

                    except json.JSONDecodeError as e:   # 捕获JSON解析错误
                        print(f"  错误: 第{line_num}行JSON解析失败: {e}")   # 打印解析失败信息

        print(f"  ✓ 成功处理 {len(processed_data)} 条数据")   # 打印成功处理的数据条数
        return processed_data   # 返回处理后的数据列表

    def process_soulchat_json(self, file_path: Path) -> List[Dict]:   # 定义方法：处理SoulChatCorpus JSON格式数据
        """处理 SoulChatCorpus-sft-multi-Turn.json 格式"""   # 方法文档字符串
        processed_data = []   # 初始化处理后的数据列表

        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开文件
            try:   # 开始异常捕获
                data = json.load(f)   # 加载整个JSON文件（不是逐行）

                # 处理不同的JSON结构   # 注释：SoulChat数据可能为列表或字典格式
                if isinstance(data, list):   # 如果根节点是列表
                    items = data   # 直接使用列表作为数据项
                elif isinstance(data, dict):   # 如果根节点是字典
                    # 尝试找到实际的数据列表   # 注释：尝试从不同字段名中提取数据
                    if 'data' in data:   # 如果有data字段
                        items = data['data']   # 从data字段获取数据列表
                    elif 'conversations' in data:   # 如果有conversations字段
                        items = data['conversations']   # 从conversations字段获取数据列表
                    else:   # 如果以上字段都不存在
                        items = [data]   # 将整个字典作为单条数据
                else:   # 如果是其他不支持的数据类型
                    print(f"  错误: 不支持的数据格式 {type(data)}")   # 打印错误信息
                    return []   # 返回空列表

                for idx, item in enumerate(items):   # 遍历每条数据项
                    if not isinstance(item, dict):   # 如果数据项不是字典类型
                        continue   # 跳过该条数据

                    # SoulChat格式通常是多轮对话   # 注释：SoulChat数据以心理咨询多轮对话为主
                    if 'instruction' in item and 'output' in item:   # 如果是单轮对话格式
                        # 单轮格式   # 注释：instruction-output单轮对话
                        processed_item = {   # 构建统一格式的处理后数据
                            'id': hashlib.md5(f"soulchat_{idx}_{item.get('instruction', '')}".encode()).hexdigest(),
                            # 生成唯一ID：使用soulchat_索引_指令内容的MD5哈希
                            'role': '心理咨询',   # 角色字段设为"心理咨询"
                            'question': item.get('instruction', ''),   # 将instruction作为问题
                            'answer': item.get('output', ''),   # 将output作为回答
                            'context': item.get('input', ''),   # 提取输入作为上下文
                            'intent': item.get('intent', 'psychological_counseling'),   # 意图字段，默认为psychological_counseling
                            'difficulty': item.get('difficulty', 'medium'),   # 难度字段，默认为medium
                            'source': 'SoulChatCorpus',   # 标记数据来源
                            'timestamp': datetime.now().isoformat()   # 记录当前时间戳
                        }
                        if processed_item['question'] and processed_item['answer']:   # 如果问题且回答都不为空
                            processed_data.append(processed_item)   # 将条目添加到结果列表

                    elif 'conversations' in item or 'dialogue' in item:   # 如果是多轮对话格式
                        # 多轮对话格式   # 注释：conversations或dialogue字段标识的多轮对话
                        conversations = item.get('conversations', item.get('dialogue', []))   # 获取对话列表
                        for conv_idx, conv in enumerate(conversations):   # 遍历每一轮对话
                            if isinstance(conv, dict):   # 如果该轮对话是字典类型
                                processed_item = {   # 构建统一格式的处理后数据
                                    'id': hashlib.md5(f"soulchat_{idx}_{conv_idx}_{str(conv)}".encode()).hexdigest(),
                                    # 生成唯一ID：使用soulchat_索引_对话索引_内容的MD5哈希
                                    'role': '心理咨询',   # 角色字段设为"心理咨询"
                                    'question': conv.get('question', conv.get('user', conv.get('input', ''))),
                                    # 提取用户问题，兼容question/user/input三种命名
                                    'answer': conv.get('answer', conv.get('assistant', conv.get('output', ''))),
                                    # 提取助手回答，兼容answer/assistant/output三种命名
                                    'context': conv.get('context', conv.get('history', '')),   # 提取上下文或历史
                                    'intent': 'multi_turn_dialogue',   # 意图标记为多轮对话
                                    'difficulty': 'medium',   # 默认难度为medium
                                    'source': 'SoulChatCorpus',   # 标记数据来源
                                    'timestamp': datetime.now().isoformat()   # 记录当前时间戳
                                }
                                if processed_item['question'] and processed_item['answer']:   # 如果问题且回答都不为空
                                    processed_data.append(processed_item)   # 将条目添加到结果列表

                    elif 'messages' in item:   # 如果是消息列表格式（类似OpenAI格式）
                        # 消息列表格式   # 注释：messages字段标识的消息列表
                        messages = item['messages']   # 获取消息列表
                        for i in range(0, len(messages) - 1, 2):   # 按用户-助手成对遍历（步长为2）
                            if i + 1 < len(messages):   # 确保有对应的助手回复
                                processed_item = {   # 构建统一格式的处理后数据
                                    'id': hashlib.md5(
                                        f"soulchat_{idx}_{i}_{messages[i].get('content', '')}".encode()).hexdigest(),
                                    # 生成唯一ID：使用soulchat_索引_位置_用户消息内容的MD5哈希
                                    'role': '心理咨询',   # 角色字段设为"心理咨询"
                                    'question': messages[i].get('content', ''),   # 用户消息作为问题（偶数索引）
                                    'answer': messages[i + 1].get('content', ''),   # 助手回复作为回答（奇数索引）
                                    'context': '',   # 上下文为空
                                    'intent': 'dialogue',   # 意图标记为对话
                                    'difficulty': 'medium',   # 默认难度为medium
                                    'source': 'SoulChatCorpus',   # 标记数据来源
                                    'timestamp': datetime.now().isoformat()   # 记录当前时间戳
                                }
                                if processed_item['question'] and processed_item['answer']:   # 如果问题且回答都不为空
                                    processed_data.append(processed_item)   # 将条目添加到结果列表

                print(f"  ✓ 成功处理 {len(processed_data)} 条数据")   # 打印成功处理的数据条数

            except json.JSONDecodeError as e:   # 捕获JSON解析错误
                print(f"  错误: JSON解析失败: {e}")   # 打印解析失败信息
            except Exception as e:   # 捕获其他所有异常
                print(f"  错误: 处理文件时出错: {e}")   # 打印处理错误信息

        return processed_data   # 返回处理后的数据列表

    def save_data(self, data: List[Dict], filename: str):   # 定义方法：保存处理后的数据
        """保存处理后的数据"""   # 方法文档字符串
        if not data:   # 如果没有数据
            return   # 直接返回，不保存

        # 保存为JSON   # 注释：保存为格式化的JSON文件
        json_file = self.output_dir / f"{filename}.json"   # 构建JSON文件路径
        with open(json_file, 'w', encoding='utf-8') as f:   # 以写入模式、UTF-8编码打开文件
            json.dump(data, f, ensure_ascii=False, indent=2)   # 写入JSON（保留中文，缩进2空格）

        # 保存为CSV   # 注释：保存为CSV文件以便在Excel中查看
        try:   # 开始异常捕获
            df = pd.DataFrame(data)   # 将数据转换为pandas DataFrame
            csv_file = self.output_dir / f"{filename}.csv"   # 构建CSV文件路径
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')   # 写入CSV（不保存行索引，使用utf-8-sig编码兼容Excel）
        except Exception as e:   # 捕获保存CSV时的异常
            print(f"  保存CSV时出错: {e}")   # 打印错误信息

        print(f"  💾 已保存: {json_file.name} ({len(data)} 条)")   # 打印保存成功信息

    def inspect_file_structure(self):   # 定义方法：检查文件结构以了解实际格式
        """检查文件结构以了解实际格式"""   # 方法文档字符串
        print("\n" + "=" * 50)   # 打印分隔线
        print("文件结构检查")   # 打印标题
        print("=" * 50)   # 打印分隔线

        for filename in ['eval.jsonl', 'r1_data_example.jsonl', 'SoulChatCorpus-sft-multi-Turn.json']:   # 遍历三个数据文件
            file_path = self.data_dir / filename   # 构建文件完整路径
            if file_path.exists():   # 如果文件存在
                print(f"\n📄 {filename}:")   # 打印文件名
                try:   # 开始异常捕获
                    if filename.endswith('.jsonl'):   # 如果是JSONL文件（逐行JSON）
                        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开
                            first_line = f.readline()   # 读取第一行
                            if first_line:   # 如果第一行不为空
                                data = json.loads(first_line)   # 解析第一行为JSON对象
                                print(f"  第一条数据类型: {type(data)}")   # 打印数据类型
                                print(f"  字段: {list(data.keys()) if isinstance(data, dict) else '列表'}")   # 打印字段名
                                print(f"  示例内容: {json.dumps(data, ensure_ascii=False)[:200]}")   # 打印前200字符示例
                    else:   # 如果是普通JSON文件（整体加载）
                        with open(file_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开
                            data = json.load(f)   # 加载整个JSON内容
                            print(f"  数据类型: {type(data)}")   # 打印数据类型
                            if isinstance(data, list) and len(data) > 0:   # 如果是列表且非空
                                print(f"  列表长度: {len(data)}")   # 打印列表长度
                                print(f"  第一条字段: {list(data[0].keys()) if isinstance(data[0], dict) else '非字典'}")
                                # 打印第一条数据的字段名
                                print(f"  示例: {json.dumps(data[0], ensure_ascii=False)[:200]}")   # 打印前200字符示例
                            elif isinstance(data, dict):   # 如果是字典
                                print(f"  字段: {list(data.keys())}")   # 打印所有字段名
                                if 'data' in data and len(data['data']) > 0:   # 如果有data字段且非空
                                    print(f"  data字段类型: {type(data['data'])}")   # 打印data字段的类型
                                    if isinstance(data['data'], list) and len(data['data']) > 0:   # 如果data是列表且非空
                                        print(f"  第一条data字段: {list(data['data'][0].keys()) if isinstance(data['data'][0], dict) else '非字典'}")
                                        # 打印data列表中第一条的字段名
                except Exception as e:   # 捕获读取或解析时的异常
                    print(f"  读取错误: {e}")   # 打印错误信息


# 主程序   # 注释：以下为脚本直接运行时的入口
if __name__ == "__main__":   # 判断是否直接运行此脚本（而非被导入）
    DATA_DIR = str(PROJECT_ROOT / "vector_index")   # 设置数据目录为项目根目录下的vector_index文件夹
    OUTPUT_DIR = str(PROJECT_ROOT / "vector_index" / "processed_data")   # 设置输出目录为vector_index/processed_data

    # 创建处理器   # 注释：实例化数据处理器的实例
    processor = SpecializedDataProcessor(DATA_DIR, OUTPUT_DIR)   # 创建数据处理器的实例

    # 先检查文件结构   # 注释：先检查数据文件的结构以了解实际格式
    processor.inspect_file_structure()   # 调用文件结构检查方法

    # 处理所有文件   # 注释：开始正式的数据处理
    print("\n" + "=" * 50)   # 打印分隔线
    print("开始处理数据")   # 打印标题
    print("=" * 50)   # 打印分隔线

    processed_data = processor.process_all_files()   # 调用核心处理方法，处理所有数据文件

    # 输出统计信息   # 注释：打印处理结果的统计分析
    if processed_data:   # 如果成功获取到处理后的数据
        print("\n" + "=" * 50)   # 打印分隔线
        print("处理统计")   # 打印标题
        print("=" * 50)   # 打印分隔线
        df = pd.DataFrame(processed_data)   # 将数据转换为pandas DataFrame以便分析
        print(f"总数据量: {len(df)}")   # 打印总数据条数
        print(f"来源分布:")   # 打印来源统计标题
        print(df['source'].value_counts())   # 打印各来源的数据条数分布
        print(f"\n角色分布:")   # 打印角色统计标题
        print(df['role'].value_counts())   # 打印各角色的数据条数分布
        if 'intent' in df.columns:   # 如果存在意图字段
            print(f"\n意图分布:")   # 打印意图统计标题
            print(df['intent'].value_counts())   # 打印各意图的数据条数分布

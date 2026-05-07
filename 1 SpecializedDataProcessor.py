# -*- coding: utf-8 -*-
import json                     #用于读写josn格式数据
import hashlib                  #用于生成唯一的ID
from pathlib import Path        #跨平台路径处理
from typing import List, Dict, Any #类型提示 增强代码可读性
from datetime import datetime      #时间戳记录
import pandas as pd                #数据分析库 用于导出csv
import re                          #正则表达式

#这是定义了一个名为SpecializedDataProcessor的类 用于处理特定数据
class SpecializedDataProcessor:
    """专门处理三种特殊格式数据的处理器"""


    def __init__(self, data_dir: str, output_dir: str):
        #这是一个特殊方法 当创建类的实例(对象)时会自动调用它 self代表实例本身 里面有两个参数 期望传入两个字符串
        self.data_dir = Path(data_dir)       #输入目录
        self.output_dir = Path(output_dir)   #输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)  #如果目录步存在则创建

    def process_all_files(self):
        """处理所有文件"""
        all_processed_data = []   #存储所有处理后的数据

        # 处理 eval.jsonl
        eval_file = self.data_dir / "eval.jsonl"
        if eval_file.exists():
            print("处理 eval.jsonl...")   #调用专门的处理函数
            eval_data = self.process_eval_jsonl(eval_file)
            all_processed_data.extend(eval_data)  #合并结果
            self.save_data(eval_data, "eval_processed") #保存单个文件
        else:
            print(f"未找到: {eval_file}")
            #如果文件不存在 打印一条警告信息

        # 处理 r1_data_example.jsonl
        r1_file = self.data_dir / "r1_data_example.jsonl"
        if r1_file.exists():
            print("处理 r1_data_example.jsonl...")
            r1_data = self.process_r1_jsonl(r1_file)
            all_processed_data.extend(r1_data)
            self.save_data(r1_data, "r1_processed")
        else:
            print(f"未找到: {r1_file}")

        # 处理 SoulChatCorpus-sft-multi-Turn.json
        soulchat_file = self.data_dir / "SoulChatCorpus-sft-multi-Turn.json"
        if soulchat_file.exists():
            print("处理 SoulChatCorpus-sft-multi-Turn.json...")
            soulchat_data = self.process_soulchat_json(soulchat_file)
            all_processed_data.extend(soulchat_data)
            self.save_data(soulchat_data, "soulchat_processed")
        else:
            print(f"未找到: {soulchat_file}")

        # 保存所有合并数据
        if all_processed_data:
            self.save_data(all_processed_data, "all_data_merged")
            print(f"\n✅ 处理完成！共处理 {len(all_processed_data)} 条数据")
        else:
            print("\n❌ 未找到任何数据文件！")

        return all_processed_data

    def process_eval_jsonl(self, file_path: Path) -> List[Dict]:
        """处理 eval.jsonl 格式"""
        processed_data = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        item = json.loads(line)

                        # 根据实际格式提取数据
                        # 假设 eval.jsonl 可能包含的字段
                        processed_item = {
                            'id': hashlib.md5(f"eval_{line_num}_{str(item)}".encode()).hexdigest(),
                            'role': '评估数据',
                            'question': item.get('question', item.get('input', item.get('prompt', ''))),
                            'answer': item.get('answer', item.get('output', item.get('response', ''))),
                            'context': item.get('context', item.get('history', '')),
                            'intent': item.get('intent', 'evaluation'),
                            'difficulty': item.get('difficulty', 'medium'),
                            'source': 'eval.jsonl',
                            'timestamp': datetime.now().isoformat(),
                            'original_data': json.dumps(item, ensure_ascii=False)[:200]  # 保留原始数据片段
                        }

                        # 只添加有效数据
                        if processed_item['question'] and processed_item['answer']:
                            processed_data.append(processed_item)
                        else:
                            print(f"  警告: 第{line_num}行缺少必要字段")

                    except json.JSONDecodeError as e:
                        print(f"  错误: 第{line_num}行JSON解析失败: {e}")

        print(f"  ✓ 成功处理 {len(processed_data)} 条数据")
        return processed_data

    def process_r1_jsonl(self, file_path: Path) -> List[Dict]:
        """处理 r1_data_example.jsonl 格式"""
        processed_data = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        item = json.loads(line)

                        # R1格式可能包含的特殊字段
                        processed_item = {
                            'id': hashlib.md5(f"r1_{line_num}_{str(item)}".encode()).hexdigest(),
                            'role': '推理数据',
                            'question': item.get('question', item.get('instruction', item.get('query', ''))),
                            'answer': item.get('answer', item.get('response', item.get('output', ''))),
                            'context': item.get('context', item.get('reasoning', '')),
                            'intent': item.get('intent', 'reasoning'),
                            'difficulty': item.get('difficulty', 'medium'),
                            'source': 'r1_data_example.jsonl',
                            'timestamp': datetime.now().isoformat(),
                            'original_data': json.dumps(item, ensure_ascii=False)[:200]
                        }

                        if processed_item['question'] and processed_item['answer']:
                            processed_data.append(processed_item)
                        else:
                            print(f"  警告: 第{line_num}行缺少必要字段")

                    except json.JSONDecodeError as e:
                        print(f"  错误: 第{line_num}行JSON解析失败: {e}")

        print(f"  ✓ 成功处理 {len(processed_data)} 条数据")
        return processed_data

    def process_soulchat_json(self, file_path: Path) -> List[Dict]:
        """处理 SoulChatCorpus-sft-multi-Turn.json 格式"""
        processed_data = []

        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)

                # 处理不同的JSON结构
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    # 尝试找到实际的数据列表
                    if 'data' in data:
                        items = data['data']
                    elif 'conversations' in data:
                        items = data['conversations']
                    else:
                        items = [data]
                else:
                    print(f"  错误: 不支持的数据格式 {type(data)}")
                    return []

                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue

                    # SoulChat格式通常是多轮对话
                    if 'instruction' in item and 'output' in item:
                        # 单轮格式
                        processed_item = {
                            'id': hashlib.md5(f"soulchat_{idx}_{item.get('instruction', '')}".encode()).hexdigest(),
                            'role': '心理咨询',
                            'question': item.get('instruction', ''),
                            'answer': item.get('output', ''),
                            'context': item.get('input', ''),
                            'intent': item.get('intent', 'psychological_counseling'),
                            'difficulty': item.get('difficulty', 'medium'),
                            'source': 'SoulChatCorpus',
                            'timestamp': datetime.now().isoformat()
                        }
                        if processed_item['question'] and processed_item['answer']:
                            processed_data.append(processed_item)

                    elif 'conversations' in item or 'dialogue' in item:
                        # 多轮对话格式
                        conversations = item.get('conversations', item.get('dialogue', []))
                        for conv_idx, conv in enumerate(conversations):
                            if isinstance(conv, dict):
                                processed_item = {
                                    'id': hashlib.md5(f"soulchat_{idx}_{conv_idx}_{str(conv)}".encode()).hexdigest(),
                                    'role': '心理咨询',
                                    'question': conv.get('question', conv.get('user', conv.get('input', ''))),
                                    'answer': conv.get('answer', conv.get('assistant', conv.get('output', ''))),
                                    'context': conv.get('context', conv.get('history', '')),
                                    'intent': 'multi_turn_dialogue',
                                    'difficulty': 'medium',
                                    'source': 'SoulChatCorpus',
                                    'timestamp': datetime.now().isoformat()
                                }
                                if processed_item['question'] and processed_item['answer']:
                                    processed_data.append(processed_item)

                    elif 'messages' in item:
                        # 消息列表格式
                        messages = item['messages']
                        for i in range(0, len(messages) - 1, 2):
                            if i + 1 < len(messages):
                                processed_item = {
                                    'id': hashlib.md5(
                                        f"soulchat_{idx}_{i}_{messages[i].get('content', '')}".encode()).hexdigest(),
                                    'role': '心理咨询',
                                    'question': messages[i].get('content', ''),
                                    'answer': messages[i + 1].get('content', ''),
                                    'context': '',
                                    'intent': 'dialogue',
                                    'difficulty': 'medium',
                                    'source': 'SoulChatCorpus',
                                    'timestamp': datetime.now().isoformat()
                                }
                                if processed_item['question'] and processed_item['answer']:
                                    processed_data.append(processed_item)

                print(f"  ✓ 成功处理 {len(processed_data)} 条数据")

            except json.JSONDecodeError as e:
                print(f"  错误: JSON解析失败: {e}")
            except Exception as e:
                print(f"  错误: 处理文件时出错: {e}")

        return processed_data

    def save_data(self, data: List[Dict], filename: str):
        """保存处理后的数据"""
        if not data:
            return

        # 保存为JSON
        json_file = self.output_dir / f"{filename}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 保存为CSV
        try:
            df = pd.DataFrame(data)
            csv_file = self.output_dir / f"{filename}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        except Exception as e:
            print(f"  保存CSV时出错: {e}")

        print(f"  💾 已保存: {json_file.name} ({len(data)} 条)")

    def inspect_file_structure(self):
        """检查文件结构以了解实际格式"""
        print("\n" + "=" * 50)
        print("文件结构检查")
        print("=" * 50)

        for filename in ['eval.jsonl', 'r1_data_example.jsonl', 'SoulChatCorpus-sft-multi-Turn.json']:
            file_path = self.data_dir / filename
            if file_path.exists():
                print(f"\n📄 {filename}:")
                try:
                    if filename.endswith('.jsonl'):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            first_line = f.readline()
                            if first_line:
                                data = json.loads(first_line)
                                print(f"  第一条数据类型: {type(data)}")
                                print(f"  字段: {list(data.keys()) if isinstance(data, dict) else '列表'}")
                                print(f"  示例内容: {json.dumps(data, ensure_ascii=False)[:200]}")
                    else:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            print(f"  数据类型: {type(data)}")
                            if isinstance(data, list) and len(data) > 0:
                                print(f"  列表长度: {len(data)}")
                                print(
                                    f"  第一条字段: {list(data[0].keys()) if isinstance(data[0], dict) else '非字典'}")
                                print(f"  示例: {json.dumps(data[0], ensure_ascii=False)[:200]}")
                            elif isinstance(data, dict):
                                print(f"  字段: {list(data.keys())}")
                                if 'data' in data and len(data['data']) > 0:
                                    print(f"  data字段类型: {type(data['data'])}")
                                    if isinstance(data['data'], list) and len(data['data']) > 0:
                                        print(
                                            f"  第一条data字段: {list(data['data'][0].keys()) if isinstance(data['data'][0], dict) else '非字典'}")
                except Exception as e:
                    print(f"  读取错误: {e}")


# 主程序
if __name__ == "__main__":
    # 设置路径 - 改为您的实际路径
    DATA_DIR =  r"C:\Users\31326\Desktop\adsd\vector_index"  # JSON文件所在目录
    OUTPUT_DIR = r"C:\Users\31326\Desktop\adsd\vector_index\processed_data"  # 输出目录

    # 创建处理器
    processor = SpecializedDataProcessor(DATA_DIR, OUTPUT_DIR)

    # 先检查文件结构
    processor.inspect_file_structure()

    # 处理所有文件
    print("\n" + "=" * 50)
    print("开始处理数据")
    print("=" * 50)

    processed_data = processor.process_all_files()
#调用核心处理方法 process_all_files开始真正的数据处理流程 并将返回的所有数据
#保存到process_all_files变量中

    # 输出统计信息
    if processed_data:
        print("\n" + "=" * 50)
        print("处理统计")
        print("=" * 50)
        df = pd.DataFrame(processed_data)
        print(f"总数据量: {len(df)}")
        print(f"来源分布:")
        print(df['source'].value_counts())
        print(f"\n角色分布:")
        print(df['role'].value_counts())
        if 'intent' in df.columns:
            print(f"\n意图分布:")
            print(df['intent'].value_counts())
#如果成功处理了数据 则再次使用pandas将其转换为DataFrame 并打印一些基本的统计分析
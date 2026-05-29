# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，以支持中文等字符
"""
数据质量分析模块。

本模块用于分析数据预处理阶段生成的合并数据文件（all_data_merged.json），
提供以下功能：
1. 自动搜索数据文件（支持多个备选路径）
2. 数据质量分析：字段完整性检查、缺失值检测
3. 统计分析：角色分布、来源分布、文本长度统计
4. 质量评分：基于数据量和字段完整性计算综合评分（0-100分）
5. 生成JSON格式的分析报告

可通过直接运行或在runner中调用analyze_processed_data()使用。
"""


# scripts/check_processed_data.py   # 脚本文件所在的路径和文件名注释

import json   # 导入json模块，用于处理JSON数据的读写
import pandas as pd   # 导入pandas库并简写为pd，用于数据分析和DataFrame操作
from pathlib import Path   # 从pathlib导入Path类，用于跨平台的文件路径处理

# 定义项目根目录：当前脚本文件所在目录的上一级目录（resolve()解析符号链接，parent获取父目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 定义函数：分析处理后的数据质量
def analyze_processed_data():
    """分析处理后的数据质量"""   # 函数的文档字符串，说明函数功能

    # 构建基础目录路径：项目根目录下的 "vector_index" 文件夹
    base_dir = PROJECT_ROOT / "vector_index"
    # 构建数据文件完整路径：base_dir下的 processed_data/all_data_merged.json
    data_path = base_dir / "processed_data" / "all_data_merged.json"

    # 如果上述路径不存在，则进入搜索模式
    if not data_path.exists():
        print("🔍 搜索数据文件...")   # 打印提示信息，开始搜索文件

        # 定义可能的数据文件位置列表（多个备选路径）
        possible_locations = [
            PROJECT_ROOT / "vector_index" / "processed_data" / "all_data_merged.json",
            PROJECT_ROOT / "vector_index" / "all_data_merged.json",
            PROJECT_ROOT / "processed_data" / "all_data_merged.json",
            Path.cwd() / "processed_data" / "all_data_merged.json",  # cwd()获取当前工作目录
        ]

        # 遍历所有可能的位置
        for loc in possible_locations:
            if loc.exists():   # 如果该位置的文件存在
                data_path = loc   # 将data_path更新为找到的路径
                print(f"✅ 找到数据: {data_path}")   # 打印找到的路径
                break   # 找到后退出循环

        # 如果遍历完所有位置都没找到文件
        if not data_path.exists():
            print("❌ 未找到 all_data_merged.json")   # 打印未找到错误
            print("💡 请先运行数据预处理脚本，或检查以下位置:")   # 提示用户先预处理数据
            for loc in possible_locations:   # 再次打印所有可能的路径供用户参考
                print(f"   - {loc}")
            return None   # 函数返回None，表示分析失败

    # 开始读取数据文件
    print(f"\n📖 读取数据: {data_path}")   # 打印正在读取的文件路径
    with open(data_path, 'r', encoding='utf-8') as f:   # 以只读模式、UTF-8编码打开文件
        data = json.load(f)   # 使用json.load加载文件内容到变量data中

    # 打印分隔线和报告标题
    print("=" * 60)   # 打印60个等号作为分隔线
    print("数据质量分析报告")   # 打印报告标题
    print("=" * 60)   # 打印60个等号作为分隔线
    print(f"总数据量: {len(data)} 条")   # 打印数据的总条数

    # 将数据转换为pandas的DataFrame，方便进行数据分析
    df = pd.DataFrame(data)

    # 打印数据样例
    print("\n📋 数据样例:")   # 打印数据样例标题
    if len(data) > 0:   # 确保有数据
        sample = data[0]   # 取第一条数据作为样例
        # 打印问题字段的前100个字符，如果不存在则打印N/A
        print(f"  问题: {sample.get('question', 'N/A')[:100]}...")
        # 打印回答字段的前100个字符，如果不存在则打印N/A
        print(f"  回答: {sample.get('answer', 'N/A')[:100]}...")
        # 打印来源字段，如果不存在则打印N/A
        print(f"  来源: {sample.get('source', 'N/A')}")
        # 打印角色字段，如果不存在则打印N/A
        print(f"  角色: {sample.get('role', 'N/A')}")

    # 定义必要的字段列表
    required_fields = ['question', 'answer', 'role', 'intent']
    # 遍历每个必要字段
    for field in required_fields:
        if field in df.columns:   # 如果该字段存在于DataFrame的列中
            missing = df[field].isna().sum()   # 计算该字段的空值数量（isna()判断是否为空，sum()求和）
            if missing > 0:   # 如果有缺失值
                print(f"\n⚠️  {field} 字段缺失: {missing} 条")   # 打印缺失警告
        else:   # 如果该字段不存在于DataFrame中
            print(f"\n⚠️  {field} 字段不存在")   # 打印不存在警告

    # 分析数据中角色字段的分布情况
    print(f"\n📊 角色分布:")   # 打印角色分布标题
    if 'role' in df.columns:   # 如果存在role列
        # value_counts()统计每个值的出现次数，items()遍历每个值及其计数
        for role, count in df['role'].value_counts().items():
            percentage = count / len(df) * 100   # 计算该角色所占百分比
            print(f"  {role}: {count} 条 ({percentage:.1f}%)")   # 打印角色统计信息
    else:   # 如果不存在role列
        print("  (无 role 字段)")   # 提示无role字段

    # 分析数据中来源字段的分布情况
    print(f"\n📊 来源分布:")   # 打印来源分布标题
    if 'source' in df.columns:   # 如果存在source列
        for source, count in df['source'].value_counts().items():   # 遍历每个来源及其计数
            percentage = count / len(df) * 100   # 计算该来源所占百分比
            print(f"  {source}: {count} 条 ({percentage:.1f}%)")   # 打印来源统计信息
    else:   # 如果不存在source列
        print("  (无 source 字段)")   # 提示无source字段

    # 分析文本长度相关信息
    if 'question' in df.columns and 'answer' in df.columns:   # 如果问题和回答列都存在
        # 创建question_len列：将question转为字符串后计算长度
        df['question_len'] = df['question'].astype(str).str.len()
        # 创建answer_len列：将answer转为字符串后计算长度
        df['answer_len'] = df['answer'].astype(str).str.len()

        # 打印文本长度统计信息
        print(f"\n📏 文本长度统计:")   # 打印长度统计标题
        print(f"  问题平均长度: {df['question_len'].mean():.0f} 字符")   # 问题平均长度（均值）
        print(f"  回答平均长度: {df['answer_len'].mean():.0f} 字符")   # 回答平均长度
        print(f"  问题长度范围: {df['question_len'].min()} - {df['question_len'].max()} 字符")   # 问题长度最小值和最大值
        print(f"  回答长度范围: {df['answer_len'].min()} - {df['answer_len'].max()} 字符")   # 回答长度最小值和最大值

        # 检查过短的问题（长度小于5个字符）
        short_questions = df[df['question_len'] < 5]   # 使用布尔索引筛选问题过短的数据
        if len(short_questions) > 0:   # 如果存在过短问题
            print(f"\n⚠️  问题过短 (<5字符): {len(short_questions)} 条")   # 打印警告

        # 检查空的回答（长度为0）
        empty_answers = df[df['answer_len'] == 0]   # 筛选回答为空的数据
        if len(empty_answers) > 0:   # 如果存在空回答
            print(f"\n⚠️  空回答: {len(empty_answers)} 条")   # 打印警告

    # 构建分析报告的保存路径
    report_path = base_dir / "processed_data" / "data_analysis_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)   # 创建父目录，exists_ok=True表示目录已存在时不报错

    # 构建分析报告的数据字典
    analysis_report = {
        'total_count': len(data),   # 总数据条数
        # 如果存在role列，则获取值计数并转为字典，否则为空字典
        'role_distribution': df['role'].value_counts().to_dict() if 'role' in df.columns else {},
        # 如果存在source列，则获取值计数并转为字典，否则为空字典
        'source_distribution': df['source'].value_counts().to_dict() if 'source' in df.columns else {},
        # 如果存在question列，计算平均长度，否则为0
        'avg_question_length': float(df['question_len'].mean()) if 'question' in df.columns else 0,
        # 如果存在answer列，计算平均长度，否则为0
        'avg_answer_length': float(df['answer_len'].mean()) if 'answer' in df.columns else 0,
        'file_path': str(data_path)   # 数据文件的路径（转为字符串）
    }

    # 将分析报告写入JSON文件
    with open(report_path, 'w', encoding='utf-8') as f:   # 以写入模式、UTF-8编码打开文件
        json.dump(analysis_report, f, ensure_ascii=False, indent=2)   # 写入JSON，不转义非ASCII字符，缩进2格

    # 打印报告保存成功的信息
    print(f"\n✅ 分析报告已保存: {report_path}")

    # 输出数据质量评分（第二部分分析）
    print("\n" + "=" * 60)   # 打印分隔线
    print("数据质量评分")   # 打印评分标题
    print("=" * 60)   # 打印分隔线

    score = 100   # 初始化评分为满分100分
    if len(data) == 0:   # 如果没有数据
        score = 0   # 评分为0
    elif len(data) < 100:   # 如果数据量少于100条
        score -= 20   # 扣20分
        print("⚠️  数据量较少 (<100条)")   # 打印警告

    # 检查问题字段的缺失情况
    if 'question' in df.columns:   # 如果question列存在
        missing_q = df['question'].isna().sum()   # 计算缺失数量
        if missing_q > 0:   # 如果有缺失
            score -= (missing_q / len(df)) * 50   # 按缺失比例扣分（最高扣50分）
            print(f"⚠️  问题缺失: {missing_q} 条")   # 打印缺失警告

    # 检查回答字段的缺失情况
    if 'answer' in df.columns:   # 如果answer列存在
        missing_a = df['answer'].isna().sum()   # 计算缺失数量
        if missing_a > 0:   # 如果有缺失
            score -= (missing_a / len(df)) * 50   # 按缺失比例扣分（最高扣50分）
            print(f"⚠️  回答缺失: {missing_a} 条")   # 打印缺失警告

    # 打印最终评分（确保评分在0-100之间）
    print(f"\n📊 综合质量评分: {max(0, min(100, score)):.1f}/100")

    return data   # 返回加载的数据

# 脚本入口：如果直接运行此脚本（而非被导入），则执行以下代码
if __name__ == "__main__":
    data = analyze_processed_data()   # 调用分析函数，获取数据

    if data:   # 如果成功获取到数据
        print(f"\n✅ 分析完成！共分析了 {len(data)} 条数据")   # 打印完成信息
    else:   # 如果分析失败（data为None）
        print("\n❌ 分析失败，请检查数据文件是否存在")   # 打印失败提示
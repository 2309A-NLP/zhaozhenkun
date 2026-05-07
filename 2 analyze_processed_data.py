# -*- coding: utf-8 -*-
# scripts/check_processed_data.py
import json
import pandas as pd
from pathlib import Path


def analyze_processed_data():
    """分析处理后的数据质量"""

    # 修改为正确的路径
    base_dir = Path(r"C:\Users\31326\Desktop\adsd\vector_index")
    data_path = base_dir / "processed_data" / "all_data_merged.json"

    # 如果上面找不到，尝试其他可能的位置
    if not data_path.exists():
        print("🔍 搜索数据文件...")

        # 搜索可能的位置
        possible_locations = [
            Path(r"C:\Users\31326\Desktop\adsd\vector_index\processed_data\all_data_merged.json"),
            Path(r"C:\Users\31326\Desktop\adsd\vector_index\all_data_merged.json"),
            Path(r"C:\Users\31326\Desktop\模型\项目二\processed_data\all_data_merged.json"),
            Path.cwd() / "processed_data" / "all_data_merged.json",
        ]

        for loc in possible_locations:
            if loc.exists():
                data_path = loc
                print(f"✅ 找到数据: {data_path}")
                break

        if not data_path.exists():
            print("❌ 未找到 all_data_merged.json")
            print("💡 请先运行数据预处理脚本，或检查以下位置:")
            for loc in possible_locations:
                print(f"   - {loc}")
            return None

    # 读取数据
    print(f"\n📖 读取数据: {data_path}")
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 60)
    print("数据质量分析报告")
    print("=" * 60)
    print(f"总数据量: {len(data)} 条")

    # 转换为DataFrame方便分析
    df = pd.DataFrame(data)

    # 显示前几条数据样例
    print("\n📋 数据样例:")
    if len(data) > 0:
        sample = data[0]
        print(f"  问题: {sample.get('question', 'N/A')[:100]}...")
        print(f"  回答: {sample.get('answer', 'N/A')[:100]}...")
        print(f"  来源: {sample.get('source', 'N/A')}")
        print(f"  角色: {sample.get('role', 'N/A')}")

    # 检查必要字段
    required_fields = ['question', 'answer', 'role', 'intent']
    for field in required_fields:
        if field in df.columns:
            missing = df[field].isna().sum()
            if missing > 0:
                print(f"\n⚠️  {field} 字段缺失: {missing} 条")
        else:
            print(f"\n⚠️  {field} 字段不存在")

    # 分析数据分布
    print(f"\n📊 角色分布:")
    if 'role' in df.columns:
        for role, count in df['role'].value_counts().items():
            percentage = count / len(df) * 100
            print(f"  {role}: {count} 条 ({percentage:.1f}%)")
    else:
        print("  (无 role 字段)")

    print(f"\n📊 来源分布:")
    if 'source' in df.columns:
        for source, count in df['source'].value_counts().items():
            percentage = count / len(df) * 100
            print(f"  {source}: {count} 条 ({percentage:.1f}%)")
    else:
        print("  (无 source 字段)")

    # 分析文本长度
    if 'question' in df.columns and 'answer' in df.columns:
        df['question_len'] = df['question'].astype(str).str.len()
        df['answer_len'] = df['answer'].astype(str).str.len()

        print(f"\n📏 文本长度统计:")
        print(f"  问题平均长度: {df['question_len'].mean():.0f} 字符")
        print(f"  回答平均长度: {df['answer_len'].mean():.0f} 字符")
        print(f"  问题长度范围: {df['question_len'].min()} - {df['question_len'].max()} 字符")
        print(f"  回答长度范围: {df['answer_len'].min()} - {df['answer_len'].max()} 字符")

        # 极短文本检查
        short_questions = df[df['question_len'] < 5]
        if len(short_questions) > 0:
            print(f"\n⚠️  问题过短 (<5字符): {len(short_questions)} 条")

        empty_answers = df[df['answer_len'] == 0]
        if len(empty_answers) > 0:
            print(f"\n⚠️  空回答: {len(empty_answers)} 条")

    # 保存分析结果
    report_path = base_dir / "processed_data" / "data_analysis_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    analysis_report = {
        'total_count': len(data),
        'role_distribution': df['role'].value_counts().to_dict() if 'role' in df.columns else {},
        'source_distribution': df['source'].value_counts().to_dict() if 'source' in df.columns else {},
        'avg_question_length': float(df['question_len'].mean()) if 'question' in df.columns else 0,
        'avg_answer_length': float(df['answer_len'].mean()) if 'answer' in df.columns else 0,
        'file_path': str(data_path)
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 分析报告已保存: {report_path}")

    # 输出数据质量评分
    print("\n" + "=" * 60)
    print("数据质量评分")
    print("=" * 60)

    score = 100
    if len(data) == 0:
        score = 0
    elif len(data) < 100:
        score -= 20
        print("⚠️  数据量较少 (<100条)")

    if 'question' in df.columns:
        missing_q = df['question'].isna().sum()
        if missing_q > 0:
            score -= (missing_q / len(df)) * 50
            print(f"⚠️  问题缺失: {missing_q} 条")

    if 'answer' in df.columns:
        missing_a = df['answer'].isna().sum()
        if missing_a > 0:
            score -= (missing_a / len(df)) * 50
            print(f"⚠️  回答缺失: {missing_a} 条")

    print(f"\n📊 综合质量评分: {max(0, min(100, score)):.1f}/100")

    return data


if __name__ == "__main__":
    data = analyze_processed_data()

    if data:
        print(f"\n✅ 分析完成！共分析了 {len(data)} 条数据")
    else:
        print("\n❌ 分析失败，请检查数据文件是否存在")
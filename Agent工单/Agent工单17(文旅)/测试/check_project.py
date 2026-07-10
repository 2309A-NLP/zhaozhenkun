# 这里定义简单的项目自检脚本。
import os
from pathlib import Path


def count_lines(path: Path) -> int:
    # 这里统计文件行数。
    with open(path, 'r', encoding='utf-8') as file:
        return sum(1 for _ in file)


def main():
    # 这里定位项目根目录。
    root = Path(__file__).resolve().parents[1]
    # 这里收集所有 Python 文件。
    py_files = sorted(root.rglob('*.py'))
    # 这里逐个输出行数。
    for file_path in py_files:
        print(f'{count_lines(file_path)}\t{file_path}')
    # 这里检查是否存在超 300 行文件。
    too_long = [str(path) for path in py_files if count_lines(path) > 300]
    # 这里输出检查结果。
    if too_long:
        print('存在超过300行的文件:')
        for item in too_long:
            print(item)
        raise SystemExit(1)
    print('所有 Python 文件均不超过300行。')


if __name__ == '__main__':
    # 这里运行主函数。
    main()

"""工单19：最终交付包生成脚本。"""

# 工单19：导入压缩包工具，生成作业提交文件。
import zipfile

# 工单19：导入路径工具，统一处理项目目录与输出文件。
from pathlib import Path


# 工单19：定位项目根目录。
BASE_DIR = Path(__file__).resolve().parents[1]

# 工单19：定义最终交付压缩包名称。
OUTPUT_ZIP = BASE_DIR / "Agent工单19_个性化学习推荐_最终版.zip"

# 工单19：定义需要忽略的目录和文件后缀。
SKIP_PARTS = {"__pycache__", ".idea", ".git"}
SKIP_SUFFIXES = {".pyc", ".db", ".zip", ".log"}
SKIP_NAMES = {".env.local", "dashboard_after.json"}


# 工单19：判断文件是否应进入最终交付包。
def should_include(path):
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if path.name in SKIP_NAMES:
        return False
    if path.suffix in SKIP_SUFFIXES:
        return False
    return path.is_file()


# 工单19：生成可提交的最终压缩包。
def build_archive():
    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in BASE_DIR.rglob("*"):
            if should_include(path):
                archive.write(path, path.relative_to(BASE_DIR))
    return OUTPUT_ZIP


# 工单19：允许直接执行脚本生成最终作业包。
def main():
    archive_path = build_archive()
    print(f"最终交付包已生成: {archive_path.name}")


# 工单19：直接运行时生成压缩包。
if __name__ == "__main__":
    main()

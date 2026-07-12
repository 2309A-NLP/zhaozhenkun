# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""json_store.py - 教育 Agent 的本地 JSON 读写仓储。"""  # 说明当前文件职责。

from pathlib import Path  # 导入路径处理工具。
import json  # 导入 JSON 处理模块。
from threading import Lock  # 导入线程锁工具。


class JsonStore:  # 定义通用 JSON 仓储类。
    def __init__(self, path: str, default_data):  # 初始化仓储实例。
        self.path = Path(path)  # 保存目标文件路径。
        self.default_data = default_data  # 保存默认数据模板。
        self.lock = Lock()  # 初始化线程锁对象。

    def _ensure_file(self):  # 确保目标文件存在。
        self.path.parent.mkdir(parents=True, exist_ok=True)  # 确保父目录存在。
        if self.path.exists():  # 当目标文件已存在时无需再创建。
            return  # 结束当前方法。
        self.write(self.default_data)  # 按默认数据写入新文件。

    def read(self):  # 读取并返回完整 JSON 数据。
        self._ensure_file()  # 先确保文件已准备就绪。
        with self.lock:  # 进入线程安全读取区间。
            return json.loads(self.path.read_text(encoding="utf-8"))  # 读取并解析 JSON 内容。

    def write(self, data):  # 将完整数据写回 JSON 文件。
        self.path.parent.mkdir(parents=True, exist_ok=True)  # 确保父目录存在。
        with self.lock:  # 进入线程安全写入区间。
            payload = json.dumps(data, ensure_ascii=False, indent=2)  # 序列化为格式化 JSON 字符串。
            self.path.write_text(payload, encoding="utf-8")  # 将内容写入磁盘文件。

    def append_item(self, item):  # 追加单条记录到列表型 JSON 文件。
        data = self.read()  # 读取当前文件内容。
        if not isinstance(data, list):  # 当数据结构不是列表时拒绝追加。
            raise TypeError("当前 JSON 文件不是列表结构")  # 抛出结构错误异常。
        data.append(item)  # 将新记录追加到列表末尾。
        self.write(data)  # 将更新后的列表写回文件。
        return item  # 返回刚刚写入的记录。

    def upsert_mapping(self, key: str, value):  # 更新或写入字典型 JSON 文件中的指定键值。
        data = self.read()  # 读取当前文件内容。
        if not isinstance(data, dict):  # 当数据结构不是字典时拒绝写入。
            raise TypeError("当前 JSON 文件不是字典结构")  # 抛出结构错误异常。
        data[key] = value  # 更新目标键的值。
        self.write(data)  # 将更新后的字典写回文件。
        return value  # 返回刚刚写入的值。

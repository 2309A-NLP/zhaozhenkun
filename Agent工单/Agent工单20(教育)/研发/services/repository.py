# 工单20：本文件用于管理面试记录与复盘缓存的本地存储。
# 工单20：导入JSON处理工具。
import json  # 工单20：代码语句。
# 工单20：导入日期时间工具。
from datetime import datetime  # 工单20：代码语句。
# 工单20：导入路径工具。
from pathlib import Path  # 工单20：代码语句。

# 工单20：定义仓储类。
class InterviewRepository:  # 工单20：代码语句。
    # 工单20：初始化仓储依赖路径。
    def __init__(self, data_dir: str):  # 工单20：代码语句。
        # 工单20：保存数据目录对象。
        self.data_dir = Path(data_dir)  # 工单20：代码语句。
        # 工单20：定义面试记录文件路径。
        self.interviews_path = self.data_dir / "interviews.json"  # 工单20：代码语句。
        # 工单20：定义知识库文件路径。
        self.knowledge_path = self.data_dir / "knowledge_base.json"  # 工单20：代码语句。
        # 工单20：定义缓存文件路径。
        self.cache_path = self.data_dir / "reviews_cache.json"  # 工单20：代码语句。

    # 工单20：定义读取JSON文件方法。
    def _read_json(self, path: Path, default_value):  # 工单20：代码语句。
        # 工单20：文件不存在时返回默认值。
        if not path.exists():  # 工单20：代码语句。
            return default_value  # 工单20：代码语句。
        # 工单20：读取并解析JSON。
        return json.loads(path.read_text(encoding="utf-8"))  # 工单20：代码语句。

    # 工单20：定义写入JSON文件方法。
    def _write_json(self, path: Path, payload) -> None:  # 工单20：代码语句。
        # 工单20：以格式化方式写回JSON。
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")  # 工单20：代码语句。

    # 工单20：定义获取全部面试记录方法。
    def list_interviews(self) -> list:  # 工单20：代码语句。
        # 工单20：读取所有面试记录。
        rows = self._read_json(self.interviews_path, [])  # 工单20：代码语句。
        # 工单20：按面试时间倒序返回。
        return sorted(rows, key=lambda item: item.get("interview_time", ""), reverse=True)  # 工单20：代码语句。

    # 工单20：定义根据编号获取记录方法。
    def get_interview(self, interview_id: str) -> dict | None:  # 工单20：代码语句。
        # 工单20：遍历所有记录定位目标。
        for row in self.list_interviews():  # 工单20：代码语句。
            if row.get("id") == interview_id:  # 工单20：代码语句。
                return row  # 工单20：代码语句。
        # 工单20：未命中时返回空值。
        return None  # 工单20：代码语句。

    # 工单20：定义批量导入记录方法。
    def import_rows(self, rows: list, reporter_name: str) -> int:  # 工单20：代码语句。
        # 工单20：读取当前记录列表。
        current_rows = self.list_interviews()  # 工单20：代码语句。
        # 工单20：建立现有编号集合。
        exists = {item.get("id") for item in current_rows}  # 工单20：代码语句。
        # 工单20：初始化导入计数。
        imported = 0  # 工单20：代码语句。
        # 工单20：遍历待导入记录。
        for row in rows:  # 工单20：代码语句。
            # 工单20：补充默认字段。
            row.setdefault("reporter_name", reporter_name)  # 工单20：代码语句。
            row.setdefault("report_time", datetime.now().strftime("%Y-%m-%d %H:%M"))  # 工单20：代码语句。
            row.setdefault("source_type", "teacher_import")  # 工单20：代码语句。
            row.setdefault("status", "已上报")  # 工单20：代码语句。
            row.setdefault("question_answers", [])  # 工单20：代码语句。
            row.setdefault("audio_text", "")  # 工单20：代码语句。
            row.setdefault("audio_file_name", "")  # 工单20：代码语句。
            row.setdefault("notes", "")  # 工单20：代码语句。
            # 工单20：跳过重复编号。
            if row.get("id") in exists:  # 工单20：代码语句。
                continue  # 工单20：代码语句。
            # 工单20：写入新记录。
            current_rows.append(row)  # 工单20：代码语句。
            # 工单20：记录新增编号。
            exists.add(row.get("id"))  # 工单20：代码语句。
            # 工单20：累加导入数量。
            imported += 1  # 工单20：代码语句。
        # 工单20：保存最新记录。
        self._write_json(self.interviews_path, current_rows)  # 工单20：代码语句。
        # 工单20：返回导入数量。
        return imported  # 工单20：代码语句。

    # 工单20：定义可编辑判断方法。
    def can_edit(self, interview: dict) -> bool:  # 工单20：代码语句。
        # 工单20：待完善状态始终允许修改。
        if interview.get("status") == "待完善":  # 工单20：代码语句。
            return True  # 工单20：代码语句。
        # 工单20：读取上报时间字符串。
        raw_time = interview.get("report_time", "")  # 工单20：代码语句。
        # 工单20：时间缺失时不允许修改。
        if not raw_time:  # 工单20：代码语句。
            return False  # 工单20：代码语句。
        # 工单20：解析上报时间。
        report_time = datetime.strptime(raw_time, "%Y-%m-%d %H:%M")  # 工单20：代码语句。
        # 工单20：判断是否在两天内。
        return (datetime.now() - report_time).days < 2  # 工单20：代码语句。

    # 工单20：定义更新面试记录方法。
    def update_interview(self, interview_id: str, payload: dict, editor_name: str) -> tuple[bool, str]:  # 工单20：代码语句。
        # 工单20：读取全部记录。
        rows = self.list_interviews()  # 工单20：代码语句。
        # 工单20：遍历查找目标记录。
        for index, row in enumerate(rows):  # 工单20：代码语句。
            if row.get("id") != interview_id:  # 工单20：代码语句。
                continue  # 工单20：代码语句。
            # 工单20：校验是否允许编辑。
            if not self.can_edit(row):  # 工单20：代码语句。
                return False, "当前记录仅支持两天内或待完善状态修改。"  # 工单20：代码语句。
            # 工单20：更新允许编辑的字段。
            for field in ["self_intro", "full_transcript", "notes", "audio_text", "audio_file_name", "status", "question_answers"]:  # 工单20：代码语句。
                if field in payload:  # 工单20：代码语句。
                    row[field] = payload[field]  # 工单20：代码语句。
            # 工单20：按需求将上报人改为学生姓名。
            row["reporter_name"] = editor_name  # 工单20：代码语句。
            # 工单20：将来源标记为学生更新后的记录。
            row["source_type"] = "student_report"  # 工单20：代码语句。
            # 工单20：更新时间戳。
            row["report_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")  # 工单20：代码语句。
            # 工单20：回写列表中的目标项。
            rows[index] = row  # 工单20：代码语句。
            # 工单20：保存全部记录。
            self._write_json(self.interviews_path, rows)  # 工单20：代码语句。
            # 工单20：清理该记录的复盘缓存。
            self.clear_review_cache(interview_id)  # 工单20：代码语句。
            # 工单20：返回成功结果。
            return True, "修改成功。"  # 工单20：代码语句。
        # 工单20：未找到目标记录。
        return False, "未找到面试记录。"  # 工单20：代码语句。

    # 工单20：定义获取岗位知识点方法。
    def get_knowledge_points(self, position_name: str) -> list:  # 工单20：代码语句。
        # 工单20：读取知识库字典。
        knowledge_map = self._read_json(self.knowledge_path, {})  # 工单20：代码语句。
        # 工单20：返回对应岗位知识点列表。
        return knowledge_map.get(position_name, [])  # 工单20：代码语句。

    # 工单20：定义获取复盘缓存方法。
    def get_review_cache(self, interview_id: str, provider: str) -> dict | None:  # 工单20：代码语句。
        # 工单20：读取缓存字典。
        cache = self._read_json(self.cache_path, {})  # 工单20：代码语句。
        # 工单20：读取编号对应的提供方缓存。
        provider_cache = cache.get(interview_id, {})  # 工单20：代码语句。
        # 工单20：返回指定模型缓存。
        return provider_cache.get(provider)  # 工单20：代码语句。

    # 工单20：定义保存复盘缓存方法。
    def save_review_cache(self, interview_id: str, provider: str, payload: dict) -> None:  # 工单20：代码语句。
        # 工单20：读取现有缓存。
        cache = self._read_json(self.cache_path, {})  # 工单20：代码语句。
        # 工单20：确保当前编号存在缓存容器。
        cache.setdefault(interview_id, {})  # 工单20：代码语句。
        # 工单20：写入目标模型缓存。
        cache[interview_id][provider] = payload  # 工单20：代码语句。
        # 工单20：保存更新后的缓存。
        self._write_json(self.cache_path, cache)  # 工单20：代码语句。

    # 工单20：定义清理复盘缓存方法。
    def clear_review_cache(self, interview_id: str) -> None:  # 工单20：代码语句。
        # 工单20：读取现有缓存。
        cache = self._read_json(self.cache_path, {})  # 工单20：代码语句。
        # 工单20：移除目标记录缓存。
        cache.pop(interview_id, None)  # 工单20：代码语句。
        # 工单20：保存清理后的缓存。
        self._write_json(self.cache_path, cache)  # 工单20：代码语句。

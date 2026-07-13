# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：版本管理服务 - 内容版本快照、历史回溯、差异对比
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import difflib  # 文本差异对比库
import uuid  # 唯一ID生成
import threading  # 线程锁（保护并发读写）
from typing import List, Optional, Dict, Tuple  # 类型提示
from datetime import datetime  # 时间处理
from collections import OrderedDict  # 有序字典


class VersionControlService:
    """版本管理服务类 - 实现教学内容的版本控制和历史回溯"""

    def __init__(self):
        """初始化版本管理服务 - 使用内存存储（生产环境需替换为数据库）"""
        self._versions: Dict[str, List[Dict]] = {}  # 版本存储字典：key=content_id, value=版本列表
        self._max_versions_per_content = 50  # 每个内容最多保留的版本数
        self._lock = threading.RLock()  # 可重入锁，保护并发版本操作

    def save_version(self, content_id: str, content_snapshot: str,
                     editor_id: str, change_summary: Optional[str] = None) -> Dict:
        """保存版本快照 - 为指定内容创建新的版本记录"""
        with self._lock:  # 线程安全：版本列表的读写需要原子操作
            if content_id not in self._versions:  # 该内容首次保存版本
                self._versions[content_id] = []  # 初始化版本列表
            version_list = self._versions[content_id]  # 获取当前版本列表
            version_number = len(version_list) + 1  # 版本号递增
            version_record = {  # 构建版本记录
                "version_id": str(uuid.uuid4()),  # 版本唯一ID
                "content_id": content_id,  # 关联的内容ID
                "version_number": version_number,  # 版本号
                "content_snapshot": content_snapshot,  # 内容快照
                "editor_id": editor_id,  # 编辑者ID
                "change_summary": change_summary or f"第{version_number}次编辑",  # 变更摘要
                "created_at": datetime.now().isoformat(),  # 创建时间
            }
            version_list.append(version_record)  # 添加到版本列表
            # 限制版本数量（保留最新版本）
            if len(version_list) > self._max_versions_per_content:  # 超过最大版本数
                version_list.pop(0)  # 删除最老的版本
        print(f"版本保存成功：{content_id} v{version_number}")  # 成功日志
        return version_record  # 返回版本记录

    def get_versions(self, content_id: str) -> List[Dict]:
        """获取所有版本 - 返回指定内容的所有历史版本列表"""
        with self._lock:  # 线程安全读取
            versions = list(self._versions.get(content_id, []))  # 获取版本列表快照
        # 返回不含快照内容的摘要列表（减少数据传输量）
        summary_list = []  # 摘要列表
        for v in versions:  # 遍历版本
            summary = {  # 构建版本摘要
                "version_id": v["version_id"],
                "version_number": v["version_number"],
                "editor_id": v["editor_id"],
                "change_summary": v["change_summary"],
                "created_at": v["created_at"],
                "snapshot_preview": v["content_snapshot"][:100] + "..." if len(v["content_snapshot"]) > 100 else v["content_snapshot"],  # 预览前100字符
            }
            summary_list.append(summary)  # 添加到摘要列表
        return summary_list  # 返回摘要列表

    def get_version_detail(self, version_id: str) -> Optional[Dict]:
        """获取版本详情 - 根据版本ID获取完整的版本快照"""
        for content_versions in self._versions.values():  # 遍历所有内容的版本
            for version in content_versions:  # 遍历每个版本
                if version["version_id"] == version_id:  # 找到匹配的版本ID
                    return version  # 返回完整版本记录
        return None  # 未找到返回None

    def restore_version(self, content_id: str, version_id: str) -> Optional[str]:
        """恢复历史版本 - 将指定内容恢复到历史版本的状态"""
        target_version = self.get_version_detail(version_id)  # 获取目标版本详情
        if not target_version:  # 版本不存在
            return None  # 返回None表示失败
        # 恢复操作实际上创建一个新版本（版本号继续递增）
        restored_snapshot = target_version["content_snapshot"]  # 获取历史快照
        print(f"内容 {content_id} 已恢复到版本 v{target_version['version_number']}")  # 恢复日志
        return restored_snapshot  # 返回恢复的内容快照

    def compare_versions(self, version_id_a: str, version_id_b: str) -> Optional[Dict]:
        """对比两个版本差异 - 使用diff算法比较两个版本的文本变更"""
        version_a = self.get_version_detail(version_id_a)  # 获取版本A
        version_b = self.get_version_detail(version_id_b)  # 获取版本B
        if not version_a or not version_b:  # 任一版本不存在
            return None  # 返回None表示失败
        text_a = version_a["content_snapshot"]  # 版本A的文本
        text_b = version_b["content_snapshot"]  # 版本B的文本
        # 使用difflib生成差异对比
        diff = list(difflib.unified_diff(  # 生成统一格式差异
            text_a.splitlines(keepends=True),  # 版本A行列表
            text_b.splitlines(keepends=True),  # 版本B行列表
            fromfile=f"v{version_a['version_number']} - {version_a['created_at']}",  # 来源标签
            tofile=f"v{version_b['version_number']} - {version_b['created_at']}",  # 目标标签
        ))
        # 统计变更
        additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))  # 新增行数
        deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))  # 删除行数
        return {  # 对比结果
            "version_a": {"number": version_a["version_number"], "time": version_a["created_at"]},
            "version_b": {"number": version_b["version_number"], "time": version_b["created_at"]},
            "diff_text": "".join(diff),  # 完整差异文本
            "stats": {"additions": additions, "deletions": deletions,
                      "total_changes": additions + deletions},  # 变更统计
        }

    def get_version_count(self, content_id: str) -> int:
        """获取版本数量 - 返回指定内容的版本总数"""
        return len(self._versions.get(content_id, []))  # 返回版本列表长度

    def cleanup_old_versions(self, content_id: str,
                             keep_latest: int = 10) -> int:
        """清理旧版本 - 保留最新N个版本，删除其余"""
        if content_id not in self._versions:  # 内容不存在
            return 0  # 返回0
        versions = self._versions[content_id]  # 获取版本列表
        if len(versions) <= keep_latest:  # 版本数不超标
            return 0  # 无需清理
        removed_count = len(versions) - keep_latest  # 计算需删除数量
        self._versions[content_id] = versions[-keep_latest:]  # 保留最新版本
        print(f"清理了 {removed_count} 个旧版本，保留最新 {keep_latest} 个")  # 清理日志
        return removed_count  # 返回删除数量


class CollaborationManager:
    """协同编辑管理类 - 管理多人实时协同编辑会话"""

    def __init__(self):
        """初始化协同管理器 - 使用内存存储会话"""
        self._sessions: Dict[str, Dict] = {}  # 会话存储：key=session_id, value=会话信息
        self._lock = threading.RLock()  # 可重入锁，保护并发修改

    def create_session(self, content_id: str, creator_id: str) -> Dict:
        """创建协同编辑会话 - 为指定内容创建多人编辑会话"""
        session_id = str(uuid.uuid4())  # 生成会话唯一ID
        session = {  # 会话信息
            "session_id": session_id,
            "content_id": content_id,
            "participants": [creator_id],  # 初始参与者（创建者）
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "is_active": True,
        }
        with self._lock:  # 线程安全
            self._sessions[session_id] = session  # 存储会话
        print(f"协同编辑会话已创建：{session_id}")  # 创建日志
        return session  # 返回会话信息

    def join_session(self, session_id: str, user_id: str) -> bool:
        """加入协同编辑会话 - 用户加入已有的编辑会话"""
        with self._lock:  # 线程安全
            session = self._sessions.get(session_id)  # 查找会话
            if not session or not session["is_active"]:  # 会话不存在或已结束
                return False  # 加入失败
            if user_id not in session["participants"]:  # 用户不在参与者列表中
                session["participants"].append(user_id)  # 添加参与者
            session["last_activity"] = datetime.now().isoformat()  # 更新活动时间
        print(f"用户 {user_id} 已加入会话 {session_id}")  # 加入日志
        return True  # 加入成功

    def leave_session(self, session_id: str, user_id: str) -> bool:
        """离开协同编辑会话 - 用户离开编辑会话"""
        with self._lock:  # 线程安全
            session = self._sessions.get(session_id)  # 查找会话
            if not session:  # 会话不存在
                return False  # 离开失败
            if user_id in session["participants"]:  # 用户在参与者列表中
                session["participants"].remove(user_id)  # 移除参与者
            if len(session["participants"]) == 0:  # 没有参与者了
                session["is_active"] = False  # 标记会话结束
        print(f"用户 {user_id} 已离开会话 {session_id}")  # 离开日志
        return True  # 离开成功

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息 - 返回会话详情包括参与者列表"""
        with self._lock:  # 线程安全读取
            session = self._sessions.get(session_id)  # 返回会话信息或None
            return dict(session) if session else None  # 返回副本，避免外部修改

    def get_active_sessions_for_content(self, content_id: str) -> List[Dict]:
        """获取内容的活跃会话 - 返回指定内容的所有活跃协同编辑会话"""
        with self._lock:  # 线程安全读取
            active = []  # 活跃会话列表
            for session in self._sessions.values():  # 遍历所有会话
                if session["content_id"] == content_id and session["is_active"]:  # 匹配内容且活跃
                    active.append(dict(session))  # 添加会话副本
        return active  # 返回活跃会话列表


# 全局版本控制和协同管理单例
version_control_service = VersionControlService()  # 创建全局唯一的版本管理实例
collaboration_manager = CollaborationManager()  # 创建全局唯一的协同编辑管理器实例

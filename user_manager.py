# -*- coding: utf-8 -*-
import json
import threading
from datetime import datetime
from typing import Dict
from utils import normalize_username


class UserManager:
    """用户管理器"""

    def __init__(self, user_data_file, mysql_manager):
        """初始化用户管理器

        Args:
            user_data_file: 本地用户数据文件路径
            mysql_manager: MySQL管理器实例，用于记录用户操作日志
        """
        self.user_data_file = user_data_file  # 存储用户数据的本地文件路径
        self.mysql_manager = mysql_manager  # MySQL管理器实例
        self.user_store_lock = threading.RLock()  # 可重入锁，用于线程安全的用户数据操作
        self._ensure_local_user_store()  # 确保本地用户存储文件存在

    def _ensure_local_user_store(self):
        """确保本地用户存储文件存在，如果不存在则创建"""
        self.user_data_file.parent.mkdir(parents=True, exist_ok=True)  # 创建父目录（如果不存在）
        if not self.user_data_file.exists():  # 检查用户数据文件是否存在
            # 如果不存在，创建一个包含空用户字典的JSON文件
            self.user_data_file.write_text(json.dumps({"users": {}}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_local_user_store(self) -> Dict:
        """从本地文件加载用户数据

        Returns:
            包含用户数据的字典，如果加载失败则返回默认结构
        """
        with self.user_store_lock:  # 使用线程锁保证线程安全
            try:
                # 读取并解析JSON文件中的用户数据
                return json.loads(self.user_data_file.read_text(encoding="utf-8"))
            except:
                # 如果读取或解析失败，返回默认的用户数据结构
                return {"users": {}}

    def _save_local_user_store(self, store: Dict) -> None:
        """将用户数据保存到本地文件

        Args:
            store: 要保存的用户数据字典
        """
        with self.user_store_lock:  # 使用线程锁保证线程安全
            # 将用户数据以JSON格式写入文件（带缩进，支持中文）
            self.user_data_file.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    def register_user(self, username: str, email: str = "", password: str = "") -> Dict:
        """注册新用户

        Args:
            username: 用户名
            email: 邮箱地址（可选）
            password: 密码（可选）

        Returns:
            包含注册结果的字典
        """
        username = normalize_username(username)  # 规范化用户名（如转小写、去除空格等）
        store = self._load_local_user_store()  # 加载现有用户数据
        store.setdefault("users", {})[username] = {  # 在用户字典中添加新用户
            "username": username,  # 用户名
            "password": password or "",  # 密码（如果未提供则为空字符串）
            "created_at": datetime.now().isoformat(),  # 创建时间（ISO格式）
            "avatar_id": "doctor",  # 默认头像ID为"doctor"
            "email": email or f"{username}@example.com"  # 邮箱（如果未提供则使用默认邮箱）
        }
        self._save_local_user_store(store)  # 保存更新后的用户数据
        self.mysql_manager.log_user_action(username, "register", {"email": email})  # 记录注册日志到MySQL
        return {"success": True, "username": username, "avatar_id": "doctor"}  # 返回成功结果

    def login_user(self, username: str, password: str = "") -> Dict:
        """用户登录（如果用户不存在则自动注册）

        Args:
            username: 用户名
            password: 密码（可选）

        Returns:
            包含登录结果的字典
        """
        username = normalize_username(username)  # 规范化用户名
        store = self._load_local_user_store()  # 加载现有用户数据
        users = store.setdefault("users", {})  # 获取用户字典（如果不存在则创建）

        if username not in users:  # 如果用户不存在
            # 自动创建新用户
            users[username] = {
                "username": username,  # 用户名
                "password": password or "",  # 密码（如果未提供则为空字符串）
                "created_at": datetime.now().isoformat(),  # 创建时间
                "avatar_id": "doctor"  # 默认头像ID
            }
            self._save_local_user_store(store)  # 保存新用户数据

        self.mysql_manager.log_user_action(username, "login")  # 记录登录日志到MySQL
        # 返回成功结果，包含用户头像ID
        return {"success": True, "username": username, "avatar_id": users[username].get("avatar_id", "doctor")}

    def set_user_avatar(self, username: str, avatar_id: str) -> bool:
        """设置用户头像

        Args:
            username: 用户名
            avatar_id: 头像ID

        Returns:
            设置是否成功
        """
        store = self._load_local_user_store()  # 加载现有用户数据
        users = store.setdefault("users", {})  # 获取用户字典
        if username not in users:  # 如果用户不存在
            # 自动创建用户记录
            users[username] = {
                "username": username,
                "password": "",
                "created_at": datetime.now().isoformat(),
                "avatar_id": "doctor"
            }
        users[username]["avatar_id"] = avatar_id  # 更新用户头像ID
        self._save_local_user_store(store)  # 保存更新后的用户数据
        # 记录切换头像日志到MySQL
        self.mysql_manager.log_user_action(username, "switch_avatar", {"avatar_id": avatar_id})
        return True  # 返回成功

    def get_user_avatar(self, username: str) -> str:
        """获取用户头像ID

        Args:
            username: 用户名

        Returns:
            用户头像ID，如果用户不存在则返回默认的"doctor"
        """
        # 从加载的用户数据中获取指定用户的头像ID，如果不存在则返回"doctor"
        return self._load_local_user_store().get("users", {}).get(username, {}).get("avatar_id", "doctor")
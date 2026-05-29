# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符正常处理

"""
ADSD 在线服务 - Redis缓存管理器模块
负责管理与Redis服务器的连接和数据缓存操作
主要功能：
1. 连接Redis服务器（支持密码认证、超时设置、健康检查）
2. 键值操作：设置（支持过期时间）、获取、删除、检查存在
3. 自动解码：响应内容自动从字节解码为字符串
4. 异常处理：连接失败时降级运行，不影响主服务
"""

try:
    import redis
except Exception:
    redis = None


# 尝试导入redis库，如果失败（未安装redis模块），则将redis设为None，避免程序崩溃


class RedisManager:
    """Redis管理器"""

    # 定义一个Redis管理类，用于封装Redis操作

    def __init__(self, host: str, port: int, password: str = None):
        # 类的构造函数，在创建实例时自动调用
        # host: Redis服务器地址
        # port: Redis端口号
        # password: Redis密码，默认为None

        self.host = host
        # 将传入的host参数保存到实例变量self.host中

        self.port = port
        # 将传入的port参数保存到实例变量self.port中

        self.password = password if password else None
        # 如果password有值则使用password，否则设为None（空字符串也转为None）

        self.client = None
        # 初始化Redis客户端对象为None，连接成功后会被赋值

        self.enabled = False
        # 添加enabled属性，标记Redis是否可用，初始为False

    def connect(self) -> bool:
        # 定义连接方法，返回布尔值表示连接是否成功

        if redis is None:
            # 如果redis模块未导入成功（为None）

            print("[WARN] redis 模块未安装，跳过 Redis 连接")
            # 打印警告信息，提示模块未安装

            self.enabled = False
            # 设置enabled为False

            return False
            # 返回False表示连接失败

        try:
            # 尝试执行连接操作，捕获可能的异常

            print(f"[INFO] 连接 Redis: {self.host}:{self.port}")
            # 打印正在连接的信息，显示主机和端口

            # 构建连接参数
            connection_params = {
                # 创建参数字典
                'host': self.host,
                # Redis服务器地址
                'port': self.port,
                # Redis端口
                'decode_responses': True,
                # 自动将响应从字节串解码为字符串
                'socket_connect_timeout': 5,
                # 连接超时时间（秒）
                'socket_timeout': 5,
                # 读写操作超时时间（秒）
                'retry_on_timeout': True,
                # 超时后是否重试
                'health_check_interval': 30
                # 健康检查间隔时间（秒）
            }

            # 如果有密码，添加密码参数
            if self.password:
                # 如果password不为空

                connection_params['password'] = self.password
                # 将密码添加到参数字典中

            self.client = redis.Redis(**connection_params)
            # 创建Redis客户端对象，使用**将参数字典解包传入

            # 测试连接
            self.client.ping()
            # 发送PING命令测试连接是否正常，如果连接失败会抛出异常

            # 获取 Redis 信息
            redis_info = self.client.info('server')
            # 获取Redis服务器信息，指定'server'部分

            redis_version = redis_info.get('redis_version', 'unknown')
            # 从服务器信息中获取redis版本号，如果不存在则使用'unknown'

            self.enabled = True
            # 连接成功，将enabled设为True

            print(f"[OK] Redis 连接成功 | 版本: {redis_version} | 地址: {self.host}:{self.port}")
            # 打印连接成功信息，显示版本和地址

            return True
            # 返回True表示连接成功

        except redis.exceptions.ConnectionError as e:
            # 捕获连接错误异常（如无法连接到服务器）

            print(f"[WARN] Redis 连接失败: 无法连接到 {self.host}:{self.port}")
            # 打印连接失败信息，显示地址和端口

            print(f"   错误详情: {e}")
            # 打印具体的错误详情

            print("   提示: 请检查 1) Redis 服务是否启动 2) 网络是否连通 3) 防火墙设置")
            # 给出排查建议

            self.client = None
            # 清空客户端对象

            self.enabled = False
            # 设置enabled为False

            return False
            # 返回False表示连接失败

        except redis.exceptions.AuthenticationError as e:
            # 捕获认证错误异常（密码错误）

            print("[WARN] Redis 认证失败: 密码错误")
            # 打印认证失败信息

            print("   提示: 请检查 REDIS_PASSWORD 配置是否正确")
            # 提示检查密码配置

            self.client = None
            # 清空客户端对象

            self.enabled = False
            # 设置enabled为False

            return False
            # 返回False表示连接失败

        except Exception as e:
            # 捕获其他所有异常

            print(f"[WARN] Redis 连接失败: {e}")
            # 打印失败信息和错误详情

            self.client = None
            # 清空客户端对象

            self.enabled = False
            # 设置enabled为False

            return False
            # 返回False表示连接失败

    def set(self, key: str, value: str, expire: int = None) -> bool:
        # 设置键值对方法
        # key: 键名
        # value: 键值
        # expire: 过期时间（秒），默认None表示永不过期
        # 返回布尔值表示操作是否成功

        if not self.client or not self.enabled:
            # 如果客户端不存在或未启用

            return False
            # 返回False表示操作失败

        try:
            # 尝试执行设置操作

            self.client.set(key, value)
            # 使用Redis的SET命令存储键值对

            if expire:
                # 如果指定了过期时间

                self.client.expire(key, expire)
                # 设置键的过期时间（秒）

            return True
            # 返回True表示操作成功

        except Exception as e:
            # 捕获任何异常

            print(f"Redis set 失败: {e}")
            # 打印失败信息和错误详情

            return False
            # 返回False表示操作失败

    def get(self, key: str) -> str:
        # 获取键值方法
        # key: 键名
        # 返回键对应的值（字符串），如果失败或不存在返回None

        if not self.client or not self.enabled:
            # 如果客户端不存在或未启用

            return None
            # 返回None

        try:
            # 尝试执行获取操作

            return self.client.get(key)
            # 使用Redis的GET命令获取键值，并直接返回

        except Exception as e:
            # 捕获任何异常

            print(f"Redis get 失败: {e}")
            # 打印失败信息和错误详情

            return None
            # 返回None

    def delete(self, key: str) -> bool:
        # 删除键方法
        # key: 要删除的键名
        # 返回布尔值表示删除是否成功

        if not self.client or not self.enabled:
            # 如果客户端不存在或未启用

            return False
            # 返回False表示操作失败

        try:
            # 尝试执行删除操作

            return bool(self.client.delete(key))
            # 使用Redis的DELETE命令删除键，将返回值转为布尔值
            # delete()返回删除的键数量，1表示成功删除，0表示键不存在

        except Exception as e:
            # 捕获任何异常

            print(f"Redis delete 失败: {e}")
            # 打印失败信息和错误详情

            return False
            # 返回False表示操作失败

    def exists(self, key: str) -> bool:
        # 检查键是否存在方法
        # key: 键名
        # 返回布尔值表示键是否存在

        if not self.client or not self.enabled:
            # 如果客户端不存在或未启用

            return False
            # 返回False

        try:
            # 尝试执行检查操作

            return self.client.exists(key) > 0
            # 使用Redis的EXISTS命令，返回存在的键数量
            # 如果大于0表示键存在，返回True；否则返回False

        except Exception as e:
            # 捕获任何异常

            print(f"Redis exists 失败: {e}")
            # 打印失败信息和错误详情

            return False
            # 返回False

    def close(self):
        # 关闭连接方法

        if self.client:
            # 如果客户端对象存在

            self.client.close()
            # 关闭Redis连接

            print("[OK] Redis 连接已关闭")
            # 打印关闭成功的信息

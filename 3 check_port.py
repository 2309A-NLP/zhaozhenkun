# -*- coding: utf-8 -*-
"""检查所有服务是否正常运行"""
import socket
#导入python的底层网络通信库
#作用:用于检查端口是否开放 不依赖具体的服务协议
import redis
#导入redis的python的客户端库
#作用: 主动连接redis并进行功能测试
from pymilvus import connections
#从milvus的python客户端导入连接管理器
#作用:测试与milvus向量数据库的连接

def check_port(host, port, service_name):
    """检查端口是否开放"""
#定义一个函数接收三个参数
#host:服务器地址
#post:端口号
#service_name:服务名称 用于显示
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#含义:创建一个TCP套接字
#socket.AF_INET :使用IPv4地址族
#socket.SOCK_STREAM:使用TCP协议
        sock.settimeout(2)
#设置超市时间为2秒
#如果2秒内没有响应 就认为连接失败 避免程序长时间卡住
        result = sock.connect_ex((host, port))
#尝试连接到指定的主机和端口
#.connect_ex是connect的扩展版本
#关键区别connect失败会抛出异常 connect_ex()失败只返回错误码
        sock.close()
#关闭套接字 释放资源
        if result == 0:
            print(f"✅ {service_name} 运行中: {host}:{port}")
            return True
        else:
            print(f"❌ {service_name} 未运行: {host}:{port}")
            return False
#根据返回值判断服务状态
#  result == 0 端口开放 服务正在监听
# 其他值 端口未开放或服务未启动
    except Exception as e:
        print(f"❌ {service_name} 检查失败: {e}")
        return False
#捕获任何异常(如网络不可达)打印错误信息并返回_

def main():
    print("=" * 50)
    print("服务状态检查")
    print("=" * 50)
#打印分割线与标题
    # 检查Docker服务
    services_ok = True
    services_ok &= check_port('localhost', 19530, 'Milvus')
    services_ok &= check_port('localhost', 6379, 'Redis')
    services_ok &= check_port('localhost', 3306, 'MySQL')
#services_ok = True:初始化状态
#&= 按位与赋值操作符
#任何一个服务检查失败 services_ok就会变成False
#这种写法会依次检查所有服务(不会因为第一个失败就停止)
#检查三个服务
#milvus:向量数据库 默认端口:19530
#redis:内存数据库/缓存 默认端口:6379
#mysql:关系型数据库 默认端口:3306
    if not services_ok:
        print("\n⚠️  部分服务未启动，请运行:")
        print("   docker-compose up -d")
        return False
#如果端口检查有失败 提示用户启动Docker服务并退出函数
#docker-compose up -d 在后台启动Docker Compose定义的所有服务
    # 测试Redis连接
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✅ Redis 连接测试成功")
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        services_ok = False
#redis.Redis 创建redis客户端对象
#decode_responses=True 自动将返回字节数据解码为字符串
#r.ping向redis发送PING命令
#正常工作会返回True
#这是redis的标准健康检查方式 比端口检查更可靠
#services_ok = False如果连接失败 将状态标志设为False

    # 测试Milvus连接
    try:
        connections.connect(alias="default", host='localhost', port='19530')
        print("✅ Milvus 连接测试成功")
        connections.disconnect("default")
    except Exception as e:
        print(f"❌ Milvus 连接失败: {e}")
        services_ok = False

    return services_ok
    #返回最终的检查结果(True表示所有服务正常)

#connections.connect 建立与milvus服务器的连接
#alias="default 给这个连接起个别名叫default 方便后续引用
#host和port指定服务器地址和端口
# connections.disconnect("default")断开连接 释放资源

if __name__ == "__main__":
    if main():
        print("\n🎉 所有服务正常！可以开始创建向量索引")
    else:
        print("\n请先启动Docker服务")
#直接运行脚本时执行
#如果返回True显示成功信息 提示可以继续操作
#如果返回False显示错误信息 提示启动Docker
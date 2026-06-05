# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
"""
检查所有服务是否正常运行，验证RAG系统所需的基础服务是否正常运行。

本模块通过TCP端口扫描和客户端连接测试两种方式，
依次检查Milvus(19530)、Redis(6379)、MySQL(3306)三个核心服务是否就绪。
"""
import socket   # 导入socket库，用于底层TCP端口检查（不依赖具体服务协议）
import redis   # 导入Redis的Python客户端库，用于主动连接Redis并进行功能测试
from pymilvus import connections   # 从pymilvus导入连接管理器，用于测试与Milvus向量数据库的连接


def check_port(host, port, service_name):   # 定义端口检查函数，接收主机、端口、服务名称三个参数
    """检查端口是否开放"""   # 函数文档字符串
    try:   # 开始异常捕获
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # 创建一个TCP套接字（IPv4 + TCP协议）
        sock.settimeout(2)   # 设置超时时间为2秒，避免长时间阻塞
        result = sock.connect_ex((host, port))   # 尝试连接指定主机和端口，返回错误码（非阻塞版本）
        sock.close()   # 关闭套接字，释放系统资源
        if result == 0:   # 如果返回值为0，表示连接成功，端口开放
            print(f"✅ {service_name} 运行中: {host}:{port}")   # 打印服务运行中的成功信息
            return True   # 返回True表示服务正常
        else:   # 如果返回值非0，表示连接失败，端口未开放
            print(f"❌ {service_name} 未运行: {host}:{port}")   # 打印服务未运行的失败信息
            return False   # 返回False表示服务异常
    except Exception as e:   # 捕获任何异常（如网络不可达）
        print(f"❌ {service_name} 检查失败: {e}")   # 打印异常信息
        return False   # 返回False表示检查失败


def main():   # 定义主函数
    """主函数：依次检查所有依赖服务的端口和连接状态"""   # 函数文档字符串
    print("=" * 50)   # 打印50个等号作为分隔线
    print("服务状态检查")   # 打印标题
    print("=" * 50)   # 打印50个等号作为分隔线

    # 检查Docker服务   # 注释：使用端口扫描检查三个核心服务
    services_ok = True   # 初始化服务状态标志为True
    services_ok &= check_port('localhost', 19530, 'Milvus')   # 检查Milvus向量数据库（默认端口19530）
    services_ok &= check_port('localhost', 6379, 'Redis')   # 检查Redis缓存数据库（默认端口6379）
    services_ok &= check_port('localhost', 3306, 'MySQL')   # 检查MySQL关系型数据库（默认端口3306）
    # 使用&=操作符依次累加检查结果，只要有一个失败，services_ok就变成False

    if not services_ok:   # 如果有任何一个服务端口检查失败
        print("\n⚠️  部分服务未启动，请运行:")   # 提示用户部分服务未启动
        print("   docker-compose up -d")   # 提示运行Docker Compose命令启动服务
        return False   # 返回False

    # 测试Redis连接   # 注释：进行更深入的Redis功能测试（PING命令）
    try:   # 开始异常捕获
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)   # 创建Redis客户端，自动解码响应为字符串
        r.ping()   # 发送PING命令测试连接是否正常（比端口检查更可靠）
        print("✅ Redis 连接测试成功")   # 打印成功信息
    except Exception as e:   # 如果连接或PING失败
        print(f"❌ Redis 连接失败: {e}")   # 打印失败信息
        services_ok = False   # 将状态标志设为False

    # 测试Milvus连接   # 注释：进行更深入的Milvus功能测试
    try:   # 开始异常捕获
        connections.connect(alias="default", host='localhost', port='19530')   # 建立与Milvus服务器的连接
        print("✅ Milvus 连接测试成功")   # 打印成功信息
        connections.disconnect("default")   # 断开连接，释放资源
    except Exception as e:   # 如果连接失败
        print(f"❌ Milvus 连接失败: {e}")   # 打印失败信息
        services_ok = False   # 将状态标志设为False

    return services_ok   # 返回最终的检查结果（True表示所有服务正常）


if __name__ == "__main__":   # 判断是否直接运行此脚本（而非被导入）
    if main():   # 调用主函数并检查返回值
        print("\n🎉 所有服务正常！可以开始创建向量索引")   # 所有服务正常，打印成功信息
    else:   # 如果有服务异常
        print("\n请先启动Docker服务")   # 提示需要先启动Docker服务

# 这里定义接口测试脚本。
import io
import json

from app import create_app


def main():
    # 这里创建应用实例。
    app = create_app()
    # 这里创建测试客户端。
    client = app.test_client()
    # 这里执行健康检查。
    health = client.get('/api/health').json
    # 这里执行 DeepSeek 文本检索。
    search = client.post('/api/search', json={'query': '故宫历史', 'input_type': 'text', 'language': 'zh', 'mode': 'history', 'provider': 'deepseek'}).json
    # 这里执行千问文本检索。
    qwen_search = client.post('/api/search', json={'query': '西湖故事', 'input_type': 'text', 'language': 'zh', 'mode': 'story', 'provider': 'qwen'}).json
    # 这里模拟上传一张图片并执行千问多模态检索。
    image_search = client.post('/api/image-search', data={'query': '这是什么景点', 'hints': '红墙 宫殿 古建筑', 'provider': 'qwen', 'image': (io.BytesIO(b'fake-image-bytes'), 'demo.png')}, content_type='multipart/form-data').json
    # 这里打印结果，方便核对。
    print(json.dumps({'health': health, 'search': search, 'qwen_search': qwen_search, 'image_search': image_search}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    # 这里运行主函数。
    main()

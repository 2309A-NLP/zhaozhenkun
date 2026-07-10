import json
from app import create_app

app = create_app()
client = app.test_client()

result = {
    "health": client.get('/api/health').json,
    "search": client.post('/api/search', json={
        'query': '故宫历史',
        'input_type': 'text',
        'language': 'zh',
        'mode': 'history'
    }).json,
    "image_search": client.post('/api/image-search', json={
        'hints': '红墙 宫殿 古建筑'
    }).json,
}
print(json.dumps(result, ensure_ascii=False, indent=2))

# 部署说明补充

## DeepSeek 与千问接入方式
本项目已经内置两个模型提供方：
1. DeepSeek：适合文本讲解增强
2. 千问兼容接口：适合文本增强与真实图片上传多模态识别

## 本地实装能力
1. OCR：tesseract + pytesseract
2. TTS：espeak 生成 wav 音频
3. 检索索引：faiss IndexFlatIP

## 环境变量
- DEEPSEEK_BASE_URL=https://api.deepseek.com
- DEEPSEEK_API_KEY=你的 DeepSeek 密钥
- DEEPSEEK_MODEL=deepseek-chat
- QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
- QWEN_API_KEY=你的千问密钥
- QWEN_MODEL=qwen-vl-max
- FLASK_PORT=5057

## 页面功能
1. 文本检索区：可选择 DeepSeek 或 千问
2. 图片多模态区：支持真实图片上传
3. 图片上传后会进入 OCR + 多模态理解链路
4. 返回结果附带真实 wav 语音播报 base64 字段

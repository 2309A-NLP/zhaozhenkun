工单18 智能助教部署说明
1. 执行：py -3 部署/write_secrets.py
2. 启动：py -3 部署/run_server.py
3. 如果 8018 端口被占用，可改端口启动：set EDU_AGENT_PORT=8028 && py -3 部署/run_server.py
4. 访问：首页 http://127.0.0.1:8018/
5. 演示账号：teacher01 / 123456，student01 / 123456
6. 前端模型切换：左侧“模型选择”区域支持 DeepSeek 与千问切换，图片上传默认优先走当前模型提供商。
7. 文件上传优先支持：PDF、TXT、MD、CSV、XLSX、DOCX、PPTX、PNG、JPG、JPEG、BMP、WEBP。
8. 旧版 DOC / PPT / XLS 会返回清晰提示，建议先转换为 DOCX / PPTX / XLSX 后再上传。
9. 如果当前 Python 环境缺少依赖，请先执行：python -m pip install fastapi uvicorn requests pypdf openpyxl python-multipart
10. 测试执行：py -3 -m pytest 测试/test_app.py -q

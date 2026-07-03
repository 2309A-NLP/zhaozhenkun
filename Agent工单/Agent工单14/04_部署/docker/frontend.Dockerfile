# 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
# 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
FROM nginx:alpine
COPY ../../02_研发/frontend /usr/share/nginx/html
RUN echo 'server { \
    listen 80; \
    location / { root /usr/share/nginx/html; index index.html; try_files $uri /index.html; } \
    location /api/ { proxy_pass http://backend:8000/api/; proxy_http_version 1.1; proxy_set_header Host $host; } \
}' > /etc/nginx/conf.d/default.conf
EXPOSE 80

FROM nginx:alpine
# build context 已经指向 02_研发/frontend，直接 COPY 当前目录
COPY . /usr/share/nginx/html
RUN echo 'server { \
    listen 80; \
    location / { root /usr/share/nginx/html; index index.html; try_files $uri /index.html; } \
    location /api/ { proxy_pass http://backend:8080/api/; proxy_http_version 1.1; proxy_set_header Host $host; } \
}' > /etc/nginx/conf.d/default.conf
EXPOSE 80

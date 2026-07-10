# 工单19部署说明

## 一、运行环境
- Python 3.10 及以上
- 已安装 Flask
- 如需真实模型生成，需要可访问 DeepSeek API 的网络环境

## 二、建议安装命令
```bash
pip install flask
```

## 三、启动方式
在 `研发/source` 目录执行：
```bash
py -3.12 app.py
```

启动后访问：
- 首页：`http://127.0.0.1:5050/`
- 健康检查：`http://127.0.0.1:5050/api/health`

## 四、DeepSeek 配置
项目会自动读取 `部署/.env` 中的以下配置：
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- `DEEPSEEK_TIMEOUT_SECONDS`
- `DEEPSEEK_COOLDOWN_SECONDS`

如果未配置密钥，或仍保留示例值 `your_api_key_here`，系统会自动回退到本地模板生成结果。
若已配置真实密钥但网络不可达或模型响应过慢，系统会在超时后自动回退，并在短时间内快速熔断后续模型请求，避免首页与导出链路长时间阻塞。

## 五、高德地图配置
项目首页地图路线功能会自动读取 `部署/.env` 中的以下配置：
- `AMAP_WEB_KEY`
- `AMAP_SECURITY_CODE`

配置完成后，首页可基于浏览器定位权限展示“当前位置 -> 当前景点”的真实路线、距离与预计时长。

## 六、浏览器权限说明
- 首次点击“定位并规划”时，浏览器需要允许定位权限。
- 如果浏览器拒绝定位，地图区域会提示重新授权，但不会影响策划、内容、推荐与导出功能。
- 地图脚本依赖外网加载高德 JS API，因此运行环境需要可访问高德地图静态资源。

## 七、可选环境变量
- `DEBUG`
- `HOST`
- `PORT`
- `DEFAULT_CITY`
- `DEFAULT_THEME`
- `MAP_DEFAULT_ZOOM`

## 八、目录说明
- `设计/`：需求、架构、接口与 PDF 验收矩阵文档
- `研发/`：源码与数据
- `测试/`：测试用例、测试结果、页面截图、下载样例
- `部署/`：部署说明与环境变量示例
- `优化/`：优化建议

## 九、提交前检查
- 不要提交 `部署/.env`，仓库已通过 `.gitignore` 忽略真实密钥配置。
- 不要提交 `测试/chrome-profile/` 与 `测试/chrome-profile-recheck-cdp/` 等浏览器运行时目录。
- 首次交付时建议复制 `部署/.env.example` 为本地 `部署/.env` 后再填写真实密钥。
- 如仅做离线演示，可不填 DeepSeek 密钥，系统会自动回退到本地模板结果。

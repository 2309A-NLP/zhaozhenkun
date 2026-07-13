# 工单19 最终交付说明

## 一、项目功能
- 学生学习画像诊断
- 基于知识图谱的学习路径推荐
- 今日学习任务自动生成
- 自适应练习推荐
- AIGC 错题本与变式题生成
- 推荐资源与学习趋势展示

## 二、真实模型接入
1. 复制 `.env.local.example` 为 `.env.local`
2. 按需填写：
   - `MODEL_PROVIDER=deepseek` 或 `qwen`
   - `DEEPSEEK_API_KEY=你的密钥`
   - `QWEN_API_KEY=你的密钥`
3. 启动项目：`py main.py`
4. 未配置真实密钥时，系统自动回退到本地错题解析逻辑

## 三、运行方式
- 安装依赖：`pip install -r requirements.txt`
- 启动项目：`py main.py`
- 访问地址：`http://127.0.0.1:5000/`

## 四、目录说明
- `design/`：设计说明
- `development/`：研发代码
- `tests/`：测试代码
- `deploy/`：部署与打包脚本
- `optimization/`：优化建议

## 五、提交建议
- 不要提交 `.env.local`
- 不要提交 `*.db`、`__pycache__`、`app.log`
- 可直接提交本目录压缩包

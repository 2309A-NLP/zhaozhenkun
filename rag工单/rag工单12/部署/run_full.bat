@echo off
chcp 65001 >nul
cd /d "C:\Users\31326\Desktop\rag工单12"
echo ============================================================
echo  LightRAG 全流程启动
echo ============================================================
echo.
echo Step 1-3: PDF解析 + 分块 + BGE-M3编码（从缓存加载）
echo Step 4: 实体/关系提取（200个chunk，约10分钟）
echo Step 5: 知识图谱构建
echo Step 6-7: 双模式检索 + 问答生成（16题）
echo Step 8: RAGAS评估对比
echo.
echo 开始时间：%date% %time%
echo.
python run.py
echo.
echo 完成时间：%date% %time%
pause

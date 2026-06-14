# DeepDoc 解析器缓存分析

## 现状

DeepDoc OCR模型加载位于 `deepdoc/vision/ocr.py`:

```python
# line 36: 模块级缓存字典
loaded_models = {}

# line 71-79: 带缓存的加载函数
def load_model(model_dir, nm, device_id=None):
    model_cached_tag = model_file_path + str(device_id)
    global loaded_models
    loaded_model = loaded_models.get(model_cached_tag)
    if loaded_model:
        logging.info(f"load_model reuses cached model")
        return loaded_model
    # ... 加载ONNX模型到GPU/CPU
```

## 分析结论

1. **已有缓存**: DeepDoc ONNX模型已通过 `loaded_models` 字典实现模块级缓存
2. **使用方式**: PdfParser/RAGFlowExcelParser通过类方法调用（非实例化），`task_service.py:392`
3. **缓存范围**: 单进程内（每个TaskExecutor worker独立缓存）
4. **GPU内存**: 模型加载到ONNX Runtime，GPU内存受 `OCR_GPU_MEM_LIMIT_MB` 控制（默认2048MB）

## 优化建议

1. 设置合理的环境变量限制GPU内存:
   - `OCR_GPU_MEM_LIMIT_MB=1024` (限制1GB)
   - `OCR_INTRA_OP_NUM_THREADS=2`
   - `OCR_GPU_MEM_ARENA_SHRINKAGE=1` (启用内存回收)

2. 预加载模型: 在TaskExecutor启动时调用一次 `PdfParser.total_page_number()` 触发模型加载
